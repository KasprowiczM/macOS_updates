#!/usr/bin/env python3
"""tests/test_architecture_rosetta.py — Tests for architecture awareness & Rosetta."""

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))

from inventory import app_architecture, norm_name
from run_summary import collect_run_items


class ArchitectureRosettaTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="macupd_test_arch_")
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

    def _create_mock_app(self, app_name: str, exe_name: str | None = None) -> Path:
        app_dir = Path(self.temp_dir) / f"{app_name}.app"
        macos_dir = app_dir / "Contents" / "MacOS"
        macos_dir.mkdir(parents=True, exist_ok=True)
        actual_exe = exe_name or app_name
        exe_file = macos_dir / actual_exe
        exe_file.write_text("#!/bin/sh\nexit 0\n")
        exe_file.chmod(0o755)

        info_plist = app_dir / "Contents" / "Info.plist"
        info_plist.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>{actual_exe}</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
</dict>
</plist>
""", encoding="utf-8")
        return app_dir

    def test_norm_name_ignores_arch_markers(self):
        self.assertEqual(norm_name("DJI Assistant 2 [x86_64]"), norm_name("DJI Assistant 2"))
        self.assertEqual(norm_name("DJI Assistant 2 [x86_64-only]"), norm_name("DJI Assistant 2"))
        self.assertEqual(norm_name("Foo [arm64]"), norm_name("Foo"))
        self.assertEqual(norm_name("Bar [universal]"), norm_name("Bar"))

    def test_app_architecture_unit(self):
        # 1. lipo outputs arm64
        self._create_mock_bin("lipo", 'echo "arm64"')
        app1 = self._create_mock_app("ArmApp")
        self.assertEqual(app_architecture(app1), "arm64")

        # 2. lipo outputs universal
        self._create_mock_bin("lipo", 'echo "arm64 x86_64"')
        app2 = self._create_mock_app("UniApp")
        self.assertEqual(app_architecture(app2), "universal")

        # 3. lipo outputs x86_64
        self._create_mock_bin("lipo", 'echo "x86_64"')
        app3 = self._create_mock_app("IntelApp")
        self.assertEqual(app_architecture(app3), "x86_64-only")

        # 4. Non-existent app
        self.assertEqual(app_architecture(Path(self.temp_dir) / "Missing.app"), "unknown")

    def test_rosetta_installed_behavior(self):
        # Sourcing lib/platform.sh and testing mac_update_rosetta_installed
        script = f"""
        . "{REPO_ROOT}/lib/platform.sh"
        mac_update_rosetta_installed
        """
        # Case A: pgrep reports oahd running
        self._create_mock_bin("pgrep", 'echo "1234"; exit 0')
        res = subprocess.run(["bash", "-c", script], env=os.environ, capture_output=True)
        self.assertEqual(res.returncode, 0)

        # Case B: pgrep reports not running and dir does not exist
        self._create_mock_bin("pgrep", 'exit 1')
        res = subprocess.run(["bash", "-c", script], env=os.environ, capture_output=True)
        self.assertEqual(res.returncode, 1)

    def test_run_summary_rosetta_item(self):
        sdir = Path(self.temp_dir) / "session"
        sdir.mkdir(parents=True, exist_ok=True)
        (sdir / "rosetta_missing_apps.txt").write_text("DJI Assistant 2\n", encoding="utf-8")

        items = collect_run_items(sdir)
        rosetta_items = [it for it in items if "Rosetta missing" in (it.get("details") or "")]
        self.assertEqual(len(rosetta_items), 1)
        self.assertEqual(rosetta_items[0]["name"], "DJI Assistant 2")
        self.assertEqual(rosetta_items[0]["status"], "pending")
        self.assertEqual(rosetta_items[0]["category"], "internet")
        self.assertEqual(rosetta_items[0]["details"], "Intel-only; Rosetta missing; EOL macOS 28")

    def test_update_internet_rosetta_default_without_flag(self):
        # Mock lipo outputting x86_64
        self._create_mock_bin("lipo", 'echo "x86_64"')
        # Mock pgrep returning 1 (Rosetta not installed)
        self._create_mock_bin("pgrep", 'exit 1')
        # Mock softwareupdate logging calls
        log_file = os.path.join(self.temp_dir, "su_calls.log")
        self._create_mock_bin("softwareupdate", f'echo "$@" >> "{log_file}"\nexit 0')

        sdir = Path(self.temp_dir) / "session"
        sdir.mkdir(parents=True, exist_ok=True)
        app_path = self._create_mock_app("DJI Assistant 2")

        test_script = f"""
        export MAC_UPDATE_SESSION_DIR="{sdir}"
        export SCRIPT_DIR="{REPO_ROOT}"
        . "{REPO_ROOT}/lib/platform.sh"
        . "{REPO_ROOT}/lib/ui.sh"
        . "{REPO_ROOT}/lib/version.sh"
        . "{REPO_ROOT}/lib/internet_i18n.sh"
        . "{REPO_ROOT}/i18n/loader.sh"
        . "{REPO_ROOT}/lib/internet_apps.sh"

        internet_app_path() {{
            echo "{app_path}"
        }}

        . "{REPO_ROOT}/lib/internet_app_updates.sh"
        iu_dji_assistant
        echo "RESULT_STATUS=$STATUS_DJI"
        """
        env = dict(os.environ)
        env["MAC_LANG"] = "pl"
        res = subprocess.run(["bash", "-c", test_script], env=env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("wymaga Rosetty", res.stdout)
        self.assertIn("(niezainstalowana)", res.stdout)
        # Verify softwareupdate was never called
        self.assertFalse(os.path.exists(log_file))
        # Verify rosetta_missing_apps.txt was written
        missing_file = sdir / "rosetta_missing_apps.txt"
        self.assertTrue(missing_file.is_file())
        self.assertIn("DJI Assistant 2", missing_file.read_text(encoding="utf-8"))

    def test_update_internet_rosetta_opt_in_installs_and_remeasures(self):
        # Mock lipo outputting x86_64
        self._create_mock_bin("lipo", 'echo "x86_64"')
        state_file = os.path.join(self.temp_dir, "rosetta_installed.state")
        # Mock pgrep checking state_file
        self._create_mock_bin("pgrep", f'if [ -f "{state_file}" ]; then exit 0; else exit 1; fi')
        # Mock softwareupdate logging calls and creating state_file
        log_file = os.path.join(self.temp_dir, "su_calls.log")
        self._create_mock_bin("softwareupdate", f'echo "$@" >> "{log_file}"\ntouch "{state_file}"\nexit 0')

        sdir = Path(self.temp_dir) / "session"
        sdir.mkdir(parents=True, exist_ok=True)
        app_path = self._create_mock_app("DJI Assistant 2")

        test_script = f"""
        export MAC_UPDATE_SESSION_DIR="{sdir}"
        export MAC_UPDATE_INSTALL_ROSETTA=1
        export SCRIPT_DIR="{REPO_ROOT}"
        . "{REPO_ROOT}/lib/platform.sh"
        . "{REPO_ROOT}/lib/ui.sh"
        . "{REPO_ROOT}/lib/version.sh"
        . "{REPO_ROOT}/lib/internet_i18n.sh"
        . "{REPO_ROOT}/i18n/loader.sh"
        . "{REPO_ROOT}/lib/internet_apps.sh"

        internet_app_path() {{
            echo "{app_path}"
        }}

        # Simulate update_internet_apps.sh pre-check
        if ! mac_update_rosetta_installed; then
            if [ "${{MAC_UPDATE_INSTALL_ROSETTA:-0}}" = "1" ]; then
                softwareupdate --install-rosetta --agree-to-license
            fi
        fi

        . "{REPO_ROOT}/lib/internet_app_updates.sh"
        iu_dji_assistant
        echo "RESULT_STATUS=$STATUS_DJI"
        """
        env = dict(os.environ)
        env["MAC_LANG"] = "pl"
        res = subprocess.run(["bash", "-c", test_script], env=env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        # Rosetta was installed, so it should NOT say (niezainstalowana)
        self.assertIn("wymaga Rosetty", res.stdout)
        self.assertNotIn("(niezainstalowana)", res.stdout)
        # Verify softwareupdate was called once with --install-rosetta --agree-to-license
        self.assertTrue(os.path.exists(log_file))
        calls = Path(log_file).read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].strip(), "--install-rosetta --agree-to-license")


if __name__ == "__main__":
    unittest.main()
