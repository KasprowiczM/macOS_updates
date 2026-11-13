"""Consent binds installation and source, while ordinary versions may change."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib/python'))
import user_policy as policy

NOW = '2026-11-13T12:00:00Z'
TARGET = dict(package_id='pkg1', manager='npm', prefix='/fixture/npm', installed_receipt='/fixture/npm/lib/node_modules/tool/package.json', source_identity='tool', version='1', channel='stable', presence='present', freshness='fresh', evidence=[dict(kind='npm', name='tool', prefix='/fixture/npm', manifest_path='/fixture/npm/lib/node_modules/tool/package.json')])
RESOLUTION = dict(target=dict(kind='package', id='pkg1'), source='npm', capability='native_managed', adapter_id=None, evidence_grade='confirmed', candidate_sources=['npm'], reason_codes=[])

def decision(choice='allow_update_same_source', scope='manager_update', target=None, resolution=None):
    return policy.make_decision(target or TARGET, resolution or RESOLUTION, choice, scope, NOW)

class UserPolicyTests(unittest.TestCase):
    def test_record_lookup_and_version_only_change(self):
        store = policy.record_decision(decision(), {})
        target = dict(TARGET, version='2')
        self.assertEqual(policy.get_decision(target, RESOLUTION, store, NOW)['choice'], 'allow_update_same_source')
        self.assertEqual(store['revision'], 1)
    def test_identity_and_source_changes_invalidate(self):
        d = decision()
        for key, value in [('prefix', '/other'), ('source_identity', 'other'), ('channel', 'beta'), ('installed_receipt', None)]:
            with self.subTest(key=key):
                self.assertFalse(policy.decision_is_valid(d, dict(TARGET, **{key:value}), RESOLUTION, NOW))
        self.assertFalse(policy.decision_is_valid(d, TARGET, dict(RESOLUTION, source='homebrew'), NOW))
    def test_preserve_source_never_grants_update(self):
        d = decision('preserve_source')
        self.assertFalse(policy.permits(d, 'manager_update'))
    def test_scope_does_not_expand(self):
        d = decision()
        self.assertTrue(policy.permits(d, 'manager_update'))
        self.assertFalse(policy.permits(d, 'direct_update'))
        self.assertFalse(policy.permits(d, 'native_launch'))
    def test_defer_defaults_to_seven_days_and_expires(self):
        d = decision('defer')
        self.assertEqual(d['expires_at'], '2026-11-20T12:00:00Z')
        self.assertTrue(policy.decision_is_valid(d, TARGET, RESOLUTION, NOW))
        self.assertFalse(policy.decision_is_valid(d, TARGET, RESOLUTION, '2026-11-20T12:00:00Z'))
    def test_ignore_is_explicit_and_can_be_replaced(self):
        store = policy.record_decision(decision('ignore'), {})
        self.assertEqual(policy.get_decision(TARGET, RESOLUTION, store, NOW)['choice'], 'ignore')
        store = policy.record_decision(decision(), store)
        self.assertEqual(len(store['decisions']), 1)
        self.assertEqual(store['revision'], 2)
    def test_unknown_choice_and_scope_are_rejected(self):
        for choice, scope in [('install', 'manager_update'), ('allow_native_launch', 'manager_update'), ('allow_update_same_source', 'native_launch')]:
            with self.assertRaises(ValueError): decision(choice, scope)
    def test_conflict_evidence_change_reopens_choice(self):
        r = dict(RESOLUTION, source='conflict', candidate_sources=['npm', 'homebrew'], reason_codes=['conflicting_sources'])
        d = decision('defer', resolution=r)
        self.assertFalse(policy.decision_is_valid(d, TARGET, RESOLUTION, NOW))
