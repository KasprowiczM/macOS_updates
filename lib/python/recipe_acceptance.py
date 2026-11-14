"""Pure, fail-closed evidence matching for immutable recipe candidates.

This module performs no discovery, network requests or process execution. Its
caller owns trustworthy local observations, consent, and the trusted catalog.
Synthetic fixtures cannot establish a public live acceptance claim.
"""

import hashlib
import json

from app_recipes import _date, _os, validate_recipe


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                                     allow_nan=False).encode('utf-8')).hexdigest()


def recipe_fingerprint(recipe):
    """Bind all execution facts, excluding only the evidence being signed off."""
    return _digest({key: value for key, value in recipe.items() if key != 'acceptance_records'})


# Retained as a descriptive alias for callers building evidence records.
recipe_hash = recipe_fingerprint


def candidate_binding(candidate):
    """Bind version AND build, bytes, host, source, channel and feed sequence."""
    return _digest(candidate)


def requirements_fingerprint(recipe):
    return _digest(recipe['requirement_graph'])


def _version(value):
    if not isinstance(value, str) or len(value) > 255:
        return None
    parts = value.split('.')
    if any(not part.isascii() or not part.isdigit() for part in parts):
        return None
    parsed = tuple(int(part) for part in parts)
    while len(parsed) > 1 and parsed[-1] == 0:
        parsed = parsed[:-1]
    return parsed


def _rollback(candidate, previous):
    if type(previous) is not dict:
        return True
    if any(candidate[key] != previous.get(key) for key in
           ('product', 'edition', 'bundle_id', 'team_id', 'installation_source', 'channel', 'architecture')):
        return True
    sequence = previous.get('feed_sequence')
    if type(sequence) is not int or sequence < 0:
        return True
    if candidate['feed_sequence'] < sequence:
        return True
    if candidate['feed_sequence'] == sequence and candidate_binding(candidate) != candidate_binding(previous):
        return True
    old_version, new_version = _version(previous.get('version')), _version(candidate['version'])
    if old_version is None or new_version is None:
        # No generic ordering for RC/beta/nightly. An identical candidate is
        # safe; any changed prerelease needs a separately established baseline.
        return candidate_binding(candidate) != candidate_binding(previous)
    if new_version < old_version:
        return True
    return old_version == new_version and any(
        candidate[key] != previous.get(key) for key in ('build', 'sha256')
    )


def _record_matches(row, recipe, operation, environment, permissions):
    try:
        age = (_date(environment.get('now')) - _date(row['recorded_at'])).total_seconds()
        return (
            row['kind'] == 'live' and row['result'] == 'passed'
            and row['operation'] == operation and not row['limitations']
            and 0 <= age <= recipe['limits']['maximum_evidence_age_days'] * 86400
            and row['recipe_revision'] == recipe['revision']
            and row['recipe_sha256'] == recipe_fingerprint(recipe)
            and row['candidate_sha256'] == candidate_binding(recipe['candidate'])
            and row['artifact_sha256'] == recipe['candidate']['sha256']
            and row['requirements_sha256'] == requirements_fingerprint(recipe)
            and row['os_version'] == environment.get('os_version')
            and row['architecture'] == environment.get('architecture')
            and permissions.issubset(row['permissions'])
            and set(row['permissions']).issubset(environment.get('granted_permissions', []))
            and set(row['effect_scope']) == set(recipe['effect_scope'][operation])
        )
    except (ValueError, TypeError, KeyError):
        return False


def _candidate_observed(recipe, observation):
    if type(observation) is not dict:
        return False
    candidate = recipe['candidate']
    return (
        observation.get('signature_valid') is True
        and observation.get('app_store_receipt') is (recipe['installation_source'] == 'app_store')
        and observation.get('artifact_sha256') == candidate['sha256']
        and all(observation.get(key) == candidate[key] for key in
                ('bundle_id', 'team_id', 'version', 'build', 'architecture', 'minimum_os'))
    )


