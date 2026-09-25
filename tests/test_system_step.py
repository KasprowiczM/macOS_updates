#!/usr/bin/env python3
"""tests/test_system_step.py — Tests for macOS system update step (P0-3)."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

SAMPLE_LISTING = """Software Update Tool

Finding available software
Software Update found the following new or updated software:
* Label: Safari27.0TahoeAuto-27.0
\tTitle: Safari, Version: 27.0, Size: 249465KiB, Recommended: YES,\x20
* Label: macOS Tahoe 26.7-25G229
\tTitle: macOS Tahoe 26.7, Version: 26.7, Size: 2960352KiB, Recommended: YES, Action: restart,\x20
* Label: macOS 27-26A428
\tTitle: macOS 27, Version: 27, Size: 11727573KiB, Recommended: YES, Action: restart,\x20
"""


class SystemUpdatesModuleTests(unittest.TestCase):
    def test_parse_and_classify_softwareupdate_list(self) -> None:
        import sys
        sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))
        from system_updates import classify_updates, parse_softwareupdate_list

        items = parse_softwareupdate_list(SAMPLE_LISTING)
        self.assertEqual(len(items), 3)

        self.assertEqual(items[0]["label"], "Safari27.0TahoeAuto-27.0")
        self.assertEqual(items[0]["title"], "Safari")
        self.assertEqual(items[0]["version"], "27.0")
        self.assertEqual(items[0]["size_kib"], 249465)
        self.assertTrue(items[0]["recommended"])
        self.assertFalse(items[0]["restart"])

        self.assertEqual(items[1]["label"], "macOS Tahoe 26.7-25G229")
        self.assertEqual(items[1]["title"], "macOS Tahoe 26.7")
        self.assertEqual(items[1]["version"], "26.7")
        self.assertTrue(items[1]["recommended"])
        self.assertTrue(items[1]["restart"])

        self.assertEqual(items[2]["label"], "macOS 27-26A428")
        self.assertEqual(items[2]["title"], "macOS 27")
        self.assertEqual(items[2]["version"], "27")
        self.assertTrue(items[2]["recommended"])
        self.assertTrue(items[2]["restart"])

        classified = classify_updates(items, current_version="26.6.2")
        self.assertEqual([x["label"] for x in classified["other"]], ["Safari27.0TahoeAuto-27.0"])
        self.assertEqual([x["label"] for x in classified["same_major"]], ["macOS Tahoe 26.7-25G229"])
        self.assertEqual([x["label"] for x in classified["major"]], ["macOS 27-26A428"])


class SystemStepBehavioralTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.tmp_dir.name)
        self.bin_dir = self.work_dir / "bin"
        self.bin_dir.mkdir()
        self.session_dir = self.work_dir / "session"
        self.session_dir.mkdir()

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def create_mock_script(self, name: str, code: str) -> Path:
        p = self.bin_dir / name
        p.write_text(f"#!/bin/sh\n{code}\n", encoding="utf-8")
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return p

    def setup_mocks(self, log_file: Path) -> None:
        self.create_mock_script("uname", "echo arm64")
        self.create_mock_script(
            "sw_vers",
            """
            if [ "$1" = "-productVersion" ]; then
                echo "26.6.2"
                exit 0
            fi
            echo "ProductName: macOS"
            echo "ProductVersion: 26.6.2"
            echo "BuildVersion: 25F71"
            """,
        )
        self.create_mock_script(
            "sudo",
            f"""
            echo "sudo $@" >> "{log_file}"
            cmd="$1"
            shift
            exec "$cmd" "$@"
            """,
        )
        self.create_mock_script(
            "softwareupdate",
            f"""
            echo "softwareupdate $@" >> "{log_file}"
            if [ "$1" = "-l" ]; then
                cat << 'EOF'
{SAMPLE_LISTING}
EOF
                exit 0
            fi
            exit 0
            """,
        )

    def test_default_skips_major_and_installs_same_major_and_other(self) -> None:
        """Default: only same_major and other are installed, major is skipped; no -ia used."""
        log_file = self.work_dir / "calls.log"
        self.setup_mocks(log_file)

        env = dict(os.environ)
        env["PATH"] = f"{self.bin_dir}:{env['PATH']}"
        env["MAC_UPDATE_SESSION_DIR"] = str(self.session_dir)
        env["MAC_UPDATE_YES"] = "1"
        env.pop("MAC_UPDATE_ALLOW_MAJOR_UPGRADE", None)

        res = subprocess.run(
            ["bash", str(REPO_ROOT / "update_system.sh")],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Output:\n{res.stdout}\n{res.stderr}")

        calls = log_file.read_text()
        self.assertNotIn("-ia", calls)
        self.assertIn('softwareupdate -i Safari27.0TahoeAuto-27.0 -R --verbose', calls)
        self.assertIn('softwareupdate -i macOS Tahoe 26.7-25G229 -R --verbose', calls)
        self.assertNotIn('macOS 27-26A428', calls)

    def test_with_allow_major_and_yes_installs_major(self) -> None:
        """With MAC_UPDATE_ALLOW_MAJOR_UPGRADE=1 and confirmation, major is installed."""
        log_file = self.work_dir / "calls.log"
        self.setup_mocks(log_file)

        env = dict(os.environ)
        env["PATH"] = f"{self.bin_dir}:{env['PATH']}"
        env["MAC_UPDATE_SESSION_DIR"] = str(self.session_dir)
        env["MAC_UPDATE_YES"] = "1"
        env["MAC_UPDATE_ALLOW_MAJOR_UPGRADE"] = "1"

        res = subprocess.run(
            ["bash", str(REPO_ROOT / "update_system.sh")],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Output:\n{res.stdout}\n{res.stderr}")

        calls = log_file.read_text()
        self.assertIn('macOS 27-26A428', calls)

    def test_user_decline_exits_10_and_records_skipped_by_user(self) -> None:
        """Declining update exits 10, writes system_skipped_by_user and pending_system=3."""
        log_file = self.work_dir / "calls.log"
        self.setup_mocks(log_file)

        env = dict(os.environ)
        env["PATH"] = f"{self.bin_dir}:{env['PATH']}"
        env["MAC_UPDATE_SESSION_DIR"] = str(self.session_dir)
        env["MAC_UPDATE_YES"] = "0"

        # Pass 'n' as input
        res = subprocess.run(
            ["bash", str(REPO_ROOT / "update_system.sh")],
            input="n\n",
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 10, f"Output:\n{res.stdout}\n{res.stderr}")
        self.assertTrue((self.session_dir / "system_skipped_by_user").exists())
        self.assertEqual((self.session_dir / "pending_system").read_text().strip(), "3")

    def test_batch_restart_labels_two_invocations_restart_last(self) -> None:
        """Listing with one no-restart and two restart labels produces two invocations with both restarts last."""
        log_file = self.work_dir / "calls.log"
        self.setup_mocks(log_file)

        env = dict(os.environ)
        env["PATH"] = f"{self.bin_dir}:{env['PATH']}"
        env["MAC_UPDATE_SESSION_DIR"] = str(self.session_dir)
        env["MAC_UPDATE_YES"] = "1"
        env["MAC_UPDATE_ALLOW_MAJOR_UPGRADE"] = "1"

        res = subprocess.run(
            ["bash", str(REPO_ROOT / "update_system.sh")],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Output:\n{res.stdout}\n{res.stderr}")

        calls = [
            line.strip()
            for line in log_file.read_text().splitlines()
            if line.strip().startswith("softwareupdate -i")
        ]
        self.assertEqual(len(calls), 2, f"Expected 2 softwareupdate install calls, got: {calls}")
        # First call is no-restart
        self.assertIn("Safari27.0TahoeAuto-27.0", calls[0])
        self.assertNotIn("26.7", calls[0])
        self.assertNotIn("macOS 27", calls[0])
        # Second call is batch restart containing both restart labels
        self.assertIn("macOS Tahoe 26.7-25G229", calls[1])
        self.assertIn("macOS 27-26A428", calls[1])
        self.assertTrue(calls[1].endswith("-R --verbose"))


if __name__ == "__main__":
    unittest.main()
