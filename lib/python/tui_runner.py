"""Run supervision: tail the engine's JSON-lines event file, keep a tolerant
model of groups/items/prompts, and split PTY output into per-group log
blocks. Nothing here blocks; every read is incremental and bounded.
"""
import json
import os
import re
import time

from tui_widgets import ANSI

GROUP_ORDER = ('prescan', 'appstore', 'cli', 'brew', 'internet', 'inventory', 'system')
LEGACY_GROUPS = {'npmcli': 'cli', 'npm': 'cli', 'postupdate': 'inventory', 'scan': 'prescan', 'app_store': 'appstore'}
ITEM_RESULTS = ('updated', 'current', 'needs_you', 'failed', 'skipped', 'available', 'unchecked')   # available, unchecked: only in a preview
PHASES = ('checking', 'downloading', 'verifying', 'installing', 'waiting')
PHASE_STEP = dict(checking=0.25, downloading=0.5, verifying=0.75, installing=0.9, waiting=0.5)


def item_fraction(item):
    """Real percent when the engine sends one, else a stepped value per phase."""
    if item.result:
        return 1.0
    if item.percent is not None:
        return item.percent / 100.0
    return PHASE_STEP.get(item.phase, 0.25)
# Machine reasons an engine may attach to item_end (field ``reason``); each has
# a localized sentence (ui_reason_<code>) and suggested action (ui_reason_<code>_do).
REASON_CODES = ('app_running', 'signin_required', 'needs_password', 'needs_restart', 'no_method', 'checksum_mismatch',
                'download_failed', 'feed_unreachable', 'manual_mode', 'major_upgrade_blocked', 'disk_low',
                'battery_low', 'timeout', 'vendor_updater_opened', 'still_installing', 'updater_unconfirmed',
                'store_not_offered', 'preview_unchecked', 'vendor_update_pending', 'teams_via_own_updater', 'requirement_missing', 'blocked_by_login_items', 'unknown')
MAX_LINE = 65536
MAX_LOG_LINES = 5000
YESNO = re.compile(r'\[(y/n|Y/n|y/N|Y/N)\]|\((y/n|Y/n|y/N)\)|\b(yes/no)\b', re.I)


def _group_result(text):
    text = str(text or '')
    if text in ('ok', 'updated', 'current', 'completed', 'success'):
        return 'ok'
    if text in ('warn', 'warning', 'warnings', 'needs_you', 'unconfirmed', 'partial'):
        return 'warn'
    if text in ('failed', 'error', 'fail'):
        return 'failed'
    if text in ('skipped', 'skipped_by_user', 'off', 'disabled'):
        return 'off'
    return 'ok' if not text else 'unknown'


class Item:
    __slots__ = ('id', 'name', 'source', 'from_v', 'to_v', 'phase', 'percent', 'result', 'detail', 'reason', 'started',
                 'ended')

    def __init__(self, ident, name=''):
        self.id, self.name = ident, name or ident
        self.source = self.from_v = self.to_v = self.detail = self.reason = ''
        self.phase, self.percent, self.result = 'checking', None, None
        self.started, self.ended = time.monotonic(), None


class Group:
    def __init__(self, ident, enabled=True):
        self.id = ident
        self.enabled = enabled
        self.state = 'pending' if enabled else 'off'     # pending | running | done | off
        self.result = None                               # ok | warn | failed | off | unknown
        self.total = None
        self.items = {}
        self.order = []
        self.counts = dict(updated=0, current=0, needs_you=0, failed=0, skipped=0, available=0, unchecked=0)
        self.started = self.ended = None
        self.seconds = None
        self.from_events = False

    def finished(self):
        return sum(1 for i in self.items.values() if i.result)

    def known_total(self):
        """Total from group_start/group_total; never below the items seen."""
        if self.total is None:
            return None
        return max(self.total, self.finished())

    def fraction(self):
        """Finished items / total. None only while running without a total."""
        if self.state in ('done', 'off'):
            return 1.0
        if self.state != 'running':
            return 0.0
        total = self.known_total()
        if total:
            return min(1.0, self.finished() / float(total))
        if total == 0:
            return 1.0
        return None

    def elapsed(self, now=None):
        if self.seconds is not None:
            return self.seconds
        if self.started is None:
            return None
        return (self.ended or now or time.monotonic()) - self.started

    def item(self, ident, name=''):
        if ident not in self.items:
            self.items[ident] = Item(ident, name)
            self.order.append(ident)
        elif name:
            self.items[ident].name = name
        return self.items[ident]


