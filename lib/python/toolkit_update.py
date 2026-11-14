"""Explicit, fast-forward-only self-update for an idle public checkout."""
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time
import uuid

from update_scheduler import claim_action_resources
from inventory_store import StoreError

from run_lock import release

OFFICIAL_REMOTE = 'https://github.com/KasprowiczM/macOS_updates.git'
RECEIPT_TTL = 900
SHA = re.compile(r'^[0-9a-f]{40,64}$')


class UpdateError(Exception):
    pass


def _git(args, cwd=None, *, check=True):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0')
    cmd = ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
           '-c', 'credential.helper=', *args]
    try:
        process = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=30)
        except subprocess.TimeoutExpired as exc:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                try:
                    process.kill()
                except OSError:
                    pass
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                # A detached helper may still hold inherited pipes. Never wait forever.
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
            raise UpdateError('git_timeout') from exc
        p = subprocess.CompletedProcess(cmd, process.returncode, stdout, stderr)
    except (OSError, subprocess.SubprocessError) as exc:
        raise UpdateError('git_unavailable') from exc
    if check and p.returncode:
        raise UpdateError('git_failed')
    return p


def _text(args, cwd=None):
    return _git(args, cwd).stdout.decode('utf-8', 'strict').strip()


def _local(repo):
    root = Path(repo).resolve(strict=True)
    if not (root / '.git').is_dir() or (root / '.git').is_symlink():
        raise UpdateError('unsupported_git_directory')
    if _text(['rev-parse', '--show-toplevel'], root) != str(root):
        raise UpdateError('not_checkout_root')
    if _text(['symbolic-ref', '--quiet', '--short', 'HEAD'], root) != 'main':
        raise UpdateError('branch_not_main')
    urls = _git(['config', '--local', '--get-all', 'remote.origin.url'], root).stdout.decode().splitlines()
    if urls != [OFFICIAL_REMOTE]:
        raise UpdateError('untrusted_origin')
    if _text(['config', '--local', '--get', 'branch.main.remote'], root) != 'origin' or _text(['config', '--local', '--get', 'branch.main.merge'], root) != 'refs/heads/main':
        raise UpdateError('unexpected_upstream')
    # Do not execute repository-specific conversion filters, includes, URL
    # rewrites, alternate upload commands or custom attributes.
    keys = _git(['config', '--local', '--name-only', '--list'], root).stdout.decode().lower().splitlines()
    forbidden = ('filter.', 'url.', 'include.', 'includeif.', 'core.attributesfile',
                 'core.worktree', 'remote.origin.uploadpack', 'extensions.worktreeconfig')
    if any(any(k.startswith(x) for x in forbidden) for k in keys):
        raise UpdateError('unsafe_git_config')
    gd = Path(_text(['rev-parse', '--absolute-git-dir'], root))
    if (gd / 'info' / 'attributes').exists() or (root / '.gitattributes').exists():
        raise UpdateError('unsafe_git_attributes')
    head = _text(['rev-parse', '--verify', 'HEAD'], root)
    if not SHA.fullmatch(head):
        raise UpdateError('invalid_head')
    index = _git(['ls-files', '-v', '-z'], root).stdout.split(b'\0')
    if any(row and (row[:1] == b'S' or row[:1].islower()) for row in index):
        raise UpdateError('hidden_index_changes')
    dirty = _git(['status', '--porcelain=v1', '-z', '--untracked-files=all'], root).stdout
    version = (root / 'VERSION').read_text(encoding='utf-8').strip()[:64]
    return root, head, version, bool(dirty)


def _target():
    out = _text(['ls-remote', '--exit-code', OFFICIAL_REMOTE, 'refs/heads/main'])
    lines = out.splitlines()
    if len(lines) != 1:
        raise UpdateError('invalid_remote_head')
    fields = lines[0].split()
    if len(fields) != 2 or fields[1] != 'refs/heads/main' or not SHA.fullmatch(fields[0]):
        raise UpdateError('invalid_remote_head')
    return fields[0]


def check(repo):
    result = dict(status='blocked', current_sha=None, current_version=None,
                  target_sha=None, dirty=False, reasons=[])
    try:
        root, head, version, dirty = _local(repo)
        result.update(current_sha=head, current_version=version, dirty=dirty)
        if dirty:
            result['reasons'].append('dirty_checkout')
            return result
        if (root / '.mac-update.lock').exists() and _owned_lock != str(root):
            result['reasons'].append('run_lock_present')
            return result
        target = _target()
        result.update(target_sha=target, status='current' if head == target else 'available')
    except (UpdateError, OSError, ValueError, UnicodeError) as exc:
        result['reasons'].append(str(exc) if isinstance(exc, UpdateError) else 'inspection_failed')
    return result


