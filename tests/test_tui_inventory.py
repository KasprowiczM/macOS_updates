"""Inventory controls change only private policy in isolated fixture state."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from inventory_collect import Providers, collect_snapshot
from inventory_providers import read_brew_receipts
from inventory_store import save_snapshot
from policy_runtime import load_policies, save_policies
from tui_inventory import load_inventory, save_selection, load_catalog, prepare_catalog_selection
from user_policy import make_decision, record_decision

ROOT = Path(__file__).resolve().parents[1]


class InventoryViewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.state = self.root / 'state'
        self.prefix = self.root / 'brew'
        for name in ('Zulu', 'Alpha'):
            receipt = self.prefix / 'Cellar' / name / '1.0' / 'INSTALL_RECEIPT.json'
            receipt.parent.mkdir(parents=True)
            receipt.write_text('{"installed_on_request": true}')
        snapshot = collect_snapshot([], Providers(list_brew=read_brew_receipts, brew_prefixes=[str(self.prefix)]), None)
        save_snapshot(self.state, snapshot, 0)

    def test_saved_rows_are_sorted_and_no_host_scan_or_write_occurs(self):
        before = {p.name: p.read_bytes() for p in self.state.iterdir()}
        with patch('subprocess.run', side_effect=AssertionError('no host scan')):
            model = load_inventory(ROOT, self.state)
        self.assertEqual([r['name'] for r in model['rows']], ['Alpha', 'Zulu'])
        self.assertTrue(all(r['source'] == 'homebrew' for r in model['rows']))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.state.iterdir()})

    def test_exclude_persists_and_reenable_does_not_restore_prior_grant(self):
        model = load_inventory(ROOT, self.state)
        action = model['plan']['actions'][0]
        policies = record_decision(make_decision(action['expected_target'], action['expected_resolution'],
                                  'allow_update_same_source', 'manager_update', model['plan']['created_at']),
                                  {'profile_id': model['plan']['profile_id']})
        save_policies(policies, self.state)
        model = load_inventory(ROOT, self.state)
        row = model['rows'][0]
        inventory_before = (self.state / 'inventory.json').read_bytes()
        save_selection(model, {row['id']: False}, self.state)
        model = load_inventory(ROOT, self.state)
        row = next(r for r in model['rows'] if r['name'] == row['name'])
        self.assertEqual(row['status'], 'excluded')
        save_selection(model, {row['id']: True}, self.state)
        model = load_inventory(ROOT, self.state)
        row = next(r for r in model['rows'] if r['name'] == row['name'])
        self.assertTrue(row['enabled'])
        self.assertIn('consent_required', row['reasons'])
        self.assertEqual((self.state / 'inventory.json').read_bytes(), inventory_before)
        self.assertFalse(any(d['choice'].startswith('allow_') for d in load_policies(self.state)['decisions']))

    def test_stale_policy_revision_is_not_overwritten(self):
        model = load_inventory(ROOT, self.state)
        save_selection(model, {model['rows'][0]['id']: False}, self.state)
        before = (self.state / 'policy.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'policy_changed'):
            save_selection(model, {model['rows'][1]['id']: False}, self.state)
        self.assertEqual(before, (self.state / 'policy.json').read_bytes())

    def test_stale_snapshot_is_rejected(self):
        model = load_inventory(ROOT, self.state)
        changed = copy.deepcopy(model)
        changed['plan']['snapshot_id'] = 'stale'
        with self.assertRaisesRegex(ValueError, 'inventory_changed'):
            save_selection(changed, {model['rows'][0]['id']: False}, self.state)
        self.assertFalse((self.state / 'policy.json').exists())

    def test_unknown_action_and_non_boolean_choice_are_rejected(self):
        model = load_inventory(ROOT, self.state)
        for changes in ({'foreign': False}, {model['rows'][0]['id']: 'yes'}):
            with self.assertRaises(ValueError):
                save_selection(model, changes, self.state)
        self.assertFalse((self.state / 'policy.json').exists())

    def test_missing_inventory_returns_empty_model_without_creating_state(self):
        missing = self.root / 'absent'
        self.assertEqual(load_inventory(ROOT, missing)['rows'], [])
        self.assertFalse(missing.exists())

    def test_catalog_uses_saved_personal_inventory_without_host_scan_or_selection(self):
        before = {p.name:p.read_bytes() for p in self.state.iterdir()}
        with patch('subprocess.run', side_effect=AssertionError('no host scan')):
            model = load_catalog(ROOT, self.state)
        self.assertGreater(len(model['rows']), 0)
        self.assertTrue(all(row['selected'] is False for row in model['rows']))
        self.assertEqual(model['snapshot']['profile_id'], load_inventory(ROOT, self.state)['plan']['profile_id'])
        self.assertEqual(before, {p.name:p.read_bytes() for p in self.state.iterdir()})

    def test_catalog_cannot_prepare_without_explicit_selection_and_source(self):
        model = load_catalog(ROOT, self.state)
        for selected, sources, reason in ((set(), {}, 'catalog_selection_empty'),
                                          ({model['rows'][0]['product_id']}, {}, 'catalog_source_required')):
            with self.assertRaisesRegex(ValueError, reason):
                prepare_catalog_selection(model, selected, sources)
        self.assertFalse((self.state/'install-plans').exists())
