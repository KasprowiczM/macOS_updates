"""Reviewed cask execution fixtures only; no host managers are invoked."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib/python'))
try:
    import catalog_manager_install as manager
except ImportError:
    manager = None

# A non-host executable sentinel: every invocation is mocked explicitly.
MOCK_BREW = '/fixture/mock-brew'

class CatalogHomebrewTests(unittest.TestCase):
    def setUp(self):
        self.metadata = {'token':'keepassxc', 'version':'2.8.0,2.8.0-1', 'sha256':'a'*64,
                         'auto_updates':False, 'disabled':False, 'deprecated':False,
                         'artifacts':[{'app':['KeePassXC.app']}], 'depends_on':{'macos':{'>=':['12']}}}

    def test_only_reviewed_stable_exact_app_metadata_is_accepted(self):
        self.assertEqual(manager.validate_cask('keepassxc-gui', self.metadata, '2.8.0')['token'], 'keepassxc')
        for change in ({'version':'2.8.0-beta'}, {'auto_updates':True}, {'artifacts':[{'pkg':['evil.pkg']}]},
                       {'sha256':'no_check'}, {'depends_on':{'formula':['other']}}, {'token':'attacker'},
                       {'auto_updates':None}, {'disabled':None}, {'deprecated':None}, {'version':'2.8.0-rc'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                manager.validate_cask('keepassxc-gui', dict(self.metadata, **change), '2.8.0')
        with self.assertRaises(ValueError):
            manager.validate_cask('firefox-developer-edition-gui', self.metadata, '2.8.0')
        with self.assertRaises(ValueError):
            manager.validate_cask('keepassxc-gui', self.metadata, '2.8.1')

    def test_partial_or_present_inventory_cannot_authorize_install(self):
        snapshot = {'sources': {'filesystem:/Applications': {'status':'ok', 'complete':True}}, 'instances':[], 'packages':[]}
        self.assertTrue(manager.snapshot_proves_absence(snapshot, 'keepassxc-gui', '/Applications/KeePassXC.app'))
        for modified in (dict(snapshot, sources={'filesystem:/Applications': {'status':'partial', 'complete':False}}),
                         dict(snapshot, sources={'filesystem:/Applications': {'status':'ok', 'complete':True},
                                                 'homebrew': {'status':'partial', 'complete':False}}),
                         dict(snapshot, packages=None),
                         dict(snapshot, instances=[{'presence':'present','product_id':'keepassxc-gui'}])):
            self.assertFalse(manager.snapshot_proves_absence(modified, 'keepassxc-gui', '/Applications/KeePassXC.app'))


class ManagerDelegationExecutionTests(unittest.TestCase):
    def fixture(self):
        from install_plan import build_install_plan
        from install_execution import make_install_consent
        from policy_runtime import utc_now
        metadata = CatalogHomebrewTests(); metadata.setUp()
        metadata.metadata['tap']='homebrew/cask'
        recipe = dict(product_id='keepassxc-gui', name='KeePassXC', edition='gui',
                      sources=[dict(source_id='homebrew', official_url='https://formulae.brew.sh/cask/keepassxc')],
                      manager_delegation=dict(token='keepassxc', stable_version='2.8.0', reviewed_at=utc_now()),
                      install_adapter='homebrew_cask', installation_source='homebrew', channel='stable',
                      bundle_id='org.keepassxc.keepassxc',
                      version='2.8.0', destination='/Applications/KeePassXC.app',
                      artifact_effects=['/Applications/KeePassXC.app'], requirements=[],
                      permissions=['manager_delegated_install'])
        recipes={'recipes':[recipe]}
        snapshot={'sources':{'filesystem:/Applications':{'status':'ok','complete':True}},
                  'instances':[], 'packages':[], 'environment':{'homebrew':{'satisfied':True}}}
        from unittest.mock import patch
        with patch.object(manager, 'preview_cask', return_value=manager.validate_manager_cask('keepassxc-gui', metadata.metadata, '2.8.0')):
            plan=build_install_plan([dict(product_id='keepassxc-gui', edition='gui', source_id='homebrew')],snapshot,recipes,utc_now())
        consent=make_install_consent(plan,[plan['actions'][0]['action_id']],utc_now())
        return plan,consent,recipes,snapshot,metadata.metadata

    def current(self, plan):
        action=plan['actions'][0]
        return dict(plan_digest=plan['plan_digest'], recipe_fingerprint=action['recipe_fingerprint'],
                    requirement_graph_digest=plan['requirement_graph_digest'], requirements_complete=True,
                    source_conflict=False,presence='absent',destination_symlink=False,
                    canonical_destination=action['destination'])

    def test_selected_explicit_manager_install_verifies_only_manager_receipt(self):
        import tempfile
        from unittest.mock import patch
        from install_execution import execute_install_action
        plan,consent,recipes,snapshot,metadata=self.fixture()
        with tempfile.TemporaryDirectory() as state, patch.object(manager,'trusted_brew',return_value=MOCK_BREW), \
             patch.object(manager,'query_cask',return_value=metadata), patch.object(manager,'refresh_snapshot',return_value=snapshot), patch.object(manager,'target_absent',return_value=True), \
             patch.object(manager,'run_install',return_value=None) as run, \
             patch.object(manager,'verify_receipt',return_value=True), \
             patch('install_execution._current',return_value=self.current(plan)):
            result=execute_install_action(plan,plan['actions'][0]['action_id'],consent,recipes,snapshot['environment'],snapshot=snapshot,state_dir=state)
        self.assertEqual(result['status'],'manager_installed_verified',result)
        self.assertEqual(result['verification_scope'],'homebrew_receipt')
        self.assertFalse(result.get('vendor_artifact_accepted',True))
        self.assertEqual(run.call_args.args,(MOCK_BREW,'keepassxc'))

    def test_guards_prevent_manager_mutation(self):
        import tempfile
        from unittest.mock import patch
        from install_execution import execute_install_action
        for fault in ('no_approval','wrong_source','exists','missing_brew','metadata_change','concurrent','dry_run'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as state:
                plan,consent,recipes,snapshot,metadata=self.fixture()
                if fault=='no_approval': consent['action_ids']=[]
                if fault=='wrong_source': snapshot['instances']=[dict(presence='present',product_id='keepassxc-gui',source_id='vendor')]
                if fault=='metadata_change': metadata=dict(metadata,sha256='b'*64)
                with patch.dict('os.environ',{'MAC_UPDATE_DRY_RUN':'1' if fault=='dry_run' else '0'}), \
                     patch.object(manager,'trusted_brew',side_effect=ValueError('homebrew_missing') if fault=='missing_brew' else None,return_value=MOCK_BREW), \
                     patch.object(manager,'query_cask',return_value=metadata), patch.object(manager,'refresh_snapshot',return_value=snapshot), \
                     patch.object(manager,'target_absent',return_value=fault!='exists'), \
                     patch.object(manager,'run_install') as run, \
                     patch.object(manager,'verify_receipt',return_value=True), \
                     patch('install_execution._current',return_value=self.current(plan)):
                    lease=None
                    if fault=='concurrent':
                        from update_scheduler import claim_action_resources
                        lease=claim_action_resources(dict(action_id='other',scope_complete=False,parallel_safe=False),state)
                    try:
                        result=execute_install_action(plan,plan['actions'][0]['action_id'],consent,recipes,snapshot['environment'],snapshot=snapshot,state_dir=state)
                    finally:
                        if lease: lease.finish('test',helpers_complete=True)
                run.assert_not_called()
                self.assertNotEqual(result['status'],'manager_installed_verified')

class ManagerBindingTests(unittest.TestCase):
    def test_expired_review_returns_catalog_to_manual_without_install_authority(self):
        import datetime
        from unittest.mock import patch
        from setup_catalog import build_catalog_view
        from user_policy import timestamp
        plan,_,recipes,snapshot,_=ManagerDelegationExecutionTests().fixture()
        reviewed=recipes['recipes'][0]['manager_delegation']['reviewed_at']
        expired=(timestamp(reviewed)+datetime.timedelta(days=8)).isoformat()
        eligible=manager.manager_recipe_eligible
        self.assertFalse(eligible(recipes['recipes'][0],expired))
        with patch.object(manager,'manager_recipe_eligible',side_effect=lambda recipe: eligible(recipe,expired)):
            row=build_catalog_view(snapshot,recipes,[],{})['rows'][0]
        self.assertEqual(row['installation_status'],'manual')
        self.assertEqual(row['evidence_level'],'metadata_only')
        self.assertFalse(row['selected'])

    def test_installed_runtime_fields_do_not_change_manager_recipe_binding(self):
        fixture=CatalogHomebrewTests(); fixture.setUp()
        metadata=dict(fixture.metadata,tap='homebrew/cask')
        before=manager.validate_manager_cask('keepassxc-gui',dict(metadata,installed=None),'2.8.0')
        after=manager.validate_manager_cask('keepassxc-gui',dict(metadata,installed='2.8.0,2.8.0-1'),'2.8.0')
        self.assertEqual(before,after)
        for changes in ({'tap':'attacker/cask'}, {'artifacts':[{'pkg':['bad.pkg']}]},
                        {'artifacts':[{'app':['KeePassXC.app']},{'binary':['/tmp/bad'],'target':'/Applications/Other.app'}]}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                manager.validate_manager_cask('keepassxc-gui',dict(metadata,**changes),'2.8.0')

    def test_inaccessible_paths_are_not_absent(self):
        from unittest.mock import patch
        with patch.object(manager.os,'lstat',side_effect=PermissionError(13,'denied')):
            self.assertFalse(manager.target_absent('keepassxc','/Applications/KeePassXC.app'))

    def test_renamed_or_unknown_presence_product_is_not_absent(self):
        snapshot={'sources':{'filesystem:/Applications':{'status':'ok','complete':True}},'instances':[], 'packages':[]}
        for target in ({'bundle_id':'org.keepassxc.keepassxc','path':'/Applications/Renamed.app','presence':'present'},
                       {'product_id':'keepassxc-gui','presence':'unknown'}):
            self.assertFalse(manager.snapshot_proves_absence(dict(snapshot,instances=[target]),'keepassxc-gui','/Applications/KeePassXC.app'))

class ManagerRecoveryTests(unittest.TestCase):
    fixture = ManagerDelegationExecutionTests.fixture
    current = ManagerDelegationExecutionTests.current
    def test_fresh_source_presence_blocks_stale_absent_snapshot(self):
        import tempfile
        from unittest.mock import patch
        from install_execution import execute_install_action
        plan,consent,recipes,snapshot,metadata=self.fixture()
        fresh=copy.deepcopy(snapshot)
        fresh['instances']=[dict(product_id='keepassxc-gui',presence='present',path='/Other/KeePassXC.app')]
        with tempfile.TemporaryDirectory() as state, patch.object(manager,'trusted_brew',return_value=MOCK_BREW), \
             patch.object(manager,'query_cask',return_value=metadata), patch.object(manager,'refresh_snapshot',return_value=fresh), \
             patch.object(manager,'target_absent',return_value=True), patch.object(manager,'run_install') as run, \
             patch('install_execution._current',return_value=self.current(plan)):
            result=execute_install_action(plan,plan['actions'][0]['action_id'],consent,recipes,snapshot['environment'],snapshot=snapshot,state_dir=state)
        run.assert_not_called()
        self.assertEqual(result['reason_code'],'source_absence_unproven')

    def test_spawn_failure_releases_lease_and_completed_failure_can_recover(self):
        import tempfile
        from unittest.mock import patch, Mock
        from install_execution import execute_install_action
        from update_scheduler import pending_sessions
        for spawn_failure in (True, False):
            with self.subTest(spawn_failure=spawn_failure), tempfile.TemporaryDirectory() as state:
                plan,consent,recipes,snapshot,metadata=self.fixture()
                child=Mock(pid=123456,returncode=1)
                child.poll.return_value=1
                with patch.object(manager,'trusted_brew',return_value=MOCK_BREW), \
                     patch.object(manager,'query_cask',return_value=metadata), patch.object(manager,'refresh_snapshot',return_value=snapshot), \
                     patch.object(manager,'target_absent',return_value=True), patch.object(manager,'verify_receipt',return_value=False), \
                     patch('install_execution._current',return_value=self.current(plan)), \
                     patch('subprocess.Popen',side_effect=OSError('spawn failed') if spawn_failure else None,return_value=child), \
                     patch.object(manager,'process_group_complete',return_value=True), \
                     patch('inventory_migration.collect_current_snapshot',return_value=snapshot):
                    result=execute_install_action(plan,plan['actions'][0]['action_id'],consent,recipes,snapshot['environment'],snapshot=snapshot,state_dir=state)
                    if spawn_failure:
                        self.assertEqual(result['status'],'deferred')
                        self.assertEqual(pending_sessions(state),[])
                    else:
                        self.assertEqual(result['status'],'recovery_required')
                        recovered=manager.recover_manager_installations(state)
                        self.assertEqual(recovered[0]['status'],'deferred')
                        self.assertEqual(pending_sessions(state),[])

    def test_live_process_group_stays_pending(self):
        from unittest.mock import patch,Mock
        child=Mock(pid=123456,returncode=1)
        child.poll.return_value=1
        with patch('subprocess.Popen',return_value=child), patch.object(manager,'process_group_complete',return_value=False):
            complete=Mock()
            with self.assertRaisesRegex(ValueError,'manager_helper_unconfirmed'):
                manager.run_install(MOCK_BREW,'keepassxc',record_complete=complete)
            complete.assert_not_called()

    def test_metadata_change_after_install_stays_unconfirmed_until_receipt_reobserved(self):
        import tempfile
        from unittest.mock import patch
        from install_execution import execute_install_action
        from update_scheduler import pending_sessions
        plan,consent,recipes,snapshot,metadata=self.fixture()
        changed=dict(metadata,sha256='b'*64)
        with tempfile.TemporaryDirectory() as state, patch.object(manager,'trusted_brew',return_value=MOCK_BREW), \
             patch.object(manager,'query_cask',side_effect=[metadata,changed]), patch.object(manager,'refresh_snapshot',return_value=snapshot), patch.object(manager,'target_absent',return_value=True), \
             patch.object(manager,'run_install',return_value=None), \
             patch('install_execution._current',return_value=self.current(plan)):
            result=execute_install_action(plan,plan['actions'][0]['action_id'],consent,recipes,snapshot['environment'],snapshot=snapshot,state_dir=state)
            self.assertEqual(result['status'],'recovery_required')
            self.assertFalse(result['verified'])
            self.assertTrue(pending_sessions(state))
            with patch.object(manager,'verify_receipt',return_value=True):
                recovered=manager.recover_manager_installations(state)
            self.assertEqual(recovered[0]['status'],'manager_installed_verified')
            self.assertFalse(recovered[0]['vendor_artifact_accepted'])
            self.assertEqual(pending_sessions(state),[])

    def test_completed_failed_attempt_can_be_reobserved_without_claiming_no_mutation(self):
        import tempfile
        from unittest.mock import patch
        from install_execution import execute_install_action
        from update_scheduler import pending_sessions
        plan,consent,recipes,snapshot,metadata=self.fixture()
        with tempfile.TemporaryDirectory() as state, patch.object(manager,'trusted_brew',return_value=MOCK_BREW), \
             patch.object(manager,'query_cask',return_value=metadata), patch.object(manager,'refresh_snapshot',return_value=snapshot), patch.object(manager,'target_absent',return_value=True), \
             patch.object(manager,'run_install',return_value=None), patch.object(manager,'verify_receipt',return_value=False), \
             patch('install_execution._current',return_value=self.current(plan)), \
             patch('inventory_migration.collect_current_snapshot',return_value=snapshot):
            result=execute_install_action(plan,plan['actions'][0]['action_id'],consent,recipes,snapshot['environment'],snapshot=snapshot,state_dir=state)
            self.assertEqual(result['status'],'recovery_required')
            recovered=manager.recover_manager_installations(state)
            self.assertEqual(recovered[0]['status'],'deferred')
            self.assertEqual(recovered[0]['reason_code'],'manager_attempt_completed_unverified')
            self.assertFalse(recovered[0]['verified'])
            self.assertNotIn('no_mutation',str(recovered))
            self.assertEqual(pending_sessions(state),[])

    def test_manager_command_is_official_selected_cask_without_force_or_shell(self):
        from unittest.mock import patch,Mock
        child=Mock(pid=123456,returncode=0)
        child.poll.return_value=0
        with patch('subprocess.Popen',return_value=child) as popen,patch.object(manager,'process_group_complete',return_value=True):
            manager.run_install(MOCK_BREW,'keepassxc')
        self.assertEqual(popen.call_args.args[0],[MOCK_BREW,'install','--cask','homebrew/cask/keepassxc','--appdir=/Applications'])
        self.assertTrue(popen.call_args.kwargs['start_new_session'])
        self.assertNotIn('shell',popen.call_args.kwargs)

if __name__ == '__main__': unittest.main()