def _receipt_digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def prepare(repo):
    result = check(repo)
    if result['status'] != 'available':
        return result
    root = Path(repo).resolve(strict=True)
    head, target = result['current_sha'], result['target_sha']
    try:
        with tempfile.TemporaryDirectory(prefix='mac_update_review_') as tmp:
            _git(['init', '--bare', tmp])
            _git(['--git-dir', tmp, '-c', 'protocol.file.allow=always', 'fetch', '--no-tags', str(root), head])
            _git(['--git-dir', tmp, 'fetch', '--no-tags', OFFICIAL_REMOTE, target])
            if _git(['--git-dir', tmp, 'merge-base', '--is-ancestor', head, target], check=False).returncode:
                raise UpdateError('not_fast_forward')
            changed = _git(['--git-dir', tmp, 'diff', '--name-only', '-z', head, target]).stdout.split(b'\0')
            if any(p == b'.gitattributes' or p.endswith(b'/.gitattributes') for p in changed):
                raise UpdateError('unsafe_git_attributes')
            ignored = _git(['ls-files', '--others', '--ignored', '--exclude-standard', '-z'], root).stdout.split(b'\0')
            if any(a == b or a.startswith(b + b'/') or b.startswith(a + b'/')
                   for a in changed if a for b in ignored if b):
                raise UpdateError('ignored_path_collision')
            # All tracked attribute files matter, not only the root attribute file.
            if any(p == b'.gitattributes' or p.endswith(b'/.gitattributes') for p in _git(['--git-dir', tmp, 'ls-tree', '-r', '--name-only', target]).stdout.splitlines()):
                raise UpdateError('unsafe_git_attributes')
            target_version = _text(['--git-dir', tmp, 'show', target + ':VERSION'])[:64]
        data = dict(schema=1, repo=str(root), current_sha=head, target_sha=target,
                    current_version=result['current_version'], target_version=target_version,
                    created=int(time.time()), changed_paths=[os.fsdecode(p) for p in changed if p])
        data['digest'] = _receipt_digest(data)
        return dict(result, status='ready', receipt=data)
    except (UpdateError, OSError, UnicodeError, ValueError) as exc:
        return dict(result, status='blocked', reasons=[str(exc) if isinstance(exc, UpdateError) else 'preview_failed'])


def apply(repo, receipt, confirmed=False):
    if not confirmed:
        return dict(status='blocked', reasons=['explicit_confirmation_required'])
    if not isinstance(receipt, dict):
        return dict(status='blocked', reasons=['invalid_receipt'])
    data = dict(receipt)
    digest = data.pop('digest', None)
    try:
        valid_digest = digest == _receipt_digest(data)
    except (ValueError, TypeError):
        valid_digest = False
    if not valid_digest or type(data.get('created')) is not int or not 0 <= time.time() - data['created'] <= RECEIPT_TTL:
        return dict(status='blocked', reasons=['invalid_or_expired_receipt'])
    root = Path(repo).resolve()
    if str(root) != data.get('repo') or not SHA.fullmatch(str(data.get('target_sha', ''))):
        return dict(status='blocked', reasons=['invalid_receipt'])
    try:
        fd = os.open(root / '.mac-update.lock', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as lock:
            lock.write('pid=%s\nstarted_unix=%s\n' % (os.getpid(), time.time()))
    except OSError:
        return dict(status='blocked', reasons=['run_lock_present'])
    lease = None
    mutation_started = False
    mutation_complete = False
    try:
        lease = claim_action_resources(dict(action_id='toolkit-update:' + str(uuid.uuid4()),
                                            resources=['exclusive:toolkit'],
                                            scope_complete=False, parallel_safe=False))
        # Rebuild the preview while holding the run lock. check() itself sees
        # our lock, so temporarily use the explicit owned-lock-aware helper.
        fresh = _prepare_owned(root)
        if fresh.get('status') != 'ready':
            return fresh
        fresh_data = fresh['receipt']
        for key in ('repo', 'current_sha', 'target_sha', 'current_version', 'target_version', 'changed_paths'):
            if fresh_data[key] != data.get(key):
                return dict(status='blocked', reasons=['preview_changed'])
        mutation_started = True
        _git(['fetch', '--no-tags', OFFICIAL_REMOTE, data['target_sha']], root)
        _, head, _, dirty = _local(root)
        if head != data['current_sha'] or dirty or _target() != data['target_sha']:
            raise UpdateError('checkout_changed')
        _git(['merge', '--ff-only', '--no-overwrite-ignore', data['target_sha']], root)
        updated_sha = _text(['rev-parse', 'HEAD'], root)
        if updated_sha != data['target_sha']:
            raise UpdateError('updated_head_mismatch')
        mutation_complete = True
        return dict(status='updated', current_sha=updated_sha,
                    current_version=data['current_version'], target_version=data['target_version'],
                    restart_required=True)
    except (UpdateError, OSError, ValueError, StoreError) as exc:
        return dict(status='failed', reasons=[str(exc) if isinstance(exc, UpdateError) else 'apply_failed'],
                    message='Inspect the checkout before retrying; restart the toolkit.')
    finally:
        try:
            if lease is not None:
                if mutation_started and not mutation_complete:
                    lease.pending('toolkit_update_unconfirmed')
                else:
                    lease.finish('finished', helpers_complete=True)
        finally:
            release(root)


def _prepare_owned(root):
    # A live owned lock must not be removed to perform a preview.
    global _owned_lock
    _owned_lock = str(root)
    try:
        return prepare(root)
    finally:
        _owned_lock = None


_owned_lock = None


def read_receipt(path):
    """Read one bounded private regular file without following links or FIFOs."""
    import stat
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
        with os.fdopen(fd, 'rb') as stream:
            st = os.fstat(stream.fileno())
            if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid()
                    or stat.S_IMODE(st.st_mode) != 0o600 or st.st_nlink != 1 or st.st_size > 65536):
                raise ValueError('invalid_receipt_file')
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError('invalid_receipt_file')
        value = json.loads(raw.decode('utf-8'))
        if not isinstance(value, dict):
            raise ValueError('invalid_receipt_file')
        receipt = value.get('receipt', value)
        if not isinstance(receipt, dict) or not isinstance(receipt.get('target_sha'), str) or not SHA.fullmatch(receipt['target_sha']):
            raise ValueError('invalid_receipt_file')
        return receipt
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('invalid_receipt_file') from exc


