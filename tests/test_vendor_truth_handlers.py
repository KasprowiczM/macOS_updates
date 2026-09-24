#!/usr/bin/env python3
"""tests/test_vendor_truth_handlers.py — tests for vendor truth handlers."""

import base64
import hashlib
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

try:
    from ._env import shell_env
except ImportError:
    from _env import shell_env

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@unittest.skipUnless(shutil.which("bash"), "bash required")
class TestVendorTruthHandlers(unittest.TestCase):

    def setUp(self):
        self.fixtures_dir = os.path.join(REPO_ROOT, "tests", "fixtures", "vendor_feeds")
        self.tmpdir = tempfile.mkdtemp(prefix="mac_update_vth_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run_bash(self, script: str, extra_env: dict = None) -> subprocess.CompletedProcess:
        env = shell_env(SCRIPT_DIR=REPO_ROOT, **(extra_env or {}))
        return subprocess.run(
            ["bash", "-c", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

    def test_sparkle_check_stale_feed_is_not_current(self):
        rdm_fixture = os.path.join(self.fixtures_dir, "rdm_ascending.xml")
        script = f"""
        . "{REPO_ROOT}/i18n/lang_en.sh"
        . "{REPO_ROOT}/lib/version.sh"
        . "{REPO_ROOT}/lib/internet_i18n.sh"
        . "{REPO_ROOT}/lib/ui.sh" 2>/dev/null || true
        print_info() {{ :; }}
        print_warn() {{ :; }}
        print_step() {{ :; }}
        print_ok() {{ :; }}
        defaults() {{ echo "https://example.com/appcast.xml"; }}
        curl() {{ cat "{rdm_fixture}"; }}
        app_version() {{ echo "2026.3.0.5"; }}
        silent_launch_app() {{ return 0; }}

        . "{REPO_ROOT}/lib/internet_handlers.sh"

        internet_handler_sparkle_check "Remote Desktop Manager" "/Applications/Remote Desktop Manager.app" "Remote Desktop Manager"
        echo "STATUS=$INTERNET_LAST_STATUS"
        echo "VERIFIED=$INTERNET_LAST_VERIFIED"
        """
        proc = self._run_bash(script)
        self.assertEqual(proc.returncode, 0, f"Stderr: {proc.stderr}")
        self.assertIn("stale", proc.stdout.lower())
        self.assertIn("VERIFIED=0", proc.stdout)

    def test_sparkle_check_max_item_detects_update(self):
        docker_fixture = os.path.join(self.fixtures_dir, "docker_attr.xml")
        script = f"""
        . "{REPO_ROOT}/i18n/lang_en.sh"
        . "{REPO_ROOT}/lib/version.sh"
        . "{REPO_ROOT}/lib/internet_i18n.sh"
        . "{REPO_ROOT}/lib/ui.sh" 2>/dev/null || true
        print_info() {{ :; }}
        print_warn() {{ :; }}
        print_step() {{ :; }}
        print_ok() {{ :; }}
        defaults() {{ echo "https://example.com/appcast.xml"; }}
        curl() {{ cat "{docker_fixture}"; }}
        app_version() {{ echo "4.91.0"; }}
        silent_launch_app() {{ return 0; }}

        . "{REPO_ROOT}/lib/internet_handlers.sh"

        internet_handler_sparkle_check "Docker Desktop" "/Applications/Docker.app" "Docker"
        echo "STATUS=$INTERNET_LAST_STATUS"
        echo "VERIFIED=$INTERNET_LAST_VERIFIED"
        """
        proc = self._run_bash(script)
        self.assertEqual(proc.returncode, 0, f"Stderr: {proc.stderr}")
        self.assertIn("Update available", proc.stdout)
        self.assertIn("4.92.0", proc.stdout)
        self.assertIn("VERIFIED=1", proc.stdout)

    def test_vendor_direct_host_allowlist(self):
        script = f"""
        . "{REPO_ROOT}/lib/vendor_direct.sh"
        vendor_direct_host_allowed "https://downloads.claude.ai/releases/darwin/universal/RELEASES.json" "downloads.claude.ai"
        echo "MATCH1=$?"
        vendor_direct_host_allowed "https://evil.com/releases/RELEASES.json" "downloads.claude.ai"
        echo "MATCH2=$?"
        vendor_direct_host_allowed "http://downloads.claude.ai/releases/RELEASES.json" "downloads.claude.ai"
        echo "MATCH3=$?"
        """
        proc = self._run_bash(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("MATCH1=0", proc.stdout)
        self.assertIn("MATCH2=1", proc.stdout)
        self.assertIn("MATCH3=1", proc.stdout)

    def test_vendor_direct_checksum_kinds(self):
        sample_file = os.path.join(self.tmpdir, "sample.bin")
        data = b"hello macOS Updates v1.5.0\n"
        with open(sample_file, "wb") as f:
            f.write(data)

        sha256 = hashlib.sha256(data).hexdigest().upper()
        sha512_b64 = base64.b64encode(hashlib.sha512(data).digest()).decode("ascii")

        script = f"""
        . "{REPO_ROOT}/lib/vendor_direct.sh"
        vendor_direct_verify_checksum "{sample_file}" "sha256hex" "{sha256}"
        echo "SHA256_UPPER=$?"
        vendor_direct_verify_checksum "{sample_file}" "sha512b64" "{sha512_b64}"
        echo "SHA512_B64=$?"
        vendor_direct_verify_checksum "{sample_file}" "sha256hex" "0000000000000000000000000000000000000000000000000000000000000000"
        echo "MISMATCH=$?"
        """
        proc = self._run_bash(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("SHA256_UPPER=0", proc.stdout)
        self.assertIn("SHA512_B64=0", proc.stdout)
        self.assertIn("MISMATCH=1", proc.stdout)

    def test_vendor_direct_refuses_non_applications_path(self):
        script = f"""
        . "{REPO_ROOT}/lib/vendor_direct.sh"
        vendor_direct_install "/Users/fake/Test.app" "https://example.com/app.zip" "zip" "-" "-" "example.com"
        echo "RC=$?"
        """
        proc = self._run_bash(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("RC=1", proc.stdout)

    def test_vendor_direct_dry_run_returns_2(self):
        script = f"""
        MAC_UPDATE_DRY_RUN=1
        . "{REPO_ROOT}/lib/vendor_direct.sh"
        vendor_direct_install "/Applications/Test.app" "https://example.com/app.zip" "zip" "-" "-" "example.com"
        echo "RC=$?"
        """
        proc = self._run_bash(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("RC=2", proc.stdout)

    def test_vendor_truth_equal_does_not_launch(self):
        open_log = os.path.join(self.tmpdir, "open.log")
        script = f"""
        . "{REPO_ROOT}/i18n/lang_en.sh"
        . "{REPO_ROOT}/lib/version.sh"
        . "{REPO_ROOT}/lib/internet_i18n.sh"
        . "{REPO_ROOT}/lib/vendor_feeds.sh"
        . "{REPO_ROOT}/lib/vendor_direct.sh"
        . "{REPO_ROOT}/lib/internet_handlers.sh"

        print_info() {{ :; }}
        print_warn() {{ :; }}
        print_step() {{ :; }}
        silent_launch_app() {{ echo "$@" >> "{open_log}"; return 0; }}
        app_version() {{ echo "2.0.0"; }}
        vendor_feed_lookup() {{ echo "2.0.0|https://downloads.claude.ai/app.zip|-|-|zip|downloads.claude.ai"; }}

        internet_handler_vendor_truth "Claude" "/Applications/Claude.app" "Claude"
        echo "STATUS=$INTERNET_LAST_STATUS"
        echo "VERIFIED=$INTERNET_LAST_VERIFIED"
        """
        proc = self._run_bash(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Up to date", proc.stdout)
        self.assertIn("vendor feed", proc.stdout)
        self.assertIn("VERIFIED=1", proc.stdout)
        self.assertFalse(os.path.exists(open_log), "silent_launch_app was called when versions are equal")

    def test_vendor_truth_running_app_is_never_touched(self):
        open_log = os.path.join(self.tmpdir, "open.log")
        quit_log = os.path.join(self.tmpdir, "quit.log")
        script = f"""
        . "{REPO_ROOT}/i18n/lang_en.sh"
        . "{REPO_ROOT}/lib/version.sh"
        . "{REPO_ROOT}/lib/internet_i18n.sh"
        . "{REPO_ROOT}/lib/vendor_feeds.sh"
        . "{REPO_ROOT}/lib/vendor_direct.sh"
        . "{REPO_ROOT}/lib/internet_handlers.sh"

        print_info() {{ :; }}
        print_warn() {{ :; }}
        print_step() {{ :; }}
        silent_launch_app() {{ echo "$@" >> "{open_log}"; return 0; }}
        internet_app_bundle_id() {{ echo "com.anthropic.claude"; }}
        internet_app_is_running() {{ return 0; }}
        internet_app_quit_gracefully() {{ echo "$@" >> "{quit_log}"; return 0; }}
        app_version() {{ echo "2.0.0"; }}
        vendor_feed_lookup() {{ echo "2.1.0|https://downloads.claude.ai/app.zip|-|-|zip|downloads.claude.ai"; }}

        internet_handler_vendor_truth "Claude" "/Applications/Claude.app" "Claude"
        echo "STATUS=$INTERNET_LAST_STATUS"
        echo "VERIFIED=$INTERNET_LAST_VERIFIED"
        """
        proc = self._run_bash(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("quit the app so its updater can install it", proc.stdout)
        self.assertIn("VERIFIED=1", proc.stdout)
        self.assertFalse(os.path.exists(open_log), "silent_launch_app was called on running app")
        self.assertFalse(os.path.exists(quit_log), "internet_app_quit_gracefully was called without user consent")

    def test_vendor_truth_behind_without_actions_reports_behind(self):
        script = f"""
        . "{REPO_ROOT}/i18n/lang_en.sh"
        . "{REPO_ROOT}/lib/version.sh"
        . "{REPO_ROOT}/lib/internet_i18n.sh"
        . "{REPO_ROOT}/lib/vendor_feeds.sh"
        . "{REPO_ROOT}/lib/vendor_direct.sh"
        . "{REPO_ROOT}/lib/internet_handlers.sh"

        print_info() {{ :; }}
        print_warn() {{ :; }}
        print_step() {{ :; }}
        internet_app_bundle_id() {{ echo "com.anthropic.claude"; }}
        internet_app_is_running() {{ return 1; }}
        app_version() {{ echo "2.0.0"; }}
        vendor_feed_lookup() {{ echo "2.1.0|https://downloads.claude.ai/app.zip|-|-|zip|downloads.claude.ai"; }}

        export MAC_UPDATE_STAGE_WAIT=0
        export MAC_UPDATE_VENDOR_DIRECT=0

        internet_handler_vendor_truth "Claude" "/Applications/Claude.app" "Claude"
        echo "STATUS=$INTERNET_LAST_STATUS"
        echo "VERIFIED=$INTERNET_LAST_VERIFIED"
        """
        proc = self._run_bash(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("behind", proc.stdout.lower())
        self.assertIn("2.0.0 < 2.1.0", proc.stdout)
        self.assertIn("VERIFIED=1", proc.stdout)

    def test_vendor_truth_stale_feed(self):
        script = f"""
        . "{REPO_ROOT}/i18n/lang_en.sh"
        . "{REPO_ROOT}/lib/version.sh"
        . "{REPO_ROOT}/lib/internet_i18n.sh"
        . "{REPO_ROOT}/lib/vendor_feeds.sh"
        . "{REPO_ROOT}/lib/vendor_direct.sh"
        . "{REPO_ROOT}/lib/internet_handlers.sh"

        print_info() {{ :; }}
        print_warn() {{ :; }}
        print_step() {{ :; }}
        internet_app_bundle_id() {{ echo "com.anthropic.claude"; }}
        internet_app_is_running() {{ return 1; }}
        app_version() {{ echo "2.0.0"; }}
        vendor_feed_lookup() {{ echo "1.9.0|https://downloads.claude.ai/app.zip|-|-|zip|downloads.claude.ai"; }}

        internet_handler_vendor_truth "Claude" "/Applications/Claude.app" "Claude"
        echo "STATUS=$INTERNET_LAST_STATUS"
        echo "VERIFIED=$INTERNET_LAST_VERIFIED"
        """
        proc = self._run_bash(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("stale", proc.stdout.lower())
        self.assertIn("1.9.0", proc.stdout)
        self.assertIn("2.0.0", proc.stdout)
        self.assertIn("VERIFIED=0", proc.stdout)

    def test_vendor_truth_feed_unreachable_falls_back(self):
        script = f"""
        . "{REPO_ROOT}/i18n/lang_en.sh"
        . "{REPO_ROOT}/lib/version.sh"
        . "{REPO_ROOT}/lib/internet_i18n.sh"
        . "{REPO_ROOT}/lib/vendor_feeds.sh"
        . "{REPO_ROOT}/lib/vendor_direct.sh"
        . "{REPO_ROOT}/lib/internet_handlers.sh"

        print_info() {{ :; }}
        print_warn() {{ :; }}
        print_step() {{ :; }}
        silent_launch_app() {{ return 0; }}
        app_version() {{ echo "2.0.0"; }}
        vendor_feed_lookup() {{ return 22; }}

        internet_handler_vendor_truth "Claude" "/Applications/Claude.app" "Claude"
        echo "STATUS=$INTERNET_LAST_STATUS"
        echo "VERIFIED=$INTERNET_LAST_VERIFIED"
        """
        proc = self._run_bash(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("unverified", proc.stdout.lower())
        self.assertIn("VERIFIED=0", proc.stdout)

    def test_vendor_truth_dry_run_reports_update_available_without_launch(self):
        open_log = os.path.join(self.tmpdir, "open.log")
        script = f"""
        . "{REPO_ROOT}/i18n/lang_en.sh"
        . "{REPO_ROOT}/lib/version.sh"
        . "{REPO_ROOT}/lib/internet_i18n.sh"
        . "{REPO_ROOT}/lib/vendor_feeds.sh"
        . "{REPO_ROOT}/lib/vendor_direct.sh"
        . "{REPO_ROOT}/lib/internet_handlers.sh"

        print_info() {{ :; }}
        print_warn() {{ :; }}
        print_step() {{ :; }}
        silent_launch_app() {{ echo "$@" >> "{open_log}"; return 0; }}
        app_version() {{ echo "2.0.0"; }}
        vendor_feed_lookup() {{ echo "2.1.0|https://downloads.claude.ai/app.zip|-|-|zip|downloads.claude.ai"; }}

        export MAC_UPDATE_DRY_RUN=1

        internet_handler_vendor_truth "Claude" "/Applications/Claude.app" "Claude"
        echo "STATUS=$INTERNET_LAST_STATUS"
        echo "VERIFIED=$INTERNET_LAST_VERIFIED"
        """
        proc = self._run_bash(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Update available", proc.stdout)
        self.assertIn("2.0.0", proc.stdout)
        self.assertIn("2.1.0", proc.stdout)
        self.assertIn("VERIFIED=1", proc.stdout)
        self.assertFalse(os.path.exists(open_log), "silent_launch_app called in dry run")

    def test_vendor_direct_rejects_older_bundle_version(self):
        copy_log = os.path.join(self.tmpdir, "copy.log")
        zip_path = os.path.join(self.tmpdir, "dummy.zip")
        # Create a mock zip with Dummy.app
        app_in_zip = os.path.join(self.tmpdir, "extract_src", "Dummy.app")
        os.makedirs(app_in_zip, exist_ok=True)
        subprocess.run(["ditto", "-c", "-k", os.path.join(self.tmpdir, "extract_src"), zip_path], check=True)

        script = f"""
        . "{REPO_ROOT}/i18n/lang_en.sh"
        . "{REPO_ROOT}/lib/version.sh"
        . "{REPO_ROOT}/lib/internet_i18n.sh"
        . "{REPO_ROOT}/lib/vendor_direct.sh"

        print_info() {{ :; }}
        print_warn() {{ :; }}
        fetch_to_file() {{ cp "{zip_path}" "$2"; }}
        vendor_direct_verify_checksum() {{ return 0; }}
        internet_app_bundle_id() {{ echo "com.example.dummy"; }}
        internet_app_is_running() {{ return 1; }}
        app_version() {{
            case "$1" in
                */Dummy.app)
                    if [[ "$1" == *"/Applications/"* ]]; then
                        echo "1.5"
                    else
                        echo "1.0"
                    fi
                    ;;
                *) echo "1.0" ;;
            esac
        }}
        copy_verified_app() {{ echo "$@" >> "{copy_log}"; return 0; }}

        vendor_direct_install "/Applications/Dummy.app" "https://example.com/dummy.zip" "zip" "-" "-" "example.com" "2.0"
        echo "RC=$?"
        """
        proc = self._run_bash(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("RC=1", proc.stdout)
        self.assertFalse(os.path.exists(copy_log), "copy_verified_app should not be called when version is older")

    def test_vendor_direct_diag_is_logged(self):
        diag_log = os.path.join(self.tmpdir, "diag.log")
        script = f"""
        . "{REPO_ROOT}/i18n/lang_en.sh"
        . "{REPO_ROOT}/lib/vendor_direct.sh"

        print_info() {{ :; }}
        print_warn() {{ :; }}
        internet_diag_log() {{ echo "$@" >> "{diag_log}"; }}

        vendor_direct_install "/Applications/Dummy.app" "https://bad.com/d.zip" "zip" "-" "-" "good.com" "2.0"
        echo "RC=$?"
        """
        proc = self._run_bash(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("RC=1", proc.stdout)
        self.assertTrue(os.path.exists(diag_log), "diag log was not created")
        content = Path(diag_log).read_text(encoding="utf-8")
        self.assertIn("not allowed", content)

    def test_fetch_refuses_http_redirect(self):
        curl_log = os.path.join(self.tmpdir, "curl_args.log")
        dest = os.path.join(self.tmpdir, "out.bin")
        script = f"""
        . "{REPO_ROOT}/lib/fetch.sh"
        curl() {{
            echo "$@" > "{curl_log}"
            local out=""
            while [ $# -gt 0 ]; do
                if [ "$1" = "-o" ]; then
                    out="$2"
                    shift 2
                else
                    shift
                fi
            done
            if [ -n "$out" ]; then
                echo "downloaded" > "$out"
            fi
            return 0
        }}
        fetch_to_file "https://example.com/file" "{dest}" 60 1000
        """
        proc = self._run_bash(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(os.path.exists(curl_log), "curl was not called")
        content = Path(curl_log).read_text(encoding="utf-8")
        self.assertIn("--proto-redir =https", content)
        self.assertIn("--max-filesize 1000", content)

    def test_launch_cycle_message_shows_remote_version(self):
        script = f"""
        . "{REPO_ROOT}/i18n/lang_en.sh"
        . "{REPO_ROOT}/lib/version.sh"
        . "{REPO_ROOT}/lib/internet_i18n.sh"
        . "{REPO_ROOT}/lib/vendor_feeds.sh"
        . "{REPO_ROOT}/lib/vendor_direct.sh"
        . "{REPO_ROOT}/lib/internet_handlers.sh"

        print_info() {{ :; }}
        print_warn() {{ :; }}
        print_step() {{ :; }}
        silent_launch_app() {{ :; }}
        sleep() {{ :; }}
        internet_app_bundle_id() {{ echo "com.anthropic.test"; }}
        internet_app_is_running() {{ return 1; }}
        app_version() {{ echo "2.0.0"; }}
        vendor_feed_lookup() {{ echo "2.1.0|https://downloads.claude.ai/app.zip|-|-|zip|downloads.claude.ai"; }}
        export MAC_UPDATE_STAGE_WAIT=90

        internet_handler_vendor_truth "Claude" "/Applications/Claude.app" "Claude"
        """
        proc = self._run_bash(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # Format string expects %s %s -> Claude 2.1.0 (not 90)
        self.assertIn("2.1.0", proc.stdout)
        self.assertNotIn("90", proc.stdout)

    def test_toolkit_launched_tracking_and_graceful_quit(self):
        bin_dir = os.path.join(self.tmpdir, "bin")
        os.makedirs(bin_dir, exist_ok=True)
        state_dir = os.path.join(self.tmpdir, "running_state")
        os.makedirs(state_dir, exist_ok=True)
        session_dir = os.path.join(self.tmpdir, "session")
        os.makedirs(session_dir, exist_ok=True)
        quit_log = os.path.join(self.tmpdir, "quit.log")
        open_log = os.path.join(self.tmpdir, "open.log")

        # Stub osascript
        osascript_stub = os.path.join(bin_dir, "osascript")
        with open(osascript_stub, "w", encoding="utf-8") as f:
            f.write(f"""#!/usr/bin/env bash
cmd="$*"
if echo "$cmd" | grep -q "is running"; then
    bid=$(echo "$cmd" | sed -n 's/.*application id \\"\\([^\\"]*\\)\\".*/\\1/p')
    if [ -f "{state_dir}/$bid.running" ]; then
        echo "true"
    else
        echo "false"
    fi
    exit 0
fi
if echo "$cmd" | grep -q "to quit"; then
    bid=$(echo "$cmd" | sed -n 's/.*tell application id \\"\\([^\\"]*\\)\\".*/\\1/p')
    echo "quit $bid" >> "{quit_log}"
    if [ -f "{state_dir}/$bid.fail_quit" ]; then
        exit 0
    fi
    rm -f "{state_dir}/$bid.running"
    exit 0
fi
exit 0
""")
        os.chmod(osascript_stub, 0o755)

        # Stub open
        open_stub = os.path.join(bin_dir, "open")
        with open(open_stub, "w", encoding="utf-8") as f:
            f.write(f"""#!/usr/bin/env bash
echo "$@" >> "{open_log}"
for arg in "$@"; do
    case "$arg" in
        AppA|*AppA.app) touch "{state_dir}/com.test.appA.running" ;;
        AppB|*AppB.app) touch "{state_dir}/com.test.appB.running" ;;
        AppC|*AppC.app) touch "{state_dir}/com.test.appC.running" ;;
    esac
done
exit 0
""")
        os.chmod(open_stub, 0o755)

        # Pre-seed state:
        # App A is NOT running
        # App B IS running
        Path(os.path.join(state_dir, "com.test.appB.running")).touch()
        # App C is NOT running, but will fail to quit once launched
        Path(os.path.join(state_dir, "com.test.appC.fail_quit")).touch()

        script = f"""
        export PATH="{bin_dir}:$PATH"
        export MAC_UPDATE_SESSION_DIR="{session_dir}"

        . "{REPO_ROOT}/i18n/lang_en.sh"
        . "{REPO_ROOT}/lib/ui.sh" 2>/dev/null || true
        . "{REPO_ROOT}/lib/proc.sh"
        . "{REPO_ROOT}/lib/vendor_direct.sh"

        print_info() {{ :; }}
        print_warn() {{ echo "WARN: $*"; }}
        print_error() {{ echo "ERROR: $*"; }}
        print_ok() {{ :; }}
        sleep() {{ :; }}

        internet_app_path() {{
            echo "/Applications/$1.app"
        }}
        internet_app_bundle_id() {{
            case "$1" in
                *AppA*) echo "com.test.appA" ;;
                *AppB*) echo "com.test.appB" ;;
                *AppC*) echo "com.test.appC" ;;
                *) echo "" ;;
            esac
        }}

        INTERNET_SOFT_FAIL=0

        # Load silent_launch_app and quit_toolkit_launched_apps from update_internet_apps.sh
        eval "$(sed -n '/^silent_launch_app()/,/^}}/p' "{REPO_ROOT}/update_internet_apps.sh")"
        eval "$(sed -n '/^quit_toolkit_launched_apps()/,/^}}/p' "{REPO_ROOT}/update_internet_apps.sh")"

        # App A was NOT running prior to launch -> should record into toolkit_launched.txt
        silent_launch_app "AppA"

        # Duplicate launch of App A -> should not duplicate in toolkit_launched.txt
        silent_launch_app "AppA" "com.test.appA"

        # App B WAS running prior to launch -> should NOT record into toolkit_launched.txt
        silent_launch_app "AppB" "com.test.appB"

        # App C was NOT running prior to launch -> should record into toolkit_launched.txt, will fail quit
        silent_launch_app "/Applications/AppC.app" "com.test.appC"

        # Settle cleanup
        quit_toolkit_launched_apps

        echo "SOFT_FAIL=$INTERNET_SOFT_FAIL"
        """
        proc = self._run_bash(script)
        self.assertEqual(proc.returncode, 0, f"Script failed with stderr:\n{proc.stderr}\nstdout:\n{proc.stdout}")

        # Check toolkit_launched.txt
        launched_file = os.path.join(session_dir, "toolkit_launched.txt")
        self.assertTrue(os.path.exists(launched_file), "toolkit_launched.txt was not created")
        launched_content = Path(launched_file).read_text(encoding="utf-8").splitlines()
        self.assertIn("com.test.appA", launched_content)
        self.assertNotIn("com.test.appB", launched_content)
        self.assertIn("com.test.appC", launched_content)
        self.assertEqual(launched_content.count("com.test.appA"), 1, "App A should be recorded exactly once")

        # Check quit log
        self.assertTrue(os.path.exists(quit_log), "quit.log was not created")
        quit_content = Path(quit_log).read_text(encoding="utf-8")
        self.assertIn("quit com.test.appA", quit_content)
        self.assertNotIn("quit com.test.appB", quit_content)
        self.assertIn("quit com.test.appC", quit_content)

        # App A should no longer be running
        self.assertFalse(os.path.exists(os.path.join(state_dir, "com.test.appA.running")), "App A should have exited")

        # App C failed to exit within 60s -> warning with L_INTERNET_APP_STILL_RUNNING_FMT
        self.assertIn("com.test.appC was launched for update and did not exit within 60s", proc.stdout)
        self.assertIn("SOFT_FAIL=1", proc.stdout)

    def test_opencode_vendor_feed_equal_does_not_launch(self):
        open_log = os.path.join(self.tmpdir, "open.log")
        fake_app = os.path.join(self.tmpdir, "OpenCode.app")
        os.makedirs(fake_app, exist_ok=True)
        script = f"""
        . "{REPO_ROOT}/i18n/lang_en.sh"
        . "{REPO_ROOT}/lib/version.sh"
        . "{REPO_ROOT}/lib/internet_i18n.sh"
        . "{REPO_ROOT}/lib/vendor_feeds.sh"
        . "{REPO_ROOT}/lib/vendor_direct.sh"
        . "{REPO_ROOT}/lib/internet_handlers.sh"
        . "{REPO_ROOT}/lib/internet_apps.sh"
        . "{REPO_ROOT}/lib/internet_app_updates.sh"

        print_header() {{ :; }}
        print_info() {{ :; }}
        print_warn() {{ :; }}
        print_step() {{ :; }}
        print_ok() {{ :; }}
        internet_msg() {{ printf "%s %s %s" "$@"; }}
        silent_launch_app() {{ echo "$@" >> "{open_log}"; return 0; }}
        app_version() {{ echo "1.18.32"; }}
        internet_app_path() {{ echo "{fake_app}"; }}
        vendor_feed_lookup() {{ echo "1.18.32|https://example.com/opencode.tar.gz|-|-|tar.gz|example.com"; }}

        STATUS_OPENCODE=""
        iu_opencode_desktop
        echo "STATUS_OPENCODE=$STATUS_OPENCODE"
        """
        proc = self._run_bash(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("STATUS_OPENCODE=", proc.stdout)
        self.assertIn("1.18.32", proc.stdout)
        self.assertIn("vendor feed", proc.stdout.lower())
        self.assertFalse(os.path.exists(open_log), "silent_launch_app was called for OpenCode when feed is equal")

    def test_teams_cask_oracle_equal_does_not_launch(self):
        open_log = os.path.join(self.tmpdir, "open.log")
        fake_app = os.path.join(self.tmpdir, "Microsoft Teams.app")
        os.makedirs(fake_app, exist_ok=True)
        script = f"""
        . "{REPO_ROOT}/i18n/lang_en.sh"
        . "{REPO_ROOT}/lib/version.sh"
        . "{REPO_ROOT}/lib/internet_i18n.sh"
        . "{REPO_ROOT}/lib/brew.sh"
        . "{REPO_ROOT}/lib/internet_handlers.sh"
        . "{REPO_ROOT}/lib/internet_apps.sh"
        . "{REPO_ROOT}/lib/internet_app_updates.sh"

        print_header() {{ :; }}
        print_info() {{ :; }}
        print_warn() {{ :; }}
        print_step() {{ :; }}
        print_ok() {{ :; }}
        internet_msg() {{ printf "%s %s %s" "$@"; }}
        silent_launch_app() {{ echo "$@" >> "{open_log}"; return 0; }}
        app_version() {{ echo "24.100.0"; }}
        internet_app_path() {{ echo "{fake_app}"; }}
        brew_cask_latest_versions() {{ printf "microsoft-teams\t24.100.0\n"; }}

        STATUS_TEAMS=""
        iu_microsoft_teams
        echo "STATUS_TEAMS=$STATUS_TEAMS"
        """
        proc = self._run_bash(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("STATUS_TEAMS=", proc.stdout)
        self.assertIn("cask", proc.stdout.lower())
        self.assertFalse(os.path.exists(open_log), "silent_launch_app was called for Teams when cask oracle is equal")

    def test_teams_cask_oracle_newer_launches_app(self):
        open_log = os.path.join(self.tmpdir, "open.log")
        fake_app = os.path.join(self.tmpdir, "Microsoft Teams.app")
        os.makedirs(fake_app, exist_ok=True)
        script = f"""
        . "{REPO_ROOT}/i18n/lang_en.sh"
        . "{REPO_ROOT}/lib/version.sh"
        . "{REPO_ROOT}/lib/internet_i18n.sh"
        . "{REPO_ROOT}/lib/brew.sh"
        . "{REPO_ROOT}/lib/internet_handlers.sh"
        . "{REPO_ROOT}/lib/internet_apps.sh"
        . "{REPO_ROOT}/lib/internet_app_updates.sh"

        print_header() {{ :; }}
        print_info() {{ :; }}
        print_warn() {{ :; }}
        print_step() {{ :; }}
        print_ok() {{ :; }}
        internet_msg() {{ printf "%s %s %s" "$@"; }}
        silent_launch_app() {{ echo "$@" >> "{open_log}"; return 0; }}
        app_version() {{ echo "24.100.0"; }}
        internet_app_path() {{ echo "{fake_app}"; }}
        brew_cask_latest_versions() {{ printf "microsoft-teams\t24.200.0\n"; }}

        STATUS_TEAMS=""
        iu_microsoft_teams
        echo "STATUS_TEAMS=$STATUS_TEAMS"
        """
        proc = self._run_bash(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(os.path.exists(open_log), "silent_launch_app was NOT called when Teams is behind")
        self.assertIn("unverified", proc.stdout.lower())

    def test_teams_mau_verified_does_not_launch(self):
        open_log = os.path.join(self.tmpdir, "open.log")
        fake_app = os.path.join(self.tmpdir, "Microsoft Teams.app")
        os.makedirs(fake_app, exist_ok=True)
        script = f"""
        . "{REPO_ROOT}/i18n/lang_en.sh"
        . "{REPO_ROOT}/lib/version.sh"
        . "{REPO_ROOT}/lib/internet_i18n.sh"
        . "{REPO_ROOT}/lib/brew.sh"
        . "{REPO_ROOT}/lib/internet_handlers.sh"
        . "{REPO_ROOT}/lib/internet_apps.sh"
        . "{REPO_ROOT}/lib/internet_app_updates.sh"

        print_header() {{ :; }}
        print_info() {{ :; }}
        print_warn() {{ :; }}
        print_step() {{ :; }}
        print_ok() {{ :; }}
        internet_msg() {{ printf "%s %s %s" "$@"; }}
        silent_launch_app() {{ echo "$@" >> "{open_log}"; return 0; }}
        app_version() {{ echo "24.100.0"; }}
        internet_app_path() {{ echo "{fake_app}"; }}
        # Cask oracle returns nothing (e.g. offline)
        brew_cask_latest_versions() {{ return 1; }}

        # MAU listed updates, TEAMS21 was not offered, and MAU status is current
        MAU_LISTED=1
        MAU_TEAMS21_OFFERED=0
        STATUS_MICROSOFT="$L_INTERNET_STATUS_CURRENT"

        STATUS_TEAMS=""
        iu_microsoft_teams
        echo "STATUS_TEAMS=$STATUS_TEAMS"
        """
        proc = self._run_bash(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(os.path.exists(open_log), "silent_launch_app was called for Teams when MAU verified current")
    def test_cursor_vendor_direct_first_skips_launch(self):
        """When Cursor is in vendor_direct_first.txt, app is not running, and feed is newer,
        silent_launch_app is skipped and vendor_direct_install is invoked directly."""
        open_log = os.path.join(self.tmpdir, "open.log")
        vdi_log = os.path.join(self.tmpdir, "vdi.log")
        fake_app = os.path.join(self.tmpdir, "Cursor.app")
        os.makedirs(fake_app, exist_ok=True)
        script = f"""
        . "{REPO_ROOT}/i18n/lang_en.sh"
        . "{REPO_ROOT}/lib/version.sh"
        . "{REPO_ROOT}/lib/internet_i18n.sh"
        . "{REPO_ROOT}/lib/internet_handlers.sh"

        print_info() {{ :; }}
        print_warn() {{ :; }}
        print_step() {{ :; }}
        print_ok() {{ :; }}
        internet_msg() {{ printf "%s %s %s" "$@"; }}
        silent_launch_app() {{ echo "$@" >> "{open_log}"; return 0; }}
        internet_app_bundle_id() {{ echo "com.todesktop.230313mzl4w4u92"; }}
        internet_app_is_running() {{ return 1; }}  # not running
        app_version() {{
            if [ -f "{vdi_log}" ]; then
                echo "3.22.7"
            else
                echo "3.21.18"
            fi
        }}
        vendor_direct_install() {{
            echo "VDI: $@" >> "{vdi_log}"
            return 0
        }}
        vendor_feed_lookup() {{
            echo "3.22.7|https://downloads.cursor.com/mac/universal/3.22.7|-|-|zip|downloads.cursor.com"
        }}

        internet_handler_vendor_truth "Cursor" "{fake_app}" "{fake_app}"
        echo "STATUS=$INTERNET_LAST_STATUS"
        echo "VERIFIED=$INTERNET_LAST_VERIFIED"
        """
        proc = self._run_bash(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(os.path.exists(open_log), "silent_launch_app was called for Cursor despite vendor_direct_first")
        self.assertTrue(os.path.exists(vdi_log), "vendor_direct_install was NOT called for Cursor")
        self.assertIn("3.22.7", proc.stdout)

    def test_cursor_vendor_direct_first_running_app_returns_needs_restart(self):
        """When Cursor is in vendor_direct_first.txt but is running, it returns needs restart without launching or installing."""
        open_log = os.path.join(self.tmpdir, "open.log")
        vdi_log = os.path.join(self.tmpdir, "vdi.log")
        fake_app = os.path.join(self.tmpdir, "Cursor.app")
        os.makedirs(fake_app, exist_ok=True)
        script = f"""
        . "{REPO_ROOT}/i18n/lang_en.sh"
        . "{REPO_ROOT}/lib/version.sh"
        . "{REPO_ROOT}/lib/internet_i18n.sh"
        . "{REPO_ROOT}/lib/internet_handlers.sh"

        print_info() {{ :; }}
        print_warn() {{ :; }}
        print_step() {{ :; }}
        print_ok() {{ :; }}
        internet_msg() {{ printf "%s %s %s" "$@"; }}
        silent_launch_app() {{ echo "$@" >> "{open_log}"; return 0; }}
        internet_app_bundle_id() {{ echo "com.todesktop.230313mzl4w4u92"; }}
        internet_app_is_running() {{ return 0; }}  # IS running
        app_version() {{ echo "3.21.18"; }}
        vendor_direct_install() {{ echo "VDI: $@" >> "{vdi_log}"; return 0; }}
        vendor_feed_lookup() {{
            echo "3.22.7|https://downloads.cursor.com/mac/universal/3.22.7|-|-|zip|downloads.cursor.com"
        }}

        internet_handler_vendor_truth "Cursor" "{fake_app}" "{fake_app}"
        echo "STATUS=$INTERNET_LAST_STATUS"
        echo "VERIFIED=$INTERNET_LAST_VERIFIED"
        """
        proc = self._run_bash(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(os.path.exists(open_log))
        self.assertFalse(os.path.exists(vdi_log))
        self.assertIn("quit the app", proc.stdout.lower())


if __name__ == "__main__":
    unittest.main()

