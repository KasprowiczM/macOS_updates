"""Read saved inventory and edit exclusions without granting update authority."""
import copy
import os

from inventory_store import load_snapshot, locked_state
from policy_runtime import _atomic_json, _recipe_catalog, load_policies, utc_now
from source_resolver import resolve_snapshot
from update_plan import build_plan
from user_policy import digest, make_decision, record_decision
from tui_events import candidate


def load_inventory(repo, state_dir=None):
    snapshot = load_snapshot(state_dir)
    if snapshot is None:
        return dict(plan=None, rows=[], snapshot_id=None, generation=None)
    policies = load_policies(state_dir)
    if policies.get('profile_id') not in (None, snapshot['profile_id']):
        raise ValueError('policy_profile_mismatch')
    plan = build_plan(snapshot, resolve_snapshot(snapshot, _recipe_catalog(repo)), policies, utc_now())
    rows = [candidate(action) for action in plan['actions']]
    rows.sort(key=lambda row: (row['source'], row['name'].casefold(), row['path']))
    return dict(plan=plan, rows=rows, snapshot_id=snapshot['snapshot_id'], generation=snapshot['generation'])


def save_selection(model, changes, state_dir=None):
    """False excludes; True clears all target grants and requires fresh consent."""
    if not isinstance(changes, dict) or any(type(value) is not bool for value in changes.values()):
        raise ValueError('invalid_inventory_selection')
    plan = model.get('plan')
    if not plan:
        raise ValueError('inventory_missing')
    actions = {action['action_id']: action for action in plan['actions']}
    if set(changes) - set(actions):
        raise ValueError('inventory_selection_changed')
    with locked_state(state_dir) as root:
        snapshot = load_snapshot(root)
        if (snapshot is None or snapshot['snapshot_id'] != plan['snapshot_id']
                or snapshot['generation'] != plan['snapshot_generation']
                or snapshot['profile_id'] != plan['profile_id']):
            raise ValueError('inventory_changed')
        current = load_policies(root)
        if digest(current) != plan['policy_fingerprint']:
            raise ValueError('policy_changed')
        if not changes:
            return
        policies = copy.deepcopy(current)
        policies.update(schema_version=1, profile_id=plan['profile_id'])
        for action_id, enabled in changes.items():
            action = actions[action_id]
            policies['decisions'] = [d for d in policies.get('decisions', []) if d.get('target') != action['target']]
            policies['revision'] = policies.get('revision', 0) + 1
            if not enabled:
                decision = make_decision(action['expected_target'], action['expected_resolution'],
                                         'ignore', action['action_scope'], utc_now())
                policies = record_decision(decision, policies)
        _atomic_json(os.path.join(root, 'policy.json'), policies)


def load_catalog(repo, state_dir=None):
    """Read catalog metadata and this Mac's saved snapshot, without a host scan."""
    from setup_catalog import build_catalog_view, load_setup_catalog
    recipes = load_setup_catalog(repo)
    snapshot = load_snapshot(state_dir)
    view = build_catalog_view(snapshot or {}, recipes, [], {})
    return dict(view, snapshot=snapshot, recipes=recipes)


def prepare_catalog_selection(model, selected, sources):
    """Only explicit product/source pairs enter the existing installation plan."""
    from setup_catalog import _save_install_plan, prepare_catalog_selections
    if not selected:
        raise ValueError('catalog_selection_empty')
    if not model.get('snapshot'):
        raise ValueError('inventory_missing')
    if any(product not in sources for product in selected):
        raise ValueError('catalog_source_required')
    plan = prepare_catalog_selections([(product, sources[product]) for product in sorted(selected)],
                                      model['snapshot'], model['recipes'], utc_now())
    return _save_install_plan(plan)
