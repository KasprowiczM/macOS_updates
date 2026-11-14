"""Saved agreement and target-specific source checks use fixtures only."""
import copy
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'lib/python'))
import policy_runtime as runtime
import user_policy as policy
from source_resolver import resolve_target
from update_plan import build_plan,authorize_action
import plan_orchestration as planner
from test_installed_native_updaters import target,NOW


def fixture(app=None, agreement=True):
    app=copy.deepcopy(app or target())
    snapshot=dict(snapshot_id='fixture',profile_id='p1',generation=0,instances=[app],packages=[],sources={})
    resolution=resolve_target(app,snapshot,{'recipes':[]})
    policies=dict(schema_version=1,revision=1,profile_id='p1',decisions=[],installed_updates=dict(
        enabled=agreement,scope='same_source_existing_only',allow_registered_vendor_groups=True,confirmed_at=NOW))
    return app,snapshot,resolution,policies


class InstalledUpdateDefaultsTests(unittest.TestCase):
    class TTY(io.StringIO):
        def isatty(self):return True

    def test_first_run_agreement_is_single_explicit_default_cancel_prompt(self):
        stream=self.TTY('ENABLE\n')
        with patch.dict(os.environ,{'MAC_UPDATE_YES':'0','MAC_UPDATE_NONINTERACTIVE':'0'}), \
             patch.object(planner.select,'select',return_value=([stream],[],[])):
            self.assertTrue(planner.review_installed_update_agreement(stream,io.StringIO()))
        self.assertFalse(planner.review_installed_update_agreement(io.StringIO('ENABLE\n'),io.StringIO()))
        with patch.dict(os.environ,{'MAC_UPDATE_YES':'1'}):
            self.assertFalse(planner.review_installed_update_agreement(self.TTY('ENABLE\n'),io.StringIO()))

    def test_agreement_input_failure_does_not_grant_permission(self):
        with patch.dict(os.environ,{'MAC_UPDATE_YES':'0','MAC_UPDATE_NONINTERACTIVE':'0'}), \
             patch.object(planner.select,'select',side_effect=OSError('unavailable')):
            self.assertFalse(planner.review_installed_update_agreement(self.TTY('ENABLE\n'),io.StringIO()))

    def test_profile_agreement_cannot_authorize_a_different_inventory_profile(self):
        app,snapshot,res,policies=fixture()
        with self.assertRaisesRegex(ValueError,'policy_profile_mismatch'):
            build_plan(dict(snapshot,profile_id='p2'),[res],policies,NOW)

    def test_saved_agreement_skips_repeated_batch_approval_and_never_defers_saved_authority(self):
        app,snapshot,res,policies=fixture()
        plan=build_plan(snapshot,[res],policies,NOW)
        with tempfile.TemporaryDirectory() as session, \
             patch.dict(os.environ,{'MAC_UPDATE_AUTOMATIC_INTERNET_BATCH':'1'}), \
             patch.object(planner,'load_policies',return_value=policies), \
             patch.object(planner,'refresh_inventory'), \
             patch('update_transaction.recover_pending_transactions',return_value=[]), \
             patch.object(planner,'build_runtime_plan',return_value=plan), \
             patch.object(planner,'review_internet_batch') as batch, \
             patch.object(planner,'review_choices',return_value={}), \
             patch.object(planner,'emit_plan'),patch.object(planner,'save_plan') as saved:
            self.assertEqual(planner.prepare_run('/fixture',session,self.TTY(''),io.StringIO()),0)
        batch.assert_not_called()
        self.assertEqual(saved.call_args.args[0]['actions'][0]['reason_codes'],[])

    def test_first_agreement_acceptance_rebuilds_permissions_without_the_old_fifty_action_prompt(self):
        app,snapshot,res,policies=fixture()
        plan=build_plan(snapshot,[res],dict(policies,installed_updates={}),NOW)
        stream=self.TTY('ENABLE\n')
        with tempfile.TemporaryDirectory() as session, \
             patch.dict(os.environ,{'MAC_UPDATE_AUTOMATIC_INTERNET_BATCH':'1','MAC_UPDATE_YES':'0','MAC_UPDATE_NONINTERACTIVE':'0'}), \
             patch.object(planner,'load_policies',return_value={}), \
             patch.object(planner,'set_installed_update_default',return_value=policies) as setter, \
             patch.object(planner.select,'select',return_value=([stream],[],[])), \
             patch.object(planner,'refresh_inventory'),patch('update_transaction.recover_pending_transactions',return_value=[]), \
             patch.object(planner,'build_runtime_plan',return_value=plan), \
             patch.object(planner,'review_internet_batch') as batch, \
             patch.object(planner,'review_choices',return_value={}) as ordinary, \
             patch.object(planner,'emit_plan'),patch.object(planner,'save_plan') as saved:
            self.assertEqual(planner.prepare_run('/fixture',session,stream,io.StringIO()),0)
        setter.assert_called_once_with(True,allow_registered_vendor_groups=True)
        batch.assert_not_called()
        self.assertEqual(ordinary.call_args.args[0]['actions'][0]['reason_codes'],[])
        self.assertEqual(saved.call_args.args[0]['actions'][0]['reason_codes'],[])

    def test_saved_agreement_updates_fresh_installed_target_without_per_app_grants(self):
        app,snapshot,res,policies=fixture()
        plan=build_plan(snapshot,[res],policies,NOW)
        action=plan['actions'][0]
        self.assertNotIn('consent_required',action['reason_codes'])
        self.assertTrue(authorize_action(action,dict(app,resolution=res),policies,NOW)['allowed'])
        self.assertEqual(policies['decisions'],[])
        changed=dict(app,real_path='/Applications/Other.app',resolution=res)
        self.assertFalse(authorize_action(action,changed,policies,NOW)['allowed'])

    def test_no_agreement_and_unknown_capability_still_require_permission_or_evidence(self):
        app,snapshot,res,policies=fixture(agreement=False)
        self.assertIn('consent_required',build_plan(snapshot,[res],policies,NOW)['actions'][0]['reason_codes'])
        policies['installed_updates']['enabled']=True
        res=dict(res,capability='inventory_only',adapter_id=None)
        self.assertEqual(build_plan(snapshot,[res],policies,NOW)['actions'][0]['kind'],'manual')

    def test_raw_inventory_exclusion_survives_signature_enrichment_without_relaxing_allow_authority(self):
        app,snapshot,res,policies=fixture()
        raw=dict(app,team_id=None,evidence=[])
        raw_resolution=dict(target=res['target'],source='unknown',capability='inventory_only',adapter_id=None,candidate_sources=[])
        denial=policy.make_decision(raw,raw_resolution,'ignore','local_observation',NOW)
        for existing in (denial,{k:v for k,v in denial.items() if k!='deny_binding'}):
            with self.subTest(legacy='deny_binding' not in existing):
                policies['decisions']=[existing]
                action=build_plan(snapshot,[res],policies,NOW)['actions'][0]
                self.assertEqual(action['kind'],'skip')
                self.assertIn('ignored_by_policy',action['reason_codes'])
                self.assertFalse(authorize_action(action,dict(app,resolution=res),policies,NOW)['allowed'])
        grant=policy.make_decision(raw,raw_resolution,'allow_native_launch','delegated_native_update',NOW)
        self.assertFalse(policy.decision_is_valid(grant,app,res,NOW))
        self.assertFalse(policy.deny_decision_matches(denial,dict(app,real_path='/Applications/Other.app'),NOW))
        self.assertFalse(policy.deny_decision_matches(denial,dict(app,instance_id='another'),NOW))

    def test_saved_manual_ignore_and_active_deferral_override_profile_default(self):
        app,snapshot,res,policies=fixture()
        for choice,reason in [('preserve_source','manual_by_policy'),('ignore','ignored_by_policy'),('defer','deferred_by_user')]:
            policies['decisions']=[policy.make_decision(app,res,choice,'delegated_native_update',NOW)]
            action=build_plan(snapshot,[res],policies,NOW)['actions'][0]
            self.assertIn(reason,action['reason_codes'])
            self.assertFalse(authorize_action(action,dict(app,resolution=res),policies,NOW)['allowed'])

    def test_package_default_cannot_bypass_an_excluded_related_app(self):
        from source_resolver import resolve_snapshot
        app,snapshot,res,policies=fixture()
        claim=dict(kind='homebrew',token='claude',prefix='/fixture/brew',
                   installed_receipt='/fixture/brew/Caskroom/claude/1/receipt.json',artifact_path=app['real_path'])
        app['evidence']=[claim]
        package=dict(package_id='cask',manager='homebrew',source_identity='cask:claude',
                     prefix='/fixture/brew',installed_receipt=claim['installed_receipt'],
                     presence='present',freshness='fresh',channel='stable',version='1',
                     related_instance_ids=[app['instance_id']],evidence=[claim],running=False)
        snapshot['packages']=[package]
        resolutions=resolve_snapshot(snapshot,{'recipes':[]})
        app_resolution=next(r for r in resolutions if r['target']['kind']=='app')
        package_resolution=next(r for r in resolutions if r['target']['kind']=='package')
        for choice,reason in [('preserve_source','manual_by_policy'),('ignore','ignored_by_policy'),('defer','deferred_by_user')]:
            policies['decisions']=[policy.make_decision(app,app_resolution,choice,'manager_update',NOW)]
            action=build_plan(snapshot,resolutions,policies,NOW)['actions'][1]
            self.assertIn(reason,action['reason_codes'])
            current=dict(package,resolution=package_resolution)
            self.assertFalse(authorize_action(action,current,policies,NOW)['allowed'])
            # Even a malformed action kind cannot use the package default to
            # evade an exclusion on an app within its observed effect scope.
            self.assertFalse(authorize_action(dict(action,kind='update',reason_codes=[]),current,policies,NOW)['allowed'])

    def test_agreement_setter_binds_profile_and_preserves_denials_without_creating_per_app_grants(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=str(Path(tmp).resolve()/'state')
            app,snapshot,res,policies=fixture(agreement=False)
            policies.pop('installed_updates')
            policies['decisions']=[policy.make_decision(app,res,'ignore','delegated_native_update',runtime.utc_now())]
            runtime.save_policies(policies,state)
            with patch.object(runtime,'load_snapshot',return_value={'profile_id':'p1'}):
                updated=runtime.set_installed_update_default(True,state,allow_registered_vendor_groups=True)
            self.assertTrue(updated['installed_updates']['enabled'])
            self.assertEqual(updated['profile_id'],'p1')
            self.assertEqual(updated['decisions'],policies['decisions'])
            self.assertEqual(updated['revision'],2)

    def test_missing_brew_prefix_and_unrelated_partial_metadata_do_not_stale_a_signed_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();prefix=root/'brew';(prefix/'Caskroom/other/1.0').mkdir(parents=True)
            app,snapshot,res,policies=fixture()
            action=build_plan(snapshot,[res],policies,NOW)['actions'][0]
            for source in [dict(status='unavailable',complete=False,items=[],reason_code='manager_metadata_missing'),
                           dict(status='partial',complete=False,items=[],reason_code='manager_metadata_incomplete')]:
                with patch.dict(os.environ,{'MAC_UPDATE_BREW_PREFIXES':str(prefix)+':'+str(root/'missing')}), \
                     patch.object(runtime,'_current_app',return_value=copy.deepcopy(app)), \
                     patch.object(runtime,'read_brew_receipts',return_value=source), \
                     patch.object(runtime,'_running',return_value=False):
                    current=runtime.reobserve_action(action)
                self.assertEqual(current['freshness'],'fresh')
                self.assertTrue(authorize_action(action,current,policies,NOW)['allowed'])

    def test_incomplete_receipt_cannot_hide_a_cask_link_claiming_the_selected_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();appdir=root/'Applications/Claude.app';appdir.mkdir(parents=True)
            prefix=root/'brew';staged=prefix/'Caskroom/claude/1.0/Claude.app';staged.parent.mkdir(parents=True);staged.symlink_to(appdir)
            app,snapshot,res,policies=fixture(target(str(appdir)))
            action=build_plan(snapshot,[res],policies,NOW)['actions'][0]
            with patch.dict(os.environ,{'MAC_UPDATE_BREW_PREFIXES':str(prefix)}), \
                 patch.object(runtime,'_current_app',return_value=copy.deepcopy(app)), \
                 patch.object(runtime,'read_brew_receipts',return_value=dict(status='partial',complete=False,items=[])), \
                 patch.object(runtime,'_running',return_value=False):
                current=runtime.reobserve_action(action)
            self.assertEqual(current['freshness'],'stale')
            self.assertFalse(authorize_action(action,current,policies,NOW)['allowed'])

    def test_ownership_probe_is_bounded_and_unreadable_or_linked_roots_remain_unknown(self):
        from installed_native_updaters import probe_brew_app_ownership
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();prefix=root/'brew';room=prefix/'Caskroom'
            (room/'other/1').mkdir(parents=True)
            target_path=str(root/'Applications/Claude.app')
            self.assertEqual(probe_brew_app_ownership(str(prefix),target_path,max_entries=0),'unknown')
            with patch('installed_native_updaters.os.lstat',side_effect=PermissionError('fixture')):
                self.assertEqual(probe_brew_app_ownership(str(prefix),target_path),'unknown')
            with patch('installed_native_updaters.os.scandir',side_effect=PermissionError('fixture')):
                self.assertEqual(probe_brew_app_ownership(str(prefix),target_path),'unknown')
            room.rename(prefix/'real-casks');room.symlink_to(prefix/'real-casks')
            self.assertEqual(probe_brew_app_ownership(str(prefix),target_path),'unknown')


if __name__=='__main__':unittest.main()
