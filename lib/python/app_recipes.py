"""Bounded, declarative recipe and legacy capability catalog readers."""

import json
import re

_MAX_BYTES = 1024 * 1024
_ADAPTERS = frozenset(
    (
        "keystone",
        "github_dmg",
        "mozilla_dmg",
        "silent_launch",
        "msupdate",
        "mau_fallback_self_update",
        "docker_cli",
        "brew_cask",
        "appstore_gui",
        "manual",
        "sparkle_appcast",
        "chromium_updater",
    )
)
_FIELDS = frozenset(
    (
        "id",
        "adapter_id",
        "bundle_ids",
        "team_ids",
        "channels",
        "architectures",
        "minimum_os",
        "download_hosts",
        "allowed_artifacts",
    )
)
_LISTS = _FIELDS - {"id", "adapter_id", "minimum_os"}


def _read(path):
    with open(path, "rb") as handle:
        data = handle.read(_MAX_BYTES + 1)
    if len(data) > _MAX_BYTES:
        raise ValueError("catalog exceeds size limit")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("invalid UTF-8") from exc


def load_recipes(path):
    try:
        data = json.loads(_read(path), object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("invalid recipe JSON") from exc
    if (
        not isinstance(data, dict)
        or set(data) != {"schema_version", "recipes"}
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or not isinstance(data["recipes"], list)
    ):
        raise ValueError("invalid recipe catalog")
    ids = set()
    for recipe in data["recipes"]:
        if not isinstance(recipe, dict) or set(recipe) != _FIELDS:
            raise ValueError("invalid recipe fields")
        if (
            not isinstance(recipe["id"], str)
            or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,127}", recipe["id"])
            or recipe["id"] in ids
        ):
            raise ValueError("invalid or duplicate recipe id")
        ids.add(recipe["id"])
        if (
            not isinstance(recipe["adapter_id"], str)
            or recipe["adapter_id"] not in _ADAPTERS
        ):
            raise ValueError("unknown adapter")
        for field in _LISTS:
            value = recipe[field]
            if (
                not isinstance(value, list)
                or len(value) > 128
                or any(not isinstance(x, str) or not x or len(x) > 255 for x in value)
                or len(value) != len(set(value))
            ):
                raise ValueError("invalid recipe list: " + field)
        if recipe["minimum_os"] is not None and (
            not isinstance(recipe["minimum_os"], str)
            or not re.fullmatch(r"\d+(?:\.\d+){0,2}", recipe["minimum_os"])
        ):
            raise ValueError("invalid minimum OS")
        if any(x not in ("stable", "beta", "testflight") for x in recipe["channels"]):
            raise ValueError("invalid channel")
        if any(x not in ("arm64", "x86_64") for x in recipe["architectures"]):
            raise ValueError("invalid architecture")
        if any(
            not re.fullmatch(r"[A-Za-z0-9.-]+", x) or ".." in x
            for x in recipe["download_hosts"]
        ):
            raise ValueError("invalid download host")
        if any(
            x not in ("dmg", "pkg", "zip", "app") for x in recipe["allowed_artifacts"]
        ):
            raise ValueError("invalid artifact")
    return data


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def load_legacy_capabilities(path):
    """Read adapter availability only; names never establish local ownership."""
    result = []
    for line in _read(path).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split("|")
        if len(fields) not in (3, 4) or not fields[0] or fields[1] not in _ADAPTERS:
            raise ValueError("invalid legacy adapter row")
        result.append({"name": fields[0], "adapter_id": fields[1]})
    return result


# V2 is deliberately independent of the legacy capability catalog above. A row
# describes a bounded mechanism; it never proves live acceptance or consent.
_OPERATIONS = frozenset(('update', 'install', 'lifecycle'))
_SOURCES = frozenset(('vendor', 'homebrew', 'app_store', 'npm', 'apple_system', 'enterprise_managed'))
_CHANNELS = frozenset(('stable', 'rc', 'beta', 'nightly', 'testflight'))
_V2_FIELDS = frozenset((
    'id', 'product', 'edition', 'revision', 'bundle_ids', 'team_ids',
    'installation_source', 'update_mechanism', 'channel', 'minimum_os',
    'architectures', 'allowed_artifacts', 'download_hosts', 'requirement_graph',
    'effect_scope', 'adapter_id', 'observation_contract', 'limits', 'candidate',
    'acceptance_records', 'matrix_ids',
))
_CANDIDATE_FIELDS = frozenset((
    'url', 'sha256', 'version', 'build', 'artifact_type', 'bundle_name',
    'minimum_os', 'architecture', 'channel', 'product', 'edition', 'bundle_id',
    'team_id', 'installation_source', 'feed_sequence',
))
_RECORD_FIELDS = frozenset((
    'id', 'recorded_at', 'recipe_revision', 'recipe_sha256', 'candidate_sha256',
    'artifact_sha256', 'operation', 'kind', 'result', 'os_version',
    'architecture', 'permissions', 'effect_scope', 'requirements_sha256',
    'limitations', 'redacted_traces',
))
_EFFECTS = {
    'update': frozenset(('replace_existing_app', 'native_update', 'manager_update')),
    'install': frozenset(('install_app', 'install_dependency')),
    'lifecycle': frozenset(('launch_app', 'quit_owned_app', 'restart_owned_app')),
}


