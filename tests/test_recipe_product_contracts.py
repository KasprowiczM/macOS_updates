"""Actual catalog source contracts and historical parser fixtures, no live acceptance."""
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib' / 'python'))
from channel_probes import load_channel_sources, _parse
from channel_advisor import recommend_channel
from setup_catalog import load_setup_catalog, build_catalog_view
from source_resolver import resolve_target
from app_recipes import load_verified_recipes
from recipe_acceptance import validate_recipe_evidence
import vendor_feeds

NOW = '2026-11-14T00:00:00Z'
ENV = dict(os_version='26.0', architecture='arm64')
FIXTURES = ROOT / 'tests' / 'fixtures'


class ProductContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.products = load_channel_sources()['products']
        cls.evidence = {r['key']:r for r in json.loads((ROOT/'docs/catalog/SOURCE_RESEARCH_EVIDENCE.json').read_text())['observations']}
        cls.catalog = load_setup_catalog()
        cls.verified = load_verified_recipes(str(ROOT/'config/verified_recipes.json'))

    def contract(self, product):
        path=FIXTURES/'recipes'/product['product_id']/'contract.json'
        self.assertTrue(path.is_file(), 'missing actual product contract: '+product['product_id'])
        return json.loads(path.read_text())

    def parsed(self, product, source, body):
        return _parse(product, source, dict(body=json.dumps(body)), ENV, NOW)

    def test_every_actual_product_contract_matches_manifest_and_remains_manual(self):
        view = build_catalog_view(dict(environment=ENV), self.catalog, [], {})
        by_id={r['product_id']:r for r in view['rows']}
        source_urls={r['product_id']:{s['source_id']:s.get('official_url') for s in r['sources']}
                     for r in self.catalog['recipes']}
        files={p.parent.name for p in (FIXTURES/'recipes').glob('*/contract.json')}
        self.assertEqual(files,{p['product_id'] for p in self.products})
        for product in self.products:
            with self.subTest(product=product['product_id']):
                contract=self.contract(product)
                self.assertEqual(contract['product_id'],product['product_id'])
                self.assertEqual(contract['edition'],product['edition'])
                self.assertEqual(contract['version_comparison_policy'],product['version_comparison_policy'])
                self.assertEqual([s['manifest'] for s in contract['sources']],product['sources'])
                for source in contract['sources']:
                    self.assertIn('official_url',source)
                    self.assertEqual(source['official_url'],source_urls[product['product_id']][source['manifest']['source_id']])
                self.assertEqual(by_id[product['product_id']]['installation_status'],'manual')
                self.assertEqual(by_id[product['product_id']]['evidence_level'],'metadata_only')

    def test_real_captured_source_metadata_obeys_product_specific_parsers(self):
        for product in self.products:
            if product['product_id']=='deepseek-harness-gui':continue
            for spec in self.contract(product)['sources']:
                source=spec['manifest']; record=self.evidence.get(source['evidence_key'],{})
                metadata=record.get('metadata')
                with self.subTest(product=product['product_id'],source=source['source_id']):
                    if spec['expected']['decision']=='parser_unreviewed':
                        with self.assertRaisesRegex(ValueError,'parser_unreviewed'):
                            self.parsed(product,source,metadata if isinstance(metadata,dict) else {})
                        continue
                    if source['parser']=='app_store_mac':
                        # The existing evidence is a projection without kind.
                        # Do not invent a mac-software declaration to make it pass.
                        with self.assertRaisesRegex(ValueError,'store_identity_or_platform_unverified'):
                            self.parsed(product,source,dict(results=metadata))
                        continue
                    observations=self.parsed(product,source,metadata)
                    self.assertEqual([r['version'] for r in observations],spec['expected']['versions'])
                    self.assertEqual([r['stable_confirmed'] for r in observations],spec['expected']['stable_confirmed'])
                    self.assertTrue(all(r['availability']!='offered' for r in observations))
                    advice=recommend_channel(product,observations,None,{})
                    self.assertIsNone(advice['actually_offered'])
                    for identity in ('edition','product_id'):
                        foreign=[dict(r,**{identity:'unmatched-fixture-identity'}) for r in observations]
                        rejected=recommend_channel(product,foreign,None,{})
                        self.assertIsNone(rejected['recommended_source_id'])
                        self.assertIsNone(rejected['latest_global_stable'])
                    if source['parser']=='brew_cask':
                        bad=dict(metadata,token='unrelated-fixture-token')
                        with self.assertRaisesRegex(ValueError,'manager_identity_changed'):
                            self.parsed(product,source,bad)
                    elif source['parser']=='github_release':
                        prerelease=json.loads((FIXTURES/'channels/github_prerelease.json').read_text())
                        rejected=self.parsed(product,source,prerelease)
                        self.assertFalse(rejected[0]['stable_confirmed'])
                        self.assertIsNone(recommend_channel(product,rejected,None,{})['latest_global_stable'])
                    elif source['parser']=='open_design':
                        unavailable=self.parsed(product,source,dict(metadata,failedPlatforms=['mac_arm64']))
                        self.assertEqual(unavailable[0]['availability'],'unavailable')
                        self.assertIsNone(recommend_channel(product,unavailable,None,{})['recommended_source_id'])
                    elif source['parser']=='json_path':
                        unreviewed=dict(source,stable_policy='unknown')
                        self.assertFalse(self.parsed(product,unreviewed,metadata)[0]['stable_confirmed'])

    def test_product_metadata_and_names_never_establish_local_ownership_or_migration(self):
        for product in self.products:
            if product['product_id']=='deepseek-harness-gui':continue
            contract=self.contract(product)
            target=dict(target=dict(kind='app',id='fixture-'+product['product_id']),
                instance_id='fixture-'+product['product_id'], product_id=product['product_id'],
                name=product['name'],edition=product['edition'], real_path='/fixture/Unverified.app',
                bundle_id=None,team_id=None,presence='present',freshness='fresh',channel='stable',
                evidence=[dict(kind='public_source_metadata',url=s['manifest']['url']) for s in contract['sources']])
            resolution=resolve_target(target,dict(instances=[target],packages=[],os_version='26.0'),self.verified)
            with self.subTest(product=product['product_id']):
                self.assertEqual(resolution['source'],'unknown')
                self.assertEqual(resolution['capability'],'inventory_only')
                self.assertIsNone(resolution['adapter_id'])
                installed=dict(product_id=product['product_id'],edition=product['edition'],source_id='conflict')
                observations=[]
                for spec in contract['sources']:
                    if spec['expected']['decision']!='parsed':continue
                    source=spec['manifest']; observations.extend(self.parsed(product,source,self.evidence[source['evidence_key']]['metadata']))
                advice=recommend_channel(product,observations,installed,{})
                self.assertIsNone(advice['recommended_source_id'])
                self.assertIn('source_conflict',advice['reason_codes'])

    def test_supported_historical_product_parser_fixtures_do_not_certify_runtime(self):
        for product in self.products:
            if product['product_id']=='deepseek-harness-gui':continue
            for case in self.contract(product)['historical_parser_fixtures']:
                with self.subTest(product=product['product_id'],fixture=case['path']):
                    text=(FIXTURES/case['path']).read_text()
                    parser=getattr(vendor_feeds,case['parser'])
                    payload=json.loads(text) if case['format']=='json' else text
                    result=parser(payload,**case.get('kwargs',{}))
                    self.assertEqual(result if isinstance(result,str) else result['version'],case['version'])
                    row=next(r for r in self.catalog['recipes'] if r['product_id']==product['product_id'])
                    self.assertIsNone(row['install_adapter'])
                    self.assertFalse(any(product['product_id'] in r['matrix_ids'] for r in self.verified['recipes']))
                    if case.get('checksum_inadequate'):
                        self.assertFalse(bool(re.fullmatch('[a-fA-F0-9]{64}',result.get('checksum') or '')))

    def test_proton_rollout_and_firefox_preview_keep_their_actual_product_contracts(self):
        for product in self.products:
            if product['product_id'] not in ('proton-mail-gui','proton-drive-gui'):continue
            source=next(s for s in product['sources'] if s['source_id']=='vendor')
            body=json.loads((FIXTURES/'channels/proton_stable_rollout.json').read_text())
            rows=self.parsed(product,source,body)
            self.assertEqual([(r['version'],r['availability']) for r in rows],[('3.0','staged'),('2.0','listed')])
            advice=recommend_channel(product,rows,None,{})
            self.assertIsNone(advice['actually_offered'])
            self.assertIn('staged_rollout',advice['uncertainty'])
        firefox=next(p for p in self.products if p['product_id']=='firefox-developer-edition-gui')
        source=next(s for s in firefox['sources'] if s['source_id']=='vendor')
        rows=self.parsed(firefox,source,self.evidence[source['evidence_key']]['metadata'])
        self.assertEqual(rows[0]['version'],'161.0b3')
        self.assertFalse(rows[0]['stable_confirmed'])
        self.assertIsNone(recommend_channel(firefox,rows,None,{})['latest_global_stable'])

    def test_deepseek_contract_exercises_exclusion_only(self):
        product=next(p for p in self.products if p['product_id']=='deepseek-harness-gui')
        self.contract(product)
        # No DeepSeek metadata or historical parser fixture is consumed here.
        result=validate_recipe_evidence(dict(product='DeepSeek Harness',matrix_ids=[product['product_id']]),'update',{})
        self.assertFalse(result['allowed'])
        self.assertIn('product_excluded_pending_stable',result['reasons'])


if __name__=='__main__':unittest.main()
