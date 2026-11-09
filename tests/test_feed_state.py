#!/usr/bin/env python3
"""Vendor feed diagnostics and persistent feed state (2026-11-08 run follow-up).

P1-1  feed fetch failures are diagnosable, a fresh cached proof avoids a blind
      launch, and an unusable feed is reported as feed_unreachable (soft).
P1-2  a vendor feed that falls below a version the vendor already published is a
      feed regression (high-water mark), not a stale-feed warning.
P1-3  Google Drive's Omaha history proof: refusals are logged with their reason,
      and the system-scope GoogleUpdater (where Drive is registered) is woken.
P1-10 registry labels say what actually runs.
P2-2  status marks are not doubled.
P2-6  sha512b64 is computed in chunks.
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

try:
    from ._env import shell_env
except ImportError:
    from _env import shell_env

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))

import feed_state as fs  # noqa: E402
from vendor_feeds import omaha_history_explain, omaha_history_status  # noqa: E402

HANDLER_PRELUDE = f"""
. "{REPO_ROOT}/i18n/lang_en.sh"
. "{REPO_ROOT}/lib/version.sh"
. "{REPO_ROOT}/lib/internet_i18n.sh"
. "{REPO_ROOT}/lib/vendor_feeds.sh"
. "{REPO_ROOT}/lib/vendor_direct.sh"
. "{REPO_ROOT}/lib/internet_handlers.sh"
. "{REPO_ROOT}/lib/internet_status.sh"
print_ok() {{ echo "OK:$*"; }}
print_info() {{ :; }}
print_warn() {{ echo "WARN:$*"; }}
print_step() {{ :; }}
vendor_appcast_published_channel() {{ return 1; }}
internet_app_bundle_id() {{ echo com.example.app; }}
internet_app_is_running() {{ return 1; }}
"""


class FeedStateModuleTests(unittest.TestCase):
    NOW = 1_800_000_000.0

    def test_record_success_tracks_last_ok_and_high_water(self) -> None:
        st = fs.empty_state()
        fs.record_success(st, "Proton Mail", "1.16.1", self.NOW)
        fs.record_success(st, "Proton Mail", "1.16.0", self.NOW + 60)
        entry = st["apps"]["Proton Mail"]
        self.assertEqual(entry["last_ok_version"], "1.16.0")
        self.assertEqual(entry["high_water_version"], "1.16.1")
        self.assertEqual(entry["high_water_at"], int(self.NOW))

    def test_record_failure_keeps_good_observation(self) -> None:
        st = fs.empty_state()
        fs.record_success(st, "OpenCode", "1.19.5", self.NOW)
        fs.record_failure(st, "OpenCode", "fetch", self.NOW + 10)
        self.assertEqual(st["apps"]["OpenCode"]["last_ok_version"], "1.19.5")
        self.assertEqual(st["apps"]["OpenCode"]["last_error"], "fetch")
        fs.record_success(st, "OpenCode", "1.19.5", self.NOW + 20)
        self.assertNotIn("last_error", st["apps"]["OpenCode"])

    def test_cached_proof_fresh_stale_and_mismatch(self) -> None:
        st = fs.empty_state()
        fs.record_success(st, "A", "2.0", self.NOW)
        fresh = fs.cached_proof(st, "A", "2.0.0", 24, self.NOW + 3 * 3600)
        self.assertIsNotNone(fresh)
        self.assertEqual(fs.format_age_h(fresh["age_h"]), "3")
        self.assertIsNone(fs.cached_proof(st, "A", "2.0", 24, self.NOW + 25 * 3600), "stale")
        self.assertIsNone(fs.cached_proof(st, "A", "2.1", 24, self.NOW + 60), "other version")
        self.assertIsNone(fs.cached_proof(st, "A", "2.0", 0, self.NOW + 60), "TTL 0 disables")
        self.assertIsNone(fs.cached_proof(st, "A", "2.0", 24, self.NOW - 60), "future observation")
        self.assertIsNone(fs.cached_proof(st, "B", "2.0", 24, self.NOW), "unknown app")

    def test_high_water_covers(self) -> None:
        st = fs.empty_state()
        fs.record_success(st, "A", "1.16.1", self.NOW)
        self.assertEqual(fs.high_water_covers(st, "A", "1.16.1")["version"], "1.16.1")
        self.assertEqual(fs.high_water_covers(st, "A", "1.16.0")["version"], "1.16.1")
        self.assertIsNone(fs.high_water_covers(st, "A", "1.17.0"))

    def test_clamp_ttl(self) -> None:
        self.assertEqual(fs.clamp_ttl("x"), 24.0)
        self.assertEqual(fs.clamp_ttl("-5"), 0.0)
        self.assertEqual(fs.clamp_ttl("999"), 168.0)
        self.assertEqual(fs.clamp_ttl("6"), 6.0)
        self.assertEqual(fs.clamp_ttl("nan"), 24.0)

    def test_save_is_atomic_private_and_load_tolerates_garbage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "feed_state.json"
            st = fs.record_success(fs.empty_state(), "A", "1.0", self.NOW)
            fs.save_state(path, st)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(fs.load_state(path)["apps"]["A"]["last_ok_version"], "1.0")
            self.assertEqual([p.name for p in path.parent.iterdir()], ["feed_state.json"])
            path.write_text("{not json", encoding="utf-8")
            self.assertEqual(fs.load_state(path), fs.empty_state())
            path.write_text(json.dumps({"format": 99, "apps": {}}), encoding="utf-8")
            self.assertEqual(fs.load_state(path), fs.empty_state())
            self.assertEqual(fs.load_state(Path(tmp) / "missing.json"), fs.empty_state())


@unittest.skipUnless(shutil.which("bash"), "bash required")
class VendorFeedFailureHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="mac_update_feedstate_")
        self.state = os.path.join(self.tmp, "state", "feed_state.json")
        self.session = os.path.join(self.tmp, "session")
        os.mkdir(self.session)
        self.launch_log = os.path.join(self.tmp, "launch.log")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _seed(self, app: str, version: str, age_h: float) -> None:
        st = fs.record_success(fs.empty_state(), app, version, time.time() - age_h * 3600)
        fs.save_state(self.state, st)

    def _run(self, lookup: str, installed: str = "1.19.5", extra: str = "") -> subprocess.CompletedProcess:
        script = HANDLER_PRELUDE + f"""
