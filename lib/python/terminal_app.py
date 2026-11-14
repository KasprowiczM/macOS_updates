"""Three-panel terminal workspace. Rendering never grants execution authority."""
import curses
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

from tui_backend import ACTIONS, GROUPS, TerminalJob, build_command, load_settings, recent_runs, save_settings
from tui_i18n import LANGUAGES, tr
from inventory_store import StoreError
from tui_recovery import handoff

VIEWS = ('home', 'updates', 'inventory', 'catalog', 'diagnostics', 'history', 'settings', 'wizard', 'help')
STEPS = ('welcome', 'requirements', 'inventory', 'sources', 'settings', 'preview', 'finish')
VIEW_ACTIONS = {
    'home': ('preview', 'update', 'doctor'),
    'updates': ('preview', 'update', 'preferences'),
    'inventory': ('inventory', 'migration_preview', 'coverage'),
    'catalog': ('catalog', 'sources', 'coverage'),
    'diagnostics': ('doctor', 'setup_inspect', 'coverage'),
}
STEP_ACTIONS = {'requirements': ('setup_inspect', 'setup_dependencies'),
                'inventory': ('inventory', 'migration_preview'),
                'sources': ('sources', 'catalog', 'preferences'),
                'settings': ('setup_shell',), 'preview': ('preview',)}
ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
NATIVE_NAMES = {'en': 'English', 'pl': 'Polski', 'de': 'Deutsch', 'es': 'Español',
                'fr': 'Français', 'it': 'Italiano', 'pt': 'Português'}


def plain(value):
    """Do not let process output or metadata issue terminal control sequences."""
    value = ANSI.sub('', str(value))
    return unicodedata.normalize('NFC', ''.join(c for c in value if c.isprintable() or c in '\n\t'))


def cell_width(text):
    return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1
               for c in plain(text))


def clip(text, width):
    result, used = [], 0
    for c in plain(text).replace('\n', ' ').replace('\t', ' '):
        size = 0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1
        if used + size > max(0, width):
            break
        result.append(c)
        used += size
    return ''.join(result)


def wrapped(text, width):
    width = max(1, width)
    result = []
    for paragraph in plain(text).splitlines():
        remaining = paragraph.replace('\t', ' ')
        if not remaining:
            result.append('')
        while remaining:
            piece = clip(remaining, width)
            if not piece:
                # A single wide glyph cannot fit a one-cell pane.
                result.append('?')
                remaining = remaining[1:]
                continue
            if len(piece) < len(remaining) and ' ' in piece:
                boundary = piece.rfind(' ')
                if boundary > 0:
                    piece = piece[:boundary]
            result.append(piece)
            remaining = remaining[len(piece):].lstrip(' ')
    return result or ['']


class Canvas:
    """Deterministic cell model shared by curses and layout/snapshot tests."""
    def __init__(self, height, width, ascii_only=False):
        self.height, self.width, self.ascii = height, width, ascii_only
        self.cells = [[' '] * width for _ in range(height)]
        self.styles = [[0] * width for _ in range(height)]

    def put(self, y, x, text, style=0, width=None):
        if not 0 <= y < self.height or x < 0 or x >= self.width:
            return
        for char in clip(text, min(self.width - x, width if width is not None else self.width)):
            size = 0 if unicodedata.combining(char) else 2 if unicodedata.east_asian_width(char) in ('W', 'F') else 1
            if size == 0:
                if x:
                    self.cells[y][x - 1] += char
                continue
            # Clear either half of any wide glyph being overwritten.
            for cell in range(x, min(self.width, x + size)):
                if self.cells[y][cell] == '' and cell:
                    self.cells[y][cell - 1] = ' '
                elif cell + 1 < self.width and self.cells[y][cell + 1] == '':
                    self.cells[y][cell + 1] = ' '
            self.cells[y][x] = char
            self.styles[y][x] = style
            if size == 2:
                self.cells[y][x + 1] = ''
                self.styles[y][x + 1] = style
            x += size

    def box(self, y, x, h, w, title='', style=2):
        if h < 2 or w < 2:
            return
        tl, trc, bl, br, hz, vt = ('+', '+', '+', '+', '-', '|') if self.ascii else ('╭', '╮', '╰', '╯', '─', '│')
        self.put(y, x, tl + hz * (w - 2) + trc, style)
        self.put(y + h - 1, x, bl + hz * (w - 2) + br, style)
        for row in range(y + 1, y + h - 1):
            self.put(row, x, vt, style)
            self.put(row, x + w - 1, vt, style)
        if title:
            self.put(y, x + 2, ' ' + title + ' ', 1, w - 4)

    def lines(self):
        return [''.join(row) for row in self.cells]


