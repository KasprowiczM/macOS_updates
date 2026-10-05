"""Native-first migration and conservative package-specific deduplication."""

import json
import os
from pathlib import Path
import tempfile
import unittest

from tests.test_cli_installers import _run_npm_cli, REPO_ROOT
from tests._env import shell_env

import sys
sys.path.insert(0, str(REPO_ROOT / 'lib/python'))
from cli_duplicates import known_npm_prefixes, npm_duplicates, removal_allowed, supported_native_path


class DuplicatePlannerTests(unittest.TestCase):
    def test_only_explicit_harness_package_in_known_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            prefix = home / '.nvm/versions/node/v24.0.0'
            package = prefix / 'lib/node_modules/opencode-ai'
            package.mkdir(parents=True)
            (package / 'package.json').write_text(json.dumps({'name': 'opencode-ai', 'version': '1.2.3'}))
            prefixes = known_npm_prefixes(str(home), str(home / 'managed'))
            self.assertEqual(npm_duplicates(prefixes, 'opencode'), [(prefix, '1.2.3')])
            self.assertEqual(npm_duplicates(prefixes, 'cline'), [])

    def test_native_proof_rejects_every_npm_prefix_and_arbitrary_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            for target in ['.local/share/mac-update/npm-global/lib/node_modules/opencode-ai/bin/opencode', '.nvm/versions/node/v24/lib/node_modules/opencode-ai/bin/opencode', '.local/bin/arbitrary']:
                executable = home / target; executable.parent.mkdir(parents=True, exist_ok=True); executable.write_text('binary')
                self.assertFalse(supported_native_path(str(home), 'opencode', str(executable)))
            native = home / '.opencode/bin/opencode'; native.parent.mkdir(parents=True); native.write_text('binary')
            self.assertTrue(supported_native_path(str(home), 'opencode', str(native)))

    def test_symlink_package_is_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            other = root / 'user-package'
            other.mkdir()
            (other / 'package.json').write_text(json.dumps({'name': 'opencode-ai', 'version': '1.2.3'}))
            prefix = root / 'prefix'
            modules = prefix / 'lib/node_modules'
            modules.mkdir(parents=True)
            (modules / 'opencode-ai').symlink_to(other, target_is_directory=True)
            self.assertEqual(npm_duplicates([prefix], 'opencode'), [])

    def test_uncertain_or_older_native_never_removes_fallback(self):
        for native, package, processes in [('1.2.2', '1.2.3', ''), ('?', '1.2.3', ''), ('1.2.3', '?', ''), ('1.2.3', '1.2.3', None)]:
            self.assertFalse(removal_allowed(native, package, processes, 'opencode'))
        self.assertTrue(removal_allowed('1.2.3', '1.2.3', '/usr/bin/other', 'opencode'))

    def test_active_native_or_npm_wrapper_retains_duplicates(self):
        for processes in ['/some/bin/opencode run', 'node /prefix/lib/node_modules/opencode-ai/bin/opencode', 'node --enable-source-maps /prefix/lib/node_modules/opencode-ai/bin/opencode', '/prefix/opencode.exe', 'bash -- /prefix/bin/opencode']:
            self.assertFalse(removal_allowed('1.2.3', '1.2.2', processes, 'opencode'))
        self.assertTrue(removal_allowed('1.2.3', '1.2.2', '/Applications/OpenCode.app/Contents/MacOS/OpenCode', 'opencode'))
        self.assertTrue(removal_allowed('1.2.3', '1.2.2', 'bash -c type -a opencode; opencode --version', 'opencode'))