app_version() {{ echo "{installed}"; }}
silent_launch_app() {{ echo "$@" >> "{self.launch_log}"; return 0; }}
{lookup}
{extra}
internet_handler_vendor_truth "OpenCode" "{self.tmp}/OpenCode.app" "OpenCode"
echo "STATUS=$INTERNET_LAST_STATUS"
echo "CODE=$(internet_status_code "$INTERNET_LAST_STATUS")"
echo "VERIFIED=$INTERNET_LAST_VERIFIED"
"""
        env = shell_env(MAC_UPDATE_FEED_STATE_FILE=self.state, MAC_UPDATE_SESSION_DIR=self.session)
        proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc

    def test_fetch_failure_with_fresh_cached_proof_reports_current_without_launch(self) -> None:
        self._seed("OpenCode", "1.19.5", age_h=2)
        proc = self._run("vendor_feed_lookup() { return 2; }")
        self.assertIn("CODE=current_cached", proc.stdout)
        self.assertIn("cached vendor check 2 h ago", proc.stdout)
        self.assertIn("VERIFIED=0", proc.stdout)
        self.assertIn("OK:Up to date per cached", proc.stdout)
        self.assertFalse(os.path.exists(self.launch_log), "cached proof must not launch the app")
        diag = Path(self.session, "internet_diag.txt").read_text(encoding="utf-8")
        self.assertIn("cached proof 1.19.5", diag)
        self.assertEqual(fs.load_state(self.state)["apps"]["OpenCode"]["last_error"], "fetch")

    def test_fetch_failure_with_stale_cache_is_feed_unreachable_and_launches(self) -> None:
        self._seed("OpenCode", "1.19.5", age_h=30)
        proc = self._run("vendor_feed_lookup() { return 2; }")
        self.assertIn("CODE=feed_unreachable", proc.stdout)
        self.assertIn("STATUS=⏳ Vendor feed unreachable", proc.stdout)
        self.assertIn("WARN:Vendor feed for OpenCode unreachable", proc.stdout)
        self.assertTrue(os.path.exists(self.launch_log), "native-updater fallback must still run")

    def test_fetch_failure_with_cache_for_other_version_is_not_proof(self) -> None:
        self._seed("OpenCode", "1.19.4", age_h=1)
        proc = self._run("vendor_feed_lookup() { return 2; }")
        self.assertIn("CODE=feed_unreachable", proc.stdout)

    def test_fetch_failure_without_cache_is_feed_unreachable(self) -> None:
        proc = self._run("vendor_feed_lookup() { return 2; }")
        self.assertIn("CODE=feed_unreachable", proc.stdout)
        self.assertTrue(os.path.exists(self.launch_log))
        self.assertEqual(fs.load_state(self.state)["apps"]["OpenCode"]["last_error"], "fetch")

    def test_parse_failure_is_feed_unreadable(self) -> None:
        proc = self._run("vendor_feed_lookup() { return 3; }")
        self.assertIn("CODE=feed_unreachable", proc.stdout)
        self.assertIn("STATUS=⏳ Vendor feed unreadable", proc.stdout)
        self.assertIn("returned no usable version", proc.stdout)

    def test_cache_ttl_env_zero_disables_cached_proof(self) -> None:
        self._seed("OpenCode", "1.19.5", age_h=1)
        proc = self._run("vendor_feed_lookup() { return 2; }", extra="export MAC_UPDATE_FEED_CACHE_TTL_H=0")
        self.assertIn("CODE=feed_unreachable", proc.stdout)

    def test_successful_lookup_records_state(self) -> None:
        proc = self._run('vendor_feed_lookup() { echo "1.19.5|-|-|-|zip|github.com|eligible"; }')
        self.assertIn("CODE=current_verified", proc.stdout)
        entry = fs.load_state(self.state)["apps"]["OpenCode"]
        self.assertEqual(entry["last_ok_version"], "1.19.5")
        self.assertEqual(entry["high_water_version"], "1.19.5")

    def test_dry_run_never_writes_state(self) -> None:
        self._run('vendor_feed_lookup() { echo "1.19.5|-|-|-|zip|github.com|eligible"; }',
                  extra="export MAC_UPDATE_DRY_RUN=1")
        self.assertFalse(os.path.exists(self.state))

    def test_high_water_mark_turns_feed_regression_into_current(self) -> None:
        # 2026-11-06 the vendor listed 1.16.1; 2026-11-08 the feed listed 1.16.0.
        self._seed("OpenCode", "1.16.1", age_h=48)
        proc = self._run('vendor_feed_lookup() { echo "1.16.0|-|-|-|dmg|proton.me|eligible"; }', installed="1.16.1")
        self.assertIn("CODE=current_feed_regressed", proc.stdout)
        self.assertIn("feed now lists 1.16.0", proc.stdout)
        self.assertNotIn("WARN:", proc.stdout)
        self.assertFalse(os.path.exists(self.launch_log))
        entry = fs.load_state(self.state)["apps"]["OpenCode"]
        self.assertEqual(entry["high_water_version"], "1.16.1")
        self.assertEqual(entry["last_ok_version"], "1.16.0")

    def test_stale_feed_without_high_water_still_warns(self) -> None:
        proc = self._run('vendor_feed_lookup() { echo "1.16.0|-|-|-|dmg|proton.me|eligible"; }', installed="1.16.1")
        self.assertIn("CODE=feed_stale", proc.stdout)
        self.assertIn("WARN:Vendor feed stale", proc.stdout)
        self.assertNotIn("WARN:⚠️", proc.stdout, "status mark must not be doubled")


@unittest.skipUnless(shutil.which("bash"), "bash required")
class VendorFeedFetchDiagnosticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="mac_update_feedfetch_")
        self.session = os.path.join(self.tmp, "session")
        os.mkdir(self.session)
        self.args = os.path.join(self.tmp, "curl_args")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _lookup(self, curl_body: str) -> tuple[subprocess.CompletedProcess, str]:
        script = f"""
