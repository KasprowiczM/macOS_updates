"""The seven screens. Each screen declares its focus zones, the keymap for
each zone, the help text for the focused element, and draws itself into the
rectangles the app hands it. Screens never start processes directly; they
ask the app (``app.start_run``, ``app.start_task``)."""
import os
import time

import tui_settings as ts
from app_glyphs import glyph_for
from tui_dialogs import ChoiceDialog, Dialog, InputDialog
from tui_keymap import Binding
from tui_runner import item_fraction
from tui_widgets import Rect, clip, duration, pad, plain, scroll_window, text_width, wrap, wrap_items

SCREENS = ('dashboard', 'apps', 'catalog', 'history', 'settings', 'diagnostics', 'about')


class ListState:
    def __init__(self):
        self.index = 0
        self.offset = 0

    def move(self, delta, total):
        if total:
            self.index = max(0, min(total - 1, self.index + delta))

    def clamp(self, total):
        self.index = max(0, min(self.index, max(0, total - 1)))



RESULT_BAR_W = 12   # the duration bars of the Groups list
ITEM_BAR_W = 10     # the bar of an app under a group: fixed, so the status word after it lines up

METHOD_LABELS = {
    'appstore': 'App Store', 'brew_cask': 'Homebrew', 'brew': 'Homebrew', 'npm': 'npm', 'native': 'CLI',
    'sparkle': 'Sparkle', 'squirrel': 'Squirrel', 'electron_updater': 'Electron', 'keystone': 'Google Keystone',
    'microsoft_autoupdate': 'Microsoft AU', 'setapp': 'Setapp', 'adobe': 'Adobe CC',
    'jetbrains_toolbox': 'JetBrains Toolbox', 'system': 'macOS', 'browser_app': 'Browser',
    'vendor_download': 'Vendor', 'app_updater': 'App updater',
}


def method_label(app, row):
    """Method column: how the app updates (from app_detect); a tested row gets ✓."""
    method = row.get('method') or ''
    if not method and not row.get('method_origin'):
        return app.t('ui_method_unknown')
    label = METHOD_LABELS.get(method) or (app.t('ui_method_manual') if method in ('', 'manual') else method)
    return label + (' ✓' if row.get('method_origin') == 'tested' else '')


def bar_phase(app, y=0):
    """The animation counter for a bar that is running right now, else None (the bar stays still). Rows are
    offset by their line so bars never move in lockstep; idle screens never animate."""
    if not app.animate or not app.run_active():
        return None
    return app.tick_count // 2 + y * 3


def status_glyph(app, state, result=None, tick=0):
    g = app.glyphs
    if state == 'running':
        return g['spinner'][tick % len(g['spinner'])] if app.animate else g['running'], 'accent'
    if state == 'off':
        return g['off'], 'muted'
    if state == 'pending':
        return g['pending'], 'muted'
    return {'ok': (g['ok'], 'ok'), 'warn': (g['needs'], 'warn'), 'failed': (g['fail'], 'fail'),
            'off': (g['off'], 'muted')}.get(result, (g['ok'], 'ok'))


def item_glyph(app, result):
    g = app.glyphs
    return {'updated': (g['ok'], 'ok'), 'current': (g['current'], 'muted'), 'needs_you': (g['needs'], 'warn'),
            'failed': (g['fail'], 'fail'), 'skipped': (g['off'], 'muted')}.get(result, (g['running'], 'accent'))


def draw_wrapped(c, rect, text, style='base', offset=0):
    lines = wrap(text, rect.w)
    for i, line in enumerate(lines[offset:offset + rect.h]):
        c.put(rect.y + i, rect.x, line, style, rect.w)
    return len(lines)


class Screen:
    id = ''
    tab = ''

    def zones(self, app):
        return ['main']

    def bindings(self, app, zone):
        return []

    def help(self, app, zone):
        return ''

    def render(self, app, c, main, side):
        pass

    def action(self, app, zone, action):
        return False

    def text(self, app, zone, text):
        return False

    def click(self, app, payload, double=False):
        return False

    def scroll(self, app, zone, delta):
        return False

    def on_enter(self, app):
        pass

    def pane_focus(self, app, *zones):
        return app.zone in zones and app.dialog is None


