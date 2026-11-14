"""Scoped legacy shell compatibility, always with mocked executors."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class ScopedLegacyBridgeTests(unittest.TestCase):
    def run_shell(self, body, dry=False):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = root / 'Example;literal.app'
            target.mkdir()
            env = dict(os.environ, TEST_ROOT=str(root), TEST_TARGET=str(target),
                       SCRIPT_DIR=str(ROOT), MAC_UPDATE_SESSION_DIR=str(root),
                       MAC_UPDATE_PLAN_PATH='fixture-plan', MAC_UPDATE_ACTION_ID='fixture-action',
                       MAC_UPDATE_BATCH_OWNER='fixture-batch', MAC_UPDATE_DRY_RUN='1' if dry else '0')
            script = '''. "$SCRIPT_DIR/lib/scoped_legacy.sh"
python3() { printf '%s\\n' iu_fixture "$TEST_TARGET" Example fixture.bundle Example; }
open() { echo 'UNEXPECTED HOST LAUNCH'; return 99; }
''' + body
            result = subprocess.run(['/bin/bash', '-c', script], env=env, stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, timeout=10)
            files = {p.name:p.read_text() for p in root.iterdir() if p.is_file()}
            return result, files

    def test_native_fallback_only_requests_supervisor_handoff(self):
        result, files = self.run_shell('''
scoped_legacy_prepare || exit $?
iu_fixture() { silent_launch_app "$SCOPED_LEGACY_TARGET"; }
scoped_legacy_execute
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(files['native_launch_requested'], 'fixture-action\n')
        self.assertNotIn('UNEXPECTED', result.stdout)

    def test_dry_run_never_reads_plan_or_runs_handler(self):
        result, files = self.run_shell('''
python3() { echo unexpected > "$TEST_ROOT/python-called"; return 99; }
scoped_legacy_prepare
''', dry=True)
        self.assertEqual(result.returncode, 10)
        self.assertEqual(files, {})

    def test_another_target_cannot_be_discovered_launched_or_replaced(self):
        result, files = self.run_shell('''
scoped_legacy_prepare || exit $?
iu_fixture() {
  internet_app_path Other && return 99
  silent_launch_app Other && return 99
  copy_verified_app "$TEST_TARGET" "$TEST_ROOT/Other.app" fixture-action && return 99
  [ "$INTERNET_COPY_DEFERRED" = 1 ]
}
scoped_legacy_execute
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('native_launch_requested', files)

    def test_legacy_handler_cannot_quit_user_application(self):
        result, _ = self.run_shell('''
scoped_legacy_prepare || exit $?
iu_fixture() { internet_app_quit_gracefully fixture.bundle && return 99; return 0; }
scoped_legacy_execute
''')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_hard_failure_preserves_hard_exit(self):
        result, _ = self.run_shell('''
scoped_legacy_prepare || exit $?
iu_fixture() { INTERNET_HARD_FAIL=1; }
scoped_legacy_execute
''')
        self.assertEqual(result.returncode, 1)

    def test_office_invokes_only_consented_ids_without_preferences_or_termination(self):
        result, files = self.run_shell('''
scoped_legacy_prepare || exit $?
SCOPED_LEGACY_HANDLER=iu_microsoft_365
SCOPED_LEGACY_MAU_IDS="MSWD2019 XCEL2019"
iu_microsoft_365() { return 99; }
scoped_legacy_mau_binary() { printf '%s\\n' "$TEST_ROOT/msupdate"; }
printf '#!/bin/bash\\nexit 99\\n' > "$TEST_ROOT/msupdate"
chmod +x "$TEST_ROOT/msupdate"
run_with_timeout() { printf '%s\\n' "$@" > "$TEST_ROOT/argv"; }
killall() { echo unexpected > "$TEST_ROOT/kill"; return 99; }
defaults() { echo unexpected > "$TEST_ROOT/preferences"; return 99; }
scoped_legacy_execute
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        args = files['argv'].splitlines()
        self.assertEqual(args[-3:], ['--apps', 'MSWD2019', 'XCEL2019'])
        self.assertNotIn('--terminate', args)
        self.assertNotIn('kill', files)
        self.assertNotIn('preferences', files)

    def test_missing_real_plan_refuses_bridge_without_host_actions(self):
        result, files = self.run_shell('''
unset -f python3
scoped_legacy_prepare
''')
        self.assertEqual(result.returncode, 10, result.stdout + result.stderr)
        self.assertEqual(files, {})