def validate_recipe_evidence(recipe, operation, environment):
    """Return allowed/reasons/evidence_ids for one explicitly scoped operation.

    This is one authorization predicate, not an updater or a consent generator.
    Call again immediately before mutation using refreshed observations. The
    runtime must still enforce source ownership, lifecycle policy and a verified
    postflight matching the declared observation contract.
    """
    reasons = []
    result = dict(allowed=False, reasons=reasons, evidence_ids=[])
    if type(recipe) is dict:
        names = [recipe.get('product'), recipe.get('id')]
        if type(recipe.get('matrix_ids')) is list:
            names.extend(recipe['matrix_ids'])
        if any(type(name) is str and name.casefold().replace('-', '').replace(' ', '').startswith('deepseek')
               for name in names):
            reasons.append('product_excluded_pending_stable')
    try:
        validate_recipe(recipe)
    except (ValueError, TypeError, KeyError, RecursionError):
        reasons.append('recipe_invalid')
        return result
    if type(operation) is not str or operation not in ('update', 'install', 'lifecycle'):
        reasons.append('operation_invalid')
        return result
    if type(environment) is not dict:
        reasons.append('environment_invalid')
        return result
    target = environment.get('target')
    if type(target) is not dict:
        target = {}
    if operation == 'install':
        if type(environment.get('candidate_observation')) is not dict:
            reasons.append('candidate_observation_required')
        elif not _candidate_observed(recipe, environment['candidate_observation']):
            reasons.append('candidate_observation_mismatch')
    else:
        if (target.get('product') != recipe['product'] or target.get('edition') != recipe['edition']
                or target.get('bundle_id') != recipe['candidate']['bundle_id']
                or target.get('team_id') != recipe['candidate']['team_id']):
            reasons.append('target_identity_mismatch')
        if target.get('signature_valid') is not True:
            reasons.append('signature_unverified')
        if target.get('installation_source') != recipe['installation_source']:
            reasons.append('installation_source_mismatch')
        if target.get('app_store_receipt') is not False and recipe['installation_source'] != 'app_store':
            reasons.append('app_store_receipt_conflict')
        if recipe['installation_source'] == 'app_store' and target.get('app_store_receipt') is not True:
            reasons.append('app_store_receipt_unverified')
    if operation in ('update', 'lifecycle') and target.get('presence') != 'present':
        reasons.append('target_not_present')
    if operation == 'install' and target.get('presence') != 'absent':
        reasons.append('install_target_not_absent')
    if operation != 'install' and target.get('channel') != recipe['channel']:
        reasons.append('channel_mismatch')
    if not recipe['effect_scope'][operation]:
        reasons.append('operation_effects_undeclared')
    try:
        if (_os(environment.get('os_version')) < _os(recipe['candidate']['minimum_os'])
                or environment.get('architecture') != recipe['candidate']['architecture']):
            reasons.append('environment_incompatible')
    except (ValueError, TypeError):
        reasons.append('environment_incompatible')
    try:
        if (type(environment.get('candidate')) is not dict
                or candidate_binding(environment['candidate']) != candidate_binding(recipe['candidate'])):
            reasons.append('candidate_binding_mismatch')
        if 'previous_candidate' in environment and _rollback(recipe['candidate'], environment['previous_candidate']):
            reasons.append('candidate_rollback_or_replacement')
        if (environment.get('approved_recipe_sha256') != recipe_fingerprint(recipe)
                or environment.get('approved_candidate_sha256') != candidate_binding(recipe['candidate'])
                or environment.get('approved_requirements_sha256') != requirements_fingerprint(recipe)):
            reasons.append('approval_binding_mismatch')
    except (ValueError, TypeError, OverflowError, RecursionError):
        reasons.append('candidate_binding_mismatch')
    permissions = set()
    dependencies = set()
    for node in recipe['requirement_graph']['nodes']:
        if operation in node['operations']:
            (permissions if node['kind'] == 'permission' else dependencies).add(node['value'])
    try:
        granted = environment.get('granted_permissions')
        available = environment.get('available_requirements')
        effects = environment.get('granted_effects')
        if (type(granted) is not list or any(type(x) is not str for x in granted)
                or type(available) is not list or any(type(x) is not str for x in available)
                or not permissions.issubset(granted) or not dependencies.issubset(available)):
            reasons.append('requirements_not_authorized')
        if (type(effects) is not list or any(type(x) is not str for x in effects)
                or not set(recipe['effect_scope'][operation]).issubset(effects)):
            reasons.append('effect_scope_not_authorized')
    except (ValueError, TypeError):
        reasons.append('requirements_not_authorized')
    matching = [row['id'] for row in recipe['acceptance_records'][operation]
                if _record_matches(row, recipe, operation, environment, permissions)]
    if not matching:
        reasons.append('live_acceptance_required')
    if not reasons:
        result.update(allowed=True, evidence_ids=matching)
    return result
