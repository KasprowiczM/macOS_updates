"""Observation of explicitly supported, already installed native runtimes.

Discovery alone is never execution authority. Consumers must bind the exact
paths and identity to a reviewed action and reobserve them before mutation.
"""
import os
import stat
from pathlib import Path


# OpenAI publishes its signing team in the Codex verification source. The
# official Anthropic CLI artifact was verified against its release manifest,
# Apple anchor and signing team; other signers require equivalent evidence.
TRUSTED_NATIVE_TEAMS = {'codex': frozenset({'2DC432GLL2'}), 'claude': frozenset({'Q6L2SF6YDW'})}


def is_trusted_native_signer(name, team):
    return isinstance(team, str) and team in TRUSTED_NATIVE_TEAMS.get(name, ())


def _existing_executable(path, root):
    try:
        root = os.path.realpath(root)
        real = os.path.realpath(path)
        if os.path.commonpath((root, real)) != root:
            return None
        mode = os.stat(real).st_mode
        if not stat.S_ISREG(mode) or not mode & 0o111:
            return None
        return real
    except (OSError, ValueError):
        return None


def discover_native_cli(home, *, version_probe, toolchain_home=None, bun_home=None, failures=None, identity_probe=None):
    home = os.path.abspath(home)
    toolchain = os.path.abspath(toolchain_home or os.path.join(home, '.local/share/mac-update'))
    bun_root = os.path.abspath(bun_home or os.path.join(home, '.bun'))
    definitions = [
        ('bun', os.path.join(bun_root, 'bin/bun'), bun_root, bun_root, None, 'bun_native'),
        ('node', os.path.join(toolchain, 'node/bin/node'), os.path.join(toolchain, 'node'),
         os.path.join(toolchain, 'node'), os.path.join(toolchain, 'npm-global/bin/n'), 'managed_node'),
    ]
    for name in ('claude', 'codex', 'agy', 'agent'):
        definitions.append((name, os.path.join(home, '.local/bin', name),
                            os.path.join(home, '.local'), home, None, 'native_vendor_cli'))
    definitions.append(('opencode', os.path.join(home, '.opencode/bin/opencode'),
                        os.path.join(home, '.opencode'), home, None, 'native_vendor_cli'))
    found = []
    for name, path, allowed_root, effect_root, helper, source in definitions:
        executable = _existing_executable(path, allowed_root)
        if not executable and name == 'codex':
            executable = _existing_executable(path, os.path.join(home, '.codex/packages/standalone/releases'))
        manager = _existing_executable(helper, os.path.join(toolchain, 'npm-global')) if helper else None
        if executable and source == 'native_vendor_cli':
            try:
                if os.path.commonpath((executable, os.path.realpath(toolchain))) == os.path.realpath(toolchain) or 'node_modules' in Path(executable).parts:
                    continue  # This alias belongs to a package manager, not the native updater.
            except ValueError:
                if failures is not None:
                    failures.append(name)
                continue
        if not executable or helper and not manager:
            if failures is not None:
                try:
                    os.lstat(path)
                except FileNotFoundError:
                    pass
                except OSError:
                    failures.append(name)
                else:
                    failures.append(name)
            continue
        try:
            version = version_probe(executable)
        except (OSError, ValueError):
            if failures is not None:
                failures.append(name)
            continue
        if not isinstance(version, str) or not version.strip():
            if failures is not None:
                failures.append(name)
            continue
        team = None
        if source == 'native_vendor_cli':
            try:
                team = (identity_probe or probe_signing_identity)(executable)
            except (OSError, ValueError):
                team = None
            if not is_trusted_native_signer(name, team):
                source = 'native_vendor_unverified'
                if failures is not None:
                    failures.append(name)
        found.append(dict(name=name, path=executable, logical_path=os.path.abspath(path),
                          team_id=team, version=version.strip(), source=source,
                          manager_path=manager, root=os.path.realpath(effect_root)))
    return found


