"""macOS Updates terminal interface: app state, layout, key/mouse dispatch
and the non-blocking curses loop. Screens live in tui_screens, dialogs in
tui_dialogs, the run model in tui_runner and settings in tui_settings.

Rendering never grants execution authority: every update, installation or
schedule change starts only from an explicit user action and the scripts keep
all their own confirmations.
"""
import curses
import os
import platform
import shutil
import sys
import time

import tui_settings as ts
from tui_backend import TerminalJob, build_command, child_environment, host_facts, read_summary, recent_runs
from tui_dialogs import ChoiceDialog, Dialog, InputDialog, prompt_dialog
from tui_i18n import tr
from tui_keymap import Binding, key_display, key_name, keybar_items, lookup
from tui_overrides import OverrideStore, state_dir as default_state_dir
from tui_runner import (EventTailer, LogBuffer, RunModel, detect_prompt, model_from_summary, parse_directive, wrap_log,
                        private_event_path)
from tui_screens import SCREENS, make_screens, status_glyph
from tui_theme import Theme, color_disabled, detect_background, glyphs, resolve_theme, wants_ascii
from tui_widgets import Canvas, Rect, clip, duration, pad, plain, text_width, wrap

MIN_ROWS, MIN_COLS = 12, 40
GENERIC = ('vmove', 'hmove', 'page', 'ends', 'adjust')
NOTICE_SECONDS = 6
SIDE_RATIO = dict(dashboard=0.40, apps=0.32, catalog=0.34, history=0.4, settings=0.36, diagnostics=0.5, about=0.6)
# Lists are sized to their content; the detail/log pane takes the rest.
MAIN_TARGET = dict(dashboard=62, catalog=62, history=54, settings=86, diagnostics=46, about=36)
MIN_MAIN = dict(dashboard=46, apps=80, catalog=80, history=50, settings=66, diagnostics=40, about=24)
VIEW_ALIASES = dict(home='dashboard', updates='dashboard', wizard='diagnostics', inventory='apps', catalog='catalog',
                    diagnostics='diagnostics', history='history', settings='settings', about='about', help='about')


