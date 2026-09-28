"""Omaha proof from the Chromium updater's structured history (2026-09-28 run log).

GoogleUpdater 156 and CometUpdater log the Omaha response on a line of its
own, below the ``[pid:tid:MMDD/HHMMSS...]`` prefix, so the text-log reader
never found a timestamp and Gemini, Google Drive and Comet came back
"launched, no recorded response" on every run — while
``updater_history.jsonl`` held a NO_UPDATE for all three from 14:10/14:40 the
same afternoon. These tests pin both readers.
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))

from vendor_feeds import omaha_history_status, omaha_recent_status  # noqa: E402

WIN_EPOCH_OFFSET = 11644473600


def _win_us(unix_seconds: float) -> str:
    return str(int((unix_seconds + WIN_EPOCH_OFFSET) * 1_000_000))


def _history(events: list[tuple[str, str, str, str]], started: float) -> str:
    """events: (appId, token, final_state, nextVersion) all in one updater process."""
    lines = []
    tokens = sorted({e[1] for e in events})
    for tok in tokens:
        lines.append(json.dumps({
            "bound": "START", "eventType": "UPDATER_PROCESS", "eventId": "0",
            "processToken": tok, "timestamp": _win_us(started),
        }))
    for i, (appid, tok, state, ver) in enumerate(events, start=5):
        lines.append(json.dumps({
            "appId": appid, "bound": "START", "eventType": "UPDATE",
            "eventId": str(i), "processToken": tok,
        }))
        lines.append(json.dumps({
            "bound": "END", "eventType": "UPDATE", "eventId": str(i),
            "processToken": tok, "result": "SUCCESS", "nextVersion": ver,
            "updateStates": [{"state": "CHECKING_FOR_UPDATES"}, {"state": state}],
        }))
    return "\n".join(lines) + "\n"


class OmahaHistoryStatusTests(unittest.TestCase):
    NOW = 1_790_609_000.0  # 2026-09-28 ~17:23 local

    def test_recent_noupdate_matching_installed_is_proof(self) -> None:
        text = _history([("com.google.geminimacos", "T1", "NO_UPDATE", "1.119.2.914")],
                        self.NOW - 3 * 3600)
        res = omaha_history_status(text, "com.google.geminimacos", ["1.119.2.914"], 6, now=self.NOW)
        self.assertIsNotNone(res)
        self.assertEqual(res[0], "noupdate")
        self.assertEqual(res[2], "1.119.2.914")
        expected = datetime.datetime.fromtimestamp(self.NOW - 3 * 3600).strftime("%H:%M")
        self.assertEqual(res[1], expected)

    def test_trailing_zero_components_compare_equal(self) -> None:
        """Drive registers 131.0.2.0 while its bundle says 131.0.2."""
        text = _history([("com.google.drivefs", "T1", "NO_UPDATE", "131.0.2.0")], self.NOW - 600)
        res = omaha_history_status(text, "com.google.drivefs", ["131.0", "131.0.2"], 6, now=self.NOW)
        self.assertEqual(res[0] if res else None, "noupdate")

    def test_stale_evidence_is_rejected(self) -> None:
        text = _history([("com.google.drivefs", "T1", "NO_UPDATE", "131.0.2.0")], self.NOW - 7 * 3600)
        self.assertIsNone(omaha_history_status(text, "com.google.drivefs", ["131.0.2"], 6, now=self.NOW))

    def test_version_mismatch_is_not_proof(self) -> None:
        """A NO_UPDATE for a build other than the installed one proves nothing."""
        text = _history([("com.google.geminimacos", "T1", "NO_UPDATE", "1.116.5.889")], self.NOW - 60)
        self.assertIsNone(
            omaha_history_status(text, "com.google.geminimacos", ["1.119.2.914"], 6, now=self.NOW))

    def test_latest_event_wins(self) -> None:
        older = _history([("com.google.chrome", "T1", "NO_UPDATE", "153.0.8010.53")], self.NOW - 5 * 3600)
        newer = _history([("com.google.chrome", "T2", "UPDATED", "154.0.8037.58")], self.NOW - 3600)
        res = omaha_history_status(older + newer, "com.google.chrome", ["154.0.8037.58"], 6, now=self.NOW)
        self.assertEqual(res[0] if res else None, "updated")

    def test_other_apps_and_garbage_are_ignored(self) -> None:
        text = "not json\n" + _history([("com.google.chrome", "T1", "NO_UPDATE", "154.0")], self.NOW - 60)
        self.assertIsNone(omaha_history_status(text, "com.google.drivefs", ["131.0"], 6, now=self.NOW))
        self.assertIsNone(omaha_history_status("", "com.google.chrome", ["154.0"], 6, now=self.NOW))

    def test_update_error_is_not_proof(self) -> None:
        text = _history([("ai.perplexity.comet", "T1", "UPDATE_ERROR", "153.0.8010.191")], self.NOW - 60)
        self.assertIsNone(
            omaha_history_status(text, "ai.perplexity.comet", ["153.0.8010.191"], 6, now=self.NOW))


class OmahaRecentStatusMultilineTests(unittest.TestCase):
    def test_response_on_line_after_prefix_is_timestamped(self) -> None:
        now = datetime.datetime(2026, 9, 28, 17, 38, 0)
        log = (
            "[29873:16872739:0928/141044.149349:VERBOSE2:components/update_client/"
            "request_sender.cc:151] Omaha response received: )]}'\n"
            '{"response":{"apps":[{"appid":"com.google.geminimacos","status":"ok",'
            '"updatecheck":{"status":"noupdate"}}]}}\n'
        )
        self.assertEqual(omaha_recent_status(log, "com.google.geminimacos", 6, now=now),
                         ("noupdate", "14:10"))


import stat  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402


def _bash(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)


COMMON = f"""
    source "{REPO_ROOT}/i18n/lang_en.sh"
    source "{REPO_ROOT}/lib/version.sh"
    source "{REPO_ROOT}/lib/internet_handlers.sh"
    _INTERNET_HANDLERS_DIR="{REPO_ROOT}/lib"
    print_header() {{ :; }}; print_info() {{ :; }}; print_step() {{ :; }}
    print_ok() {{ :; }}; print_warn() {{ :; }}
    internet_msg() {{ printf "$@"; }}
    run_with_timeout() {{ shift; "$@"; }}
