"""Narrow first-install adapter for explicitly reviewed Homebrew casks.

Cask metadata is not vendor-recipe acceptance. Selection and exact preview
confirmation remain separate from the existing vendor installation path.
"""
import copy
import os
import re
from pathlib import Path

# Closed product/source pairs. Unproven stable feeds remain manual.
CASKS = {
    'keepassxc-gui': ('keepassxc', 'KeePassXC.app'),
}


def validate_cask(product_id, metadata, stable_version):
    from vendor_feeds import version_compare
    pair = CASKS.get(product_id)
    if not pair or not isinstance(metadata, dict):
        raise ValueError('unsupported_cask')
    token, app = pair
    version = metadata.get('version')
    sha = metadata.get('sha256')
    if (metadata.get('token') != token or metadata.get('auto_updates') is not False
            or metadata.get('disabled') is not False or metadata.get('deprecated') is not False
            or not isinstance(version, str) or len(version) > 128
            or re.search(r'(?:alpha|beta|nightly|preview|snapshot|\brc\b|rc\d|latest)', version, re.I)
            or not isinstance(sha, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', sha)
            or not isinstance(stable_version, str)
            or version_compare(version.split(',')[0], stable_version.lstrip('v')) != 0):
        raise ValueError('cask_not_verified_stable')
    artifacts = metadata.get('artifacts')
    if artifacts != [{'app': [app]}]:
        raise ValueError('cask_effects_not_app_only')
    dependencies = metadata.get('depends_on') or {}
    if not isinstance(dependencies, dict) or any(v for k, v in dependencies.items() if k not in ('macos', 'arch')):
        raise ValueError('cask_dependency_effects')
    return dict(product_id=product_id, token=token, version=version,
                sha256=sha.lower(), destination='/Applications/' + app,
                stable_version=stable_version, metadata=copy.deepcopy(metadata))


def snapshot_proves_absence(snapshot, product_id, destination):
    if not isinstance(snapshot, dict):
        return False
    sources = snapshot.get('sources')
    if not isinstance(sources, dict):
        return False
    filesystem = {k: v for k, v in sources.items() if isinstance(k, str) and k.startswith('filesystem:')}
    if not filesystem or 'filesystem:/Applications' not in filesystem:
        return False
    for key, source in sources.items():
        if not isinstance(source, dict):
            return False
        if source.get('status') == 'ok' and source.get('complete') is True:
            continue
        # Signed-out stores and unrelated CLI managers cannot hide a GUI app
        # from complete filesystem roots. Missing optional roots are proved by
        # lstat, while permission errors and partial scans remain unsafe.
        if key == 'mas' or key.startswith('cli:'):
            continue
        if key.startswith('brew:'):
            import errno
            prefix = key.split(':', 1)[1]
            absence_proven = True
            for name in ('keepassxc', 'keepassxc@beta', 'keepassxc@snapshot'):
                try:
                    os.lstat(os.path.join(prefix, 'Caskroom', name))
                    absence_proven = False
                except OSError as exc:
                    if exc.errno != errno.ENOENT:
                        absence_proven = False
            if absence_proven:
                continue
        if key.startswith(('filesystem:', 'brew:')):
            import errno
            try:
                os.lstat(key.split(':', 1)[1])
            except OSError as exc:
                if exc.errno == errno.ENOENT:
                    continue
        return False
    expected = os.path.basename(destination).casefold()
    instances, packages = snapshot.get('instances'), snapshot.get('packages')
    if not isinstance(instances, list) or not isinstance(packages, list):
        return False
    for target in instances + packages:
        if not isinstance(target, dict):
            return False
        matches = (target.get('product_id') == product_id
                   or target.get('bundle_id') == 'org.keepassxc.keepassxc'
                   or os.path.basename(str(target.get('path') or '')).casefold() == expected
                   or os.path.basename(str(target.get('real_path') or '')).casefold() == expected)
        if matches and target.get('presence') != 'absent':
            return False
    return True


def manager_recipe_eligible(recipe, now=None):
    """Reviewed manager delegation is separate from vendor artifact acceptance."""
    import datetime
    from user_policy import timestamp
    pair = CASKS.get(recipe.get('product_id'))
    contract = recipe.get('manager_delegation', {})
    try:
        moment = timestamp(now) if now else datetime.datetime.now(datetime.timezone.utc)
        age = (moment - timestamp(contract['reviewed_at'])).total_seconds()
        return bool(pair and recipe.get('install_adapter') == 'homebrew_cask'
                    and contract.get('token') == pair[0]
                    and recipe.get('installation_source') == 'homebrew'
                    and recipe.get('channel') == 'stable'
                    and recipe.get('bundle_id') == 'org.keepassxc.keepassxc'
                    and re.fullmatch(r'\d+\.\d+\.\d+', contract.get('stable_version', ''))
                    and recipe.get('version') == contract['stable_version']
                    and recipe.get('destination') == '/Applications/' + pair[1]
                    and recipe.get('permissions') == ['manager_delegated_install']
                    and 0 <= age <= 7 * 86400)
    except (KeyError, TypeError, ValueError):
        return False


def trusted_brew():
    """Use the existing Apple Silicon manager, never PATH or a bootstrap."""
    import stat
    path = '/opt/homebrew/bin/brew'
    if not os.path.isfile(path) or not os.access(path, os.X_OK):
        raise ValueError('homebrew_missing')
    resolved = os.path.realpath(path)
    if not resolved.startswith('/opt/homebrew/'):
        raise ValueError('homebrew_path_untrusted')
    check = resolved
    while check != '/':
        info = os.stat(check)
        if info.st_uid not in (0, os.getuid()) or stat.S_IMODE(info.st_mode) & 0o002:
            raise ValueError('homebrew_path_untrusted')
        check = os.path.dirname(check)
    return path


def _environment():
    # Ambient Homebrew options must not introduce --force, another appdir,
    # a custom API or an unrelated update/cleanup into this explicit action.
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('HOMEBREW_', 'BASH_ENV', 'ENV', 'RUBY', 'GEM_'))}
    env.update(HOMEBREW_NO_AUTO_UPDATE='1', HOMEBREW_NO_INSTALL_CLEANUP='1',
               HOMEBREW_NO_ANALYTICS='1', NONINTERACTIVE='1',
               PATH='/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin')
    return env


