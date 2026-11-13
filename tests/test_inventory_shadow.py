"""Shadow entrypoint observes and saves privately, never enters update_all."""

import json
import os
import plistlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ShadowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.repo = self.base / "repo"
        self.repo.mkdir()
        shutil.copy(ROOT / "build_inventory.sh", self.repo)
        for folder in ("lib", "i18n", "config"):
            shutil.copytree(ROOT / folder, self.repo / folder)
        (self.repo / "update_all.sh").write_text("echo ENTERED_UPDATER >&2\nexit 99\n")
        self.apps = self.base / "Applications"
        self.apps.mkdir()
        self.state = self.base / "state"
        self.prefix = self.base / "prefix"
        (self.prefix / "Cellar").mkdir(parents=True)
        self.home = self.base / "home"
        self.home.mkdir()
        self.bin = self.base / "bin"
        self.bin.mkdir()
        for name, script in [
            ("uname", "echo arm64"),
            ("sw_vers", "echo 14.0"),
            ("mas", "exit 0"),
        ]:
            path = self.bin / name
            path.write_text("#!/bin/sh\n" + script + "\n")
            path.chmod(0o755)
        self.env = dict(
            os.environ,
            PATH=str(self.bin) + ":" + os.environ["PATH"],
            HOME=str(self.home),
            MAC_UPDATE_APP_DIRS=str(self.apps),
            MAC_UPDATE_STATE_DIR=str(self.state),
            MAC_LANG="en",
            MAC_UPDATE_HOMEBREW_PREFIX=str(self.prefix),
            MAC_UPDATE_BREW_PREFIXES=str(self.prefix),
            MAC_UPDATE_CLI_PREFIXES=str(self.prefix),
        )

    def run_shadow(self, *args):
        return subprocess.run(
            ["bash", str(self.repo / "build_inventory.sh"), "--shadow", *args],
            env=self.env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def app(self):
        contents = self.apps / "Unknown Agent | Ω.app/Contents"
        contents.mkdir(parents=True)
        (contents / "Info.plist").write_bytes(
            plistlib.dumps(
                {
                    "CFBundleIdentifier": "test.unknown",
                    "CFBundleShortVersionString": "1",
                }
            )
        )
        (contents / "_MASReceipt").mkdir()
        (contents / "_MASReceipt/receipt").write_text("signal only")

    def test_shadow_creates_private_snapshot_without_legacy_inventory(self):
        self.app()
        result = self.run_shadow("--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["mode"], "shadow")
        self.assertEqual(report["instances"], 1)
        self.assertEqual(report["resolutions"][0]["source"], "app_store")
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.state / "inventory.json").stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.repo / "APPLICATIONS.md").exists())
        self.assertNotIn("ENTERED_UPDATER", result.stderr)

    def test_dry_shadow_writes_no_state(self):
        self.app()
        result = self.run_shadow("--dry-run", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.state.exists())
        self.assertFalse((self.repo / "logs").exists())

    def test_repeated_shadow_keeps_identity_and_advances_generation(self):
        self.app()
        first = self.run_shadow("--json")
        self.assertEqual(first.returncode, 0, first.stderr)
        before = json.loads((self.state / "inventory.json").read_text())
        result = self.run_shadow("--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        after = json.loads((self.state / "inventory.json").read_text())
        self.assertEqual(
            after["instances"][0]["instance_id"], before["instances"][0]["instance_id"]
        )
        self.assertEqual(after["generation"], 2)

    def test_unknown_flags_refuse_without_falling_through_to_updater(self):
        result = self.run_shadow("--install")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("ENTERED_UPDATER", result.stderr)
        self.assertFalse(self.state.exists())

    def test_missing_root_is_partial_not_empty_success(self):
        self.env["MAC_UPDATE_APP_DIRS"] = str(self.base / "missing")
        result = self.run_shadow("--json")
        self.assertEqual(result.returncode, 10, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["readiness"], "partial")
        self.assertIn(
            "root_unavailable",
            [s["reason_code"] for s in report["source_statuses"].values()],
        )

    def test_saved_conflict_survives_failed_cask_metadata_refresh(self):
        self.app()
        app = self.apps / "Unknown Agent | Ω.app"
        cask = self.prefix / "Caskroom/demo"
        receipt = cask / ".metadata/1/20261113/Casks/demo.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_text(
            json.dumps(
                {
                    "token": "demo",
                    "version": "1",
                    "artifacts": [{"app": ["Original.app"]}],
                }
            )
        )
        (cask / "1").mkdir()
        (cask / "1/Original.app").symlink_to(app)
        result = self.run_shadow("--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["resolutions"][0]["source"], "conflict")
        saved = json.loads((self.state / "inventory.json").read_text())
        self.assertEqual(
            saved["packages"][0]["related_instance_ids"],
            [saved["instances"][0]["instance_id"]],
        )
        self.assertEqual(report["resolutions"][1]["capability"], "inventory_only")
        receipt.write_text("{bad")
        result = self.run_shadow("--json")
        self.assertEqual(result.returncode, 10, result.stderr)
        resolved = json.loads(result.stdout)["resolutions"][0]
        self.assertEqual(resolved["source"], "conflict")
        self.assertEqual(resolved["capability"], "inventory_only")

    def test_active_generation_shadow_is_observation_only(self):
        self.app()
        built = subprocess.run(['bash', str(self.repo / 'build_inventory.sh')], env=self.env,
                               stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=15)
        self.assertEqual(built.returncode, 0, built.stderr + built.stdout)
        before = (self.state / 'inventory.json').read_bytes()
        report_before = (self.repo / 'APPLICATIONS.md').read_bytes()
        result = self.run_shadow('--json')
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertFalse(json.loads(result.stdout)['saved'])
        self.assertEqual((self.state / 'inventory.json').read_bytes(), before)
        self.assertEqual((self.repo / 'APPLICATIONS.md').read_bytes(), report_before)
