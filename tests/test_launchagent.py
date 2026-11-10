"""Tests for scripts/install_launchagent.sh modern launchctl and quarantine handling (P1-9)."""

from __future__ import annotations

import calendar
import os
import subprocess
import tempfile
import time
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
if [ "$1" = "bootout" ] && [ -f "{self.tmp_path}/fail_bootout" ]; then
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

        # By default the stubbed service reports as loaded once installed.
        (self.tmp_path / "active_service").touch()

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

    def _plist(self) -> Path:
        user_name = subprocess.run(["id", "-un"], capture_output=True, text=True).stdout.strip()
        return self.fake_home / "Library" / "LaunchAgents" / f"com.{user_name}.macos-updates.plist"

    def test_failed_load_exits_nonzero_without_success_line(self) -> None:
        (self.tmp_path / "active_service").unlink()
        (self.tmp_path / "fail_bootstrap").touch()
        result = subprocess.run(
            ["/bin/bash", str(SCRIPT_PATH)], env=self.env, capture_output=True, text=True
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Installed and loaded", result.stdout)
        self.assertIn("NOT loaded", result.stderr)

    def test_not_loaded_after_apparent_success_fails(self) -> None:
        # bootstrap "succeeds" but launchctl print says the service is absent
        (self.tmp_path / "active_service").unlink()
        result = subprocess.run(
            ["/bin/bash", str(SCRIPT_PATH)], env=self.env, capture_output=True, text=True
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Installed and loaded", result.stdout)

    def test_cleanup_never_uses_unload(self) -> None:
        subprocess.run(["/bin/bash", str(SCRIPT_PATH)], env=self.env, capture_output=True)
        calls = self.launchctl_log.read_text(encoding="utf-8")
        self.assertNotIn("unload", calls)

    def test_plist_has_homebrew_path(self) -> None:
        subprocess.run(["/bin/bash", str(SCRIPT_PATH)], env=self.env, capture_output=True)
        content = self._plist().read_text(encoding="utf-8")
        self.assertIn("<key>PATH</key>", content)
        self.assertIn(
            "<string>/opt/homebrew/bin:/opt/homebrew/sbin:/usr/bin:/bin:/usr/sbin:/sbin</string>",
            content,
        )

    def test_check_warns_when_plist_lacks_path(self) -> None:
        subprocess.run(["/bin/bash", str(SCRIPT_PATH)], env=self.env, capture_output=True)
        good = subprocess.run(
            ["/bin/bash", str(SCRIPT_PATH), "--check"], env=self.env, capture_output=True, text=True
        )
        self.assertEqual(good.returncode, 0)
        self.assertNotIn("no EnvironmentVariables.PATH", good.stdout)

        plist = self._plist()
        text = plist.read_text(encoding="utf-8")
        start = text.index("        <key>PATH</key>")
        end = text.index("        <key>MAC_UPDATE_NONINTERACTIVE</key>")
        plist.write_text(text[:start] + text[end:], encoding="utf-8")
        old = subprocess.run(
            ["/bin/bash", str(SCRIPT_PATH), "--check"], env=self.env, capture_output=True, text=True
        )
        self.assertEqual(old.returncode, 0)
        self.assertIn("no EnvironmentVariables.PATH", old.stdout)

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

    def test_uninstall_never_falls_back_to_unload(self) -> None:
        subprocess.run(["/bin/bash", str(SCRIPT_PATH)], env=self.env, capture_output=True)
        (self.tmp_path / "fail_bootout").touch()
        self.launchctl_log.write_text("", encoding="utf-8")
        result = subprocess.run(["/bin/bash", str(SCRIPT_PATH), "--uninstall"], env=self.env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self._plist().exists())
        calls = self.launchctl_log.read_text(encoding="utf-8").splitlines()
        # service-target bootout, then plist-path bootout; nothing else
        self.assertEqual(len([c for c in calls if c.startswith("bootout ")]), 2, calls)
        self.assertFalse([c for c in calls if "unload" in c], calls)


DATE_STUB = """#!/usr/bin/env python3
import sys, time
a = sys.argv[1:]
if a == ["+%s"]:
    print(int(time.time()))
elif len(a) == 3 and a[0] == "-r":
    print(time.strftime(a[2][1:], time.gmtime(int(a[1]))))
else:
    sys.exit(1)
"""


class LaunchAgentScheduleTests(LaunchAgentInstallerTests):
    """Schedule tests; `date` is stubbed so BSD `-r <epoch>` works on Linux CI."""

    def setUp(self) -> None:
        super().setUp()
        stub = self.fake_bin / "date"
        stub.write_text(DATE_STUB, encoding="utf-8")
        stub.chmod(0o755)

    def _run(self, *args: str, now: str = "") -> subprocess.CompletedProcess:
        env = dict(self.env)
        if now:
            env["MAC_UPDATE_LAUNCHAGENT_NOW_EPOCH"] = str(
                calendar.timegm(time.strptime(now, "%Y-%m-%d %H:%M"))
            )
        return subprocess.run(["/bin/bash", str(SCRIPT_PATH), *args], env=env,
                              capture_output=True, text=True)

    def _plist_text(self) -> str:
        return self._plist().read_text(encoding="utf-8")

    def test_minute_written_and_reported(self) -> None:
        r = self._run("--day", "2", "--hour", "7", "--minute", "5")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("<key>Minute</key>\n        <integer>5</integer>", self._plist_text())
        self.assertIn("Weekday 2 at 07:05", r.stdout)
        c = self._run("--check")
        self.assertIn("Weekday 2 at 07:05", c.stdout)

    def test_minute_default_zero_and_validation(self) -> None:
        self.assertEqual(self._run().returncode, 0)
        self.assertIn("<key>Minute</key>\n        <integer>0</integer>", self._plist_text())
        for bad in ("60", "-1", "x"):
            r = self._run("--minute", bad)
            self.assertEqual(r.returncode, 2, bad)
            self.assertIn("--minute", r.stderr)

    def test_once_in_writes_month_day_hour_minute(self) -> None:
        r = self._run("--once-in", "10", now="2026-11-10 14:55")
        self.assertEqual(r.returncode, 0, r.stderr)
        t = self._plist_text()
        self.assertNotIn("<key>Weekday</key>", t)
        for key, val in (("Month", 11), ("Day", 10), ("Hour", 15), ("Minute", 5)):
            self.assertIn(f"<key>{key}</key>\n        <integer>{val}</integer>", t)
        self.assertIn("11-10 at 15:05", r.stdout)

    def test_once_in_rolls_over_midnight_and_month_end(self) -> None:
        r = self._run("--once-in", "30", now="2026-11-30 23:50")
        self.assertEqual(r.returncode, 0, r.stderr)
        t = self._plist_text()
        for key, val in (("Month", 12), ("Day", 1), ("Hour", 0), ("Minute", 20)):
            self.assertIn(f"<key>{key}</key>\n        <integer>{val}</integer>", t)
        self.assertIn("12-01 at 00:20", r.stdout)
        r = self._run("--once-in", "1440", now="2026-12-31 12:00")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("01-01 at 12:00", r.stdout)

    def test_once_in_validation_and_exclusion(self) -> None:
        for bad in ("0", "1441", "abc"):
            self.assertEqual(self._run("--once-in", bad).returncode, 2, bad)
        for extra in (("--day", "1"), ("--hour", "9"), ("--minute", "0")):
            r = self._run("--once-in", "5", *extra)
            self.assertEqual(r.returncode, 2, extra)
            self.assertIn("cannot be combined", r.stderr)
        self.assertFalse(self.launchctl_log.exists())

    def test_check_reports_one_shot_date(self) -> None:
        self._run("--once-in", "10", now="2026-11-10 14:55")
        c = self._run("--check")
        self.assertEqual(c.returncode, 0)
        self.assertIn("one-shot on 11-10 at 15:05", c.stdout)
        self.assertNotIn("Weekday", c.stdout)

    def test_once_in_keeps_path_and_load_verification(self) -> None:
        (self.tmp_path / "active_service").unlink()
        r = self._run("--once-in", "5", now="2026-11-10 14:55")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("NOT loaded", r.stderr)
        self.assertIn("<key>PATH</key>", self._plist_text())


if __name__ == "__main__":
    unittest.main()
