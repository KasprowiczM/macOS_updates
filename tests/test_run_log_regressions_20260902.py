"""Regression tests for the defects found in the 2026-09-01 run log.

Each test pins one root cause that made a step report a warning on every run,
or hid a real update behind a guard that could never re-evaluate itself:

  * the Office DeferralDays quarantine armed on 2026-07-14 could never be
    released, because an armed deferral hides its product from
    `msupdate --list` and the release rule needed an offer to fire. Twenty
    consecutive runs reported "held by deferral"; measured with the quarantine
    lifted, the feed was offering 16.112.3 against 16.112.2 installed;
  * DeferralVersions.TEAMS21 was released ten times and re-created by MAU every
    time, because a pin AT the installed build is MAU's own bookkeeping for a
    self-updating product, not a stale pin;
  * `sudo mas upgrade` with no arguments re-enumerates the outdated set in
    root's context; on 2026-09-01 it upgraded Copilot and silently skipped
    WhatsApp, which the same command upgraded in three seconds as the user;
  * every run_summary_*.json ever written carried "counts": {}, because the
    caller never passed the mapping build_run_summary has always accepted.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LIB = REPO_ROOT / "lib" / "internet_app_updates.sh"


def run_lib(snippet: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Run a snippet with lib/internet_app_updates.sh sourced."""
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


