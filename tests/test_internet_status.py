"""Tests for internet status codes, counts, and summary filtering (T8)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))

from run_summary import collect_run_items


class InternetStatusTests(unittest.TestCase):
    def _run_bash_code_mapping(self, lang_file: str) -> None:
        script = f"""
set -e
REPO_ROOT="{REPO_ROOT}"
. "$REPO_ROOT/i18n/{lang_file}"
. "$REPO_ROOT/lib/internet_status.sh"

check() {{
    local expected="$1"
    local text="$2"
    local got
    got="$(internet_status_code "$text")"
    if [ "$got" != "$expected" ]; then
        echo "FAIL: expected '$expected' for '$text', got '$got'" >&2
        exit 1
    fi
}}

check "current_vendor" "$L_INTERNET_STATUS_VENDOR_NOUPDATE"
check "current_vendor" "$L_INTERNET_STATUS_CHECKED_CLI"
check "current_verified" "$L_INTERNET_STATUS_CURRENT"
check "current_verified" "$(printf "$L_INTERNET_STATUS_CURRENT_FMT" "1.2.3")"
check "current_verified" "$(printf "$L_INTERNET_STATUS_VENDOR_CURRENT_FMT" "1.2.3")"
check "updated" "$(printf "$L_INTERNET_STATUS_UPDATED_FMT" "1.2.0" "1.2.3")"
check "current_cask_only" "$L_INTERNET_STATUS_CASK_CURRENT"
check "rollout_hold" "$(printf "$L_INTERNET_STATUS_ROLLOUT_HOLD_FMT" "1.0" "1.1")"
check "update_available" "$(printf "$L_INTERNET_STATUS_UPDATE_AVAILABLE_FMT" "1.1")"
check "behind" "$(printf "$L_INTERNET_STATUS_BEHIND_FMT" "1.0" "1.1")"
check "behind" "$(printf "$L_INTERNET_STATUS_CASK_BEHIND_FMT" "1.0" "1.1")"
check "needs_restart" "$(printf "$L_INTERNET_STATUS_NEEDS_RESTART_FMT" "1.0" "1.1")"
check "feed_stale" "$(printf "$L_INTERNET_STATUS_FEED_STALE_FMT" "1.0" "1.1")"
check "unverified" "$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
check "unverified" "$L_INTERNET_STATUS_UPDATER_TRIGGERED"
check "unverified" "$L_INTERNET_STATUS_UPDATE_IN_PROGRESS"
check "managed_brew" "$L_INTERNET_STATUS_MANAGED_BREW"
check "managed_appstore" "$L_INTERNET_STATUS_MANAGED_APPSTORE"
check "manual" "$L_INTERNET_STATUS_MANUAL_UPDATE"
check "skipped" "$L_INTERNET_STATUS_SKIPPED"
check "error_hard" "$L_INTERNET_STATUS_INSTALL_ERROR"
check "error_hard" "$L_INTERNET_STATUS_MOUNT_ERROR"
check "error_hard" "$L_INTERNET_STATUS_EXTRACT_ERROR"
check "error_soft" "$L_INTERNET_STATUS_OFFLINE"
check "error_soft" "$L_INTERNET_STATUS_NO_URL"
check "error_soft" "$L_INTERNET_STATUS_DOWNLOAD_ERROR"
check "error_soft" "$L_INTERNET_STATUS_CHECK_MAU"
check "error_soft" "$L_INTERNET_STATUS_MAU_MISSING"
check "error_soft" "$L_INTERNET_STATUS_MAU_QUARANTINED"
check "error_soft" "$L_INTERNET_STATUS_MAU_OPENED"
check "error_soft" "$L_INTERNET_STATUS_UNKNOWN_VERSION"
check "error_soft" "$L_INTERNET_STATUS_CASK_MISSING"
check "error_soft" "$L_INTERNET_STATUS_LAUNCH_FAILED"
check "unknown" "completely unknown string"
"""
        proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"Bash mapping failed:\n{proc.stderr}\n{proc.stdout}")

    def test_status_code_mapping_en(self) -> None:
        self._run_bash_code_mapping("lang_en.sh")

    def test_status_code_mapping_pl(self) -> None:
        self._run_bash_code_mapping("lang_pl.sh")

    def test_counts_use_codes_not_substrings(self) -> None:
        script = f"""