class RunModel:
    def __init__(self, groups_enabled=GROUP_ORDER, dry_run=False):
        self.dry_run = dry_run
        self.groups = {g: Group(g, g in groups_enabled) for g in GROUP_ORDER}
        self.started = time.monotonic()
        self.ended = None
        self.result = None           # ok | failed | stopped | unknown
        self.summary = None
        self.version = None
        self.prompt = None           # dict from a prompt event (or detected)
        self.answered = set()
        self.last_event = None
        self.events_seen = 0
        self.prompt_events = 0
        self.active = None
        self.from_history = False

    # -- events --------------------------------------------------------------
    def handle(self, event):
        if not isinstance(event, dict) or not isinstance(event.get('type'), str):
            return
        kind = event['type']
        self.events_seen += 1
        self.last_event = time.monotonic()
        group = self._group(event.get('group'))
        if kind == 'run_start':
            self.version = str(event.get('version', ''))[:32]
            listed = event.get('groups')
            if isinstance(listed, list) and listed:
                for g in self.groups.values():
                    if g.id not in listed and g.state == 'pending':
                        g.state, g.enabled = 'off', False
        elif kind in ('group_start', 'group_total') and group:
            group.from_events = True
            total = event.get('total')
            if type(total) is int and total >= 0:
                group.total = total
            if kind == 'group_start':
                self._start_group(group)
        elif kind == 'item_start' and group:
            self._start_group(group)
            item = group.item(str(event.get('id', '?'))[:200], str(event.get('name', ''))[:200])
            item.source = str(event.get('source', '') or '')[:40]
            item.from_v = str(event.get('from', '') or '')[:40]
            item.to_v = str(event.get('to', '') or '')[:40]
            item.phase = 'checking'
        elif kind == 'item_progress' and group:
            self._start_group(group)
            item = group.item(str(event.get('id', '?'))[:200])
            phase = event.get('phase')
            if phase == 'waiting_for_app_updater':     # the app's own updater is working
                phase = 'waiting'
            if phase in PHASES:
                item.phase = phase
            pct = event.get('percent')
            if isinstance(pct, (int, float)) and not isinstance(pct, bool):
                item.percent = max(0.0, min(100.0, float(pct)))
        elif kind == 'item_end' and group:
            self._start_group(group)
            item = group.item(str(event.get('id', '?'))[:200], str(event.get('name', '') or '')[:200])
            result = event.get('result')
            if result not in ITEM_RESULTS:
                result = 'failed' if result in ('error', 'fail') else 'current'
            if result == 'current' and event.get('reason') == 'preview_unchecked' and self.dry_run:
                result = 'unchecked'       # the preview could not look at it: never counted as up to date
            if result == 'available' and not self.dry_run:
                result = 'needs_you'       # a real run never "would update"; something is off, so ask the user
            if item.result:
                group.counts[item.result] -= 1
            item.result = result
            item.ended = time.monotonic()
            item.percent = 100.0
            for key, attr in (('from', 'from_v'), ('to', 'to_v'), ('detail', 'detail')):
                if event.get(key):
                    setattr(item, attr, str(event[key])[:300])
            reason = event.get('reason')
            if isinstance(reason, str) and reason in REASON_CODES:
                item.reason = reason
            group.counts[result] += 1
        elif kind == 'group_end' and group:
            group.from_events = True
            self._end_group(group, _group_result(event.get('result')))
            for key in ('updated', 'current', 'needs_you', 'failed', 'available'):
                value = event.get(key)
                if key == 'available' and not self.dry_run:
                    continue
                if key == 'current' and type(value) is int and value >= 0:
                    value = max(0, value - sum(1 for i in group.items.values() if i.result == 'unchecked'))
                if type(value) is int and value >= 0:
                    group.counts[key] = value
            seconds = event.get('seconds')
            if isinstance(seconds, (int, float)) and not isinstance(seconds, bool) and seconds >= 0:
                group.seconds = float(seconds)
        elif kind == 'prompt':
            self.prompt_events += 1
            ident = str(event.get('id', '')) or 'prompt-%d' % self.events_seen
            if ident not in self.answered:
                options = event.get('options') if isinstance(event.get('options'), list) else []
                timeout = event.get('timeout')
                self.prompt = dict(id=ident, kind=event.get('kind') if event.get('kind') in ('yesno', 'sudo', 'choice') else 'yesno',
                                   text=str(event.get('text', ''))[:2000], options=[str(o)[:80] for o in options[:9]],
                                   default=str(event.get('default', '') or ''),
                                   timeout=timeout if isinstance(timeout, (int, float)) and not isinstance(timeout, bool) and timeout > 0 else None,
                                   opened=time.monotonic(), group=group.id if group else None)
        elif kind == 'prompt_end':
            # The engine emits this right after sudo returned: the password request is over.
            ident = str(event.get('id', ''))
            current = self.prompt
            if current is not None and (current['id'] == ident or (event.get('kind') or 'sudo') == current.get('kind')):
                self.prompt = None
            if ident:
                self.answered.add(ident)
        elif kind == 'run_end':
            self.finish(event.get('result'), event.get('seconds'), event.get('summary'))

    def _group(self, ident):
        ident = LEGACY_GROUPS.get(ident, ident)
        return self.groups.get(ident)

    def _start_group(self, group):
        if group.state in ('pending', 'off'):
            group.state, group.enabled = 'running', True
            group.started = time.monotonic()
        self.active = group.id
        # A group starting implies earlier running groups are over.
        for other in self.groups.values():
            if other is not group and other.state == 'running' and GROUP_ORDER.index(other.id) < GROUP_ORDER.index(group.id):
                self._end_group(other, other.result or 'ok')

    def _end_group(self, group, result):
        if group.started is None:
            group.started = time.monotonic()
        group.state = 'done' if result != 'off' else 'off'
        group.result = result
        group.ended = time.monotonic()
        if self.active == group.id:
            self.active = None

    def legacy_phase(self, key, status):
        """Handle ``@@MAC_UPDATE_PHASE key status`` lines from the PTY."""
        group = self._group(key)
        if group is None or group.from_events:
            return
        self.last_event = time.monotonic()
        if status == 'running':
            self._start_group(group)
        else:
            self._end_group(group, _group_result(status))

    def finish(self, result=None, seconds=None, summary=None, returncode=None, stopped=False):
        if self.ended is not None and result is None:
            return
        self.ended = time.monotonic()
        for group in self.groups.values():
            if group.state == 'running':
                self._end_group(group, 'failed' if (stopped or (returncode not in (None, 0))) else 'ok')
            elif group.state == 'pending':
                group.state = 'off' if stopped or not group.enabled else group.state
        if stopped:
            self.result = 'stopped'
        elif result is not None:
            self.result = {'ok': 'ok', 'success': 'ok', 'completed': 'ok', 'warn': 'warn', 'needs_you': 'warn'}.get(str(result), 'failed' if str(result) in ('failed', 'error') else 'ok')
        elif self.result is None:
            self.result = 'ok' if returncode in (0, None) else 'failed'
        if isinstance(summary, (dict, str)):
            self.summary = summary
        self.prompt = None

    # -- derived -------------------------------------------------------------
    def overall(self):
        """Weighted by groups: finished groups count fully, the active group by
        its fraction (0 while its total is unknown). Never moves backwards."""
        enabled = [g for g in self.groups.values() if g.enabled]
        if not enabled:
            value = 1.0
        else:
            value = sum((g.fraction() or 0.0) for g in enabled) / len(enabled)
        self._overall = max(getattr(self, '_overall', 0.0), value)
        return self._overall

    def counts(self):
        out = dict(updated=0, current=0, needs_you=0, failed=0, skipped=0, available=0, unchecked=0)
        for g in self.groups.values():
            for key in out:
                out[key] += g.counts.get(key, 0)
        return out

    def buckets(self):
        updated, current, needs = [], [], []
        for g in self.groups.values():
            for ident in g.order:
                item = g.items[ident]
                if item.result == 'updated':
                    updated.append((g.id, item))
                elif item.result == 'current':
                    current.append((g.id, item))
                elif item.result in ('needs_you', 'failed'):
                    needs.append((g.id, item))
        return updated, current, needs

    def available_items(self):
        """Items a preview found that would be updated, as (group id, item)."""
        return [(g.id, g.items[i]) for g in self.groups.values() for i in g.order if g.items[i].result == 'available']

    def unchecked_items(self):
        """Items a preview could not check (their own updater does), as (group id, item)."""
        return [(g.id, g.items[i]) for g in self.groups.values() for i in g.order if g.items[i].result == 'unchecked']

    def stalled(self, seconds=8.0):
        reference = self.last_event or self.started
        return time.monotonic() - reference > seconds


