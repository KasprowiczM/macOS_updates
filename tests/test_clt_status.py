#!/usr/bin/env python3
"""tests/test_clt_status.py — Tests for CLT status diagnosis and brew doctor collapse."""

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class CltStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="macupd_test_clt_")
        self.bin_dir = os.path.join(self.temp_dir, "bin")
        os.makedirs(self.bin_dir, exist_ok=True)
        self.old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{self.bin_dir}:{self.old_path}"

    def tearDown(self):
        os.environ["PATH"] = self.old_path
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_mock_bin(self, name: str, script_body: str) -> str:
        bin_path = os.path.join(self.bin_dir, name)
        with open(bin_path, "w", encoding="utf-8") as f:
            f.write(f"#!/bin/sh\n{script_body}\n")
        os.chmod(bin_path, os.stat(bin_path).st_mode | stat.S_IXUSR)
        return bin_path

    def _run_clt_status(self, clt_dir: str, env_override=None) -> str:
        env = dict(os.environ)
        env["MAC_UPDATE_CLT_DIR"] = clt_dir
        if env_override:
            env.update(env_override)
        cmd = f'. "{REPO_ROOT}/lib/platform.sh"; mac_update_clt_status'
        res = subprocess.run(
            ["bash", "-c", cmd],
            env=env,
            capture_output=True,
            text=True,
        )
        return res.stdout.strip()

    def test_clt_missing_when_dir_does_not_exist(self):
        non_existent = os.path.join(self.temp_dir, "non_existent_clt")
        status = self._run_clt_status(non_existent)
        self.assertEqual(status, "missing")

    def test_clt_orphan_when_dir_exists_but_no_receipt(self):
        clt_dir = os.path.join(self.temp_dir, "CommandLineTools")
        os.makedirs(clt_dir, exist_ok=True)
        self._create_mock_bin("pkgutil", 'echo "No receipt found" >&2; exit 1')
        status = self._run_clt_status(clt_dir)
        self.assertEqual(status, "orphan")

    def test_clt_stale_when_version_older_than_os(self):
        clt_dir = os.path.join(self.temp_dir, "CommandLineTools")
        os.makedirs(clt_dir, exist_ok=True)
        self._create_mock_bin("sw_vers", 'echo "27.0"')
        self._create_mock_bin(
            "pkgutil",
            'echo "package-id: com.apple.pkg.CLTools_Executables\nversion: 16.2.0.0.1.1733965759"',
        )
        status = self._run_clt_status(clt_dir)
        self.assertEqual(status, "stale")

    def test_clt_ok_when_version_matches_or_newer_than_os(self):
        clt_dir = os.path.join(self.temp_dir, "CommandLineTools")
        os.makedirs(clt_dir, exist_ok=True)
        self._create_mock_bin("sw_vers", 'echo "27.0"')
        self._create_mock_bin(
            "pkgutil",
            'echo "package-id: com.apple.pkg.CLTools_Executables\nversion: 27.0.0.0.1.1733965759"',
        )
        status = self._run_clt_status(clt_dir)
        self.assertEqual(status, "ok")

    def test_brew_preflight_reports_orphan_clt(self):
        session_dir = os.path.join(self.temp_dir, "session")
        os.makedirs(session_dir, exist_ok=True)

        self._create_mock_bin("brew", 'echo "Homebrew 7.0.2"')
        self._create_mock_bin("sw_vers", 'echo "27.0"')
        self._create_mock_bin("pkgutil", 'echo "No receipt found" >&2; exit 1')

        clt_dir = os.path.join(self.temp_dir, "CommandLineTools")
        os.makedirs(clt_dir, exist_ok=True)

        env = dict(os.environ)
        env["MAC_UPDATE_SESSION_DIR"] = session_dir
        env["MAC_UPDATE_CLT_DIR"] = clt_dir
        env["MAC_UPDATE_NONINTERACTIVE"] = "1"
        env["MAC_UPDATE_YES"] = "1"
        env["MAC_LANG"] = "en"
        env["MAC_UPDATE_DRY_RUN"] = "1"

        res = subprocess.run(
            ["bash", str(REPO_ROOT / "update_brew.sh")],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"update_brew failed: {res.stderr}")
        self.assertIn("Command Line Tools (orphan)", res.stdout)
        self.assertIn("sudo rm -rf /Library/Developer/CommandLineTools && sudo xcode-select --install", res.stdout)

    def test_brew_doctor_collapses_multiple_clt_warnings(self):
        doctor_mock_input = """Please note that these warnings are just used to help the Homebrew maintainers
with debugging if you file an issue. If everything you use Homebrew for is
working fine: please don't worry or file an issue; just ignore this. Thanks!

Warning: A newer Command Line Tools release is available.
Update them from Software Update in System Settings.

If that doesn't show you any updates, run:
  sudo rm -rf /Library/Developer/CommandLineTools
  sudo xcode-select --install

Alternatively, manually download them from:
  https://developer.apple.com/download/all/.
You should download the Command Line Tools for Xcode 27.0.

Warning: Your Command Line Tools (CLT) does not support macOS 27.
It is either outdated or was modified.

Please update your Command Line Tools (CLT) or delete it if no updates are available.
Update them from Software Update in System Settings.

If that doesn't show you any updates, run:
  sudo rm -rf /Library/Developer/CommandLineTools
  sudo xcode-select --install

Alternatively, manually download them from:
  https://developer.apple.com/download/all/.
You should download the Command Line Tools for Xcode 27.0.
This is a Tier 2 configuration:
  https://docs.brew.sh/Support-Tiers#tier-2
You can report issues with Tier 2 configurations to Homebrew/* repositories!
  https://docs.brew.sh/Troubleshooting
Read the above document before opening any issues or PRs.
"""
        awk_script = """
    function emit_dylib_block() {
        if (!(dylib_paths == 1 && asaf_paths == 1)) {
            printf "%s", dylib_block
        }
        in_dylib_block = 0
        dylib_block = ""
        dylib_paths = 0
        asaf_paths = 0
    }
    function emit_clt_block() {
        if (!clt_emitted) {
            printf "Warning: Command Line Tools (CLT) requires update/reinstall (details in brew_doctor.txt)\\n"
            clt_emitted = 1
        }
        in_clt_block = 0
    }
    in_clt_block && /^(Warning:|Error:)/ {
        emit_clt_block()
        if ($0 ~ /^Warning: .*Command Line Tools/) {
            in_clt_block = 1
            next
        }
    }
    in_clt_block {
        next
    }
    /^Warning: .*Command Line Tools/ {
        if (in_dylib_block) emit_dylib_block()
        in_clt_block = 1
        next
    }
    /^Warning: Unbrewed dylibs were found in \\/usr\\/local\\/lib/ {
        in_dylib_block = 1
        dylib_block = $0 ORS
        next
    }
    in_dylib_block && /^(Warning:|Error:)/ {
        emit_dylib_block()
        print
        next
    }
    in_dylib_block {
        dylib_block = dylib_block $0 ORS
        if ($0 ~ /^[[:space:]]+\\/usr\\/local\\/lib\\//) {
            dylib_path = $0
            sub(/^[[:space:]]+/, "", dylib_path)
            dylib_paths++
            if (dylib_path == "/usr/local/lib/libASAF.dylib") asaf_paths++
        }
        next
    }
    { print }
    END {
        if (in_dylib_block) emit_dylib_block()
        if (in_clt_block) emit_clt_block()
    }
"""
        res = subprocess.run(
            ["awk", awk_script],
            input=doctor_mock_input,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        lines = [line for line in res.stdout.splitlines() if line.strip()]
        clt_warning_lines = [line for line in lines if "Command Line Tools" in line]
        self.assertEqual(len(clt_warning_lines), 1)
        self.assertEqual(
            clt_warning_lines[0],
            "Warning: Command Line Tools (CLT) requires update/reinstall (details in brew_doctor.txt)",
        )


if __name__ == "__main__":
    unittest.main()