# Fallbacks keep CLI readable until a matching catalog entry is available.
_CLI_FALLBACK = {
    'toolkit_status': 'Status', 'toolkit_current_version': 'Current version',
    'toolkit_target_version': 'Target version', 'toolkit_reasons': 'Reason',
    'toolkit_restart': 'Close all other toolkit sessions before continuing. Restart the toolkit after an update.',
    'toolkit_confirm_sha': 'Type the full commit ID to confirm: ',
    'toolkit_invalid_receipt': 'Invalid receipt.',
    'toolkit_terminal_required': 'A terminal is required.',
}


def toolkit_status_label(status, lang="en"):
    """Translate a closed result code for human display, preserving JSON codes."""
    from tui_i18n import tr
    if status not in ("blocked", "current", "available", "ready", "updated", "failed"):
        status = "failed"
    return tr("toolkit_status_" + status, lang)


def toolkit_reason_label(reason, lang="en"):
    """Explain known failure classes without exposing raw internal codes."""
    from tui_i18n import tr
    groups = {
        "dirty": {"dirty_checkout", "ignored_path_collision", "hidden_index_changes"},
        "branch": {"branch_not_main", "unsupported_git_directory", "not_checkout_root", "unexpected_upstream", "not_fast_forward"},
        "origin": {"untrusted_origin", "unsafe_git_config", "unsafe_git_attributes", "invalid_remote_head"},
        "busy": {"run_lock_present", "scheduler_busy", "resource_conflict", "mutation_capacity_reached"},
        "changed": {"preview_changed", "checkout_changed", "updated_head_mismatch", "invalid_or_expired_receipt", "invalid_receipt"},
    }
    category = next((key for key, values in groups.items() if reason in values), "unknown")
    return tr("toolkit_reason_" + category, lang)


def main(repo, argv=None):
    import argparse
    import sys
    from tui_i18n import tr
    lang = os.environ.get('MAC_UPDATE_LANG') or os.environ.get('MAC_LANG') or 'en'
    def translate(key, **values):
        result = tr(key, lang, **values)
        return _CLI_FALLBACK.get(key, key) if result == key else result
    def safe(value):
        return ''.join(c for c in str(value or '-') if c.isprintable())[:128]
    parser = argparse.ArgumentParser(description='Toolkit update')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--prepare', action='store_true')
    group.add_argument('--apply', metavar='RECEIPT_JSON')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    if args.apply:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            print(translate('toolkit_terminal_required'), file=sys.stderr)
            return 2
        try:
            receipt = read_receipt(args.apply)
            target = receipt['target_sha']
            print(translate('toolkit_restart'))
            print(target)
            confirmed = input(translate('toolkit_confirm_sha', sha=target)).strip() == target
        except (ValueError, EOFError):
            print(translate('toolkit_invalid_receipt'), file=sys.stderr)
            return 2
        result = apply(repo, receipt, confirmed=confirmed)
    else:
        result = check(repo) if args.check else prepare(repo)
    if args.json:
        print(json.dumps(result, ensure_ascii=True))
    elif os.environ.get('MAC_UPDATE_TUI_CHILD') == '1' and not args.apply:
        print('@@MAC_UPDATE_TOOLKIT ' + json.dumps(result, ensure_ascii=True))
    else:
        print(translate('toolkit_status'))
        print(translate('toolkit_status') + ': ' + toolkit_status_label(result.get('status'), lang))
        print(translate('toolkit_current_version') + ': ' + safe(result.get('current_version')))
        target_version = result.get('target_version') or result.get('receipt', {}).get('target_version')
        print(translate('toolkit_target_version') + ': ' + safe(target_version))
        for reason in result.get('reasons', []):
            print(translate('toolkit_reasons') + ': ' + toolkit_reason_label(reason, lang))
        if result.get('restart_required'):
            print(translate('toolkit_restart'))
    return 0 if result.get('status') in ('current', 'available', 'ready', 'updated') else 2
