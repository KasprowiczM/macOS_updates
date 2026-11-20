"""Read-only app lists for the Apps and Catalog screens.

The Apps list comes from the saved inventory snapshot when present, else from
APPLICATIONS.md. Neither path scans the Mac or changes any state; "Scan now"
runs build_inventory.sh as a separate, explicit job.
"""
import os
import re

KIND_ORDER = ('appstore', 'cask', 'internet', 'brew', 'cli', 'system')
METHOD_ORIGINS = ('tested', 'detected', 'manual')


MODES = ('auto', 'manual', 'skip')


def _row(group, ident, name, version='', path='', method='', origin='', confidence='', default_mode='auto'):
    return dict(group=group, id=str(ident)[:300], name=str(name or ident)[:200], version=str(version or '')[:40],
                path=str(path or '')[:400], method=str(method or '')[:40],
                method_origin=origin if origin in METHOD_ORIGINS else '',
                confidence=confidence if confidence in ('high', 'medium', 'low') else '',
                default_mode=default_mode if default_mode in MODES else 'auto')


def _evidence(record, kind):
    for item in record.get('evidence', []):
        if isinstance(item, dict) and item.get('kind') == kind:
            return item
    return None


def apps_from_snapshot(snapshot):
    rows, covered = [], set()
    for package in snapshot.get('packages', []):
        if package.get('presence') != 'present':
            continue
        manager = str(package.get('manager', ''))
        evidence = _evidence(package, 'homebrew') or _evidence(package, 'npm') or {}
        name = package.get('name') or evidence.get('token') or evidence.get('name') or package.get('source_identity') or '?'
        related = [r for r in package.get('related_instance_ids', []) if isinstance(r, str)]
        group = 'cli' if manager == 'npm' else ('cask' if manager == 'homebrew' and related else
                                              ('brew' if manager == 'homebrew' else 'cli'))
        if group == 'cask':
            covered.update(related)
        rows.append(_row(group, name, name, package.get('version'), package.get('prefix'),
                         package.get('method'), package.get('method_origin'), package.get('confidence')))
    for inst in snapshot.get('instances', []):
        if inst.get('presence') != 'present' or inst.get('instance_id') in covered or inst.get('parent_instance_id'):
            continue
        if inst.get('hidden'):
            # Helpers, background agents and browser-hosted apps: app_detect
            # marks them hidden; they are neither listed nor counted.
            continue
        bundle = inst.get('bundle_id') or ''
        path = inst.get('path') or ''
        store = _evidence(inst, 'mas') or _evidence(inst, 'app_store_receipt')
        if store:
            group, ident = 'appstore', store.get('store_id') or bundle or inst.get('name')
        elif path.startswith('/System/') or bundle.startswith('com.apple.'):
            group, ident = 'system', bundle or inst.get('name')
        else:
            group, ident = 'internet', bundle or inst.get('name')
        rows.append(_row(group, ident, inst.get('name') or os.path.basename(path)[:-4], inst.get('short_version'),
                         path, inst.get('method'), inst.get('method_origin'), inst.get('confidence'),
                         inst.get('default_mode', 'auto')))
    return rows


_MD_GROUPS = {'1': 'system', '2': 'appstore', '3': 'internet', '4': 'brew'}


def apps_from_markdown(text):
    rows, group, sub = [], None, ''
    for line in text.splitlines():
        heading = re.match(r'^##\s+\S+\s+(\d)\b', line)
        if heading:
            group, sub = _MD_GROUPS.get(heading.group(1)), ''
            continue
        if line.startswith('## '):
            group = None
            continue
        if line.startswith('### '):
            sub = line.lower()
            continue
        if not group or not line.startswith('|') or re.match(r'^\|\s*-', line):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) < 2 or cells[0] in ('Nazwa', 'Pakiet', 'Name', 'Package', ''):
            continue
        name = re.sub(r'\s*[\U0001F100-\U0001FAFF☀-➿]+\s*', ' ', cells[0]).strip()
        kind = group
        if group == 'brew':
            kind = 'cask' if 'cask' in sub else ('cli' if 'npm' in sub or 'cli' in sub else 'brew')
        version = cells[1] if kind != 'appstore' and re.match(r'^[0-9][\w.\-+]*$', cells[1]) else ''
        ident = cells[1] if kind == 'appstore' and cells[1].isdigit() else name
        rows.append(_row(kind, ident, name, version))
    return rows


