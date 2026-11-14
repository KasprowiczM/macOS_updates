"""Research coverage and synthetic safety contracts, never product acceptance."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib' / 'python'))
from app_recipes import load_verified_recipes
from recipe_acceptance import validate_recipe_evidence
from recipe_adapters import prepare_recipe_action
from source_resolver import resolve_target
from update_transaction import prepare_transaction, TransactionDeferred
from vendor_feeds import version_compare
from test_recipe_acceptance import recipe, record, environment

FIXTURES = ROOT / 'tests' / 'fixtures' / 'recipes'


class ProductFixtureMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.products = json.loads((ROOT / 'config' / 'channel_sources.json').read_text())['products']
        cls.catalog = load_verified_recipes(str(ROOT / 'config' / 'verified_recipes.json'))

    def load(self, product):
        return json.loads((FIXTURES / product['product_id'] / 'scenarios.json').read_text())

    def synthetic(self, product):
        value = recipe()
        value['id'] = 'fixture-' + product['product_id']
        value['product'] = 'Synthetic ' + product['product_id']
        value['candidate']['product'] = value['product']
        value['matrix_ids'] = [product['product_id']]
        value['acceptance_records']['update'] = [record(value, kind='fixture')]
        env = environment(value)
        env['target']['product'] = value['product']
        env['target'].update(short_version='1.0', build='100', running=False, freshness='fresh')
        return value, env

    def test_all_catalog_products_have_safety_fixtures_and_no_recipe_authority(self):
        expected = {p['product_id'] for p in self.products}
        observed = {p.parent.name for p in FIXTURES.glob('*/scenarios.json')}
        self.assertEqual(observed, expected)
        for product in self.products:
            data = self.load(product)
            with self.subTest(product=product['product_id']):
                self.assertEqual(data['product_id'], product['product_id'])
                self.assertFalse(any(product['product_id'] in r['matrix_ids'] for r in self.catalog['recipes']))

    def test_each_scenario_exercises_real_fail_closed_predicates(self):
        for product in self.products:
            if product['product_id'] == 'deepseek-harness-gui':
                continue
            data = self.load(product)
            for scenario in data['scenarios']:
                with self.subTest(product=product['product_id'], scenario=scenario['id']):
                    value, env = self.synthetic(product)
                    for key, changes in scenario.get('environment', {}).items():
                        if type(changes) is dict and type(env.get(key)) is dict:
                            env[key].update(changes)
                        else:
                            env[key] = copy.deepcopy(changes)
                    result = validate_recipe_evidence(value, 'update', env)
                    self.assertFalse(result['allowed'], result)
                    self.assertEqual(result['evidence_ids'], [])
                    for reason in scenario['expected_reasons']:
                        self.assertIn(reason, result['reasons'])
                    target = dict(env['target'], real_path='/fixture/Applications/Example.app')
                    self.assertFalse(prepare_recipe_action(value, target, 'update', env)['allowed'])
                    if 'version_comparison' in scenario:
                        pair = scenario['version_comparison']
                        self.assertEqual(version_compare(pair['candidate'], pair['installed']), pair['expected'])
                    self.check_resolver(product, scenario)
                    if scenario['id'] == 'running':
                        self.check_running_transaction()

    def check_resolver(self, product, scenario):
        ref = dict(kind='app', id='fixture-' + product['product_id'])
        target = dict(target=ref, instance_id=ref['id'], name=product['name'],
                      real_path='/fixture/Applications/Example.app', bundle_id=None, team_id=None,
                      presence='present', freshness='fresh', channel='stable', evidence=[])
        snapshot = dict(instances=[target], packages=[], os_version='15.1')
        resolver_case = scenario.get('resolver_case')
        if resolver_case == 'absent':
            target['presence'] = 'absent'
        elif resolver_case == 'duplicate':
            target['bundle_id'] = 'org.example.fixture'
            snapshot['instances'].append(dict(target, target=dict(kind='app', id='fixture-duplicate'), instance_id='fixture-duplicate'))
        elif resolver_case == 'source_conflict':
            target['evidence'] = [dict(kind='app_store_receipt'), dict(kind='homebrew',
                token='fixture-token', prefix='/fixture/homebrew', installed_receipt=True,
                artifact_path=target['real_path'])]
        elif resolver_case == 'crash':
            target.update(source_status='error', source_complete=False)
        resolved = resolve_target(target, snapshot, self.catalog)
        self.assertEqual(resolved['capability'], 'inventory_only', resolved)
        self.assertIsNone(resolved['adapter_id'])
        if scenario.get('expected_resolver_reason'):
            self.assertIn(scenario['expected_resolver_reason'], resolved['reason_codes'])

    def check_running_transaction(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root).resolve() / 'Fixture.app'; path.mkdir()
            action = dict(target_path=str(path), action_scope='direct_update',
                          target=dict(kind='app', id='fixture'), action_id='fixture')
            current = dict(path=str(path), presence='present', freshness='fresh', running=True)
            with self.assertRaisesRegex(TransactionDeferred, 'running_or_unknown'):
                prepare_transaction(action, current)
            self.assertEqual(list(path.iterdir()), [])

    def test_deepseek_is_deferred_by_real_acceptance_guard(self):
        product = next(p for p in self.products if p['product_id'] == 'deepseek-harness-gui')
        self.load(product)
        value, env = self.synthetic(product)
        result = validate_recipe_evidence(value, 'update', env)
        self.assertFalse(result['allowed'])
        self.assertIn('product_excluded_pending_stable', result['reasons'])
        self.assertEqual(result['evidence_ids'], [])


if __name__ == '__main__':
    unittest.main()
