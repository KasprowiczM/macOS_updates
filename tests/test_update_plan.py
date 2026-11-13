"""Pure action-plan guard behavior and immutable scoped snapshots."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib/python'))
from tests.test_user_policy import TARGET, RESOLUTION, NOW, decision
import user_policy
import update_plan

class PlanTests(unittest.TestCase):
    def setup_plan(self, choice='allow_update_same_source'):
        policies = user_policy.record_decision(decision(choice), {})
        snapshot = dict(snapshot_id='snapshot1', profile_id='profile1', generation=1, packages=[copy.deepcopy(TARGET)], instances=[], sources={})
        plan = update_plan.build_plan(snapshot, [RESOLUTION], policies, NOW)
        return snapshot, policies, plan
    def test_approved_manager_action_and_deep_scoped_copy(self):
        snapshot, policies, plan = self.setup_plan()
        a = plan['actions'][0]
        current = dict(TARGET, resolution=RESOLUTION, running=False)
        self.assertTrue(update_plan.authorize_action(a, current, policies, NOW)['allowed'])
        snapshot['packages'][0]['prefix']='/changed'
        self.assertEqual(a['expected_target']['prefix'], '/fixture/npm')
    def test_absent_stale_unknown_conflict_path_identity_removed_running_all_defer(self):
        _, policies, plan = self.setup_plan()
        a = plan['actions'][0]
        base = dict(TARGET, resolution=RESOLUTION, running=False)
        cases = [dict(base, presence='absent'), dict(base, freshness='stale'), dict(base, running=True), dict(base, running=None), dict(base, prefix='/other'), dict(base, source_identity='other'), dict(base, resolution=dict(RESOLUTION, source='unknown')), dict(base, resolution=dict(RESOLUTION, source='conflict')), {}]
        for current in cases:
            with self.subTest(current=current):
                self.assertFalse(update_plan.authorize_action(a, current, policies, NOW)['allowed'])
    def test_old_and_future_plan_and_policy_change_defer(self):
        _, policies, plan=self.setup_plan()
        a=plan['actions'][0]
        current=dict(TARGET, resolution=RESOLUTION, running=False)
        for now in ['2026-11-13T12:15:01Z','2026-11-13T11:59:59Z']:
            self.assertFalse(update_plan.authorize_action(a,current,policies,now)['allowed'])
        changed=user_policy.record_decision(decision('ignore'),policies)
        self.assertFalse(update_plan.authorize_action(a,current,changed,NOW)['allowed'])
    def test_no_consent_is_deferred_even_for_formula_npm_node(self):
        for manager, identity in [('npm','tool'),('homebrew','formula:node'),('unknown','node')]:
            t=dict(TARGET,manager=manager,source_identity=identity)
            r=dict(RESOLUTION,source=manager)
            p=update_plan.build_plan(dict(snapshot_id='s',profile_id='p',generation=0,instances=[],packages=[t],sources={}),[r],{},NOW)
            self.assertFalse(update_plan.authorize_action(p['actions'][0],dict(t,resolution=r,running=False),{},NOW)['allowed'])
    def test_preserve_ignore_and_defer_are_honest_nonmutation_actions(self):
        for choice, expected in [('preserve_source','manual_by_policy'),('ignore','ignored_by_policy'),('defer','deferred_by_user')]:
            _, policies, plan=self.setup_plan(choice)
            self.assertIn(expected,plan['actions'][0]['reason_codes'])
            self.assertFalse(update_plan.authorize_action(plan['actions'][0],dict(TARGET,resolution=RESOLUTION,running=False),policies,NOW)['allowed'])
    def test_scope_mismatch_and_artifact_changes_defer(self):
        _, policies, plan=self.setup_plan()
        a=dict(plan['actions'][0],action_scope='direct_update')
        self.assertFalse(update_plan.authorize_action(a,dict(TARGET,resolution=RESOLUTION,running=False),policies,NOW)['allowed'])
        a=dict(plan['actions'][0],artifact_effects=['/new/app'])
        self.assertFalse(update_plan.authorize_action(a,dict(TARGET,resolution=RESOLUTION,running=False),policies,NOW)['allowed'])
