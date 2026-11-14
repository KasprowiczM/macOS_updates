"""Mixed adapter dispatch preserves scope selection and aggregate severity."""
import os
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib/python'))
import policy_runtime as runtime


class MixedAdapterTests(unittest.TestCase):
    def test_selected_adapters_share_one_queue_and_excluded_adapters_do_not_run(self):
        actions = [dict(action_id=name, adapter_id=name, reason_codes=[],
                        expected_resolution={'source': name}, expected_target={'name': name},
                        target={'kind': 'package'}, target_path='/fixture/' + name,
                        artifact_effects=[]) for name in ('npm', 'homebrew', 'app_store')]
        seen = []
        def fake_queue(queue, execute, state_dir):
            seen.extend(queue)
            return [dict(action_id=a['action_id'], status='deferred_by_user',
                         verified=False, _exit_code=10 if a['adapter_id'] == 'npm' else 1)
                    for a in queue]
        with tempfile.TemporaryDirectory() as root, patch.object(runtime, 'load_plan', return_value={'actions': actions, 'plan_id': 'fixture'}), \
             patch('update_scheduler.execute_queue', side_effect=fake_queue), \
             patch.object(runtime, '_append'):
            self.assertEqual(runtime.run_adapters('fixture', ('npm', 'homebrew'), root), 1)
        self.assertEqual([a['adapter_id'] for a in seen], ['npm', 'homebrew'])
        self.assertTrue(all(a['parallel_safe'] is False for a in seen))

    def test_per_adapter_report_records_skips_and_severity(self):
        actions = [dict(action_id=name, adapter_id=name, reason_codes=[],
                        expected_resolution={'source': name}, expected_target={'name': name},
                        target={'kind': 'package'}, target_path='/fixture/' + name,
                        artifact_effects=[]) for name in ('npm', 'homebrew')]
        def fake_queue(queue, execute, state_dir):
            return [dict(action_id=a['action_id'], status='deferred_by_user', verified=False,
                         _exit_code=10 if a['adapter_id'] == 'npm' else 1) for a in queue]
        with tempfile.TemporaryDirectory() as root, patch.object(runtime, 'load_plan', return_value={'actions': actions, 'plan_id': 'fixture'}), \
             patch('update_scheduler.execute_queue', side_effect=fake_queue), \
             patch.object(runtime, '_append'), patch.dict(os.environ, {'MAC_UPDATE_ADAPTER_REPORT': str(Path(root, 'report.json'))}):
            self.assertEqual(runtime.run_adapters('fixture', ('npm', 'homebrew', 'app_store'), root), 1)
            report = json.loads(Path(root, 'report.json').read_text())
        self.assertEqual(report['adapters'], {'npm': 10, 'homebrew': 1, 'app_store': 0})

    def test_delegated_actions_are_sent_to_batch_after_other_managers(self):
        actions = [dict(action_id=name, adapter_id=adapter, reason_codes=[],
                        action_scope=scope, expected_resolution={'source': source},
                        expected_target={'name': name}, target={'kind': 'app'},
                        target_path='/fixture/' + name, artifact_effects=[])
                   for name, adapter, scope, source in (
                       ('browser-a', 'installed_native:a', 'delegated_native_update', 'vendor'),
                       ('browser-b', 'installed_native:b', 'legacy_same_source_update', 'vendor'),
                       ('npm', 'npm', 'manager_update', 'npm'))]
        calls = []
        def ordinary(queue, callback, state):
            calls.append(('ordinary', [a['action_id'] for a in queue]))
            return [dict(action_id='npm', status='current_verified', _exit_code=0)]
        def batch(queue, callback, state):
            calls.append(('batch', [a['action_id'] for a in queue]))
            return [dict(action_id=a['action_id'], status='triggered_unconfirmed',
                         mutation_started=True, recovery_required=True, _exit_code=10) for a in queue]
        with tempfile.TemporaryDirectory() as root, patch.object(runtime, 'load_plan', return_value={'actions': actions, 'plan_id': 'fixture'}), \
             patch('update_scheduler.execute_queue', side_effect=ordinary), \
             patch('update_scheduler.execute_exclusive_batch', side_effect=batch), \
             patch.object(runtime, '_append'), patch.dict(os.environ, {'MAC_UPDATE_ADAPTER_REPORT': str(Path(root, 'report.json'))}):
            self.assertEqual(runtime.run_adapters('fixture', ('npm', 'vendor'), root), 10)
            report = json.loads(Path(root, 'report.json').read_text())
        self.assertEqual(calls, [('ordinary', ['npm']), ('batch', ['browser-a', 'browser-b'])])
        self.assertTrue(report['native_batch_pending'])

    def test_real_batch_dispatch_runs_delegated_callbacks_together(self):
        from update_scheduler import pending_sessions
        gate = threading.Barrier(2)
        actions = [dict(action_id=name, adapter_id='installed_native:' + name,
                        action_scope='delegated_native_update', reason_codes=[],
                        expected_resolution={'source': 'vendor'}, expected_target={'name': name},
                        target={'kind': 'app'}, target_path='/fixture/' + name,
                        artifact_effects=[], scope_complete=False, parallel_safe=False)
                   for name in ('a', 'b')]
        def fake_action(plan, adapter, action, state_dir, lease, **kwargs):
            self.assertTrue(kwargs.get('batch_managed'))
            gate.wait(timeout=5)
            return dict(action_id=action['action_id'], status='triggered_unconfirmed',
                        verified=False, mutation_started=True, recovery_required=True), 10
        with tempfile.TemporaryDirectory() as root, patch.object(runtime, 'load_plan', return_value={'actions': actions, 'plan_id': 'fixture'}), \
             patch.object(runtime, '_execute_action', side_effect=fake_action), \
             patch.object(runtime, 'emit_target'), patch.object(runtime, '_append'):
            self.assertEqual(runtime.run_adapters('fixture', ('vendor',), root), 10)
            self.assertEqual(pending_sessions(root)[0]['status'], 'recovery_required')

    def test_phase_events_start_before_work_and_finish_from_result(self):
        calls = []
        actions = [dict(action_id='npm-a', adapter_id='npm', action_scope='manager_update',
                        reason_codes=[], expected_resolution={'source':'npm'},
                        expected_target={'name':'fixture'}, target={'kind':'package'},
                        target_path='/fixture/npm', artifact_effects=[])]
        def fake_action(plan, adapter, action, state, lease, **kwargs):
            calls.append(('execute', adapter))
            return dict(action_id=action['action_id'], status='deferred_by_user', verified=False,
                        mutation_started=False, recovery_required=False), 10
        with tempfile.TemporaryDirectory() as root, patch.object(runtime, 'load_plan', return_value={'actions': actions, 'plan_id': 'fixture'}), \
             patch.object(runtime, '_execute_action', side_effect=fake_action), \
             patch.object(runtime, 'emit_target'), patch.object(runtime, '_append'), \
             patch('tui_events.emit_phase', side_effect=lambda adapter, status: calls.append((status, adapter)), create=True):
            self.assertEqual(runtime.run_adapters('fixture', ('npm',), root), 10)
        self.assertEqual(calls, [('running', 'npm'), ('execute', 'npm'), ('warn', 'npm')])

    def test_invalid_adapter_rejected_before_loading_plan(self):
        with patch.object(runtime, 'load_plan') as load:
            self.assertEqual(runtime.run_adapters('fixture', ('npm', 'unknown')), 1)
        load.assert_not_called()