def query_cask(brew, token):
    import json
    import subprocess
    result = subprocess.run([brew, 'info', '--json=v2', '--cask', 'homebrew/cask/' + token],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, env=_environment(),
                            timeout=60, check=True)
    if len(result.stdout.encode()) > 2 * 1024 * 1024:
        raise ValueError('cask_metadata_too_large')
    data = json.loads(result.stdout)
    rows = data.get('casks', [])
    if len(rows) != 1 or rows[0].get('tap') != 'homebrew/cask':
        raise ValueError('cask_source_untrusted')
    return rows[0]


def preview_cask(recipe):
    if not manager_recipe_eligible(recipe):
        raise ValueError('manager_contract_unreviewed')
    brew = trusted_brew()
    value = validate_manager_cask(recipe['product_id'], query_cask(brew, recipe['manager_delegation']['token']),
                          recipe['manager_delegation']['stable_version'])
    return value


def target_absent(token, destination):
    import errno
    # lstat distinguishes missing from inaccessible. Never interpret EACCES as
    # proof that another installation/manager receipt does not exist.
    names = (token, token + '@beta', token + '@snapshot')
    paths = [destination] + ['/opt/homebrew/Caskroom/' + name for name in names]
    for path in paths:
        try:
            os.lstat(path)
            return False
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                return False
    return True


def run_install(brew, token, record_process=None, record_complete=None):
    import subprocess
    # Popen/poll preserves the persistent lease if a helper may still be alive.
    import time
    try:
        process = subprocess.Popen([brew, 'install', '--cask', 'homebrew/cask/' + token,
                                    '--appdir=/Applications'], stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   env=_environment(), start_new_session=True)
    except OSError:
        # Popen reports a definite failure to execute; no manager helper exists.
        if record_complete:
            record_complete(started=False)
        raise
    if record_process:
        record_process(process.pid)
    deadline = time.monotonic() + 1800
    while process.poll() is None:
        if time.monotonic() >= deadline:
            raise ValueError('manager_helper_unconfirmed')
        time.sleep(0.1)
    if not process_group_complete(process.pid):
        raise ValueError('manager_helper_unconfirmed')
    if record_complete:
        record_complete()
    if process.returncode != 0:
        raise ValueError('manager_install_failed')