_SUMMARY_STEPS = {'prescan': 'prescan', 'scan': 'prescan', 'appstore': 'appstore', 'npmcli': 'cli', 'npm': 'cli',
                  'cli': 'cli', 'brew': 'brew', 'internet': 'internet', 'postupdate': 'inventory', 'inventory': 'inventory',
                  'system': 'system'}
_SUMMARY_CATEGORIES = {'appstore': 'appstore', 'app_store': 'appstore', 'background': 'appstore', 'brew': 'brew',
                       'cask': 'brew', 'formula': 'brew', 'brew_formula': 'brew', 'brew_cask': 'brew', 'npm_cli': 'cli',
                       'npm': 'cli', 'cli': 'cli', 'native': 'cli', 'internet': 'internet', 'system': 'system',
                       'macos': 'system'}
_SUMMARY_STATUS = {'updated': 'updated', 'current': 'current', 'current_verified': 'current', 'needs_you': 'needs_you',
                   'available': 'available', 'pending': 'needs_you', 'warning': 'needs_you', 'unconfirmed': 'needs_you', 'manual': 'needs_you',
                   'failed': 'failed', 'error': 'failed', 'skipped': 'skipped'}


def model_from_summary(summary):
    """Rebuild a finished RunModel from a saved run_summary JSON (format 4 and
    later); unknown fields are ignored so older and newer files both load."""
    model = RunModel()
    model.from_history = True
    if not isinstance(summary, dict):
        return model
    steps = summary.get('steps') if isinstance(summary.get('steps'), dict) else {}
    for key, step in steps.items():
        group = model.groups.get(_SUMMARY_STEPS.get(key, ''))
        if group is None or not isinstance(step, dict):
            continue
        result = _group_result(step.get('code'))
        group.enabled = True
        group.state = 'off' if result == 'off' else 'done'
        group.result = result
        group.started = group.ended = 0.0
        seconds = step.get('duration_seconds')
        group.seconds = float(seconds) if isinstance(seconds, int) and seconds >= 0 else None
    items = summary.get('items') if isinstance(summary.get('items'), list) else []
    for index, raw in enumerate(items[:2000]):
        if not isinstance(raw, dict):
            continue
        result = _SUMMARY_STATUS.get(str(raw.get('status', '')))
        group = model.groups.get(_SUMMARY_CATEGORIES.get(str(raw.get('category', raw.get('group', ''))), ''))
        if result is None or group is None:
            continue
        item = group.item(str(raw.get('id') or raw.get('name') or index)[:200], str(raw.get('name') or '')[:200])
        item.result = result
        item.from_v = str(raw.get('old_version') or raw.get('from') or '')[:40]
        item.to_v = str(raw.get('new_version') or raw.get('to') or '')[:40]
        item.detail = str(raw.get('details') or raw.get('detail') or '')[:300]
        reason = raw.get('reason')
        item.reason = reason if reason in REASON_CODES else ''
        group.counts[result] += 1
        if group.state == 'pending':
            group.state, group.result, group.enabled = 'done', 'ok', True
    status = summary.get('run_status')
    model.result = {'completed': 'ok', 'failed': 'failed', 'interrupted': 'stopped'}.get(status, 'unknown')
    if model.result == 'ok' and (summary.get('exit_class') not in (None, 'ok', 'clean', 'success')
                                 or any(g.result in ('warn', 'failed') for g in model.groups.values())):
        model.result = 'warn'
    duration = summary.get('duration_seconds')
    model.started = 0.0
    model.ended = float(duration) if isinstance(duration, int) and duration >= 0 else 0.0
    model.dry_run = bool((summary.get('flags') or {}).get('dry_run')) if isinstance(summary.get('flags'), dict) else False
    if not model.dry_run:
        for group in model.groups.values():
            for item in group.items.values():
                if item.result == 'available':
                    item.result = 'needs_you'
                    group.counts['available'] -= 1
                    group.counts['needs_you'] += 1
    return model