class QuarantineExpiryTests(unittest.TestCase):
    """The quarantine must be able to expire without an offer to trigger it."""

    def test_unrecorded_active_deferral_counts_as_expired(self) -> None:
        """A live deferral with no arm record predates the clock, so it is old.

        This is the exact 2026-09-01 state: five Office DeferralDays entries
        armed on 2026-07-14, no bookkeeping, and no way to prove their age. The
        safe reading is 'older than the window', because the alternative is the
        blackout that actually happened.
        """
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "quar.tsv")
            out = run_lib(
                'mau_active_office_deferrals() { echo "MSWD2019 XCEL2019"; }; '
                "mau_quarantine_expired_ids",
                {"MAC_UPDATE_MAU_STATE_FILE": state},
            )
            self.assertEqual(out.stdout.strip(), "MSWD2019 XCEL2019", out.stderr)

    def test_recent_arm_is_not_expired(self) -> None:
        """A quarantine inside its window must stay armed, or it protects nothing."""
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "quar.tsv")
            out = run_lib(
                'mau_active_office_deferrals() { echo "MSWD2019"; }; '
                'mau_quarantine_note_armed "MSWD2019"; '
                "mau_quarantine_expired_ids",
                {"MAC_UPDATE_MAU_STATE_FILE": state},
            )
            self.assertEqual(out.stdout.strip(), "", out.stderr)

    def test_rearming_does_not_restart_the_clock(self) -> None:
        """The defect being fixed is a quarantine that renews itself forever.

        mau_arm_deferrals is a no-op when the value is already the configured
        day count, so a long-lived quarantine is re-reported as 'armed' run
        after run. If that refreshed the timestamp, the expiry could never fire
        and this fix would reproduce the original bug with extra steps.
        """
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "quar.tsv")
            run_lib('mau_quarantine_note_armed "MSWD2019"', {"MAC_UPDATE_MAU_STATE_FILE": state})
            first = Path(state).read_text(encoding="utf-8")
            run_lib('mau_quarantine_note_armed "MSWD2019"', {"MAC_UPDATE_MAU_STATE_FILE": state})
            self.assertEqual(first, Path(state).read_text(encoding="utf-8"))

    def test_expiry_fires_past_the_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "quar.tsv"
            state.write_text("MSWD2019\t1000000000\n", encoding="utf-8")
            out = run_lib(
                'mau_active_office_deferrals() { echo "MSWD2019"; }; mau_quarantine_expired_ids',
                {"MAC_UPDATE_MAU_STATE_FILE": str(state)},
            )
            self.assertEqual(out.stdout.strip(), "MSWD2019", out.stderr)

    def test_release_clears_the_record(self) -> None:
        """A released quarantine must start a fresh clock if it is ever re-armed."""
        with tempfile.TemporaryDirectory() as tmp:
            state = os.path.join(tmp, "quar.tsv")
            out = run_lib(
                'mau_quarantine_note_armed "MSWD2019 XCEL2019"; '
                'mau_quarantine_forget "DeferralDays.XCEL2019"; '
                'cut -f1 "$MAC_UPDATE_MAU_STATE_FILE" | tr "\\n" " "',
                {"MAC_UPDATE_MAU_STATE_FILE": state},
            )
            self.assertEqual(out.stdout.split(), ["MSWD2019"], out.stderr)

    def test_max_days_is_clamped(self) -> None:
        for raw, expected in (("", "14"), ("abc", "14"), ("0", "14"), ("500", "14"), ("21", "21")):
            out = run_lib("mau_quarantine_max_days", {"MAC_UPDATE_MAU_QUARANTINE_MAX_DAYS": raw})
            self.assertEqual(out.stdout.strip(), expected, f"raw={raw!r}")

    def test_empty_branch_reconciles_exactly_once(self) -> None:
        """Two export/import cycles in one run race each other through cfprefsd.

        The expired set is therefore passed as the offer argument of the SAME
        reconcile call, never as a second call.
        """
        text = LIB.read_text(encoding="utf-8")
        branch = text.split('MAU_HELD="$(mau_active_office_deferrals)"')[0]
        branch = branch.split("# Nothing offered.")[-1]
        self.assertIn('MAU_EXPIRED="$(mau_quarantine_expired_ids)"', branch)
        self.assertIn('mau_reconcile_deferrals "" "$MAU_EXPIRED"', branch)
        # Count call sites, not the comments that explain them.
        calls = [
            line for line in branch.splitlines()
            if line.strip().startswith("mau_reconcile_deferrals")
        ]
        self.assertEqual(len(calls), 1, calls)

    def test_bookkeeping_runs_only_on_verified_sets(self) -> None:
        """The clock must never be started by a write that did not land.

        mau_reconcile_deferrals re-reads the live domain and narrows $removed to
        what it actually contains; the bookkeeping calls have to sit after that.
        """
        text = LIB.read_text(encoding="utf-8")
        body = text.split("mau_reconcile_deferrals() {")[1]
        verify = body.index('removed="${verified_removed# }"')
        note = body.index('mau_quarantine_note_armed "$armed"')
        forget = body.index('mau_quarantine_forget "$removed"')
        self.assertLess(verify, note)
        self.assertLess(verify, forget)


