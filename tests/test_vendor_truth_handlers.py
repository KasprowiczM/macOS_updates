#!/usr/bin/env python3
"""tests/test_vendor_truth_handlers.py — tests for vendor truth handlers."""

import os
import shutil
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

    def _run_bash(self, script: str) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["SCRIPT_DIR"] = REPO_ROOT
        env["PYTHONPATH"] = os.path.join(REPO_ROOT, "lib", "python")
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
        # Define stubs
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
        # Define stubs
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


if __name__ == "__main__":
    unittest.main()