# ---------------------------------------------------------------------------
class Dashboard(Screen):
    id, tab = 'dashboard', 'ui_tab_dashboard'

    def __init__(self):
        self.button = 0
        self.groups = ListState()
        self.expanded, self.collapsed = set(), set()
        self.sel, self.offset, self.follow = 0, 0, True
        self.result_open, self.result_sel = set(), 0
        self.result_scroll = 0
        self.status_scroll = 0
        self.result_bars = {}

    def result_mode(self, app):
        return app.show_result and app.last_model is not None and not app.run_active()

    def zones(self, app):
        if self.result_mode(app):
            return ['actions', 'result']
        return ['actions', 'groups', 'log' if app.run_active() else 'status']

    def buttons(self, app):
        if self.result_mode(app):
            out = [('ui_btn_done', 'done'), ('ui_btn_log', 'log'), ('ui_btn_again', 'again')]
            if app.last_model.dry_run and app.last_model.counts()['available'] > 0:
                out.insert(0, ('ui_btn_update_now', 'update_now'))      # a preview that found updates: apply them
            return out
        if app.run_active():
            out = []
            if app.prompt_hidden:
                out.append(('ui_btn_answer', 'answer'))
            return out + [('ui_btn_stop', 'stop'), ('ui_btn_log', 'log')]
        primary = 'ui_btn_check_all' if app.settings.get('check_only') else 'ui_btn_update'
        chosen = app.enabled_groups()
        if primary == 'ui_btn_update' and 0 < len(chosen) < len(ts.GROUPS):
            primary = ('ui_btn_update_n', dict(n=len(chosen), total=len(ts.GROUPS)))
        return [(primary, 'update'), ('ui_btn_preview', 'preview')]

    @staticmethod
    def label_text(app, label):
        return app.t(label[0], **label[1]) if isinstance(label, tuple) else app.t(label)

    def button_disabled(self, app, what):
        return what in ('update', 'preview') and not app.run_active() and not app.enabled_groups()

    def bindings(self, app, zone):
        if zone == 'actions':
            return [Binding(('enter',), 'ui_key_select', 'press'), Binding(('left', 'right'), 'ui_key_other_button', 'hmove'),
                    Binding(('down',), 'ui_key_move', 'down', show=False), Binding(('up',), 'ui_key_move', 'up', show=False)]
        if zone == 'groups':
            out = [Binding(('up', 'down'), 'ui_key_move', 'vmove'), Binding(('enter',), 'ui_key_expand', 'enter')]
            if not app.run_active():
                out.append(Binding(('space',), 'ui_key_toggle', 'space'))
                out.append(Binding(('a',), 'ui_key_all', 'all'))
            return out + [Binding(('pgup', 'pgdn'), 'ui_key_scroll', 'page', show=False),
                          Binding(('home', 'end'), 'ui_key_scroll', 'ends', show=False)]
        if zone == 'log':
            return [Binding(('up', 'down'), 'ui_key_scroll', 'vmove'), Binding(('enter',), 'ui_key_expand', 'expand'),
                    Binding(('pgup', 'pgdn'), 'ui_key_scroll', 'page', show=False),
                    Binding(('home', 'end'), 'ui_key_scroll', 'ends', show=False)]
        if zone == 'result':
            return [Binding(('up', 'down'), 'ui_key_move', 'vmove'), Binding(('enter',), 'ui_key_expand', 'result_toggle'),
                    Binding(('pgup', 'pgdn'), 'ui_key_scroll', 'page', show=False)]
        if zone == 'status':
            out = [Binding(('up', 'down'), 'ui_key_scroll', 'vmove')]
            if app.schedule().get('state') == 'off':
                out.append(Binding(('enter',), 'ui_btn_enable', 'enable_schedule'))
            return out
        return []

    def help(self, app, zone):
        if zone == 'actions':
            if self.result_mode(app):
                return app.t('ui_help_dash_result')
            return app.t('ui_help_dash_actions_run' if app.run_active() else 'ui_help_dash_actions')
        if zone == 'groups':
            kind, gid, ident = self.selected_row(app)
            model = app.current_model()
            if kind == 'item' and model is not None:
                item = model.groups[gid].items[ident]
                lines = [item.name]
                if item.from_v or item.to_v:
                    lines.append('%s %s %s' % (item.from_v or '?', app.glyphs['arrow'], item.to_v or '?'))
                if item.result in ('needs_you', 'failed'):
                    why, todo = app.explain(gid, item)
                    lines += [why, app.t('ui_suggest', action=todo)]
                elif not item.result:
                    lines.append(app.t('ui_phase_' + item.phase))
                return '\n'.join(lines)
            return app.t('ui_group_' + gid) + ': ' + app.t('ui_group_desc_' + gid) + '\n\n' + app.t('ui_help_dash_groups')
        if zone == 'log':
            return app.t('ui_help_log')
        if zone == 'result':
            return app.t('ui_help_dash_result')
        if zone == 'status':
            return app.t('ui_help_status')
        return ''

    def action(self, app, zone, action):
        buttons = self.buttons(app)
        if zone == 'actions':
            self.button = min(self.button, max(0, len(buttons) - 1))
            if action == 'hmove':
                return True
            if action == 'left':
                self.button = max(0, self.button - 1)
            elif action == 'right':
                self.button = min(len(buttons) - 1, self.button + 1)
            elif action == 'down':
                app.focus_zone(self.zones(app)[1])
            elif action == 'up':
                app.focus_zone('tabs')
            elif action == 'press' and buttons:
                self.press(app, buttons[self.button][1])
            return True
        if zone == 'groups':
            return self.groups_action(app, action)
        if zone == 'status':
            if action in ('up', 'down'):
                self.status_scroll = max(0, self.status_scroll + (1 if action == 'down' else -1))
                return True
            if action == 'enable_schedule':
                app.open_schedule_setup()
                return True
            return action == 'vmove'
        if zone == 'result':
            if action in ('up', 'down'):
                self.result_sel = max(0, self.result_sel + (1 if action == 'down' else -1))
                return True
            if action in ('pgup', 'pgdn'):
                self.result_scroll = max(0, self.result_scroll + (10 if action == 'pgdn' else -10))
                return True
            if action == 'result_toggle' and app.last_model is not None:
                updated, current, needs = app.last_model.buckets()
                gids = [gid for gid in ts.GROUPS if any(g_ == gid for g_, _ in current)]
                if gids:
                    gid = gids[min(self.result_sel, len(gids) - 1)]
                    self.result_open.symmetric_difference_update({gid})
                return True
            return action in ('vmove', 'page')
        if zone in ('log', 'result'):
            step = {'up': 1, 'down': -1, 'pgup': 10, 'pgdn': -10, 'home': 10 ** 6, 'end': -10 ** 6}.get(action)
            if step is not None:
                if zone == 'log':
                    app.log_scroll = max(0, app.log_scroll + step)
                else:
                    self.result_scroll = max(0, self.result_scroll - step)
                return True
            if action == 'expand':
                app.log_expand_all = not app.log_expand_all
                return True
            return action in ('vmove', 'page', 'ends')
        return False

    def press(self, app, what):
        if what == 'update':
            app.start_run(dry_run=False)
        elif what == 'preview':
            app.start_run(dry_run=True)
        elif what == 'stop':
            app.ask_stop()
        elif what == 'log':
            app.toggle_full_log()
        elif what == 'answer':
            app.reopen_prompt()
        elif what == 'done':
            app.show_result = False
            self.button = 0
            app.focus_zone('actions')
        elif what == 'update_now':
            app.show_result = False
            app.start_run(dry_run=False)
        elif what == 'again':
            app.show_result = False
            app.start_run(dry_run=app.last_model.dry_run if app.last_model else False)

    def toggle_group(self, app, gid):
        """Tick or untick a group for this session only; the Settings file is never touched here."""
        app.toggle_session_group(gid)

    def click(self, app, payload, double=False):
        kind = payload[0]
        if kind == 'dash_button':
            app.focus_zone('actions')
            self.button = payload[1]
            buttons = self.buttons(app)
            if self.button < len(buttons):
                self.press(app, buttons[self.button][1])
            return True
        if kind == 'result_toggle':
            app.focus_zone('result')
            self.result_open.symmetric_difference_update({payload[1]})
            return True
        if kind == 'status_enable':
            app.open_schedule_setup()
            return True
        if kind == 'dash_check':
            app.focus_zone('groups')
            rows = self.list_rows(app)
            if ('group', payload[1], None) in rows:
                self.sel, self.follow = rows.index(('group', payload[1], None)), False
            if not app.run_active():
                self.toggle_group(app, payload[1])
            return True
        if kind == 'dash_row':
            app.focus_zone('groups')
            self.sel, self.follow = payload[1], False
            kind_, gid, _ = self.selected_row(app)
            model = app.current_model()
            has_items = bool(model and model.groups[gid].items)
            if kind_ == 'group' and has_items:
                self.toggle_expand(app, gid)
            return True
        return False

    def scroll(self, app, zone, delta):
        if zone == 'log':
            app.log_scroll = max(0, app.log_scroll - delta)
        elif zone == 'result':
            self.result_scroll = max(0, self.result_scroll + delta)
        else:
            rows = self.list_rows(app)
            self.follow = False
            self.sel = max(0, min(len(rows) - 1, self.sel + delta))
        return True

    # -- drawing ---------------------------------------------------------
    def render(self, app, c, main, side):
        if self.result_mode(app):
            area = main if side is None else Rect(main.y, main.x, main.h, side.x + side.w - main.x) \
                if side.y == main.y else Rect(main.y, main.x, side.y + side.h - main.y, main.w)
            self.render_result(app, c, area)
            return
        focused = self.pane_focus(app, 'actions', 'groups')
        model = app.current_model()
        right = (app.t('ui_preview_badge') if model and model.dry_run else '')
        c.box(main, app.t('ui_pane_groups'), focused, right=right)
        inner = main.inner()
        y = inner.y
        # Buttons
        x = inner.x
        for index, (label, what) in enumerate(self.buttons(app)):
            label = self.label_text(app, label)
            if x + text_width(label) + 4 > inner.x + inner.w:
                break
            x = c.button(y, x, label, focused=(app.zone == 'actions' and index == self.button and app.dialog is None),
                         primary=index == 0, action=('dash_button', index), disabled=self.button_disabled(app, what)) + 2
        tight = inner.h < 15
        y += 1 if tight else 2
        # Overall line (only while a run is active; idle shows the hint)
        if model and app.run_active():
            label = app.t('ui_overall')
            pct = int(round(model.overall() * 100))
            elapsed = duration((model.ended or time.monotonic()) - model.started)
            tail = ' %3d%%  %s' % (pct, elapsed)
            bar_w = max(6, inner.w - text_width(label) - text_width(tail) - 2)
            c.put(y, inner.x, label, 'strong')
            done = model.overall() >= 1
            c.bar(y, inner.x + text_width(label) + 1, bar_w, model.overall(), phase=None if done else bar_phase(app, y),
                  tone='ok' if done else 'run')
            c.put(y, inner.x + text_width(label) + 2 + bar_w, tail.strip(), 'base')
        elif not tight:
            for line in wrap(app.t('ui_idle_hint'), inner.w)[:2]:
                c.put(y, inner.x, line, 'muted')
                y += 1
            missing = app.missing_requirements()
            if missing:
                c.put(y, inner.x, clip(app.t('ui_req_missing_one' if len(missing) == 1 else 'ui_req_missing_n', count=len(missing)),
                                       inner.w, app.glyphs['ellipsis']), 'warn')
                y += 1
            y -= 1
        else:
            y -= 1
        y += 1 if tight else 2
        bottom = inner.y + inner.h
        self.tight = tight
        y = self.render_groups(app, c, Rect(y, inner.x, bottom - y, inner.w), model, main)
        if y + 2 <= bottom:
            for line in wrap_items(app.t('ui_legend_preview' if model is not None and model.dry_run else 'ui_legend'), inner.w)[:bottom - y - 1]:
                y += 1
                c.put(y, inner.x, line, 'muted')
        if model is None and app.last_run and y + 4 <= bottom:
            self.render_last_run(app, c, Rect(y + 2, inner.x, bottom - y - 2, inner.w))
        if side is not None:
            if app.run_active():
                self.render_log(app, c, side)
            else:
                self.render_status(app, c, side)

    # -- the scrollable group / item list -----------------------------------
    def sync_run(self, app):
        run = app.run
        if run is not getattr(self, '_seen_run', None):
            self._seen_run = run
            if run is not None:
                self.follow, self.sel, self.offset = True, 0, 0
                self.expanded, self.collapsed = set(), set()

    def is_expanded(self, app, gid, group):
        if group is None or not group.items:
            return False
        if gid in self.collapsed:
            return False
        if gid in self.expanded:
            return True
        return group.state == 'running' and app.run_active()

    def list_rows(self, app):
        self.sync_run(app)
        model = app.current_model()
        rows = []
        for gid in ts.GROUPS:
            group = model.groups[gid] if model else None
            rows.append(('group', gid, None))
            if self.is_expanded(app, gid, group):
                rows.extend(('item', gid, ident) for ident in group.order)
        return rows

    def selected_row(self, app):
        rows = self.list_rows(app)
        self.sel = max(0, min(self.sel, len(rows) - 1))
        return rows[self.sel]

    def follow_target(self, app, rows):
        model = app.run
        if model is None or model.active is None:
            return None
        active = model.active
        last = None
        for index, (kind, gid, ident) in enumerate(rows):
            if gid != active:
                continue
            if kind == 'group':
                last = index
            elif not model.groups[gid].items[ident].result:
                return index
            else:
                last = index
        return last

    def toggle_expand(self, app, gid):
        group = app.current_model().groups[gid] if app.current_model() else None
        if self.is_expanded(app, gid, group):
            self.expanded.discard(gid)
            self.collapsed.add(gid)
        else:
            self.collapsed.discard(gid)
            self.expanded.add(gid)

    def groups_action(self, app, action):
        rows = self.list_rows(app)
        step = {'up': -1, 'down': 1, 'pgup': -10, 'pgdn': 10}.get(action)
        if step is not None:
            if action == 'up' and self.sel == 0:
                app.focus_zone('actions')
                return True
            self.follow = False
            self.sel = max(0, min(len(rows) - 1, self.sel + step))
            return True
        if action in ('home', 'end'):
            self.sel = 0 if action == 'home' else len(rows) - 1
            self.follow = action == 'end' and app.run_active()
            return True
        kind, gid, ident = self.selected_row(app)
        model = app.current_model()
        group = model.groups[gid] if model else None
        if action == 'enter':
            if not app.run_active():
                self.toggle_group(app, gid)
            elif group is not None and group.items:
                self.toggle_expand(app, gid)
                if kind == 'item':
                    self.sel = rows.index(('group', gid, None))
            return True
        if action == 'all':
            if not app.run_active():
                app.toggle_all_session_groups()
            return True
        if action == 'space':
            if app.run_active():
                if group is not None and group.items:
                    self.toggle_expand(app, gid)
            else:
                self.toggle_group(app, gid)
            return True
        return action in ('vmove', 'page', 'ends')

    def group_info(self, app, group, state, result):
        """Text after the bar: real counts, n/total and %, or the state word."""
        g = app.glyphs
        if group is not None and state == 'running':
            total = group.known_total()
            if total is None:
                return app.t('ui_state_checking'), 'accent'
            finished = group.finished()
            pct = int(round(100.0 * finished / total)) if total else 100
            return '%d/%d  %d%%' % (finished, total, pct), 'base'
        if group is not None and state == 'done':
            counts = group.counts
            symbols = (('available', g['up']), ('updated', g['ok']), ('current', g['current']), ('needs_you', g['needs']),
                       ('failed', g['fail']), ('unchecked', g['off']))
            compact = ' '.join('%s%d' % (sym, counts[k]) for k, sym in symbols if counts.get(k))
            if compact:
                return compact, 'base'
        word = {'pending': 'pending', 'running': 'running', 'off': 'off', 'skipped': 'skipped'}.get(state) or \
            {'ok': 'done', 'warn': 'warn', 'failed': 'failed', 'off': 'off'}.get(result, 'done')
        glyph, style = status_glyph(app, state, result)
        return app.t('ui_state_' + word), (style if state != 'pending' else 'muted')

    def render_groups(self, app, c, rect, model, box):
        """Draw every group and the items of expanded groups, scrolled so the
        selection (or, while following, the running item) stays visible."""
        g = app.glyphs
        rows = self.list_rows(app)
        visible = max(1, rect.h)
        scrolling = len(rows) > visible
        width = rect.w - (2 if scrolling else 0)
        if self.follow and app.run_active():
            target = self.follow_target(app, rows)
            if target is not None:
                self.offset = max(0, min(target - visible * 2 // 3, len(rows) - visible))
                if app.zone != 'groups':
                    self.sel = target
        else:
            self.offset = scroll_window(self.sel, getattr(self, 'offset', 0), visible, len(rows))
        self.offset = max(0, min(self.offset, max(0, len(rows) - visible)))
        names = [app.t('ui_group_' + gid) for gid in ts.GROUPS]
        item_names = [model.groups[gid].items[ident].name for kind, gid, ident in rows if kind == 'item'] if model else []
        # Group names and app names share one column, so the bars of both start at the same x.
        # An app's emoji (config/app_glyphs.tsv; not in ASCII mode) takes 3 more cells in that column.
        item_widths = [text_width(n) + (3 if self.item_emoji(app, n) else 0) for n in item_names]
        name_w = min(max(max(text_width(n) for n in names), min(26, max(item_widths + [0]))),
                     max(8, width - 18))
        item_w = name_w
        for line, (kind, gid, ident) in enumerate(rows[self.offset:self.offset + visible]):
            index = self.offset + line
            y = rect.y + line
            selected = app.zone == 'groups' and index == self.sel and app.dialog is None
            c.region(y, rect.x, 1, width, ('dash_row', index))
            c.put(y, rect.x, (g['marker'] + ' ') if selected else '  ', 'focus_title')
            group = model.groups[gid] if model else None
            if kind == 'group':
                self.render_group_row(app, c, y, rect.x + 2, width - 2, gid, group, name_w, model)
            else:
                self.render_item_row(app, c, y, rect.x + 4, width - 4, group.items[ident], item_w, rect.x + 7 + name_w)
        if scrolling:
            self.render_scrollbar(c, rect.y, rect.x + rect.w - 1, visible, self.offset, len(rows))
            label = ' %s ' % app.t('ui_range', first=self.offset + 1, last=min(len(rows), self.offset + visible), total=len(rows))
            c.put(box.y + box.h - 1, box.x + box.w - 2 - text_width(label), label, 'muted')
        return rect.y + min(visible, len(rows) - self.offset)

    @staticmethod
    def render_scrollbar(c, y, x, height, offset, total):
        thumb = max(1, height * height // max(1, total))
        start = (height - thumb) * offset // max(1, total - height)
        for i in range(height):
            on = start <= i < start + thumb
            c.put(y + i, x, c.g['bar_full'] if on else c.g['v'], 'accent' if on else 'border')

    def render_group_row(self, app, c, y, x, width, gid, group, name_w, model):
        g = app.glyphs
        enabled = app.group_enabled(gid)
        idle = not app.run_active()
        state, result = (group.state, group.result) if group is not None else (('pending' if enabled else 'off'), None)
        if state == 'off' and model is not None and model.from_history and enabled:
            state = 'skipped'
        if idle and group is not None and enabled != group.enabled:
            # The ticks changed since the last run: show this run's plan, not the previous result.
            group, state, result = None, ('pending' if enabled else 'off'), None
        glyph, gstyle = status_glyph(app, state if state != 'skipped' else 'off', result, app.tick_count)
        has_items = group is not None and bool(group.items)
        marker = (g['expand'] if self.is_expanded(app, gid, group) else g['collapse']) if has_items else ' '
        c.put(y, x, marker, 'muted')
        if idle:
            # Before a run the first column is the checkbox; the previous result glyph moves behind it.
            box = g['check_on'] if enabled else g['check_off']
            end = c.put(y, x + 2, box, 'accent' if enabled else 'muted')
            c.region(y, x + 2, 1, end - x - 2, ('dash_check', gid))
            name_x, lead = end + 1, end + 1 - (x + 2)
        else:
            c.put(y, x + 2, glyph, gstyle)
            name_x, lead = x + 4, 2
        c.put(y, name_x, clip(app.t('ui_group_' + gid), name_w, g['ellipsis']), 'strong' if enabled else 'muted')
        x += 3 + lead + name_w
        remaining = width - 3 - lead - name_w
        info, info_style = self.group_info(app, group, state, result)
        shows_time = group is not None and group.started is not None and state not in ('off', 'skipped', 'pending')
        elapsed = duration(group.elapsed()) if shows_time else ''
        info_w = text_width(info)
        el_w = 6 if elapsed and remaining - info_w - 14 >= 6 else 0
        bar_w = max(6, min(20, remaining - info_w - el_w - 2))
        if bar_w + 1 + info_w > remaining:
            info = clip(info, max(0, remaining - bar_w - 1), g['ellipsis'])
        if state in ('off', 'skipped', 'pending'):
            c.bar(y, x, bar_w, 0.0)
        else:
            fraction = group.fraction() if group is not None else 0.0
            tone = {'warn': 'warn', 'failed': 'fail'}.get(result, 'ok') if state == 'done' else 'run'
            # Only a running group moves; finished, waiting and failed bars are still.
            c.bar(y, x, bar_w, fraction, phase=bar_phase(app, y) if state == 'running' else None, tone=tone)
        c.put(y, x + bar_w + 1, info, info_style, remaining - bar_w - 1)
        if el_w:
            c.put(y, x + remaining - 5, pad(elapsed, 5, 'right'), 'muted')

    @staticmethod
    def item_emoji(app, name):
        """The app's emoji as a separate display prefix; empty in ASCII mode (borders drawn with '+')."""
        return '' if app.glyphs['tl'] == '+' else glyph_for(name)

    def render_item_row(self, app, c, y, x, width, item, name_w, bar_x):
        """One app under a group. Its bar starts at the same column as the group bars (``bar_x``) and has a
        fixed width; the status word follows the bar and never sits on the track."""
        g = app.glyphs
        glyph, style = item_glyph(app, item.result)
        c.put(y, x, glyph, style)
        emoji = self.item_emoji(app, item.name)
        if emoji:
            c.put(y, x + 2, emoji, 'base')
        c.put(y, x + 2 + (3 if emoji else 0), clip(item.name, name_w - (3 if emoji else 0), g['ellipsis']),
              'base' if item.result else 'strong')
        cx = bar_x
        end = x + width
        if not item.result:
            phase = app.t('ui_phase_' + item.phase)
            if item.percent is not None:
                phase += ' %d%%' % int(item.percent)
            bw = ITEM_BAR_W if end - cx - text_width(phase) - 1 >= ITEM_BAR_W else 0
            if bw:
                # No percent yet while checking: nothing to measure, so the bar glides instead of filling.
                fraction = None if item.percent is None and item.phase == 'checking' else item_fraction(item)
                c.bar(y, cx, bw, fraction, phase=bar_phase(app, y))
                cx += bw + 1
            cx = c.put(y, cx, phase, 'accent', max(0, end - cx)) + 1
        versions = ''
        if item.to_v and item.from_v and item.to_v != item.from_v:
            versions = '%s %s %s' % (item.from_v, g['arrow'], item.to_v)
        elif item.from_v or item.to_v:
            versions = item.to_v or item.from_v
        if versions and text_width(versions) <= end - cx:
            c.put(y, cx, versions, 'muted')
        elif versions and item.result and cx < end - 4:
            c.put(y, cx, clip(versions, end - cx, g['ellipsis']), 'muted')

    def render_last_run(self, app, c, rect):
        from tui_screens import History
        row = app.last_run
        word, style, glyph = History.result_word(None, app, row)
        when = (row.get('timestamp') or '')[:16].replace('T', ' ')
        c.put(rect.y, rect.x, app.t('ui_last_run_title'), 'strong')
        c.put(rect.y + 1, rect.x, '%s %s' % (glyph, word), style)
        tail = '  %s  %s' % (when, duration(row.get('duration_seconds')))
        c.put(rect.y + 1, rect.x + text_width(glyph + ' ' + word), clip(tail, rect.w - text_width(word) - 2, app.glyphs['ellipsis']), 'muted')

    def render_log(self, app, c, rect):
        focused = self.pane_focus(app, 'log')
        lines = app.log_display_lines(rect.w - 4)
        right = ''
        model = app.current_model()
        if app.run_active() and model:
            right = duration(time.monotonic() - model.started)
        c.box(rect, app.t('ui_pane_log'), focused, right=right)
        inner = rect.inner()
        if not lines:
            draw_wrapped(c, inner, app.t('ui_log_empty'), 'muted')
            return
        app.log_scroll = min(app.log_scroll, max(0, len(lines) - inner.h))
        end = len(lines) - app.log_scroll
        start = max(0, end - inner.h)
        for i, (text, style) in enumerate(lines[start:end]):
            c.put(inner.y + i, inner.x, clip(text, inner.w, app.glyphs['ellipsis']), style)

    def status_lines(self, app, width):
        g = app.glyphs
        sep = ' %s ' % g['sep']
        out = []           # (text, style) or ('button', label, action)
        model = app.last_model
        out.append((app.t('ui_last_run_title'), 'accent'))
        if model is not None and (app.last_run or not model.from_history):
            glyph, style = status_glyph(app, 'done', {'ok': 'ok', 'warn': 'warn', 'failed': 'failed',
                                                      'stopped': 'warn'}.get(model.result, 'ok'))
            word = app.t({'ok': 'ui_res_completed', 'warn': 'ui_res_warn', 'failed': 'ui_res_failed',
                          'stopped': 'ui_res_interrupted'}.get(model.result, 'ui_res_unknown'))
            when = (app.last_run or {}).get('timestamp', '')[:16].replace('T', ' ') if model.from_history else ''
            took = duration(model.ended - model.started) if model.ended else ''
            parts = [glyph + ' ' + word] + [p for p in (app.relative(app.last_run_time), when, took) if p]
            for i, line in enumerate(wrap_items(sep.join(parts), width, sep)):
                out.append((line, style if i == 0 else 'muted'))
            totals = model.counts()
            counts = (' %s ' % g['sep']).join(text.split(' ', 1)[1] for text, _ in self.count_parts(app, model)) if model.dry_run else \
                '  '.join(text for text, _ in self.count_parts(app, model))
            out.extend((line, 'base') for line in wrap_items(counts, width))
            out.append(('', 'base'))
            out.append((app.t('ui_status_needs'), 'accent'))
            needs = model.buckets()[2]
            if not needs:
                out.append((g['ok'] + ' ' + app.t('ui_status_needs_none'), 'ok'))
            for gid, item in needs[:5]:
                failed = item.result == 'failed'
                out.append((clip('%s %s' % (g['fail'] if failed else g['needs'], item.name), width, g['ellipsis']),
                            'fail' if failed else 'warn'))
                out.extend(('  ' + line, 'muted') for line in wrap(g['arrow'] + ' ' + app.explain(gid, item)[1], width - 2)[:3])
            if len(needs) > 5:
                out.append((app.t('ui_more', count=len(needs) - 5), 'muted'))
        else:
            out.extend((line, 'muted') for line in wrap(app.t('ui_status_none'), width))
        out.append(('', 'base'))
        out.append((app.t('ui_sec_schedule'), 'accent'))
        state = app.schedule().get('state')
        if state == 'on':
            out.append((app.t('ui_status_next', when=app.next_run_text()), 'ok'))
        elif state == 'off':
            out.append(('button', app.t('ui_btn_enable'), ('status_enable',), app.t('ui_schedule_off')))
        else:
            out.append((app.t('ui_schedule_unknown'), 'muted'))
        out.append(('', 'base'))
        out.append((app.t('ui_status_mac'), 'accent'))
        report = app.toolkit_report or {}
        status = str(report.get('status', ''))
        if status in ('available', 'ready'):
            avail = app.t('ui_status_toolkit_available', version=plain(report.get('target_version') or '?')[:20])
        elif status == 'current':
            avail = app.t('ui_status_toolkit_current')
        else:
            avail = app.t('ui_status_toolkit_unknown')
        out.append((app.t('ui_status_toolkit', version=app.version), 'base'))
        out.extend(('  ' + line, 'muted') for line in wrap(avail, width - 2))
        facts = app.facts()
        if 'disk_free_gb' in facts:
            gb = facts['disk_free_gb']
            low = gb < app.settings.get('min_free_gb')
            out.extend((line, 'warn' if low else 'base') for line in wrap((g['needs'] + ' ' if low else '') + app.t('ui_status_disk', gb=gb), width))
        power = facts.get('power')
        if power:
            pct = power.get('percent')
            if power.get('source') == 'battery':
                low = pct is not None and pct < app.settings.get('min_battery')
                text, style = (g['needs'] + ' ' if low else '') + app.t('ui_status_power_batt', percent=pct if pct is not None else '?'), \
                    'warn' if low else 'base'
            elif pct is not None:
                text, style = app.t('ui_status_power_ac_batt', percent=pct), 'base'
            else:
                text, style = app.t('ui_status_power_ac'), 'base'
            out.extend((line, style) for line in wrap(text, width))
        return out

    def render_status(self, app, c, rect):
        focused = self.pane_focus(app, 'status')
        c.box(rect, app.t('ui_pane_status'), focused)
        inner = rect.inner()
        lines = self.status_lines(app, inner.w)
        self.status_scroll = min(self.status_scroll, max(0, len(lines) - inner.h))
        for i, line in enumerate(lines[self.status_scroll:self.status_scroll + inner.h]):
            y = inner.y + i
            if line[0] == 'button':
                x = inner.x
                if len(line) > 3:
                    x = c.put(y, x, line[3], 'warn') + 2
                c.button(y, x, line[1], focused=focused, primary=True, action=line[2])
            else:
                c.put(y, inner.x, line[0], line[1], inner.w)

    def group_summary(self, app, group, dry_run=False):
        """One sentence per group from group_end counts, so no group is invisible."""
        g = app.glyphs
        counts = group.counts
        checked = sum(counts.get(k, 0) for k in ('updated', 'current', 'needs_you', 'failed', 'skipped', 'available'))
        checked = max(checked, group.total or 0)
        if not checked:
            if dry_run and group.result == 'off' and not group.counts.get('unchecked'):
                return app.t('ui_group_preview_skipped')
            if group.state == 'done' and group.result == 'ok':
                # It ran and had nothing to report: that is fine, not "no data".
                return app.t('ui_group_no_updates' if group.id == 'system' else 'ui_group_ok_none')
            return app.t('ui_group_nothing')
        text = app.t('ui_group_checked', n=checked)
        if counts.get('current', 0) == checked:
            return text + ', ' + app.t('ui_group_all_current')
        parts = ['%s%d' % (sym, counts[k]) for k, sym in (('available', g['up']), ('updated', g['ok']), ('current', g['current']),
                                                         ('needs_you', g['needs']), ('failed', g['fail']),
                                                         ('unchecked', g['off'])) if counts.get(k)]
        return text + ' · ' + ' '.join(parts)

    def count_parts(self, app, model):
        """The result counters as (text, style): a preview counts what would update instead of what updated."""
        g = app.glyphs
        totals = model.counts()
        first = (g['up'] + ' ' + app.t('ui_res_available_n', count=totals['available']), 'accent') if model.dry_run else \
            (g['ok'] + ' ' + app.t('ui_res_updated_n', count=totals['updated']), 'ok')
        out = [first, (g['current'] + ' ' + app.t('ui_res_current_n', count=totals['current']), 'muted'),
               (g['needs'] + ' ' + app.t('ui_res_needs_n', count=totals['needs_you']), 'warn'),
               (g['fail'] + ' ' + app.t('ui_res_failed_n', count=totals['failed']), 'fail')]
        if model.dry_run and totals['unchecked']:
            out.append((g['off'] + ' ' + app.t('ui_res_unchecked_n', count=totals['unchecked']), 'muted'))
        return out

    def result_lines(self, app, model, width):
        """Rows: (text, style, toggle_gid_or_None). Needs you and Updated stay
        expanded; Up to date is grouped by update group and collapsible."""
        g = app.glyphs
        out = []
        updated, current, needs = model.buckets()
        out.append(('%s %s (%d)' % (g['needs'], app.t('ui_bucket_needs'), len(needs)), 'warn', None))
        if not needs:
            out.append(('  ' + app.t('ui_bucket_empty'), 'muted', None))
        out.extend(line + (None,) for line in self.bucket_lines(app, needs, width, 'warn', g['needs']))
        out.append(('', 'base', None))
        if model.dry_run:
            available = model.available_items()
            out.append(('%s %s (%d)' % (g['up'], app.t('ui_bucket_available'), len(available)), 'accent', None))
            if not available:
                out.append(('  ' + app.t('ui_bucket_empty'), 'muted', None))
            out.extend(line + (None,) for line in self.bucket_lines(app, available, width, 'accent', g['up']))
            out.append(('', 'base', None))
        if updated or not model.dry_run:
            out.append(('%s %s (%d)' % (g['ok'], app.t('ui_bucket_updated'), len(updated)), 'ok', None))
            if not updated:
                out.append(('  ' + app.t('ui_bucket_empty'), 'muted', None))
            out.extend(line + (None,) for line in self.bucket_lines(app, updated, width, 'ok', g['ok']))
            out.append(('', 'base', None))
        by_group = {}
        for gid, item in current:
            by_group.setdefault(gid, []).append(item)
        out.append(('%s %s (%d)' % (g['current'], app.t('ui_bucket_current'), max(len(current), model.counts()['current'])),
                    'strong', None))
        for gid in ts.GROUPS:
            items = by_group.get(gid)
            counted = model.groups[gid].counts.get('current', 0)
            if not items and counted:
                # The engine reported a count but no item names: still show the group.
                out.append(('    %s (%d)' % (app.t('ui_group_' + gid), counted), 'base', None))
                continue
            if not items:
                continue
            opened = gid in self.result_open
            out.append(('  %s %s (%d)' % (g['expand'] if opened else g['collapse'], app.t('ui_group_' + gid), len(items)),
                        'base', gid))
            if opened:
                names = ', '.join(i.name for i in items)
                out.extend(('      ' + line, 'muted', None) for line in wrap(names, max(10, width - 6)))
        if not current:
            out.append(('  ' + app.t('ui_bucket_empty'), 'muted', None))
        out.append(('', 'base', None))
        unchecked = model.unchecked_items() if model.dry_run else []
        if unchecked:
            out.append(('%s %s (%d)' % (g['off'], app.t('ui_bucket_unchecked'), len(unchecked)), 'strong', None))
            out.extend(('  ' + line, 'muted', None) for line in wrap(app.t('ui_unchecked_note'), max(10, width - 2)))
            names = ', '.join(i.name for _, i in unchecked)
            out.extend(('  ' + line, 'base', None) for line in wrap(names, max(10, width - 2)))
            out.append(('', 'base', None))
        out.append((app.t('ui_bucket_groups'), 'strong', None))
        self.result_bars = {}      # line index -> (column, fraction, tone) of a duration bar in that line
        groups = [gr for gr in model.groups.values() if gr.enabled and (gr.started is not None or gr.state == 'done')]
        longest = max([(gr.elapsed() or 0) for gr in groups] + [1])
        name_w = max([text_width(app.t('ui_group_' + gr.id)) for gr in groups] + [8])
        for gr in groups:
            glyph, style = status_glyph(app, gr.state, gr.result)
            took = duration(gr.elapsed()) if gr.started is not None else ''
            bar = ''
            if took and width >= name_w + 60:
                bar = ' ' + ' ' * RESULT_BAR_W      # drawn over the blanks by the screen, in the slim bar family
            start = len('  %s %s  %s' % (glyph, pad(app.t('ui_group_' + gr.id), name_w), took and pad(took, 6, 'right'))) + 1
            if bar:
                self.result_bars[len(out)] = (start, (gr.elapsed() or 0) / float(longest),
                                              {'warn': 'warn', 'failed': 'fail'}.get(gr.result, 'ok'))
            line = '  %s %s  %s%s  %s' % (glyph, pad(app.t('ui_group_' + gr.id), name_w), took and pad(took, 6, 'right'), bar,
                                          self.group_summary(app, gr, model.dry_run))
            out.append((line, style if gr.result in ('warn', 'failed') else 'base', None))
        return out

    def render_result(self, app, c, rect):
        g = app.glyphs
        model = app.last_model
        focused = self.pane_focus(app, 'actions', 'result')
        title = {'ok': 'ui_result_title', 'warn': 'ui_result_title', 'failed': 'ui_result_title_failed',
                 'stopped': 'ui_result_title_stopped'}.get(model.result, 'ui_result_title')
        if model.dry_run and model.result != 'failed':
            title = 'ui_result_title_preview'
        c.box(rect, app.t('ui_pane_result'), focused)
        inner = rect.inner()
        y = inner.y
        glyph, style = status_glyph(app, 'done', {'ok': 'ok', 'warn': 'warn', 'failed': 'failed', 'stopped': 'warn'}.get(model.result, 'ok'))
        c.put(y, inner.x, glyph + ' ' + app.t(title), style)
        took = app.t('ui_result_time', time=duration((model.ended or time.monotonic()) - model.started))
        c.put(y, inner.x + inner.w - text_width(took), took, 'muted')
        y += 1
        x = inner.x
        for number, (text, st) in enumerate(self.count_parts(app, model)):
            if model.dry_run:
                # "N would update · M up to date · K need you · F failed"
                text = text.split(' ', 1)[1]
                if number:
                    x = c.put(y, x, ' %s ' % g['sep'], 'muted')
            if x + text_width(text) > inner.x + inner.w:
                break
            x = c.put(y, x, text, st) + (0 if model.dry_run else 3)
        y += 2
        x = inner.x
        for index, (label, _) in enumerate(self.buttons(app)):
            x = c.button(y, x, self.label_text(app, label), focused=app.zone == 'actions' and index == self.button and app.dialog is None,
                         primary=index == 0, action=('dash_button', index)) + 2
        y += 2
        area = Rect(y, inner.x, inner.y + inner.h - y, inner.w)
        lines = self.result_lines(app, model, area.w - 2)
        toggles = [i for i, line in enumerate(lines) if line[2]]
        if toggles:
            self.result_sel = max(0, min(self.result_sel, len(toggles) - 1))
        selected_line = toggles[self.result_sel] if toggles and app.zone == 'result' else None
        if selected_line is not None:
            self.result_scroll = scroll_window(selected_line, self.result_scroll, area.h, len(lines))
        self.result_scroll = max(0, min(self.result_scroll, max(0, len(lines) - area.h)))
        for i, (text, st, gid) in enumerate(lines[self.result_scroll:self.result_scroll + area.h]):
            index = self.result_scroll + i
            row_style = ('sel_focus' if app.dialog is None else 'sel') if index == selected_line else st
            if index == selected_line:
                c.fill(area.y + i, area.x, 1, area.w - 2, row_style)
            c.put(area.y + i, area.x, clip(text, area.w - 2, g['ellipsis']), row_style)
            span = getattr(self, 'result_bars', {}).get(index)
            if span and index != selected_line and span[0] + RESULT_BAR_W <= area.w - 2:
                col, fraction, tone = span
                c.bar(area.y + i, area.x + col, RESULT_BAR_W, fraction, tone=tone)
            if gid:
                c.region(area.y + i, area.x, 1, area.w - 2, ('result_toggle', gid))
        if len(lines) > area.h:
            self.render_scrollbar(c, area.y, area.x + area.w - 1, area.h, self.result_scroll, len(lines))
            label = ' %s ' % app.t('ui_range', first=self.result_scroll + 1, last=min(len(lines), self.result_scroll + area.h),
                                   total=len(lines))
            c.put(rect.y + rect.h - 1, rect.x + rect.w - 2 - text_width(label), label, 'muted')

    def bucket_lines(self, app, items, width, style, glyph):
        out = []
        for gid, item in items:
            version = ''
            if item.to_v and item.from_v and item.to_v != item.from_v:
                version = '  %s %s %s' % (item.from_v, app.glyphs['arrow'], item.to_v)
            elif item.from_v or item.to_v:
                version = '  ' + (item.to_v or item.from_v)
            emoji = Dashboard.item_emoji(app, item.name)
            out.append(('  %s %s%s%s' % (glyph if item.result != 'failed' else app.glyphs['fail'], emoji + ' ' if emoji else '', item.name, version),
                        style if item.result != 'failed' else 'fail'))
            if not version and item.detail and item.result not in ('needs_you', 'failed'):
                # No versions to show: the detail says what happened, quietly under the name.
                out.extend(('    ' + line, 'muted') for line in wrap(item.detail, max(10, width - 4)))
            if item.result in ('needs_you', 'failed'):
                why, todo = app.explain(gid, item)
                for line in wrap(why, max(10, width - 4)):
                    out.append(('    ' + line, 'base'))
                for line in wrap(app.t('ui_suggest', action=todo), max(10, width - 4)):
                    out.append(('    ' + line, 'accent'))
        return out


# ---------------------------------------------------------------------------
class Apps(Screen):
    id, tab = 'apps', 'ui_tab_apps'

    def __init__(self):
        self.list = ListState()
        self.query = ''
        self.marked = set()
        self.model = None

    def on_enter(self, app):
        if self.model is None:
            self.reload(app)

    def reload(self, app):
        from tui_inventory import load_apps
        try:
            self.model = load_apps(app.repo, app.state_dir)
        except Exception as exc:  # never break the screen
            self.model = dict(rows=[], source=None, error=str(exc))

    def rows(self, app):
        rows = (self.model or {}).get('rows', [])
        q = self.query.casefold().strip()
        if not q:
            return rows
        return [r for r in rows if q in r['name'].casefold() or q in app.t('ui_kind_' + r['group']).casefold()
                or q in r['id'].casefold()]

    def zones(self, app):
        return ['list', 'search']

    def bindings(self, app, zone):
        if zone == 'search':
            return [Binding((), 'ui_key_type', 'type', display='abc'), Binding(('down', 'enter'), 'ui_key_back', 'to_list'),
                    Binding(('backspace',), 'ui_key_clear', 'backspace')]
        if not (self.model or {}).get('rows'):
            return [Binding(('enter',), 'ui_btn_scan', 'scan')]
        return [Binding(('up', 'down'), 'ui_key_move', 'vmove'), Binding(('enter',), 'ui_key_change', 'popup'),
                Binding(('space',), 'ui_key_mark', 'mark'), Binding(('/',), 'ui_key_search', 'to_search'),
                Binding(('pgup', 'pgdn'), 'ui_key_scroll', 'page', show=False), Binding(('r',), 'ui_btn_scan', 'scan', show=False)]

    def help(self, app, zone):
        if zone == 'search':
            return app.t('ui_help_apps_search')
        rows = self.rows(app)
        if not rows:
            return app.t('ui_help_apps_list')
        row = rows[min(self.list.index, len(rows) - 1)]
        mode, source = app.overrides.get(app.override_group(row), row['id'], row.get('default_mode', 'auto'))
        method = (app.t('ui_method_' + row['method_origin']) if row['method_origin'] else '—') + \
            (' (%s)' % row['method'] if row['method'] else '')
        lines = [row['name'],
                 '%s: %s' % (app.t('ui_col_source'), app.t('ui_kind_' + row['group'])),
                 '%s: %s' % (app.t('ui_col_version'), row['version'] or '—'),
                 '%s: %s' % (app.t('ui_col_mode'), app.t('ui_mode_' + mode)),
                 '%s: %s' % (app.t('ui_popup_section_source'), app.t('ui_src_' + (source or 'default'))),
                 '%s: %s' % (app.t('ui_col_method'), method), '',
                 app.t('ui_mode_%s_help' % mode), '', app.t('ui_help_apps_list'), '', app.t('ui_method_help')]
        return '\n'.join(lines)

    def action(self, app, zone, action):
        rows = self.rows(app)
        if action == 'scan':
            app.start_task('inventory', label='ui_diag_inventory')
            return True
        if zone == 'search':
            if action in ('down', 'enter', 'to_list'):
                app.focus_zone('list')
            elif action == 'backspace':
                self.query = self.query[:-1]
                self.list.index = 0
            elif action == 'up':
                app.focus_zone('tabs')
            else:
                return False
            return True
        if action == 'to_search':
            app.focus_zone('search')
        elif action == 'up':
            if self.list.index == 0:
                app.focus_zone('search')
            self.list.move(-1, len(rows))
        elif action == 'down':
            self.list.move(1, len(rows))
        elif action == 'pgup':
            self.list.move(-10, len(rows))
        elif action == 'pgdn':
            self.list.move(10, len(rows))
        elif action == 'mark' and rows:
            key = (rows[self.list.index]['group'], rows[self.list.index]['id'])
            self.marked.symmetric_difference_update({key})
            self.list.move(1, len(rows))
        elif action == 'popup' and rows:
            self.popup(app, rows)
        else:
            return action in ('vmove', 'page')
        return True

    def text(self, app, zone, text):
        if zone == 'search':
            self.query = (self.query + text)[:60]
            self.list.index = 0
            return True
        return False

    def popup(self, app, rows):
        targets = [r for r in rows if (r['group'], r['id']) in self.marked] or [rows[self.list.index]]
        keys = [(app.override_group(r), r['id']) for r in targets]
        defaults = {(app.override_group(r), r['id']): r.get('default_mode', 'auto') for r in targets}
        mode, source = app.overrides.get(*keys[0], default=defaults[keys[0]])
        title = app.t('ui_popup_mode', name=targets[0]['name']) if len(targets) == 1 else app.t('ui_popup_mode_many', count=len(targets))
        entries = [(app.t('ui_popup_section_mode'), None)]
        entries += [('%s — %s' % (app.t('ui_mode_' + m), app.t('ui_mode_%s_help' % m)), ('mode', m)) for m in ('auto', 'manual', 'skip')]
        entries += [('', None), (app.t('ui_popup_section_source'), None)]
        entries += [(app.t('ui_src_' + (s or 'default')), ('source', s)) for s in ('', 'brew', 'appstore', 'vendor', 'native')]

        def done(a, value):
            if not value:
                return
            try:
                if value[0] == 'mode':
                    a.overrides.set_many(keys, mode=value[1], defaults=defaults)
                else:
                    a.overrides.set_many(keys, source=value[1], defaults=defaults)
                a.notify(a.t('ui_override_saved', count=len(keys)), 'status_ok')
                self.marked.clear()
            except (OSError, ValueError) as exc:
                a.notify(a.t('ui_error', message=plain(exc)), 'status_warn')
        app.open_dialog(ChoiceDialog(title, entries, done, current=frozenset({('mode', mode), ('source', source)})))

    def click(self, app, payload, double=False):
        if payload[0] == 'app_row':
            app.focus_zone('list')
            self.list.index = payload[1]
            if double:
                self.popup(app, self.rows(app))
            return True
        if payload[0] == 'apps_search':
            app.focus_zone('search')
            return True
        if payload[0] == 'apps_scan':
            app.start_task('inventory', label='ui_diag_inventory')
            return True
        return False

    def scroll(self, app, zone, delta):
        self.list.move(delta, len(self.rows(app)))
        return True

    def columns(self, app, width, rows):
        def widest(values, label, cap):
            return min(cap, max([text_width(label)] + [text_width(v) for v in values]))
        sample = rows[:400]
        cols = [('name', app.t('ui_col_name'), 0),
                ('group', app.t('ui_col_source'), widest([app.t('ui_kind_' + r['group']) for r in sample], app.t('ui_col_source'), 18)),
                ('version', app.t('ui_col_version'), widest([r['version'] or '—' for r in sample], app.t('ui_col_version'), 12)),
                ('mode', app.t('ui_col_mode'), widest([app.t('ui_mode_' + m) + '*' for m in ('auto', 'manual', 'skip')], app.t('ui_col_mode'), 16)),
                ('method', app.t('ui_col_method'), widest([method_label(app, r) for r in sample] or ['—'], app.t('ui_col_method'), 18))]
        for key in ('method', 'version', 'group'):
            fixed = sum(w + 1 for k, _, w in cols if k != 'name')
            if width - fixed >= 18:
                break
            cols = [col for col in cols if col[0] != key]
        return cols

    def render(self, app, c, main, side):
        g = app.glyphs
        self.on_enter(app)
        rows = self.rows(app)
        total = len((self.model or {}).get('rows', []))
        focused = self.pane_focus(app, 'list', 'search')
        c.box(main, app.t('ui_pane_apps'), focused, right=app.t('ui_apps_count', shown=len(rows), total=total) if total else '')
        inner = main.inner()
        y = inner.y
        label = app.t('ui_search_label')
        searching = app.zone == 'search' and app.dialog is None
        field = self.query + ('▏' if searching and g['tl'] != '+' else ('_' if searching else ''))
        c.put(y, inner.x, label, 'focus_title' if searching else 'muted')
        c.put(y, inner.x + text_width(label), clip(field or app.t('ui_search_hint'), inner.w - text_width(label), g['ellipsis']),
              'input' if searching else ('base' if field else 'muted'))
        c.region(y, inner.x, 1, inner.w, ('apps_search',))
        if self.marked:
            note = app.t('ui_selected_count', count=len(self.marked))
            c.put(y, inner.x + inner.w - text_width(note), note, 'accent')
        y += 2
        if not total:
            lines = wrap(app.t('ui_apps_empty'), inner.w)
            for line in lines:
                c.put(y, inner.x, line, 'base')
                y += 1
            c.button(y + 1, inner.x, app.t('ui_btn_scan'), focused=app.zone == 'list' and app.dialog is None, primary=True,
                     action=('apps_scan',))
            if side is not None:
                c.box(side, app.t('ui_pane_details'))
            return
        cols = self.columns(app, inner.w - 6, rows)
        fixed = sum(w + 1 for k, _, w in cols if k != 'name')
        name_w = max(8, inner.w - 6 - fixed)
        x = inner.x + 6
        for key, lbl, w in cols:
            width = name_w if key == 'name' else w
            c.put(y, x, lbl, 'muted')
            x += width + 1
        y += 1
        visible = inner.y + inner.h - y
        self.list.clamp(len(rows))
        self.list.offset = scroll_window(self.list.index, self.list.offset, visible, len(rows))
        if not rows:
            c.put(y, inner.x, app.t('ui_apps_nomatch'), 'muted')
        for i, row in enumerate(rows[self.list.offset:self.list.offset + visible], self.list.offset):
            selected = i == self.list.index
            mark = g['check_on'] if (row['group'], row['id']) in self.marked else g['check_off']
            mode, source = app.overrides.get(app.override_group(row), row['id'], row.get('default_mode', 'auto'))
            values = dict(name=row['name'], group=app.t('ui_kind_' + row['group']), version=row['version'] or '—',
                          mode=app.t('ui_mode_' + mode) + ('*' if source else ''),
                          method=method_label(app, row))
            style = ('sel_focus' if app.zone == 'list' else 'sel') if selected else 'base'
            if selected:
                c.fill(y, inner.x, 1, inner.w, style)
                c.put(y, inner.x, g['marker'], style)
            c.put(y, inner.x + 2, mark, style)
            x = inner.x + 6
            for key, lbl, w in cols:
                width = name_w if key == 'name' else w
                st = style
                if key == 'mode' and not selected:
                    st = {'auto': 'ok', 'manual': 'warn', 'skip': 'muted'}[mode]
                c.put(y, x, clip(values[key], width, g['ellipsis']), st)
                x += width + 1
            c.region(y, inner.x, 1, inner.w, ('app_row', i))
            y += 1
        if side is not None:
            self.render_details(app, c, side, rows)

    def render_details(self, app, c, rect, rows):
        c.box(rect, app.t('ui_pane_details'))
        inner = rect.inner()
        if not rows:
            return
        row = rows[min(self.list.index, len(rows) - 1)]
        mode, source = app.overrides.get(app.override_group(row), row['id'], row.get('default_mode', 'auto'))
        y = inner.y
        c.put(y, inner.x, clip(row['name'], inner.w, app.glyphs['ellipsis']), 'strong')
        y += 2
        pairs = [(app.t('ui_col_source'), app.t('ui_kind_' + row['group'])),
                 (app.t('ui_col_version'), row['version'] or '—'),
                 (app.t('ui_col_mode'), app.t('ui_mode_' + mode)),
                 (app.t('ui_popup_section_source'), app.t('ui_src_' + (source or 'default'))),
                 (app.t('ui_col_method'), (app.t('ui_method_' + row['method_origin']) if row['method_origin'] else '—')
                  + (' (%s)' % row['method'] if row['method'] else '')),
                 ('ID', row['id'])]
        label_w = max(text_width(k) for k, _ in pairs) + 1
        for key, value in pairs:
            if y >= inner.y + inner.h:
                break
            if label_w + 8 > inner.w:
                c.put(y, inner.x, key, 'muted')
                y += 1
                c.put(y, inner.x + 2, clip(value, inner.w - 2, app.glyphs['ellipsis']), 'base')
            else:
                c.put(y, inner.x, key, 'muted')
                c.put(y, inner.x + label_w, clip(value, inner.w - label_w, app.glyphs['ellipsis']), 'base')
            y += 1
        y += 1
        for line in wrap(app.t('ui_mode_%s_help' % mode), inner.w):
            if y >= inner.y + inner.h:
                break
            c.put(y, inner.x, line, 'muted')
            y += 1
        if row['path'] and y + 1 < inner.y + inner.h:
            y += 1
            for line in wrap(row['path'], inner.w)[:inner.y + inner.h - y]:
                c.put(y, inner.x, line, 'muted')
                y += 1


# ---------------------------------------------------------------------------
class Catalog(Screen):
    """The whole tested catalog: apps that can be added first, installed ones after."""
    id, tab = 'catalog', 'ui_tab_catalog'

    def __init__(self):
        self.list = ListState()
        self.rows_cache = None
        self.model = None
        self.error = False
        self.selected = set()
        self.sources = {}
        self.button_focus = False

    def on_enter(self, app):
        if self.rows_cache is None:
            self.reload(app)

    def reload(self, app):
        from tui_inventory import catalog_rows, load_catalog
        try:
            self.model = load_catalog(app.repo, app.state_dir)
            self.rows_cache = catalog_rows(self.model)
            self.error = False
        except Exception:  # catalog problems stay inside this screen
            self.model, self.rows_cache, self.error = None, [], True
        self.list.index = 0                         # first row is the first installable one
        self.selected &= {r['product_id'] for r in self.rows_cache if not r['installed']}
        for row in self.rows_cache:
            if row['recommended'] and not row['installed']:
                self.sources.setdefault(row['product_id'], row['recommended'])

    def current(self):
        rows = self.rows_cache or []
        return rows[min(self.list.index, len(rows) - 1)] if rows else None

    def addable(self):
        return [r for r in self.rows_cache or [] if not r['installed']]

    def zones(self, app):
        return ['list', 'actions']

    def bindings(self, app, zone):
        if zone == 'actions':
            return [Binding(('enter',), 'ui_btn_install', 'install'), Binding(('down',), 'ui_key_move', 'to_list', show=False)]
        row = self.current()
        move = Binding(('up', 'down'), 'ui_key_move', 'vmove')
        if row is not None and row['installed']:
            return [move, Binding(('i',), 'ui_btn_install', 'install')]
        return [move, Binding(('space',), 'ui_key_mark', 'mark'),
                Binding(('enter',), 'ui_key_choose_source', 'source'), Binding(('i',), 'ui_btn_install', 'install')]

    def help(self, app, zone):
        row = self.current()
        text = app.t('ui_help_catalog')
        if zone == 'list' and row:
            if row['installed']:
                return '%s\n%s: %s\n%s: %s\n\n%s' % (row['name'], app.t('ui_col_version'), row['version'] or '—',
                                                      app.t('ui_col_source'), self.installed_source(app, row),
                                                      app.t('ui_catalog_installed_help'))
            srcs = ', '.join(self.source_label(app, s) for s in row['sources']) or '—'
            text = '%s\n%s: %s\n\n%s' % (row['name'], app.t('ui_col_source'), srcs, text)
        return text

    @staticmethod
    def source_label(app, source):
        if source == 'homebrew':
            return app.t('ui_src_brew')
        return app.t('ui_src_' + source) if source in ('vendor', 'appstore', 'native') else source

    @staticmethod
    def installed_source(app, row):
        return METHOD_LABELS.get(row['method']) or row['method'] or '—'

    def action(self, app, zone, action):
        rows = self.rows_cache or []
        row = self.current()
        if action == 'install':
            self.install(app)
        elif zone == 'actions' and action in ('down', 'to_list'):
            app.focus_zone('list')
        elif zone == 'actions' and action == 'up':
            app.focus_zone('tabs')
        elif action == 'up':
            if self.list.index == 0:
                app.focus_zone('actions')
            self.list.move(-1, len(rows))
        elif action == 'down':
            self.list.move(1, len(rows))
        elif action == 'mark' and row and not row['installed']:
            self.selected.symmetric_difference_update({row['product_id']})
        elif action == 'source' and row and not row['installed']:
            self.choose_source(app, row)
        else:
            return action in ('vmove',)
        return True

    def choose_source(self, app, row):
        if len(row['sources']) <= 1:
            self.selected.symmetric_difference_update({row['product_id']})
            return
        entries = [(app.t('ui_src_' + ('brew' if s == 'homebrew' else s)) if s in ('homebrew', 'vendor', 'appstore', 'native') else s, s)
                   for s in row['sources']]

        def done(a, value):
            if value:
                self.sources[row['product_id']] = value
                self.selected.add(row['product_id'])
        app.open_dialog(ChoiceDialog(app.t('ui_catalog_source_popup', name=row['name']), entries, done,
                                     current=self.sources.get(row['product_id'])))

    def install(self, app):
        if not self.addable():
            app.notify(app.t('ui_catalog_all_done'), 'status_warn')
            return
        if not self.selected:
            app.notify(app.t('ui_catalog_nothing'), 'status_warn')
            return
        names = [r['name'] for r in self.addable() if r['product_id'] in self.selected]

        def go(a, value):
            if value != 'yes':
                return
            from tui_inventory import prepare_catalog_selection
            try:
                plan = prepare_catalog_selection(self.model or {}, set(self.selected), dict(self.sources))
            except (ValueError, KeyError) as exc:
                key = 'ui_catalog_need_inventory' if str(exc).strip("'") == 'inventory_missing' else 'ui_catalog_unavailable'
                a.open_dialog(Dialog(a.t('ui_dlg_confirm'), a.t(key), [(a.t('ui_btn_ok'), None)], None))
                return
            except Exception as exc:
                a.notify(a.t('ui_error', message=plain(exc)), 'status_warn')
                return
            a.start_task('catalog', label='ui_btn_install', install_plan=plan)
            self.selected.clear()
        app.open_dialog(Dialog(app.t('ui_dlg_confirm'), app.t('ui_catalog_confirm', count=len(names), names=', '.join(names)),
                               [(app.t('ui_btn_install'), 'yes'), (app.t('ui_btn_cancel'), None)], go, default=1))

    def click(self, app, payload, double=False):
        if payload[0] == 'cat_row':
            app.focus_zone('list')
            self.list.index = payload[1]
            row = self.current()
            if row and not row['installed'] and (payload[2] == 'check' or double):
                self.selected.symmetric_difference_update({row['product_id']})
            return True
        if payload[0] == 'cat_install':
            app.focus_zone('actions')
            self.install(app)
            return True
        return False

    def scroll(self, app, zone, delta):
        self.list.move(delta, len(self.rows_cache or []))
        return True

    def summary(self, app):
        rows = self.rows_cache or []
        if not (self.model or {}).get('snapshot'):
            return app.t('ui_catalog_summary_unknown', total=len(rows))
        return app.t('ui_catalog_summary', installed=len(rows) - len(self.addable()), total=len(rows), addable=len(self.addable()))

    def status_text(self, app, row):
        if not row['installed']:
            return app.t('ui_catalog_st_missing')
        return app.t('ui_catalog_st_installed_v', version=row['version']) if row['version'] else app.t('ui_catalog_st_installed')

    def render(self, app, c, main, side):
        g = app.glyphs
        self.on_enter(app)
        rows = self.rows_cache or []
        addable = self.addable()
        focused = self.pane_focus(app, 'list', 'actions')
        right = app.t('ui_selected_count', count=len(self.selected)) if self.selected else ''
        c.box(main, app.t('ui_pane_catalog'), focused, right=right)
        inner = main.inner()
        y = inner.y
        if rows and not self.error:
            for line in wrap(self.summary(app), inner.w)[:2]:
                c.put(y, inner.x, line, 'muted')
                y += 1
            y += 1
        c.button(y, inner.x, app.t('ui_btn_install'), focused=app.zone == 'actions' and app.dialog is None,
                 primary=bool(self.selected), action=('cat_install',), disabled=bool(rows) and not addable)
        y += 2
        if self.error or not rows:
            c.put(y, inner.x, app.t('ui_catalog_unavailable' if self.error else 'ui_catalog_empty'), 'muted')
        else:
            if not addable:
                c.put(y, inner.x, clip(app.t('ui_catalog_all_done'), inner.w, g['ellipsis']), 'ok')
                y += 2
            labels = [app.t('ui_src_brew'), app.t('ui_src_vendor'), app.t('ui_src_appstore'), app.t('ui_src_native')]
            labels += [self.installed_source(app, r) for r in rows if r['installed']]
            src_w = min(22, max([text_width(app.t('ui_col_source'))] + [text_width(l) for l in labels]))
            st_w = min(24, max([text_width(app.t('ui_col_status'))] + [text_width(self.status_text(app, r)) for r in rows]))
            name_w = max(10, inner.w - 6 - st_w - src_w - 3)
            st_x = inner.x + 6 + name_w + 1
            src_x = st_x + st_w + 2
            c.put(y, inner.x + 6, app.t('ui_col_name'), 'muted')
            c.put(y, st_x, app.t('ui_col_status'), 'muted')
            c.put(y, src_x, app.t('ui_col_source'), 'muted')
            y += 1
            # Display lines: a heading before each non-empty section, then its rows.
            lines, line_of = [], {}
            for i, row in enumerate(rows):
                if i == 0 or row['installed'] != rows[i - 1]['installed']:
                    count = len(rows) - len(addable) if row['installed'] else len(addable)
                    lines.append(('head', app.t('ui_catalog_head_have' if row['installed'] else 'ui_catalog_head_add', count=count)))
                line_of[i] = len(lines)
                lines.append(('row', i))
            visible = inner.y + inner.h - y
            self.list.clamp(len(rows))
            target = line_of[self.list.index]
            offset = scroll_window(target, self.list.offset, visible, len(lines))
            if target > 0 and lines[target - 1][0] == 'head' and offset > target - 1 and visible > 1:
                offset = target - 1                 # keep the section heading above its first row
            self.list.offset = offset
            for kind, value in lines[offset:offset + max(0, visible)]:
                if kind == 'head':
                    c.put(y, inner.x + 2, clip(value, inner.w - 2, g['ellipsis']), 'strong')
                    y += 1
                    continue
                i, row = value, rows[value]
                selected = i == self.list.index
                style = ('sel_focus' if app.zone == 'list' and app.dialog is None else 'sel') if selected else 'base'
                if selected:
                    c.fill(y, inner.x, 1, inner.w, style)
                    c.put(y, inner.x, g['marker'], style)
                if row['installed']:
                    c.put(y, inner.x + 3, g['ok'], style if selected else 'ok')
                    src = self.installed_source(app, row)
                else:
                    c.put(y, inner.x + 2, g['check_on'] if row['product_id'] in self.selected else g['check_off'], style)
                    src = self.sources.get(row['product_id']) or (row['sources'][0] if row['sources'] else '—')
                    src = self.source_label(app, src)
                c.put(y, inner.x + 6, clip(row['name'], name_w, g['ellipsis']), style)
                c.put(y, st_x, clip(self.status_text(app, row), st_w, g['ellipsis']),
                      style if selected else ('ok' if row['installed'] else 'muted'))
                c.put(y, src_x, clip(src, src_w, g['ellipsis']), style if selected else 'muted')
                if not row['installed']:
                    c.region(y, inner.x, 1, 6, ('cat_row', i, 'check'))
                c.region(y, inner.x + 6, 1, inner.w - 6, ('cat_row', i, 'row'))
                y += 1
        if side is not None:
            c.box(side, app.t('ui_pane_details'))
            row = self.current()
            if row:
                si = side.inner()
                c.put(si.y, si.x, clip(row['name'], si.w, g['ellipsis']), 'strong')
                if row['installed']:
                    text = '%s: %s\n%s: %s\n%s: %s\n\n%s' % (
                        app.t('ui_col_status'), app.t('ui_catalog_st_installed'), app.t('ui_col_version'), row['version'] or '—',
                        app.t('ui_col_source'), self.installed_source(app, row), app.t('ui_catalog_installed_help'))
                else:
                    srcs = ', '.join(self.source_label(app, s) for s in row['sources'])
                    text = '%s: %s\n%s: %s' % (app.t('ui_col_status'), app.t('ui_catalog_st_missing'),
                                              app.t('ui_col_source'), srcs or '—')
                draw_wrapped(c, Rect(si.y + 2, si.x, si.h - 2, si.w), text, 'base')


# ---------------------------------------------------------------------------
class History(Screen):
    id, tab = 'history', 'ui_tab_history'

    def __init__(self):
        self.list = ListState()
        self.rows = None

    def on_enter(self, app):
        if self.rows is None:
            self.reload(app)

    def reload(self, app):
        from tui_backend import recent_runs
        try:
            self.rows = recent_runs(app.repo, 50)
        except Exception:
            self.rows = []

    def zones(self, app):
        return ['list']

    def bindings(self, app, zone):
        return [Binding(('up', 'down'), 'ui_key_move', 'vmove'), Binding(('enter',), 'ui_btn_open_log', 'open')]

    def help(self, app, zone):
        rows = self.rows or []
        return (self.detail(app, rows[self.list.index]) + '\n\n' if rows else '') + app.t('ui_help_history')

    def result_word(self, app, row):
        status = row['run_status']
        if status == 'completed' and row.get('exit_class') not in ('ok', 'success', 'clean', 'unknown', ''):
            return app.t('ui_res_failed'), 'warn', app.glyphs['needs']
        return {'completed': (app.t('ui_res_completed'), 'ok', app.glyphs['ok']),
                'failed': (app.t('ui_res_failed'), 'fail', app.glyphs['fail']),
                'interrupted': (app.t('ui_res_interrupted'), 'warn', app.glyphs['needs']),
                'started': (app.t('ui_res_started'), 'muted', app.glyphs['running'])}.get(status, (app.t('ui_res_unknown'), 'muted', '?'))

    def detail(self, app, row):
        word = self.result_word(app, row)[0]
        return app.t('ui_history_detail', file=row['filename'], result=word, exit=row.get('exit_class', ''),
                     time=duration(row.get('duration_seconds')) or '—')

    def action(self, app, zone, action):
        rows = self.rows or []
        if action == 'up':
            if self.list.index == 0:
                app.focus_zone('tabs')
            self.list.move(-1, len(rows))
        elif action == 'down':
            self.list.move(1, len(rows))
        elif action == 'open' and rows:
            app.view_run_log(rows[self.list.index])
        else:
            return action == 'vmove'
        return True

    def model_for(self, app, row):
        from tui_backend import read_summary
        from tui_runner import model_from_summary
        cache = getattr(self, '_models', {})
        if row['filename'] not in cache:
            cache[row['filename']] = model_from_summary(read_summary(app.repo, row['filename']))
        self._models = cache
        return cache[row['filename']]

    def click(self, app, payload, double=False):
        if payload[0] == 'hist_row':
            app.focus_zone('list')
            self.list.index = payload[1]
            if double:
                self.action(app, 'list', 'open')
            return True
        if payload[0] == 'hist_log':
            rows = self.rows or []
            if rows:
                app.view_run_log(rows[self.list.index])
            return True
        return False

    def scroll(self, app, zone, delta):
        self.list.move(delta, len(self.rows or []))
        return True

    def render(self, app, c, main, side):
        self.on_enter(app)
        rows = self.rows or []
        c.box(main, app.t('ui_pane_history'), self.pane_focus(app, 'list'), right=str(len(rows)) if rows else '')
        inner = main.inner()
        if not rows:
            draw_wrapped(c, inner, app.t('ui_history_empty'), 'muted')
            return
        y = inner.y
        when_w, res_w = 17, max(text_width(app.t('ui_col_result')), 14)
        c.put(y, inner.x + 2, app.t('ui_col_when'), 'muted')
        c.put(y, inner.x + 2 + when_w + 1, app.t('ui_col_result'), 'muted')
        c.put(y, inner.x + 2 + when_w + res_w + 4, app.t('ui_col_time'), 'muted')
        y += 1
        visible = inner.y + inner.h - y
        self.list.clamp(len(rows))
        self.list.offset = scroll_window(self.list.index, self.list.offset, visible, len(rows))
        for i, row in enumerate(rows[self.list.offset:self.list.offset + visible], self.list.offset):
            selected = i == self.list.index
            style = ('sel_focus' if app.zone == 'list' and app.dialog is None else 'sel') if selected else 'base'
            if selected:
                c.fill(y, inner.x, 1, inner.w, style)
                c.put(y, inner.x, app.glyphs['marker'], style)
            ts_ = row['timestamp']
            when = ts_[:16].replace('T', ' ') if ts_ else row['filename'][12:27]
            word, st, glyph = self.result_word(app, row)
            c.put(y, inner.x + 2, when, style)
            c.put(y, inner.x + 2 + when_w + 1, glyph + ' ' + word, style if selected else st)
            c.put(y, inner.x + 2 + when_w + res_w + 4, duration(row.get('duration_seconds')) or '—', style if selected else 'muted')
            c.region(y, inner.x, 1, inner.w, ('hist_row', i))
            y += 1
        if side is not None:
            self.render_details(app, c, side, rows[self.list.index])

    def render_details(self, app, c, rect, row):
        """The selected run's buckets and items (same view as the result screen)."""
        c.box(rect, app.t('ui_pane_details'))
        inner = rect.inner()
        word, style, glyph = self.result_word(app, row)
        when = (row.get('timestamp') or '')[:16].replace('T', ' ')
        c.put(inner.y, inner.x, '%s %s  %s  %s' % (glyph, word, when, duration(row.get('duration_seconds')) or ''), style, inner.w)
        c.button(inner.y + 2, inner.x, app.t('ui_btn_open_log'), primary=True, action=('hist_log',))
        model = self.model_for(app, row)
        dash = app.screens[0]
        lines = dash.result_lines(app, model, inner.w)
        area_y = inner.y + 4
        for i, (text, st, _) in enumerate(lines[:max(0, inner.y + inner.h - area_y)]):
            c.put(area_y + i, inner.x, clip(text, inner.w, app.glyphs['ellipsis']), st)
            span = dash.result_bars.get(i)
            if span and span[0] + RESULT_BAR_W <= inner.w:
                c.bar(area_y + i, inner.x + span[0], RESULT_BAR_W, span[1], tone=span[2])


# ---------------------------------------------------------------------------
class SettingsScreen(Screen):
    id, tab = 'settings', 'ui_tab_settings'

    def __init__(self):
        self.list = ListState()
        self.query = ''
        self.list.index = 0

    def on_enter(self, app):
        pass

    def zones(self, app):
        return ['list', 'search']

    def rows(self, app):
        """Flattened rows: ('section', id) | ('profile',) | ('setting', Setting)."""
        q = self.query.casefold().strip()
        out = []
        if not q or q in app.t('ui_profile').casefold() or q in app.t('ui_profile_help').casefold():
            out.append(('profile', None))
        hidden = set()
        if app.schedule().get('state') != 'on':
            hidden = {'schedule_test'}          # a test run needs automation set up first
        for section in ts.SECTIONS:
            items = [s for s in ts.SCHEMA if s.section == section and s.key not in hidden and self.matches(app, s, q)]
            if items:
                out.append(('section', section))
                out.extend(('setting', s) for s in items)
        return out

    def matches(self, app, setting, q):
        if not q:
            return True
        return q in self.label(app, setting).casefold() or q in app.t(setting.help).casefold()

    def label(self, app, setting):
        if setting.key == 'schedule' and app.schedule().get('state') != 'on':
            return app.t('ui_schedule_status_off')
        if setting.key.startswith('group_'):
            return app.t(setting.label, name=app.t('ui_group_' + setting.key[6:]))
        return app.t(setting.label)

    def selectable(self, rows):
        return [i for i, r in enumerate(rows) if r[0] != 'section']

    def current(self, app):
        rows = self.rows(app)
        sel = self.selectable(rows)
        if not sel:
            return rows, None
        if self.list.index not in sel:
            self.list.index = min(sel, key=lambda i: abs(i - self.list.index))
        return rows, rows[self.list.index]

    def value_text(self, app, setting):
        key = setting.key
        if setting.kind == 'bool':
            return app.t('ui_on') if app.settings.get(key) else app.t('ui_off')
        if setting.kind == 'choice':
            value = app.settings.get(key)
            if key == 'language':
                return ts.NATIVE_NAMES.get(value, value)
            if key == 'schedule_day':
                return app.t('ui_day_' + value)
            prefix = {'theme': 'ui_theme_', 'accent': 'ui_accent_', 'density': 'ui_density_',
                      'notify': 'ui_notify_', 'system_mode': 'ui_sysmode_', 'new_app_mode': 'ui_newapp_'}.get(key, 'ui_')
            return app.t(prefix + value)
        if setting.kind == 'int':
            value = app.settings.get(key)
            if key in ('schedule_hour', 'schedule_minute'):
                return '%02d' % value
            return str(value)
        if key == 'schedule':
            self.on_enter(app)
            st = app.schedule()
            if st.get('state') == 'off':
                return ''                       # the label already says "off"; no day or time shown
            return app.schedule_text(st)
        if key == 'exclusions':
            n = ts.count_config_lines(app.repo, 'inventory_exclusions.txt')
            return '—' if n is None else app.t('ui_entries', count=n)
        if key == 'npm_clis':
            n = ts.count_config_lines(app.repo, 'npm_global_clis.txt')
            return '—' if n is None else app.t('ui_entries', count=n)
        if key == 'github_token':
            return app.t('ui_token_set' if ts.github_token_present() else 'ui_token_missing')
        return app.glyphs['arrow']

    def default_text(self, app, setting):
        if setting.kind not in ('bool', 'choice', 'int'):
            return ''
        saved = app.settings.values[setting.key]
        app.settings.values[setting.key] = setting.default
        text = self.value_text(app, setting)
        app.settings.values[setting.key] = saved
        return text

    def bindings(self, app, zone):
        if zone == 'search':
            return [Binding((), 'ui_key_type', 'type', display='abc'), Binding(('down', 'enter'), 'ui_key_back', 'to_list'),
                    Binding(('backspace',), 'ui_key_clear', 'backspace')]
        rows, row = self.current(app)
        out = [Binding(('up', 'down'), 'ui_key_move', 'vmove')]
        kind = row[1].kind if row and row[0] == 'setting' else ('choice' if row else None)
        if kind == 'bool':
            out.append(Binding(('enter', 'space'), 'ui_key_toggle', 'activate'))
        elif kind in ('choice', 'int'):
            out += [Binding(('enter',), 'ui_key_change', 'activate'), Binding(('left', 'right'), 'ui_key_adjust', 'adjust')]
        elif kind == 'action':
            out.append(Binding(('enter',), 'ui_key_open', 'activate'))
        out.append(Binding(('/',), 'ui_key_search', 'to_search'))
        out.append(Binding(('pgup', 'pgdn'), 'ui_key_scroll', 'page', show=False))
        return out

    def help(self, app, zone):
        if zone == 'search':
            return app.t('ui_settings_search_hint')
        rows, row = self.current(app)
        if not row:
            return app.t('ui_help_settings')
        if row[0] == 'profile':
            return app.t('ui_profile_help') + '\n\n' + app.t('ui_help_settings')
        s = row[1]
        text = app.t(s.help)
        if s.kind in ('bool', 'choice', 'int'):
            origin = app.settings.origin.get(s.key, 'default')
            text += '\n\n' + app.t('ui_setting_detail', value=self.value_text(app, s), default=self.default_text(app, s))
            text += '\n' + app.t('ui_origin_label', origin=app.t('ui_origin_' + origin))
            if s.env:
                text += '\n' + app.t('ui_env_var', name=s.env)
        return text + '\n\n' + app.t('ui_help_settings')

    def action(self, app, zone, action):
        if zone == 'search':
            if action in ('down', 'enter', 'to_list'):
                app.focus_zone('list')
            elif action == 'backspace':
                self.query = self.query[:-1]
            elif action == 'up':
                app.focus_zone('tabs')
            else:
                return False
            return True
        rows, row = self.current(app)
        sel = self.selectable(rows)
        if action in ('up', 'down', 'pgup', 'pgdn'):
            if not sel:
                return True
            pos = sel.index(self.list.index) if self.list.index in sel else 0
            delta = {'up': -1, 'down': 1, 'pgup': -8, 'pgdn': 8}[action]
            if action == 'up' and pos == 0:
                app.focus_zone('search')
                return True
            self.list.index = sel[max(0, min(len(sel) - 1, pos + delta))]
            return True
        if action == 'to_search':
            app.focus_zone('search')
            return True
        if row is None:
            return action in ('vmove', 'page')
        if action in ('left', 'right'):
            self.adjust(app, row, -1 if action == 'left' else 1)
            return True
        if action == 'activate':
            self.activate(app, row)
            return True
        return action in ('vmove', 'page', 'adjust')

    def text(self, app, zone, text):
        if zone == 'search':
            self.query = (self.query + text)[:40]
            self.list.index = 0
            return True
        return False

    def save(self, app, key, value):
        try:
            app.settings.set(key, value)
        except PermissionError as exc:
            app.notify(app.t('ui_env_locked', env=str(exc)), 'status_warn')
            return
        except (OSError, ValueError) as exc:
            app.notify(app.t('ui_error', message=plain(exc)), 'status_warn')
            return
        app.after_setting(key)
        app.notify(app.t('ui_saved', name=self.label(app, ts.BY_KEY[key])), 'status_ok')

    def adjust(self, app, row, delta):
        if row[0] == 'profile':
            names = list(ts.PROFILES)
            current = app.settings.profile()
            index = names.index(current) if current in names else -1
            self.set_profile(app, names[(index + delta) % len(names)])
            return
        s = row[1]
        if s.kind == 'int':
            self.save(app, s.key, max(s.low, min(s.high, app.settings.get(s.key) + delta * s.step)))
        elif s.kind == 'choice':
            choices = list(s.choices)
            index = choices.index(app.settings.get(s.key))
            self.save(app, s.key, choices[(index + delta) % len(choices)])
        elif s.kind == 'bool':
            self.save(app, s.key, not app.settings.get(s.key))
        else:
            app.notify(app.t('ui_unknown_key', keys='Enter'), 'status')

    def set_profile(self, app, name):
        try:
            app.settings.apply_profile(name)
        except OSError as exc:
            app.notify(app.t('ui_error', message=plain(exc)), 'status_warn')
            return
        app.notify(app.t('ui_saved', name=app.t('ui_profile') + ': ' + app.t('ui_profile_' + name)), 'status_ok')

    def activate(self, app, row):
        if row[0] == 'profile':
            entries = [(app.t('ui_profile_' + p) + ' — ' + app.t('ui_profile_%s_help' % p), p) for p in ts.PROFILES]
            app.open_dialog(ChoiceDialog(app.t('ui_profile'), entries, lambda a, v: v and self.set_profile(a, v),
                                         current=app.settings.profile()))
            return
        s = row[1]
        if s.kind == 'bool':
            self.save(app, s.key, not app.settings.get(s.key))
        elif s.kind == 'choice':
            saved = app.settings.get(s.key)
            entries = []
            for choice in s.choices:
                app.settings.values[s.key] = choice
                entries.append((self.value_text(app, s), choice))
            app.settings.values[s.key] = saved
            app.open_dialog(ChoiceDialog(self.label(app, s), entries, lambda a, v: v is not None and self.save(a, s.key, v),
                                         current=saved))
        elif s.kind == 'int':
            def validate(text):
                try:
                    value = int(text.strip())
                except ValueError:
                    value = None
                if value is None or not s.low <= value <= s.high:
                    return app.t('ui_number_invalid', low=s.low, high=s.high)
                return ''
            app.open_dialog(InputDialog(self.label(app, s), app.t('ui_number_prompt', low=s.low, high=s.high), '> ',
                                        lambda a, v: v not in (None, 'timeout') and self.save(a, s.key, int(v.strip())),
                                        validate=validate, initial=str(app.settings.get(s.key)),
                                        ok_label=app.t('ui_btn_apply'), cancel_label=app.t('ui_btn_cancel')))
        elif s.kind == 'action':
            app.settings_action(s.key, self)
        elif s.kind == 'info':
            app.open_dialog(Dialog(self.label(app, s), app.t(s.help), [(app.t('ui_btn_ok'), None)], None))

    def click(self, app, payload, double=False):
        if payload[0] == 'set_row':
            app.focus_zone('list')
            self.list.index = payload[1]
            if double:
                rows, row = self.current(app)
                if row:
                    self.activate(app, row)
            return True
        if payload[0] == 'set_search':
            app.focus_zone('search')
            return True
        return False

    def scroll(self, app, zone, delta):
        self.action(app, 'list', 'down' if delta > 0 else 'up')
        return True

    def render(self, app, c, main, side):
        g = app.glyphs
        self.on_enter(app)
        rows, row = self.current(app)
        c.box(main, app.t('ui_pane_settings'), self.pane_focus(app, 'list', 'search'))
        inner = main.inner()
        y = inner.y
        searching = app.zone == 'search' and app.dialog is None
        label = app.t('ui_search_label')
        field = self.query + (('▏' if g['tl'] != '+' else '_') if searching else '')
        c.put(y, inner.x, label, 'focus_title' if searching else 'muted')
        c.put(y, inner.x + text_width(label), clip(field or app.t('ui_settings_search_hint'), inner.w - text_width(label), g['ellipsis']),
              'input' if searching else ('base' if field else 'muted'))
        c.region(y, inner.x, 1, inner.w, ('set_search',))
        y += 2
        compact = app.settings.get('density') == 'compact'
        # Build display lines: each selectable row may wrap to two lines.
        lines = []      # (row_index, text_left, value, origin, kind)
        value_w = 0
        for i, r in enumerate(rows):
            if r[0] == 'section':
                if lines and not compact:
                    lines.append((None, '', '', '', 'blank'))
                lines.append((None, app.t(ts.SECTION_LABELS[r[1]]), '', '', 'section'))
            elif r[0] == 'profile':
                lines.append((i, app.t('ui_profile'), app.t('ui_profile_' + app.settings.profile()), '', 'profile'))
            else:
                s = r[1]
                origin = app.settings.origin.get(s.key, '') if s.kind in ('bool', 'choice', 'int') else ''
                lines.append((i, self.label(app, s), self.value_text(app, s), origin, s.kind))
        origin_w = max(text_width(app.t('ui_origin_' + o)) for o in ('default', 'file', 'env')) if inner.w >= 70 else 0
        for entry in lines:
            if entry[0] is not None:
                value_w = max(value_w, text_width(entry[2]))
        value_w = min(value_w, max(10, inner.w // 2))
        label_w = inner.w - value_w - (origin_w + 2 if origin_w else 0) - 4
        display = []
        for entry in lines:
            index, text, value, origin, kind = entry
            if index is None:
                display.append(entry + (0,))
                continue
            if text_width(text) <= label_w:
                display.append(entry + (0,))
            else:
                parts = wrap(text, label_w)
                display.append((index, parts[0], value, origin, kind, 0))
                for part in parts[1:]:
                    display.append((index, part, '', '', kind, 1))
        visible = inner.y + inner.h - y
        sel_line = next((n for n, d in enumerate(display) if d[0] == self.list.index and d[5] == 0), 0)
        self.list.offset = scroll_window(sel_line, self.list.offset, visible, len(display))
        if sel_line + 1 < len(display) and display[sel_line + 1][5] == 1 and sel_line + 1 >= self.list.offset + visible:
            self.list.offset += 1
        for index, text, value, origin, kind, cont in display[self.list.offset:self.list.offset + visible]:
            if kind == 'section':
                c.put(y, inner.x, text, 'accent')
                c.put(y, inner.x + text_width(text) + 1, g['h'] * max(0, inner.w - text_width(text) - 1), 'border')
            elif kind != 'blank':
                selected = index == self.list.index
                style = ('sel_focus' if app.zone == 'list' and app.dialog is None else 'sel') if selected else 'base'
                if selected:
                    c.fill(y, inner.x, 1, inner.w, style)
                    if not cont:
                        c.put(y, inner.x, g['marker'], style)
                c.put(y, inner.x + 2, text, style if selected else ('strong' if kind == 'profile' else 'base'))
                if value:
                    vstyle = style if selected else ({'on': 'ok'}.get('on' if value == app.t('ui_on') else '', 'accent'))
                    c.put(y, inner.x + 2 + label_w + 1, clip(value, value_w, g['ellipsis']), vstyle)
                if origin and origin_w:
                    c.put(y, inner.x + inner.w - origin_w, pad(app.t('ui_origin_' + origin), origin_w, 'right'),
                          style if selected else ('warn' if origin == 'env' else 'muted'))
                c.region(y, inner.x, 1, inner.w, ('set_row', index))
            y += 1
        if side is not None:
            c.box(side, app.t('ui_pane_details'))
            si = side.inner()
            if row and row[0] == 'setting':
                c.put(si.y, si.x, clip(self.label(app, row[1]), si.w, g['ellipsis']), 'strong')
                used = draw_wrapped(c, Rect(si.y + 2, si.x, si.h - 2, si.w), self.help(app, 'list').rsplit('\n\n', 1)[0], 'base')
                if row[1].key == 'accent':
                    self.render_accent_preview(app, c, Rect(si.y + 3 + used, si.x, si.h - 3 - used, si.w))
            elif row:
                c.put(si.y, si.x, app.t('ui_profile'), 'strong')
                text = '\n'.join('%s %s — %s' % (g['radio_on'] if p == app.settings.profile() else g['radio_off'],
                                                  app.t('ui_profile_' + p), app.t('ui_profile_%s_help' % p)) for p in ts.PROFILES)
                draw_wrapped(c, Rect(si.y + 2, si.x, si.h - 2, si.w), text, 'base')


    def render_accent_preview(self, app, c, rect):
        """Live preview: each accent's own colour on a sample bar and button."""
        g = app.glyphs
        if rect.h < 2:
            return
        c.put(rect.y, rect.x, app.t('ui_accent_preview'), 'accent')
        current = app.settings.get('accent')
        name_w = max(text_width(app.t('ui_accent_' + a)) for a in ts.BY_KEY['accent'].choices)
        for i, accent in enumerate(ts.BY_KEY['accent'].choices[:rect.h - 1]):
            y = rect.y + 1 + i
            mark = g['radio_on'] if accent == current else g['radio_off']
            c.put(y, rect.x, '%s %s' % (mark, pad(app.t('ui_accent_' + accent), name_w)), 'swatch_' + accent)
            x = rect.x + 3 + name_w
            if x + 14 <= rect.x + rect.w:
                c.bar(y, x, 10, 0.7, style='swatch_' + accent)
                x += 11
            sample = '[ %s ]' % app.t('ui_accent_sample')
            if x + text_width(sample) <= rect.x + rect.w:
                c.put(y, x, sample, 'swatch_' + accent)


# ---------------------------------------------------------------------------
ALL_DIAG_ACTIONS = (('doctor', 'ui_diag_doctor', False), ('setup_inspect', 'ui_diag_setup', False),
                    ('requirements_view', 'ui_diag_requirements', False),
                    ('coverage_table', 'ui_diag_coverage', False), ('inventory', 'ui_diag_inventory', True),
                    ('toolkit_check', 'ui_diag_toolkit', False), ('native_recovery', 'ui_diag_recovery', True),
                    ('prepare', 'ui_diag_prepare', True))


def recovery_pending(state_dir):
    """True only when an interrupted update left a journal or session behind."""
    for name in ('transactions', 'native-sessions'):
        path = os.path.join(state_dir or '', name)
        try:
            if os.path.isdir(path) and not os.path.islink(path) and any(not n.startswith('.') for n in os.listdir(path)):
                return True
        except OSError:
            continue
    return False


def diag_actions(app):
    pending = recovery_pending(app.state_dir)
    return [row for row in ALL_DIAG_ACTIONS if row[0] != 'native_recovery' or pending]


def requirement_lines(app, width):
    """The Requirements view: glyph, name, status word, who needs it, and the hint when not present."""
    g = app.glyphs
    rows = app.requirements
    if rows is None:
        return [app.t('ui_req_loading' if app.requirements_state in ('idle', 'loading') else 'ui_req_unavailable')]
    if not rows:
        return [app.t('ui_req_all_present')]
    out = []
    for row in rows:
        glyph = g['ok'] if row.present else (g['needs'] if row.level == 'optional' or row.status == 'manual' else g['fail'])
        word = app.t('ui_req_status_' + row.status)
        names = ', '.join(app.t('ui_req_core') if gid == 'core' else app.t('ui_group_' + gid) for gid in row.groups)
        level = '' if row.level == 'required' else ' (%s)' % app.t('ui_req_optional')
        out.append('%s %s%s: %s' % (glyph, row.name, level, word))
        out.append('    ' + app.t('ui_req_needed_by', groups=names))
        if not row.present and row.hint:
            out.extend('    ' + line for line in wrap(g['arrow'] + ' ' + row.hint, max(10, width - 4)))
    return out


def coverage_lines(app, width):
    """A readable table from the inventory fields method / method_origin."""
    from tui_inventory import load_apps
    try:
        rows = load_apps(app.repo, app.state_dir).get('rows', [])
    except Exception:
        rows = []
    if not rows:
        return [app.t('ui_coverage_empty')]
    counts = dict(tested=0, detected=0, manual=0, unknown=0)
    name_w = min(30, max(text_width(r['name']) for r in rows))
    how_w = min(24, max([text_width(app.t('ui_coverage_how'))] + [text_width(r['method'] or '—') for r in rows]))
    out = [pad(app.t('ui_col_name'), name_w) + '  ' + pad(app.t('ui_coverage_how'), how_w) + '  ' + app.t('ui_coverage_origin')]
    for row in rows:
        origin = row['method_origin'] or 'unknown'
        counts[origin if origin in counts else 'unknown'] += 1
        label = app.t('ui_method_' + origin) if origin != 'unknown' else app.t('ui_method_unknown')
        out.append(pad(clip(row['name'], name_w), name_w) + '  ' + pad(clip(row['method'] or '—', how_w), how_w) + '  ' + label)
    out.insert(0, app.t('ui_coverage_summary', **counts))
    out.insert(1, '')
    return out


class Diagnostics(Screen):
    id, tab = 'diagnostics', 'ui_tab_diagnostics'

    def __init__(self):
        self.list = ListState()
        self.scroll_pos = 0

    def zones(self, app):
        return ['list', 'output']

    def bindings(self, app, zone):
        if zone == 'output':
            return [Binding(('up', 'down'), 'ui_key_scroll', 'vmove'), Binding(('pgup', 'pgdn'), 'ui_key_scroll', 'page', show=False)]
        return [Binding(('up', 'down'), 'ui_key_move', 'vmove'), Binding(('enter',), 'ui_key_run', 'run')]

    def help(self, app, zone):
        if zone == 'output':
            return app.t('ui_help_output')
        action, label, _ = diag_actions(app)[min(self.list.index, len(diag_actions(app)) - 1)]
        return app.t(label + '_help') + '\n\n' + app.t('ui_help_diag')

    def run(self, app, index):
        action, label, confirm = diag_actions(app)[index]
        if action == 'coverage_table':
            if app.busy():
                app.notify(app.t('ui_busy'), 'status_warn')
                return
            from tui_runner import LogBuffer
            app.task_log, app.task_label, app.task_action = LogBuffer(), 'ui_coverage_title', None
            app.task_log.feed('\n'.join(coverage_lines(app, 120)) + '\n')
            self.scroll_pos = 0
            return
        if action == 'requirements_view':
            from tui_runner import LogBuffer
            app.task_log, app.task_label, app.task_action = LogBuffer(), label, action
            self.scroll_pos = 0
            if app.requirements_state == 'idle':
                app.load_requirements()
            return
        if action == 'prepare':
            from tui_requirements import installable
            rows = installable(app.requirements)
            if app.requirements is not None and not rows:
                app.notify(app.t('ui_req_nothing_to_install'), 'status')
                return
            names = '\n'.join('%s %s' % (app.glyphs['current'], r.name) for r in rows) if rows else app.t('ui_diag_prepare_help')
            if app.busy():
                app.notify(app.t('ui_busy'), 'status_warn')
                return
            app.open_dialog(Dialog(app.t('ui_dlg_confirm'), app.t('ui_prepare_confirm', names=names),
                                   [(app.t('ui_btn_run'), 'yes'), (app.t('ui_btn_cancel'), None)],
                                   lambda a, v: v == 'yes' and a.start_task('prepare', label=label), default=1))
            return
        if confirm:
            app.open_dialog(Dialog(app.t('ui_dlg_confirm'), app.t('ui_confirm_action', name=app.t(label), help=app.t(label + '_help')),
                                   [(app.t('ui_btn_run'), 'yes'), (app.t('ui_btn_cancel'), None)],
                                   lambda a, v: v == 'yes' and a.start_task(action, label=label), default=1))
        else:
            app.start_task(action, label=label)

    def action(self, app, zone, action):
        if zone == 'output':
            step = {'up': 1, 'down': -1, 'pgup': 10, 'pgdn': -10}.get(action)
            if step is None:
                return action in ('vmove', 'page')
            self.scroll_pos = max(0, self.scroll_pos + step)
            return True
        if action == 'up':
            if self.list.index == 0:
                app.focus_zone('tabs')
            self.list.move(-1, len(diag_actions(app)))
        elif action == 'down':
            self.list.move(1, len(diag_actions(app)))
        elif action == 'run':
            self.run(app, self.list.index)
        else:
            return action == 'vmove'
        return True

    def click(self, app, payload, double=False):
        if payload[0] == 'diag_row':
            app.focus_zone('list')
            self.list.index = payload[1]
            if double:
                self.run(app, payload[1])
            return True
        return False

    def scroll(self, app, zone, delta):
        if zone == 'output':
            self.scroll_pos = max(0, self.scroll_pos - delta)
        else:
            self.list.move(delta, len(diag_actions(app)))
        return True

    def render(self, app, c, main, side):
        g = app.glyphs
        c.box(main, app.t('ui_pane_diag'), self.pane_focus(app, 'list'))
        inner = main.inner()
        y = inner.y
        for i, (action, label, confirm) in enumerate(diag_actions(app)):
            if y + 1 >= inner.y + inner.h:
                break
            selected = i == self.list.index
            style = ('sel_focus' if app.zone == 'list' and app.dialog is None else 'sel') if selected else 'base'
            running = app.task_action == action and app.job is not None and app.job.running
            if selected:
                c.fill(y, inner.x, 1, inner.w, style)
                c.put(y, inner.x, g['marker'], style)
            c.put(y, inner.x + 2, app.t(label), style if selected else 'strong')
            if running:
                c.put(y, inner.x + inner.w - 2, g['spinner'][app.tick_count % len(g['spinner'])], 'accent')
            c.region(y, inner.x, 1, inner.w, ('diag_row', i))
            y += 1
            for line in ([] if app.settings.get('density') == 'compact' else wrap(app.t(label + '_help'), inner.w - 2)):
                if y >= inner.y + inner.h:
                    break
                c.put(y, inner.x + 2, line, 'muted')
                y += 1
            y += 0 if app.settings.get('density') == 'compact' else 1
        if side is not None:
            focused = self.pane_focus(app, 'output')
            c.box(side, app.t('ui_pane_output'), focused, right=app.t(app.task_label) if app.task_label else '')
            si = side.inner()
            from tui_runner import wrap_log
            if app.task_action == 'requirements_view' and app.job is None:
                lines = [ln for text in requirement_lines(app, si.w) for ln in (wrap(text, si.w) or [''])]
            else:
                lines = wrap_log(app.task_log.all_lines(), si.w, '') if app.task_log else []
            if not lines:
                draw_wrapped(c, si, app.t('ui_log_empty'), 'muted')
                return
            self.scroll_pos = min(self.scroll_pos, max(0, len(lines) - si.h))
            end = len(lines) - self.scroll_pos
            for i, line in enumerate(lines[max(0, end - si.h):end]):
                c.put(si.y + i, si.x, line, 'base', si.w)


# ---------------------------------------------------------------------------
class About(Screen):
    """Tab 7: a scrollable guide with a table of contents; About comes last."""
    id, tab = 'about', 'ui_tab_about'

    def __init__(self):
        self.offset = 0
        self.section = 0

    def sections(self, app):
        from tui_runner import REASON_CODES
        reasons = '\n'.join('%s %s' % (app.glyphs['needs'], app.t('ui_reason_' + code))
                             for code in REASON_CODES if code != 'unknown')
        out = [(app.t('ui_guide_first_t'), app.t('ui_guide_first')),
               (app.t('ui_guide_how_t'), app.t('ui_guide_how')),
               (app.t('ui_guide_needs_t'), app.t('ui_guide_needs') + '\n' + reasons)]
        for screen in SCREENS:
            out.append((app.t('ui_tab_' + screen), app.t('ui_guide_tab_' + screen)))
        out.append((app.t('ui_guide_about_t'), app.t('ui_about_body', version=app.version, author=app.author)))
        return out

    def lines(self, app, width):
        out, starts = [], []
        for title, body in self.sections(app):
            starts.append(len(out))
            out.append((title, 'accent'))
            out.extend((line, 'base') for line in wrap(body, width))
            out.append(('', 'base'))
        return out, starts

    def zones(self, app):
        return ['toc', 'text']

    def bindings(self, app, zone):
        if zone == 'toc':
            return [Binding(('up', 'down'), 'ui_key_move', 'vmove'), Binding(('enter',), 'ui_key_open', 'enter'),
                    Binding(('pgup', 'pgdn'), 'ui_key_jump_section', 'page')]
        return [Binding(('up', 'down'), 'ui_key_scroll', 'vmove'), Binding(('pgup', 'pgdn'), 'ui_key_jump_section', 'page')]

    def help(self, app, zone):
        return app.t('ui_guide_tab_about')

    def jump(self, app, delta):
        starts = getattr(self, '_starts', [0])
        current = max([i for i, start in enumerate(starts) if start <= self.offset] or [0])
        self.section = max(0, min(len(starts) - 1, current + delta))
        self.offset = starts[self.section]

    def action(self, app, zone, action):
        if zone == 'toc':
            count = len(self.sections(app))
            if action in ('pgup', 'pgdn'):
                self.jump(app, -1 if action == 'pgup' else 1)
                return True
            if action == 'up':
                if self.section == 0:
                    app.focus_zone('tabs')
                    return True
                self.section -= 1
            elif action == 'down':
                self.section = min(count - 1, self.section + 1)
            elif action == 'enter':
                app.focus_zone('text')
            else:
                return action == 'vmove'
            self.offset = getattr(self, '_starts', [0] * count)[self.section]
            return True
        if action == 'up':
            if self.offset == 0:
                app.focus_zone('tabs')
            self.offset = max(0, self.offset - 1)
        elif action == 'down':
            self.offset += 1
        elif action in ('pgup', 'pgdn'):
            self.jump(app, -1 if action == 'pgup' else 1)
        else:
            return action in ('vmove', 'page')
        return True

    def click(self, app, payload, double=False):
        if payload[0] == 'guide_sec':
            self.section = payload[1]
            self.offset = getattr(self, '_starts', [0] * (payload[1] + 1))[payload[1]]
            app.focus_zone('toc')
            return True
        return False

    def scroll(self, app, zone, delta):
        self.offset = max(0, self.offset + delta)
        return True

    def render(self, app, c, main, side):
        g = app.glyphs
        if side is not None:
            toc_rect, text_rect = main, side
        else:
            toc_rect, text_rect = None, main
        sections = self.sections(app)
        inner_w = text_rect.w - 4
        lines, starts = self.lines(app, inner_w)
        self._starts = starts
        if toc_rect is not None:
            c.box(toc_rect, app.t('ui_guide_contents'), self.pane_focus(app, 'toc'))
            ti = toc_rect.inner()
            current = max([i for i, start in enumerate(starts) if start <= self.offset] or [0])
            for i, (title, _) in enumerate(sections[:ti.h]):
                selected = i == current
                style = ('sel_focus' if app.zone == 'toc' and app.dialog is None else 'sel') if selected else 'base'
                if selected:
                    c.fill(ti.y + i, ti.x, 1, ti.w, style)
                c.put(ti.y + i, ti.x, (g['marker'] + ' ' if selected else '  ') + clip(title, ti.w - 2, g['ellipsis']), style)
                c.region(ti.y + i, ti.x, 1, ti.w, ('guide_sec', i))
        c.box(text_rect, app.t('ui_pane_about'), self.pane_focus(app, 'text') or (toc_rect is None and self.pane_focus(app, 'toc')),
              right=app.t('ui_range', first=min(len(lines), self.offset + 1),
                          last=min(len(lines), self.offset + text_rect.h - 2), total=len(lines)))
        inner = text_rect.inner()
        self.offset = max(0, min(self.offset, max(0, len(lines) - inner.h)))
        for i, (text, style) in enumerate(lines[self.offset:self.offset + inner.h]):
            c.put(inner.y + i, inner.x, text, style, inner.w)


def make_screens():
    return [Dashboard(), Apps(), Catalog(), History(), SettingsScreen(), Diagnostics(), About()]