class EventTailer:
    """Incremental reader for a JSON-lines file that may not exist yet."""

    def __init__(self, path):
        self.path = path
        self.offset = 0
        self.partial = b''

    def read(self, limit=262144):
        events = []
        try:
            with open(self.path, 'rb') as handle:
                handle.seek(self.offset)
                data = handle.read(limit)
        except OSError:
            return events
        if not data:
            return events
        self.offset += len(data)
        data = self.partial + data
        lines = data.split(b'\n')
        self.partial = lines.pop()
        if len(self.partial) > MAX_LINE:
            self.partial = b''
        for raw in lines:
            if not raw.strip() or len(raw) > MAX_LINE:
                continue
            try:
                value = json.loads(raw.decode('utf-8', 'replace'))
            except ValueError:
                continue
            if isinstance(value, dict) and isinstance(value.get('type'), str):
                events.append(value)
        return events


# Variation selector 16 asks for emoji presentation; terminals disagree on whether
# "⬇️" takes one cell or two, which shifted the text after it and clipped the next
# letter. The log shows the plain one-cell symbol instead.
VS16 = '️'


class LogBuffer:
    """Turns PTY text into lines, grouped into per-step blocks.

    Engine control lines (``@@MAC_UPDATE_...``) are removed from the visible
    log and returned to the caller as directives."""

    def __init__(self):
        self.blocks = [[None, []]]      # [group id or None, lines]
        self.partial = ''
        self.last_output = time.monotonic()
        self.count = 0

    def begin(self, group):
        if self.blocks[-1][0] != group:
            if not self.blocks[-1][1] and self.blocks[-1][0] is None:
                self.blocks[-1][0] = group
            else:
                self.blocks.append([group, []])

    def feed(self, text):
        directives = []
        if not text:
            return directives
        self.last_output = time.monotonic()
        text = self.partial + text.replace('\r\n', '\n')
        parts = text.split('\n')
        self.partial = parts.pop()
        if '\r' in self.partial:
            self.partial = self.partial.rsplit('\r', 1)[-1]
        if len(self.partial) > 4000:
            parts.append(self.partial)
            self.partial = ''
        for line in parts:
            if '\r' in line:
                line = line.rstrip('\r').rsplit('\r', 1)[-1]
            line = ANSI.sub('', line)
            line = ''.join(c for c in line if c.isprintable() or c == '\t').replace('\t', '    ')
            line = line.replace(VS16, '')
            if line.startswith('@@MAC_UPDATE_'):
                directives.append(line)
                continue
            self.blocks[-1][1].append(line)
            self.count += 1
        if self.count > MAX_LOG_LINES:
            drop = self.count - MAX_LOG_LINES
            while drop > 0 and self.blocks:
                lines = self.blocks[0][1]
                cut = min(drop, len(lines))
                del lines[:cut]
                drop -= cut
                self.count -= cut
                if not lines and len(self.blocks) > 1:
                    self.blocks.pop(0)
        return directives

    def visible_partial(self):
        return ''.join(c for c in ANSI.sub('', self.partial) if c.isprintable()).replace(VS16, '')

    def all_lines(self):
        out = []
        for _, lines in self.blocks:
            out.extend(lines)
        partial = self.visible_partial()
        if partial.strip():
            out.append(partial)
        return out

    def last_line(self, settle=0.5):
        """Newest line for the status bar. An unfinished line is shown only once
        output has paused for ``settle`` seconds (a prompt, say); mid-write it
        would flash fragments such as "Vendor feed ChatGPT / Codex: fetc"."""
        partial = self.visible_partial().strip()
        if partial and time.monotonic() - self.last_output >= settle:
            return partial
        for _, lines in reversed(self.blocks):
            for line in reversed(lines):
                if line.strip():
                    return line.strip()
        return ''


