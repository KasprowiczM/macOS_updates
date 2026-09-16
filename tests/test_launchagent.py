"""Tests for scripts/install_launchagent.sh modern launchctl and quarantine handling (P1-9)."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "install_launchagent.sh"


class LaunchAgentInstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        self.fake_bin = self.tmp_path / "bin"
        self.fake_bin.mkdir()
        self.fake_home = self.tmp_path / "home"
        self.fake_home.mkdir()

        self.launchctl_log = self.tmp_path / "launchctl_calls.log"
        self.xattr_log = self.tmp_path / "xattr_calls.log"

        # Create mock launchctl
        mock_launchctl = self.fake_bin / "launchctl"
        mock_launchctl.write_text(
            f"""#!/bin/sh
echo "$@" >> "{self.launchctl_log}"
if [ "$1" = "bootstrap" ] && [ -f "{self.tmp_path}/fail_bootstrap" ]; then
    exit 1
fi
if [ "$1" = "list" ] || [ "$1" = "print" ]; then
    if [ -f "{self.tmp_path}/active_service" ]; then
        exit 0
    fi
    exit 1
fi
exit 0
""",
            encoding="utf-8",
        )
        mock_launchctl.chmod(0o755)

        # Create mock xattr
        mock_xattr = self.fake_bin / "xattr"
        mock_xattr.write_text(
            f"""#!/bin/sh
echo "$@" >> "{self.xattr_log}"
exit 0
""",
            encoding="utf-8",
        )
        mock_xattr.chmod(0o755)

        self.env = dict(os.environ)
        self.env["PATH"] = f"{self.fake_bin}:{self.env.get('PATH', '/usr/bin:/bin')}"
        self.env["HOME"] = str(self.fake_home)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_install_uses_quarantine_removal_and_bootstrap(self) -> None:
        cmd = ["/bin/bash", str(SCRIPT_PATH), "--day", "3", "--hour", "10"]
        result = subprocess.run(cmd, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")

        # Verify xattr removed com.apple.quarantine
        self.assertTrue(self.xattr_log.exists())
        xattr_calls = self.xattr_log.read_text(encoding="utf-8")
        self.assertIn("-d com.apple.quarantine", xattr_calls)

        # Verify launchctl bootstrap and enable were called
        self.assertTrue(self.launchctl_log.exists())
        launchctl_calls = self.launchctl_log.read_text(encoding="utf-8")
        self.assertIn("bootstrap gui/", launchctl_calls)
        self.assertIn("enable gui/", launchctl_calls)

        # Verify plist content
        user_name = subprocess.run(["id", "-un"], capture_output=True, text=True).stdout.strip()
        plist_path = self.fake_home / "Library" / "LaunchAgents" / f"com.{user_name}.macos-updates.plist"
        self.assertTrue(plist_path.exists())
        content = plist_path.read_text(encoding="utf-8")
        self.assertIn("<integer>3</integer>", content)
        self.assertIn("<integer>10</integer>", content)
        self.assertIn("<string>--skip-system</string>", content)

    def test_install_bootstrap_fallback_to_load(self) -> None:
        # Trigger bootstrap failure
        (self.tmp_path / "fail_bootstrap").touch()

        cmd = ["/bin/bash", str(SCRIPT_PATH), "--day", "1", "--hour", "9"]
        result = subprocess.run(cmd, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")

        launchctl_calls = self.launchctl_log.read_text(encoding="utf-8")
        self.assertIn("bootstrap gui/", launchctl_calls)
        self.assertIn("load -w", launchctl_calls)

    def test_uninstall_uses_bootout(self) -> None:
        # First install
        subprocess.run(["/bin/bash", str(SCRIPT_PATH)], env=self.env, capture_output=True)

        user_name = subprocess.run(["id", "-un"], capture_output=True, text=True).stdout.strip()
        plist_path = self.fake_home / "Library" / "LaunchAgents" / f"com.{user_name}.macos-updates.plist"
        self.assertTrue(plist_path.exists())

        # Now uninstall
        cmd = ["/bin/bash", str(SCRIPT_PATH), "--uninstall"]
        result = subprocess.run(cmd, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(plist_path.exists())

        launchctl_calls = self.launchctl_log.read_text(encoding="utf-8")
        self.assertIn("bootout gui/", launchctl_calls)


if __name__ == "__main__":
    unittest.main()
