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

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@unittest.skipUnless(shutil.which("bash"), "bash required")
class TestVendorTruthHandlers(unittest.TestCase):

    def setUp(self):
        self.fixtures_dir = os.path.join(REPO_ROOT, "tests", "fixtures", "vendor_feeds")
        self.tmpdir = tempfile.mkdtemp(prefix="mac_update_vth_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run_bash(self, script: str, extra_env: dict = None) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["SCRIPT_DIR"] = REPO_ROOT
        env["PYTHONPATH"] = os.path.join(REPO_ROOT, "lib", "python")
        if extra_env:
            env.update(extra_env)
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


if __name__ == "__main__":
    unittest.main()
