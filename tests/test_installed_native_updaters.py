"""Delegated vendor updater fixtures. No host application or updater is run."""
import copy
import contextlib
import io
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib/python'))
from source_resolver import resolve_target
from update_plan import build_plan, authorize_action
from user_policy import make_decision, record_decision
import policy_runtime as runtime
from update_scheduler import claim_action_resources, pending_sessions, resource_keys

NOW = '2026-11-14T12:00:00Z'


def target(path='/Applications/Claude.app'):
    return dict(instance_id='claude', path=path, real_path=path,
                name='Claude', bundle_id='com.anthropic.claudefordesktop',
                team_id='Q6L2SF6YDW', channel='unknown', short_version='5.11492.5',
                presence='present', freshness='fresh', running=False,
                evidence=[dict(kind='vendor_signature',
                               bundle_id='com.anthropic.claudefordesktop',
                               team_id='Q6L2SF6YDW', verification='installed_code_valid'),
                          dict(kind='installed_native_updater', contract_id='claude-desktop', revision=1)])


def plan_for(app, choice='allow_native_launch'):
    snapshot = dict(snapshot_id='s1', profile_id='p1', generation=0,
                    instances=[app], packages=[], sources={})
    res = resolve_target(app, snapshot, {'recipes': []})
    scope = ('legacy_same_source_update' if res.get('installed_updater_contract', {}).get('execution_kind') == 'legacy_handler'
             else 'delegated_native_update')
    policies = {'profile_id': 'p1'}
    if choice:
        if scope == 'legacy_same_source_update' and choice == 'allow_native_launch':
            choice = 'allow_update_same_source'
        policies = record_decision(make_decision(app, res, choice,
                                                scope, NOW), policies)
    return build_plan(snapshot, [res], policies, NOW), policies, res