# The engine's own plain-text overall bar ("[████████░░░░] 66% overall"); the Dashboard already shows Overall.
PROGRESS_LINE = re.compile(r'^\[[█░▓▒#=\-. ]{4,}\]\s*\d{1,3}%')

_BOX = set('║│┃|╔╗╚╝╠╣═─━┌┐└┘├┤╭╮╰╯┏┓┗┛▔▁=*#~_+-')


def clean_log_line(line):
    """Strip decorative box-drawing frames; None for pure banner lines."""
    text = line.strip()
    if PROGRESS_LINE.match(text):
        return None
    while text and text[0] in _BOX:
        text = text[1:].lstrip()
    while text and text[-1] in _BOX:
        text = text[:-1].rstrip()
    if not any(ch.isalnum() for ch in text):
        return None if line.strip() else ''
    return text if line.strip() != text else line.rstrip()


def wrap_log(lines, width, indent='  '):
    """Clean and wrap log lines to ``width``; continuation lines are indented."""
    from tui_widgets import wrap
    out = []
    for line in lines:
        text = clean_log_line(line)
        if text is None:
            continue
        parts = wrap(text, max(8, width - len(indent) - 2)) or ['']
        out.append(indent + parts[0])
        out.extend(indent + '  ' + part for part in parts[1:])
    return out