"""


class OmahaHistoryShellTests(unittest.TestCase):
    def test_evaluate_uses_history_next_to_google_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "updater.log").write_text("", encoding="utf-8")
            Path(tmp, "updater_history.jsonl").write_text(
                _history([("com.google.drivefs", "T1", "NO_UPDATE", "131.0.2.0")], time.time() - 1800),
                encoding="utf-8")
            res = _bash(COMMON + f"""
                curl() {{ return 1; }}
                export MAC_UPDATE_GOOGLE_USER_LOG="/dev/null"
                export MAC_UPDATE_GOOGLE_SYS_LOG="{tmp}/updater.log"
                app_version() {{ echo "131.0"; }}
                app_build_version() {{ echo "131.0.2"; }}
                evaluate_omaha_status "Google Drive" "{tmp}/Google Drive.app" "" "com.google.drivefs"
                echo "STATUS=$INTERNET_LAST_STATUS"; echo "VERIFIED=$INTERNET_LAST_VERIFIED"
            """)
            self.assertIn("STATUS=✅ Up to date (vendor updater check at", res.stdout, res.stderr)
            self.assertIn("VERIFIED=1", res.stdout)

    def test_comet_recent_history_skips_wake(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            calls = Path(tmp, "calls")
            updater = Path(tmp, "CometUpdater")
            updater.write_text(f'#!/bin/bash\necho "$@" >> "{calls}"\n', encoding="utf-8")
            updater.chmod(updater.stat().st_mode | stat.S_IEXEC)
            Path(tmp, "updater.log").write_text("", encoding="utf-8")
            Path(tmp, "updater_history.jsonl").write_text(
                _history([("ai.perplexity.comet", "T1", "NO_UPDATE", "153.0.8010.191")], time.time() - 600),
                encoding="utf-8")
            Path(tmp, "Comet.app").mkdir()
            res = _bash(COMMON + f"""
                app_version() {{ echo "153.0.8010.191"; }}
                MAC_UPDATE_OMAHA_WAIT=1
                internet_handler_chromium_updater "Comet" "{tmp}/Comet.app" "{updater}" "{tmp}/updater.log" "ai.perplexity.comet"
                echo "STATUS=$INTERNET_LAST_STATUS"; echo "VERIFIED=$INTERNET_LAST_VERIFIED"
            """)
            self.assertIn("STATUS=✅ Up to date (vendor updater check at", res.stdout, res.stderr)
            self.assertIn("VERIFIED=1", res.stdout)
            self.assertFalse(calls.exists(), "updater must not be woken when history already proves current")

    def test_gemini_recent_history_skips_keystone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            calls = Path(tmp, "calls")
            Path(tmp, "updater.log").write_text("", encoding="utf-8")
            Path(tmp, "updater_history.jsonl").write_text(
                _history([("com.google.geminimacos", "T1", "NO_UPDATE", "1.119.2.914")], time.time() - 600),
                encoding="utf-8")
            Path(tmp, "Gemini.app").mkdir()
            res = _bash(COMMON + f"""
                source "{REPO_ROOT}/lib/internet_app_updates.sh" >/dev/null 2>&1
                _INTERNET_HANDLERS_DIR="{REPO_ROOT}/lib"
                print_header() {{ :; }}; print_info() {{ :; }}; print_step() {{ :; }}
                print_ok() {{ :; }}; print_warn() {{ :; }}
                export MAC_UPDATE_GOOGLE_USER_LOG="{tmp}/updater.log"
                export MAC_UPDATE_GOOGLE_SYS_LOG="/dev/null"
                app_version() {{ echo "1.119.2.914"; }}
                google_keystone_check() {{ echo called >> "{calls}"; return 0; }}
                eval "$(declare -f iu_gemini | sed 's|/Applications/Gemini.app|{tmp}/Gemini.app|g')"
                iu_gemini
                echo "STATUS=$STATUS_GEMINI"
            """)
            self.assertIn("STATUS=✅ Up to date (vendor updater check at", res.stdout, res.stderr)
            self.assertFalse(calls.exists(), "Keystone must not be woken when history already proves current")


if __name__ == "__main__":
    unittest.main()