def verify_receipt(token, version, destination):
    from inventory_providers import read_brew_receipts
    result = read_brew_receipts('/opt/homebrew')
    from inventory_collect import read_bundle_static
    app = read_bundle_static(destination)
    identity = app.get('status') == 'ok' and any(
        item.get('bundle_id') == 'org.keepassxc.keepassxc'
        and item.get('short_version') == version.split(',')[0] for item in app.get('items', []))
    return bool(identity and os.path.isdir(destination) and not os.path.islink(destination)
                and any(item.get('source_identity') == 'cask:' + token
                        and item.get('version') == version
                        and any(e.get('artifact_path') == destination for e in item.get('evidence', []))
                        for item in result.get('items', [])))


def refresh_snapshot(snapshot, recipes, state_dir):
    """Reobserve every configured source immediately before manager mutation."""
    from inventory_migration import collect_current_snapshot
    from inventory_store import load_snapshot
    from setup_catalog import match_catalog_snapshot
    fresh = collect_current_snapshot(str(Path(__file__).resolve().parents[2]), state_dir)
    if load_snapshot(state_dir) is None and snapshot.get('profile_id') is not None:
        fresh['profile_id'] = snapshot['profile_id']
        fresh['generation'] = snapshot.get('generation', 0)
    return match_catalog_snapshot(fresh, recipes)


def execute_manager_install(plan, action, consent, recipes, environment, snapshot, state_dir):
    from install_execution import authorize_install, _current, _roots
    from inventory_store import _root
    from policy_runtime import utc_now, TargetLock, _atomic_json
    from update_scheduler import claim_action_resources
    from user_policy import digest
    import uuid
    import subprocess
    result = dict(action_id=action['action_id'], product_id=action['product_id'], name=action['name'],
                  status='deferred', verified=False, recovery_required=False,
                  verification_scope='homebrew_receipt', vendor_artifact_accepted=False)
    lease = None
    attempted = False
    complete = False
    journal_path = None
    try:
        if os.environ.get('MAC_UPDATE_DRY_RUN') == '1':
            raise ValueError('dry_run_no_install')
        if digest(recipes) != plan['recipe_fingerprint']:
            raise ValueError('recipe_catalog_changed')
        if not snapshot_proves_absence(snapshot, action['product_id'], action['destination']):
            raise ValueError('source_absence_unproven')
        current = _current(action, plan, recipes, environment, snapshot, _roots(None))
        guard = authorize_install(action, current, consent, utc_now())
        if not guard['allowed']:
            raise ValueError(guard['reason_code'])
        root = _root(state_dir, True)
        lease = claim_action_resources(dict(action_id=action['action_id'], target_path=action['destination'],
                                           scope_complete=False, parallel_safe=False,
                                           shared_resources=['manager:homebrew']), root)
        with TargetLock(action['destination'], root, owner_action_id=action['action_id']):
            brew = trusted_brew()
            preview = action['manager_preview']
            token = CASKS[action['product_id']][0]
            current_metadata = validate_manager_cask(action['product_id'], query_cask(brew, token),
                                             action['recipe']['manager_delegation']['stable_version'])
            if digest(current_metadata) != digest(preview):
                raise ValueError('manager_metadata_changed')
            if not target_absent(token, action['destination']):
                raise ValueError('target_appeared_since_preview')
            # Consent and filesystem state are rechecked after all read-only probes.
            snapshot = refresh_snapshot(snapshot, recipes, root)
            if not snapshot_proves_absence(snapshot, action['product_id'], action['destination']):
                raise ValueError('source_absence_unproven')
            current = _current(action, plan, recipes, environment, snapshot, _roots(None))
            guard = authorize_install(action, current, consent, utc_now())
            if not guard['allowed']:
                raise ValueError(guard['reason_code'])
            journal_path = os.path.join(root, 'manager-install-' + str(uuid.uuid4()) + '.json')
            result.update(plan_digest=plan['plan_digest'], destination=action['destination'],
                          status='manager_install_intent', manager_preview=copy.deepcopy(preview))
            result.update(action=copy.deepcopy(action), lease_id=lease.lease_id)
            _atomic_json(journal_path, result, exclusive=True)
            attempted = True
            def record_process(pid):
                result['helper_process_group'] = pid
                _atomic_json(journal_path, result)
            def record_complete(started=True):
                nonlocal attempted
                if not started:
                    attempted = False
                result['helpers_complete'] = True
                _atomic_json(journal_path, result)
            run_install(brew, token, record_process=record_process, record_complete=record_complete)
            result['helpers_complete'] = True
            after = validate_manager_cask(action['product_id'], query_cask(brew, token),
                                  action['recipe']['manager_delegation']['stable_version'])
            if digest(after) != digest(preview) or not verify_receipt(token, preview['version'], action['destination']):
                raise ValueError('manager_install_unconfirmed')
            result.update(status='manager_installed_verified', verified=True,
                          reason_code='manager_receipt_verified')
            complete = True
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        reason = str(exc)
        if not re.fullmatch(r'[a-z_]+', reason):
            reason = 'manager_install_unconfirmed'
        result.update(status='recovery_required' if attempted else 'deferred',
                      recovery_required=attempted, reason_code=reason)
    finally:
        if journal_path:
            _atomic_json(journal_path, result)
        if lease:
            if complete or not attempted:
                lease.finish('manager_receipt_verified' if complete else 'no_mutation', helpers_complete=True)
            else:
                lease.pending('manager_install_unconfirmed')
    return result


