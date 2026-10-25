"""Regressions for the 2026-10-25 run log.

Covers: App Store Track 2 false negative (honest `not_offered` branch, robust
AppleScript, id validation, Track-2-only prompt), Proton Drive gradual-rollout
cross-check against the app's Sparkle appcast, warnings-only final banner,
localized step/summary strings, and profile backups only when content changes.
"""
from __future__ import annotations

import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import shell_env  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))

from run_summary import classify_step_status, degraded_is_warnings_only  # noqa: E402
from vendor_feeds import (  # noqa: E402
    appcast_publishes_installed,
    appcast_url_allowed,
    sparkle_appcast_items,
)

LANGS = ("en", "pl", "es", "it", "pt", "de", "fr")

APPCAST = """<?xml version="1.0" standalone="yes"?>
<rss xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle" version="2.0">
<channel><title>Proton Drive</title>
<item><title>3.1.0</title><sparkle:channel>gradual-rollout</sparkle:channel>
<sparkle:version>12778.3</sparkle:version><sparkle:shortVersionString>3.1.0</sparkle:shortVersionString>
<enclosure url="https://proton.me/download/drive/macos/3.1.0/x.tar.xz" length="1" type="application/octet-stream"/></item>
<item><title>3.0.3</title><sparkle:channel>stable</sparkle:channel>
<sparkle:version>12567.3</sparkle:version><sparkle:shortVersionString>3.0.3</sparkle:shortVersionString>
<enclosure url="https://proton.me/download/drive/macos/3.0.3/x.tar.xz" length="1" type="application/octet-stream"/></item>
<item><title>3.0.0</title><sparkle:version>100.1</sparkle:version>
<enclosure url="https://proton.me/a.tar.xz" length="1" sparkle:shortVersionString="3.0.0"/></item>
</channel></rss>"""


def read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def run_bash(script: str, env=None, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["/bin/bash", "-c", script],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
        env=env if env is not None else shell_env(), timeout=timeout,
    )


class AppcastCrossCheck(unittest.TestCase):
    def test_items_are_channel_aware(self) -> None:
        items = sparkle_appcast_items(APPCAST)
        self.assertEqual([i["channel"] for i in items], ["gradual-rollout", "stable", ""])
        self.assertEqual(items[0]["short"], "3.1.0")
        self.assertEqual(items[0]["build"], "12778.3")
        self.assertEqual(items[2]["short"], "3.0.0")  # enclosure attribute fallback

    def test_garbage_is_empty(self) -> None:
        self.assertEqual(sparkle_appcast_items("<not xml"), [])
        self.assertEqual(sparkle_appcast_items(""), [])

    def test_installed_rollout_version_is_proven(self) -> None:
        self.assertEqual(appcast_publishes_installed(APPCAST, "3.1.0", "12778.3"), "gradual-rollout")
        self.assertEqual(appcast_publishes_installed(APPCAST, "3.1.0"), "gradual-rollout")

    def test_build_match_alone_is_enough(self) -> None:
        self.assertEqual(appcast_publishes_installed(APPCAST, "9.9.9", "12778.3"), "gradual-rollout")

    def test_stable_and_default_channel_preferred(self) -> None:
        self.assertEqual(appcast_publishes_installed(APPCAST, "3.0.3", "1"), "stable")
        self.assertEqual(appcast_publishes_installed(APPCAST, "3.0.0", "1"), "")

    def test_unpublished_version_is_not_proven(self) -> None:
        self.assertIsNone(appcast_publishes_installed(APPCAST, "3.2.0", "99999.1"))
        self.assertIsNone(appcast_publishes_installed("", "3.1.0", "1"))

    def test_url_allowlist(self) -> None:
        self.assertTrue(appcast_url_allowed("https://proton.me/download/drive/macos/appcast.xml", "proton.me"))
        self.assertFalse(appcast_url_allowed("http://proton.me/a.xml", "proton.me"))
        self.assertFalse(appcast_url_allowed("https://evil.proton.me.example/a.xml", "proton.me"))
        self.assertFalse(appcast_url_allowed("https://proton.me@evil.example/a.xml", "proton.me"))
        self.assertFalse(appcast_url_allowed("https://proton.me/a.xml", "-"))
        self.assertFalse(appcast_url_allowed("", "proton.me"))

    def test_config_and_handler_wiring(self) -> None:
        cfg = read("config/vendor_appcasts.txt")
        self.assertIn("Proton Drive|https://proton.me/download/drive/macos/appcast.xml", cfg)
        handler = read("lib/internet_handlers.sh")
        vt = handler[handler.index("internet_handler_vendor_truth() {"):]
        stale = vt.index("L_INTERNET_STATUS_FEED_STALE_FMT")
        self.assertIn("vendor_appcast_published_channel", vt[:stale])
        self.assertIn("L_INTERNET_STATUS_VENDOR_CHANNEL_CURRENT_FMT", vt[:stale])

    @unittest.skipUnless(sys.platform == "darwin" and shutil.which("defaults"), "needs macOS defaults(1) to read Info.plist")
    def test_shell_helper_end_to_end_with_stub_curl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            app = tmp_p / "Proton Drive.app" / "Contents"
            app.mkdir(parents=True)
            with open(app / "Info.plist", "wb") as fh:
                plistlib.dump({"CFBundleShortVersionString": "3.1.0", "CFBundleVersion": "12778.3"}, fh)
            old = tmp_p / "Old.app" / "Contents"
            old.mkdir(parents=True)
            with open(old / "Info.plist", "wb") as fh:
                plistlib.dump({"CFBundleShortVersionString": "9.9.9", "CFBundleVersion": "1"}, fh)
            bindir = tmp_p / "bin"
            bindir.mkdir()
            (tmp_p / "appcast.xml").write_text(APPCAST, encoding="utf-8")
            stub = bindir / "curl"
            stub.write_text(f'#!/bin/sh\ncat "{tmp_p}/appcast.xml"\n', encoding="utf-8")
            stub.chmod(0o755)
            env = shell_env(PATH=f"{bindir}:{os.environ['PATH']}")
            script = (
                f'. lib/vendor_feeds.sh; '
                f'vendor_appcast_published_channel "Proton Drive" "{tmp_p}/Proton Drive.app"; echo "rc=$?"; '
                f'vendor_appcast_published_channel "Proton Drive" "{tmp_p}/Old.app"; echo "rc=$?"; '
                f'vendor_appcast_published_channel "Nonexistent App" "{tmp_p}/Old.app"; echo "rc=$?"'
            )
            res = run_bash(script, env=env)
            self.assertEqual(res.stdout.split(), ["gradual-rollout", "rc=0", "rc=1", "rc=1"], res.stderr)