. "{REPO_ROOT}/lib/internet_i18n.sh"
. "{REPO_ROOT}/lib/vendor_feeds.sh"
curl() {{ echo "$@" > "{self.args}"; {curl_body} }}
vendor_feed_lookup "OpenCode"
echo "RC=$?"
"""
        env = shell_env(MAC_UPDATE_SESSION_DIR=self.session)
        proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env)
        diag_path = Path(self.session, "internet_diag.txt")
        return proc, diag_path.read_text(encoding="utf-8") if diag_path.exists() else ""

    def test_http_error_is_a_fetch_failure_with_code_and_status(self) -> None:
        proc, diag = self._lookup('echo "<html>busy</html>"; echo "VFMETA 503 15.002" >&2; return 0;')
        self.assertIn("RC=2", proc.stdout)
        self.assertIn("Vendor feed OpenCode: fetch FAILED (curl=22 http=503 time=15.002s", diag)
        self.assertIn("host=github.com", diag)

    def test_network_error_records_curl_exit_and_message(self) -> None:
        proc, diag = self._lookup('echo "curl: (6) Could not resolve host: github.com" >&2; '
                                  'echo "VFMETA 000 0.01" >&2; return 6;')
        self.assertIn("RC=2", proc.stdout)
        self.assertIn("curl=6 http=000", diag)
        self.assertIn("Could not resolve host", diag)

    def test_parse_failure_is_distinct_from_fetch_failure(self) -> None:
        proc, diag = self._lookup('echo "not yaml at all"; echo "VFMETA 200 0.3" >&2; return 0;')
        self.assertIn("RC=3", proc.stdout)
        self.assertIn("fetch ok (curl=0 http=200", diag)
        self.assertIn("parse FAILED (kind=yml", diag)

    def test_success_and_hardened_flags(self) -> None:
        body = "version: 1.19.5\\nfiles:\\n  - url: OpenCode-1.19.5-arm64.zip\\n    sha512: abc\\npath: OpenCode-1.19.5-arm64.zip\\n"
        proc, diag = self._lookup(f'printf "{body}"; echo "VFMETA 200 0.2" >&2; return 0;')
        self.assertIn("RC=0", proc.stdout)
        self.assertTrue(proc.stdout.startswith("1.19.5|"), proc.stdout)
        args = Path(self.args).read_text(encoding="utf-8")
        for flag in ("--proto =https", "--proto-redir =https", "--retry-all-errors", "--max-filesize"):
            self.assertIn(flag, args)

    def test_system_curl_supports_retry_all_errors(self) -> None:
        curl = shutil.which("curl")
        if not curl:
            self.skipTest("curl not installed")
        out = subprocess.run([curl, "--help", "all"], capture_output=True, text=True).stdout
        self.assertIn("--retry-all-errors", out)


def _history(app_ts_unix: float, version: str, state: str = "NO_UPDATE", appid: str = "com.google.drivefs") -> str:
    win_us = int((app_ts_unix + 11644473600) * 1_000_000)
    lines = [
        {"eventType": "UPDATER_PROCESS", "bound": "START", "processToken": "T", "timestamp": str(win_us), "scope": "SYSTEM"},
        {"eventType": "UPDATE", "bound": "START", "processToken": "T", "eventId": "6", "appId": appid},
        {"eventType": "UPDATE", "bound": "END", "processToken": "T", "eventId": "6", "nextVersion": version,
         "updateStates": [{"state": "CHECKING_FOR_UPDATES"}, {"state": state}]},
    ]
    return "\n".join(json.dumps(x) for x in lines) + "\n"


class GoogleDriveProofTests(unittest.TestCase):
    """2026-11-08: Drive (133.0 / build 133.0.2, history 133.0.2.0) was refused
    because the newest system-scope check was 14 h old after the Mac slept."""

    def test_drive_build_with_trailing_zero_is_accepted_when_recent(self) -> None:
        now = time.time()
        res = omaha_history_status(_history(now - 3600, "133.0.2.0"), "com.google.drivefs", ["133.0", "133.0.2"], 6.0, now)
        self.assertIsNotNone(res)
        self.assertEqual(res[0], "noupdate")

    def test_refusal_reasons(self) -> None:
        now = time.time()
        ex = omaha_history_explain(_history(now - 14.3 * 3600, "133.0.2.0"), "com.google.drivefs", ["133.0", "133.0.2"], 6.0, now)
        self.assertIsNone(ex["proof"])
        self.assertEqual(ex["reason"], "too_old")
        self.assertEqual(ex["version"], "133.0.2.0")
        ex = omaha_history_explain(_history(now - 3600, "134.0.0.0"), "com.google.drivefs", ["133.0", "133.0.2"], 6.0, now)
        self.assertEqual(ex["reason"], "version_mismatch", "a NO_UPDATE for another build is never proof")
        ex = omaha_history_explain(_history(now - 3600, "133.0.2.0", appid="other"), "com.google.drivefs", ["133.0.2"], 6.0, now)
        self.assertEqual(ex["reason"], "no_event_for_app")
        ex = omaha_history_explain(_history(now - 3600, "133.0.2.0", state="UPDATE_ERROR"), "com.google.drivefs", ["133.0.2"], 6.0, now)
        self.assertEqual(ex["reason"], "outcome_not_proof")
        self.assertEqual(omaha_history_explain("", "x", [])["reason"], "no_history")

    @unittest.skipUnless(shutil.which("bash"), "bash required")
    def test_refused_proof_is_logged_to_internet_diag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            gdir = Path(tmp) / "GoogleUpdater"
            gdir.mkdir()
            (gdir / "updater_history.jsonl").write_text(_history(time.time() - 14 * 3600, "133.0.2.0"), encoding="utf-8")
            session = Path(tmp) / "session"
            session.mkdir()
            script = f"""