class DelegatedNativeTests(unittest.TestCase):
    def _legacy_app_action(self, root):
        path=root/'KeePassXC.app';path.mkdir()
        app=target(str(path));app.update(name='KeePassXC',bundle_id='org.keepassxc.keepassxc',team_id='FIXTURE123')
        app['evidence'][0].update(bundle_id=app['bundle_id'],team_id=app['team_id'])
        return plan_for(app)[0]['actions'][0]

    def test_post_mutation_legacy_error_never_releases_as_an_unstarted_action(self):
        from installed_native_updaters import run_delegated_update
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();state=str(root/'state')
            action=self._legacy_app_action(root)
            lease=claim_action_resources(action,state)
            with patch('installed_native_updaters.execute_legacy_handler',side_effect=OSError('after child mutation')):
                result=run_delegated_update(action,lease,authorize=lambda:True,plan_path='fixture')
            self.assertTrue(result['mutation_started'])
            self.assertTrue(result['recovery_required'])
            self.assertEqual(len(pending_sessions(state)),1)
            self.assertFalse(lease.closed)

    def test_timed_out_live_legacy_writer_is_durable_and_cannot_be_recovered(self):
        from installed_native_updaters import run_delegated_update,reconcile_delegated_update
        class Process:
            pid=54321
            def wait(self,timeout): raise subprocess.TimeoutExpired('fixture',timeout)
        def ps(argv,**kwargs):
            return subprocess.CompletedProcess(argv,0,'Sat Nov 14 12:00:00 2026\n','')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();state=str(root/'state')
            action=self._legacy_app_action(root);lease=claim_action_resources(action,state)
            action.pop('execution_kind')  # Journal metadata must not bypass the closed contract.
            with patch('installed_native_updaters.subprocess.Popen',return_value=Process()), \
                 patch('installed_native_updaters.subprocess.run',side_effect=ps):
                result=run_delegated_update(action,lease,authorize=lambda:True,plan_path='fixture')
                current=dict(action['expected_target'],resolution=action['expected_resolution'])
                with patch.object(runtime,'reobserve_action',return_value=current):
                    self.assertFalse(reconcile_delegated_update(result['native_session_id'],state_dir=state,confirmed=True))
            journal=next((root/'state/delegated-native').glob('*.json')).read_text()
            self.assertIn('54321',journal)
            self.assertIn('start_token',journal)
            self.assertEqual(len(pending_sessions(state)),1)

    def test_child_writer_barrier_rejects_a_released_lease_before_any_updater_mutation(self):
        from installed_native_updaters import record_legacy_writer_start
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();state=str(root/'state')
            action=self._legacy_app_action(root);lease=claim_action_resources(action,state)
            session=root/'state/delegated-native/11111111-1111-1111-1111-111111111111'
            session.mkdir(parents=True,mode=0o700)
            session.parent.chmod(0o700)
            runtime._atomic_json(str(session)+'.json',dict(action=action,lease_id=lease.lease_id,
                batch_action_id=None,state='trigger_attempted'))
            env=dict(MAC_UPDATE_STATE_DIR=state,MAC_UPDATE_SESSION_DIR=str(session),
                MAC_UPDATE_ACTION_ID=action['action_id'],MAC_UPDATE_BATCH_OWNER=action['action_id'])
            with patch.dict(os.environ,env), \
                 patch('installed_native_updaters._probe_legacy_writer',return_value={'state':'running','start_token':'fixture-token'}):
                journal=runtime._read_json(str(session)+'.json')
                journal['lease_id']='different-lease'
                runtime._atomic_json(str(session)+'.json',journal)
                self.assertFalse(record_legacy_writer_start())
                journal['lease_id']=lease.lease_id
                runtime._atomic_json(str(session)+'.json',journal)
                self.assertTrue(record_legacy_writer_start())
                lease.finish('fixture finished',helpers_complete=True)
                self.assertFalse(record_legacy_writer_start())

    def test_known_signature_enrichment_overlaps_preserves_order_and_skips_unknown_apps(self):
        from installed_native_updaters import enrich_installed_updater_identities
        apps=[target(), dict(target('/Applications/Unknown.app'),bundle_id='fixture.unknown'),
              dict(target('/Applications/Warp.app'),bundle_id='dev.warp.Warp-Stable')]
        barrier=threading.Barrier(2)
        inspected=[]
        def inspect(app):
            inspected.append(app['real_path'])
            barrier.wait(timeout=2)
            return dict(app, signature_fixture=True)
        with patch('installed_native_updaters.inspect_installed_target',side_effect=inspect):
            result=enrich_installed_updater_identities({'instances':apps})
        self.assertEqual([a['real_path'] for a in result['instances']],[a['real_path'] for a in apps])
        self.assertEqual(set(inspected),{'/Applications/Claude.app','/Applications/Warp.app'})
        self.assertNotIn('signature_fixture',result['instances'][1])

    def test_signature_enrichment_failure_is_stale_without_inherited_signing_authority(self):
        from installed_native_updaters import enrich_installed_updater_identities
        with patch('installed_native_updaters.inspect_installed_target',side_effect=OSError('fixture')):
            current=enrich_installed_updater_identities({'instances':[target()]})['instances'][0]
        self.assertEqual(current['freshness'],'stale')
        self.assertIsNone(current['team_id'])
        self.assertFalse(any(e.get('kind') in ('vendor_signature','installed_native_updater') for e in current['evidence']))

    def test_vendor_helper_requires_a_valid_signature_with_the_approved_installed_team(self):
        from installed_native_updaters import verify_installed_updater_executable
        with tempfile.TemporaryDirectory() as tmp:
            binary=Path(tmp).resolve()/'GoogleUpdater'
            binary.write_text('fixture'); binary.chmod(0o700)
            def native(argv, **kwargs):
                return subprocess.CompletedProcess(argv, 0, '', 'TeamIdentifier=EQHXZ8M8AV\n')
            with patch('installed_native_updaters.subprocess.run', side_effect=native) as command:
                self.assertTrue(verify_installed_updater_executable(str(binary), 'EQHXZ8M8AV'))
                self.assertFalse(verify_installed_updater_executable(str(binary), 'OTHER12345'))
            self.assertEqual(command.call_args_list[0].args[0][:3], ('codesign', '--verify', '--strict'))

    def test_common_observation_deadline_monitors_all_apps_without_serial_waits_or_verifying_latest(self):
        from installed_native_updaters import observe_batch_versions
        clock = [0.0]
        a = plan_for(target('/Applications/Claude.app'))[0]['actions'][0]
        b = copy.deepcopy(a); b.update(action_id='second', target_path='/Applications/Warp.app')
        b['expected_target']['real_path'] = b['target_path']
        outcomes = [dict(action_id=a['action_id'], status='triggered_unconfirmed', verified=False),
                    dict(action_id=b['action_id'], status='triggered_unconfirmed', verified=False)]
        def observe(path):
            newer = path.endswith('Claude.app') or clock[0] >= 1
            return dict(status='ok', complete=True, items=[dict(bundle_id='com.anthropic.claudefordesktop',
                        short_version='6.0' if newer else '5.11492.5', build_version='new' if newer else None)])
        events=[]
        results = observe_batch_versions([a,b], outcomes, timeout=30, clock=lambda: clock[0],
                                        sleep=lambda seconds: clock.__setitem__(0, clock[0]+seconds),
                                        observe=observe, emit=lambda action, outcome: events.append(outcome))
        self.assertEqual(clock[0], 1.0)
        self.assertEqual([r['status'] for r in results], ['observed_version_changed', 'observed_version_changed'])
        self.assertTrue(all(r['verified'] is False for r in results))
        self.assertTrue(all(r['vendor_completion'] == 'unconfirmed' for r in results))
        self.assertEqual(sum(r['status']=='observed_version_changed' for r in events), 2)

    def test_dry_run_without_mutation_lease_never_launches_or_writes_journal(self):
        from installed_native_updaters import run_delegated_update
        action = plan_for(target())[0]['actions'][0]
        with patch.dict(os.environ, {'MAC_UPDATE_DRY_RUN': '1'}), \
             patch('installed_native_updaters.subprocess.Popen') as spawn, \
             patch('installed_native_updaters._root') as root:
            result = run_delegated_update(action, None, authorize=lambda: True)
        self.assertFalse(result['mutation_started'])
        spawn.assert_not_called()
        root.assert_not_called()

    def test_signed_desktop_exposes_real_opt_in_without_faking_release_acceptance(self):
        app = target()
        plan, policies, res = plan_for(app)
        self.assertEqual(res['capability'], 'installed_native_delegate')
        self.assertEqual(res['source'], 'unknown')
        action = plan['actions'][0]
        self.assertEqual(action['kind'], 'open_native_updater')
        self.assertNotIn('recipe', action)
        self.assertEqual(action['action_scope'], 'delegated_native_update')
        self.assertEqual(action['reason_codes'], [])
        self.assertFalse(action['scope_complete'])
        self.assertFalse(action['parallel_safe'])
        self.assertTrue(authorize_action(action, dict(app, resolution=res), policies, NOW)['allowed'])

    def test_manual_and_missing_choice_do_not_authorize_a_launch(self):
        for choice, expected in [('preserve_source', 'manual'), (None, 'open_native_updater')]:
            with self.subTest(choice=choice):
                app = target()
                plan, policies, res = plan_for(app, choice)
                self.assertEqual(plan['actions'][0]['kind'], expected)
                self.assertFalse(authorize_action(plan['actions'][0], dict(app, resolution=res), policies, NOW)['allowed'])

    def test_ios_wrong_signer_unsigned_and_prerelease_are_never_delegate_candidates(self):
        for changes in [dict(bundle_id='com.anthropic.claude'), dict(team_id='OTHER12345'),
                        dict(evidence=[]), dict(channel='nightly'), dict(channel='beta')]:
            app = dict(target(), **changes)
            self.assertNotEqual(resolve_target(app, {'instances': [app]}, {'recipes': []})['capability'],
                                'installed_native_delegate')

    def test_manager_claim_duplicate_or_stale_target_cannot_delegate(self):
        for bad in ['mas', 'enterprise', 'duplicate', 'stale']:
            app = target()
            snapshot = {'instances': [app]}
            if bad == 'mas':
                app['evidence'].append(dict(kind='app_store_receipt'))
            elif bad == 'enterprise':
                app['evidence'].append(dict(kind='enterprise_managed'))
            elif bad == 'duplicate':
                snapshot['instances'].append(dict(app, instance_id='other'))
            else:
                app['freshness'] = 'stale'
            self.assertNotEqual(resolve_target(app, snapshot, {'recipes': []})['capability'], 'installed_native_delegate')

    def test_fresh_guards_reject_running_and_identity_changes(self):
        app = target()
        plan, policies, res = plan_for(app)
        for changes in [dict(running=True), dict(running=None), dict(team_id='OTHER12345'), dict(channel='stable')]:
            self.assertFalse(authorize_action(plan['actions'][0], dict(app, resolution=res, **changes), policies, NOW)['allowed'])

    def test_manager_adoption_after_consent_is_detected_by_fresh_native_guard(self):
        app = target()
        plan, policies, res = plan_for(app)
        receipt = dict(kind='homebrew', token='claude', prefix='/fixture/brew',
                       installed_receipt='/fixture/brew/receipt.json', artifact_path=app['real_path'])
        with patch.dict(os.environ, {'MAC_UPDATE_BREW_PREFIXES': '/fixture/brew'}), \
             patch.object(runtime, '_current_app', return_value=copy.deepcopy(app)), \
             patch.object(runtime, 'read_brew_receipts', return_value={'status': 'ok', 'complete': True, 'items': [{'evidence': [receipt]}]}), \
             patch.object(runtime, '_running', return_value=False):
            current = runtime.reobserve_action(plan['actions'][0])
        self.assertEqual(current['resolution']['source'], 'homebrew')
        self.assertFalse(authorize_action(plan['actions'][0], current, policies, NOW)['allowed'])

    def test_signature_enrichment_verifies_exact_desktop_signer_and_never_launches(self):
        from installed_native_updaters import inspect_installed_target
        with tempfile.TemporaryDirectory() as tmp:
            app = target(os.path.realpath(tmp))
            app['team_id'] = None
            app['evidence'] = []
            commands = []
            def command(argv, **kwargs):
                commands.append(argv)
                return subprocess.CompletedProcess(argv, 0, '',
                    'Identifier=com.anthropic.claudefordesktop\nTeamIdentifier=Q6L2SF6YDW\n')
            with patch('installed_native_updaters.subprocess.run', side_effect=command):
                result = inspect_installed_target(app)
            self.assertEqual(result['team_id'], 'Q6L2SF6YDW')
            self.assertEqual([c[0] for c in commands], ['codesign', 'spctl', 'codesign'])
            self.assertTrue(any(e.get('verification') == 'installed_code_valid' for e in result['evidence']))
            self.assertNotIn('installed_code_valid', str(app['evidence']))

    def test_failed_signature_never_inherits_previous_verified_evidence(self):
        from installed_native_updaters import inspect_installed_target
        with tempfile.TemporaryDirectory() as tmp:
            app = target(os.path.realpath(tmp))
            with patch('installed_native_updaters.subprocess.run', side_effect=subprocess.CalledProcessError(1, ['codesign'])):
                result = inspect_installed_target(app)
            self.assertIsNone(result['team_id'])
            self.assertNotEqual(resolve_target(result, {'instances': [result]}, {'recipes': []})['capability'], 'installed_native_delegate')

    def test_trigger_is_exact_path_once_truthful_and_holds_exclusive_lease(self):
        from installed_native_updaters import run_delegated_update
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            app_path = root / 'Claude.app'; app_path.mkdir()
            app = target(str(app_path))
            plan, policies, res = plan_for(app)
            action = plan['actions'][0]
            lease = claim_action_resources(action, str(root / 'state'))
            calls = []
            def spawn(argv, **kwargs):
                calls.append(argv)
                return object()
            with patch('installed_native_updaters.subprocess.Popen', side_effect=spawn):
                result = run_delegated_update(action, lease, authorize=lambda: True)
            self.assertEqual(calls, [('open', '-g', str(app_path))])
            self.assertEqual(result['status'], 'triggered_unconfirmed')
            self.assertFalse(result['verified'])
            self.assertTrue(result['recovery_required'])
            rows = pending_sessions(str(root / 'state'))
            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0]['exclusive'])
            self.assertEqual(rows[0]['status'], 'recovery_required')
            self.assertTrue(list((root / 'state' / 'delegated-native').glob('*.json')))

    def test_registry_restores_native_and_legacy_direct_products_but_excludes_deepseek(self):
        for name, kind in [('Warp', 'native_window'), ('KeePassXC', 'legacy_handler'),
                           ('Visual Studio Code', 'legacy_handler'), ('Google Chrome', 'legacy_handler')]:
            app = target('/Applications/'+name+'.app')
            app.update(name=name, bundle_id='fixture.'+name.replace(' ', ''), team_id='FIXTURE123')
            app['evidence'][0].update(bundle_id=app['bundle_id'], team_id=app['team_id'])
            res = resolve_target(app, {'instances': [app]}, {'recipes': []})
            self.assertEqual(res['capability'], 'installed_native_delegate', name)
            self.assertEqual(res['installed_updater_contract']['execution_kind'], kind)
            self.assertEqual(res['source'], 'unknown')
        app = target('/Applications/DeepSeek Harness.app')
        app.update(name='DeepSeek Harness', bundle_id='fixture.deepseek')
        self.assertNotEqual(resolve_target(app, {'instances': [app]}, {'recipes': []})['capability'], 'installed_native_delegate')

    def test_fresh_batch_approval_can_replace_only_an_explicit_old_manual_choice(self):
        from installed_native_updaters import batch_approval_choice
        app = target()
        action = plan_for(app, 'preserve_source')[0]['actions'][0]
        self.assertEqual(batch_approval_choice(action), 'allow_native_launch')
        for reason in ['ignored_by_policy', 'deferred_by_user', 'source_conflict', 'scan_partial']:
            self.assertIsNone(batch_approval_choice(dict(action, reason_codes=[reason])))

    def test_direct_handler_mapping_is_code_owned_and_cannot_be_an_inventory_command(self):
        from installed_native_updaters import legacy_handler_for
        app = target('/Applications/KeePassXC.app')
        app.update(name='KeePassXC', bundle_id='org.keepassxc.keepassxc', team_id='FIXTURE123')
        app['evidence'][0].update(bundle_id=app['bundle_id'], team_id=app['team_id'])
        action = plan_for(app)[0]['actions'][0]
        self.assertEqual(legacy_handler_for(action), 'iu_keepassxc')
        action['legacy_handler_id'] = 'touch /outside'
        self.assertEqual(legacy_handler_for(action), 'iu_keepassxc')

    def test_legacy_replacement_keeps_original_guard_and_transaction_target_binding(self):
        from installed_native_updaters import execute_legacy_replacement
        app = target('/Applications/KeePassXC.app')
        app.update(name='KeePassXC', bundle_id='org.keepassxc.keepassxc', team_id='FIXTURE123')
        app['evidence'][0].update(bundle_id=app['bundle_id'], team_id=app['team_id'])
        action = plan_for(app)[0]['actions'][0]
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(runtime, 'load_plan', return_value={'actions': [action]}), \
             patch.object(runtime, 'guard_action', return_value={'allowed': True}) as guard, \
             patch('update_transaction.execute_transaction', return_value={'state': 'verified'}) as transaction:
            result = execute_legacy_replacement('plan', action['action_id'], '/fixture/payload.app', app['real_path'], 'batch', state_dir=str(Path(tmp).resolve()/'state'))
            self.assertEqual(result, 0)
            internal = transaction.call_args.args[0]
            self.assertEqual(internal['action_scope'], 'direct_update')
            self.assertEqual(internal['adapter_id'], 'legacy_verified_bundle')
            self.assertEqual(internal['target_path'], app['real_path'])
            self.assertTrue(transaction.call_args.args[4]())
            self.assertEqual(guard.call_args.args[3], 'batch')

    def test_unknown_channel_legacy_replacement_performs_the_real_signed_bundle_transaction(self):
        import update_transaction as transaction
        from installed_native_updaters import execute_legacy_replacement
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();apps=root/'Applications';apps.mkdir()
            app=apps/'KeePassXC.app';app.mkdir();(app/'version').write_text('1.0')
            source=root/'download'/'KeePassXC.app';source.mkdir(parents=True);(source/'version').write_text('2.0')
            installed=target(str(app));installed.update(name='KeePassXC',bundle_id='org.keepassxc.keepassxc',team_id='FIXTURE123')
            installed['evidence'][0].update(bundle_id=installed['bundle_id'],team_id=installed['team_id'])
            action=plan_for(installed)[0]['actions'][0]
            def current(action):
                return dict(installed,resolution=action['expected_resolution'],running=False)
            def observe(path):
                return dict(good=True,receipt_present=False,running=False,
                    bundle_id=installed['bundle_id'],team_id=installed['team_id'],
                    version=(Path(path)/'version').read_text(),architectures=['arm64'],minimum_os='13.0',host_os='26.0')
            with patch.object(runtime,'load_plan',return_value={'actions':[action]}), \
                 patch.object(runtime,'reobserve_action',side_effect=current), \
                 patch.object(runtime,'guard_action',return_value={'allowed':True}), \
                 patch.object(transaction,'observe_bundle',side_effect=observe), \
                 patch.object(transaction,'approved_roots',return_value=[str(apps)]), \
                 patch.object(transaction,'sys_platform_darwin',return_value=False):
                code=execute_legacy_replacement('plan',action['action_id'],str(source),str(app),'batch',state_dir=str(root/'state'))
            self.assertEqual(code,0)
            self.assertEqual((app/'version').read_text(),'2.0')
            self.assertEqual(installed['channel'],'unknown')
            journal=next((root/'state/transactions').glob('*.json')).read_text()
            self.assertIn('"state": "verified"',journal)

    def test_native_batch_fanout_does_not_release_or_pending_shared_lease_per_row(self):
        from installed_native_updaters import run_delegated_update, pending_delegated_sessions
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            first = root / 'Claude.app'; first.mkdir()
            second = root / 'Warp.app'; second.mkdir()
            a = plan_for(target(str(first)))[0]['actions'][0]
            app = target(str(second)); app.update(name='Warp', bundle_id='dev.warp.Warp-Stable', team_id='FIXTURE123')
            app['evidence'][0].update(bundle_id=app['bundle_id'], team_id=app['team_id'])
            b = plan_for(app)[0]['actions'][0]
            group = dict(a, action_id='group', resources=sorted(set(resource_keys(a)+resource_keys(b))), scope_complete=False)
            state = str(root / 'state')
            lease = claim_action_resources(group, state)
            with patch('installed_native_updaters.subprocess.Popen') as spawn:
                for action in (a, b):
                    result = run_delegated_update(action, lease, authorize=lambda: True, batch_managed=True)
                    self.assertEqual(result['status'], 'triggered_unconfirmed')
            self.assertEqual(spawn.call_count, 2)
            self.assertEqual(pending_sessions(state)[0]['status'], 'active')
            self.assertEqual(len(pending_delegated_sessions(state)), 2)
            self.assertFalse(lease.closed)

    def test_batch_recovery_never_releases_a_shared_lease_from_one_member(self):
        from installed_native_updaters import run_delegated_update, pending_delegated_sessions, reconcile_delegated_batch, reconcile_delegated_update
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            one = root / 'Claude.app'; one.mkdir()
            two = root / 'Warp.app'; two.mkdir()
            a = plan_for(target(str(one)))[0]['actions'][0]
            app = target(str(two)); app.update(name='Warp', bundle_id='dev.warp.Warp-Stable', team_id='FIXTURE123')
            app['evidence'][0].update(bundle_id=app['bundle_id'], team_id=app['team_id'])
            b = plan_for(app)[0]['actions'][0]
            state = str(root / 'state')
            group = dict(a, action_id='group', resources=sorted(set(resource_keys(a)+resource_keys(b))), scope_complete=False)
            lease = claim_action_resources(group, state)
            with patch('installed_native_updaters.subprocess.Popen'):
                for action in (a, b):
                    run_delegated_update(action, lease, authorize=lambda: True, batch_managed=True)
            lease.pending('batch_unconfirmed')
            sessions = [r['session_id'] for r in pending_delegated_sessions(state)]
            def observe(action):
                return dict(action['expected_target'], resolution=action['expected_resolution'])
            with patch.object(runtime, 'reobserve_action', side_effect=observe):
                self.assertFalse(reconcile_delegated_update(sessions[0], state_dir=state, confirmed=True))
                self.assertEqual(len(pending_sessions(state)), 1)
                self.assertFalse(reconcile_delegated_batch(sessions[:1], state_dir=state, confirmed=True))
                self.assertTrue(reconcile_delegated_batch(sessions, state_dir=state, confirmed=True))
            self.assertEqual(pending_sessions(state), [])

    def test_runtime_dispatch_rechecks_consent_before_trigger(self):
        app = target()
        plan, policies, res = plan_for(app)
        action = plan['actions'][0]
        with patch.object(runtime, 'guard_action', return_value={'allowed': True}), \
             patch.object(runtime, 'TargetLock', return_value=contextlib.nullcontext()), \
             patch('installed_native_updaters.run_delegated_update', return_value={'status': 'triggered_unconfirmed', 'verified': False}) as execute:
            outcome, code = runtime._execute_action('fixture-plan', 'vendor', action, lease=SimpleNamespace(action_id=action['action_id']))
            self.assertTrue(execute.call_args.kwargs['authorize']())
        self.assertEqual(code, 10)
        self.assertEqual(outcome['status'], 'triggered_unconfirmed')

    def test_legacy_hard_failure_preserves_failure_exit(self):
        action = plan_for(target())[0]['actions'][0]
        with patch.object(runtime, 'guard_action', return_value={'allowed': True}), \
             patch.object(runtime, 'TargetLock', return_value=contextlib.nullcontext()), \
             patch('installed_native_updaters.run_delegated_update', return_value={'status': 'update_failed', 'verified': False}):
            outcome, code = runtime._execute_action('fixture-plan', 'vendor', action,
                                                   lease=SimpleNamespace(action_id=action['action_id']))
        self.assertEqual(code, 1)
        self.assertEqual(outcome['status'], 'update_failed')

    def test_prelaunch_guard_denial_is_proved_not_started_and_has_no_recovery_journal(self):
        action = plan_for(target())[0]['actions'][0]
        with patch.object(runtime, 'guard_action', return_value={'allowed': False, 'reason_code': 'source_conflict'}), \
             patch.object(runtime, 'TargetLock', return_value=contextlib.nullcontext()), \
             patch('installed_native_updaters.run_delegated_update') as execute:
            outcome, code = runtime._execute_action('fixture-plan', 'vendor', action,
                lease=SimpleNamespace(action_id='batch'), batch_managed=True)
        self.assertFalse(outcome['mutation_started'])
        execute.assert_not_called()

    def test_google_whole_manager_scope_is_bound_to_concrete_contract_and_approval(self):
        from installed_native_updaters import batch_approval_choice
        app=target('/Applications/Google Chrome.app')
        app.update(name='Google Chrome', bundle_id='com.google.Chrome', team_id='EQHXZ8M8AV')
        app['evidence'][0].update(bundle_id=app['bundle_id'], team_id=app['team_id'])
        action=plan_for(app)[0]['actions'][0]
        self.assertEqual(action['whole_registered_manager_scope'], 'google')
        self.assertEqual(batch_approval_choice(action), 'allow_update_same_source')
        action.pop('whole_registered_manager_scope')
        self.assertIsNone(batch_approval_choice(action))

    def test_scoped_mau_can_update_only_selected_office_ids_without_touching_unselected_apps(self):
        from installed_native_updaters import legacy_group_members
        actions=[]
        for name in ['Microsoft Excel','Microsoft Word']:
            app=target('/Applications/'+name+'.app')
            app.update(name=name,bundle_id='com.microsoft.'+name.split()[-1],team_id='UBF8T346G9')
            app['evidence'][0].update(bundle_id=app['bundle_id'],team_id=app['team_id'])
            actions.append(plan_for(app)[0]['actions'][0])
        with patch.dict(os.environ, {'MAC_UPDATE_LEGACY_GROUP_ACTION_IDS': __import__('json').dumps([actions[0]['action_id']])}), \
             patch.object(runtime,'load_plan',return_value={'actions':actions}), \
             patch.object(runtime,'guard_action',return_value={'allowed':True}):
            selected=legacy_group_members('plan',actions[0]['action_id'],'batch')
        self.assertEqual([a['action_id'] for a in selected],[actions[0]['action_id']])

    def test_deepseek_is_explicit_manual_and_open_design_is_explicit_unsupported(self):
        for name, expected_kind, expected_reason in [('DeepSeek Harness','manual','deepseek_manual_only'),
                                                     ('Open Design','unsupported','unsupported_automatic_method')]:
            app=target('/Applications/'+name+'.app')
            app.update(name=name,bundle_id='fixture.'+name.replace(' ',''))
            plan, policies, res=plan_for(app,None)
            self.assertEqual(plan['actions'][0]['kind'],expected_kind)
            self.assertIn(expected_reason,plan['actions'][0]['reason_codes'])

    def test_denied_revalidation_has_zero_launches_and_releases_unstarted_lease(self):
        from installed_native_updaters import run_delegated_update
        with tempfile.TemporaryDirectory() as tmp:
            state = str(Path(tmp).resolve() / 'state')
            action = plan_for(target())[0]['actions'][0]
            lease = claim_action_resources(action, state)
            with patch('installed_native_updaters.subprocess.Popen') as spawn:
                result = run_delegated_update(action, lease, authorize=lambda: False)
            spawn.assert_not_called()
            self.assertEqual(result['status'], 'deferred_by_user')
            self.assertEqual(pending_sessions(state), [])

    def _pending(self, root):
        from installed_native_updaters import run_delegated_update
        path = root / 'Claude.app'; path.mkdir()
        app = target(str(path))
        action = plan_for(app)[0]['actions'][0]
        state = str(root / 'state')
        lease = claim_action_resources(action, state)
        with patch('installed_native_updaters.subprocess.Popen'):
            result = run_delegated_update(action, lease, authorize=lambda: True)
        return state, action, result['native_session_id']

    def test_recovery_requires_human_attestation_and_fresh_same_signed_identity(self):
        from installed_native_updaters import reconcile_delegated_update
        with tempfile.TemporaryDirectory() as tmp:
            state, action, session = self._pending(Path(tmp).resolve())
            current = dict(action['expected_target'], resolution=action['expected_resolution'])
            with patch.object(runtime, 'reobserve_action', return_value=current) as observe:
                self.assertFalse(reconcile_delegated_update(session, state_dir=state))
                observe.assert_not_called()
                changed = dict(current, team_id='OTHER12345')
                observe.return_value = changed
                self.assertFalse(reconcile_delegated_update(session, state_dir=state, confirmed=True))
                self.assertEqual(len(pending_sessions(state)), 1)
                observe.return_value = current
                self.assertTrue(reconcile_delegated_update(session, state_dir=state, confirmed=True))
            self.assertEqual(pending_sessions(state), [])
            journal = next((Path(state) / 'delegated-native').glob('*.json')).read_text()
            self.assertIn('user_reported_vendor_finished', journal)
            self.assertNotIn('live', journal)

    def test_recovery_cli_defaults_cancel_and_never_accepts_closed_stdin(self):
        from installed_native_updaters import native_recovery_cli
        class TTY(io.StringIO):
            def isatty(self): return True
        with tempfile.TemporaryDirectory() as tmp:
            state, action, session = self._pending(Path(tmp).resolve())
            for stream in [io.StringIO('1\nFINISHED\n'), TTY('\n'), TTY('1\n\n')]:
                with patch('installed_native_updaters.select.select', side_effect=lambda inputs, *a: (inputs, [], [])):
                    self.assertEqual(native_recovery_cli(state_dir=state, stream=stream, output=io.StringIO()), 10)
                self.assertEqual(len(pending_sessions(state)), 1)
            with patch.dict(os.environ, {'MAC_UPDATE_YES': '1'}):
                self.assertEqual(native_recovery_cli(state_dir=state, stream=TTY('1\nFINISHED\n'), output=io.StringIO()), 10)
                self.assertEqual(len(pending_sessions(state)), 1)

    def test_wrapper_refuses_missing_python_without_executing_a_developer_tool_shim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            for folder in ('scripts', 'lib', 'i18n', 'bin'):
                (root / folder).mkdir()
            shutil.copyfile(Path(__file__).resolve().parents[1] / 'scripts/reconcile_native.sh', root / 'scripts/reconcile_native.sh')
            (root / 'lib/platform.sh').write_text('mac_update_tool_usable() { return 1; }\n')
            (root / 'i18n/loader.sh').write_text('L_CATALOG_PYTHON_REQUIRED="fixture Python unavailable"\n')
            shim = root / 'bin/python3'
            shim.write_text('#!/bin/sh\ntouch "'+str(root / 'shim-ran')+'"\n')
            shim.chmod(0o755)
            result = subprocess.run(['bash', str(root / 'scripts/reconcile_native.sh')],
                                    env=dict(os.environ, PATH=str(root / 'bin')+':/usr/bin:/bin'),
                                    capture_output=True, text=True, stdin=subprocess.DEVNULL)
            self.assertEqual(result.returncode, 2)
            self.assertIn('fixture Python unavailable', result.stderr)
            self.assertFalse((root / 'shim-ran').exists())

    def test_recovery_cli_releases_only_selected_session_after_explicit_tty_confirmation(self):
        from installed_native_updaters import native_recovery_cli
        class TTY(io.StringIO):
            def isatty(self): return True
        with tempfile.TemporaryDirectory() as tmp:
            state, action, session = self._pending(Path(tmp).resolve())
            current = dict(action['expected_target'], resolution=action['expected_resolution'])
            with patch('installed_native_updaters.select.select', side_effect=lambda inputs, *a: (inputs, [], [])), \
                 patch.object(runtime, 'reobserve_action', return_value=current):
                self.assertEqual(native_recovery_cli(state_dir=state, stream=TTY('1\nFINISHED\n'), output=io.StringIO()), 0)
            self.assertEqual(pending_sessions(state), [])


if __name__ == '__main__':
    unittest.main()
