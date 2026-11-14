"""Visible controls and saved inventory remain separate from update authority."""

import copy
import curses
import json
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import terminal_app as app
from tui_backend import ACTIONS, DEFAULT_SETTINGS, GROUPS
from test_terminal_app import MemoryJob


class UsabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name).resolve()
        (self.repo / "VERSION").write_text("1.8.1\n")
        for spec in ACTIONS.values():
            script = self.repo / spec["script"]
            script.parent.mkdir(parents=True, exist_ok=True)
            script.write_text("# Fixture only; never execute.\n")
        MemoryJob.instances = []
        worker = patch.object(app, "TerminalJob", MemoryJob)
        worker.start()
        self.addCleanup(worker.stop)

    def workspace(self, view="home"):
        settings = copy.deepcopy(DEFAULT_SETTINGS)
        settings.update(wizard_complete=True, auto_resize=False, language="en")
        return app.Workspace(self.repo, view, settings)

    def attach(self, workspace, secret=False):
        job = MemoryJob(self.repo, "preview", GROUPS, workspace.settings)
        job.start()
        job.secret_input = secret
        workspace.job, workspace.job_action = job, "preview"
        return job

    def test_fast_navigation_and_answer_enter_are_not_mistaken_for_paste(self):
        workspace = self.workspace()
        workspace.feed_keys(["s", "\t"])
        self.assertEqual(workspace.view, "settings")
        self.assertNotEqual(workspace.focus, 0)
        job = self.attach(workspace)
        workspace.key("i")
        workspace.feed_keys(["1", ",", "3", "\n"])
        self.assertEqual(job.answers, ["1,3\n"])

    def test_prompt_event_and_secret_mode_open_answer_editor_without_shortcut(self):
        workspace = self.workspace()
        job = self.attach(workspace)
        job.chunks = ["@@MAC_UPDATE_PROMPT consent\nReview only this scope.\nChoose entries:\n"]
        workspace.tick()
        self.assertEqual(workspace.modal, "input")
        workspace.buffer = "1"
        workspace.tick()
        self.assertEqual(workspace.buffer, "1")
        workspace.key("\x1b")
        job.secret_input = True
        workspace.tick()
        self.assertEqual(workspace.modal, "input")
        self.assertTrue(workspace.input_secret)
        self.assertEqual(job.answers, [])

    def test_visible_footer_run_defaults_to_cancel_and_space_does_not_press_it(self):
        workspace = self.workspace("updates")
        workspace.focus = 3
        workspace.footer_selected = workspace.footer_buttons().index("run")
        workspace.key(" ")
        self.assertIsNone(workspace.modal)
        workspace.key("\n")
        self.assertEqual(workspace.modal, "confirm")
        workspace.key("\n")
        self.assertIsNone(workspace.job)
        workspace.request_action("update")
        workspace.key(curses.KEY_RIGHT)
        workspace.key("\n")
        self.assertTrue(workspace.job.running)

    def test_bracketed_paste_cannot_press_buttons_or_send_an_answer(self):
        workspace = self.workspace("updates")
        workspace.feed_keys(list("\x1b[200~ry\n\x1b[201~"))
        self.assertIsNone(workspace.job)
        job = self.attach(workspace)
        workspace.key("i")
        workspace.feed_keys(list("\x1b[200~yes\n\x1b[201~"))
        self.assertEqual(workspace.buffer, "yes ")
        self.assertEqual(job.answers, [])

    def test_single_batch_cannot_open_and_confirm_a_mutating_operation(self):
        workspace = self.workspace("updates")
        workspace.focus = 3
        workspace.footer_selected = workspace.footer_buttons().index("run")
        workspace.feed_keys(["\n", "y"])
        self.assertIsNone(workspace.job)

    def test_inventory_changes_are_staged_and_save_does_not_start_an_update(self):
        model = {"plan": None, "snapshot_id": "snapshot", "generation": 1, "rows": [
            dict(id="a", name="Alpha", version="1.2", source="homebrew", status="enabled",
                 reasons=["consent_required"], path="/fixture/Alpha.app", enabled=True, kind="app")
        ]}
        stored = copy.deepcopy(model)

        def save(model_arg, changes, state_dir=None):
            for row in stored["rows"]:
                if row["id"] in changes:
                    row.update(enabled=changes[row["id"]], status="enabled" if changes[row["id"]] else "excluded")

        with patch.object(app, "load_inventory", side_effect=lambda *args, **kwargs: copy.deepcopy(stored), create=True), \
             patch.object(app, "save_selection", side_effect=save, create=True):
            workspace = self.workspace()
            workspace.change_view("inventory")
            workspace.focus = 1
            workspace.selected = workspace.items().index(("target", "a"))
            workspace.key(" ")
            self.assertTrue(stored["rows"][0]["enabled"])
            self.assertEqual(workspace.inventory_changes, {"a": False})
            workspace.request_action("update")
            self.assertIsNone(workspace.job)
            workspace.focus = 3
            workspace.footer_selected = workspace.footer_buttons().index("save_inventory")
            workspace.key("\n")
            self.assertFalse(stored["rows"][0]["enabled"])
            self.assertEqual(workspace.inventory_changes, {})
            self.assertIsNone(workspace.job)

    def test_inventory_search_source_filter_and_natural_version_order_use_real_rows(self):
        rows = [dict(id="a", name="Zulu", version="1.2", source="homebrew", status="enabled", enabled=True, reasons=[], path="/fixture/A.app", kind="app"),
                dict(id="b", name="Alpha", version="1.10", source="homebrew", status="excluded", enabled=False, reasons=[], path="/fixture/B.app", kind="app"),
                dict(id="c", name="Other", version="2", source="unknown", status="manual", enabled=True, reasons=[], path="/fixture/C.app", kind="app")]
        with patch.object(app, "load_inventory", return_value={"rows": rows, "plan": None}, create=True):
            workspace = self.workspace()
            workspace.change_view("inventory")
            workspace.inventory_sort = "version"
            workspace.inventory_source = "homebrew"
            self.assertEqual([r["id"] for r in workspace.visible_inventory_rows()], ["a", "b"])
            workspace.inventory_query = "alpha"
            self.assertEqual([r["id"] for r in workspace.visible_inventory_rows()], ["b"])

    def target(self, identity="a", **values):
        row = dict(id=identity, target={"kind": "app", "id": "fixture.app"},
                   identity_fingerprint="identity", source_fingerprint="source",
                   name="Fixture application", version="1.2", source="homebrew",
                   status="enabled", reasons=["consent_required"], enabled=True)
        row.update(values)
        return row

    def test_candidate_table_survives_preview_and_matches_runtime_by_both_fingerprints(self):
        workspace = self.workspace()
        row = self.target()
        job = self.attach(workspace)
        payload = "@@MAC_UPDATE_CANDIDATES_BEGIN\n@@MAC_UPDATE_CANDIDATE " + json.dumps(row) + "\n@@MAC_UPDATE_CANDIDATES_END\n"
        job.chunks = [payload[:65], payload[65:]]
        workspace.tick()
        job.running, job.returncode = False, 0
        workspace.tick()
        self.assertEqual(workspace.view, "updates")
        self.assertEqual(workspace.preview_rows, [row])
        self.assertFalse(any("@@MAC_UPDATE" in line for line in workspace.log))
        job.running, job.returncode = True, None
        workspace.job_action = "update"
        event = self.target("different-action-id", status="running")
        job.chunks = ["@@MAC_UPDATE_TARGET " + json.dumps(event) + "\n"]
        with patch.object(app.time, "monotonic", return_value=100):
            workspace.tick()
        with patch.object(app.time, "monotonic", return_value=107):
            bar, elapsed = workspace.row_activity(row)
        self.assertNotIn("100%", bar)
        self.assertEqual(elapsed, "0:07")
        self.assertEqual(workspace.row_status(row), "running")
        self.assertNotEqual(workspace.row_status(self.target(source_fingerprint="other")), "running")
        event.update(status="updated", verified=False)
        job.chunks = ["@@MAC_UPDATE_TARGET " + json.dumps(event) + "\n"]
        workspace.tick()
        self.assertNotIn("100%", workspace.row_activity(row)[0])
        self.assertEqual(workspace.row_status(row), "warnings")
        event["verified"] = True
        job.chunks = ["@@MAC_UPDATE_TARGET " + json.dumps(event) + "\n"]
        workspace.tick()
        self.assertIn("100%", workspace.row_activity(row)[0])
        frame = "\n".join(workspace.frame(38, 140).lines())
        self.assertIn("Fixture application", frame)
        self.assertIn("100%", frame)

    def test_malformed_target_events_cannot_break_table_or_rename_a_saved_selection(self):
        workspace = self.workspace()
        self.assertIsNone(workspace.target_key(self.target(target={"kind": "app", "id": ["unexpected"]})))
        self.assertIsNone(workspace.target_key(self.target(target={"kind": {}, "id": "fixture"})))
        workspace.view = "updates"
        workspace.inventory_model = {"rows": [self.target("saved-id")]}
        workspace.preview_rows = [self.target("preview-id")]
        self.assertEqual(workspace.selection_id(workspace.preview_rows[0]), "saved-id")
        workspace.preview_rows[0]["identity_fingerprint"] = "different"
        self.assertIsNone(workspace.selection_id(workspace.preview_rows[0]))

    def test_enriched_preview_can_exclude_same_installation_without_weakening_enable_matching(self):
        workspace = self.workspace()
        workspace.view = 'updates'
        raw = self.target('saved-id', path='/fixture/Alpha.app')
        enriched = dict(raw, id='preview-id', source_fingerprint='new-source-evidence')
        workspace.inventory_model = {'rows':[raw]}
        workspace.preview_rows = [enriched]
        workspace.focus = 1
        workspace.selected = workspace.items().index(('target','preview-id'))
        self.assertIsNone(workspace.selection_id(enriched))
        workspace.key(' ')
        self.assertEqual(workspace.inventory_changes, {'saved-id':False})
        self.assertFalse(workspace.row_enabled(enriched))
        workspace.key(' ')
        self.assertEqual(workspace.inventory_changes, {})
        workspace.preview_rows[0]['path'] = '/fixture/Other.app'
        workspace.key(' ')
        self.assertEqual(workspace.inventory_changes, {})

    def test_running_without_terminal_result_becomes_unknown_when_child_exits(self):
        workspace = self.workspace()
        row = self.target()
        workspace.preview_rows = [row]
        job = self.attach(workspace)
        workspace.job_action = "update"
        job.chunks = ["@@MAC_UPDATE_TARGET " + json.dumps(self.target(status="running")) + "\n"]
        workspace.tick()
        job.running, job.returncode = False, 0
        workspace.tick()
        self.assertEqual(workspace.row_status(row), "unknown")
        self.assertNotIn("100%", workspace.row_activity(row)[0])

    def test_all_language_footers_and_candidate_states_remain_visible(self):
        workspace = self.workspace()
        workspace.preview_rows = [self.target()]
        for language in app.LANGUAGES:
            workspace.settings['language'] = language
            for view in ('updates', 'inventory', 'about'):
                workspace.view = view
                for width in (80, 140):
                    frame = workspace.frame(38, width)
                    footer = "\n".join(frame.lines()[-4:])
                    self.assertIn(workspace.t('exit_button'), footer, (language, view, width, footer))
                    self.assertIn(workspace.t('help_button'), footer, (language, view, width, footer))
                    self.assertEqual(footer.count(workspace.t('controls_hint')[:30]), 1)
        workspace.settings['language'] = 'pl'
        workspace.view = 'updates'
        rendered = "\n".join(workspace.frame(38, 140).lines())
        self.assertIn(workspace.t('inventory_status_enabled'), rendered)
        self.assertIn(workspace.t('nav_wizard'), rendered)
        self.assertNotIn('[ [x]', rendered)

    def test_toolkit_apply_runs_only_after_curses_window_and_paste_cleanup(self):
        workspace = self.workspace('about')
        workspace.pending_toolkit_receipt = {'fixture': True}
        events = []

        class Display(io.StringIO):
            def isatty(self):
                return True

        class Window:
            def __init__(self, *args):
                pass
            def __enter__(self):
                events.append('window-enter')
            def __exit__(self, *args):
                events.append('window-exit')

        output = Display()
        def wrapper(main):
            events.append('curses-restored')
            return 0
        def finish(repo, receipt, language):
            self.assertEqual(events, ['window-enter', 'curses-restored', 'window-exit'])
            self.assertTrue(output.getvalue().endswith('\x1b[?2004l'))
            self.assertEqual(receipt, {'fixture': True})
            self.assertIsNone(workspace.job)
            return 10
        with patch.object(app, 'Workspace', return_value=workspace), \
             patch.object(app, 'TerminalWindow', Window), \
             patch.object(app.curses, 'wrapper', side_effect=wrapper), \
             patch.object(app.sys, 'stdin', Display()), patch.object(app.sys, 'stdout', output), \
             patch.dict(os.environ, {'TERM': 'xterm-256color'}), \
             patch('tui_toolkit.finish_update', side_effect=finish):
            self.assertEqual(app.run(self.repo), 10)

    def test_native_recovery_is_visible_fixed_command_and_requires_confirmation(self):
        workspace = self.workspace('diagnostics')
        self.assertIn(('action', 'native_recovery'), workspace.items())
        workspace.selected = workspace.items().index(('action', 'native_recovery'))
        workspace.focus = 1
        workspace.key('\n')
        self.assertEqual(workspace.modal, 'confirm')
        self.assertIsNone(workspace.job)
        workspace.key('\n')
        self.assertIsNone(workspace.job)
        self.assertIn('reconcile_native.sh', ' '.join(app.build_command(self.repo, 'native_recovery', GROUPS, workspace.settings)))

    def test_about_explains_blocked_feature_branch_without_internal_reason_code(self):
        from toolkit_update import toolkit_reason_label
        workspace = self.workspace('about')
        workspace.toolkit_report = {'status': 'blocked', 'reasons': ['branch_not_main']}
        text = "\n".join(workspace.frame(38, 140).lines())
        self.assertIn(toolkit_reason_label('branch_not_main', 'en'), text)
        self.assertNotIn('branch_not_main', text)
        self.assertTrue(workspace.button_disabled('toolkit_apply'))

    def test_table_actions_are_visible_and_route_explicitly_even_with_empty_inventory(self):
        for view in ('inventory', 'updates'):
            workspace = self.workspace()
            workspace.view = view
            workspace.inventory_model = {'rows': [], 'plan': None}
            actions = [item for item in workspace.items() if item[0] == 'action']
            self.assertTrue(actions)
            for language in app.LANGUAGES:
                workspace.settings['language'] = language
                for size in ((24, 80), (38, 140)):
                    for item in actions:
                        workspace.selected = workspace.items().index(item)
                        frame = workspace.frame(*size)
                        left, right = app.panel_sizes(size[1])
                        center = ' '.join(' '.join(line[left+2:size[1]-right-2].strip().lstrip('> ') for line in frame.lines()[3:-6]).split())
                        self.assertIn('[ ' + workspace.item_label(item) + ' ]', center, (language, view, size))
            for item in actions:
                workspace.selected = workspace.items().index(item)
                workspace.focus = 1
                with patch.object(workspace, 'request_action') as request:
                    workspace.key('\n')
                    request.assert_called_once_with(item[1])
            job = self.attach(workspace)
            workspace.selected = workspace.items().index(actions[0])
            workspace.key('\n')
            self.assertIs(workspace.job, job)
            self.assertEqual(workspace.notice, workspace.t('busy'))

    def test_unconfirmed_native_and_unknown_outcomes_cannot_fall_back_to_included(self):
        workspace = self.workspace()
        row = self.target()
        for outcome, expected in (('triggered_unconfirmed', 'warnings'), ('future_outcome', 'unknown')):
            workspace.target_states[workspace.target_key(row)] = dict(row, status=outcome, verified=False)
            self.assertEqual(workspace.row_status(row), expected)
            self.assertNotIn('100%', workspace.row_activity(row)[0])
        workspace.target_states[workspace.target_key(row)]['status'] = 'triggered_unconfirmed'
        self.assertIn(workspace.t('action_native_recovery'), workspace.row_reason(row))
        workspace.target_states.clear()
        row['reasons'] = ['pending_updater_session']
        self.assertIn(workspace.t('action_native_recovery'), workspace.row_reason(row))

    def test_internet_mode_control_requests_batch_without_granting_or_launching(self):
        workspace = self.workspace('updates')
        self.assertEqual(workspace.settings['internet_mode'], 'automatic')
        mode = ('control', 'internet_mode')
        self.assertIn(mode, workspace.items())
        workspace.focus = 1
        workspace.selected = workspace.items().index(mode)
        with patch.object(app, 'save_settings') as save:
            workspace.key('\n')
            self.assertEqual(workspace.settings['internet_mode'], 'per_app')
            self.assertIsNone(workspace.job)
            save.assert_not_called()
            workspace.key('\n')
            self.assertEqual(workspace.settings['internet_mode'], 'automatic')
            workspace.request_action('update')
            self.assertEqual(workspace.modal, 'confirm')
            self.assertEqual(workspace.modal_selected, 0)
            self.assertIsNone(workspace.job)
            self.assertIn(workspace.t('internet_batch_hint').split('.')[0], '\n'.join(workspace.frame(38, 140).lines()))
            workspace.key('\n')
            self.assertIsNone(workspace.job)
            save.assert_not_called()
        job = self.attach(workspace)
        workspace.modal = None
        workspace.selected = workspace.items().index(mode)
        workspace.key('\n')
        self.assertEqual(workspace.settings['internet_mode'], 'automatic')
        self.assertIs(workspace.job, job)
        self.assertEqual(workspace.notice, workspace.t('busy'))
        job.chunks = ['@@MAC_UPDATE_PROMPT native_batch\nType AUTO for the exact displayed scope.\n']
        workspace.tick()
        self.assertEqual(workspace.modal, 'input')
        workspace.feed_keys(list('\x1b[200~AUTO\n\x1b[201~'))
        self.assertEqual(job.answers, [])
        self.assertEqual(workspace.buffer, 'AUTO ')

    def test_observed_version_change_keeps_native_completion_unconfirmed(self):
        workspace = self.workspace()
        row = self.target(version='1.2')
        workspace.preview_rows = [row]
        workspace.view = 'updates'
        workspace.target_states[workspace.target_key(row)] = dict(row, status='triggered_unconfirmed', verified=False, after='1.3')
        workspace.selected = workspace.items().index(('target', row['id']))
        self.assertEqual(workspace.row_version(row), '1.3')
        self.assertIn('1.2 -> 1.3', workspace.row_version(row, detail=True))
        self.assertEqual(workspace.row_status(row), 'warnings')
        self.assertNotIn('100%', workspace.row_activity(row)[0])
        text = '\n'.join(workspace.frame(38, 140).lines())
        self.assertIn(workspace.t('native_pending'), text)
        self.assertIn(workspace.t('native_pending_detail').split('.')[0], workspace.row_reason(row))
        self.assertIn('1.2 -> 1.3', '\n'.join(workspace.details()))
        for outcome in ('observed_version_changed', 'legacy_handler_completed_unconfirmed'):
            workspace.target_states[workspace.target_key(row)]['status'] = outcome
            self.assertEqual(workspace.row_status(row), 'warnings')
            self.assertNotIn('100%', workspace.row_activity(row)[0])
        job = self.attach(workspace)
        workspace.job_action = 'update'
        workspace.target_states[workspace.target_key(row)]['status'] = 'vendor_updater_observing'
        self.assertEqual(workspace.row_status(row), 'running')
        job.running = False
        self.assertEqual(workspace.row_status(row), 'warnings')

    def test_owner_manual_choice_and_unsupported_method_have_distinct_explanations(self):
        workspace = self.workspace()
        manual = self.target(status='manual', reasons=['deepseek_manual_only'])
        unsupported = self.target(status='blocked', reasons=['unsupported_automatic_method'])
        self.assertEqual(workspace.row_reason(manual), workspace.t('inventory_reason_owner_manual'))
        self.assertEqual(workspace.row_reason(unsupported), workspace.t('inventory_reason_unsupported'))

    def test_context_help_and_status_are_visible_on_every_screen_at_all_widths(self):
        workspace = self.workspace()
        for width in (80, 100, 119, 120, 140):
            for view in app.VIEWS:
                workspace.view = view
                frame = workspace.frame(30, width)
                right = '\n'.join(line[-app.panel_sizes(width)[1]:] for line in frame.lines())
                self.assertIn('Help', right, (view,width,right))
                self.assertIn(workspace.t('idle'), right, (view,width,right))
                self.assertIn('Enter', right, (view,width,right))
        workspace.view = 'updates'
        job = self.attach(workspace)
        workspace.job_action = 'preview'
        workspace.open_input()
        right = '\n'.join(line[-26:] for line in workspace.frame(38,100).lines())
        self.assertIn('Enter',right)
        self.assertIn(workspace.t('waiting'),' '.join(right.split()))
        self.assertEqual(job.answers,[])

    def test_wizard_includes_unselected_catalog_and_cancel_first_saved_agreement(self):
        workspace = self.workspace('wizard')
        self.assertIn('catalog', app.STEPS)
        self.assertIn('agreement', app.STEPS)
        workspace.wizard_step = app.STEPS.index('agreement')
        workspace.focus = 1
        item = ('control', 'installed_default')
        self.assertIn(item, workspace.items())
        workspace.selected = workspace.items().index(item)
        with patch('policy_runtime.set_installed_update_default') as save:
            workspace.key('\n')
            self.assertEqual(workspace.modal, 'installed_default')
            self.assertEqual(workspace.modal_selected, 0)
            workspace.key('\n')
            save.assert_not_called()
            workspace.key('\n')
            workspace.key(curses.KEY_RIGHT)
            workspace.key('\n')
            save.assert_called_once_with(True, allow_registered_vendor_groups=True)
        self.assertIsNone(workspace.job)

    def test_catalog_selection_requires_explicit_product_and_source_and_never_launches(self):
        workspace = self.workspace('catalog')
        workspace.catalog_model = {'rows': [dict(product_id='alpha', name='Alpha', sources=[{'source_id':'vendor'}, {'source_id':'homebrew'}], installation_status='manual')]}
        workspace.catalog_error = ''
        workspace.focus = 1
        self.assertEqual(workspace.catalog_selected, set())
        target = ('catalog_target', 'alpha')
        source = ('catalog_source', 'alpha')
        self.assertIn(target, workspace.items())
        workspace.selected = workspace.items().index(target)
        workspace.key(' ')
        self.assertEqual(workspace.catalog_selected, {'alpha'})
        self.assertEqual(workspace.catalog_sources, {})
        workspace.selected = workspace.items().index(source)
        workspace.key(' ')
        self.assertEqual(workspace.catalog_sources, {})
        workspace.key('\n')
        self.assertEqual(workspace.catalog_sources, {'alpha':'vendor'})
        self.assertIsNone(workspace.job)

    def test_confirmation_never_covers_sidebar_at_minimum_size(self):
        workspace = self.workspace('updates')
        for modal in ('confirm', 'input', 'search', 'palette', 'installed_default'):
            workspace.modal, workspace.pending_action = modal, 'update'
            for width in (80,100,120,140):
                frame = workspace.frame(24,width)
                right = '\n'.join(line[-app.panel_sizes(width)[1]:] for line in frame.lines()[2:-5])
                self.assertIn(workspace.t('context_title'), right)
                self.assertIn(workspace.t('idle'), ' '.join(right.split()))
                self.assertIn('Enter', right)

    def test_prompt_clears_background_borders_and_footer_without_hiding_help(self):
        workspace = self.workspace('updates')
        self.attach(workspace)
        workspace.open_input()
        frame = workspace.frame(24,80)
        self.assertNotIn('╭─╭', '\n'.join(frame.lines()))
        self.assertNotIn(workspace.t('interrupt_button'), '\n'.join(frame.lines()[-5:-1]))
        self.assertIn(workspace.t('context_title'), '\n'.join(frame.lines()))

    def test_running_target_sidebar_keeps_observed_group_count(self):
        workspace = self.workspace('updates')
        row = self.target()
        workspace.preview_rows = [row]
        self.attach(workspace)
        workspace.job_action = 'update'
        workspace.group_states = {group:'running' for group in GROUPS}
        workspace.group_states['brew'] = 'completed'
        workspace.selected = workspace.items().index(('target',row['id']))
        frame = workspace.frame(38,140)
        right = '\n'.join(line[-32:] for line in frame.lines())
        self.assertIn('1/5',right)

    def test_minimum_running_screen_shows_active_target_and_group_without_cut_help(self):
        workspace = self.workspace('updates')
        done = self.target('a', name='Alpha Editor', identity_fingerprint='alpha', source_fingerprint='alpha')
        active = self.target('b', name='Beta Browser', source='vendor', identity_fingerprint='beta', source_fingerprint='beta')
        workspace.preview_rows = [done, active]
        self.attach(workspace)
        workspace.job_action = 'update'
        workspace.group_states['brew'] = 'completed'
        workspace.group_states['internet'] = 'running'
        workspace.target_states[workspace.target_key(done)] = dict(done, status='updated', verified=True)
        workspace.target_states[workspace.target_key(active)] = dict(active, status='vendor_updater_observing', verified=False)
        lines = workspace.frame(24, 80).lines()
        text = '\n'.join(lines)
        right = ' '.join(line[-26:].strip(' │') for line in lines)
        self.assertIn('Beta Browser', text)
        self.assertIn('Running', text)
        self.assertIn('Vendor applications: Running', right)
        self.assertIn('Review alone grants no new permission.', right)

    def test_about_identifies_author_version_and_public_project_without_a_job(self):
        workspace = self.workspace("about")
        text = "\n".join(workspace.frame(38, 140).lines())
        self.assertIn("Michał Kasprowicz", text)
        self.assertIn("1.8.1", text)
        self.assertIn("macos-updates.64bit.site", text)
        self.assertIn("github.com/KasprowiczM/macOS_updates", text)
        self.assertIsNone(workspace.job)


if __name__ == "__main__":
    unittest.main()