class TeamsDeferralVersionTests(unittest.TestCase):
    """A pin at the installed build is MAU bookkeeping, not a stale pin."""

    def test_pin_at_installed_build_is_not_a_health_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plist = os.path.join(tmp, "mau.plist")
            subprocess.run(
                ["plutil", "-create", "xml1", plist], check=True, capture_output=True
            )
            subprocess.run(
                [
                    "plutil", "-insert", "OptionalUpdatesDeferrals", "-json",
                    '{"DeferralVersions":{"TEAMS21":"26213.1006.5011.1671"}}', plist,
                ],
                check=True, capture_output=True,
            )
            out = run_lib(
                'mau_installed_build_for_id() { echo "26213.1006.5011.1671"; }; '
                f'mau_deferral_health_warnings "{plist}"'
            )
            self.assertEqual(out.stdout.strip(), "", out.stderr)

    def test_genuinely_malformed_pin_still_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plist = os.path.join(tmp, "mau.plist")
            subprocess.run(["plutil", "-create", "xml1", plist], check=True, capture_output=True)
            subprocess.run(
                [
                    "plutil", "-insert", "OptionalUpdatesDeferrals", "-json",
                    '{"DeferralVersions":{"TEAMS21":"not-a-version"}}', plist,
                ],
                check=True, capture_output=True,
            )
            out = run_lib(
                'mau_installed_build_for_id() { echo "26213.1006.5011.1671"; }; '
                f'mau_deferral_health_warnings "{plist}"'
            )
            self.assertIn("not the documented Major.Minor form", out.stdout)

    def test_pin_at_installed_build_is_not_removed(self) -> None:
        """Ten runs released it and MAU re-created it every time — stop writing."""
        with tempfile.TemporaryDirectory() as tmp:
            plist = os.path.join(tmp, "mau.plist")
            subprocess.run(["plutil", "-create", "xml1", plist], check=True, capture_output=True)
            subprocess.run(
                [
                    "plutil", "-insert", "OptionalUpdatesDeferrals", "-json",
                    '{"DeferralVersions":{"TEAMS21":"26213.1006.5011.1671"}}', plist,
                ],
                check=True, capture_output=True,
            )
            out = run_lib(
                'mau_installed_build_for_id() { echo "26213.1006.5011.1671"; }; '
                f'mau_clean_stale_deferrals "{plist}" ""'
            )
            self.assertEqual(out.stdout.strip(), "", out.stderr)
            still = subprocess.run(
                ["plutil", "-extract", "OptionalUpdatesDeferrals.DeferralVersions.TEAMS21",
                 "raw", "-o", "-", plist],
                capture_output=True, text=True,
            )
            self.assertEqual(still.stdout.strip(), "26213.1006.5011.1671")

    def test_stale_pin_below_installed_build_is_still_removed(self) -> None:
        """A pin genuinely older than what is installed does cap the product."""
        with tempfile.TemporaryDirectory() as tmp:
            plist = os.path.join(tmp, "mau.plist")
            subprocess.run(["plutil", "-create", "xml1", plist], check=True, capture_output=True)
            subprocess.run(
                [
                    "plutil", "-insert", "OptionalUpdatesDeferrals", "-json",
                    '{"DeferralVersions":{"TEAMS21":"26100.0.0.0"}}', plist,
                ],
                check=True, capture_output=True,
            )
            out = run_lib(
                'mau_installed_build_for_id() { echo "26213.1006.5011.1671"; }; '
                f'mau_clean_stale_deferrals "{plist}" ""'
            )
            self.assertIn("DeferralVersions.TEAMS21", out.stdout)

    def test_bookkeeping_pin_is_not_actionable(self) -> None:
        """The preflight banner must not shout about a pin nobody can clear."""
        with tempfile.TemporaryDirectory() as tmp:
            plist = os.path.join(tmp, "mau.plist")
            subprocess.run(["plutil", "-create", "xml1", plist], check=True, capture_output=True)
            subprocess.run(
                ["plutil", "-insert", "OptionalUpdatesDeferrals", "-json",
                 '{"DeferralVersions":{"TEAMS21":"26213.1006.5011.1671"}}', plist],
                check=True, capture_output=True,
            )
            out = run_lib(
                'mau_installed_build_for_id() { echo "26213.1006.5011.1671"; }; '
                f'mau_actionable_deferrals "{plist}"'
            )
            self.assertEqual(out.stdout.strip(), "", out.stderr)

    def test_office_quarantine_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plist = os.path.join(tmp, "mau.plist")
            subprocess.run(["plutil", "-create", "xml1", plist], check=True, capture_output=True)
            subprocess.run(
                ["plutil", "-insert", "OptionalUpdatesDeferrals", "-json",
                 '{"DeferralDays":{"MSWD2019":7}}', plist],
                check=True, capture_output=True,
            )
            out = run_lib(f'mau_actionable_deferrals "{plist}"')
            self.assertIn("DeferralDays.MSWD2019", out.stdout)

    def test_preflight_banner_is_conditional(self) -> None:
        text = LIB.read_text(encoding="utf-8")
        preflight = text.split("mau_deferral_preflight() {")[1].split("\n}")[0]
        self.assertIn('if [ -n "$(mau_actionable_deferrals "$plist")" ]; then', preflight)
        self.assertIn("print_info", preflight)

    def test_teams_has_a_bundle_mapping(self) -> None:
        out = run_lib("mau_app_path_for_id TEAMS21")
        self.assertEqual(out.stdout.strip(), "/Applications/Microsoft Teams.app")