def load_apps(repo, state_dir=None):
    """Return dict(rows=[...], source='snapshot'|'markdown'|None, error=str|None)."""
    try:
        from inventory_store import load_snapshot
        snapshot = load_snapshot(state_dir)
    except Exception as exc:   # invalid or unsafe store: fall back, never crash
        snapshot, error = None, str(exc)[:200]
    else:
        error = None
    if snapshot:
        rows = apps_from_snapshot(snapshot)
        if rows:
            return dict(rows=_sorted(rows), source='snapshot', error=None)
    import mu_paths
    path = mu_paths.report_path('APPLICATIONS.md', root=repo, read=True)
    try:
        if os.path.isfile(path) and not os.path.islink(path):
            with open(path, encoding='utf-8', errors='replace') as handle:
                rows = apps_from_markdown(handle.read(4 * 1024 * 1024))
            if rows:
                return dict(rows=_sorted(rows), source='markdown', error=error)
    except OSError as exc:
        error = str(exc)[:200]
    return dict(rows=[], source=None, error=error)


def _sorted(rows):
    seen, out = set(), []
    for row in sorted(rows, key=lambda r: (KIND_ORDER.index(r['group']), r['name'].casefold())):
        key = (row['group'], row['id'])
        if key not in seen:
            seen.add(key)
            out.append(row)
    return out


def load_catalog(repo, state_dir=None):
    """Read catalog metadata and this Mac's saved snapshot, without a host scan."""
    from inventory_store import load_snapshot
    from setup_catalog import build_catalog_view, load_setup_catalog
    recipes = load_setup_catalog(repo)
    snapshot = load_snapshot(state_dir)
    view = build_catalog_view(snapshot or {}, recipes, [], {})
    return dict(view, snapshot=snapshot, recipes=recipes)


def _installed_by_name(snapshot):
    """Apps present on this Mac, keyed by normalized name, bundle file name and
    bundle id (instance names, hidden ones included), from the saved snapshot."""
    import unicodedata
    found = {}
    for inst in (snapshot or {}).get('instances', []) or []:
        if not isinstance(inst, dict) or inst.get('presence') not in (None, 'present'):
            continue
        path = str(inst.get('path') or '')
        for value in (inst.get('name'), os.path.basename(path)[:-4] if path.endswith('.app') else '', inst.get('bundle_id')):
            if value:
                found.setdefault(unicodedata.normalize('NFC', str(value)).casefold().strip(), inst)
    return found


def _first_text(targets, *fields):
    for target in targets:
        if isinstance(target, dict):
            for field in fields:
                if target.get(field):
                    return str(target[field])[:40]
    return ''


def catalog_rows(model):
    """Every tested app of the catalog, with this Mac's saved install state.

    Installable rows come first, installed ones after, each group by name.
    "Installed" also covers an app the detector found under the product's name
    or bundle id, whatever its update method. Nothing is scanned here: version
    and update method come from the saved snapshot only, and an app whose state
    is unknown stays installable."""
    import unicodedata
    rows = []
    present = _installed_by_name((model or {}).get('snapshot'))
    for row in (model or {}).get('rows', []):
        targets = [t for t in row.get('installed') or [] if isinstance(t, dict)]
        installed = row.get('installation_status') == 'already_installed' or bool(targets)
        if not installed:
            keys = {unicodedata.normalize('NFC', str(v)).casefold().strip()
                    for v in (row.get('name'), row.get('product_id'), row.get('bundle_id')) if v}
            match = next((present[k] for k in sorted(keys) if k in present), None)
            if match is not None:
                installed, targets = True, [match]
        sources = [s.get('source_id') for s in row.get('sources', []) if isinstance(s, dict) and s.get('source_id')]
        rows.append(dict(product_id=row['product_id'], name=row.get('name', row['product_id']), sources=sources,
                         recommended=row.get('recommended_source_id') or (sources[0] if sources else None),
                         status=row.get('installation_status', 'manual'), installed=installed,
                         version=_first_text(targets, 'short_version', 'version') if installed else '',
                         method=_first_text(targets, 'method') if installed else ''))
    rows.sort(key=lambda r: (r['installed'], r['name'].casefold()))
    return rows


def missing_catalog_rows(model):
    """Tested apps that are not installed (the installable part of catalog_rows)."""
    return [r for r in catalog_rows(model) if not r['installed']]


def prepare_catalog_selection(model, selected, sources):
    """Only explicit product/source pairs enter the existing installation plan."""
    from policy_runtime import utc_now
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