class WarningsOnly(unittest.TestCase):
    def _session(self, tmp: str, steps: dict, codes: list, pending: dict) -> str:
        p = Path(tmp)
        (p / "step_status_codes.txt").write_text(
            "".join(f"{k}={v}\n" for k, v in steps.items()), encoding="utf-8")
        (p / "internet_status_codes.txt").write_text(
            "".join(f"{a}|{c}|text\n" for a, c in codes), encoding="utf-8")
        for k, v in pending.items():
            (p / k).write_text(f"{v}\n", encoding="utf-8")
        return tmp

    BASE = {"appstore": "ok", "npmcli": "ok", "brew": "ok", "internet": "warn", "postupdate": "ok", "system": "ok"}

    def test_feed_stale_only_is_warnings_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._session(tmp, self.BASE, [("Proton Drive", "feed_stale"), ("X", "current_verified")],
                          {"pending_appstore": 0})
            self.assertTrue(degraded_is_warnings_only(tmp))

    def test_unverified_or_behind_is_not(self) -> None:
        for code in ("unverified", "behind", "needs_restart", "error_soft"):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as tmp:
                self._session(tmp, self.BASE, [("A", "feed_stale"), ("B", code)], {})
                self.assertFalse(degraded_is_warnings_only(tmp))

    def test_pending_or_other_step_warning_is_not(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self._session(tmp, self.BASE, [("A", "feed_stale")], {"pending_appstore": 1})
            self.assertFalse(degraded_is_warnings_only(tmp))
        with tempfile.TemporaryDirectory() as tmp:
            steps = dict(self.BASE, appstore="warn")
            self._session(tmp, steps, [("A", "feed_stale")], {})
            self.assertFalse(degraded_is_warnings_only(tmp))

    def test_missing_evidence_is_conservative(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(degraded_is_warnings_only(tmp))

    def test_master_uses_it_and_status_codes_not_text(self) -> None:
        text = read("update_all.sh")
        self.assertIn("degraded_is_warnings_only", text)
        self.assertIn("L_ALL_WARNINGS_ONLY", text)
        self.assertNotIn('"$RESULT_MD" = "$L_STATUS_OK', text)
        self.assertNotIn("$L_STATUS_OK completed", text)
        self.assertNotIn("reported warnings (soft)", text)


class StepTextClassification(unittest.TestCase):
    def test_new_texts_classify_in_every_language(self) -> None:
        for lang in LANGS:
            text = read(f"i18n/lang_{lang}.sh")
            ok = re.search(r'(?m)^L_ALL_RESULT_OK="([^"]+)"', text).group(1)
            warn = re.search(r'(?m)^L_ALL_RESULT_DEGRADED="([^"]+)"', text).group(1)
            with self.subTest(lang=lang):
                self.assertEqual(classify_step_status(ok), "ok")
                self.assertEqual(classify_step_status("⚠️  " + warn), "warn")

    def test_legacy_texts_still_classify(self) -> None:
        self.assertEqual(classify_step_status("OK completed"), "ok")
        self.assertEqual(classify_step_status("Ostrzeżenie zakończono z ostrzeżeniami"), "warn")
        self.assertEqual(classify_step_status({"code": "warn", "text": "anything"}), "warn")


class AppStoreTrack2(unittest.TestCase):
    def setUp(self) -> None:
        self.text = read("update_appstore.sh")

    def test_not_offered_branch_is_honest(self) -> None:
        i = self.text.index('elif echo "$AS_RESULT" | grep -q "^NO_UPDATES_FOUND" && [ -n "${_IOS_PENDING:-}" ]')
        branch = self.text[i:self.text.index("\nelif ", i + 10)]
        self.assertIn('APPSTORE_TOR2_BRANCH="not_offered"', branch)
        self.assertIn("L_APPSTORE_IOS_NOT_OFFERED_FMT", branch)
        self.assertIn("SOFT_FAIL=1", branch)
        self.assertIn("appstore_ios_pending.txt", branch)
        self.assertNotIn("L_APPSTORE_NO_UPDATES", branch)
        self.assertNotIn("L_APPSTORE_TOR2_NOTHING", branch)

    def test_nothing_pending_summary_excludes_not_offered(self) -> None:
        summary = self.text[self.text.index('if [ "$APPSTORE_EXIT" -eq 0 ]; then'):]
        clean = summary[:summary.index('elif [ "$APPSTORE_EXIT" -eq "$MAC_UPDATE_SOFT_EXIT" ]')]
        nothing = clean[clean.index('if [ "$APPSTORE_TOR2_BRANCH" = "no_updates" ]'):clean.index("L_APPSTORE_TOR2_NOTHING")]
        self.assertNotIn("not_offered", nothing)
        soft = summary[summary.index('elif [ "$APPSTORE_EXIT" -eq "$MAC_UPDATE_SOFT_EXIT" ]'):]
        self.assertIn('"not_offered"', soft)
        self.assertIn("L_APPSTORE_TOR2_NOT_OFFERED", soft)

    def test_pending_count_includes_not_offered(self) -> None:
        self.assertIn("NOT_OFFERED_COUNT", self.text)
        self.assertRegex(self.text, r"PENDING_APPSTORE=\$\(\( \$\{PENDING_APPSTORE:-0\} \+ \$\{NOT_OFFERED_COUNT:-0\} \)\)")

    def test_undefined_severity_function_not_called(self) -> None:
        self.assertNotIn("mac_update_severity_register", self.text)

    def test_track2_only_prompt(self) -> None:
        self.assertIn('appstore_confirm "$L_CONFIRM_TRACK2"', self.text)
        self.assertIn("L_TRACK2_ONLY_INFO", self.text)
        block = self.text[self.text.index('"$APPSTORE_CONFIRMED" -eq 0 ]'):]
        block = block[:block.index("_TRACK2_SKIP_GUI=1")]
        self.assertNotIn("L_AX_PERMISSION_CHECK", block)

    def test_applescript_is_robust(self) -> None:
        a = self.text[self.text.index("cat <<'APPLESCRIPT'"):self.text.index("\nAPPLESCRIPT\n")]
        self.assertNotIn("delay 6", a)
        self.assertIn("on run argv", a)
        for needle in ("description of elem", "title of elem", "name of elem",
                       "Uaktualnij wszystko", "Alle aktualisieren", "Actualizar todo", "Aggiorna tutto",
                       "Atualizar Tudo", "Tout mettre à jour", "Uaktualnij", "Mettre à jour",
                       'keystroke "r" using command down', "macappstores://apps.apple.com/app/id",
                       "PRODUCT_PAGE_UPDATES:", "NO_UPDATES_FOUND"):
            self.assertIn(needle, a)
        # exactly one refresh keystroke
        self.assertEqual(a.count('keystroke "r"'), 1)
        self.assertIn('"$AS_BUDGET" $TRACK2_IDS', self.text)

    @unittest.skipUnless(shutil.which("osacompile"), "osacompile not available")
    def test_applescript_compiles(self) -> None:
        a = self.text[self.text.index("cat <<'APPLESCRIPT'"):self.text.index("\nAPPLESCRIPT\n")]
        body = a.split("\n", 1)[1]
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp, "t.applescript")
            src.write_text(body + "\n", encoding="utf-8")
            res = subprocess.run(["osacompile", "-o", str(Path(tmp, "t.scpt")), str(src)],
                                 capture_output=True, text=True, timeout=60)
            self.assertEqual(res.returncode, 0, res.stderr)

    def test_ids_are_digits_only(self) -> None:
        pending = "UniFi|1057750338|11.0.1|11.0.2\nEvil|12;rm -rf /|1|2\nBad|abc|1|2\nTwo|99|1|2\nnopipe\n"
        res = run_bash('. lib/appstore_ios.sh; ios_pending_ids "$1"', env=shell_env())
        self.assertEqual(res.returncode, 0)
        res = subprocess.run(["/bin/bash", "-c", '. lib/appstore_ios.sh; ios_pending_ids "$1"', "x", pending],
                             capture_output=True, text=True, cwd=str(REPO_ROOT), env=shell_env())
        self.assertEqual(res.stdout.split(), ["1057750338", "99"])

    def test_banners_and_headers_are_localized(self) -> None:
        for raw in ('print_header "Checking mas tool..."', "SCRIPT 2 FINISHED WITH", "An App Store operation failed",
                    "— sudo mas upgrade skipped", "timed out or failed; review window manually",
                    "native App Store state is unknown.\""):
            self.assertNotIn(raw, self.text)


class I18nKeys(unittest.TestCase):
    KEYS = {
        "L_INTERNET_STATUS_VENDOR_CHANNEL_CURRENT_FMT": 1,
        "L_APPSTORE_IOS_NOT_OFFERED_FMT": 2,
        "L_CONFIRM_TRACK2": 0, "L_TRACK2_ONLY_INFO": 0, "L_APPSTORE_TOR2_NOT_OFFERED": 0,
        "L_APPSTORE_CHECKING_MAS": 0, "L_APPSTORE_TOR1_SKIPPED": 0, "L_APPSTORE_TOR2_GUI_FAILED": 0,
        "L_APPSTORE_BANNER_WARNINGS": 0, "L_APPSTORE_BANNER_ERRORS": 0, "L_APPSTORE_BG_STILL_INSTALLING": 0,
        "L_APPSTORE_STATE_UNVERIFIED": 0, "L_APPSTORE_OP_FAILED": 0, "L_APPSTORE_MAS_OUTDATED_UNKNOWN": 0,
        "L_APPSTORE_MAS_OUTDATED_ACCURATE_UNKNOWN": 0, "L_APPSTORE_TOR2_BG_UNVERIFIED_FMT": 1,
        "L_ALL_STEP_SOFT_WARNINGS_FMT": 1, "L_ALL_STEP_INTERNET_NAME": 0, "L_ALL_WARNINGS_ONLY": 0,
        "L_ALL_RESULT_OK": 0, "L_ALL_RESULT_AX_REQUIRED": 0, "L_ALL_RESULT_MISSING_FILE": 0,
        "L_ALL_LABEL_SCAN": 0, "L_ALL_LABEL_APPSTORE": 0, "L_ALL_LABEL_NPMCLI": 0, "L_ALL_LABEL_BREW": 0,
        "L_ALL_LABEL_INTERNET": 0, "L_ALL_LABEL_SYSTEM": 0, "L_ALL_DURATION_FMT": 2,
        "L_ALL_RUN_SUMMARY_TITLE": 0, "L_ALL_CHRONIC_TITLE": 0, "L_ALL_CHRONIC_ITEM_FMT": 3,
        "L_NPM_PROFILE_BACKUP_FMT": 1,
    }

    def test_keys_in_all_languages_with_consistent_placeholders(self) -> None:
        for lang in LANGS:
            text = read(f"i18n/lang_{lang}.sh")
            for key, n in self.KEYS.items():
                with self.subTest(lang=lang, key=key):
                    m = re.search(rf'(?m)^{key}="([^"]+)"$', text)
                    self.assertIsNotNone(m, "missing or empty")
                    self.assertEqual(m.group(1).count("%s"), n)


class ProfileBackupOnlyOnChange(unittest.TestCase):
    def _run(self, home: Path, body: str) -> subprocess.CompletedProcess:
        text = read("update_npm_cli.sh")
        funcs = text[text.index("resolve_target_file() {"):text.index("expand_node_manager_paths() {")]
        script = (
            'print_info() { echo "INFO: $*"; }\nprint_warn() { echo "WARN: $*"; }\n'
            'L_NPM_PROFILE_BACKUP_FMT="Profile backup: %s"\nL_NPM_DEEP_SYMLINK_CHAIN="%s %s"\n'
            f'NPMRC_PATH="{home}/.npmrc"\n' + funcs + "\n" + body
        )
        return run_bash(script, env=shell_env(HOME=str(home)))

    def _backups(self, home: Path) -> list:
        return sorted(p.name for p in home.iterdir() if "macupd-backup" in p.name)

    def test_no_backup_when_nothing_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".zshrc").write_text("alias a=b\n\nexport FOO=1\n", encoding="utf-8")
            (home / ".npmrc").write_text("registry=https://registry.npmjs.org/\n", encoding="utf-8")
            before = (home / ".zshrc").read_text(encoding="utf-8")
            res = self._run(home, f'remove_line_from_file "{home}/.zshrc" "export N_PREFIX=x"; '
                                  f'remove_npmrc_prefix; ensure_line_in_file "{home}/.zshrc" "export FOO=1"')
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(self._backups(home), [])
            self.assertNotIn("Profile backup", res.stdout)
            self.assertEqual((home / ".zshrc").read_text(encoding="utf-8"), before)

    def test_backup_when_content_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".zshrc").write_text("alias a=b\nexport N_PREFIX=x\n", encoding="utf-8")
            (home / ".npmrc").write_text("prefix=/tmp/x\nregistry=r\n", encoding="utf-8")
            res = self._run(home, f'remove_line_from_file "{home}/.zshrc" "export N_PREFIX=x"; remove_npmrc_prefix')
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(len(self._backups(home)), 2)
            self.assertEqual(res.stdout.count("Profile backup"), 2)
            self.assertNotIn("N_PREFIX", (home / ".zshrc").read_text(encoding="utf-8"))
            self.assertNotIn("prefix", (home / ".npmrc").read_text(encoding="utf-8"))


    def test_managed_block_resync_is_idempotent(self) -> None:
        """The real flow removes every block variant and re-appends the canonical
        lines. That must not rewrite or back up an already-correct profile (the
        2026-10-25 log showed a fresh ~/.zshrc backup on every run)."""
        text = read("update_npm_cli.sh")
        sync = text[text.index("sync_profile_block() {"):text.index("normalize_semver() {")]
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".zshrc").write_text("alias a=b\n", encoding="utf-8")
            (home / ".npmrc").write_text("registry=r\n", encoding="utf-8")
            body = (
                f'N_PREFIX="{home}/n"; NPM_GLOBAL_BIN="{home}/g/bin"; BUN_BIN="{home}/.bun/bin"; '
                f'BUN_HOME="{home}/.bun"; LOCAL_BIN="{home}/.local/bin"; NVM_BIN=""\n'
                + sync + f'\nsync_profile_block "{home}/.zshrc" || exit 9\n'
            )
            first = self._run(home, body)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(len(self._backups(home)), 1)
            after_first = (home / ".zshrc").read_text(encoding="utf-8")
            self.assertIn("# Managed by macOS Updates — native CLI toolchain", after_first)
            self.assertTrue(after_first.startswith("alias a=b\n"))
            for _ in range(2):
                again = self._run(home, body)
                self.assertEqual(again.returncode, 0, again.stderr)
                self.assertNotIn("Profile backup", again.stdout)
            self.assertEqual(len(self._backups(home)), 1)
            self.assertEqual((home / ".zshrc").read_text(encoding="utf-8"), after_first)

if __name__ == "__main__":
    unittest.main()