def validate_manager_cask(product_id, metadata, stable_version):
    """A manager recipe binding, never vendor bundle/signature acceptance.

    The reviewed KeePassXC cask installs its app, CLI symlink and manual pages.
    Its uninstall/zap declarations are inactive during plain `brew install`.
    """
    from vendor_feeds import version_compare
    pair = CASKS.get(product_id)
    if not pair or not isinstance(metadata, dict):
        raise ValueError('unsupported_cask')
    token, app = pair
    version = metadata.get('version')
    if (metadata.get('token') != token or metadata.get('tap') != 'homebrew/cask'
            or metadata.get('disabled') is not False or metadata.get('deprecated') is not False
            or metadata.get('auto_updates') not in (None, False)
            or not isinstance(version, str) or len(version) > 128
            or not re.fullmatch(r'\d+\.\d+\.\d+(?:,[0-9A-Za-z.-]+)?', version)
            or not isinstance(stable_version, str)
            or version_compare(version.split(',')[0], stable_version) != 0
            or not isinstance(metadata.get('sha256'), str)
            or not re.fullmatch(r'[a-fA-F0-9]{64}', metadata['sha256'])):
        raise ValueError('cask_not_verified_stable')
    artifacts = metadata.get('artifacts')
    if not isinstance(artifacts, list) or not 1 <= len(artifacts) <= 16:
        raise ValueError('cask_effects_unreviewed')
    apps = 0
    for item in artifacts:
        if not isinstance(item, dict) or not item or set(item) - {'app','binary','manpage','uninstall','zap','target'}:
            raise ValueError('cask_effects_unreviewed')
        keys = set(item) - {'target'}
        if len(keys) != 1:
            raise ValueError('cask_effects_unreviewed')
        key = next(iter(keys))
        if key == 'app':
            if item[key] != [app] or item.get('target', '/Applications/' + app) != '/Applications/' + app:
                raise ValueError('cask_effects_unreviewed')
            apps += 1
        if key in ('binary','manpage'):
            allowed = {'binary': ['$APPDIR/KeePassXC.app/Contents/MacOS/keepassxc-cli'],
                       'manpage': ['$APPDIR/KeePassXC.app/Contents/Resources/man/man1/keepassxc.1',
                                   '$APPDIR/KeePassXC.app/Contents/Resources/man/man1/keepassxc-cli.1']}
            targets = {'binary': ['$HOMEBREW_PREFIX/bin/keepassxc-cli'],
                       'manpage': ['$HOMEBREW_PREFIX/share/man/man1/keepassxc.1', '$HOMEBREW_PREFIX/share/man/man1/keepassxc-cli.1']}
            if (not isinstance(item[key], list) or len(item[key]) != 1 or item[key][0] not in allowed[key]
                    or item.get('target') is not None and item['target'] not in targets[key]):
                raise ValueError('cask_effects_unreviewed')
    if apps != 1:
        raise ValueError('cask_effects_unreviewed')
    deps = metadata.get('depends_on') or {}
    if not isinstance(deps, dict) or set(deps) - {'macos','arch','formula','cask'}:
        raise ValueError('cask_dependency_effects')
    for key in ('formula','cask'):
        if key in deps and (not isinstance(deps[key], list) or len(deps[key]) > 64
                or any(not isinstance(x, str) or not re.fullmatch(r'[a-z0-9][a-z0-9@+_.-]*', x) for x in deps[key])):
            raise ValueError('cask_dependency_effects')
    # Exclude installed/runtime fields, which legitimately change after install.
    bound = {key: copy.deepcopy(metadata.get(key)) for key in
             ('token','tap','version','sha256','url','auto_updates','disabled','deprecated','artifacts','depends_on','conflicts_with')}
    return dict(product_id=product_id, token=token, version=version, sha256=metadata['sha256'].lower(),
                destination='/Applications/' + app, stable_version=stable_version, metadata=bound)