class Workspace:
    def __init__(self, repo, initial_view='home', settings=None):
        self.repo = str(Path(repo).resolve())
        self.settings = load_settings() if settings is None else dict(settings)
        self.settings['groups'] = list(self.settings['groups'])
        preferred = os.environ.get('MAC_UPDATE_LANG') or (os.environ.get('MAC_LANG') if not self.settings['wizard_complete'] else None)
        if preferred in LANGUAGES and settings is None:
            self.settings['language'] = preferred
        self.view = initial_view if initial_view in VIEWS else 'home'
        if not self.settings['wizard_complete'] and initial_view == 'home':
            self.view = 'wizard'
        self.focus, self.selected, self.wizard_step = 0, 0, 0
        self.job, self.job_action = None, None
        self.log, self.partial = [], ''
        self.log_scroll, self.help_scroll = 0, 0
        self.progress = None
        self.group_states = {g: 'idle' for g in GROUPS}
        self.status, self.notice = 'idle', ''
        self.modal, self.buffer, self.pending_action = None, '', None
        self.input_secret = False
        self.palette_index, self.palette_search = 0, ''
        self.should_exit, self.exit_after_job = False, False
        self.rows, self.cols = 30, 120
        self.history = []
        self.last_command = []
        self.last_returncode = None
        self.completed_actions = set()
        self._paste_buffer, self._pasting = '', False
        self._escape_buffer = ''
        try:
            self.version = (Path(self.repo) / 'VERSION').read_text().strip()[:32]
        except OSError:
            self.version = '?'

    def t(self, key, **values):
        return tr(key, self.settings['language'], **values)

    def change_view(self, view):
        self.view, self.selected, self.help_scroll = view, 0, 0
        if view == 'history':
            self.history = recent_runs(self.repo)

    def items(self):
        result = []
        if self.view in ('updates', 'settings'):
            result += [('group', g) for g in GROUPS]
        if self.view == 'settings':
            result += [('setting', k) for k in ('language', 'theme', 'ascii', 'auto_resize')]
            result += [('save', 'save')]
        elif self.view == 'wizard':
            step = STEPS[self.wizard_step]
            if step == 'welcome':
                result += [('setting', 'language')]
            if step == 'settings':
                result += [('group', g) for g in GROUPS]
                result += [('setting', 'theme'), ('setting', 'ascii')]
            result += [('action', a) for a in STEP_ACTIONS.get(step, ())]
            if self.wizard_step:
                result += [('wizard', 'back')]
            result += [('wizard', 'finish' if step == 'finish' else 'next')]
        elif self.view == 'history':
            result += [('history', str(i)) for i in range(len(self.history))]
        else:
            result += [('action', a) for a in VIEW_ACTIONS.get(self.view, ())]
        return result

    def selected_item(self):
        items = self.items()
        if not items:
            return None
        self.selected = min(max(0, self.selected), len(items) - 1)
        return items[self.selected]

    def item_label(self, item):
        kind, value = item
        if kind == 'group':
            return ('[x] ' if value in self.settings['groups'] else '[ ] ') + self.t('group_' + value)
        if kind == 'setting':
            current = self.settings[value]
            if value == 'language':
                current = NATIVE_NAMES[current]
            elif value == 'theme':
                current = self.t('theme_' + current)
            elif isinstance(current, bool):
                current = '[x]' if current else '[ ]'
            return self.t(value) + ': ' + str(current)
        if kind == 'action':
            return self.t('action_' + value)
        if kind == 'history':
            row = self.history[int(value)]
            return row['timestamp'] + ' | ' + row['exit_class']
        return self.t(value)

    def details(self):
        item = self.selected_item()
        lines = []
        if self.view == 'wizard':
            lines += [self.t('wizarddesc_' + STEPS[self.wizard_step]), '']
        if item:
            kind, value = item
            if kind == 'action':
                lines += [self.t('desc_' + value), '']
                try:
                    command = build_command(self.repo, value, self.settings['groups'], self.settings)
                    lines += [shlex.join(command), '']
                except (OSError, ValueError, StoreError) as exc:
                    lines += [plain(exc), '']
            elif kind in ('setting', 'group', 'save'):
                lines += [self.t('groups_hint' if kind == 'group' else 'settings_hint'), '']
            elif kind == 'history':
                row = self.history[int(value)]
                lines += [row['filename'], row['run_status'], row['exit_class'],
                          self.t('elapsed') + ': ' + str(row['duration_seconds']) + ' s', '']
        lines += [self.t('serial_notice'), '', self.t('input_hint')]
        return lines

    def save(self, complete=False):
        if complete:
            self.settings['wizard_complete'] = True
        try:
            save_settings(None, self.settings)
            self.notice = self.t('saved')
            if complete:
                self.change_view('home')
                self.focus = 1
        except (OSError, ValueError, StoreError) as exc:
            self.notice = self.t('error', message=plain(exc))
            if complete:
                self.settings['wizard_complete'] = False

    def activate(self):
        item = self.selected_item()
        if item is None:
            return
        kind, value = item
        if kind == 'action':
            self.request_action(value)
        elif kind == 'group':
            groups = self.settings['groups']
            if value in groups:
                groups.remove(value)
            else:
                groups.append(value)
        elif kind == 'setting':
            if value == 'language':
                self.settings[value] = LANGUAGES[(LANGUAGES.index(self.settings[value]) + 1) % len(LANGUAGES)]
            elif value == 'theme':
                self.settings[value] = 'light' if self.settings[value] == 'dark' else 'dark'
            else:
                self.settings[value] = not self.settings[value]
        elif kind == 'save':
            self.save()
        elif kind == 'wizard':
            if self.job and self.job.running:
                self.notice = self.t('busy')
            elif value == 'finish':
                self.save(complete=True)
            else:
                self.wizard_step = max(0, min(len(STEPS) - 1, self.wizard_step + (1 if value == 'next' else -1)))
                self.selected = 0

    def request_action(self, action):
        if self.job and self.job.running:
            self.notice = self.t('busy')
            return
        if action not in ACTIONS:
            return
        try:
            build_command(self.repo, action, self.settings['groups'], self.settings)
        except (OSError, ValueError, StoreError) as exc:
            self.notice = self.t('error', message=plain(exc))
            return
        self.pending_action = action
        if ACTIONS[action]['mutating']:
            self.modal = 'confirm'
        else:
            self.start_job(action)

    def start_job(self, action):
        try:
            job = TerminalJob(self.repo, action, self.settings['groups'], self.settings)
            job.resize(max(10, self.rows - 8), max(40, self.cols - 30))
            job.start()
            self.job, self.job_action = job, action
            self.last_command = list(job.command)
            self.log, self.partial, self.progress, self.log_scroll = [], '', None, 0
            self.status, self.notice, self.modal = 'running', '', None
            self.last_returncode = None
            self.group_states = {g: ('queued' if g in self.settings['groups'] else 'skipped') for g in GROUPS} if action == 'update' else {g: 'idle' for g in GROUPS}
        except (OSError, ValueError, StoreError) as exc:
            self.notice, self.modal = self.t('error', message=plain(exc)), None

    def tick(self):
        if self.job is None:
            return
        for chunk in self.job.poll():
            clean = plain(chunk.replace('\r\n', '\n').replace('\r', '\n'))
            pieces = (self.partial + clean).split('\n')
            self.partial = pieces.pop()[-4096:]
            for line in pieces:
                event = re.fullmatch(r'@@MAC_UPDATE_PHASE ([a-z]+) ([a-z_]+)', line)
                if event:
                    group = {'npmcli': 'npm'}.get(event[1], event[1])
                    state = {'ok': 'completed', 'warn': 'warnings', 'error': 'failed', 'skipped_by_user': 'skipped', 'unconfirmed': 'warnings'}.get(event[2], event[2])
                    if self.job_action == 'update' and group in GROUPS and state in ('running', 'completed', 'warnings', 'failed', 'skipped', 'unknown'):
                        self.group_states[group] = state
                else:
                    self.log.append(line[:4096])
            self.log = self.log[-2000:]
            for match in re.finditer(r'(\d{1,3})%\s+overall', clean):
                self.progress = min(99 if self.job.running else 100, int(match.group(1)))
            if clean.strip():
                self.status = 'running'
            tail = clean.rstrip()
            if tail.endswith((':', '?')) or re.search(r'\[[^\]\n]{1,20}\]:?\s*$', tail):
                self.status = 'waiting'
        if self.job.running and self.job.secret_input:
            self.status = 'waiting'
        if not self.job.running and self.last_returncode is None:
            self.last_returncode = self.job.returncode
            if self.last_returncode is not None:
                self.status = 'completed' if self.last_returncode == 0 else 'warnings' if self.last_returncode == 10 else 'failed'
                if self.last_returncode in (0, 10):
                    self.completed_actions.add(self.job_action)
                self.group_states = {g: ('unknown' if state in ('running', 'queued') else state) for g, state in self.group_states.items()}
                self.notice = self.t('job_finished', code=self.last_returncode)
                if self.modal == 'input':
                    self.modal, self.buffer = None, ''
                if self.exit_after_job:
                    self.should_exit = True

    def log_line_count(self):
        left = 23 if self.cols >= 110 else 20
        right = 31 if self.cols >= 120 else 0
        width = max(1, self.cols - left - right - 4)
        return sum(len(wrapped(entry, width)) for entry in self.log + ([self.partial] if self.partial else []))

    def copy(self):
        if self.modal == 'input':
            return
        item = self.selected_item()
        if self.focus == 2:
            lines = self.log + ([self.partial] if self.partial else [])
            text = lines[max(0, len(lines) - 1 - self.log_scroll)] if lines else ''
        elif item and item[0] == 'action':
            try:
                text = shlex.join(build_command(self.repo, item[1], self.settings['groups'], self.settings))
            except (OSError, ValueError, StoreError):
                return
        else:
            text = '\n'.join(self.details())
        self.clipboard('copy', text)

    def clipboard(self, action, text=''):
        command = shutil.which('pbcopy' if action == 'copy' else 'pbpaste')
        if not command:
            self.notice = self.t('clipboard_unavailable')
            return
        try:
            if action == 'copy':
                subprocess.run([command], input=text[:65536], text=True, check=True, timeout=2)
                self.notice = self.t('copied')
            else:
                # Paste only into the answer editor. It cannot execute or submit.
                result = subprocess.run([command], capture_output=True, text=True, check=True, timeout=2)
                self.buffer = (self.buffer + plain(result.stdout).replace('\n', ' '))[:4096]
        except (OSError, subprocess.SubprocessError):
            self.notice = self.t('clipboard_unavailable')

    def palette_actions(self):
        query = self.palette_search.casefold()
        return [a for a in ACTIONS if query in self.t('action_' + a).casefold()]

    def paste_text(self, value):
        # Pasted text is data, never a stream of action shortcuts or Enter keys.
        value = plain(value).replace('\n', ' ').replace('\t', ' ')
        if self.modal == 'input':
            self.buffer = (self.buffer + value)[:4096]
        elif self.modal == 'palette':
            self.palette_search = (self.palette_search + value)[:80]
            self.palette_index = 0
        else:
            self.notice = self.t('input_hint')

    def feed_keys(self, keys):
        text = ''.join(k for k in keys if isinstance(k, str))
        combined = self._escape_buffer + text
        marker = '\x1b[200~'
        if (not self._pasting and (len(keys) > 1 or self._escape_buffer)
                and any(c.isprintable() for c in text)
                and not marker.startswith(combined) and not combined.startswith(marker)):
            self._escape_buffer = ''
            self.paste_text(combined)
            return
        for key in keys:
            if not isinstance(key, str):
                self.key(key)
                continue
            if self._pasting:
                self._paste_buffer += key
                if self._paste_buffer.endswith('\x1b[201~'):
                    self.paste_text(self._paste_buffer[:-6])
                    self._pasting, self._paste_buffer = False, ''
                    return
                elif len(self._paste_buffer) > 8192:
                    self._paste_buffer = self._paste_buffer[-4096:]
                continue
            if self._escape_buffer or key == '\x1b':
                self._escape_buffer += key
                self._escape_started = time.monotonic()
                if self._escape_buffer == '\x1b[200~':
                    self._pasting, self._escape_buffer = True, ''
                elif not '\x1b[200~'.startswith(self._escape_buffer):
                    self._escape_buffer = ''
                    self.key('\x1b')
                continue
            self.key(key)

    def flush_escape(self):
        if self._escape_buffer and time.monotonic() - self._escape_started > .08:
            self._escape_buffer = ''
            self.key('\x1b')

    def key(self, key):
        if key == curses.KEY_RESIZE:
            return
        if self.rows < 24 or self.cols < 80:
            if key in ('q', '\x1b') and (not self.job or not self.job.running):
                self.should_exit = True
            return
        if self.modal:
            self.modal_key(key)
            return
        if key == '\x1b' and (self.rows < 24 or self.cols < 80):
            if not self.job or not self.job.running:
                self.should_exit = True
            return
        if key in ('q', '\x03'):
            if self.job and self.job.running:
                self.modal = 'quit'
            else:
                self.should_exit = True
        elif key in ('?', curses.KEY_F1):
            self.change_view('help')
            self.focus = 1
        elif key == '\x10':
            self.modal, self.palette_search, self.palette_index = 'palette', '', 0
        elif key == '\t':
            self.focus = (self.focus + 1) % 3
        elif key in (curses.KEY_LEFT, '\x1b'):
            self.focus = 0
        elif key == curses.KEY_RIGHT:
            self.focus = 1
        elif key in (curses.KEY_UP, curses.KEY_DOWN):
            direction = 1 if key == curses.KEY_DOWN else -1
            if self.focus == 0:
                self.change_view(VIEWS[(VIEWS.index(self.view) + direction) % len(VIEWS)])
            elif self.focus == 2:
                self.log_scroll = max(0, min(self.log_line_count(), self.log_scroll - direction))
            elif self.view == 'help':
                self.help_scroll = max(0, self.help_scroll + direction)
            elif self.items():
                self.selected = (self.selected + direction) % len(self.items())
        elif key in (curses.KEY_PPAGE, curses.KEY_NPAGE):
            delta = 6 if key == curses.KEY_PPAGE else -6
            if self.view == 'help' and self.focus == 1:
                self.help_scroll = max(0, self.help_scroll - delta)
            else:
                self.log_scroll = max(0, min(self.log_line_count(), self.log_scroll + delta))
        elif key in ('\n', '\r', curses.KEY_ENTER, ' '):
            if self.focus == 0:
                self.focus = 1
            elif self.focus == 1:
                self.activate()
        elif key == 'r':
            item = self.selected_item()
            if item and item[0] == 'action':
                self.request_action(item[1])
        elif key == 'd':
            self.request_action('preview')
        elif key == 's':
            self.change_view('settings')
            self.focus = 1
        elif key == 'c':
            self.copy()
        elif key == 'i' and self.job and self.job.running:
            self.modal, self.buffer = 'input', ''
            self.input_secret = bool(self.job.secret_input)
        elif key == 'x' and self.job and self.job.running:
            self.modal = 'interrupt'

    def modal_key(self, key):
        if key == '\x1b':
            self.modal, self.buffer = None, ''
            self.input_secret = False
            return
        if self.modal in ('confirm', 'interrupt', 'quit'):
            # A deliberate y is required. Enter never defaults to an operation.
            if key == 'y':
                modal, self.modal = self.modal, None
                if modal == 'confirm':
                    self.start_job(self.pending_action)
                else:
                    self.exit_after_job = modal == 'quit'
                    self.job.interrupt()
                    self.status = 'running'
            elif key in ('n', '\n', '\r', 'q'):
                self.modal = None
            return
        if self.modal == 'palette':
            items = self.palette_actions()
            if key in (curses.KEY_UP, curses.KEY_DOWN) and items:
                self.palette_index = (self.palette_index + (1 if key == curses.KEY_DOWN else -1)) % len(items)
            elif key in ('\n', '\r', curses.KEY_ENTER) and items:
                action = items[min(self.palette_index, len(items) - 1)]
                self.modal = None
                self.request_action(action)
            elif key in (curses.KEY_BACKSPACE, '\x7f', '\b'):
                self.palette_search = self.palette_search[:-1]
            elif isinstance(key, str) and key.isprintable():
                self.palette_search = (self.palette_search + key)[:80]
                self.palette_index = 0
            return
        if self.modal == 'input':
            if key in (curses.KEY_PPAGE, curses.KEY_NPAGE):
                self.log_scroll = max(0, self.log_scroll + (6 if key == curses.KEY_PPAGE else -6))
            elif key == '\x16':
                self.clipboard('paste')
            elif key in ('\n', '\r', curses.KEY_ENTER):
                if self.job and self.job.running:
                    self.job.send(self.buffer + '\n')
                self.buffer, self.modal, self.status = '', None, 'running'
                self.input_secret = False
            elif key in (curses.KEY_BACKSPACE, '\x7f', '\b'):
                self.buffer = self.buffer[:-1]
            elif key == '\x15':
                self.buffer = ''
            elif isinstance(key, str) and key.isprintable():
                self.buffer = (self.buffer + key)[:4096]

    def frame(self, height, width):
        self.rows, self.cols = height, width
        c = Canvas(height, width, self.settings['ascii'])
        if height < 24 or width < 80:
            c.put(0, 0, self.t('app_title'), 1)
            c.put(2, 0, self.t('resize'), 4)
            c.put(4, 0, 'q / Esc', 3)
            return c
        c.put(0, 2, self.t('app_title') + '  ' + self.version, 1)
        badge = self.t(self.status).upper()
        c.put(0, max(40, width - cell_width(badge) - 3), badge, 5 if self.status == 'completed' else 4 if self.status == 'waiting' else 1)
        left = 23 if width >= 110 else 20
        right = 31 if width >= 120 else 0
        mid_x, mid_w = left, width - left - right
        body_h = height - 3
        c.box(1, 0, body_h, left, self.t('actions'), 1 if self.focus == 0 else 2)
        c.box(1, mid_x, body_h, mid_w, self.t('nav_' + self.view), 1 if self.focus == 1 else 2)
        if right:
            c.box(1, width - right, body_h, right, self.t('details'))
        for i, view in enumerate(VIEWS):
            c.put(3 + i * (2 if height >= 29 else 1), 2, ('> ' if view == self.view else '  ') + self.t('nav_' + view),
                  1 if view == self.view else 0, left - 4)
        c.put(height - 5, 2, NATIVE_NAMES[self.settings['language']], 3, left - 4)
        x, usable = mid_x + 2, mid_w - 4
        y = 3
        if self.view == 'help':
            lines = wrapped(self.t('help_body'), usable)
            self.help_scroll = min(self.help_scroll, max(0, len(lines) - body_h + 5))
            for line in lines[self.help_scroll:self.help_scroll + body_h - 4]:
                c.put(y, x, line, 0, usable)
                y += 1
        else:
            if self.view == 'wizard':
                c.put(y, x, '%s / %s  %s' % (self.wizard_step + 1, len(STEPS), self.t('wizardstep_' + STEPS[self.wizard_step])), 1, usable)
                y += 2
                for line in wrapped(self.t('wizarddesc_' + STEPS[self.wizard_step]), usable)[:2]:
                    c.put(y, x, line, 3, usable)
                    y += 1
            elif self.view == 'home':
                c.put(y, x, self.t('scan_hint'), 3, usable)
                y += 2
            elif self.view == 'history' and not self.history:
                c.put(y, x, self.t('no_history'), 3, usable)
                y += 1
            items = self.items()
            self.selected_item()
            available = max(3, (height - y - 11))
            offset = max(0, self.selected - available + 1)
            for index in range(offset, min(len(items), offset + available)):
                c.put(y, x, ('> ' if index == self.selected else '  ') + self.item_label(items[index]),
                      1 if self.focus == 1 and index == self.selected else 0, usable)
                y += 1
            if items:
                c.put(y, x, '%s/%s' % (self.selected + 1, len(items)), 3, usable)
            log_top = max(y + 2, min(height // 2, height - 10))
            if log_top < height - 7:
                label = self.t('action_' + self.job_action) if self.job_action else self.t('idle')
                c.put(log_top, x, label, 1, usable)
                duration = int(time.monotonic() - self.job.started_at) if self.job and self.job.started_at else 0
                progress = self.progress
                bar_w = max(5, usable - 20)
                full = int(bar_w * progress / 100) if progress is not None else 0
                fill, empty = ('#', '-') if self.settings['ascii'] else ('━', '─')
                bar = fill * full + empty * (bar_w - full)
                c.put(log_top + 1, x, bar + ' ' + (str(progress) + '%' if progress is not None else '--') + '  ' + str(duration) + 's', 1, usable)
                c.put(log_top + 2, x, self.t('live_log') + '  [i] ' + self.t('input') + '  [c] ' + self.t('copy'), 3, usable)
                log_rows = max(0, height - log_top - 7)
                log = [line for entry in self.log + ([self.partial] if self.partial else []) for line in wrapped(entry, usable)]
                end = max(0, len(log) - self.log_scroll)
                for j, line in enumerate(log[max(0, end - log_rows):end]):
                    c.put(log_top + 3 + j, x, line, 0, usable)
        if self.focus == 2 and self.view != 'help':
            for row in range(2, height - 3):
                c.put(row, x, ' ' * usable)
            c.put(3, x, self.t('live_log') + '  [i] ' + self.t('input') + '  [c] ' + self.t('copy'), 1, usable)
            output = [line for entry in self.log + ([self.partial] if self.partial else []) for line in wrapped(entry, usable)]
            end = max(0, len(output) - self.log_scroll)
            for row, line in enumerate(output[max(0, end - (height - 9)):end], 5):
                c.put(row, x, line, 0, usable)
        if right:
            y = 3
            if self.job_action == 'update':
                for group in GROUPS:
                    state = self.group_states[group]
                    c.put(y, width - right + 2, self.t('group_' + group), 0, right - 4)
                    c.put(y + 1, width - right + 2, ('[####] ' if state == 'completed' else '[>>>>] ' if state == 'running' else '[----] ') + self.t(state), 5 if state == 'completed' else 4 if state in ('warnings', 'failed') else 1, right - 4)
                    y += 3
            for paragraph in self.details():
                for line in wrapped(paragraph, right - 4):
                    if y >= height - 5:
                        break
                    c.put(y, width - right + 2, line, 3, right - 4)
                    y += 1
        c.put(height - 2, 2, self.notice or self.t('shortcut_hint'), 4 if self.notice else 3, width - 4)
        c.put(height - 1, 2, 'Tab  |  Enter  |  r  ' + self.t('start') + '  |  d  dry-run  |  i  ' + self.t('input') + '  |  ?  ' + self.t('help_title') + '  |  Ctrl-P  |  q', 1, width - 4)
        if self.modal:
            self.render_modal(c)
        return c

    def render_modal(self, c):
        if self.modal == 'input' and self.job and self.job.secret_input:
            self.input_secret = True
        w, h = min(c.width - 6, 88), min(c.height - 4, 18)
        if self.modal == 'input':
            w, h = c.width - 6, c.height - 4
        x, y = (c.width - w) // 2, (c.height - h) // 2
        for row in range(y, y + h):
            c.put(row, x, ' ' * w)
        title = self.t('secret_input' if self.modal == 'input' and self.input_secret else self.modal if self.modal in ('input', 'palette', 'confirm') else 'confirm')
        c.box(y, x, h, w, title, 1)
        lines = []
        if self.modal in ('confirm', 'interrupt', 'quit'):
            lines = [self.t('confirm_body' if self.modal == 'confirm' else 'quit_body' if self.modal == 'quit' else 'interrupt_body'), '']
            if self.modal == 'confirm':
                lines += [self.t('action_' + self.pending_action), self.t('desc_' + self.pending_action), '']
                try:
                    lines += [shlex.join(build_command(self.repo, self.pending_action, self.settings['groups'], self.settings))]
                except ValueError:
                    pass
            lines += ['', '[y] ' + self.t('confirm') + '    [Enter / Esc] ' + self.t('cancel')]
        elif self.modal == 'input':
            # Keep the actual question and its scopes visible while answering.
            context = [line for entry in self.log + ([self.partial] if self.partial else [])
                       for line in wrapped(entry, w - 4)]
            end = max(0, len(context) - self.log_scroll)
            room = max(1, h - 10)
            lines = context[max(0, end - room):end] + ['',
                     self.t('secret_input' if self.input_secret else 'input') + ':',
                     clip(('*' * len(self.buffer)) if self.input_secret else self.buffer, w - 4),
                     '', 'Enter  |  Esc  |  Ctrl-V  ' + self.t('paste') + '  |  PgUp / PgDn']
        else:
            lines = [self.t('search') + ': ' + self.palette_search, '']
            actions = self.palette_actions()
            offset = max(0, self.palette_index - (h - 7))
            for i in range(offset, min(len(actions), offset + h - 6)):
                action = actions[i]
                lines += [('> ' if i == self.palette_index else '  ') + self.t('action_' + action)]
        row = y + 2
        for paragraph in lines:
            for line in wrapped(paragraph, w - 4):
                if row < y + h - 1:
                    c.put(row, x + 2, line, 0, w - 4)
                    row += 1


def configure_colors(theme):
    if not curses.has_colors():
        return {}
    curses.start_color()
    count = getattr(curses, 'COLORS', 8)
    if count >= 256:
        bg, fg = (235, 252) if theme == 'dark' else (255, 235)
        colors = [fg, 81 if theme == 'dark' else 25, 60, 245, 214 if theme == 'dark' else 130, 78 if theme == 'dark' else 28]
    else:
        bg, fg = (curses.COLOR_BLACK, curses.COLOR_WHITE) if theme == 'dark' else (curses.COLOR_WHITE, curses.COLOR_BLACK)
        colors = [fg, curses.COLOR_CYAN, curses.COLOR_BLUE, fg, curses.COLOR_YELLOW, curses.COLOR_GREEN]
    result = {}
    for i, color in enumerate(colors, 1):
        curses.init_pair(i, color, bg)
        result[i - 1] = curses.color_pair(i)
    return result


class TerminalWindow:
    """Best-effort xterm window resize; restore the original dimensions on exit."""
    def __init__(self, stream, enabled=True):
        self.stream, self.enabled = stream, enabled
        self.original, self.requested = None, False

    def __enter__(self):
        if not self.enabled or not self.stream.isatty() or os.environ.get('TMUX') or os.environ.get('STY'):
            return self
        term = os.environ.get('TERM', '')
        if not term.startswith(('xterm', 'rxvt')):
            return self
        try:
            size = os.get_terminal_size(self.stream.fileno())
            self.original = (size.lines, size.columns)
            if size.lines < 38 or size.columns < 140:
                self.stream.write('\x1b[8;%s;%st' % (max(38, size.lines), max(140, size.columns)))
                self.stream.flush()
                self.requested = True
        except (OSError, ValueError):
            pass
        return self

    def __exit__(self, *unused):
        if self.requested and self.original:
            try:
                self.stream.write('\x1b[8;%s;%st' % self.original)
                self.stream.flush()
            except (OSError, ValueError):
                pass


def run(repo, initial_view='home'):
    if not sys.stdin.isatty() or not sys.stdout.isatty() or os.environ.get('TERM') in (None, '', 'dumb'):
        return 2
    try:
        workspace = Workspace(repo, initial_view)
    except (OSError, ValueError, StoreError) as exc:
        print(tr('error', os.environ.get('MAC_UPDATE_LANG', 'en'), message=plain(exc)), file=sys.stderr)
        return 2

    def main(screen):
        curses.raw()
        curses.noecho()
        screen.keypad(True)
        screen.timeout(80)
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        theme, colors = None, {}
        while not workspace.should_exit:
            workspace.tick()
            workspace.flush_escape()
            height, width = screen.getmaxyx()
            if (height, width) != (workspace.rows, workspace.cols) and workspace.job and workspace.job.running:
                workspace.job.resize(max(1, height - 8), max(1, width - 30))
            if theme != workspace.settings['theme']:
                theme = workspace.settings['theme']
                colors = configure_colors(theme)
                screen.bkgd(' ', colors.get(0, 0))
            frame = workspace.frame(height, width)
            screen.erase()
            for y in range(height):
                x = 0
                while x < width:
                    style = frame.styles[y][x]
                    end = x + 1
                    while end < width and frame.styles[y][end] == style:
                        end += 1
                    try:
                        screen.addstr(y, x, ''.join(frame.cells[y][x:end]), colors.get(style, 0) | (curses.A_BOLD if style == 1 else 0))
                    except curses.error:
                        pass
                    x = end
            screen.refresh()
            try:
                key = screen.get_wch()
            except curses.error:
                continue
            keys = [key]
            screen.timeout(0)
            for _ in range(8192):
                try:
                    keys.append(screen.get_wch())
                except curses.error:
                    break
            screen.timeout(80)
            workspace.feed_keys(keys)
        return 0

    try:
        sys.stdout.write('\x1b[?2004h')
        sys.stdout.flush()
        with TerminalWindow(sys.stdout, workspace.settings.get('auto_resize', True)):
            try:
                return curses.wrapper(main)
            except (Exception, KeyboardInterrupt) as exc:
                if workspace.job and workspace.job.running:
                    return handoff(workspace.job, workspace.t('ui_recovery'))
                print(workspace.t('error', message=plain(exc)), file=sys.stderr)
                return 2
    finally:
        try:
            sys.stdout.write('\x1b[?2004l')
            sys.stdout.flush()
        except OSError:
            pass