class App:
    def __init__(self, repo, initial_view='dashboard', state_dir=None, home=None, environ=None, sysinfo=None,
                 launch_dry_run=False, launch_skip=(), animate=True, requirements_reader=None):
        self.repo = os.path.realpath(repo)
        self.environ = dict(os.environ if environ is None else environ)
        self.state_dir = state_dir or default_state_dir()
        self.home = home
        self.settings = ts.SettingsStore(self.state_dir, self.environ, home=self.home)
        self.overrides = OverrideStore(self.state_dir)
        self.screens = make_screens()
        self.screen_index = SCREENS.index(VIEW_ALIASES.get(initial_view, initial_view)) \
            if VIEW_ALIASES.get(initial_view, initial_view) in SCREENS else 0
        self.zone = self.help_target = 'actions'
        self.dialog = None
        self.job = None
        self.job_kind = None
        self.task_action = None
        self.task_label = None
        self.task_log = None
        self.run = None
        self.run_log = None
        self.tailer = None
        self.event_path = None
        self.last_model = None
        self.show_result = False
        self.prompt_hidden = None
        self.answered_detected = set()
        self.detected_count = -1
        self.log_scroll = 0
        self.log_expand_all = False
        self.overlay = None           # None | 'log' | ('viewer', title, lines)
        self.overlay_scroll = 0
        self.help_scroll = 0
        self.help_visible = None      # None = follow the setting on wide screens
        self.notice = ('', 'status', 0)
        self.should_exit = False
        self.exit_mode = None
        self.exit_after_job = False
        self.pending_toolkit_receipt = None
        self.toolkit_report = None
        self.launch_dry_run = bool(launch_dry_run)
        # Dashboard ticks for this session only: gid -> bool. A group not in here follows Settings.
        self.session_groups = {LEGACY.get(g, g): False for g in launch_skip}
        self.tick_count = 0
        # Requirements (update_all.sh --requirements --tsv) are read lazily in a thread after the first frames;
        # None = not read (yet) or unreadable, [] = read and empty. Without a reader nothing is ever run.
        self.requirements_reader = requirements_reader
        self.requirements, self.requirements_state, self._req_thread = None, 'idle', None
        self._exit_seen = None
        self._task_prompt = None
        self.mode = 'wide'
        self.animate = animate
        self.theme_dirty = True
        self.terminal_bg = None            # 'light' | 'dark' as asked from the terminal at start-up (OSC 11)
        self.last_canvas = None
        self.rows, self.cols = 24, 80
        self.probe_host = sysinfo is None
        self.sysinfo = sysinfo or system_info()
        self.facts_cache, self.facts_time = None, 0.0
        self.schedule_cache = None
        self.last_run_time = None
        try:
            with open(os.path.join(self.repo, 'VERSION'), encoding='utf-8') as handle:
                self.version = plain(handle.read().strip())[:32]
        except OSError:
            self.version = '?'
        self.author = plain(tr('about_author', self.lang))
        self.last_run = None
        self.refresh_last_run()
        self.zone = self.help_target = self.screen.zones(self)[0]
        self.screen.on_enter(self)

    # -- basics ----------------------------------------------------------------
    @property
    def lang(self):
        return self.settings.get('language')

    @property
    def screen(self):
        return self.screens[self.screen_index]

    @property
    def glyphs(self):
        return glyphs(wants_ascii(self.environ, self.settings.get('ascii')), mono=color_disabled(self.environ))

    def theme_name(self):
        """'light' or 'dark': the Colours setting, with ``auto`` resolved from the terminal's own background."""
        return resolve_theme(self.settings.get('theme'), self.terminal_bg, self.environ)

    def t(self, key, **values):
        return tr(key, self.lang, **values)

    def notify(self, text, style='status'):
        self.notice = (text, style, time.monotonic())

    def busy(self):
        return self.job is not None

    def run_active(self):
        return self.run is not None

    def current_model(self):
        return self.run or self.last_model

    def refresh_last_run(self):
        try:
            rows = recent_runs(self.repo, 1)
            self.last_run = rows[0] if rows else None
        except Exception:
            self.last_run = None
        if self.last_run and (self.last_model is None or self.last_model.from_history):
            self.last_model = model_from_summary(read_summary(self.repo, self.last_run['filename']))
            self.last_run_time = parse_time(self.last_run.get('timestamp'))

    def facts(self):
        """Free disk and power, refreshed at most once a minute (read only)."""
        if not self.probe_host:
            return self.sysinfo.get('facts', {})
        if self.facts_cache is None or time.monotonic() - self.facts_time > 60:
            try:
                self.facts_cache = host_facts()
            except Exception:
                self.facts_cache = {}
            self.facts_time = time.monotonic()
        return self.facts_cache

    def schedule(self):
        if self.schedule_cache is None:
            self.schedule_cache = ts.schedule_status(self.home)
        return self.schedule_cache

    def relative(self, epoch):
        if epoch is None:
            return '?'
        delta = max(0, time.time() - epoch)
        if delta < 90:
            return self.t('ui_ago_now')
        if delta < 3600:
            return self.t('ui_ago_min', n=int(delta // 60))
        if delta < 86400:
            return self.t('ui_ago_hour', n=int(delta // 3600))
        days = int(delta // 86400)
        return self.t('ui_ago_yesterday') if days == 1 else self.t('ui_ago_days', n=days)

    def next_run_text(self):
        st = self.schedule()
        if st.get('state') != 'on':
            return None
        return self.schedule_text(st)

    def override_group(self, row):
        return row['group']

    def group_enabled(self, gid):
        chosen = self.session_groups.get(gid)
        return bool(self.settings.get('group_' + gid)) if chosen is None else chosen

    def enabled_groups(self):
        return [g for g in ts.GROUPS if self.group_enabled(g)]

    def toggle_session_group(self, gid):
        """Tick or untick one group for this session. The Settings file is not written."""
        if gid not in ts.GROUPS:
            return
        self.session_groups[gid] = not self.group_enabled(gid)

    def toggle_all_session_groups(self):
        """All groups when any is unticked, otherwise none."""
        value = len(self.enabled_groups()) < len(ts.GROUPS)
        for gid in ts.GROUPS:
            self.session_groups[gid] = value

    def focus_zone(self, zone):
        if zone not in ('tabs', 'help', 'overlay') and zone not in self.screen.zones(self):
            zone = self.screen.zones(self)[0]
        self.zone = zone
        if zone not in ('tabs', 'help'):
            self.help_target = zone
            self.help_scroll = 0

    def switch(self, index):
        if 0 <= index < len(self.screens):
            self.screen_index = index
            self.screen.on_enter(self)
            self.focus_zone(self.screen.zones(self)[0])
            self.overlay = None

    def open_dialog(self, dialog):
        self.dialog = dialog

    # -- jobs ----------------------------------------------------------------
    def start_run(self, dry_run=False):
        if self.busy():
            self.notify(self.t('ui_busy'), 'status_warn')
            return False
        enabled = self.enabled_groups()
        if not enabled:
            self.notify(self.t('ui_no_groups'), 'status_warn')
            return False
        dry_run = dry_run or self.launch_dry_run or self.settings.get('check_only')
        flags = self.settings.flags(dry_run=dry_run, groups=enabled)
        try:
            command = build_command(self.repo, 'run', flags)
            self.event_path = private_event_path()
            env = child_environment(self.lang, self.settings.child_env())
            env['MAC_UPDATE_EVENT_FILE'] = self.event_path
            job = self.spawn(command, env)
        except Exception as exc:
            self.notify(self.t('ui_error', message=plain(exc)), 'status_warn')
            return False
        self.job, self.job_kind = job, 'run'
        self.run = RunModel(enabled, dry_run)
        self.run_log = LogBuffer()
        self.tailer = EventTailer(self.event_path)
        self.show_result = False
        self.prompt_hidden = None
        self.log_scroll = 0
        dash = self.screens[0]
        dash.button = len(dash.buttons(self)) - 1
        dash.expanded = set()
        self.notify(self.t('ui_started', name=self.t('ui_btn_preview' if dry_run else 'ui_btn_update')), 'status')
        return True

    def start_task(self, action, label=None, extra=(), install_plan=None):
        if self.busy():
            self.notify(self.t('ui_busy'), 'status_warn')
            return False
        try:
            command = build_command(self.repo, action, list(extra), install_plan=install_plan)
            job = self.spawn(command, child_environment(self.lang, self.settings.child_env()))
        except Exception as exc:
            self.notify(self.t('ui_error', message=plain(exc)), 'status_warn')
            return False
        self.job, self.job_kind = job, 'task'
        self.task_action, self.task_label = action, label
        self.task_log = LogBuffer()
        self.notify(self.t('ui_started', name=self.t(label) if label else action), 'status')
        return True

    def spawn(self, command, env):
        job = TerminalJob(command, env)
        job.resize(max(10, self.rows - 6), max(40, self.cols // 2))
        return job.start()

    def current_log(self):
        return self.run_log if self.job_kind == 'run' else self.task_log

    def load_requirements(self):
        """Start (or restart) reading the requirements in the background."""
        if self.requirements_reader is None or (self._req_thread is not None and self._req_thread.is_alive()):
            return
        import threading

        def work():
            try:
                rows = self.requirements_reader()
            except Exception:
                rows = None
            if rows is None:
                self.requirements_state = 'error'
            else:
                self.requirements, self.requirements_state = rows, 'ready'
        self.requirements_state = 'loading'
        self._req_thread = threading.Thread(target=work, name='mau-requirements', daemon=True)
        self._req_thread.start()

    def missing_requirements(self):
        from tui_requirements import missing_required
        return missing_required(self.requirements)

    def tick(self):
        self.tick_count += 1
        if self.requirements_state == 'idle' and self.requirements_reader is not None and self.tick_count >= 3:
            self.load_requirements()   # after the first frames, never before
        job = self.job
        if job is not None:
            log = self.current_log()
            try:
                chunks = job.poll()
            except OSError:
                chunks = []
            for chunk in chunks:
                for line in log.feed(chunk):
                    self.directive(line)
            if self.run is not None and self.tailer is not None:
                for event in self.tailer.read():
                    self.run.handle(event)
                    if event.get('type') in ('group_start', 'item_start') and self.run.active:
                        self.run_log.begin(self.run.active)
            if log.count != self.detected_count:
                self.detected_count = log.count
                self.answered_detected.clear()
            self.check_prompts(job, log)
            if not job.running:
                now = time.monotonic()
                if self._exit_seen is None:
                    self._exit_seen = now
                if job._master is None or now - self._exit_seen > 3:
                    self.finish_job()
            else:
                self._exit_seen = None
        if self.dialog is not None:
            self.dialog.tick(self)

    def directive(self, line):
        kind, payload = parse_directive(line)
        if kind == 'phase' and self.run is not None:
            self.run.legacy_phase(*payload)
            if payload[1] == 'running' and self.run.active:
                self.run_log.begin(self.run.active)
        elif kind == 'toolkit' and self.task_action in ('toolkit_check', 'toolkit_prepare'):
            self.toolkit_report = payload

    def echo_off(self):
        """True only while the job's pty is in hidden-input mode (ECHO off): the one state in which a password
        may be typed or forwarded."""
        job = self.job
        try:
            return bool(job is not None and job.running and job.secret_input)
        except Exception:
            return False

    def password_box_open(self):
        return self.dialog is not None and getattr(self.dialog, 'kind', '') == 'input' and getattr(self.dialog, 'secret', False)

    def close_password_box(self):
        """Drop an open password box without sending anything; it is wiped by finish()."""
        dialog = self.dialog
        if dialog is not None:
            dialog.value = ''
        self.dialog = None

    def sudo_notice_active(self):
        prompt = self.run.prompt if self.run is not None else None
        return bool(prompt and prompt.get('kind') == 'sudo' and not prompt.get('detected') and not self.password_box_open())

    def check_prompts(self, job, log):
        prompt = self.run.prompt if self.run is not None else None
        secret = self.echo_off()
        # The password box lives only as long as the pty hides its input.
        if self.password_box_open() and self.run is not None and self.run.prompt is None and \
                getattr(self.dialog, 'ident', None) != 'pty-sudo':
            self.close_password_box()            # the engine said the password request is over
        if self.password_box_open() and not secret:
            self.close_password_box()
            if prompt is not None and (prompt.get('detected') or prompt.get('kind') == 'sudo'):
                if prompt.get('detected') and self.run is not None:
                    self.run.prompt = None
                self._task_prompt = None
                self.prompt_hidden = None
            prompt = self.run.prompt if self.run is not None else None
        if prompt is None and job.running:
            idle = time.monotonic() - log.last_output
            found = detect_prompt(log, secret, idle, allow_yesno=not (self.run is not None and self.run.prompt_events))
            if found and found['id'] not in self.answered_detected:
                prompt = found
                if self.run is not None:
                    self.run.prompt = found
                else:
                    self._task_prompt = found
            elif getattr(self, '_task_prompt', None) is not None and self.run is None:
                prompt = self._task_prompt
        if prompt is None:
            return
        if prompt.get('kind') == 'sudo':
            # An engine "sudo" prompt is only a heads-up (Touch ID may answer it); the input box needs hidden input.
            if not secret:
                return
        if self.prompt_hidden == prompt['id']:
            return
        if self.dialog is not None and getattr(self.dialog, 'ident', None) == prompt['id']:
            return
        self.dialog = prompt_dialog(self, prompt)

    def answer_prompt(self, prompt, value, secret=False):
        if value is None:
            self.prompt_hidden = prompt['id']
            self.notify(self.t('ui_prompt_waiting'), 'status_warn')
            return
        self.prompt_hidden = None
        self._task_prompt = None
        # Until new output arrives, the PTY still looks like it is asking.
        self.answered_detected.update(('pty-sudo', 'pty-yesno'))
        if prompt.get('detected'):
            self.answered_detected.add(prompt['id'])
        if self.run is not None:
            self.run.answered.add(prompt['id'])
            self.run.prompt = None
        if value == 'timeout':
            self.notify(self.t('ui_default_used'), 'status')
            return
        if secret and not self.echo_off():
            # Echo is on: the shell is not asking for a password now, so typed text must not reach the run
            # (it would show in the log). Drop it.
            value = None
            self.notify(self.t('ui_password_not_needed'), 'status')
            return
        if self.job is not None:
            try:
                self.job.send(value + '\n')
            except (OSError, ValueError):
                pass
        value = None
        self.notify(self.t('ui_password_sent' if secret else 'ui_answer_sent'), 'status_ok')

    def reopen_prompt(self):
        prompt = (self.run.prompt if self.run is not None else None) or getattr(self, '_task_prompt', None)
        self.prompt_hidden = None
        if prompt is not None and (prompt.get('kind') != 'sudo' or self.echo_off()):
            self.dialog = prompt_dialog(self, prompt)

    def finish_job(self):
        job, kind = self.job, self.job_kind
        self._exit_seen = None
        code = job.returncode
        if kind == 'run' and self.run is not None:
            if self.tailer is not None:
                for event in self.tailer.read():
                    self.run.handle(event)
            self.run.finish(returncode=code, stopped=job.stop_requested)
            self.last_model = self.run
            self.last_run_time = time.time()
            self.run = None
            self.show_result = True
            self.prompt_hidden = None
            self.cleanup_events()
            self.refresh_last_run()
            if self.dialog is not None and getattr(self.dialog, 'ident', None):
                self.dialog = None
            self.notify(self.t('ui_finished' if code == 0 else 'ui_job_failed',
                               name=self.t('ui_btn_preview' if self.last_model.dry_run else 'ui_btn_update')),
                        'status_ok' if code == 0 else 'status_warn')
            if self.screen_index == 0:
                self.focus_zone('actions')
                self.screens[0].button = 0
        else:
            action = self.task_action
            name = self.t(self.task_label) if self.task_label else action
            self.notify(self.t('ui_finished' if code == 0 else 'ui_job_failed', name=name),
                        'status_ok' if code == 0 else 'status_warn')
            self._task_prompt = None
            if action == 'inventory':
                self.screens[SCREENS.index('apps')].model = None
                self.screens[SCREENS.index('catalog')].rows_cache = None
                self.screen.on_enter(self)
            elif action == 'catalog':
                self.screens[SCREENS.index('catalog')].rows_cache = None
            elif action == 'schedule':
                self.schedule_cache = None
            elif action in ('toolkit_check', 'toolkit_prepare'):
                self.toolkit_result()
            elif action == 'prepare':
                self.load_requirements()
        self.job, self.job_kind = None, None
        if self.exit_after_job:
            self.should_exit = True

    KEEP_EVENT_FILES = 20

    def cleanup_events(self):
        """Keep the run's event file as <state>/events/run-<time>.jsonl (0600, the
        newest KEEP_EVENT_FILES are kept) so a run can be diagnosed later."""
        if self.event_path:
            try:
                import time
                import mu_paths
                folder = os.path.join(self.state_dir, 'events')
                mu_paths.make_private_dirs(folder)
                if os.path.isfile(self.event_path) and not os.path.islink(self.event_path):
                    target = os.path.join(folder, time.strftime('run-%Y%m%d-%H%M%S.jsonl'))
                    import shutil
                    os.chmod(self.event_path, 0o600)
                    shutil.move(self.event_path, target)
                kept = sorted(n for n in os.listdir(folder) if n.startswith('run-') and n.endswith('.jsonl'))
                for name in kept[:-self.KEEP_EVENT_FILES]:
                    os.unlink(os.path.join(folder, name))
            except (OSError, ValueError):
                pass
            try:
                os.unlink(self.event_path)
            except OSError:
                pass
            try:
                os.rmdir(os.path.dirname(self.event_path))
            except OSError:
                pass
        self.event_path = None
        self.tailer = None

    def toolkit_result(self):
        report = self.toolkit_report or {}
        status = str(report.get('status', ''))
        if status == 'ready' and isinstance(report.get('receipt'), dict):
            version = plain(report.get('target_version') or report.get('version') or '?')[:32]

            def done(app, value):
                if value == 'yes':
                    app.pending_toolkit_receipt = report['receipt']
                    app.should_exit = True
            self.dialog = Dialog(self.t('ui_set_toolkit'), self.t('ui_toolkit_ready', version=version),
                                 [(self.t('ui_btn_yes'), 'yes'), (self.t('ui_btn_no'), None)], done, default=1)
        elif status in ('current', 'blocked', 'available', 'failed'):
            self.notify(self.t('ui_toolkit_status', status=self.t('toolkit_status_' + status)), 'status')

    def ask_stop(self):
        if self.job is None:
            return

        def done(app, value):
            if value == 'stop' and app.job is not None:
                app.job.interrupt()
                app.notify(app.t('ui_stopping'), 'status_warn')
        self.dialog = Dialog(self.t('ui_dlg_stop_title'), self.t('ui_dlg_stop_body'),
                             [(self.t('ui_btn_stop_run'), 'stop'), (self.t('ui_btn_keep'), None)], done, default=1)

    def ask_quit(self):
        if self.job is None or not self.job.running:
            self.should_exit = True
            return

        def done(app, value):
            if value == 'detach':
                app.exit_mode = 'detach'
                app.should_exit = True
            elif value == 'stop' and app.job is not None:
                app.job.interrupt()
                app.exit_after_job = True
                app.notify(app.t('ui_stopping'), 'status_warn')
        self.dialog = Dialog(self.t('ui_dlg_quit_title'), self.t('ui_dlg_quit_body'),
                             [(self.t('ui_btn_keep'), None), (self.t('ui_btn_detach'), 'detach'),
                              (self.t('ui_btn_stop_run'), 'stop')], done, default=0)

    def toggle_full_log(self):
        self.overlay = None if self.overlay == 'log' else 'log'
        self.overlay_scroll = 0

    def open_viewer(self, title, lines):
        self.overlay = ('viewer', title, lines)
        self.overlay_scroll = 0

    # -- settings actions ------------------------------------------------------
    def after_setting(self, key):
        if key in ('theme', 'accent', 'ascii', 'mouse'):
            self.theme_dirty = True
        if key == 'help_open':
            self.help_visible = None

    def settings_action(self, key, screen):
        if key == 'open_apps':
            self.switch(SCREENS.index('apps'))
        elif key == 'open_diagnostics':
            self.switch(SCREENS.index('diagnostics'))
        elif key == 'scan_now':
            self.start_task('inventory', label='ui_diag_inventory')
        elif key == 'toolkit_update':
            self.start_task('toolkit_prepare', label='ui_set_toolkit')
        elif key == 'schedule':
            self.schedule_flow()
        elif key == 'schedule_test':
            minutes = ts.TEST_RUN_MINUTES

            def done_test(app, value):
                if value == 'yes':
                    app.start_task('schedule', label='ui_set_schedule_test', extra=['--once-in', str(minutes)])
            self.dialog = Dialog(self.t('ui_set_schedule_test'), self.t('ui_sched_test_confirm', minutes=minutes),
                                 [(self.t('ui_btn_apply'), 'yes'), (self.t('ui_btn_cancel'), None)], done_test, default=1)
        elif key == 'open_last_log':
            self.view_last_log()
        elif key == 'export':
            self.dialog = InputDialog(self.t('ui_set_export'), self.t('ui_export_prompt'), '> ', self.do_export,
                                      initial=os.path.join(self.home or os.path.expanduser('~'), 'mac-update-settings.json'),
                                      ok_label=self.t('ui_btn_apply'), cancel_label=self.t('ui_btn_cancel'))
        elif key == 'import':
            self.dialog = InputDialog(self.t('ui_set_import'), self.t('ui_import_prompt'), '> ', self.do_import,
                                      initial=os.path.join(self.home or os.path.expanduser('~'), 'mac-update-settings.json'),
                                      ok_label=self.t('ui_btn_apply'), cancel_label=self.t('ui_btn_cancel'))
        elif key == 'reset':
            def done(app, value):
                if value == 'yes':
                    try:
                        app.settings.reset()
                        app.theme_dirty = True
                        app.notify(app.t('ui_reset_done'), 'status_ok')
                    except OSError as exc:
                        app.notify(app.t('ui_error', message=plain(exc)), 'status_warn')
            self.dialog = Dialog(self.t('ui_set_reset'), self.t('ui_reset_confirm'),
                                 [(self.t('ui_set_reset'), 'yes'), (self.t('ui_btn_cancel'), None)], done, default=1)

    def do_export(self, app, path):
        if not path or path == 'timeout':
            return
        import json
        path = os.path.expanduser(path.strip())
        try:
            data = self.settings.export_data(self.overrides.export_rows())
            ts.atomic_write(path, (json.dumps(data, indent=1, ensure_ascii=False) + '\n').encode('utf-8'))
            self.notify(self.t('ui_exported', path=path), 'status_ok')
        except OSError as exc:
            self.notify(self.t('ui_error', message=plain(exc)), 'status_warn')

    def do_import(self, app, path):
        if not path or path == 'timeout':
            return
        import json
        path = os.path.expanduser(path.strip())
        try:
            with open(path, 'rb') as handle:
                data = json.loads(handle.read(1024 * 1024).decode('utf-8'))
            rows = self.settings.import_data(data)
            count = self.overrides.import_rows(rows)
            self.theme_dirty = True
            self.notify(self.t('ui_imported', count=count), 'status_ok')
        except (OSError, ValueError) as exc:
            self.notify(self.t('ui_error', message=plain(exc)), 'status_warn')

    def schedule_flow(self):
        """Daily automation. Off: ask the trigger, the time (no preset) and the
        notification mode, then confirm with exactly what will be installed.
        On: confirm turning it off. Nothing changes without the final Yes."""
        status = ts.schedule_status(self.home)
        if status.get('state') == 'on':
            def done_off(app, value):
                if value == 'yes':
                    app.start_task('schedule', label='ui_set_schedule', extra=['--uninstall'])
            self.dialog = Dialog(self.t('ui_set_schedule'), self.t('ui_sched_confirm_off'),
                                 [(self.t('ui_btn_disable'), 'yes'), (self.t('ui_btn_cancel'), None)], done_off, default=1)
            return
        choice = {}

        def confirm(app):
            try:
                args = ts.schedule_args(choice['trigger'], choice.get('time'), choice['notify'],
                                        system_updates=bool(app.settings.get('schedule_system')))
            except ValueError:
                app.notify(app.t('ui_sched_time_invalid'), 'status_warn')
                return
            what = app.schedule_text(dict(state='on', notify=choice['notify'], triggers=(
                ([dict(type='calendar', weekday=None, hour=ts.parse_hhmm(choice['time'])[0],
                       minute=ts.parse_hhmm(choice['time'])[1])] if choice['trigger'] != 'login' else [])
                + ([dict(type='login')] if choice['trigger'] != 'daily' else []))))
            body = app.t('ui_sched_confirm_on', what=what, plist=ts.launchagent_path(app.home),
                         command='install_launchagent.sh ' + ' '.join(args))

            def done(app2, value):
                if value == 'yes':
                    app2.start_task('schedule', label='ui_set_schedule', extra=args)
            app.dialog = Dialog(app.t('ui_set_schedule'), body,
                                [(app.t('ui_btn_enable'), 'yes'), (app.t('ui_btn_cancel'), None)], done, default=1)

        def ask_notify(app):
            entries = [(app.t('ui_sched_notify_title'), None)] + [
                (app.t('ui_sched_notify_' + m), m) for m in ts.SCHEDULE_NOTIFY]

            def done(app2, value):
                if value in ts.SCHEDULE_NOTIFY:
                    choice['notify'] = value
                    confirm(app2)
            app.open_dialog(ChoiceDialog(app.t('ui_set_schedule'), entries, done))

        def ask_time(app):
            def valid(text):
                try:
                    ts.parse_hhmm(text)
                except ValueError:
                    return app.t('ui_sched_time_invalid')
                return ''

            def done(app2, value):
                if value and value != 'timeout':
                    choice['time'] = value.strip()
                    ask_notify(app2)
            app.open_dialog(InputDialog(app.t('ui_set_schedule'), app.t('ui_sched_time_prompt'), '> ', done,
                                        validate=valid, initial='', ok_label=app.t('ui_btn_apply'),
                                        cancel_label=app.t('ui_btn_cancel')))

        entries = [(self.t('ui_sched_trigger_title'), None)] + [
            (self.t('ui_sched_trigger_' + t), t) for t in ts.SCHEDULE_TRIGGERS]

        def done_trigger(app, value):
            if value in ts.SCHEDULE_TRIGGERS:
                choice['trigger'] = value
                if value == 'login':
                    ask_notify(app)
                else:
                    ask_time(app)
        self.open_dialog(ChoiceDialog(self.t('ui_set_schedule'), entries, done_trigger))

    def schedule_text(self, status):
        """One line for the automation state: off, or the triggers and notify mode."""
        state = status.get('state')
        if state == 'off':
            return self.t('ui_schedule_off')
        if state != 'on':
            return self.t('ui_schedule_unknown')
        parts = []
        for trig in status.get('triggers') or []:
            if trig.get('type') == 'login':
                parts.append(self.t('ui_sched_what_login'))
            elif trig.get('type') == 'calendar':
                when = '%02d:%02d' % (trig.get('hour') or 0, trig.get('minute') or 0)
                day = trig.get('weekday')
                if isinstance(day, int) and 0 <= day <= 7:
                    parts.append(self.t('ui_schedule_on', day=self.t('ui_day_%s' % (7 if day == 0 else day)), time=when))
                else:
                    parts.append(self.t('ui_sched_what_daily', time=when))
        notify = status.get('notify')
        text = ', '.join(parts) or self.t('ui_schedule_unknown')
        if notify in ts.SCHEDULE_NOTIFY:
            text += ' · ' + self.t('ui_sched_notify_' + notify)
        if status.get('system_updates'):
            text += ' · ' + self.t('ui_sched_with_macos')
        return text
    def open_schedule_setup(self):
        """Settings → daily automation, then the set-up questions (no preset
        day or time; turning it on still ends with an explicit confirmation)."""
        index = SCREENS.index('settings')
        screen = self.screens[index]
        self.switch(index)
        rows = screen.rows(self)
        for i, row in enumerate(rows):
            if row[0] == 'setting' and row[1].key == 'schedule':
                screen.list.index = i
        self.schedule_flow()

    def view_run_log(self, row):
        """Open the update_all_<stamp>.log that belongs to a run summary."""
        stamp = row['filename'][len('run_summary_'):-len('.json')]
        name = 'update_all_%s.log' % stamp
        import mu_paths
        path = os.path.join(mu_paths.logs_dir(self.repo), name)
        if not os.path.isfile(path) or os.path.islink(path):
            self.view_last_log()
            return
        self.open_log_file(path, name)

    def open_log_file(self, path, name):
        try:
            with open(path, 'rb') as handle:
                handle.seek(max(0, os.path.getsize(path) - 512 * 1024))
                text = handle.read().decode('utf-8', 'replace')
        except OSError as exc:
            self.notify(self.t('ui_error', message=plain(exc)), 'status_warn')
            return
        buffer = LogBuffer()
        buffer.feed(text + '\n')
        self.open_viewer(name, buffer.all_lines()[-3000:])

    def view_last_log(self):
        import mu_paths
        logs = mu_paths.logs_dir(self.repo)
        try:
            names = sorted(n for n in os.listdir(logs) if n.startswith('update_all_') and n.endswith('.log')
                           and not os.path.islink(os.path.join(logs, n)))
        except OSError:
            names = []
        if not names:
            self.notify(self.t('ui_no_log'), 'status_warn')
            return
        path = os.path.join(logs, names[-1])
        try:
            with open(path, 'rb') as handle:
                handle.seek(max(0, os.path.getsize(path) - 512 * 1024))
                text = handle.read().decode('utf-8', 'replace')
        except OSError as exc:
            self.notify(self.t('ui_error', message=plain(exc)), 'status_warn')
            return
        buffer = LogBuffer()
        buffer.feed(text + '\n')
        self.open_viewer(names[-1], buffer.all_lines()[-3000:])

    # -- presentation helpers ----------------------------------------------------
    def explain(self, gid, item):
        reason = getattr(item, 'reason', '')
        detail = plain(item.detail) if item.detail else ''
        if reason and not (reason == 'unknown' and detail):
            return self.t('ui_reason_' + reason), self.t('ui_reason_%s_do' % reason)
        why = detail or self.t('ui_why_failed' if item.result == 'failed' else 'ui_why_needs_you')
        if item.result == 'failed':
            todo = self.t('ui_do_failed')
        elif gid == 'appstore':
            todo = self.t('ui_do_needs_appstore')
        elif gid == 'system':
            todo = self.t('ui_do_needs_system')
        else:
            todo = self.t('ui_do_needs_generic')
        return why, todo

    def log_display_lines(self, width):
        log = self.run_log
        if log is None:
            return []
        model = self.current_model()
        g = self.glyphs
        out = []
        # The engine can come back to a group after another one started (items of two groups interleave),
        # which leaves several blocks for one group. They share one header, in the position of the first.
        merged, blocks = {}, []
        for gid, lines in log.blocks:
            if gid is not None and gid in merged:
                merged[gid].extend(lines)
                continue
            block = [gid, list(lines)]
            blocks.append(block)
            if gid is not None:
                merged[gid] = block[1]
        for gid, lines in blocks:
            group = model.groups.get(gid) if model and gid else None
            if group is not None:
                glyph, style = status_glyph(self, group.state, group.result, self.tick_count)
                running = group.state == 'running'
                collapsed = group.state == 'done' and group.result == 'ok' and not self.log_expand_all
                marker = g['collapse'] if collapsed else g['expand']
                tail = duration(group.elapsed()) if group.started else ''
                header = '%s %s %s' % (marker, glyph, self.t('ui_group_' + gid))
                if running:
                    tail = self.t('ui_log_block_running') + ' ' + tail
                out.append((pad(header, max(0, width - text_width(tail) - 1)) + ' ' + tail, style if not running else 'accent'))
                if collapsed:
                    continue
                out.extend((line, 'base') for line in wrap_log(lines, width))
            else:
                out.extend((line, 'muted') for line in wrap_log(lines, width, ''))
        partial = log.visible_partial()
        if partial.strip():
            out.extend((line, 'base') for line in wrap_log([partial], width))
        return out

    # -- layout and drawing ----------------------------------------------------
    def help_shown(self, mode):
        if self.help_visible is not None:
            return self.help_visible
        return mode == 'wide' and self.settings.get('help_open')

    def layout(self, h, w):
        body = Rect(2, 0, h - 4, w)
        mode = 'wide' if w >= 120 and h >= 24 else ('medium' if w >= 80 and h >= 20 else 'narrow')
        ratio = SIDE_RATIO.get(self.screen.id, 0.4)
        help_rect = main = side = None
        show_help = self.help_shown(mode)
        if mode == 'wide':
            content = body
            if show_help:
                hw = max(32, min(36, w // 5))
                help_rect = Rect(body.y, w - hw, body.h, hw)
                content = Rect(body.y, 0, body.h, w - hw)
            target = MAIN_TARGET.get(self.screen.id)
            sw = (content.w - target) if target else int(content.w * ratio)
            if target and sw < 30:
                sw = int(content.w * ratio) if content.w - int(content.w * ratio) >= MIN_MAIN.get(self.screen.id, 40) else 0
            if sw >= 26 and content.w - sw >= MIN_MAIN.get(self.screen.id, 50):
                main = Rect(content.y, content.x, content.h, content.w - sw)
                side = Rect(content.y, content.x + content.w - sw, content.h, sw)
            else:
                main = content
        elif mode == 'medium':
            target = MAIN_TARGET.get(self.screen.id)
            sw = max(28, int(w * max(ratio, 0.38))) if ratio else 0
            if target and w - target >= 28:
                sw = w - target
            if sw and w - sw < MIN_MAIN.get(self.screen.id, 50):
                sw = 0
            main = Rect(body.y, 0, body.h, w - sw) if sw else body
            side = Rect(body.y, w - sw, body.h, sw) if sw else None
            if show_help:
                if side is None:
                    hw = max(28, w // 3)
                    main = Rect(body.y, 0, body.h, w - hw)
                    side = Rect(body.y, w - hw, body.h, hw)
                help_rect, side = side, None
        else:
            if body.h >= 16 and ratio and self.screen.id in ('dashboard', 'diagnostics'):
                mh = max(9, int(body.h * 0.6))
                if self.screen.id == 'dashboard':
                    mh = min(body.h - 5, max(mh, 13)) if self.run is not None else body.h
                main = Rect(body.y, 0, mh, w)
                side = Rect(body.y + mh, 0, body.h - mh, w) if body.h - mh >= 3 else None
            else:
                main = body
            if show_help:
                if side is None:
                    mh = max(6, body.h // 2)
                    main = Rect(body.y, 0, mh, w)
                    side = Rect(body.y + mh, 0, body.h - mh, w)
                help_rect, side = side, None
        return mode, main, side, help_rect

    def frame(self, h, w):
        self.rows, self.cols = h, w
        c = Canvas(h, w, self.glyphs)
        if h < MIN_ROWS or w < MIN_COLS:
            msg = self.t('ui_too_small', cols=MIN_COLS, rows=MIN_ROWS)
            for i, line in enumerate(wrap(msg, max(1, w - 2))[:h]):
                c.put(i, 1, line, 'warn')
            self.last_canvas = c
            return c
        mode, main, side, help_rect = self.layout(h, w)
        self.mode = mode
        zones = self.screen.zones(self)
        if self.zone not in zones and self.zone not in ('tabs', 'help'):
            self.zone = zones[0]
        if self.zone == 'help' and help_rect is None:
            self.zone = self.help_target if self.help_target in zones else zones[0]
        self.draw_header(c, w)
        self.draw_tabs(c, w)
        if main is not None:
            c.region(main.y, main.x, main.h, main.w, ('pane', zones[0]))
        if side is not None and len(zones) > 1:
            c.region(side.y, side.x, side.h, side.w, ('pane', zones[-1] if self.screen.id in ('dashboard', 'diagnostics') else zones[0]))
        if self.overlay is not None:
            self.draw_overlay(c, Rect(2, 0, h - 4, w))
        else:
            self.screen.render(self, c, main, side)
        if help_rect is not None and self.overlay is None:
            c.region(help_rect.y, help_rect.x, help_rect.h, help_rect.w, ('pane', 'help'))
            self.draw_help(c, help_rect)
        if self.dialog is not None:
            self.dialog.render(self, c)
        self.draw_status(c, h - 2, w)
        self.draw_keybar(c, h - 1, w)
        self.last_canvas = c
        return c

    def draw_header(self, c, w):
        g = self.glyphs
        c.fill(0, 0, 1, w, 'header')
        name = ' %s %s ' % (self.t('ui_app_name'), self.version)
        x = c.put(0, 0, ' ' + name.strip() + ' ', 'header_accent')
        # Right side: run state or last run.
        model = self.run
        if model is not None:
            pct = int(round(model.overall() * 100))
            state = '%s %s ' % (g['spinner'][self.tick_count % len(g['spinner'])] if self.animate else g['running'],
                                self.t('ui_run_in_progress', percent=pct))
            if model.dry_run:
                state = self.t('ui_preview_badge') + ' ' + state
            right_style = 'header_accent'
        elif self.last_model is not None and (self.last_run or not self.last_model.from_history):
            counts = self.last_model.counts()
            when = (self.t('ui_last_run_short', when=self.relative(self.last_run_time)) + ' ' + g['sep'] + ' ') \
                if self.last_run_time is not None else ''
            first = (g['up'], counts['available']) if self.last_model.dry_run else (g['ok'], counts['updated'])
            state = '%s%s%d %s%d %s%d ' % (when, first[0], first[1], g['needs'], counts['needs_you'],
                                           g['fail'], counts['failed'])
            right_style = 'header'
        else:
            state = self.t('ui_last_run_none') + ' '
            right_style = 'header'
        facts = [self.sysinfo.get('host', ''), 'macOS ' + self.sysinfo.get('macos', '?')]
        middle = ''
        for fact in facts:
            candidate = (middle + '  %s  ' % g['sep'] if middle else ' ') + fact
            if x + text_width(candidate) + text_width(state) + 2 <= w:
                middle = candidate
        c.put(0, x, middle, 'header')
        if x + text_width(middle) + text_width(state) + 1 <= w:
            c.put(0, w - text_width(state), state, right_style)

    def tab_labels(self, w):
        full = [' %d %s ' % (i + 1, self.t(s.tab)) for i, s in enumerate(self.screens)]
        if sum(text_width(l) + 1 for l in full) <= w:
            return full
        return [full[i] if i == self.screen_index else ' %d ' % (i + 1) for i in range(len(full))]

    def draw_tabs(self, c, w):
        x = 0
        focused = self.zone == 'tabs' and self.dialog is None
        for i, label in enumerate(self.tab_labels(w)):
            active = i == self.screen_index
            if active and focused:
                label = label.replace(' ', self.glyphs['marker'], 1) if self.glyphs['tl'] != '+' else '>' + label[1:]
            end = c.put(1, x, label, 'tab_active' if active else 'tab')
            c.region(1, x, 1, end - x, ('tab', i))
            x = end + 1
        if x < w:
            c.put(1, x, self.glyphs['h'] * (w - x), 'border')

    def zone_help(self, zone):
        if zone == 'tabs':
            return self.t('ui_help_tabs')
        if zone == 'help':
            return self.t('ui_help_help')
        if zone == 'overlay':
            return self.t('ui_help_log')
        return self.screen.help(self, zone)

    def draw_help(self, c, rect):
        """Stable help: a fixed "This screen" block, then the selected element,
        then the keys valid now (anchored at the bottom when there is room)."""
        focused = self.zone == 'help' and self.dialog is None
        c.box(rect, self.t('ui_pane_help'), focused)
        inner = rect.inner()
        if self.dialog is not None:
            text = self.t(getattr(self.dialog, 'help_key', 'ui_help_dialog'))
        else:
            target = self.zone if self.zone != 'help' else self.help_target
            text = self.zone_help(target)
        intro = [(l, 'accent') for l in wrap(self.t('ui_help_this_screen'), inner.w)]
        intro += [(l, 'base') for l in wrap(self.t('ui_intro_' + self.screen.id), inner.w)]
        selected = [(l, 'accent') for l in wrap(self.t('ui_help_selected'), inner.w)]
        selected += [(l, 'base') for l in wrap(text, inner.w)]
        keys = [(l, 'accent') for l in wrap(self.t('ui_help_keys_now'), inner.w)]
        ascii_only = self.glyphs['tl'] == '+'
        seen = set()
        for binding in self.active_bindings():
            if binding.label in seen or not binding.label:
                continue
            seen.add(binding.label)
            key = key_display(binding, ascii_only)
            kw = 8
            parts = wrap(self.t(binding.label), max(4, inner.w - kw))
            keys.append((pad(key, kw - 1) + ' ' + parts[0], 'keyline'))
            keys.extend((' ' * kw + p, 'base') for p in parts[1:])
        rows = {}
        if len(intro) + len(selected) + len(keys) + 2 <= inner.h:
            for i, line in enumerate(intro):
                rows[i] = line
            for i, line in enumerate(selected):
                rows[len(intro) + 1 + i] = line
            for i, line in enumerate(keys):
                rows[inner.h - len(keys) + i] = line
        else:
            flow = intro + [('', 'base')] + selected + [('', 'base')] + keys
            self.help_scroll = min(self.help_scroll, max(0, len(flow) - inner.h))
            for i, line in enumerate(flow[self.help_scroll:self.help_scroll + inner.h]):
                rows[i] = line
        for i, (line, style) in rows.items():
            if style == 'keyline':
                c.put(inner.y + i, inner.x, line[:7], 'accent', inner.w)
                c.put(inner.y + i, inner.x + 7, line[7:], 'base', inner.w - 7)
            else:
                c.put(inner.y + i, inner.x, line, style, inner.w)

    def draw_overlay(self, c, rect):
        if self.overlay == 'log':
            title = self.t('ui_pane_log')
            lines = self.log_display_lines(rect.w - 4) if self.run_log else []
            if self.job_kind == 'task' or (self.run_log is None and self.task_log):
                lines = [(l, 'base') for l in wrap_log(self.task_log.all_lines() if self.task_log else [], rect.w - 4, '')]
        else:
            title = self.overlay[1]
            lines = [(l, 'base') for l in wrap_log(self.overlay[2], rect.w - 4, '')]
        c.box(rect, title, self.dialog is None, right=self.t('ui_key_close') + ': Esc')
        inner = rect.inner()
        self.overlay_scroll = min(self.overlay_scroll, max(0, len(lines) - inner.h))
        end = len(lines) - self.overlay_scroll
        for i, (text, style) in enumerate(lines[max(0, end - inner.h):end]):
            c.put(inner.y + i, inner.x, clip(text, inner.w, self.glyphs['ellipsis']), style)

    def draw_status(self, c, y, w):
        text, style, when = self.notice
        g = self.glyphs
        if not text or time.monotonic() - when > NOTICE_SECONDS:
            text, style = '', 'status'
            if self.job is not None:
                log = self.current_log()
                started = self.job.started_at or time.monotonic()
                elapsed = duration(time.monotonic() - started)
                spinner = g['spinner'][self.tick_count % len(g['spinner'])] if self.animate else g['running']
                line = log.last_line() if log else ''
                if self.prompt_hidden:
                    text, style = self.t('ui_prompt_waiting'), 'status_warn'
                elif self.sudo_notice_active():
                    text, style = self.t('ui_auth_notice'), 'status'
                elif line:
                    text = spinner + ' ' + self.t('ui_waiting_events', elapsed=elapsed, line=plain(line)[:200])
                else:
                    text = spinner + ' ' + self.t('ui_working', elapsed=elapsed)
        c.fill(y, 0, 1, w, 'status')
        c.put(y, 1, clip(text, w - 2, g['ellipsis']), style)

    def active_bindings(self):
        """Bindings valid right now, in key-bar priority order."""
        if self.dialog is not None:
            return self.dialog.bindings()
        if self.overlay is not None:
            return [Binding(('up', 'down'), 'ui_key_scroll', 'vmove'), Binding(('esc', 'l', 'L'), 'ui_key_close', 'close',
                                                                                  display='Esc'),
                    Binding(('pgup', 'pgdn'), 'ui_key_scroll', 'page', show=False)]
        if self.zone == 'tabs':
            local = [Binding(('left', 'right'), 'ui_key_switch_tab', 'hmove'), Binding(('enter', 'down'), 'ui_key_open', 'enter')]
        elif self.zone == 'help':
            local = [Binding(('up', 'down'), 'ui_key_scroll', 'vmove')]
        else:
            local = self.screen.bindings(self, self.zone)
        typing = self.typing()
        local = list(local)
        out = local[:2] + [Binding(('tab', 'btab'), 'ui_key_next_pane', 'tab', display='Tab'),
                           Binding(('esc',), 'ui_key_back', 'esc')] + local[2:]
        if not typing:
            out += [Binding(tuple(str(i + 1) for i in range(len(self.screens))), 'ui_key_screens', 'digit',
                            display='1-%d' % len(self.screens)),
                    Binding(('?', 'f1'), 'ui_key_help', 'help', display='?'),
                    Binding(('l', 'L'), 'ui_key_log', 'log', display='L'),
                    Binding(('q', 'ctrl-c'), 'ui_key_quit', 'quit', display='q')]
        return out

    def typing(self):
        return self.zone == 'search' and self.dialog is None and self.overlay is None

    def draw_keybar(self, c, y, w):
        c.fill(y, 0, 1, w, 'keybar')
        ascii_only = self.glyphs['tl'] == '+'
        x = 1
        for key, label, action in keybar_items(self.active_bindings(), self.t, w - 2, ascii_only):
            start = x
            x = c.put(y, x, key, 'keybar_key')
            x = c.put(y, x + 1, label, 'keybar')
            c.region(y, start, 1, x - start, ('keybar', key))
            x += 3

    # -- input -------------------------------------------------------------------
    def key(self, raw):
        name = key_name(raw) if not isinstance(raw, str) or len(raw) == 1 else raw
        return self.key_name(name)

    def key_name(self, name):
        if name in ('resize', 'mouse', 'unknown') and name != 'unknown':
            return True
        if self.dialog is not None:
            dialog = self.dialog
            if dialog.key(self, name):
                return True
            if name == 'ctrl-c':
                self.ask_quit()
                return True
            return self.unknown()
        if self.overlay is not None:
            return self.overlay_key(name)
        if self.typing() and (len(name) == 1 or name == 'space'):
            if self.screen.text(self, self.zone, ' ' if name == 'space' else name):
                return True
        if self.zone == 'tabs':
            if name in ('left', 'right'):
                self.switch((self.screen_index + (1 if name == 'right' else -1)) % len(self.screens))
                self.zone = 'tabs'
                return True
            if name in ('enter', 'down', 'space'):
                self.focus_zone(self.screen.zones(self)[0])
                return True
        elif self.zone == 'help':
            if name in ('up', 'down', 'pgup', 'pgdn'):
                self.help_scroll = max(0, self.help_scroll + {'up': -1, 'down': 1, 'pgup': -8, 'pgdn': 8}[name])
                return True
        else:
            binding = lookup(self.screen.bindings(self, self.zone), name)
            if binding is not None:
                action = name if binding.action in GENERIC else binding.action
                if self.screen.action(self, self.zone, action):
                    return True
            elif name in ('up', 'down', 'left', 'right') and self.screen.action(self, self.zone, name):
                return True
        return self.global_key(name)

    def overlay_key(self, name):
        if name in ('esc', 'l', 'L', 'q', 'enter'):
            self.overlay = None
            return True
        step = {'up': 1, 'down': -1, 'pgup': 15, 'pgdn': -15, 'home': 10 ** 6, 'end': -10 ** 6}.get(name)
        if step is not None:
            self.overlay_scroll = max(0, self.overlay_scroll + step)
            return True
        if name == 'ctrl-c':
            self.ask_quit()
            return True
        return self.unknown()

    def zone_cycle(self):
        zones = list(self.screen.zones(self))
        mode, main, side, help_rect = self.layout(self.rows, self.cols)
        if help_rect is not None:
            zones.append('help')
        zones.append('tabs')
        return zones

    def global_key(self, name):
        typing = self.typing()
        if name in ('tab', 'btab'):
            zones = self.zone_cycle()
            current = zones.index(self.zone) if self.zone in zones else 0
            target = zones[(current + (1 if name == 'tab' else -1)) % len(zones)]
            self.focus_zone(target)
            return True
        if name == 'esc':
            return self.back()
        if not typing:
            if name.isdigit() and len(name) == 1 and 1 <= int(name) <= len(self.screens):
                self.switch(int(name) - 1)
                return True
            if name in ('?', 'f1'):
                mode = getattr(self, 'mode', 'wide')
                if mode == 'wide' and self.help_shown(mode):
                    if self.zone == 'help':
                        self.help_visible = False
                        self.focus_zone(self.help_target)
                    else:
                        self.focus_zone('help')
                else:
                    self.help_visible = not self.help_shown(mode)
                return True
            if name in ('l', 'L'):
                self.toggle_full_log()
                return True
            if name in ('q', 'ctrl-c', 'f10'):
                self.ask_quit()
                return True
        if name == 'ctrl-c':
            self.ask_quit()
            return True
        if name == 'ctrl-l':
            return True
        return self.unknown()

    def back(self):
        screen = self.screen
        zones = screen.zones(self)
        if self.zone == 'search' and getattr(screen, 'query', ''):
            screen.query = ''
            return True
        if self.zone not in (zones[0],):
            self.focus_zone(zones[0])
            return True
        if self.screen_index != 0:
            self.switch(0)
            return True
        if screen.result_mode(self):
            screen.press(self, 'done')
            return True
        if self.zone != 'actions':
            self.focus_zone('actions')
            return True
        self.notify(self.t('ui_nothing_back'), 'status')
        return True

    def unknown(self):
        ascii_only = self.glyphs['tl'] == '+'
        keys = []
        for binding in self.active_bindings():
            if binding.show:
                keys.append(key_display(binding, ascii_only))
            if len(keys) >= 5:
                break
        self.notify(self.t('ui_unknown_key', keys='  '.join(keys)), 'status_warn')
        return False

    def mouse(self, y, x, kind):
        """kind: 'click' | 'double' | 'wheel_up' | 'wheel_down'."""
        canvas = self.last_canvas
        if canvas is None or not self.settings.get('mouse'):
            return False
        payload = canvas.hit(y, x)
        if kind in ('wheel_up', 'wheel_down'):
            delta = -3 if kind == 'wheel_up' else 3
            if self.dialog is not None:
                self.dialog.key(self, 'up' if delta < 0 else 'down')
                return True
            if self.overlay is not None:
                self.overlay_scroll = max(0, self.overlay_scroll - delta)
                return True
            zone = payload[1] if payload and payload[0] == 'pane' else self.zone
            if zone == 'help':
                self.help_scroll = max(0, self.help_scroll + delta)
                return True
            return self.screen.scroll(self, zone if zone in self.screen.zones(self) else self.zone, delta)
        if payload is None:
            return False
        if self.dialog is not None:
            if payload[0] == 'dialog' and payload[1] is not None:
                self.dialog.click(self, payload[1])
            return True
        what = payload[0]
        if what == 'tab':
            self.switch(payload[1])
            return True
        if what == 'keybar':
            name = {'↑↓': 'down', 'Up/Dn': 'down', '←→': 'right', 'Lt/Rt': 'right', 'Enter': 'enter', 'Tab': 'tab',
                    'Esc': 'esc', 'Space': 'space', '?': '?', 'L': 'l', 'q': 'q', 'abc': None}.get(payload[1], payload[1])
            if name and name.startswith('1-'):
                name = None
            return self.key_name(name) if name else True
        if what == 'pane':
            if payload[1] in self.screen.zones(self) or payload[1] == 'help':
                self.focus_zone(payload[1])
            return True
        return self.screen.click(self, payload, double=kind == 'double')


LEGACY = {'npm': 'cli', 'npmcli': 'cli', 'postupdate': 'inventory'}


def parse_time(text):
    import datetime
    try:
        value = datetime.datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    except ValueError:
        return None
    return value.timestamp()


def system_info():
    try:
        host = os.uname().nodename.split('.')[0]
    except Exception:
        host = ''
    return dict(host=plain(host)[:40], macos=plain(platform.mac_ver()[0] or '?')[:16])


# -- curses loop -------------------------------------------------------------
_WHEEL_DOWN = getattr(curses, 'BUTTON5_PRESSED', 0) or 0x200000


def _blit(screen, canvas, theme):
    for y in range(canvas.h):
        x = 0
        row, styles, surfaces = canvas.cells[y], canvas.styles[y], canvas.surfaces[y]
        while x < canvas.w:
            style, surface = styles[x], surfaces[x]
            end = x + 1
            while end < canvas.w and styles[end] == style and surfaces[end] == surface:
                end += 1
            text = ''.join(row[x:end])
            try:
                screen.addstr(y, x, text, theme.attr(style, surface))
            except curses.error:
                pass   # writing the bottom-right cell raises after drawing
            x = end


def _mouse_kind(bstate):
    if bstate & curses.BUTTON4_PRESSED:
        return 'wheel_up'
    if bstate & _WHEEL_DOWN or bstate & 0x8000000:
        return 'wheel_down'
    if bstate & getattr(curses, 'BUTTON1_DOUBLE_CLICKED', 0):
        return 'double'
    if bstate & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED | curses.BUTTON1_RELEASED):
        return 'click'
    return None


def main_loop(screen, app):
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    curses.raw()
    screen.keypad(True)
    screen.timeout(100)
    theme = None
    last_click = (0.0, None)
    last_draw = 0.0
    dirty = True
    while not app.should_exit:
        if app.theme_dirty:
            theme = Theme(app.theme_name(), app.settings.get('accent'), color_disabled(app.environ)).setup(curses)
            try:
                screen.bkgd(' ', theme.attr('base'))
            except curses.error:
                pass
            if app.settings.get('mouse'):
                curses.mousemask(curses.ALL_MOUSE_EVENTS)
                curses.mouseinterval(0)
            else:
                curses.mousemask(0)
            app.theme_dirty = False
            dirty = True
        app.tick()
        now = time.monotonic()
        if dirty or now - last_draw > (0.15 if app.job else 1.0):
            h, w = screen.getmaxyx()
            canvas = app.frame(h, w)
            screen.erase()
            _blit(screen, canvas, theme)
            screen.refresh()
            last_draw = now
            dirty = False
        try:
            key = screen.get_wch()
        except curses.error:
            continue
        keys = [key]
        screen.timeout(0)
        for _ in range(64):
            try:
                keys.append(screen.get_wch())
            except curses.error:
                break
        screen.timeout(100)
        for key in keys:
            dirty = True
            if key == curses.KEY_RESIZE:
                try:
                    curses.update_lines_cols()
                except AttributeError:
                    pass
                h, w = screen.getmaxyx()
                if app.job is not None:
                    try:
                        app.job.resize(max(10, h - 6), max(40, w // 2))
                    except (OSError, ValueError):
                        pass
                continue
            if key == curses.KEY_MOUSE:
                try:
                    _, mx, my, _, bstate = curses.getmouse()
                except curses.error:
                    continue
                kind = _mouse_kind(bstate)
                if kind == 'click':
                    t0, where = last_click
                    hit = app.last_canvas.hit(my, mx) if app.last_canvas else None
                    if where == hit and hit is not None and time.monotonic() - t0 < 0.4:
                        kind = 'double'
                    last_click = (time.monotonic(), hit)
                if kind:
                    app.mouse(my, mx, kind)
                continue
            app.key(key)
    return 0


def parse_launch_args(argv):
    dry, skip, unknown = False, [], []
    for arg in argv:
        if arg == '--dry-run':
            dry = True
        elif arg.startswith('--skip-') and len(arg) > 7:
            skip.append(arg[7:])
        elif arg in ('--tui', ''):
            continue
        else:
            unknown.append(arg)
    return dry, skip, unknown


FIT_COLS, FIT_ROWS = 120, 36


def fit_window(out=None, size=None, wait=0.2):
    """Ask an xterm-compatible terminal for at least FIT_COLS x FIT_ROWS
    (CSI 8 ; rows ; cols t). Returns (original, requested) when a resize was
    requested, None when the window is already big enough or not a terminal.
    The caller restores the original size on exit only if the window still has
    the requested size (a manual resize during the session is never undone)."""
    import shutil
    import time
    out = out or sys.stdout
    try:
        if not out.isatty():
            return None
        cols, rows = size or shutil.get_terminal_size((0, 0))
    except (OSError, ValueError):
        return None
    if not cols or not rows or (cols >= FIT_COLS and rows >= FIT_ROWS):
        return None
    want = (max(cols, FIT_COLS), max(rows, FIT_ROWS))
    out.write('\x1b[8;%d;%dt' % (want[1], want[0]))
    out.flush()
    time.sleep(wait)
    return (cols, rows), want


def restore_window(fitted, out=None, size=None):
    import shutil
    if not fitted:
        return
    out = out or sys.stdout
    (cols, rows), want = fitted
    try:
        now = size or tuple(shutil.get_terminal_size((0, 0)))
        if tuple(now) == tuple(want):
            out.write('\x1b[8;%d;%dt' % (rows, cols))
            out.flush()
    except (OSError, ValueError):
        pass


def run(repo, initial_view='home', *argv):
    dry, skip, unknown = parse_launch_args(argv)
    os.environ.setdefault('ESCDELAY', '25')
    from tui_requirements import read_requirements
    app = App(repo, initial_view, launch_dry_run=dry, launch_skip=skip, requirements_reader=None)
    app.requirements_reader = lambda: read_requirements(app.repo, app.lang)
    result = 0
    fitted = None
    if app.settings.get('auto_resize'):
        fitted = fit_window()
        if fitted:
            import shutil
            cols, rows = shutil.get_terminal_size((0, 0))
            if cols < FIT_COLS or rows < FIT_ROWS:      # the terminal ignored the request
                fitted = None
                app.notify(app.t('ui_resize_hint', cols=FIT_COLS, rows=FIT_ROWS), 'status_warn')
    if not color_disabled(app.environ):
        app.terminal_bg = detect_background(app.environ)        # OSC 11 query, before curses owns the terminal
    try:
        result = curses.wrapper(main_loop, app)
    except (Exception, KeyboardInterrupt) as exc:
        if app.job is not None and app.job.running:
            from tui_recovery import handoff
            return handoff(app.job, app.t('ui_recovery'))
        print(app.t('ui_error', message=plain(exc)), file=sys.stderr)
        restore_window(fitted)
        return 2
    restore_window(fitted)
    if app.exit_mode == 'detach' and app.job is not None and app.job.running:
        from tui_recovery import handoff
        return handoff(app.job, app.t('ui_recovery'))
    if app.pending_toolkit_receipt is not None:
        from tui_toolkit import finish_update
        return finish_update(repo, app.pending_toolkit_receipt, app.lang)
    return result


# Older callers import the workspace class under its previous name.
Workspace = App
