"""CLI progress uses bounded human output, never toolkit protocol records."""
import io
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib/python'))
try:
    from tui_events import Reporter
except ImportError:
    Reporter = None


def action(n, source='npm'):
    return {'action_id': str(n), 'adapter_id': source, 'target_path': '/fixture/app',
            'target': {'kind':'package'}, 'expected_target': {'name': 'Tool'+str(n)},
            'expected_resolution': {'source': source}}


class CliProgressTests(unittest.TestCase):
    def test_group_end_explains_unfinished_observation(self):
        out = io.StringIO(); reporter = Reporter('en', out)
        reporter.phase('vendor', 'running')
        reporter.target(action(1, 'vendor'))
        reporter.target(action(1, 'vendor'), {'status': 'vendor_updater_observing'})
        reporter.phase('vendor', 'warn')
        self.assertIn('completion unconfirmed', out.getvalue())

    def test_verified_update_is_not_only_reported_as_current(self):
        out = io.StringIO(); reporter = Reporter('en', out)
        reporter.target(action(1))
        reporter.target(action(1), {'status': 'current_verified', 'reason_code': 'updated_verified',
                                    'verified': True, 'before': '1', 'after': '2'})
        self.assertIn('Updated (2)', out.getvalue())

    def test_running_target_and_unconfirmed_outcome_are_human_readable(self):
        out = io.StringIO(); reporter = Reporter('en', out)
        reporter.phase('npm','running')
        reporter.target(action(1))
        reporter.target(action(1), {'status':'triggered_unconfirmed','reason_code':'delegated_vendor_completion_unconfirmed'})
        reporter.phase('npm','warn')
        text = out.getvalue()
        self.assertIn('Native CLI and npm', text)
        self.assertIn('Tool1', text)
        self.assertIn('unconfirmed', text.lower())
        self.assertNotIn('@@MAC_UPDATE_', text)

    def test_many_blocked_targets_are_summarized_once_in_polish(self):
        out = io.StringIO(); reporter = Reporter('pl', out)
        reporter.phase('homebrew','running')
        for n in range(200):
            reporter.target(action(n,'homebrew'), {'status':'deferred_by_user','reason_code':'consent_required'})
        reporter.phase('homebrew','warn')
        text = out.getvalue()
        self.assertIn('200', text)
        self.assertIn('Homebrew', text)
        self.assertLess(len(text.splitlines()), 12)
        self.assertNotIn('consent_required', text)

    def test_cli_event_hooks_show_actual_action_without_tui_protocol(self):
        import os
        from unittest.mock import patch
        import tui_events
        out = io.StringIO(); reporter = Reporter('en', out)
        with patch.dict(os.environ, {'MAC_UPDATE_TUI_CHILD':'0','MAC_UPDATE_CLI_PROGRESS':'1'}), \
             patch.object(tui_events, '_CLI_REPORTER', reporter, create=True):
            tui_events.emit_phase('npm', 'running')
            tui_events.emit_target(action(1))
            tui_events.emit_target(action(1), {'status':'current_verified','verified':True})
            tui_events.emit_phase('npm', 'ok')
        self.assertIn('Tool1', out.getvalue())
        self.assertNotIn('@@MAC_UPDATE_', out.getvalue())

    def test_cli_mode_defaults_to_review_and_respects_explicit_off(self):
        import os, subprocess
        source = (Path(__file__).resolve().parents[1] / 'update_all.sh').read_text()
        block = source[source.index('# CLI progress and batch review defaults.'):source.index('# --doctor:')]
        for configured, expected in ((None, '1'), ('0', '0')):
            env = dict(os.environ, MAC_UPDATE_TUI_CHILD='0')
            env.pop('MAC_UPDATE_AUTOMATIC_INTERNET_BATCH', None)
            if configured is not None:
                env['MAC_UPDATE_AUTOMATIC_INTERNET_BATCH'] = configured
            proc = subprocess.run(['/bin/bash', '-c', block + '\nprintf "%s" "$MAC_UPDATE_AUTOMATIC_INTERNET_BATCH"'],
                                  env=env, text=True, capture_output=True, check=True)
            self.assertEqual(proc.stdout, expected)

    def test_seven_languages_report_without_internal_reason_codes(self):
        from tui_i18n import LANGUAGES
        for lang in LANGUAGES:
            with self.subTest(lang=lang):
                out = io.StringIO(); reporter = Reporter(lang, out)
                reporter.phase('vendor', 'running')
                reporter.target(action(1, 'vendor'), {'status': 'deferred_by_user', 'reason_code': 'scan_partial'})
                reporter.phase('vendor', 'warn')
                self.assertIn('1', out.getvalue())
                self.assertNotIn('scan_partial', out.getvalue())
                self.assertNotIn('inventory_reason_evidence', out.getvalue())

    def test_idle_tick_reports_no_fake_percentage(self):
        out = io.StringIO(); reporter = Reporter('en', out)
        reporter.phase('vendor','running'); reporter.tick()
        self.assertIn('unknown', out.getvalue().lower())
        self.assertNotIn('%', out.getvalue())

if __name__ == '__main__':
    unittest.main()