set -e
REPO_ROOT="{REPO_ROOT}"
. "$REPO_ROOT/i18n/lang_en.sh"
. "$REPO_ROOT/lib/internet_status.sh"

_cnt_verified=0
_cnt_behind=0
_cnt_unverified=0

add_status() {{
    local st="$1"
    local code
    code="$(internet_status_code "$st")"
    case "$code" in
        current_verified|current_vendor|updated)
            _cnt_verified=$((_cnt_verified + 1))
            ;;
        behind|needs_restart)
            _cnt_behind=$((_cnt_behind + 1))
            ;;
        unverified)
            _cnt_unverified=$((_cnt_unverified + 1))
            ;;
    esac
}}

# Verified
add_status "$L_INTERNET_STATUS_VENDOR_NOUPDATE"
add_status "$L_INTERNET_STATUS_CURRENT"
add_status "$(printf "$L_INTERNET_STATUS_UPDATED_FMT" "1.0" "1.1")"

# Behind
add_status "$(printf "$L_INTERNET_STATUS_BEHIND_FMT" "1.0" "1.2")"
add_status "$(printf "$L_INTERNET_STATUS_NEEDS_RESTART_FMT" "1.0" "1.2")"

# Unverified
add_status "$L_INTERNET_STATUS_UPDATER_TRIGGERED"

# Non-counting statuses: rollout_hold, current_cask_only, skipped, etc.
add_status "$(printf "$L_INTERNET_STATUS_ROLLOUT_HOLD_FMT" "1.0" "1.2")"
add_status "$L_INTERNET_STATUS_CASK_CURRENT"
add_status "$L_INTERNET_STATUS_SKIPPED"

printf "%d %d %d\n" "$_cnt_verified" "$_cnt_behind" "$_cnt_unverified"
"""
        proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "3 2 1")

    def test_behind_sets_soft_failure(self) -> None:
        script = f"""
set -e
REPO_ROOT="{REPO_ROOT}"
. "$REPO_ROOT/i18n/lang_en.sh"
. "$REPO_ROOT/lib/internet_status.sh"

check_soft() {{
    local text="$1"
    local expected="$2"
    local INTERNET_SOFT_FAIL=0
    local code
    code="$(internet_status_code "$text")"
    case "$code" in
        behind|needs_restart|feed_stale)
            INTERNET_SOFT_FAIL=1
            ;;
    esac
    if [ "$INTERNET_SOFT_FAIL" != "$expected" ]; then
        echo "FAIL for '$code': expected INTERNET_SOFT_FAIL=$expected, got $INTERNET_SOFT_FAIL" >&2
        exit 1
    fi
}}

check_soft "$(printf "$L_INTERNET_STATUS_BEHIND_FMT" "1.0" "2.0")" "1"
check_soft "$(printf "$L_INTERNET_STATUS_NEEDS_RESTART_FMT" "1.0" "2.0")" "1"
check_soft "$(printf "$L_INTERNET_STATUS_FEED_STALE_FMT" "1.0" "2.0")" "1"
check_soft "$(printf "$L_INTERNET_STATUS_ROLLOUT_HOLD_FMT" "1.0" "2.0")" "0"
check_soft "$L_INTERNET_STATUS_CASK_CURRENT" "0"
check_soft "$L_INTERNET_STATUS_CURRENT" "0"
"""
        proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_summary_hides_uninstalled_rows(self) -> None:
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            installed_app = tmp_dir / "InstalledApp.app"
            installed_app.mkdir()

            script = f"""
set -e
REPO_ROOT="{REPO_ROOT}"
. "$REPO_ROOT/i18n/lang_en.sh"
. "$REPO_ROOT/lib/internet_status.sh"

internet_app_path() {{
    case "$1" in
        "InstalledApp") echo "{installed_app}" ;;
        "UninstalledApp") echo "{tmp_dir / 'UninstalledApp.app'}" ;;
        *) echo "" ;;
    esac
}}