class MasUpgradeEnumerationTests(unittest.TestCase):
    """TRACK 1 must act on the set this run measured, not on root's re-scan."""

    def setUp(self) -> None:
        self.text = (REPO_ROOT / "update_appstore.sh").read_text(encoding="utf-8")

    def test_track1_passes_explicit_ids(self) -> None:
        self.assertIn("mas upgrade $MAS_TOR1_IDS", self.text)
        self.assertIn('MAS_TOR1_IDS="$(mas_outdated_ids "$NATIVE_OUTDATED"', self.text)

    def test_user_session_retry_exists_and_runs_without_sudo(self) -> None:
        retry = self.text.split('for MAS_RETRY_ID in $MAS_TOR1_LEFT_IDS; do')[1]
        retry = retry.split("done")[0]
        self.assertIn('mas upgrade "$MAS_RETRY_ID"', retry)
        self.assertNotIn("sudo", retry)

    def test_retry_is_not_a_loop_over_the_probe(self) -> None:
        """Exactly one retry pass: a fallback for a context mismatch, not a spin."""
        self.assertEqual(self.text.count("MAS_TOR1_LEFT_IDS="), 1)

    def test_outdated_id_extraction(self) -> None:
        listing = " 310633997  WhatsApp  (26.33.73 -> 26.34.72)\n6738511300  Copilot   (25.7.1 -> 25.7.2)\nSome noise line"
        # Sourcing update_appstore.sh would run the whole step, so the awk
        # contract the helper is built on is asserted directly.
        awk = subprocess.run(
            ["awk", "$1 ~ /^[0-9]+$/ { print $1 }"],
            input=listing, capture_output=True, text=True,
        )
        self.assertEqual(awk.stdout.split(), ["310633997", "6738511300"])


class VendorFactNotWarningTests(unittest.TestCase):
    """A permanent vendor fact must not be reported as a clearable warning."""

    def test_no_auto_updater_is_information(self) -> None:
        """IPMIView and DJI Assistant 2 ship no updater; that never changes.

        Reported as a warning, they degraded the internet step on every run for
        months — the same shape as Antigravity's 404 feed, demoted on 2026-08-26.
        A warning nobody can clear is a warning everybody learns to skip.
        """
        for rel in ("lib/internet_handlers.sh", "lib/internet_app_updates.sh"):
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn(
                'print_warn "$(internet_msg "$L_INTERNET_NO_AUTO_UPDATER"', text, rel
            )
            self.assertIn(
                'print_info "$(internet_msg "$L_INTERNET_NO_AUTO_UPDATER"', text, rel
            )


class RunSummaryCountsTests(unittest.TestCase):
    """"counts": {} in 26 consecutive summaries was a caller that never passed it."""

    def test_postupdate_writes_run_counts(self) -> None:
        text = (REPO_ROOT / "update_all.sh").read_text(encoding="utf-8")
        self.assertIn('"run_counts.json"', text)
        self.assertIn('"total_version_changes": updated_count', text)

    def test_summary_passes_counts(self) -> None:
        text = (REPO_ROOT / "update_all.sh").read_text(encoding="utf-8")
        self.assertIn("counts=counts,", text)

    def test_build_run_summary_keeps_counts(self) -> None:
        sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))
        from run_summary import build_run_summary  # noqa: E402

        summary = build_run_summary(
            start_time=0, end_time=10, overall_exit=0, degraded=0, blocking_exit=0,
            step_results={}, counts={"total_version_changes": 11},
        )
        self.assertEqual(summary["counts"], {"total_version_changes": 11})


if __name__ == "__main__":
    unittest.main()
