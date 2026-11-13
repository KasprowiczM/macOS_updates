import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class DeveloperToolShimTests(unittest.TestCase):
    def run_helper(self, tool, location, clt):
        with tempfile.TemporaryDirectory() as temp:
            developer = pathlib.Path(temp) / 'Developer'
            if clt == 'yes':
                (developer / 'usr/bin').mkdir(parents=True)
                binary = developer / 'usr/bin' / tool
                binary.write_text('#!/bin/sh\nexit 99\n')
                binary.chmod(0o755)
            env = dict(os.environ, TEST_DEVELOPER=str(developer), MAC_UPDATE_HOMEBREW_PREFIX=temp,
                       TEST_TOOL=tool, TEST_LOCATION=location, TEST_CLT=clt,
                       TEST_LOG=str(pathlib.Path(temp) / 'log'))
            script = '''
command() { if [ "$1" = -v ] && [ "$2" = "$TEST_TOOL" ]; then printf '%s\\n' "$TEST_LOCATION"; else builtin command "$@"; fi; }
xcode-select() { printf 'probe\\n' >> "$TEST_LOG"; [ "$TEST_CLT" != no ] || return 1; echo "$TEST_DEVELOPER"; }
. "$1/lib/platform.sh"
mac_update_tool_usable "$TEST_TOOL"
'''
            result = subprocess.run(['/bin/bash', '-c', script, 'bash', str(ROOT)], env=env, capture_output=True)
            log = pathlib.Path(temp) / 'log'
            return result.returncode, log.read_text().splitlines() if log.exists() else []

    def test_unprovisioned_apple_shims_are_refused(self):
        for tool in ('git', 'python3'):
            with self.subTest(tool=tool):
                code, log = self.run_helper(tool, '/usr/bin/' + tool, 'no')
                self.assertNotEqual(code, 0)
                self.assertEqual(log, ['probe'])

    def test_provisioned_apple_shims_are_accepted(self):
        for tool in ('git', 'python3'):
            with self.subTest(tool=tool):
                self.assertEqual(self.run_helper(tool, '/usr/bin/' + tool, 'yes'), (0, ['probe']))

    def test_selected_but_missing_developer_tools_are_refused(self):
        self.assertNotEqual(self.run_helper('python3', '/usr/bin/python3', 'orphan')[0], 0)

    def test_external_python_does_not_probe_clt(self):
        self.assertEqual(self.run_helper('python3', '/opt/homebrew/bin/python3', 'no'), (0, []))

    def test_installer_does_not_execute_unprovisioned_git_shim(self):
        with tempfile.TemporaryDirectory() as temp:
            base = pathlib.Path(temp)
            env_file = base / 'env'
            env_file.write_text('''
uname() { echo arm64; }
sw_vers() { echo 14.0; }
command() { if [ "$1" = -v ] && [ "$2" = git ]; then echo /usr/bin/git; else builtin command "$@"; fi; }
xcode-select() { echo "$*" >> "$TEST_LOG"; return 1; }
git() { echo EXECUTED >> "$TEST_LOG"; return 1; }
''')
            env = dict(os.environ, BASH_ENV=str(env_file), HOME=temp, TEST_LOG=str(base / 'log'), MAC_UPDATE_DIR=str(base / 'repo'))
            result = subprocess.run(['/bin/bash', str(ROOT / 'install.sh')], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((base / 'log').read_text().splitlines(), ['-p'])
            self.assertFalse((base / 'repo').exists())