internet_summary_section "SECTION ONE"
internet_summary_row "Uninstalled App:" "status_foo" "UninstalledApp"

internet_summary_section "SECTION TWO"
internet_summary_row "Installed App:" "status_ok" "InstalledApp"
internet_summary_end
"""
            proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = proc.stdout
            self.assertNotIn("SECTION ONE", out)
            self.assertNotIn("Uninstalled App", out)
            self.assertIn("SECTION TWO", out)
            self.assertIn("Installed App:", out)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_run_summary_reads_status_codes(self) -> None:
        tmp_sdir = Path(tempfile.mkdtemp())
        try:
            behind_file = tmp_sdir / "internet_behind_apps.txt"
            behind_file.write_text("Docker Desktop|4.91.0|4.92.0\n", encoding="utf-8")

            codes_file = tmp_sdir / "internet_status_codes.txt"
            codes_file.write_text(
                "Docker Desktop|behind|⚠️  Behind: 4.91.0 < 4.92.0 (vendor)\n"
                "ChatGPT / Codex|needs_restart|⚠️  Update 26.917.51856 → 26.917.62051 pending — quit the app so its updater can install it\n"
                "Google Chrome|rollout_hold|ℹ️  Vendor rollout: 153.0.8010.53 installed, 154.0.8037.58 public — not offered to this Mac yet\n"
                "Warp|feed_stale|⚠️  Vendor feed stale (feed 0.2024.12.18.08.02.00 < installed 0.2026.09.16.08.27.02)\n"
                "Antigravity|update_available|⚠️  Update available: 2.16.0\n",
                encoding="utf-8",
            )

            items = collect_run_items(tmp_sdir, step_results=None)
            # Docker Desktop should be present once (from internet_behind_apps.txt), not duplicated
            docker_items = [it for it in items if it["name"] == "Docker Desktop"]
            self.assertEqual(len(docker_items), 1)

            chatgpt_items = [it for it in items if "ChatGPT" in it["name"]]
            self.assertEqual(len(chatgpt_items), 1)
            self.assertEqual(chatgpt_items[0]["status"], "pending")
            self.assertIn("quit the app so its updater can install it", chatgpt_items[0]["details"])

            chrome_items = [it for it in items if "Chrome" in it["name"]]
            self.assertEqual(len(chrome_items), 1)
            self.assertEqual(chrome_items[0]["status"], "pending")
            self.assertIn("vendor staged rollout (public 154.0.8037.58)", chrome_items[0]["details"])

            warp_items = [it for it in items if "Warp" in it["name"]]
            self.assertEqual(len(warp_items), 1)
            self.assertEqual(warp_items[0]["status"], "pending")

            antigravity_items = [it for it in items if it["name"] == "Antigravity"]
            self.assertEqual(len(antigravity_items), 1)
            self.assertEqual(antigravity_items[0]["status"], "pending")
        finally:
            shutil.rmtree(tmp_sdir, ignore_errors=True)

    def test_stale_days_does_not_override_verified_statuses(self) -> None:
        """When an app has a verified status, stale days check does not override it."""
        from tests._env import shell_env
        script = f"""
REPO_ROOT="{REPO_ROOT}"
. "$REPO_ROOT/i18n/lang_en.sh"
. "$REPO_ROOT/lib/internet_i18n.sh"
. "$REPO_ROOT/lib/internet_status.sh"

internet_get_app_days_unchanged() {{ echo 99; }}
STATUS_CURSOR="$(printf "$L_INTERNET_STATUS_VENDOR_CURRENT_FMT" "0.45.0")"
SCRIPT_DIR="$REPO_ROOT"
MAC_UPDATE_STALE_DAYS=45

# Run the snippet from update_internet_apps.sh
eval "$(sed -n '/# ── Stale Days Warning/,/done < "\\$SCRIPT_DIR\\/config\\/internet_app_methods.txt"/p' "$REPO_ROOT/update_internet_apps.sh")"

echo "STATUS_CURSOR=$STATUS_CURSOR"
"""
        proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=shell_env())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("vendor feed", proc.stdout)
        self.assertNotIn("unchanged for 99 days", proc.stdout)


if __name__ == "__main__":
    unittest.main()