. "{REPO_ROOT}/i18n/lang_en.sh"
. "{REPO_ROOT}/lib/internet_i18n.sh"
. "{REPO_ROOT}/lib/version.sh"
. "{REPO_ROOT}/lib/internet_handlers.sh"
app_version() {{ echo 133.0; }}
app_build_version() {{ echo 133.0.2; }}
omaha_history_proof com.google.drivefs "{tmp}/Google Drive.app" "{gdir}/updater.log" && echo PROVEN || echo REFUSED
"""
            proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                                  env=shell_env(MAC_UPDATE_SESSION_DIR=str(session)))
            self.assertIn("REFUSED", proc.stdout, proc.stderr)
            diag = (session / "internet_diag.txt").read_text(encoding="utf-8")
            self.assertIn("Omaha history proof refused for com.google.drivefs: reason=too_old", diag)
            self.assertIn("version=133.0.2.0", diag)
            self.assertIn("installed=133.0/133.0.2", diag)

    @unittest.skipUnless(shutil.which("bash"), "bash required")
    def test_keystone_check_also_wakes_the_system_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            calls = Path(tmp) / "calls.log"
            stubs = {}
            for scope in ("user", "sys"):
                stub = Path(tmp) / f"{scope}_GoogleUpdater"
                stub.write_text(f'#!/bin/sh\necho "{scope} $*" >> "{calls}"\nexit 0\n', encoding="utf-8")
                stub.chmod(0o755)
                stubs[scope] = stub
            script = f"""
