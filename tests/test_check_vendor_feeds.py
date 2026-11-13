#!/usr/bin/env bash
"""tests/test_check_vendor_feeds.py — Tests for scripts/check_vendor_feeds.sh (T14)."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import copy_toolkit


class CheckVendorFeedsTests(unittest.TestCase):
    def fixture_script(self, root: Path) -> Path:
        toolkit = root / "toolkit"
        copy_toolkit(REPO_ROOT, toolkit)
        script = toolkit / "scripts" / "check_vendor_feeds.sh"
        text = script.read_text()
        marker = '. "$SCRIPT_DIR/lib/version.sh"'
        mock = """
internet_app_path() { printf '%s\n' "$MOCK_APP_ROOT"; }
internet_app_snapshot_version() { echo "$*" >> "$MOCK_CALLS"; echo 1.0; }
vendor_feed_lookup() { echo "$*" >> "$MOCK_CALLS"; echo '1.0|https://example.invalid/app.zip|-|-|zip|example.invalid'; }
"""
        text = text.replace(marker, marker + "\n" + mock)
        text = text.replace('GOOGLE_LOG_SYS="/Library/Application Support/Google/GoogleUpdater/updater.log"', 'GOOGLE_LOG_SYS="$HOME/no-system-log"')
        script.write_text(text)
        return script

    def test_script_exists_and_is_executable(self) -> None:
        script = REPO_ROOT / "scripts" / "check_vendor_feeds.sh"
        self.assertTrue(script.is_file())
        st = os.stat(script)
        self.assertTrue(bool(st.st_mode & stat.S_IXUSR))

    def test_check_vendor_feeds_json_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            script = self.fixture_script(root)
            env = dict(os.environ, HOME=tmpdir, MOCK_APP_ROOT=tmpdir, MOCK_CALLS=str(root / "calls"))
            res = subprocess.run(["bash", str(script), "--json"], cwd=str(root),
                                 capture_output=True, text=True, timeout=30, env=env)
            self.assertEqual(res.returncode, 0, f"Error:\n{res.stdout}\n{res.stderr}")
            data = json.loads(res.stdout)
            app_names = [item["app"] for item in data]
            self.assertIn("Google Chrome", app_names)
            self.assertIn("Gemini", app_names)
            self.assertIn("Comet", app_names)
            self.assertTrue((root / "calls").read_text())

    def test_vendor_lookup_policy_does_not_contaminate_artifact_host(self) -> None:
        source = (REPO_ROOT / "scripts/check_vendor_feeds.sh").read_text()
        collect = source[source.index("DATA_LINES=()"):source.index("# Omaha apps:")]
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Path(tmpdir) / "feeds.txt"
            config.write_text("Proton Mail|json|https://proton.me/feed|proton_releases|dmg|proton.me\n")
            script = f"""
            CFG_FILE="{config}"
            internet_app_path() {{ echo "{tmpdir}"; }}
            internet_app_snapshot_version() {{ echo 1.0; }}
            vendor_feed_lookup() {{ echo '2.0|https://proton.me/update.dmg|sha512hex|abc|dmg|proton.me|rollout_hold'; }}
            version_cmp() {{ echo older; }}
            {collect}
            printf '%s\n' "${{DATA_LINES[@]}}"
            """
            result = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "Proton Mail|1.0|2.0|rollout_hold|proton.me")

    def test_check_vendor_feeds_reads_status_from_updater_log_old(self) -> None:
        """Omaha status present only in updater.log.old is detected in check_vendor_feeds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir) / "home"
            g_dir = fake_home / "Library" / "Application Support" / "Google" / "GoogleUpdater"
            g_dir.mkdir(parents=True)
            (g_dir / "updater.log").write_text("recent log with no chrome entry\n", encoding="utf-8")
            (g_dir / "updater.log.old").write_text(
                '[1:2:0923/094646.163000:VERBOSE2:components/update_client/request_sender.cc:200] {"response":{"apps":[{"appid":"com.google.chrome","updatecheck":{"status":"noupdate"}}]}}\n',
                encoding="utf-8",
            )
            env = dict(os.environ)
            env["HOME"] = str(fake_home)
            env["MOCK_APP_ROOT"] = str(fake_home)
            env["MOCK_CALLS"] = str(Path(tmpdir) / "calls")
            script = self.fixture_script(Path(tmpdir))
            res = subprocess.run(
                ["bash", str(script), "--json"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
            )
            self.assertEqual(res.returncode, 0, f"Error:\n{res.stdout}\n{res.stderr}")
            data = json.loads(res.stdout)
            chrome_entry = next((item for item in data if item["app"] == "Google Chrome"), None)
            self.assertIsNotNone(chrome_entry)
            self.assertEqual(chrome_entry.get("omaha_status"), "noupdate")
            self.assertTrue(Path(env["MOCK_CALLS"]).read_text())


if __name__ == "__main__":
    unittest.main()
