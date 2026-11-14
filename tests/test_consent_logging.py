"""Preparation diagnostics survive a stopped consent review without host actions."""
import json
import unittest
import test_plan_orchestration as fixtures


class ConsentLoggingTests(unittest.TestCase):
    def test_stopped_preparation_is_logged_before_any_update_step(self):
        fixture = fixtures.PlanOrchestrationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        script = fixture.repo / 'update_all.sh'
        source = script.read_text()
        # Stop at the preparation boundary: no update child or sudo runs.
        source = source.replace('PLAN_PREPARE_EXIT=$?', 'exit 0', 1)
        script.write_text(source)
        module = fixture.repo / 'lib/python/plan_orchestration.py'
        source = module.read_text().replace(
            'def main(script_dir, mode, session_dir=None):',
            'def main(script_dir, mode, session_dir=None):\n'
            '    if mode == "prepare":\n'
            '        print("CONSENT_WAIT_FIXTURE", flush=True)\n'
            '        return 0', 1)
        module.write_text(source)
        result = fixture.run_master('-y', '--skip-system', '--skip-appstore')
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        logs = list((fixture.repo / 'logs').glob('update_all_*.log'))
        self.assertEqual(len(logs), 1)
        self.assertIn('CONSENT_WAIT_FIXTURE', logs[0].read_text())
        self.assertEqual(logs[0].stat().st_mode & 0o777, 0o600)
        summaries = list((fixture.repo / 'logs').glob('run_summary_2*.json'))
        self.assertEqual(len(summaries), 1)
        self.assertIsInstance(json.loads(summaries[0].read_text()), dict)
        self.assertNotIn('sudo', result.stderr.lower())
