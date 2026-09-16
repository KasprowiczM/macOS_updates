#!/usr/bin/env python3
"""tests/test_xcode_license_gate.py — Tests for Xcode license gate (P0-1)."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class XcodeLicenseGateTests(unittest.TestCase):
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

    def test_brew_xcode_license_ok_in_lib_brew(self) -> None:
        """brew_xcode_license_ok returns 0 if CLT or license accepted, 1 if unaccepted Xcode."""
        # 1. CLT path -> returns 0
        cmd = f"""
        . "{REPO_ROOT}/lib/brew.sh"
        xcode-select() {{ echo "/Library/Developer/CommandLineTools"; }}
        brew_xcode_license_ok
        """
        res = subprocess.run(["bash", "-c", cmd], capture_output=True)
        self.assertEqual(res.returncode, 0)

        # 2. Xcode.app with license check 0 -> returns 0
        cmd = f"""
        . "{REPO_ROOT}/lib/brew.sh"
        xcode-select() {{ echo "/Applications/Xcode.app/Contents/Developer"; }}
        xcodebuild() {{
            if [ "$1" = "-license" ] && [ "$2" = "check" ]; then
                return 0
            fi
            return 1
        }}
        brew_xcode_license_ok
        """
        res = subprocess.run(["bash", "-c", cmd], capture_output=True)
        self.assertEqual(res.returncode, 0)

        # 3. Xcode.app with license check 69 -> returns 1
        cmd = f"""
        . "{REPO_ROOT}/lib/brew.sh"
        xcode-select() {{ echo "/Applications/Xcode.app/Contents/Developer"; }}
        xcodebuild() {{
            if [ "$1" = "-license" ] && [ "$2" = "check" ]; then
                return 69
            fi
            return 0
        }}
        brew_xcode_license_ok
        """
        res = subprocess.run(["bash", "-c", cmd], capture_output=True)
        self.assertEqual(res.returncode, 1)

    def test_update_brew_preflight_fails_soft_when_license_unaccepted(self) -> None:
        """When xcodebuild returns 69, update_brew.sh exits 10, writes unknown + reason, no brew update."""
        log_file = self.work_dir / "calls.log"

        # Atrapa xcode-select
        self.create_mock_script("xcode-select", 'echo "/Applications/Xcode.app/Contents/Developer"')

        # Atrapa xcodebuild -> 69
        self.create_mock_script(
            "xcodebuild",
            f"""
            echo "xcodebuild $@" >> "{log_file}"
            if [ "$1" = "-license" ] && [ "$2" = "check" ]; then
                exit 69
            fi
            exit 0
            """,
        )

        # Atrapa brew -> should not be called for update
        self.create_mock_script(
            "brew",
            f"""
            echo "brew $@" >> "{log_file}"
            if [ "$1" = "--version" ]; then
                echo "Homebrew 7.0.2"
                exit 0
            fi
            exit 0
            """,
        )

        env = dict(os.environ)
        env["PATH"] = f"{self.bin_dir}:{env['PATH']}"
        env["MAC_UPDATE_SESSION_DIR"] = str(self.session_dir)
        env["MAC_UPDATE_NONINTERACTIVE"] = "1"
        env["MAC_UPDATE_YES"] = "1"

        res = subprocess.run(
            ["bash", str(REPO_ROOT / "update_brew.sh")],
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertEqual(res.returncode, 10, f"Expected rc 10, got {res.returncode}. Output:\n{res.stdout}\n{res.stderr}")

        # Check pending files
        pbf = (self.session_dir / "pending_brew_formulae").read_text().strip()
        pbc = (self.session_dir / "pending_brew_casks").read_text().strip()
        reason = (self.session_dir / "pending_brew_reason").read_text().strip()
        self.assertEqual(pbf, "unknown")
        self.assertEqual(pbc, "unknown")
        self.assertEqual(reason, "xcode_license")

        # brew update must NOT have been called
        calls = log_file.read_text() if log_file.exists() else ""
        self.assertNotIn("brew update", calls)
        self.assertNotIn("xcodebuild -license accept", calls)

    def test_run_summary_details_with_xcode_license(self) -> None:
        """collect_run_items includes Xcode license not accepted details."""
        import sys
        sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))
        from run_summary import collect_run_items

        (self.session_dir / "pending_brew_formulae").write_text("unknown\n")
        (self.session_dir / "pending_brew_casks").write_text("unknown\n")
        (self.session_dir / "pending_brew_reason").write_text("xcode_license\n")
        (self.session_dir / "xcode_changed.txt").write_text("xcode_changed=16.2->27.0\n")

        step_results = {"brew": "Warn Homebrew skipped"}
        items = collect_run_items(self.session_dir, step_results=step_results)

        brew_items = [it for it in items if it.get("id") == "brew"]
        self.assertTrue(len(brew_items) > 0)
        self.assertIn("Xcode license not accepted (Xcode 16.2->27.0)", brew_items[0].get("details", ""))


if __name__ == "__main__":
    unittest.main()