export HOME="{tmp}"
export MAC_UPDATE_GOOGLE_USER_UPDATER="{stubs['user']}"
export MAC_UPDATE_GOOGLE_SYS_UPDATER="{stubs['sys']}"
. "{REPO_ROOT}/i18n/lang_en.sh"
. "{REPO_ROOT}/lib/version.sh"
. "{REPO_ROOT}/lib/proc.sh"
. "{REPO_ROOT}/lib/internet_i18n.sh"
. "{REPO_ROOT}/lib/vendor_feeds.sh"
. "{REPO_ROOT}/lib/internet_handlers.sh"
. "{REPO_ROOT}/lib/internet_app_updates.sh"
_LIB_DIR="{REPO_ROOT}/lib"
MAC_UPDATE_OMAHA_WAIT=0
google_keystone_check "" "com.google.drivefs"
echo "RC=$?"
"""
            proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=shell_env())
            self.assertIn("RC=0", proc.stdout, proc.stderr)
            log = calls.read_text(encoding="utf-8").splitlines()
            self.assertIn("user --wake-all", log)
            self.assertIn("sys --wake-all --system", log)


@unittest.skipUnless(shutil.which("bash"), "bash required")
class StatusClassificationTests(unittest.TestCase):
    def _codes(self, lang: str) -> dict[str, str]:
        script = f"""
