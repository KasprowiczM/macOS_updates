"""Synthetic evidence only: no fixture record constitutes live acceptance."""

import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib', 'python'))
import app_recipes
try:
    import recipe_acceptance as acceptance
except ImportError:
    acceptance = None

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'recipes', 'valid_v2.json')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def recipe():
    with open(FIXTURE) as handle:
        return json.load(handle)


def recipe_digest(value):
    return digest({k: v for k, v in value.items() if k != 'acceptance_records'})


def environment(value):
    return dict(
        target=dict(product='Fixture Editor', edition='community', bundle_id='org.example.fixture',
                    team_id='EXAMPL1234', installation_source='vendor', channel='stable',
                    presence='present', signature_valid=True, app_store_receipt=False),
        candidate=copy.deepcopy(value['candidate']), os_version='15.1', architecture='arm64',
        granted_permissions=['replace_existing_app'], granted_effects=['replace_existing_app'],
        available_requirements=[], approved_recipe_sha256=recipe_digest(value),
        approved_candidate_sha256=digest(value['candidate']),
        approved_requirements_sha256=digest(value['requirement_graph']), now='2026-11-14T00:00:00Z')


def record(value, operation='update', kind='live', **changes):
    result = dict(id='synthetic-' + operation, recorded_at='2026-11-13T00:00:00Z',
                  recipe_revision=value['revision'], recipe_sha256=recipe_digest(value),
                  candidate_sha256=digest(value['candidate']), artifact_sha256=value['candidate']['sha256'],
                  operation=operation, kind=kind, result='passed', os_version='15.1', architecture='arm64',
                  permissions=['replace_existing_app'], effect_scope=value['effect_scope'][operation][:],
                  requirements_sha256=digest(value['requirement_graph']), limitations=[],
                  redacted_traces=['Synthetic unit test evidence. No application was run.'])
    result.update(changes)
    return result


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(callable(getattr(app_recipes, 'load_verified_recipes', None)),
                        'strict schema-v2 loader is missing')

    def load(self, data):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, 'recipes.json')
            with open(path, 'w') as handle:
                handle.write(data if isinstance(data, str) else json.dumps(data))
            return app_recipes.load_verified_recipes(path)

    def catalog(self, value=None):
        return dict(schema_version=2, metadata=dict(status='evidence_required', matrix_ids=['fixture-editor'],
                    excluded_products=['DeepSeek']), recipes=[value or recipe()])

    def test_loads_strict_v2_and_keeps_v1_separate(self):
        self.assertEqual(self.load(self.catalog())['recipes'][0]['revision'], 1)
        with self.assertRaises(ValueError):
            self.load(dict(schema_version=1, recipes=[]))
        with tempfile.NamedTemporaryFile(mode='w') as handle:
            json.dump(self.catalog(), handle); handle.flush()
            with self.assertRaises(ValueError):
                app_recipes.load_recipes(handle.name)

    def test_unknown_and_executable_fields_rejected(self):
        for field in ('command', 'shell', 'name', 'post_install'):
            value = recipe(); value[field] = 'echo forbidden'
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.load(self.catalog(value))

    def test_rejects_wrong_scalar_and_collection_types(self):
        for field, bad in [('revision', True), ('revision', 0), ('minimum_os', None),
                           ('bundle_ids', []), ('architectures', ['x86_64']), ('download_hosts', ['*.example.org']),
                           ('acceptance_records', []), ('effect_scope', {'update': ['launch_app']})]:
            value = recipe(); value[field] = bad
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.load(self.catalog(value))

    def test_rejects_candidate_beyond_declared_identity(self):
        for field, bad in [('bundle_id', 'org.other'), ('team_id', 'OTHER12345'),
                           ('product', 'Other Product'), ('installation_source', 'app_store'),
                           ('url', 'https://attacker.example/file.zip'), ('url', 'https://downloads.example.org@attacker.example/file.zip'),
                           ('channel', 'beta'), ('architecture', 'x86_64'), ('minimum_os', None),
                           ('sha256', 'x'*64), ('feed_sequence', True)]:
            value = recipe(); value['candidate'][field] = bad
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.load(self.catalog(value))

    def test_rejects_duplicates_nonfinite_and_oversized_json(self):
        for text in ('{"schema_version":2,"schema_version":2,"metadata":{},"recipes":[]}',
                     '{"schema_version":NaN,"metadata":{},"recipes":[]}', ' ' * (1024*1024+1)):
            with self.subTest(text=text[:40]), self.assertRaises(ValueError):
                self.load(text)

    def test_requirements_reject_cycles_missing_edges_and_hidden_effects(self):
        for graph in [dict(nodes=[], edges=[{'from':'missing','to':'absent'}]),
                      dict(nodes=[dict(id='a', kind='permission', value='replace_existing_app', operations=['update'])],
                           edges=[{'from':'a','to':'a'}]),
                      dict(nodes=[dict(id='a', kind='dependency', value='extra-tool', operations=['update'])], edges=[])]:
            value = recipe(); value['requirement_graph'] = graph
            with self.subTest(graph=graph), self.assertRaises(ValueError):
                self.load(self.catalog(value))

    def test_rejects_update_scope_install_migration_and_lifecycle(self):
        for effect in ('install_app', 'install_dependency', 'change_source', 'change_channel', 'restart_session', 'launch_app'):
            value = recipe(); value['effect_scope']['update'].append(effect)
            with self.subTest(effect=effect), self.assertRaises(ValueError):
                self.load(self.catalog(value))

    def test_record_requires_redacted_traces_and_exact_fields(self):
        for field, bad in [('recipe_revision', True), ('recorded_at', 'yesterday'), ('artifact_sha256','bad'),
                           ('redacted_traces', []), ('permissions', 'admin'), ('kind','mock-live'),
                           ('operation','install'), ('result', True)]:
            value = recipe(); row = record(value); row[field] = bad; value['acceptance_records']['update'] = [row]
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.load(self.catalog(value))

    def test_container_values_in_scalar_fields_are_rejected_as_value_errors(self):
        for field in ('adapter_id', 'installation_source', 'channel', 'update_mechanism'):
            value = recipe(); value[field] = []
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.load(self.catalog(value))

    def test_team_identity_has_exact_apple_identifier_length(self):
        value = recipe(); value['team_ids'] = ['EXAMPLE1234']
        value['candidate']['team_id'] = 'EXAMPLE1234'
        with self.assertRaises(ValueError):
            self.load(self.catalog(value))

    def test_hash_excludes_records_but_binds_every_execution_fact(self):
        self.assertIsNotNone(acceptance, 'evidence validator is missing')
        value = recipe(); expected = recipe_digest(value)
        self.assertEqual(acceptance.recipe_fingerprint(value), expected)
        value['acceptance_records']['update'].append(record(value))
        self.assertEqual(acceptance.recipe_fingerprint(value), expected)
        value['candidate']['build'] = '201'
        self.assertNotEqual(acceptance.recipe_fingerprint(value), expected)

    def test_shipped_catalog_has_no_live_accepted_recipe(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'config', 'verified_recipes.json')
        data = app_recipes.load_verified_recipes(path)
        self.assertFalse(data['recipes'])
        self.assertIn('DeepSeek', data['metadata']['excluded_products'])
        with open(os.path.join(os.path.dirname(__file__), '..', 'config', 'channel_sources.json')) as handle:
            matrix = {product for row in json.load(handle)['registry_rows'] for product in row['product_ids']}
        self.assertEqual(set(data['metadata']['matrix_ids']), matrix)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(acceptance, 'evidence validator is missing')
        self.value = recipe()
        self.env = environment(self.value)
        self.value['acceptance_records']['update'] = [record(self.value)]

    def validate(self, operation='update'):
        return acceptance.validate_recipe_evidence(self.value, operation, self.env)

    def denied(self, reason, operation='update'):
        result = self.validate(operation)
        self.assertFalse(result['allowed'], result)
        self.assertIn(reason, result['reasons'])
        self.assertEqual(result['evidence_ids'], [])

    def test_exact_synthetic_record_can_pass_pure_validator(self):
        result = self.validate()
        self.assertEqual(result, dict(allowed=True, reasons=[], evidence_ids=['synthetic-update']))

    def test_name_never_establishes_identity(self):
        self.env['target'] = dict(name='Fixture Editor', presence='present')
        self.denied('target_identity_mismatch')

    def test_foreign_signature_product_and_source_rejected(self):
        for field, bad, reason in [('team_id','OTHER12345','target_identity_mismatch'),
                                  ('product','Other Product','target_identity_mismatch'),
                                  ('edition','enterprise','target_identity_mismatch'),
                                  ('signature_valid',False,'signature_unverified'),
                                  ('installation_source','homebrew','installation_source_mismatch')]:
            with self.subTest(field=field):
                self.env = environment(self.value); self.env['target'][field] = bad; self.denied(reason)

    def test_candidate_cannot_replace_another_allowed_bundle_or_signer(self):
        for key, list_key, alternative in [('bundle_id', 'bundle_ids', 'org.example.variant'),
                                           ('team_id', 'team_ids', 'OTHER12345')]:
            with self.subTest(field=key):
                self.value = recipe(); self.value[list_key].append(alternative)
                self.value['acceptance_records']['update'] = [record(self.value)]
                self.env = environment(self.value); self.env['target'][key] = alternative
                self.denied('target_identity_mismatch')

    def test_prior_feed_identity_cannot_cross_product_or_channel(self):
        for key, alternative in [('product', 'Other Product'), ('channel', 'beta'),
                                  ('bundle_id', 'org.example.other'), ('installation_source', 'homebrew')]:
            with self.subTest(field=key):
                self.env = environment(self.value)
                self.env['previous_candidate'] = dict(self.value['candidate'], feed_sequence=1, **{key:alternative})
                self.denied('candidate_rollback_or_replacement')

    def test_empty_scope_never_authorizes_a_lifecycle_operation(self):
        self.value['acceptance_records']['lifecycle'] = [record(self.value, operation='lifecycle')]
        self.denied('operation_effects_undeclared', 'lifecycle')

    def test_appstore_receipt_cannot_be_used_on_external_route(self):
        self.env['target']['app_store_receipt'] = True
        self.denied('app_store_receipt_conflict')

    def test_update_never_installs_absent_app(self):
        self.env['target']['presence'] = 'absent'
        self.denied('target_not_present')

    def test_unknown_minimum_os_and_incompatible_os_block(self):
        for os_version in (None, '', 'unknown', '12.9'):
            with self.subTest(os_version=os_version):
                self.env['os_version'] = os_version; self.denied('environment_incompatible')

    def test_same_version_with_new_build_or_hash_invalidates_candidate(self):
        for key, value in [('build','201'), ('sha256','b'*64), ('url','https://downloads.example.org/replaced.zip')]:
            with self.subTest(field=key):
                self.env = environment(self.value); self.env['candidate'][key] = value
                self.denied('candidate_binding_mismatch')

    def test_prerelease_rejected_despite_stable_label(self):
        self.env['candidate']['version'] = '2.1-rc.1'
        self.denied('candidate_binding_mismatch')

    def test_feed_rollback_and_same_sequence_replacement_block(self):
        for changes in (dict(feed_sequence=3), dict(sha256='b'*64), dict(build='201'), dict(version='3.0')):
            with self.subTest(changes=changes):
                self.env['previous_candidate'] = dict(self.value['candidate'], **changes)
                self.denied('candidate_rollback_or_replacement')

    def test_lower_version_even_at_newer_sequence_blocks(self):
        self.env['previous_candidate'] = dict(self.value['candidate'], version='3.0', feed_sequence=1)
        self.denied('candidate_rollback_or_replacement')

    def test_approval_binds_requirements_revision_and_candidate(self):
        for field in ('approved_recipe_sha256', 'approved_candidate_sha256', 'approved_requirements_sha256'):
            with self.subTest(field=field):
                self.env = environment(self.value); self.env[field] = '0'*64
                self.denied('approval_binding_mismatch')

    def test_requirements_change_after_consent_blocks(self):
        self.value['requirement_graph']['nodes'][0]['value'] = 'write_application'
        self.denied('approval_binding_mismatch')

    def test_missing_live_evidence_not_promoted_from_fixture(self):
        for kind in ('fixture',):
            self.value['acceptance_records']['update'][0]['kind'] = kind
            self.denied('live_acceptance_required')
        self.value['acceptance_records']['update'] = []
        self.denied('live_acceptance_required')

    def test_wrong_revision_hash_os_arch_and_permissions_do_not_match_record(self):
        for field, bad in [('recipe_revision',2), ('recipe_sha256','b'*64), ('candidate_sha256','b'*64),
                           ('artifact_sha256','b'*64), ('os_version','15.2'), ('architecture','x86_64'),
                           ('permissions',[]), ('requirements_sha256','b'*64), ('effect_scope',[]),
                           ('result','failed'), ('limitations',['Interactive prompts unverified'])]:
            with self.subTest(field=field):
                self.value['acceptance_records']['update'] = [record(self.value, **{field:bad})]
                self.denied('live_acceptance_required')

    def test_expired_future_or_unknown_clock_records_block(self):
        for now in ('2026-12-15T00:00:00Z','2026-11-12T00:00:00Z',None):
            with self.subTest(now=now):
                self.env['now'] = now; self.denied('live_acceptance_required')

    def test_operation_records_do_not_cross_authorize(self):
        self.env['target']['presence'] = 'absent'
        self.env['granted_effects'] = ['install_app']
        self.denied('live_acceptance_required', 'install')
        self.env['target']['presence'] = 'present'
        self.env['granted_effects'] = []
        self.denied('live_acceptance_required', 'lifecycle')

    def test_install_uses_signed_staged_candidate_and_actual_absence(self):
        self.value['acceptance_records']['install'] = [record(self.value, operation='install')]
        self.env['target'] = {'presence': 'absent'}
        self.env['granted_effects'] = ['install_app']
        candidate = self.value['candidate']
        self.env['candidate_observation'] = dict(
            bundle_id=candidate['bundle_id'], team_id=candidate['team_id'],
            version=candidate['version'], build=candidate['build'],
            artifact_sha256=candidate['sha256'], architecture=candidate['architecture'],
            minimum_os=candidate['minimum_os'], signature_valid=True, app_store_receipt=False)
        self.assertTrue(self.validate('install')['allowed'])
        for field, bad in [('signature_valid', False), ('bundle_id', 'org.other'),
                           ('team_id', 'OTHER12345'), ('version', '1.0'), ('build', '201'),
                           ('artifact_sha256', 'b'*64), ('architecture', 'x86_64'),
                           ('minimum_os', None), ('app_store_receipt', True)]:
            with self.subTest(field=field):
                original = self.env['candidate_observation'][field]
                self.env['candidate_observation'][field] = bad
                self.denied('candidate_observation_mismatch', 'install')
                self.env['candidate_observation'][field] = original

    def test_install_cannot_invent_a_signature_for_an_absent_target(self):
        self.value['acceptance_records']['install'] = [record(self.value, operation='install')]
        self.env['target']['presence'] = 'absent'
        self.env['granted_effects'] = ['install_app']
        self.denied('candidate_observation_required', 'install')

    def test_granted_effects_and_permissions_required(self):
        self.env['granted_permissions'] = []
        self.denied('requirements_not_authorized')
        self.env = environment(self.value); self.env['granted_effects'] = []
        self.denied('effect_scope_not_authorized')

    def test_malformed_inputs_fail_closed_without_exception(self):
        for bad in (None, [], {}, dict(self.value, revision=True)):
            result = acceptance.validate_recipe_evidence(bad, 'update', self.env)
            self.assertFalse(result['allowed']); self.assertIn('recipe_invalid', result['reasons'])
        self.assertFalse(acceptance.validate_recipe_evidence(self.value, 'shell', self.env)['allowed'])
        self.assertFalse(acceptance.validate_recipe_evidence(self.value, 'update', None)['allowed'])

    def test_deepseek_alias_and_matrix_identity_remain_excluded(self):
        for field, value in [('product', 'DeepSeek Harness'), ('id', 'deepseek-stable'),
                             ('matrix_ids', ['deepseek-harness-gui'])]:
            with self.subTest(field=field):
                self.value = recipe(); self.value[field] = value
                self.denied('product_excluded_pending_stable')

    def test_deepseek_stable_release_not_available_cannot_be_accepted(self):
        self.value['product'] = 'DeepSeek'
        self.denied('product_excluded_pending_stable')


if __name__ == '__main__':
    unittest.main()
