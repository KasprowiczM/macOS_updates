#!/usr/bin/env python3
"""tests/test_architecture_rosetta.py — Tests for architecture awareness & Rosetta."""
from __future__ import annotations

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
        self.rosetta_dir = os.path.join(self.temp_dir, "rosetta")
        os.environ["MAC_UPDATE_ROSETTA_DIR"] = self.rosetta_dir

    def tearDown(self):
        os.environ["PATH"] = self.old_path
        os.environ.pop("MAC_UPDATE_ROSETTA_DIR", None)
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
        self.assertEqual(norm_name("Fixture Intel App [x86_64]"), norm_name("Fixture Intel App"))
        self.assertEqual(norm_name("Fixture Intel App [x86_64-only]"), norm_name("Fixture Intel App"))
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

        # Case C: pgrep reports not running but rosetta dir exists
        os.makedirs(self.rosetta_dir, exist_ok=True)
        res = subprocess.run(["bash", "-c", script], env=os.environ, capture_output=True)
        self.assertEqual(res.returncode, 0)

    def test_run_summary_rosetta_item(self):
        sdir = Path(self.temp_dir) / "session"
        sdir.mkdir(parents=True, exist_ok=True)
        (sdir / "rosetta_missing_apps.txt").write_text("Fixture Intel App\n", encoding="utf-8")

        items = collect_run_items(sdir)
        rosetta_items = [it for it in items if "Rosetta missing" in (it.get("details") or "")]
        self.assertEqual(len(rosetta_items), 1)
        self.assertEqual(rosetta_items[0]["name"], "Fixture Intel App")
        self.assertEqual(rosetta_items[0]["status"], "pending")
        self.assertEqual(rosetta_items[0]["category"], "internet")
        self.assertEqual(rosetta_items[0]["details"], "Intel-only; Rosetta missing; EOL macOS 28")

    def _run_registry_script(self, body: str, install_rosetta: bool = False):
        """Run the generic Rosetta helpers of lib/internet_apps.sh against a synthetic registry
        containing one fake x86_64-only bundle (no real product handler involved)."""
        sdir = Path(self.temp_dir) / "session"
        sdir.mkdir(parents=True, exist_ok=True)
        app_path = self._create_mock_app("Fixture Intel App")
        registry = Path(self.temp_dir) / "registry.txt"
        registry.write_text(
            "# synthetic registry\nFixture Intel App|manual|STATUS_FIXTURE\nAbsent App|manual|STATUS_ABSENT\n",
            encoding="utf-8",
        )
        script = f"""
        export MAC_UPDATE_SESSION_DIR="{sdir}"
        export SCRIPT_DIR="{REPO_ROOT}"
        {'export MAC_UPDATE_INSTALL_ROSETTA=1' if install_rosetta else ''}
        . "{REPO_ROOT}/lib/platform.sh"
        . "{REPO_ROOT}/lib/ui.sh"
        . "{REPO_ROOT}/lib/version.sh"
        . "{REPO_ROOT}/lib/internet_i18n.sh"
        . "{REPO_ROOT}/i18n/loader.sh"
        . "{REPO_ROOT}/lib/internet_apps.sh"
        internet_app_path() {{
            case "$1" in
                "Fixture Intel App") echo "{app_path}" ;;
                *) echo "{self.temp_dir}/nonexistent/$1.app" ;;
            esac
        }}
        STATUS_FIXTURE="initial"
        STATUS_ABSENT="initial"
        {body.format(registry=registry)}
        echo "RESULT_STATUS=$STATUS_FIXTURE"
        echo "ABSENT_STATUS=$STATUS_ABSENT"
        """
        env = dict(os.environ)
        env["MAC_LANG"] = "pl"
        res = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
        return res, sdir

    def test_rosetta_default_without_flag(self):
        self._create_mock_bin("lipo", 'echo "x86_64"')
        self._create_mock_bin("pgrep", 'exit 1')
        log_file = os.path.join(self.temp_dir, "su_calls.log")
        self._create_mock_bin("softwareupdate", f'echo "$@" >> "{log_file}"\nexit 0')
        res, sdir = self._run_registry_script(
            'internet_rosetta_preflight "{registry}"\n        internet_rosetta_finalize "{registry}"'
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("RESULT_STATUS=", res.stdout)
        self.assertIn("wymaga Rosetty", res.stdout)
        self.assertIn("(niezainstalowana)", res.stdout)
        # an app that is not installed is left alone
        self.assertIn("ABSENT_STATUS=initial", res.stdout)
        # softwareupdate is never called without the explicit opt-in
        self.assertFalse(os.path.exists(log_file))
        missing_file = sdir / "rosetta_missing_apps.txt"
        self.assertTrue(missing_file.is_file())
        self.assertEqual(missing_file.read_text(encoding="utf-8").split("\n")[:-1], ["Fixture Intel App"])

    def test_rosetta_opt_in_installs_and_remeasures(self):
        self._create_mock_bin("lipo", 'echo "x86_64"')
        state_file = os.path.join(self.temp_dir, "rosetta_installed.state")
        self._create_mock_bin("pgrep", f'if [ -f "{state_file}" ]; then exit 0; else exit 1; fi')
        log_file = os.path.join(self.temp_dir, "su_calls.log")
        self._create_mock_bin("softwareupdate", f'echo "$@" >> "{log_file}"\ntouch "{state_file}"\nexit 0')
        res, sdir = self._run_registry_script(
            'internet_rosetta_preflight "{registry}"\n        internet_rosetta_finalize "{registry}"',
            install_rosetta=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("wymaga Rosetty", res.stdout)
        self.assertNotIn("(niezainstalowana)", res.stdout)
        calls = Path(log_file).read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].strip(), "--install-rosetta --agree-to-license")
        # Rosetta present: nothing is reported as missing
        self.assertFalse((sdir / "rosetta_missing_apps.txt").exists())

    def test_rosetta_helpers_ignore_native_apps(self):
        self._create_mock_bin("lipo", 'echo "arm64"')
        self._create_mock_bin("pgrep", 'exit 1')
        log_file = os.path.join(self.temp_dir, "su_calls.log")
        self._create_mock_bin("softwareupdate", f'echo "$@" >> "{log_file}"\nexit 0')
        res, sdir = self._run_registry_script(
            'internet_rosetta_preflight "{registry}"\n        internet_rosetta_finalize "{registry}"',
            install_rosetta=True,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("RESULT_STATUS=initial", res.stdout)
        self.assertFalse(os.path.exists(log_file))
        self.assertFalse((sdir / "rosetta_missing_apps.txt").exists())

    def test_product_registry_has_no_intel_only_handler(self):
        """The Rosetta path is generic: no product handler may carry its own copy."""
        text = (REPO_ROOT / "lib" / "internet_app_updates.sh").read_text(encoding="utf-8")
        self.assertNotIn("rosetta_missing_apps", text)
        main = (REPO_ROOT / "update_internet_apps.sh").read_text(encoding="utf-8")
        self.assertIn("internet_rosetta_preflight", main)
        self.assertIn("internet_rosetta_finalize", main)


if __name__ == "__main__":
    unittest.main()