. "{REPO_ROOT}/i18n/lang_{lang}.sh"
. "{REPO_ROOT}/lib/internet_status.sh"
for s in "$(printf "$L_INTERNET_STATUS_FEED_CACHED_CURRENT_FMT" 3 1.2.3)" \\
         "$(printf "$L_INTERNET_STATUS_FEED_REGRESSED_FMT" 1.16.1 1.16.1 1.16.0)" \\
         "$L_INTERNET_STATUS_FEED_UNREACHABLE" "$L_INTERNET_STATUS_FEED_UNREADABLE" \\
         "$(printf "$L_INTERNET_STATUS_VENDOR_CURRENT_FMT" 1.2.3)" \\
         "$(printf "$L_INTERNET_STATUS_FEED_STALE_FMT" 1.0 2.0)"; do
    echo "$(internet_status_code "$s")"
done
"""
        out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=shell_env()).stdout.split()
        return dict(zip(["cached", "regressed", "unreachable", "unreadable", "vendor", "stale"], out))

    def test_new_codes_in_every_language(self) -> None:
        for lang in ("en", "pl", "es", "it", "pt", "de", "fr"):
            with self.subTest(lang=lang):
                self.assertEqual(self._codes(lang), {
                    "cached": "current_cached",
                    "regressed": "current_feed_regressed",
                    "unreachable": "feed_unreachable",
                    "unreadable": "feed_unreachable",
                    "vendor": "current_verified",
                    "stale": "feed_stale",
                })

    def test_status_body_strips_one_mark(self) -> None:
        script = f"""
. "{REPO_ROOT}/lib/internet_handlers.sh"
for s in "✅ Up to date (1.0)" "⚠️  Vendor feed stale" "⏳ Launched" "plain" "ℹ️  Vendor rollout"; do
    printf '[%s]\\n' "$(internet_status_body "$s")"