def prepare_native_command(expected, current, node_release_index=None):
    """Prepare one already-observed target; caller still authorizes and leases it."""
    fields = ('name', 'path', 'logical_path', 'team_id', 'root', 'manager_path', 'source')
    if any(expected.get(k) != current.get(k) for k in fields):
        raise ValueError('native_identity_changed')
    if not current.get('path') or not current.get('root'):
        raise ValueError('native_identity_missing')
    if current.get('name') == 'node' and current.get('source') == 'managed_node':
        from node_releases import latest_stable_node
        version = latest_stable_node(node_release_index)
        if not version or not current.get('manager_path'):
            raise ValueError('stable_node_or_manager_unavailable')
        import re
        current_version = current.get('version', '')
        if not re.fullmatch(r'\d+\.\d+\.\d+', current_version):
            raise ValueError('native_version_unknown')
        if tuple(map(int, version[1:].split('.'))) <= tuple(map(int, current_version.split('.'))):
            return None, {}
        return [current['manager_path'], version[1:]], {'N_PREFIX': current['root']}
    if current.get('name') == 'bun' and current.get('source') == 'bun_native':
        return [current['path'], 'upgrade'], {'BUN_INSTALL': current['root']}
    if (current.get('source') == 'native_vendor_cli'
            and is_trusted_native_signer(current.get('name'), current.get('team_id'))):
        args = ['upgrade', '--method', 'curl'] if current['name'] == 'opencode' else ['update']
        env = {'CODEX_NON_INTERACTIVE': '1'} if current['name'] == 'codex' else {}
        return [current['path']] + args, env
    raise ValueError('unsupported_native_cli')


def native_inventory_source(home, *, version_probe, toolchain_home=None, bun_home=None, identity_probe=None):
    from inventory_collect import source_result
    failures = []
    found = discover_native_cli(home, version_probe=version_probe,
                                toolchain_home=toolchain_home, bun_home=bun_home, failures=failures, identity_probe=identity_probe)
    items = []
    for item in found:
        evidence = dict(kind='native_cli', name=item['name'], path=item['path'],
                        root=item['root'], source=item['source'])
        vendor = item['source'] in ('native_vendor_cli', 'native_vendor_unverified')
        if vendor:
            evidence.update(logical_path=item['logical_path'], team_id=item['team_id'])
        if item['manager_path']:
            evidence['manager_path'] = item['manager_path']
        items.append(dict(name=item['name'],
                          manager='unknown' if item['source'] == 'native_vendor_unverified' else 'native_cli',
                          version=item['version'], installed_receipt=item['logical_path'] if vendor else item['path'],
                          source_identity=item['name'], channel='stable', evidence=[evidence]))
    result = source_result('partial' if failures else 'ok', items, covered_roots=[os.path.realpath(home)],
                           reason_code='native_observation_incomplete' if failures else None)
    result['complete_native_receipts'] = [item['installed_receipt'] for item in items if item['manager'] == 'native_cli']
    return result


def native_receipt_complete(source, package):
    """Prove one observed native target despite an unrelated partial scan."""
    if package.get('manager') != 'native_cli' or not isinstance(source, dict):
        return False
    receipt = package.get('installed_receipt')
    if not receipt or receipt not in source.get('complete_native_receipts', []):
        return False
    matches = [item for item in source.get('items', []) if item.get('manager') == 'native_cli'
               and item.get('source_identity') == package.get('source_identity')
               and item.get('installed_receipt') == receipt]
    if len(matches) != 1:
        return False
    def clean(evidence):
        return [{k: v for k, v in e.items() if k not in ('source_key', 'source_status', 'source_complete')}
                for e in evidence]
    return (matches[0].get('version') == package.get('version') and
            clean(matches[0].get('evidence', [])) == clean(package.get('evidence', [])))


def probe_native_version(path):
    """Read a bounded version string without accepting executable output as a command."""
    import re
    import subprocess
    try:
        result = subprocess.run([path, '--version'], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=3, check=False)
        text = result.stdout.decode('utf-8', 'replace').strip()
        versions = re.findall(r'(?<![\w.])v?(\d+\.\d+\.\d+)(?![\w.-])', text)
        if result.returncode or len(result.stdout) > 1024 or len(set(versions)) != 1:
            return None
        return versions[0]
    except (OSError, subprocess.SubprocessError):
        return None


def probe_signing_identity(path):
    """Return a verified Developer ID team, never an unverified label."""
    import re
    import subprocess
    try:
        verified = subprocess.run(['codesign', '--verify', '--strict', path], stdin=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
        if verified.returncode:
            return None
        info = subprocess.run(['codesign', '-dv', '--verbose=4', path], stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=False)
        data = info.stdout + info.stderr
        if info.returncode or len(data) > 8192:
            return None
        match = re.search(rb'^TeamIdentifier=([A-Z0-9]{10})$', data, re.M)
        if not match:
            return None
        team = match.group(1).decode('ascii')
        requirement = 'anchor apple generic and certificate leaf[subject.OU] = "' + team + '"'
        anchored = subprocess.run(['codesign', '--verify', '--strict', '-R=' + requirement, path],
                                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, timeout=10, check=False)
        return team if anchored.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None