class NativeFirstTests(unittest.TestCase):
    def test_brew_opencode_cleanup_requires_native_version_and_inactive_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            installed = home / '.opencode/bin/opencode'; installed.parent.mkdir(parents=True)
            installed.write_text('#!/bin/sh\necho 1.2.3\n'); installed.chmod(0o755)
            local = home / '.local/bin'; local.mkdir(parents=True)
            (local / 'opencode').symlink_to(installed)
            mocks = home / 'mocks'; mocks.mkdir()
            ps = mocks / 'ps'
            log = home / 'uninstalled'
            snippet = f'''export PATH="$LOCAL_BIN:$PATH";
brew() {{ case "$*" in "--prefix") echo /mockbrew ;; "list --formula opencode") return 0 ;; "uninstall --formula opencode") touch "{log}" ;; *) return 1 ;; esac; }};
brew_formula_versions() {{ echo "opencode $TEST_BREW_VERSION"; }};
remove_legacy_brew_formulas'''
            for version, process, allowed in [('1.2.4', '', False), ('1.2.2', '/mockbrew/bin/opencode run', False), ('1.2.2', '/usr/bin/other', True)]:
                ps.write_text('#!/bin/sh\nprintf "%s\\n" "' + process + '"\n'); ps.chmod(0o755)
                result = _run_npm_cli(snippet, shell_env(HOME=str(home), PATH=f'{mocks}:{os.environ["PATH"]}', TEST_BREW_VERSION=version))
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                self.assertEqual(log.exists(), allowed, result.stdout)

    def test_cleanup_removes_only_matching_package_from_explicit_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            toolchain = home / '.local/share/mac-update'
            prefix = toolchain / 'npm-global'
            duplicate = prefix / 'lib/node_modules/opencode-ai'
            duplicate.mkdir(parents=True)
            (duplicate / 'package.json').write_text(json.dumps({'name': 'opencode-ai', 'version': '1.2.2'}))
            unrelated = prefix / 'lib/node_modules/unrelated'; unrelated.mkdir()
            npm = toolchain / 'node/bin/npm'; npm.parent.mkdir(parents=True)
            log = home / 'npm-log'
            npm.write_text(f'''#!{sys.executable}
import json, pathlib, shutil, sys
args = sys.argv[1:]
pathlib.Path({str(log)!r}).write_text(json.dumps(args))
prefix = pathlib.Path(args[args.index('--prefix') + 1])
shutil.rmtree(prefix / 'lib/node_modules' / args[-1])
'''); npm.chmod(0o755)
            installed = home / '.opencode/bin/opencode'; installed.parent.mkdir(parents=True)
            installed.write_text('#!/bin/sh\necho 1.2.3\n'); installed.chmod(0o755)
            native = home / '.local/bin/opencode'; native.parent.mkdir(parents=True)
            native.symlink_to(installed)
            result = _run_npm_cli('export PATH="$LOCAL_BIN:$PATH"; cleanup_native_npm_duplicates', shell_env(HOME=str(home)))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(json.loads(log.read_text()), ['uninstall', '-g', '--prefix', str(prefix), '--ignore-scripts', 'opencode-ai'])
            self.assertFalse(duplicate.exists()); self.assertTrue(unrelated.exists()); self.assertTrue(native.exists())

    def test_native_work_precedes_node_and_npm(self):
        source = (REPO_ROOT / 'update_npm_cli.sh').read_text().split('NODE_READY=1\n_ensure_node_rc=0')[0]
        self.assertTrue(source.rstrip().endswith('update_opencode_native_first || SOFT_FAIL=1'))
        self.assertIn('update_native_clis || SOFT_FAIL=1', source)

    def test_native_opencode_skips_npm_self_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            npm = home / '.local/share/mac-update/node/bin/npm'
            npm.parent.mkdir(parents=True)
            npm.write_text('#!/bin/sh\nexit 99\n'); npm.chmod(0o755)
            native = home / '.local/bin/opencode'
            native.parent.mkdir(parents=True)
            native.write_text('#!/bin/sh\necho 1.2.3\n'); native.chmod(0o755)
            manifest = home / 'manifest'
            manifest.write_text('opencode-cli|opencode-ai|self-update|opencode|opencode\n')
            result = _run_npm_cli('OPENCODE_NATIVE_OK=1; install_latest_npm_packages', shell_env(HOME=str(home), MANIFEST_PATH=str(manifest)))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('updater', result.stdout)

    def test_failed_native_migration_preserves_npm_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            npm_cli = home / '.local/share/mac-update/npm-global/bin/opencode'
            npm_cli.parent.mkdir(parents=True)
            npm_cli.write_text('#!/bin/sh\necho 1.2.3\n'); npm_cli.chmod(0o755)
            local = home / '.local/bin'
            local.mkdir(parents=True)
            result = _run_npm_cli('download_installer_script() { return 1; }; update_opencode_native_first', shell_env(HOME=str(home), PATH=f'{npm_cli.parent}:{os.environ["PATH"]}'))
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(npm_cli.exists())
            self.assertFalse((local / 'opencode').exists())

    def test_unknown_user_local_command_is_not_executed_or_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            local = home / '.local/bin'; local.mkdir(parents=True)
            log = home / 'executed'
            command = local / 'opencode'
            command.write_text(f'#!/bin/sh\ncase "$1" in --version) echo 1.2.3 ;; *) touch "{log}" ;; esac\n')
            command.chmod(0o755)
            result = _run_npm_cli('update_opencode_native_first', shell_env(HOME=str(home), PATH=f'{local}:{os.environ["PATH"]}'))
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(log.exists())
            self.assertFalse(command.is_symlink())

    def test_older_native_release_retains_npm_and_does_not_publish_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            npm_cli = home / '.local/share/mac-update/npm-global/bin/opencode'
            npm_cli.parent.mkdir(parents=True)
            npm_cli.write_text('#!/bin/sh\necho 1.2.3\n'); npm_cli.chmod(0o755)
            installed = home / '.opencode/bin/opencode'; installed.parent.mkdir(parents=True)
            installed.write_text('#!/bin/sh\necho 1.2.2\n'); installed.chmod(0o755)
            local = home / '.local/bin'; local.mkdir(parents=True)
            result = _run_npm_cli('update_opencode_native_first', shell_env(HOME=str(home), PATH=f'{npm_cli.parent}:{os.environ["PATH"]}'))
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(npm_cli.exists())
            self.assertFalse((local / 'opencode').exists())

    def test_installer_migrates_equal_npm_version_and_disables_profile_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            npm_cli = home / '.local/share/mac-update/npm-global/bin/opencode'
            npm_cli.parent.mkdir(parents=True)
            npm_cli.write_text('#!/bin/sh\necho 1.2.3\n'); npm_cli.chmod(0o755)
            local = home / '.local/bin'; local.mkdir(parents=True)
            installer = home / 'installer'
            installer.write_text('''#!/bin/bash
test "$1" = --no-modify-path || exit 9
command -v opencode >/dev/null && exit 8
mkdir -p "$HOME/.opencode/bin"
printf '#!/bin/sh\\necho 1.2.3\\n' > "$HOME/.opencode/bin/opencode"
chmod +x "$HOME/.opencode/bin/opencode"
''')
            snippet = f'download_installer_script() {{ cp "{installer}" "$2"; }}; update_opencode_native_first; test "$OPENCODE_NATIVE_OK" = 1'
            result = _run_npm_cli(snippet, shell_env(HOME=str(home), PATH=f'{npm_cli.parent}:{os.environ["PATH"]}'))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue((local / 'opencode').is_symlink())
            self.assertTrue(npm_cli.exists(), 'migration itself does not delete fallback')


if __name__ == '__main__':
    unittest.main()