def process_group_complete(process_group):
    import errno
    if type(process_group) is not int or process_group <= 1:
        return False
    try:
        os.killpg(process_group, 0)
    except OSError as exc:
        return exc.errno == errno.ESRCH
    return False


def recover_manager_installations(state_dir=None):
    """Reobserve a completed manager attempt. Never execute/resume an install."""
    from inventory_store import _root, StoreError
    from policy_runtime import _read_json, _atomic_json, TargetLock
    from update_scheduler import reconcile_session
    import stat
    results = []
    root = _root(state_dir)
    if root is None:
        return results
    paths = sorted(Path(root).glob('manager-install-*.json'))
    if len(paths) > 1000:
        return [dict(status='recovery_required', reason_code='manager_journal_budget')]
    for path in paths:
        value = None
        try:
            info = os.lstat(path)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1:
                raise ValueError('unsafe_manager_journal')
            value = _read_json(str(path))
            if value.get('status') not in ('manager_install_intent','recovery_required'):
                continue
            action = value['action']
            preview = action['manager_preview']
            expected = validate_manager_cask(action['product_id'], preview['metadata'], preview['stable_version'])
            if (expected != preview or value.get('manager_preview') != preview
                    or value.get('destination') != expected['destination']
                    or value.get('action_id') != action.get('action_id')
                    or value.get('vendor_artifact_accepted') is not False):
                raise ValueError('manager_journal_changed')
            # A recorded owned process group must have ended. PID absence alone
            # does not satisfy this check. No installer/hook artifacts are allowed
            # by this adapter's closed effect contract.
            helpers_complete = value.get('helpers_complete') is True or process_group_complete(value.get('helper_process_group'))
            if not helpers_complete:
                raise ValueError('manager_helper_unconfirmed')
            with TargetLock(expected['destination'], root, owner_action_id=action['action_id']):
                verified = verify_receipt(expected['token'], expected['version'], expected['destination'])
                if not verified:
                    from inventory_migration import collect_current_snapshot
                    fresh = collect_current_snapshot(str(Path(__file__).resolve().parents[2]), root)
                    if (not target_absent(expected['token'], expected['destination'])
                            or not snapshot_proves_absence(fresh, action['product_id'], expected['destination'])):
                        raise ValueError('manager_install_unconfirmed')
                if not reconcile_session(value['lease_id'], dict(action_id=action['action_id'],
                                         helpers_complete=True, target_reobserved=True), root):
                    raise ValueError('manager_lease_unconfirmed')
                value.update(status='manager_installed_verified' if verified else 'deferred', verified=verified, recovery_required=False,
                             helpers_complete=True, reason_code='manager_receipt_reobserved' if verified else 'manager_attempt_completed_unverified')
                _atomic_json(str(path), value)
            results.append(value)
        except (ValueError, OSError, KeyError, TypeError, StoreError):
            results.append(dict(status='recovery_required', verified=False,
                                reason_code='manager_install_requires_review'))
    return results
