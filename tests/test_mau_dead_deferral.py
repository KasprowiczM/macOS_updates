"""MAU DeferralVersions pins vs. the quarantine expiry (P2-11, revised 2026-09-28).

P2-11 made a DeferralVersions pin that equals the installed build count as
"expired". That contradicted mau_clean_stale_deferrals, which deliberately
keeps such a pin: it is MAU's own bookkeeping for a self-updating product and
MAU re-creates it within hours (2026-09-02 regression suite). The result on
the 2026-09-28 run: "quarantine older than 14d — releasing: TEAMS21" on every
run, followed by "released: none" and TEAMS21 still in the domain.

mau_quarantine_expired_ids therefore reports only Office DeferralDays entries
that outlived the window. Version pins are not quarantines this toolkit arms,
so they never appear in its expiry list.
"""

from __future__ import annotations

import os
import plistlib
import shutil
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


@unittest.skipUnless(shutil.which("plutil"), "requires plutil (macOS)")
class MauDeadDeferralTests(unittest.TestCase):
    def test_pin_at_installed_build_is_not_reported_as_expired(self) -> None:
        """A pin at the installed build is MAU bookkeeping: never 'released', never reported."""
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
            self.assertNotIn("TEAMS21", out.stdout.split())
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

    def test_expired_deferral_days_reported_without_version_pins(self) -> None:
        """An expired Office DeferralDays entry is reported; the Teams pin is not."""
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
            self.assertEqual(expired, ["MSWD2019"])


if __name__ == "__main__":
    unittest.main()