def _shape(value, fields, label):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError('invalid ' + label + ' fields')


def _text(value, label, maximum=255):
    if type(value) is not str or not value or len(value) > maximum or any(ord(c) < 32 for c in value):
        raise ValueError('invalid ' + label)


def _identifier(value, label):
    _text(value, label, 128)
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', value):
        raise ValueError('invalid ' + label)


def _strings(value, label, allowed=None, nonempty=False, maximum=128):
    if type(value) is not list or len(value) > maximum or (nonempty and not value):
        raise ValueError('invalid ' + label)
    for item in value:
        _text(item, label, 1024 if label == 'redacted traces' else 255)
        if allowed is not None and item not in allowed:
            raise ValueError('invalid ' + label)
    if len(set(value)) != len(value):
        raise ValueError('duplicate ' + label)


def _integer(value, label, minimum=1, maximum=2**63 - 1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('invalid ' + label)


def _hash(value, label):
    if type(value) is not str or not re.fullmatch(r'[a-f0-9]{64}', value):
        raise ValueError('invalid ' + label)


def _os(value):
    if type(value) is not str or not re.fullmatch(r'[0-9]{1,3}(?:\.[0-9]{1,3}){0,2}', value):
        raise ValueError('unknown or invalid OS')
    parts = tuple(int(p) for p in value.split('.'))
    return parts + (0,) * (3 - len(parts))


def _date(value):
    from datetime import datetime
    if type(value) is not str or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ', value):
        raise ValueError('invalid evidence date')
    try:
        return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')
    except ValueError as exc:
        raise ValueError('invalid evidence date') from exc


def _validate_requirements(graph, effects):
    _shape(graph, ('nodes', 'edges'), 'requirement graph')
    nodes, edges = graph['nodes'], graph['edges']
    if type(nodes) is not list or len(nodes) > 128 or type(edges) is not list or len(edges) > 512:
        raise ValueError('invalid requirement graph size')
    by_id = {}
    for node in nodes:
        _shape(node, ('id', 'kind', 'value', 'operations'), 'requirement node')
        _identifier(node['id'], 'requirement id')
        if node['id'] in by_id or node['kind'] not in ('permission', 'dependency'):
            raise ValueError('invalid requirement identity or kind')
        _text(node['value'], 'requirement value')
        _strings(node['operations'], 'requirement operations', _OPERATIONS, nonempty=True)
        # Dependencies are explicit installation effects, never an update side
        # effect. Update recipes may instead require a pre-existing dependency
        # through a separately accepted install operation before re-planning.
        if node['kind'] == 'dependency' and any(
            operation != 'install' or 'install_dependency' not in effects[operation]
            for operation in node['operations']
        ):
            raise ValueError('dependency installation outside install scope')
        by_id[node['id']] = node
    adjacency = {key: set() for key in by_id}
    indegrees = {key: 0 for key in by_id}
    for edge in edges:
        _shape(edge, ('from', 'to'), 'requirement edge')
        left, right = edge['from'], edge['to']
        if type(left) is not str or type(right) is not str or left not in by_id or right not in by_id:
            raise ValueError('unknown requirement edge')
        if right in adjacency[left]:
            raise ValueError('duplicate requirement edge')
        adjacency[left].add(right)
        indegrees[right] += 1
    pending = [key for key, count in indegrees.items() if not count]
    visited = 0
    while pending:
        current = pending.pop()
        visited += 1
        for child in adjacency[current]:
            indegrees[child] -= 1
            if not indegrees[child]:
                pending.append(child)
    if visited != len(by_id):
        raise ValueError('cyclic requirement graph')


def _validate_candidate(candidate, recipe):
    from urllib.parse import urlsplit
    _shape(candidate, _CANDIDATE_FIELDS, 'candidate')
    for key in ('product', 'edition', 'bundle_id', 'team_id', 'version', 'build', 'bundle_name'):
        _text(candidate[key], 'candidate ' + key)
    _hash(candidate['sha256'], 'artifact hash')
    _integer(candidate['feed_sequence'], 'feed sequence', minimum=0)
    if not re.fullmatch(r'[0-9]+(?:\.[0-9A-Za-z]+)*(?:[-+][0-9A-Za-z.-]+)?', candidate['version']):
        raise ValueError('invalid candidate version')
    if recipe['channel'] == 'stable' and not re.fullmatch(r'[0-9]+(?:\.[0-9]+)*', candidate['version']):
        raise ValueError('prerelease on stable route')
    if (candidate['product'] != recipe['product'] or candidate['edition'] != recipe['edition']
            or candidate['bundle_id'] not in recipe['bundle_ids'] or candidate['team_id'] not in recipe['team_ids']
            or candidate['installation_source'] != recipe['installation_source'] or candidate['channel'] != recipe['channel']
            or candidate['architecture'] not in recipe['architectures'] or candidate['artifact_type'] not in recipe['allowed_artifacts']):
        raise ValueError('candidate outside recipe identity')
    if _os(candidate['minimum_os']) < _os(recipe['minimum_os']):
        raise ValueError('candidate weakens minimum OS')
    name = candidate['bundle_name']
    if '/' in name or '\\' in name or name.startswith('.') or not name.endswith('.app'):
        raise ValueError('unsafe bundle name')
    _text(candidate['url'], 'candidate URL', 4096)
    try:
        parsed = urlsplit(candidate['url'])
        if (parsed.scheme != 'https' or parsed.hostname not in recipe['download_hosts'] or parsed.username is not None
                or parsed.password is not None or parsed.port not in (None, 443) or parsed.fragment or not parsed.path.startswith('/')):
            raise ValueError('candidate URL outside allowed hosts')
    except (ValueError, TypeError) as exc:
        raise ValueError('invalid candidate URL') from exc


def _validate_records(records):
    _shape(records, _OPERATIONS, 'acceptance records')
    ids = set()
    for operation in sorted(_OPERATIONS):
        rows = records[operation]
        if type(rows) is not list or len(rows) > 128:
            raise ValueError('invalid acceptance records')
        for row in rows:
            _shape(row, _RECORD_FIELDS, 'acceptance record')
            _identifier(row['id'], 'evidence id')
            if row['id'] in ids or row['operation'] != operation:
                raise ValueError('duplicate or mismatched evidence operation')
            ids.add(row['id'])
            _date(row['recorded_at'])
            _integer(row['recipe_revision'], 'evidence recipe revision')
            for key in ('recipe_sha256', 'candidate_sha256', 'artifact_sha256', 'requirements_sha256'):
                _hash(row[key], key)
            _os(row['os_version'])
            if row['kind'] not in ('fixture', 'live') or row['result'] not in ('passed', 'failed', 'blocked'):
                raise ValueError('invalid acceptance kind or result')
            if row['architecture'] not in ('arm64', 'x86_64'):
                raise ValueError('invalid acceptance architecture')
            _strings(row['permissions'], 'evidence permissions')
            _strings(row['effect_scope'], 'evidence effects', _EFFECTS[operation])
            _strings(row['limitations'], 'evidence limitations')
            _strings(row['redacted_traces'], 'redacted traces', nonempty=True, maximum=32)


def validate_recipe(recipe):
    """Validate one declarative v2 recipe, returning it without mutation.

    Structural validity never implies execution authority. Evidence and consent
    are checked independently by recipe_acceptance.validate_recipe_evidence.
    """
    _shape(recipe, _V2_FIELDS, 'recipe v2')
    _identifier(recipe['id'], 'recipe id')
    for key in ('product', 'edition'):
        _text(recipe[key], key)
    _integer(recipe['revision'], 'recipe revision')
    for key in ('bundle_ids', 'team_ids', 'download_hosts', 'matrix_ids'):
        _strings(recipe[key], key, nonempty=True)
    for value in recipe['bundle_ids']:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*', value) or '.' not in value or '..' in value:
            raise ValueError('invalid bundle id')
    for value in recipe['team_ids']:
        if not re.fullmatch(r'[A-Z0-9]{10}', value):
            raise ValueError('invalid team id')
    for value in recipe['matrix_ids']:
        _identifier(value, 'matrix id')
    for host in recipe['download_hosts']:
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', host) or '..' in host or '.' not in host:
            raise ValueError('invalid download host')
    _strings(recipe['architectures'], 'architectures', ('arm64',), nonempty=True)
    _strings(recipe['allowed_artifacts'], 'allowed artifacts', ('dmg', 'pkg', 'zip', 'app'), nonempty=True)
    if (type(recipe['installation_source']) is not str or type(recipe['channel']) is not str
            or recipe['installation_source'] not in _SOURCES or recipe['channel'] not in _CHANNELS):
        raise ValueError('invalid recipe source or channel')
    if type(recipe['update_mechanism']) is not str or recipe['update_mechanism'] not in ('direct_artifact', 'native_updater', 'manager', 'app_store'):
        raise ValueError('invalid update mechanism')
    if type(recipe['adapter_id']) is not str or recipe['adapter_id'] not in _ADAPTERS:
        raise ValueError('unknown adapter')
    _os(recipe['minimum_os'])
    _shape(recipe['effect_scope'], _OPERATIONS, 'effect scope')
    for operation in _OPERATIONS:
        _strings(recipe['effect_scope'][operation], 'effect scope', _EFFECTS[operation])
    _validate_requirements(recipe['requirement_graph'], recipe['effect_scope'])
    contract = recipe['observation_contract']
    _shape(contract, ('preflight', 'postflight', 'requires_artifact_hash'), 'observation contract')
    observed = ('identity', 'source', 'version', 'build', 'requirements', 'signature')
    for key in ('preflight', 'postflight'):
        _strings(contract[key], 'observations', observed, nonempty=True)
    if (not {'identity', 'source', 'version', 'build', 'requirements'}.issubset(contract['preflight'])
            or not {'identity', 'source', 'version', 'build', 'signature'}.issubset(contract['postflight'])
            or contract['requires_artifact_hash'] is not True):
        raise ValueError('incomplete observation contract')
    _shape(recipe['limits'], ('maximum_bytes', 'maximum_expanded_bytes', 'maximum_entries', 'maximum_evidence_age_days'), 'limits')
    for key, bound in (('maximum_bytes', 16*1024**3), ('maximum_expanded_bytes', 64*1024**3),
                       ('maximum_entries', 1000000), ('maximum_evidence_age_days', 365)):
        _integer(recipe['limits'][key], key, maximum=bound)
    if recipe['limits']['maximum_expanded_bytes'] < recipe['limits']['maximum_bytes']:
        raise ValueError('expanded size limit below download limit')
    _validate_candidate(recipe['candidate'], recipe)
    _validate_records(recipe['acceptance_records'])
    return recipe


def _reject_constant(value):
    raise ValueError('nonfinite JSON constant: ' + value)


def load_verified_recipes(path):
    """Read strict v2 evidence recipes; never promote v1 capability rows."""
    try:
        data = json.loads(_read(path), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('invalid verified recipe JSON') from exc
    _shape(data, ('schema_version', 'metadata', 'recipes'), 'verified recipe catalog')
    if type(data['schema_version']) is not int or data['schema_version'] != 2:
        raise ValueError('unsupported verified recipe schema')
    _shape(data['metadata'], ('status', 'matrix_ids', 'excluded_products'), 'verified recipe metadata')
    if data['metadata']['status'] != 'evidence_required':
        raise ValueError('catalog metadata cannot confer acceptance')
    _strings(data['metadata']['matrix_ids'], 'matrix ids')
    _strings(data['metadata']['excluded_products'], 'excluded products')
    for value in data['metadata']['matrix_ids']:
        _identifier(value, 'matrix id')
    if type(data['recipes']) is not list or len(data['recipes']) > 512:
        raise ValueError('invalid verified recipes')
    ids = set()
    for recipe in data['recipes']:
        validate_recipe(recipe)
        if recipe['id'] in ids:
            raise ValueError('duplicate recipe id')
        if not set(recipe['matrix_ids']).issubset(data['metadata']['matrix_ids']):
            raise ValueError('recipe outside declared matrix')
        if recipe['product'].casefold() in {p.casefold() for p in data['metadata']['excluded_products']}:
            raise ValueError('excluded product recipe')
        ids.add(recipe['id'])
    return data