if __name__ == '__main__':
    unittest.main()

class MixedShellIntegrationTests(unittest.TestCase):
    def run_gate(self, codes, exit_code, skips=(), missing=False, enabled=True, pending=False):
        import subprocess
        source = (Path(__file__).resolve().parents[1] / 'update_all.sh').read_text()
        block = source[source.index('# The joint queue starts only'):source.index('# STEP 1: App Store update')]
        with tempfile.TemporaryDirectory() as root:
            env = os.environ.copy()
            env.update(SESSION_DIR=root, SCRIPT_DIR=root, MAC_UPDATE_MIXED_QUEUE='1',
                       PLAN_PREPARE_EXIT='0', MAC_UPDATE_PLAN_PATH='fixture',
                       FIXTURE_CODES=json.dumps(codes), FIXTURE_EXIT=str(exit_code),
                       FIXTURE_MISSING='1' if missing else '0', FIXTURE_PENDING='1' if pending else '0')
            if enabled is None:
                env.pop('MAC_UPDATE_MIXED_QUEUE', None)
            env.update({'MAC_UPDATE_SKIP_' + name: '1' for name in skips})
            script = '''
python3() {
  if [ "$1" = "-c" ]; then
    shift 2
    [ "$1" = adapters ] || return 99
    shift 2
    printf '%s\\n' "$*" > "$SESSION_DIR/called"
    if [ "$FIXTURE_MISSING" != 1 ]; then
      /usr/bin/python3 -c 'import json,os,sys; json.dump({"schema_version":1,"native_batch_pending":os.environ["FIXTURE_PENDING"]=="1","adapters":{a:json.loads(os.environ["FIXTURE_CODES"])[a] for a in sys.argv[1:]}},open(os.environ["MAC_UPDATE_ADAPTER_REPORT"],"w"))' "$@"
    fi
    return "$FIXTURE_EXIT"
  fi
  /usr/bin/python3 "$@"
}
L_ALL_RESULT_OK=ok L_STATUS_ERROR=error DEGRADED=0 BLOCKING_EXIT=0 OVERALL_EXIT=0
''' + block + '''
printf '%s\\n' "$MIXED_QUEUE_STARTED $MIXED_APPSTORE $MIXED_NPM $MIXED_BREW $MIXED_INTERNET $MIXED_PENDING"
mixed_queue_result "$MIXED_NPM"
printf '%s\\n' "$MIXED_STATUS $DEGRADED $BLOCKING_EXIT"
'''
            result = subprocess.run(['/bin/bash', '-c', script], env=env, text=True, capture_output=True, check=True)
            called = Path(root, 'called')
            return result.stdout.splitlines(), called.read_text().strip() if called.exists() else None

    def test_enabled_adapters_run_once_and_warning_is_preserved(self):
        lines, called = self.run_gate({'npm': 10, 'homebrew': 0}, 10, ('APPSTORE', 'INTERNET'))
        self.assertEqual(called, 'npm homebrew')
        self.assertEqual(lines, ['1 0 10 0 0 0', 'warn 1 0'])

    def test_mixed_queue_is_default_when_not_configured(self):
        lines, called = self.run_gate({'npm': 0}, 0, ('APPSTORE', 'BREW', 'INTERNET'), enabled=None)
        self.assertEqual(called, 'npm')
        self.assertEqual(lines[0], '1 0 0 0 0 0')

    def test_pending_batch_flag_reaches_system_barrier(self):
        lines, called = self.run_gate({'vendor': 10}, 10, ('APPSTORE', 'NPM', 'BREW'), pending=True)
        self.assertEqual(called, 'vendor')
        self.assertEqual(lines[0], '1 0 0 0 10 1')
        source = (Path(__file__).resolve().parents[1] / 'update_all.sh').read_text()
        system = source[source.index('# FINAL MUTATING STEP: macOS system update'):]
        self.assertLess(system.index('"$MIXED_PENDING" = "1"'), system.index('mac_update_run_child "update_system.sh"'))

    def test_missing_report_fails_closed_without_retry(self):
        lines, called = self.run_gate({'npm': 0}, 0, ('APPSTORE', 'BREW', 'INTERNET'), missing=True)
        self.assertEqual(called, 'npm')
        self.assertEqual(lines, ['1 1 1 1 1 1', 'error 0 1'])
