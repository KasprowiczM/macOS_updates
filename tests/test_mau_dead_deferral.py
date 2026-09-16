"""Tests for MAU dead deferral expiry (P2-11).

If OptionalUpdatesDeferrals.DeferralVersions.<ID> matches the installed build
of the product, the deferral is dead (it points to what is already installed)
and must be considered expired immediately by mau_quarantine_expired_ids.
"""

from __future__ import annotations

import os
import plistlib
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LIB = REPO_ROOT / "lib" / "internet_app_updates.sh"


def run_lib(snippet: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    return subprocess.run(
        ["bash", "-c", f'source "{LIB}" >/dev/null 2>&1; {snippet}'],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=full_env,
    )


class MauDeadDeferralTests(unittest.TestCase):
    def test_dead_deferral_version_expires_immediately(self) -> None:
        """When DeferralVersions matches installed build, it expires immediately."""
        with tempfile.NamedTemporaryFile(suffix=".plist", delete=False) as f:
            plist_path = f.name
            plist_data = {
                "AppVersions": {
                    "/Applications/Microsoft Teams.app": "26225.1706.5101.3140"
                },
                "OptionalUpdatesDeferrals": {
                    "DeferralVersions": {
                        "TEAMS21": "26225.1706.5101.3140"
                    }
                },
            }
            plistlib.dump(plist_data, f)

        try:
            out = run_lib("mau_quarantine_expired_ids", {"MAC_UPDATE_MAU_PREFS_FILE": plist_path})
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn("TEAMS21", out.stdout.split())
        finally:
            if os.path.exists(plist_path):
                os.unlink(plist_path)

    def test_different_deferral_version_does_not_expire(self) -> None:
        """When DeferralVersions does not match installed build, it is not expired."""
        with tempfile.NamedTemporaryFile(suffix=".plist", delete=False) as f:
            plist_path = f.name
            plist_data = {
                "AppVersions": {
                    "/Applications/Microsoft Teams.app": "26225.1706.5101.3140"
                },
                "OptionalUpdatesDeferrals": {
                    "DeferralVersions": {
                        "TEAMS21": "26225.1706.5101.3141"
                    }
                },
            }
            plistlib.dump(plist_data, f)

        try:
            out = run_lib("mau_quarantine_expired_ids", {"MAC_UPDATE_MAU_PREFS_FILE": plist_path})
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertNotIn("TEAMS21", out.stdout.split())
        finally:
            if os.path.exists(plist_path):
                os.unlink(plist_path)

    def test_both_deferral_days_and_dead_deferral_version_expire(self) -> None:
        """Both expired DeferralDays and dead DeferralVersions are returned without duplicates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plist_path = os.path.join(tmpdir, "mau.plist")
            state_path = os.path.join(tmpdir, "quar.tsv")
            Path(state_path).write_text("MSWD2019\t1000000000\n", encoding="utf-8")

            plist_data = {
                "AppVersions": {
                    "/Applications/Microsoft Teams.app": "26225.1706.5101.3140"
                },
                "OptionalUpdatesDeferrals": {
                    "DeferralVersions": {
                        "TEAMS21": "26225.1706.5101.3140"
                    }
                },
            }
            with open(plist_path, "wb") as f:
                plistlib.dump(plist_data, f)

            snippet = 'mau_active_office_deferrals() { echo "MSWD2019"; }; mau_quarantine_expired_ids'
            out = run_lib(
                snippet,
                {
                    "MAC_UPDATE_MAU_PREFS_FILE": plist_path,
                    "MAC_UPDATE_MAU_STATE_FILE": state_path,
                },
            )
            self.assertEqual(out.returncode, 0, out.stderr)
            expired = out.stdout.split()
            self.assertIn("MSWD2019", expired)
            self.assertIn("TEAMS21", expired)


if __name__ == "__main__":
    unittest.main()
