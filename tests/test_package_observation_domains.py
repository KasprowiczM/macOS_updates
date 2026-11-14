"""Exact existing receipt observations survive unrelated partial manager scans."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib/python'))
from inventory_collect import Providers, collect_snapshot
from inventory_providers import read_brew_receipts, read_cli_manifests
from source_resolver import resolve_snapshot
from update_plan import build_plan, authorize_action
import policy_runtime as runtime


class PackageObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def write_json(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))

    def plan(self, providers):
        snapshot = collect_snapshot([], providers, None)
        now = runtime.utc_now()
        policies = dict(profile_id=snapshot['profile_id'], decisions=[], installed_updates=dict(
            enabled=True, scope='same_source_existing_only', confirmed_at=now))
        plan = build_plan(snapshot, resolve_snapshot(snapshot, {'recipes': []}), policies, now)
        return snapshot, plan, policies

    def assert_fresh_guard(self, action, policies):
        with patch.object(runtime, '_running', return_value=False), \
             patch.object(runtime, '_recipe_catalog', return_value={'recipes': []}):
            current = runtime.reobserve_action(action)
        self.assertEqual(current['freshness'], 'fresh')
        self.assertTrue(authorize_action(action, current, policies, runtime.utc_now())['allowed'])

    def test_formula_receipt_survives_an_unrelated_cellar_alias_through_fresh_guard(self):
        receipt = self.root / 'Cellar/healthy/1/INSTALL_RECEIPT.json'
        self.write_json(receipt, {})
        (self.root / 'Cellar/alias').symlink_to(self.root / 'Cellar/healthy')
        providers = Providers(list_brew=read_brew_receipts, brew_prefixes=[str(self.root)])
        snapshot, plan, policies = self.plan(providers)
        source = snapshot['sources']['brew:' + str(self.root)]
        self.assertEqual(source['status'], 'partial')
        self.assertFalse(source['complete'])
        self.assertFalse(source['formula_domain_complete'])
        self.assertEqual(plan['actions'][0]['reason_codes'], [])
        self.assert_fresh_guard(plan['actions'][0], policies)
        receipt.unlink()
        after = collect_snapshot([], providers, snapshot)
        self.assertEqual(after['packages'][0]['presence'], 'unobserved')
        self.assertEqual(after['packages'][0]['freshness'], 'stale')

    def test_npm_manifest_survives_an_unrelated_leftover_directory_through_fresh_guard(self):
        self.write_json(self.root / 'lib/node_modules/tool/package.json', {'name': 'tool', 'version': '1'})
        (self.root / 'lib/node_modules/.staging-leftover').mkdir()
        snapshot, plan, policies = self.plan(Providers(list_cli=read_cli_manifests, cli_prefixes=[str(self.root)]))
        self.assertEqual(snapshot['sources']['cli:' + str(self.root)]['status'], 'partial')
        self.assertEqual(plan['actions'][0]['reason_codes'], [])
        self.assert_fresh_guard(plan['actions'][0], policies)

    def test_incomplete_selected_formula_token_never_gets_receipt_scope_authority(self):
        self.write_json(self.root / 'Cellar/healthy/1/INSTALL_RECEIPT.json', {})
        broken = self.root / 'Cellar/healthy/2/INSTALL_RECEIPT.json'
        broken.parent.mkdir(parents=True)
        broken.write_text('invalid json')
        snapshot, plan, policies = self.plan(Providers(list_brew=read_brew_receipts, brew_prefixes=[str(self.root)]))
        self.assertEqual(snapshot['packages'][0]['freshness'], 'stale')
        self.assertIn('scan_partial', plan['actions'][0]['reason_codes'])

    def test_receipt_scope_requires_exact_receipt_evidence_and_provider_proof(self):
        self.write_json(self.root / 'Cellar/healthy/1/INSTALL_RECEIPT.json', {})
        (self.root / 'Cellar/alias').symlink_to(self.root / 'Cellar/healthy')
        observed = read_brew_receipts(str(self.root))
        for mutate in (lambda source: source.update(complete_package_receipts=[]),
                       lambda source: source['items'][0].update(installed_receipt=str(self.root / 'other')),
                       lambda source: source['items'][0]['evidence'][0].update(prefix='/other'),
                       lambda source: source['items'].append(dict(name='invalid', evidence='bad'))):
            with self.subTest(mutation=mutate):
                source = copy.deepcopy(observed)
                mutate(source)
                snapshot, plan, policies = self.plan(Providers(list_brew=lambda prefix: source, brew_prefixes=[str(self.root)]))
                self.assertEqual(snapshot['packages'][0]['freshness'], 'stale')
                self.assertTrue(plan['actions'][0]['reason_codes'])

    def test_npm_regular_finder_metadata_is_not_a_package_but_a_link_is_unknown(self):
        self.write_json(self.root / 'lib/node_modules/tool/package.json', {'name': 'tool', 'version': '1'})
        metadata = self.root / 'lib/node_modules/.DS_Store'
        metadata.write_bytes(b'fixture')
        self.assertEqual(read_cli_manifests(str(self.root))['status'], 'ok')
        metadata.unlink()
        metadata.symlink_to(self.root / 'outside')
        self.assertEqual(read_cli_manifests(str(self.root))['status'], 'partial')


if __name__ == '__main__':
    unittest.main()