def detect_prompt(log, secret_input, idle, allow_yesno=True):
    """Fallback for engines without prompt events: guess from the PTY state."""
    partial = log.visible_partial().strip()
    if secret_input and idle >= 0.3:
        return dict(id='pty-sudo', kind='sudo', text=partial[:300], options=[], default='', timeout=None,
                    opened=time.monotonic(), group=None, detected=True)
    if allow_yesno and partial and idle >= 0.6:
        match = YESNO.search(partial)
        if match:
            token = match.group(0)
            default = 'y' if 'Y' in token and 'N' not in token else ('n' if 'N' in token else '')
            return dict(id='pty-yesno', kind='yesno', text=partial[:300], options=['y', 'n'], default=default,
                        timeout=None, opened=time.monotonic(), group=None, detected=True)
    return None


def parse_directive(line):
    """Return (kind, payload) for engine control lines."""
    match = re.match(r'@@MAC_UPDATE_PHASE ([a-z_]+) ([a-z_]+)\s*$', line)
    if match:
        return 'phase', (match.group(1), match.group(2))
    if line.startswith('@@MAC_UPDATE_TOOLKIT '):
        try:
            value = json.loads(line[len('@@MAC_UPDATE_TOOLKIT '):])
            return ('toolkit', value) if isinstance(value, dict) else ('ignored', None)
        except ValueError:
            return 'ignored', None
    if line.startswith('@@MAC_UPDATE_PROMPT'):
        return 'prompt', None
    return 'ignored', None


def private_event_path():
    import tempfile
    directory = tempfile.mkdtemp(prefix='mac-update-tui-')
    os.chmod(directory, 0o700)
    return os.path.join(directory, 'events.jsonl')
