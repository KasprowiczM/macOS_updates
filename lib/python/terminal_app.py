"""Three-panel terminal workspace. Rendering never grants execution authority."""
import curses
import json
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
from tui_widgets import UI_EN, inventory_rows, panel_sizes

VIEWS = ('home', 'updates', 'inventory', 'catalog', 'diagnostics', 'history', 'settings', 'wizard', 'about', 'help')
STEPS = ('welcome', 'requirements', 'inventory', 'catalog', 'sources', 'agreement', 'settings', 'preview', 'finish')
VIEW_ACTIONS = {
    'home': ('preview', 'update', 'doctor'),
    'updates': ('preview', 'update', 'preferences'),
    'about': ('toolkit_check', 'toolkit_prepare'),
    'inventory': ('inventory', 'migration_preview', 'coverage'),
    'catalog': ('catalog', 'sources', 'coverage'),
    'diagnostics': ('doctor', 'setup_inspect', 'coverage', 'native_recovery'),
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


def load_inventory(repo, state_dir=None):
    from tui_inventory import load_inventory as load
    return load(repo, state_dir=state_dir)


def save_selection(model, changes, state_dir=None):
    from tui_inventory import save_selection as save
    return save(model, changes, state_dir=state_dir)


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
        self.footer_selected, self.modal_selected = 0, 0
        self.inventory_model, self.inventory_changes = None, {}
        self.preview_rows, self._candidate_batch = None, None
        self.target_states, self.target_timings = {}, {}
        self.inventory_query, self.inventory_source, self.inventory_sort = '', 'all', 'source'
        self.inventory_error = ''
        self.catalog_model, self.catalog_selected, self.catalog_sources = None, set(), {}
        self.catalog_error, self.catalog_plan = '', None
        self.installed_default_enabled = False
        self.prompt_pending, self._deferred_prompt = False, False
        self._secret_prompt_seen = False
        self.toolkit_report, self.pending_toolkit_receipt = None, None
        self._previous_view = 'home'
        try:
            from policy_runtime import load_policies
            from user_policy import installed_update_default
            self.installed_default_enabled = bool(installed_update_default(load_policies()))
        except (OSError, ValueError, StoreError):
            pass
        try:
            self.version = (Path(self.repo) / 'VERSION').read_text().strip()[:32]
        except OSError:
            self.version = '?'
        if self.view in ('updates', 'inventory'):
            self.reload_inventory()
        if self.view == 'catalog':
            self.reload_catalog()

    def reload_catalog(self):
        if self.busy():
            self.notice = self.t('busy')
            return
        try:
            from tui_inventory import load_catalog
            self.catalog_model = load_catalog(self.repo)
            self.catalog_error = ''
        except (ImportError, OSError, ValueError, StoreError, KeyError):
            self.catalog_model = {'rows': []}
            self.catalog_error = self.t('catalog_unavailable')

    def prepare_catalog(self):
        self.catalog_plan = None
        try:
            from tui_inventory import prepare_catalog_selection
            self.catalog_plan = prepare_catalog_selection(self.catalog_model or {}, self.catalog_selected, self.catalog_sources)
            self.request_action('catalog')
        except (OSError, ValueError, StoreError, KeyError) as exc:
            key = str(exc)
            self.notice = self.t(key) if key in ('catalog_selection_empty', 'catalog_source_required', 'inventory_missing') else self.t('catalog_unavailable')

    def catalog_rows(self):
        return (self.catalog_model or {}).get('rows', [])

    def catalog_row(self, product):
        return next((row for row in self.catalog_rows() if row['product_id'] == product), {})

    def t(self, key, **values):
        value = tr(key, self.settings['language'], **values)
        if value == key and key in UI_EN:
            try:
                value = UI_EN[key].format(**values)
            except (KeyError, ValueError):
                value = UI_EN[key]
        return value

    def busy(self):
        return bool(self.job and self.job.running)

    def open_input(self):
        if not self.busy():
            return
        if self.modal != 'input':
            self.modal, self.buffer, self.modal_selected = 'input', '', 0
            self.input_secret = bool(self.job.secret_input)
        self.prompt_pending = True
        self.status = 'waiting'
        self.log_scroll = 0

    def reload_inventory(self, force=False):
        if self.busy():
            self.notice = self.t('busy')
            return
        if self.inventory_changes and not force:
            self.modal, self.modal_selected = 'discard', 0
            return
        try:
            self.inventory_model = load_inventory(self.repo)
            self.inventory_error = ''
            self.inventory_changes = {}
            self.selected = 0
        except (ImportError, OSError, ValueError, StoreError):
            self.inventory_model = {'rows': [], 'plan': None}
            self.inventory_error = self.t('inventory_unavailable')
            self.notice = self.inventory_error

    def reload_candidates(self):
        self.reload_inventory(force=True)

    @staticmethod
    def target_key(row):
        target = row.get('target')
        if not isinstance(target, dict) or target.get('kind') not in ('app', 'package') or not isinstance(target.get('id'), str) or not target['id']:
            return None
        identity, source = row.get('identity_fingerprint'), row.get('source_fingerprint')
        if not isinstance(identity, str) or not isinstance(source, str):
            return None
        return target['kind'], target['id'], identity, source

    def visible_inventory_rows(self):
        rows = self.preview_rows if self.view == 'updates' and self.preview_rows is not None else (self.inventory_model or {}).get('rows', [])
        return inventory_rows(rows, self.inventory_query, self.inventory_source, self.inventory_sort)

    def inventory_row(self, identity):
        rows = self.preview_rows if self.view == 'updates' and self.preview_rows is not None else (self.inventory_model or {}).get('rows', [])
        return next((r for r in rows if r['id'] == identity), None)

    def selection_id(self, row):
        saved = (self.inventory_model or {}).get('rows', [])
        if self.view != 'updates' or self.preview_rows is None:
            return row['id'] if any(r['id'] == row['id'] for r in saved) else None
        key = self.target_key(row)
        match = next((r for r in saved if key is not None and self.target_key(r) == key), None)
        return match['id'] if match else None

    def exclusion_row(self, row):
        """Added evidence may carry a denial to the same installed location only."""
        if not isinstance(row.get('path'), str) or not row['path'] or self.target_key(row) is None:
            return None
        matches = [saved for saved in (self.inventory_model or {}).get('rows', [])
                   if saved.get('target') == row.get('target') and saved.get('path') == row['path']]
        return matches[0] if len(matches) == 1 else None

    def row_enabled(self, row):
        identity = self.selection_id(row)
        if identity is None:
            match = self.exclusion_row(row)
            if match and (self.inventory_changes.get(match['id']) is False or match.get('enabled') is False):
                return False
        return self.inventory_changes.get(identity, row.get('enabled', False))

    def row_status(self, row):
        event = self.target_states.get(self.target_key(row))
        if event:
            status = event.get('status')
            if status == 'vendor_updater_observing':
                return 'running' if self.busy() else 'warnings'
            if status == 'running':
                return 'running' if self.busy() else 'unknown'
            if status in ('updated', 'current_verified'):
                return 'completed' if event.get('verified') is True else 'warnings'
            if status in ('update_failed', 'failed', 'error'):
                return 'failed'
            if status in ('recovery_required', 'unconfirmed', 'triggered_unconfirmed', 'observed_version_changed', 'legacy_handler_completed_unconfirmed'):
                return 'warnings'
            if status == 'ignored_by_policy':
                return 'excluded'
            if status == 'manual_by_policy':
                return 'manual'
            if status == 'deferred_by_user':
                return 'skipped'
            if status in ('scan_partial', 'source_conflict', 'source_unavailable', 'removed_since_scan'):
                return 'blocked'
            return 'unknown'
        return 'excluded' if not self.row_enabled(row) else row.get('status', 'manual')

    def row_version(self, row, detail=False):
        before = plain(row.get('version') or '?')
        after = self.target_states.get(self.target_key(row), {}).get('after')
        if isinstance(after, str) and after.strip() and after.strip() != before:
            return before + ' -> ' + plain(after) if detail else plain(after)
        return before

    def row_activity(self, row):
        status = self.row_status(row)
        timing = self.target_timings.get(self.target_key(row))
        elapsed = '--'
        seconds = 0
        if timing is not None:
            seconds = max(0, int((timing[1] if timing[1] is not None else time.monotonic()) - timing[0]))
            elapsed = '%d:%02d' % (seconds // 60, seconds % 60)
        if status == 'completed':
            return '[###]100%', elapsed
        if status == 'running':
            position = seconds % 5
            return '[' + '.' * position + '>' + '.' * (4 - position) + ']', elapsed
        if status in ('failed', 'warnings'):
            return '[!----]', elapsed
        return '[-----]', elapsed

    def save_inventory(self):
        if self.busy():
            self.notice = self.t('busy')
            return
        if not self.inventory_changes:
            self.notice = self.t('saved')
            return
        try:
            save_selection(self.inventory_model, dict(self.inventory_changes))
            self.reload_inventory(force=True)
            if self.preview_rows is not None:
                saved = {self.target_key(r): r for r in (self.inventory_model or {}).get('rows', []) if self.target_key(r)}
                self.preview_rows = [dict(r, enabled=saved[self.target_key(r)]['enabled'], status=saved[self.target_key(r)]['status'])
                                     if self.target_key(r) in saved else r for r in self.preview_rows]
                self.preview_rows = [dict(row, enabled=False, status='excluded')
                                     if self.exclusion_row(row) and self.exclusion_row(row).get('enabled') is False else row
                                     for row in self.preview_rows]
            self.notice = self.t('saved')
        except (OSError, ValueError, StoreError) as exc:
            self.notice = self.t('error', message=plain(exc))

    def source_name(self, source):
        names = {'homebrew': 'Homebrew', 'npm': 'npm', 'app_store': 'App Store', 'apple_system': 'macOS'}
        keys = {'all': 'inventory_all_sources', 'conflict': 'inventory_source_conflict',
                'vendor': 'inventory_source_vendor', 'enterprise': 'inventory_source_managed'}
        return names.get(source) or self.t(keys.get(source, 'unknown'))

    def row_reason(self, row):
        reasons = set(row.get('reasons', []))
        event = self.target_states.get(self.target_key(row), {})
        if isinstance(event.get('reason_code'), str):
            reasons.add(event['reason_code'])
        if event.get('status') == 'vendor_updater_observing' and self.busy():
            return self.t('native_observing_detail')
        if event.get('status') in ('triggered_unconfirmed', 'vendor_updater_observing', 'observed_version_changed', 'legacy_handler_completed_unconfirmed') or 'pending_updater_session' in reasons:
            key = {'observed_version_changed': 'native_version_changed_detail',
                   'legacy_handler_completed_unconfirmed': 'legacy_unconfirmed_detail'}.get(event.get('status'), 'native_pending_detail')
            return self.t(key) + '\n' + self.t('nav_diagnostics') + ': ' + self.t('action_native_recovery')
        if self.row_status(row) in ('completed', 'running', 'failed', 'warnings', 'unknown'):
            return self.t(self.row_status(row))
        if not self.row_enabled(row):
            key = 'excluded'
        elif 'source_conflict' in reasons or row.get('source') == 'conflict':
            key = 'conflict'
        elif reasons.intersection(('scan_partial', 'source_unavailable', 'removed_since_scan')):
            key = 'evidence'
        elif 'unsupported_automatic_method' in reasons:
            key = 'unsupported'
        elif 'deepseek_manual_only' in reasons:
            key = 'owner_manual'
        elif 'target_running' in reasons:
            key = 'running'
        elif 'deferred_by_user' in reasons:
            key = 'deferred'
        elif row.get('status') == 'manual' or 'manual_by_policy' in reasons:
            key = 'manual'
        elif 'consent_required' in reasons:
            key = 'consent'
        else:
            key = 'review'
        return self.t('inventory_reason_' + key)

    def footer_buttons(self):
        if self.view == 'wizard':
            controls = ['back', 'finish' if self.wizard_step == len(STEPS) - 1 else 'next']
        elif self.view == 'settings':
            controls = ['back', 'save', 'preview']
        elif self.view in ('inventory', 'updates'):
            controls = ['back', 'save_inventory', 'preview'] + (['run'] if self.view == 'updates' else [])
        elif self.view == 'about':
            controls = ['back']
        else:
            controls = ['back', 'preview', 'run']
        if self.busy():
            controls += ['answer', 'interrupt']
        else:
            controls += ['output']
        return controls + ['help', 'exit']

    def button_label(self, button):
        key = {'preview': 'preview_button', 'run': 'run_button', 'help': 'help_button', 'exit': 'exit_button',
               'answer': 'input', 'interrupt': 'interrupt_button', 'output': 'output_button',
               'save_inventory': 'inventory_save'}.get(button, button)
        return self.t(key)

    def button_disabled(self, button):
        if button in ('help', 'exit', 'answer', 'interrupt', 'output', 'back'):
            return button == 'back' and self.view == 'wizard' and self.wizard_step == 0
        if self.busy():
            return True
        if button == 'toolkit_apply':
            return not isinstance(self.toolkit_report, dict) or self.toolkit_report.get('status') != 'ready' or not isinstance(self.toolkit_report.get('receipt'), dict)
        if button == 'run':
            return not self.settings['groups'] or bool(self.inventory_changes)
        if button == 'preview':
            return bool(self.inventory_changes)
        return False

    def activate_button(self, button):
        if self.button_disabled(button):
            self.notice = self.t('inventory_save_first' if self.inventory_changes and button in ('preview', 'run') else 'disabled_control')
            return
        if button == 'back':
            if self.view == 'wizard':
                self.wizard_step = max(0, self.wizard_step - 1)
            else:
                self.change_view(self._previous_view if self._previous_view != self.view else 'home')
            self.selected = 0
        elif button == 'next':
            self.wizard_step = min(len(STEPS) - 1, self.wizard_step + 1)
            self.selected = 0
            if STEPS[self.wizard_step] == 'catalog' and self.catalog_model is None:
                self.reload_catalog()
        elif button == 'finish':
            self.save(complete=True)
        elif button == 'save':
            self.save()
        elif button == 'save_inventory':
            self.save_inventory()
        elif button in ('preview', 'run'):
            self.request_action('preview' if button == 'preview' else 'update')
        elif button in ('toolkit_check', 'toolkit_preview'):
            self.request_action('toolkit_check' if button == 'toolkit_check' else 'toolkit_prepare')
        elif button == 'toolkit_apply':
            self.modal, self.modal_selected = 'apply_toolkit', 0
        elif button == 'help':
            self.change_view('help')
            self.focus = 1
        elif button == 'exit':
            self.key('q')
        elif button == 'answer':
            self.open_input()
        elif button == 'interrupt':
            self.modal, self.modal_selected = 'interrupt', 0
        elif button == 'output':
            self.focus = 2

    def change_view(self, view):
        if view not in VIEWS:
            return
        if view != self.view:
            self._previous_view = self.view
        self.view, self.selected, self.help_scroll, self.footer_selected = view, 0, 0, 0
        if view == 'history':
            self.history = recent_runs(self.repo)
        if view in ('inventory', 'updates') and self.inventory_model is None:
            self.reload_inventory()
        if view == 'catalog' and self.catalog_model is None:
            self.reload_catalog()

    def items(self):
        result = []
        if self.view in ('updates', 'inventory'):
            actions = VIEW_ACTIONS['inventory'] if self.view == 'inventory' else ('preferences',)
            result += [('action', action) for action in actions]
        if self.view in ('updates', 'settings'):
            result += [('group', g) for g in GROUPS]
        if self.view in ('updates', 'inventory'):
            result += [('control', key) for key in (('internet_mode', 'search', 'source', 'sort', 'reload') if self.view == 'updates' else ('search', 'source', 'sort', 'reload'))]
            result += [('target', row['id']) for row in self.visible_inventory_rows()]
        elif self.view == 'settings':
            result += [('setting', key) for key in ('language', 'theme', 'ascii', 'auto_resize', 'internet_mode')]
        elif self.view == 'wizard':
            step = STEPS[self.wizard_step]
            if step == 'welcome':
                result += [('setting', 'language')]
            if step == 'settings':
                result += [('group', g) for g in GROUPS]
                result += [('setting', 'theme'), ('setting', 'ascii')]
            if step == 'agreement':
                result += [('control', 'installed_default')]
            if step == 'catalog':
                result += self.catalog_items()
            result += [('action', a) for a in STEP_ACTIONS.get(step, ())]
        elif self.view == 'catalog':
            result += self.catalog_items()
        elif self.view == 'history':
            result += [('history', str(i)) for i in range(len(self.history))]
        elif self.view == 'about':
            result += [('action', a) for a in ('toolkit_check', 'toolkit_prepare') if a in ACTIONS]
            result += [('control', 'toolkit_apply')]
        else:
            result += [('action', a) for a in VIEW_ACTIONS.get(self.view, ())]
        return result

    def catalog_items(self):
        result = [('control', 'catalog_prepare'), ('control', 'catalog_reload')]
        for row in self.catalog_rows():
            result += [('catalog_target', row['product_id']), ('catalog_source', row['product_id'])]
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
            elif value == 'internet_mode':
                current = self.t('internet_mode_' + current)
            elif value == 'theme':
                current = self.t('theme_' + current)
            elif isinstance(current, bool):
                current = '[x]' if current else '[ ]'
            return self.t(value) + ': ' + str(current)
        if kind == 'target':
            row = self.inventory_row(value)
            return ('[x] ' if self.row_enabled(row) else '[ ] ') + plain(row['name'])
        if kind == 'catalog_target':
            row = self.catalog_row(value)
            return (('[x] ' if value in self.catalog_selected else '[ ] ') + plain(row.get('name', value))
                    + ' (' + self.t('catalog_status_' + row.get('installation_status', 'manual')) + ')')
        if kind == 'catalog_source':
            source = self.catalog_sources.get(value)
            return self.t('inventory_source') + ': ' + (self.source_name(source) if source else self.t('catalog_choose_source'))
        if kind == 'control':
            return {'internet_mode': self.t('internet_mode') + ': ' + self.t('internet_mode_' + self.settings['internet_mode']),
                    'catalog_prepare': self.t('catalog_prepare'), 'catalog_reload': self.t('inventory_reload'),
                    'installed_default': self.t('installed_default_enabled' if self.installed_default_enabled else 'installed_default_enable'),
                    'search': self.t('inventory_search') + ': ' + self.inventory_query,
                    'source': self.t('inventory_source') + ': ' + self.source_name(self.inventory_source),
                    'sort': self.t('inventory_sort') + ': ' + self.t('inventory_sort_' + self.inventory_sort),
                    'reload': self.t('inventory_reload'), 'toolkit_apply': self.t('toolkit_apply')}.get(value, value)
        if kind == 'action':
            return self.t('action_' + value)
        if kind == 'history':
            row = self.history[int(value)]
            return row['timestamp'] + ' | ' + row['exit_class']
        return self.t(value)

    def details(self):
        if self.focus == 3:
            buttons = self.footer_buttons()
            button = buttons[min(self.footer_selected, len(buttons) - 1)]
            if self.button_disabled(button):
                return [self.t('inventory_save_first') if self.inventory_changes else self.t('disabled_control')]
        item = self.selected_item()
        lines = [self.t('wizarddesc_' + STEPS[self.wizard_step]), ''] if self.view == 'wizard' else []
        if item:
            kind, value = item
            if kind == 'target':
                row = self.inventory_row(value)
                lines += [plain(row['name']), self.row_version(row, detail=True), self.source_name(row.get('source')),
                          plain(row.get('path', '')), '', self.row_reason(row), '', self.t('inventory_scope_note')]
            elif kind == 'action':
                lines += [self.t('desc_' + value), '']
                try:
                    lines += [shlex.join(build_command(self.repo, value, self.settings['groups'], self.settings)), '']
                except (OSError, ValueError, StoreError) as exc:
                    lines += [plain(exc), '']
            elif kind in ('setting', 'control') and value == 'internet_mode':
                lines += [self.t('internet_batch_hint'), '', self.t('internet_per_app_hint'), '']
            elif kind in ('setting', 'group'):
                lines += [self.t('groups_hint' if kind == 'group' else 'settings_hint'), '']
            elif kind == 'control' and self.view in ('inventory', 'updates'):
                lines += [self.t('inventory_scope_note'), '']
            elif kind == 'history':
                row = self.history[int(value)]
                lines += [row['filename'], row['run_status'], row['exit_class'], self.t('elapsed') + ': ' + str(row['duration_seconds']) + ' s', '']
        lines += [self.t('serial_notice'), '', self.t('controls_hint')]
        return lines

    def context_help(self):
        if self.modal == 'input':
            return [self.t('context_answer')]
        if self.modal:
            return [self.t('context_confirm')]
        if self.view == 'wizard':
            return [self.t('context_navigation'), self.t('context_wizard')]
        key = {'home': 'desc_preview', 'updates': 'groups_hint', 'inventory': 'inventory_scope_note',
               'catalog': 'desc_catalog', 'diagnostics': 'desc_doctor', 'history': 'history_hint',
               'settings': 'settings_hint', 'about': 'toolkit_idle', 'help': 'readonly_notice'}[self.view]
        item = self.selected_item()
        if item and item[0] == 'action':
            key = 'desc_' + item[1]
        if item and item[0].startswith('catalog_'):
            row = self.catalog_row(item[1])
            return [self.t('context_navigation'), self.t('catalog_status_' + row.get('installation_status', 'manual')), self.t('catalog_hint')]
        if item and item == ('control', 'installed_default'):
            return [self.t('context_navigation'), self.t('installed_default_scope')]
        return [self.t('context_navigation'), self.t(key)]

    def draw_context(self, canvas, top, x, width, bottom):
        room = max(1, bottom - top + 1)
        instruction = [line for text in self.context_help() for line in wrapped(text, width)]
        compact_running = self.cols <= 80 and self.rows <= 24 and self.busy() and self.job_action == 'update'
        y = top
        # Reserve live status before optional long help, including at 80x24.
        workflow = self.t('context_workflow', status=self.t(self.status))
        status_lines = wrapped(workflow, width) if cell_width(workflow) <= width else (wrapped(self.t('context_workflow', status='').strip(), width) + wrapped(self.t(self.status), width))
        for line in status_lines:
            canvas.put(y, x, line, 1, width)
            y += 1
        if self.progress is not None:
            canvas.put(y, x, str(self.progress) + '% ' + self.t('phase_progress'), 3, width)
            y += 1
        if self.job and self.job.started_at:
            canvas.put(y, x, self.t('elapsed') + ': ' + str(max(0, int(time.monotonic() - self.job.started_at))) + 's', 3, width)
            y += 1
        if self.job_action == 'update':
            total = len(self.settings['groups'])
            done = sum(self.group_states[group] in ('completed','warnings','failed','skipped') for group in self.settings['groups'])
            for line in wrapped(self.t('context_group_counts', done=done, total=total), width):
                canvas.put(y, x, line, 3, width)
                y += 1
        if compact_running:
            for group in GROUPS:
                if self.group_states[group] == 'running':
                    for line in wrapped(self.t('group_' + group) + ': ' + self.t('running'), width):
                        if y <= bottom:
                            canvas.put(y, x, line, 3, width)
                            y += 1
            y += 1
            for paragraph in self.context_help():
                lines = wrapped(paragraph, width)
                if len(lines) <= bottom - y + 1:
                    for line in lines:
                        canvas.put(y, x, line, 0, width)
                        y += 1
            return
        y += 1
        budget = min(len(instruction), max(3, min(8, bottom - y - 3)))
        for line in instruction[:budget]:
            if y <= bottom:
                canvas.put(y, x, line, 0, width)
            y += 1
        y += 1
        if self.job_action:
            for line in wrapped(self.t('action_' + self.job_action), width)[:2]:
                if y <= bottom:
                    canvas.put(y, x, line, 3, width)
                    y += 1
        item = self.selected_item()
        if item and item[0] == 'target':
            row = self.inventory_row(item[1])
            activity, elapsed = self.row_activity(row)
            event = self.target_states.get(self.target_key(row), {})
            status = self.t('native_pending') if event.get('status') in ('triggered_unconfirmed', 'observed_version_changed', 'legacy_handler_completed_unconfirmed') else self.t('inventory_status_' + self.row_status(row)) if self.row_status(row) in ('enabled','excluded','manual','blocked') else self.t(self.row_status(row))
            values = [row['name'], status, self.row_version(row, detail=True), activity + ' ' + elapsed, self.row_reason(row)]
            for text in values:
                for line in wrapped(text, width):
                    if y <= bottom:
                        canvas.put(y, x, line, 4 if self.row_status(row) in ('warnings','failed','blocked') else 0, width)
                        y += 1
        elif self.job_action == 'update':
            for group in GROUPS:
                if y <= bottom:
                    text = self.t('group_' + group) + ': ' + self.t(self.group_states[group])
                    for line in wrapped(text, width):
                        if y <= bottom:
                            canvas.put(y, x, line, 3, width)
                            y += 1

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

    def activate(self, checkbox_only=False):
        item = self.selected_item()
        if item is None:
            return
        kind, value = item
        if checkbox_only and kind not in ('group', 'target', 'setting', 'catalog_target'):
            return
        if kind in ('group', 'target', 'setting', 'catalog_target', 'catalog_source') and self.busy():
            self.notice = self.t('busy')
            return
        if kind == 'action':
            self.request_action(value)
        elif kind == 'catalog_target':
            self.catalog_plan = None
            if value in self.catalog_selected:
                self.catalog_selected.remove(value)
            else:
                self.catalog_selected.add(value)
        elif kind == 'catalog_source':
            self.catalog_plan = None
            choices = [source['source_id'] for source in self.catalog_row(value).get('sources', [])]
            if choices:
                current = self.catalog_sources.get(value)
                self.catalog_sources[value] = choices[(choices.index(current) + 1) % len(choices)] if current in choices else choices[0]
        elif kind == 'group':
            groups = self.settings['groups']
            if value in groups:
                groups.remove(value)
            else:
                groups.append(value)
        elif kind == 'target':
            row = self.inventory_row(value)
            selected_id = self.selection_id(row)
            enabled = not self.row_enabled(row)
            if selected_id is None:
                match = self.exclusion_row(row)
                if match and (not enabled or self.inventory_changes.get(match['id']) is False):
                    selected_id = match['id']
            if selected_id is None:
                self.notice = self.t('inventory_unavailable')
                return
            if enabled == row.get('enabled', False):
                self.inventory_changes.pop(selected_id, None)
            else:
                self.inventory_changes[selected_id] = enabled
            self.notice = self.t('inventory_changes', count=len(self.inventory_changes))
        elif kind == 'setting':
            if value == 'language':
                self.settings[value] = LANGUAGES[(LANGUAGES.index(self.settings[value]) + 1) % len(LANGUAGES)]
            elif value == 'internet_mode':
                self.settings[value] = 'per_app' if self.settings[value] == 'automatic' else 'automatic'
            elif value == 'theme':
                self.settings[value] = 'light' if self.settings[value] == 'dark' else 'dark'
            else:
                self.settings[value] = not self.settings[value]
        elif kind == 'control':
            if value in ('catalog_prepare', 'catalog_reload', 'installed_default'):
                if self.busy():
                    self.notice = self.t('busy')
                    return
                if value == 'catalog_prepare':
                    self.prepare_catalog()
                elif value == 'catalog_reload':
                    self.reload_catalog()
                else:
                    self.modal, self.modal_selected = 'installed_default', 0
            elif value == 'internet_mode':
                if self.busy():
                    self.notice = self.t('busy')
                    return
                self.settings['internet_mode'] = 'per_app' if self.settings['internet_mode'] == 'automatic' else 'automatic'
                self.notice = self.t('internet_mode_changed')
            elif value == 'search':
                self.modal, self.buffer, self.modal_selected = 'search', self.inventory_query, 0
            elif value == 'source':
                sources = ['all'] + sorted({r.get('source', 'unknown') for r in (self.inventory_model or {}).get('rows', [])})
                self.inventory_source = sources[(sources.index(self.inventory_source) + 1) % len(sources)] if self.inventory_source in sources else 'all'
                self.selected = 0
            elif value == 'sort':
                sorts = ('source', 'name', 'version', 'status')
                self.inventory_sort = sorts[(sorts.index(self.inventory_sort) + 1) % len(sorts)]
            elif value == 'reload':
                self.reload_inventory()
            elif value == 'toolkit_apply':
                self.activate_button('toolkit_apply')

    def request_action(self, action):
        if self.busy():
            self.notice = self.t('busy')
            return
        if self.inventory_changes and action in ('update', 'preview'):
            self.notice = self.t('inventory_save_first')
            return
        if action not in ACTIONS:
            return
        if action != 'catalog':
            self.catalog_plan = None
        try:
            extra = {'install_plan': self.catalog_plan} if action == 'catalog' and self.catalog_plan else {}
            build_command(self.repo, action, self.settings['groups'], self.settings, **extra)
        except (OSError, ValueError, StoreError) as exc:
            self.notice = self.t('error', message=plain(exc))
            return
        self.pending_action = action
        if ACTIONS[action]['mutating']:
            self.modal, self.modal_selected = 'confirm', 0
        else:
            self.start_job(action)

    def start_job(self, action):
        try:
            extra = {'install_plan': self.catalog_plan} if action == 'catalog' and self.catalog_plan else {}
            job = TerminalJob(self.repo, action, self.settings['groups'], self.settings, **extra)
            job.resize(max(10, self.rows - 8), max(40, self.cols - 30))
            job.start()
            self.job, self.job_action = job, action
            if action == 'catalog':
                self.catalog_plan = None
            self.last_command = list(job.command)
            self.log, self.partial, self.progress, self.log_scroll = [], '', None, 0
            self.status, self.notice, self.modal = 'running', '', None
            self.last_returncode = None
            self.prompt_pending, self._deferred_prompt, self._secret_prompt_seen = False, False, False
            if action == 'update':
                self.target_states, self.target_timings = {}, {}
            self.group_states = {g: ('queued' if g in self.settings['groups'] else 'skipped') for g in GROUPS} if action == 'update' else {g: 'idle' for g in GROUPS}
        except (OSError, ValueError, StoreError) as exc:
            self.notice, self.modal = self.t('error', message=plain(exc)), None

    def tick(self):
        if self.job is None:
            return
        for chunk in self.job.poll():
            clean = plain(chunk.replace('\r\n', '\n').replace('\r', '\n'))
            pieces = (self.partial + clean).split('\n')
            tail = pieces.pop()
            self.partial = tail[-65536:] if tail.startswith('@@MAC_UPDATE_TOOLKIT ') else tail[-16384:] if tail.startswith('@@MAC_UPDATE_') else tail[-4096:]
            for line in pieces:
                if line == '@@MAC_UPDATE_CANDIDATES_BEGIN':
                    self._candidate_batch = []
                    continue
                if line == '@@MAC_UPDATE_CANDIDATES_END':
                    if self._candidate_batch is not None:
                        self.preview_rows, self._candidate_batch = self._candidate_batch, None
                    continue
                if line.startswith(('@@MAC_UPDATE_CANDIDATE ', '@@MAC_UPDATE_TARGET ')):
                    try:
                        row = json.loads(line.split(' ', 1)[1])
                        if isinstance(row, dict) and self.target_key(row) is not None:
                            if line.startswith('@@MAC_UPDATE_CANDIDATE ') and self._candidate_batch is not None and len(self._candidate_batch) < 20000 and isinstance(row.get('id'), str):
                                self._candidate_batch.append(row)
                            elif line.startswith('@@MAC_UPDATE_TARGET ') and self.job_action == 'update':
                                key = self.target_key(row)
                                now = time.monotonic()
                                if row.get('status') in ('running', 'vendor_updater_observing', 'observed_version_changed'):
                                    self.target_timings.setdefault(key, [now, None])[1] = None
                                elif key in self.target_timings:
                                    self.target_timings[key][1] = now
                                self.target_states[key] = row
                    except (ValueError, TypeError):
                        pass
                    continue
                if re.fullmatch(r'@@MAC_UPDATE_PROMPT(?: [a-zA-Z0-9_.:-]+)?', line):
                    self.prompt_pending, self._deferred_prompt = True, True
                    continue
                if line.startswith('@@MAC_UPDATE_TOOLKIT ') and self.job_action in ('toolkit_check', 'toolkit_prepare'):
                    try:
                        report = json.loads(line[len('@@MAC_UPDATE_TOOLKIT '):])
                        if isinstance(report, dict):
                            self.toolkit_report = report
                    except (ValueError, TypeError):
                        self.notice = self.t('toolkit_idle')
                    continue
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
            if not self._secret_prompt_seen:
                self._deferred_prompt = True
            self._secret_prompt_seen = True
        elif not self.job.secret_input:
            self._secret_prompt_seen = False
        if self._deferred_prompt and self.job.running and self.modal in (None, 'input'):
            self.open_input()
            self._deferred_prompt = False
        if not self.job.running and self.last_returncode is None:
            self.last_returncode = self.job.returncode
            if self.last_returncode is not None:
                self.status = 'completed' if self.last_returncode == 0 else 'warnings' if self.last_returncode == 10 else 'failed'
                if self.last_returncode in (0, 10):
                    self.completed_actions.add(self.job_action)
                self.group_states = {g: ('unknown' if state in ('running', 'queued') else state) for g, state in self.group_states.items()}
                for timing in self.target_timings.values():
                    if timing[1] is None:
                        timing[1] = time.monotonic()
                if self.modal == 'input':
                    self.modal, self.buffer = None, ''
                self.prompt_pending, self._deferred_prompt = False, False
                if self.job_action in ('preview', 'inventory') and not self.inventory_changes:
                    self.reload_candidates()
                    if self.job_action == 'preview' and self.view != 'wizard':
                        self.change_view('updates')
                        self.focus = 1
                        self.selected = next((i for i, item in enumerate(self.items()) if item[0] == 'target'), 0)
                self.notice = self.t('job_finished', code=self.last_returncode)
                if self.exit_after_job:
                    self.should_exit = True

    def log_line_count(self):
        left, right = panel_sizes(self.cols)
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
        # Only a terminal's bracketed-paste protocol identifies paste. Ordinary
        # key events can arrive in one read and must not be discarded as text.
        combined = self._escape_buffer + ''.join(k for k in keys if isinstance(k, str))
        if combined.startswith('\x1b') and len(combined) > 1 and not combined.startswith('\x1b['):
            self._escape_buffer = ''
            self.key('\x1b')
            keys = list(combined[1:])
            combined = combined[1:]
        if '\x1b' in combined and not self._pasting and not ('\x1b[200~'.startswith(combined) or combined.startswith('\x1b[200~')):
            self._escape_buffer = ''
            if len(keys) == 1 and keys[0] == '\x1b':
                self.key('\x1b')
            else:
                self.paste_text(combined)
            return
        opened_confirmation = False
        for key in keys:
            if self._pasting:
                if isinstance(key, str):
                    self._paste_buffer += key
                    if self._paste_buffer.endswith('\x1b[201~'):
                        self.paste_text(self._paste_buffer[:-6])
                        self._pasting, self._paste_buffer = False, ''
                        return
                    self._paste_buffer = self._paste_buffer[-8192:]
                continue
            if isinstance(key, str) and (self._escape_buffer or key == '\x1b'):
                self._escape_buffer += key
                self._escape_started = time.monotonic()
                if self._escape_buffer == '\x1b[200~':
                    self._pasting, self._escape_buffer = True, ''
                elif not '\x1b[200~'.startswith(self._escape_buffer):
                    self._escape_buffer = ''
                continue
            if opened_confirmation and self.modal in ('confirm', 'interrupt', 'quit', 'discard', 'apply_toolkit', 'installed_default'):
                continue  # The new confirmation has not been shown on screen yet.
            before = self.modal
            self.key(key)
            if before != self.modal and self.modal in ('confirm', 'interrupt', 'quit', 'discard', 'apply_toolkit', 'installed_default'):
                opened_confirmation = True

    def flush_escape(self):
        if self._escape_buffer and time.monotonic() - self._escape_started > .08:
            self._escape_buffer = ''
            self.key('\x1b')

    def key(self, key):
        if key == curses.KEY_RESIZE:
            return
        if self.rows < 24 or self.cols < 80:
            if key in ('q', '\x1b') and not self.busy():
                self.should_exit = True
            return
        if self.modal:
            self.modal_key(key)
            return
        if key in ('q', '\x03'):
            if self.busy():
                self.modal, self.modal_selected = 'quit', 0
            else:
                self.should_exit = True
        elif key in ('?', curses.KEY_F1):
            self.change_view('help')
            self.focus = 1
        elif key == '\x10':
            self.modal, self.palette_search, self.palette_index = 'palette', '', 0
        elif key == '\t':
            if self.focus == 0:
                self.focus = 1
            elif self.focus == 1:
                self.focus, self.footer_selected = 3, 0
            elif self.focus == 3 and self.footer_selected + 1 < len(self.footer_buttons()):
                self.footer_selected += 1
            else:
                self.focus = 2 if self.focus == 3 else 0
        elif key == curses.KEY_BTAB:
            if self.focus == 3 and self.footer_selected:
                self.footer_selected -= 1
            else:
                self.focus = {0: 2, 1: 0, 3: 1, 2: 3}[self.focus]
        elif key == '\x1b':
            self.focus = 0
        elif key in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_LEFT, curses.KEY_RIGHT):
            direction = 1 if key in (curses.KEY_DOWN, curses.KEY_RIGHT) else -1
            if self.focus == 3:
                self.footer_selected = (self.footer_selected + direction) % len(self.footer_buttons())
            elif self.focus == 0:
                self.change_view(VIEWS[(VIEWS.index(self.view) + direction) % len(VIEWS)])
            elif self.focus == 2:
                self.log_scroll = max(0, min(self.log_line_count(), self.log_scroll - direction))
            elif self.view == 'help':
                self.help_scroll = max(0, self.help_scroll + direction)
            elif self.items():
                self.selected = (self.selected + direction) % len(self.items())
        elif key in (curses.KEY_PPAGE, curses.KEY_NPAGE):
            direction = -1 if key == curses.KEY_PPAGE else 1
            if self.focus == 1 and self.view in ('updates', 'inventory') and self.items():
                self.selected = max(0, min(len(self.items()) - 1, self.selected + direction * max(3, self.rows - 16)))
            elif self.view == 'help' and self.focus == 1:
                self.help_scroll = max(0, self.help_scroll + direction * 6)
            else:
                self.log_scroll = max(0, min(self.log_line_count(), self.log_scroll - direction * 6))
        elif key in ('\n', '\r', curses.KEY_ENTER):
            if self.focus == 0:
                self.focus = 1
            elif self.focus == 1:
                self.activate()
            elif self.focus == 3:
                buttons = self.footer_buttons()
                self.activate_button(buttons[min(self.footer_selected, len(buttons) - 1)])
        elif key == ' ' and self.focus == 1:
            self.activate(checkbox_only=True)
        elif key == 'r':
            item = self.selected_item()
            if item and item[0] == 'action':
                self.request_action(item[1])
        elif key == 'd':
            self.request_action('preview')
        elif key == 's':
            self.change_view('settings')
            self.focus = 1
        elif key == '/' and self.view in ('inventory', 'updates'):
            self.modal, self.buffer, self.modal_selected = 'search', self.inventory_query, 0
        elif key == 'c':
            self.copy()
        elif key == 'i':
            self.open_input()
        elif key == 'x' and self.busy():
            self.modal, self.modal_selected = 'interrupt', 0

    def confirm_modal(self):
        modal, self.modal = self.modal, None
        if modal == 'installed_default':
            try:
                from policy_runtime import set_installed_update_default
                set_installed_update_default(True, allow_registered_vendor_groups=True)
                self.installed_default_enabled = True
                self.notice = self.t('saved')
            except (OSError, ValueError, StoreError) as exc:
                self.notice = self.t('error', message=plain(exc))
        elif modal == 'confirm':
            self.start_job(self.pending_action)
        elif modal == 'discard':
            self.reload_inventory(force=True)
        elif modal == 'apply_toolkit':
            if not self.busy() and self.toolkit_report and self.toolkit_report.get('status') == 'ready':
                self.pending_toolkit_receipt = self.toolkit_report.get('receipt')
                self.should_exit = True
        else:
            self.exit_after_job = modal == 'quit'
            if self.busy():
                self.job.interrupt()
                self.status = 'running'

    def send_answer(self):
        if self.busy():
            self.job.send(self.buffer + '\n')
        self.buffer, self.modal, self.status = '', None, 'running'
        self.input_secret, self.prompt_pending = False, False

    def modal_key(self, key):
        if key == '\x1b':
            if self.modal == 'input':
                self.notice = self.t('prompt_cancelled')
            self.modal, self.buffer = None, ''
            self.input_secret = False
            return
        confirmations = ('confirm', 'interrupt', 'quit', 'discard', 'apply_toolkit', 'installed_default')
        if self.modal in confirmations:
            if key in ('\t', curses.KEY_LEFT, curses.KEY_RIGHT):
                self.modal_selected = 1 - self.modal_selected
            elif key == 'y':
                self.confirm_modal()
            elif key in ('\n', '\r', curses.KEY_ENTER):
                if self.modal_selected == 1:
                    self.confirm_modal()
                else:
                    self.modal = None
            elif key in ('n', 'q'):
                self.modal = None
            return
        if self.modal == 'palette':
            items = self.palette_actions()
            if key in (curses.KEY_UP, curses.KEY_DOWN) and items:
                self.palette_index = (self.palette_index + (1 if key == curses.KEY_DOWN else -1)) % len(items)
            elif key in ('\n', '\r', curses.KEY_ENTER) and items:
                self.modal = None
                self.request_action(items[min(self.palette_index, len(items) - 1)])
            elif key in (curses.KEY_BACKSPACE, '\x7f', '\b'):
                self.palette_search = self.palette_search[:-1]
            elif isinstance(key, str) and key.isprintable():
                self.palette_search = (self.palette_search + key)[:80]
                self.palette_index = 0
            return
        if self.modal in ('input', 'search'):
            if key in (curses.KEY_PPAGE, curses.KEY_NPAGE) and self.modal == 'input':
                self.log_scroll = max(0, self.log_scroll + (6 if key == curses.KEY_PPAGE else -6))
            elif key == '\x16':
                self.clipboard('paste')
            elif key == '\t':
                self.modal_selected = (self.modal_selected + 1) % 3
            elif key in ('\n', '\r', curses.KEY_ENTER):
                if self.modal == 'search':
                    self.inventory_query, self.modal = self.buffer.strip(), None
                    self.buffer, self.selected = '', 0
                elif self.modal_selected == 2:
                    self.modal, self.buffer, self.input_secret = None, '', False
                    self.notice = self.t('prompt_cancelled')
                else:
                    self.send_answer()
            elif key in (curses.KEY_BACKSPACE, '\x7f', '\b'):
                self.buffer = self.buffer[:-1]
            elif key == '\x15':
                self.buffer = ''
            elif isinstance(key, str) and key.isprintable():
                self.buffer = (self.buffer + key)[:4096 if self.modal == 'input' else 120]

    @staticmethod
    def padded(value, width):
        value = clip(value, width)
        return value + ' ' * max(0, width - cell_width(value))

    def draw_buttons(self, canvas, y, x, width, buttons, selected=None, focused=False, maximum=2, checkbox=False):
        start, row = x, y
        for index, (label, disabled) in enumerate(buttons):
            text = clip(label, width) if checkbox else '[ ' + clip(label, max(1, width - 4)) + ' ]'
            size = cell_width(text)
            if start + size > x + width and start > x:
                row, start = row + 1, x
            if row >= y + maximum:
                break
            style = 3 if disabled else 1 if focused and index == selected else 0
            canvas.put(row, start, text, style, width - (start - x))
            start += size + 1
        return row + 1

    def draw_items(self, canvas, x, y, width, bottom, items):
        """Scroll whole controls into view and wrap their labels in narrow panes."""
        rows, starts = [], []
        for index, item in enumerate(items):
            starts.append(len(rows))
            label = self.item_label(item)
            if item[0] in ('action', 'control', 'catalog_source'):
                label = '[ ' + label + ' ]'
            for number, line in enumerate(wrapped(label, max(1, width - 2))):
                rows.append((index, ('> ' if index == self.selected and number == 0 else '  ') + line))
        room = max(0, bottom - y + 1)
        cursor = min(self.selected, len(starts) - 1) if starts else 0
        end = starts[cursor + 1] if cursor + 1 < len(starts) else len(rows)
        offset = max(0, end - room) if starts else 0
        for index, line in rows[offset:offset + room]:
            canvas.put(y, x, line, 1 if self.focus == 1 and index == self.selected else 0, width)
            y += 1

    def draw_inventory(self, canvas, x, y, width, bottom):
        selected = self.selected_item()
        controls = [item for item in self.items() if item[0] != 'target']
        compact_running = self.cols <= 80 and self.rows <= 24 and self.busy() and self.job_action == 'update'
        if compact_running:
            pass
        elif width < 70:
            control_bottom = min(bottom - 3, y + 7)
            self.draw_items(canvas, x, y, width, control_bottom, controls)
            y = control_bottom + 1
        else:
            for kind in ('action', 'group', 'control'):
                items = [item for item in controls if item[0] == kind]
                labels = [(self.item_label(item), self.busy()) for item in items]
                chosen = items.index(selected) if selected in items else None
                y = self.draw_buttons(canvas, y, x, width, labels, chosen, self.focus == 1, max(1, len(items)), checkbox=kind == 'group')
        if self.inventory_changes:
            canvas.put(y, x, self.t('inventory_changes', count=len(self.inventory_changes)), 4, width)
            y += 1
        status_width = max(16, min(22, max(cell_width(self.t('inventory_status_' + state)) for state in ('enabled', 'excluded', 'manual', 'blocked'))))
        if compact_running:
            status_width = max(cell_width(self.t(state)) for state in ('running', 'completed', 'warnings', 'failed'))
        version_width, activity_width, elapsed_width = (8, 10, 6) if width >= 70 else (max(5, cell_width(self.t('inventory_column_version'))), 9, 5)
        compact = width < 50
        medium = 50 <= width < 70
        name_width = max(5, width - status_width - 5) if compact else max(5, width - status_width - version_width - 6) if medium else max(5, width - status_width - version_width - activity_width - elapsed_width - 8)
        header = self.padded(self.t('inventory_column_name'), name_width + 5) + self.t('inventory_column_status') if compact else self.padded(self.t('inventory_column_name'), name_width + 5) + self.padded(self.t('inventory_column_version'), version_width + 1) + self.t('inventory_column_status') if medium else None
        if header is not None:
            canvas.put(y, x, header, 3, width)
        else:
            canvas.put(y, x, self.padded(self.t('inventory_column_name'), name_width + 5)
                   + self.padded(self.t('inventory_column_version'), version_width + 1)
                   + self.padded(self.t('inventory_column_status'), status_width + 1)
                   + self.padded(self.t('inventory_column_activity'), activity_width + 1)
                   + self.t('inventory_column_elapsed'), 3, width)
        y += 1
        rows = self.visible_inventory_rows()
        if compact_running:
            rows = sorted(rows, key=lambda row: self.row_status(row) != 'running')
        if not rows:
            for line in wrapped(self.inventory_error or self.t('inventory_empty'), width)[:max(0, bottom - y + 1)]:
                canvas.put(y, x, line, 3, width)
                y += 1
            return
        entries, previous = [], None
        for record in rows:
            if not compact_running and record.get('source') != previous:
                previous = record.get('source')
                entries.append(('heading', previous))
            entries.append(('row', record))
        cursor = 0 if compact_running else next((i for i, item in enumerate(entries) if item[0] == 'row' and selected == ('target', item[1]['id'])), 0)
        room = max(1, bottom - y + 1)
        offset = max(0, cursor - room + 1)
        for kind, record in entries[offset:offset + room]:
            if kind == 'heading':
                canvas.put(y, x, self.source_name(record), 1, width)
            else:
                status = self.row_status(record)
                label = self.t('inventory_status_' + status) if status in ('enabled', 'excluded', 'manual', 'blocked') else self.t(status)
                event = self.target_states.get(self.target_key(record), {})
                if status == 'warnings' and event.get('status') in ('triggered_unconfirmed', 'vendor_updater_observing', 'observed_version_changed', 'legacy_handler_completed_unconfirmed'):
                    label = self.t('native_pending')
                mark = '[x] ' if self.row_enabled(record) else '[ ] '
                activity, elapsed = self.row_activity(record)
                line = (mark + self.padded(record.get('name', ''), name_width) + ' '
                        + self.padded(self.row_version(record), version_width) + ' '
                        + self.padded(label, status_width) + ' ' + self.padded(activity, activity_width) + ' '
                        + self.padded(elapsed, elapsed_width))
                if compact:
                    line = mark + self.padded(record.get('name',''), name_width) + ' ' + label
                elif medium:
                    line = mark + self.padded(record.get('name',''), name_width) + ' ' + self.padded(self.row_version(record), version_width) + ' ' + label
                style = 1 if status == 'running' or self.focus == 1 and selected == ('target', record['id']) else 4 if status in ('failed', 'blocked', 'warnings', 'unknown') else 5 if status == 'completed' else 3 if status in ('excluded', 'enabled') else 0
                canvas.put(y, x, line, style, width)
            y += 1

    def draw_log(self, canvas, x, top, width, bottom, expanded=False):
        label = self.t('action_' + self.job_action) if self.job_action else self.t('live_log')
        canvas.put(top, x, label, 1, width)
        elapsed = max(0, int(time.monotonic() - self.job.started_at)) if self.job and self.job.started_at else 0
        status = (str(self.progress) + '% ' + self.t('phase_progress')) if self.progress is not None else self.t('activity_unknown') if self.busy() else self.t(self.status)
        canvas.put(top + 1, x, status + ' | ' + str(elapsed) + 's', 3, width)
        if self.job_action == 'preview':
            canvas.put(top + 2, x, self.t('preview_notice'), 3, width)
            top += 1
        output = [line for entry in self.log + ([self.partial] if self.partial else []) for line in wrapped(entry, width)]
        end = max(0, len(output) - self.log_scroll)
        room = max(0, bottom - top - 1)
        for y, line in enumerate(output[max(0, end - room):end], top + 2):
            canvas.put(y, x, line, 0, width)

    def frame(self, height, width):
        self.rows, self.cols = height, width
        canvas = Canvas(height, width, self.settings['ascii'])
        if height < 24 or width < 80:
            canvas.put(0, 0, self.t('app_title'), 1)
            canvas.put(2, 0, self.t('resize'), 4)
            canvas.put(4, 0, 'q / Esc', 3)
            return canvas
        canvas.put(0, 2, self.t('app_title') + '  ' + self.version + ' | Michał Kasprowicz', 1, width - 16)
        badge = self.t(self.status).upper()
        canvas.put(0, max(50, width - cell_width(badge) - 2), badge, 4 if self.status == 'waiting' else 5 if self.status == 'completed' else 3, width - 50)
        left, right = panel_sizes(width)
        middle_x, middle_width = left, width - left - right
        bottom = height - 7
        canvas.box(2, 0, height - 7, left, self.t('actions'), 1 if self.focus == 0 else 2)
        canvas.box(2, middle_x, height - 7, middle_width, self.t('nav_' + self.view), 1 if self.focus in (1, 2) else 2)
        if right:
            canvas.box(2, width - right, height - 7, right, self.t('context_title'))
        spacing = 2 if height >= 33 else 1
        for index, view in enumerate(VIEWS):
            nav_lines = wrapped(self.t('nav_' + view), left - 6)[:spacing] if spacing > 1 else [clip(self.t('nav_' + view), left - 6)]
            for line_index, line in enumerate(nav_lines):
                prefix = '> ' if view == self.view and line_index == 0 else '  '
                canvas.put(3 + index * spacing + line_index, 2, prefix + line, 1 if view == self.view else 0, left - 4)
        canvas.put(height - 8, 2, NATIVE_NAMES[self.settings['language']], 3, left - 4)
        x, usable = middle_x + 2, middle_width - 4
        top, content_bottom = 3, bottom
        have_log = self.job is not None and self.view != 'help'
        if have_log and self.focus != 2:
            log_top = max(top + 6, height - 12)
            content_bottom = log_top - 1
        else:
            log_top = top
        if self.focus == 2 and self.view != 'help':
            self.draw_log(canvas, x, top, usable, bottom, expanded=True)
        elif self.view in ('inventory', 'updates'):
            self.draw_inventory(canvas, x, top, usable, content_bottom)
        elif self.view == 'help':
            lines = wrapped(self.t('controls_hint') + '\n\n' + self.t('help_body'), usable)
            self.help_scroll = min(self.help_scroll, max(0, len(lines) - (bottom - top)))
            for y, line in enumerate(lines[self.help_scroll:self.help_scroll + bottom - top + 1], top):
                canvas.put(y, x, line, 0, usable)
        else:
            y = top
            if self.view == 'about':
                paragraphs = [self.t('about_author'), self.t('about_version', version=self.version), self.t('about_website'), self.t('about_source'), '', self.t('toolkit_idle')]
                if self.toolkit_report:
                    from toolkit_update import toolkit_reason_label, toolkit_status_label
                    state = str(self.toolkit_report.get('status', 'unknown'))
                    status = toolkit_status_label(state, self.settings['language'])
                    paragraphs += ['', self.t('toolkit_result', status=status)]
                    reasons = self.toolkit_report.get('reasons', [])
                    if isinstance(reasons, list):
                        paragraphs += [toolkit_reason_label(reason, self.settings['language']) for reason in reasons[:3] if isinstance(reason, str)]
                    for field in ('current_version', 'latest_version', 'target_version', 'base_sha', 'target_sha'):
                        if self.toolkit_report.get(field):
                            paragraphs.append(plain(self.toolkit_report[field]))
            elif self.view == 'wizard':
                paragraphs = ['%s / %s  %s' % (self.wizard_step + 1, len(STEPS), self.t('wizardstep_' + STEPS[self.wizard_step])), self.t('wizarddesc_' + STEPS[self.wizard_step])]
            elif self.view == 'catalog':
                paragraphs = [self.t('catalog_hint')]
            elif self.view == 'home':
                paragraphs = [self.t('scan_hint')]
            else:
                paragraphs = [self.t('no_history')] if self.view == 'history' and not self.history else []
            items = self.items()
            paragraph_lines = [line for paragraph in paragraphs for line in wrapped(paragraph, usable)]
            paragraph_budget = max(1, content_bottom - y - 5) if items else max(1, content_bottom - y + 1)
            for line in paragraph_lines[:paragraph_budget]:
                canvas.put(y, x, line, 3, usable)
                y += 1
            if self.view == 'catalog' or self.view == 'wizard' and STEPS[self.wizard_step] == 'catalog':
                if self.catalog_error:
                    canvas.put(y, x, self.catalog_error, 4, usable)
                    y += 1
            self.draw_items(canvas, x, y, usable, content_bottom, items)
        if have_log and self.focus != 2:
            self.draw_log(canvas, x, log_top, usable, bottom)
        self.draw_context(canvas, 3, width - right + 2, right - 4, bottom)
        buttons = self.footer_buttons()
        self.footer_selected = min(self.footer_selected, len(buttons) - 1)
        labels = [(self.button_label(button), self.button_disabled(button)) for button in buttons]
        self.draw_buttons(canvas, height - 4, 1, width - 2, labels, self.footer_selected, self.focus == 3, 2)
        notice = self.notice or (self.t('inventory_changes', count=len(self.inventory_changes)) if self.inventory_changes else '')
        canvas.put(height - 2, 1, notice, 4 if self.notice or self.inventory_changes else 3, width - 2)
        canvas.put(height - 1, 1, self.t('controls_hint'), 3, width - 2)
        if self.modal:
            self.render_modal(canvas)
        return canvas

    def render_modal(self, canvas):
        if self.modal == 'input' and self.job and self.job.secret_input:
            self.input_secret = True
        _, context_width = panel_sizes(canvas.width)
        # A dialog replaces the left workspace, including its action row. Keep
        # the live sidebar and global keyboard hint without ghost controls.
        for row in range(2, canvas.height - 1):
            canvas.put(row, 0, ' ' * (canvas.width - context_width))
        for row in range(canvas.height - 5, canvas.height - 1):
            canvas.put(row, 0, ' ' * canvas.width)
        available_width = canvas.width - context_width - 4
        width, height = min(available_width, 88), min(canvas.height - 4, 20)
        if self.modal in ('input', 'search'):
            width, height = available_width, canvas.height - 4
        x, y = 2, (canvas.height - height) // 2
        for row in range(y, y + height):
            canvas.put(row, x, ' ' * width)
        title = self.t('secret_input' if self.modal == 'input' and self.input_secret else 'inventory_search' if self.modal == 'search' else 'input' if self.modal == 'input' else 'search' if self.modal == 'palette' else 'confirm')
        canvas.box(y, x, height, width, title, 1)
        lines = []
        if self.modal in ('input', 'search'):
            if self.modal == 'input':
                context = [line for entry in self.log + ([self.partial] if self.partial else []) for line in wrapped(entry, width - 4)]
                end = max(0, len(context) - self.log_scroll)
                room = max(1, height - 9)
                lines += context[max(0, end - room):end]
            else:
                lines += wrapped(self.t('inventory_scope_note'), width - 4)
            row = y + 2
            for line in lines[:height - 8]:
                canvas.put(row, x + 2, line, 0, width - 4)
                row += 1
            field_y = y + height - 5
            canvas.put(field_y, x + 2, self.t('secret_input' if self.input_secret else 'inventory_search' if self.modal == 'search' else 'input') + ':', 3, width - 4)
            text = '*' * len(self.buffer) if self.modal == 'input' and self.input_secret else self.buffer
            canvas.put(field_y + 1, x + 2, text, 1 if self.modal_selected == 0 else 0, width - 4)
            labels = [(self.t('send_button') if self.modal == 'input' else self.t('inventory_search'), False), (self.t('cancel_button'), False)]
            self.draw_buttons(canvas, y + height - 2, x + 2, width - 4, labels, self.modal_selected - 1, self.modal_selected != 0, 1)
            canvas.put(y + height - 6, x + 2, 'PgUp / PgDn  |  Tab  |  Enter  |  Esc', 3, width - 4)
            return
        if self.modal in ('confirm', 'interrupt', 'quit', 'discard', 'apply_toolkit', 'installed_default'):
            key = 'inventory_discard' if self.modal == 'discard' else 'confirm_body' if self.modal in ('confirm', 'apply_toolkit') else 'quit_body' if self.modal == 'quit' else 'interrupt_body'
            lines = [self.t(key), '']
            if self.modal == 'installed_default':
                lines = [self.t('installed_default_scope')]
            if self.modal == 'confirm' and self.pending_action == 'update' and 'internet' in self.settings['groups'] and self.settings['internet_mode'] == 'automatic':
                lines += [self.t('internet_batch_hint'), '']
            if self.modal == 'confirm':
                lines += [self.t('action_' + self.pending_action), self.t('desc_' + self.pending_action), '']
                try:
                    extra = {'install_plan': self.catalog_plan} if self.pending_action == 'catalog' and self.catalog_plan else {}
                    lines += [shlex.join(build_command(self.repo, self.pending_action, self.settings['groups'], self.settings, **extra))]
                except (OSError, ValueError):
                    pass
            elif self.modal == 'apply_toolkit':
                lines += [self.t('toolkit_apply'), self.t('toolkit_idle')]
                receipt = (self.toolkit_report or {}).get('receipt', {})
                lines += [plain(receipt.get('base_sha', '')), plain(receipt.get('target_sha', ''))]
            row = y + 2
            for paragraph in lines:
                for line in wrapped(paragraph, width - 4):
                    if row < y + height - 3:
                        canvas.put(row, x + 2, line, 0, width - 4)
                        row += 1
            labels = [(self.t('cancel_button'), False), (self.t('installed_default_confirm') if self.modal == 'installed_default' else self.t('confirm'), False)]
            self.draw_buttons(canvas, y + height - 2, x + 2, width - 4, labels, self.modal_selected, True, 1)
            return
        canvas.put(y + 2, x + 2, self.t('search') + ': ' + self.palette_search, 1, width - 4)
        actions = self.palette_actions()
        offset = max(0, self.palette_index - (height - 6))
        for index in range(offset, min(len(actions), offset + height - 5)):
            canvas.put(y + 3 + index - offset, x + 2, ('> ' if index == self.palette_index else '  ') + self.t('action_' + actions[index]), 1 if index == self.palette_index else 0, width - 4)


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

    result = 0
    try:
        sys.stdout.write('\x1b[?2004h')
        sys.stdout.flush()
        with TerminalWindow(sys.stdout, workspace.settings.get('auto_resize', True)):
            try:
                result = curses.wrapper(main)
            except (Exception, KeyboardInterrupt) as exc:
                if workspace.job and workspace.job.running:
                    result = handoff(workspace.job, workspace.t('ui_recovery'))
                else:
                    print(workspace.t('error', message=plain(exc)), file=sys.stderr)
                    result = 2
    finally:
        try:
            sys.stdout.write('\x1b[?2004l')
            sys.stdout.flush()
        except OSError:
            pass

    if workspace.pending_toolkit_receipt is not None:
        from tui_toolkit import finish_update
        return finish_update(repo, workspace.pending_toolkit_receipt, workspace.settings['language'])
    return result