done
"""
        out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=shell_env()).stdout
        self.assertEqual(out.splitlines(), ["[Up to date (1.0)]", "[Vendor feed stale]", "[Launched]", "[plain]", "[Vendor rollout]"])

    def test_cask_current_is_capitalised(self) -> None:
        for lang in ("en", "pl", "es", "it", "pt", "de", "fr"):
            text = (REPO_ROOT / "i18n" / f"lang_{lang}.sh").read_text(encoding="utf-8")
            line = next(ln for ln in text.splitlines() if ln.startswith("L_INTERNET_STATUS_CASK_CURRENT="))
            first = line.split('"')[1].split(" ", 1)[1][0]
            self.assertTrue(first.isupper(), f"{lang}: {line}")


class RunSummaryClassificationTests(unittest.TestCase):
    def test_feed_unreachable_is_unconfirmed_and_cached_codes_are_informational(self) -> None:
        from run_summary import collect_run_items, degraded_is_warnings_only
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "internet_status_codes.txt").write_text(
                "OpenCode|feed_unreachable|⏳ Vendor feed unreachable — app's own updater launched (unverified)\n"
                "Superset|current_cached|✅ Up to date per cached vendor check 2 h ago (1.0; feed unreachable now)\n"
                "Proton Mail|current_feed_regressed|✅ Up to date — vendor feed regressed (installed 1.16.1, ...)\n",
                encoding="utf-8")
            items = collect_run_items(p, step_results={"internet": {"code": "warn"}})
            names = {it["name"]: it for it in items}
            self.assertEqual(names["OpenCode"]["status"], "unconfirmed")
            self.assertNotIn("Superset", names)
            self.assertNotIn("Proton Mail", names)
            self.assertNotIn("Step: Internet apps", names, "known codes must not be 'unexplained'")
            (p / "step_status_codes.txt").write_text("internet=warn\n", encoding="utf-8")
            self.assertFalse(degraded_is_warnings_only(p), "feed_unreachable is actionable")


@unittest.skipUnless(shutil.which("bash"), "bash required")
class RegistryLabelTests(unittest.TestCase):
    def _methods(self) -> dict[str, str]:
        rows = {}
        for ln in (REPO_ROOT / "config" / "internet_app_methods.txt").read_text(encoding="utf-8").splitlines():
            ln = ln.split("#", 1)[0].strip()
            if ln:
                parts = ln.split("|")
                rows[parts[0]] = parts[1]
        return rows

    def test_labels_match_what_runs(self) -> None:
        rows = self._methods()
        self.assertEqual(rows["Firefox Developer Edition"], "mozilla_dmg")
        # IPMIView on Apple Silicon is the App Store iPad build (Wrapper/iTunesMetadata.plist).
        self.assertEqual(rows["IPMIView"], "appstore_gui")

    def test_effective_method_follows_vendor_feed_rows(self) -> None:
        script = f"""
SCRIPT_DIR="{REPO_ROOT}"
. "{REPO_ROOT}/lib/vendor_feeds.sh"
. "{REPO_ROOT}/lib/internet_registry.sh"
for pair in "ChatGPT / Codex|silent_launch" "Cursor|silent_launch" "Docker Desktop|docker_cli" \\
            "Proton Drive|sparkle_appcast" "MEGAsync|silent_launch" "KeePassXC|github_dmg"; do
    internet_effective_method "${{pair%%|*}}" "${{pair#*|}}"
done
"""
        out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=shell_env()).stdout.split("\n")
        self.assertEqual(out[:6], ["vendor_feed", "vendor_feed", "vendor_feed", "vendor_feed", "silent_launch", "github_dmg"])


@unittest.skipUnless(shutil.which("bash"), "bash required")
class StreamingChecksumTests(unittest.TestCase):
    def test_sha512b64_multi_chunk_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "artifact.zip"
            data = os.urandom(1024) * (3 * 1024 + 7)  # ~3 MiB: several 1 MiB chunks + tail
            f.write_bytes(data)
            good = base64.b64encode(hashlib.sha512(data).digest()).decode("ascii")
            bad = base64.b64encode(hashlib.sha512(data + b"x").digest()).decode("ascii")
            script = f"""
. "{REPO_ROOT}/lib/vendor_direct.sh"
vendor_direct_verify_checksum "{f}" sha512b64 "{good}"; echo "GOOD=$?"
vendor_direct_verify_checksum "{f}" sha512b64 "{bad}"; echo "BAD=$?"
"""
            out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=shell_env()).stdout
            self.assertIn("GOOD=0", out)
            self.assertIn("BAD=1", out)

    def test_sha512b64_does_not_read_whole_file(self) -> None:
        text = (REPO_ROOT / "lib" / "vendor_direct.sh").read_text(encoding="utf-8")
        block = text.split("sha512b64)", 1)[1].split(";;", 1)[0]
        self.assertNotIn("'rb').read()", block)
        self.assertIn("fh.read(1048576)", block)


if __name__ == "__main__":
    unittest.main()
