"""Regressions from the first live run on the 2026-11-09 branch.

C1 GitHub rate limit vs "no connection" (status/headers logged, cached proof),
C2 running app is never downloaded for, C3 localized strings, C4 prompt re-ask.
No test reaches the real GitHub API: curl is a stub on PATH.
"""
from __future__ import annotations

import os
import re
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import shell_env  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
LANGS = ("en", "pl", "es", "it", "pt", "de", "fr")
RESET = 1893456000  # fixed epoch for the x-ratelimit-reset header

CURL_STUB = r'''#!/bin/sh
echo "$@" >> "$STUB_DIR/curl_calls.log"
hdr=""; out=""; prev=""
for a in "$@"; do
    case "$prev" in -D) hdr="$a" ;; -o) out="$a" ;; esac
    prev="$a"
done
case "$STUB_MODE" in
    ratelimit)
        [ -n "$hdr" ] && printf 'HTTP/2 403\r\nx-ratelimit-limit: 60\r\nx-ratelimit-remaining: 0\r\nx-ratelimit-reset: %s\r\n\r\n' "$STUB_RESET" > "$hdr"
        [ -n "$out" ] && echo '{"message":"API rate limit exceeded"}' > "$out"
        printf '403'; exit 0 ;;
    forbidden)
        [ -n "$hdr" ] && printf 'HTTP/2 403\r\nx-ratelimit-remaining: 41\r\n\r\n' > "$hdr"
        [ -n "$out" ] && echo '{}' > "$out"
        printf '403'; exit 0 ;;
    ok)
        [ -n "$hdr" ] && printf 'HTTP/2 200\r\nx-ratelimit-remaining: 59\r\nx-ratelimit-reset: %s\r\n\r\n' "$STUB_RESET" > "$hdr"
        [ -n "$out" ] && echo '{"tag_name":"v9.9.9"}' > "$out"
        printf '200'; exit 0 ;;
    *)  # network down
        printf '000'; exit 6 ;;
esac
'''


class GithubHarness(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "bin").mkdir()
        stub = self.root / "bin" / "curl"
        stub.write_text(CURL_STUB, encoding="utf-8")
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_sh(self, body: str, mode: str = "ratelimit", lang: str = "en", **extra: str) -> subprocess.CompletedProcess:
        script = f'''
export SCRIPT_DIR="{REPO_ROOT}" MAC_UPDATE_SESSION_DIR="{self.root}" MAC_LANG={lang}
export MAC_UPDATE_FEED_STATE_FILE="{self.root}/feed_state.json"
. lib/platform.sh; . lib/ui.sh; . lib/version.sh; . lib/proc.sh; . lib/vendor_feeds.sh
. lib/internet_apps.sh; . lib/internet_registry.sh; . lib/internet_handlers.sh
. lib/github_release.sh; . lib/internet_i18n.sh; . lib/internet_status.sh; . i18n/loader.sh
{body}
'''
        env = shell_env(HOME=str(self.root), STUB_DIR=str(self.root), STUB_MODE=mode,
                        STUB_RESET=str(RESET), **extra)
        env["PATH"] = f"{self.root / 'bin'}:{env.get('PATH', '')}"
        env.pop("GITHUB_TOKEN", None)
        return subprocess.run(["bash", "-c", script], cwd=REPO_ROOT, capture_output=True, text=True,
                              env=env, timeout=60)

    def diag(self) -> str:
        f = self.root / "internet_diag.txt"
        return f.read_text(encoding="utf-8") if f.exists() else ""


class GithubRateLimitTests(GithubHarness):
    def test_status_and_ratelimit_headers_are_logged_and_recorded(self) -> None:
        res = self.run_sh('github_api_fetch "owner/repo" "https://api.github.com/x" "$MAC_UPDATE_SESSION_DIR/b"; echo rc=$?; github_last_outcome')
        self.assertIn("rc=1", res.stdout)
        self.assertIn(f"ratelimit|403|0|{RESET}", res.stdout)
        self.assertRegex(self.diag(), r"GitHub owner/repo: lookup FAILED \(curl=\d+ http=403 remaining=0 reset=%d " % RESET)

    def test_success_is_logged_too(self) -> None:
        res = self.run_sh('github_api_fetch "owner/repo" "https://api.github.com/x" "$MAC_UPDATE_SESSION_DIR/b"; echo rc=$?', mode="ok")
        self.assertIn("rc=0", res.stdout)
        self.assertRegex(self.diag(), r"lookup ok \(curl=0 http=200 remaining=59")

    def test_403_with_remaining_quota_is_not_a_rate_limit(self) -> None:
        res = self.run_sh('github_api_fetch "r" "https://api.github.com/x" "$MAC_UPDATE_SESSION_DIR/b"; github_last_outcome', mode="forbidden")
        self.assertIn("http|403|41", res.stdout)

    def test_latest_tag_failure_keeps_the_question_mark_contract(self) -> None:
        res = self.run_sh('github_latest_tag "owner/repo"')
        self.assertEqual(res.stdout.strip(), "?")
        res = self.run_sh('github_latest_tag "owner/repo"', mode="ok")
        self.assertEqual(res.stdout.strip(), "v9.9.9")

    def test_ratelimit_gets_a_distinct_soft_status_not_no_connection(self) -> None:
        hhmm = time.strftime("%H:%M", time.localtime(RESET))
        res = self.run_sh('''
github_latest_tag "owner/repo" >/dev/null
github_lookup_handled "Trezor Suite" "1.0.0"; echo "rc=$?"
echo "STATUS=$GITHUB_UNAVAILABLE_STATUS"
echo "CODE=$(internet_status_code "$GITHUB_UNAVAILABLE_STATUS")"
echo "OFFLINE_CODE=$(internet_status_code "$L_INTERNET_STATUS_OFFLINE")"
''')
        self.assertIn("rc=0", res.stdout)
        self.assertIn("GITHUB_TOKEN", res.stdout)
        self.assertIn(hhmm, res.stdout)
        self.assertNotIn("No connection", res.stdout.split("STATUS=")[1].split("\n")[0])
        self.assertIn("CODE=error_soft", res.stdout)

    def test_ratelimit_message_is_localized(self) -> None:
        res = self.run_sh('github_latest_tag "r" >/dev/null; github_lookup_handled "Trezor Suite" "1.0.0"; echo "$GITHUB_UNAVAILABLE_STATUS"', lang="pl")
        self.assertIn("Limit zapytań GitHub", res.stdout)

    def test_plain_network_failure_is_left_to_the_caller(self) -> None:
        res = self.run_sh('github_latest_tag "r" >/dev/null; github_lookup_handled "Trezor Suite" "1.0.0"; echo "rc=$?"', mode="down")
        self.assertIn("rc=1", res.stdout)

    def test_cached_proof_reports_current_cached_for_exact_installed_version(self) -> None:
        res = self.run_sh('''
github_lookup_record "Trezor Suite" "1.2.3"
github_latest_tag "r" >/dev/null
github_lookup_handled "Trezor Suite" "1.2.3"; echo "rc=$?"
echo "CODE=$(internet_status_code "$GITHUB_UNAVAILABLE_STATUS")"
github_lookup_handled "Trezor Suite" "1.2.2"; echo "other_rc=$?"
''', mode="ratelimit")
        self.assertIn("rc=0", res.stdout)
        self.assertIn("CODE=current_cached", res.stdout)
        # a cached listing of another version proves nothing; the rate limit is reported
        self.assertIn("other_rc=0", res.stdout)
        res = self.run_sh('github_lookup_record "KeePassXC" "2.8.0"; github_latest_tag r >/dev/null; github_lookup_handled "KeePassXC" "2.7.0"; echo "rc=$?"', mode="down")
        self.assertIn("rc=1", res.stdout)

    def test_cached_proof_expires(self) -> None:
        res = self.run_sh('github_lookup_record "CodeEdit" "1.0"; github_lookup_handled "CodeEdit" "1.0"; echo "rc=$?"',
                          mode="down", MAC_UPDATE_FEED_CACHE_TTL_H="0")
        self.assertIn("rc=1", res.stdout)

    def test_cached_proof_is_not_counted_as_verified(self) -> None:
        main = (REPO_ROOT / "update_internet_apps.sh").read_text(encoding="utf-8")
        self.assertIn("current_cached", main)
        self.assertNotRegex(main, r"current_cached\)\s*\n\s*_cnt_verified")

    def test_handlers_use_the_helpers_and_never_call_the_api_directly(self) -> None:
        text = (REPO_ROOT / "lib" / "internet_app_updates.sh").read_text(encoding="utf-8")
        self.assertNotIn("api.github.com", text.replace('"https://api.github.com/repos/trezor/trezor-suite/releases?per_page=20"', ""))
        for app in ("KeePassXC", "CodeEdit", "Trezor Suite"):
            self.assertIn(f'github_lookup_handled "{app}"', text)
            self.assertIn(f'github_lookup_record "{app}"', text)


class DeferBeforeDownloadTests(GithubHarness):
    def test_running_app_skips_download_and_reports_needs_restart(self) -> None:
        res = self.run_sh('''
replacement_app_is_idle() { return 1; }
internet_defer_running_app "$MAC_UPDATE_SESSION_DIR/Fixture.app" STATUS_FIXTURE "1.0" "2.0"; echo "rc=$?"
echo "STATUS=$STATUS_FIXTURE"
echo "CODE=$(internet_status_code "$STATUS_FIXTURE")"
''')
        self.assertIn("rc=0", res.stdout)
        self.assertIn("CODE=needs_restart", res.stdout)
        self.assertFalse((self.root / "curl_calls.log").exists())
        self.assertIn("Download skipped", self.diag())

    def test_idle_app_proceeds_to_download(self) -> None:
        res = self.run_sh('replacement_app_is_idle() { return 0; }; internet_defer_running_app "$MAC_UPDATE_SESSION_DIR/F.app" STATUS_F 1 2; echo "rc=$?"')
        self.assertIn("rc=1", res.stdout)

    def test_dry_run_never_defers(self) -> None:
        res = self.run_sh('replacement_app_is_idle() { return 1; }; MAC_UPDATE_DRY_RUN=1 internet_defer_running_app "$MAC_UPDATE_SESSION_DIR/F.app" STATUS_F 1 2; echo "rc=$?"')
        self.assertIn("rc=1", res.stdout)

    def test_every_download_handler_checks_before_downloading_and_deferral_prints_no_copy_error(self) -> None:
        text = (REPO_ROOT / "lib" / "internet_app_updates.sh").read_text(encoding="utf-8")
        self.assertEqual(text.count("internet_defer_running_app "), 6)
        # the copy-error line only appears on the non-deferred branch
        self.assertNotRegex(text, r'print_warn "\$\(internet_msg "\$L_INTERNET_COPY[A-Z_]*"[^\n]*\n\s*if \[ "\$\{INTERNET_COPY_DEFERRED')
        for m in re.finditer(r'if \[ "\$\{INTERNET_COPY_DEFERRED:-0\}" = "1" \]; then\n[^\n]*\n\s*else\n\s*print_warn', text):
            pass
        self.assertEqual(len(re.findall(r'if \[ "\$\{INTERNET_COPY_DEFERRED:-0\}" = "1" \]; then\n[^\n]*\n\s*else\n\s*print_warn', text)), 6)


class LocalizationTests(unittest.TestCase):
    KEYS = ("L_INTERNET_GITHUB_RATELIMIT_FMT", "L_INTERNET_STATUS_GITHUB_RATELIMIT_FMT",
            "L_INTERNET_COPY_DEFERRED_RUNNING_FMT", "L_INTERNET_COPY_DEFERRED_ACTIVE_FMT",
            "L_APPSTORE_MAS_UPGRADE_COMPLETED", "L_APPSTORE_MAS_RETRY_USER_SESSION",
            "L_SUMMARY_DETAIL_VENDOR_AHEAD_FMT", "L_SUMMARY_DETAIL_UPDATE_PENDING_QUIT",
            "L_SUMMARY_DETAIL_UPDATES_PENDING_FMT", "L_PROMPT_INVALID_ANSWER")

    def test_keys_exist_in_every_language_and_placeholders_match(self) -> None:
        en = (REPO_ROOT / "i18n" / "lang_en.sh").read_text(encoding="utf-8")
        for key in self.KEYS:
            want = re.search(rf'(?m)^{key}="(.*)"$', en).group(1).count("%s")
            for lang in LANGS:
                text = (REPO_ROOT / "i18n" / f"lang_{lang}.sh").read_text(encoding="utf-8")
                m = re.search(rf'(?m)^{key}="(.*)"$', text)
                self.assertIsNotNone(m, f"{lang}:{key}")
                self.assertEqual(m.group(1).count("%s"), want, f"{lang}:{key}")
        pl = (REPO_ROOT / "i18n" / "lang_pl.sh").read_text(encoding="utf-8")
        self.assertNotRegex(pl, r'(?m)^L_APPSTORE_MAS_UPGRADE_COMPLETED=".*mas upgrade command completed')

    def test_no_english_literals_left_in_the_scripts(self) -> None:
        for rel, needles in (
            ("update_internet_apps.sh", ("replacement deferred",)),
            ("update_appstore.sh", ("left these App Store updates pending; retrying in the user session:\"",)),
        ):
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            for n in needles:
                self.assertNotIn(n, text.replace("${L_APPSTORE_MAS_RETRY_USER_SESSION:-sudo mas upgrade left these App Store updates pending; retrying in the user session:}", ""), rel)

    def test_run_summary_details_follow_the_language(self) -> None:
        code = r'''
import os, sys, tempfile
from pathlib import Path
sys.path.insert(0, "lib/python")
import run_summary as rs
sdir = Path(tempfile.mkdtemp())
(sdir / "pending_appstore").write_text("3\n")
(sdir / "internet_status_codes.txt").write_text("Fixture App|needs_restart|⚠️  Update 1.0 → 2.0 pending — x\n")
for it in rs.collect_run_items(sdir):
    print(it.get("details"))
'''
        def run(env_extra):
            env = shell_env(**env_extra)
            return subprocess.run([sys.executable, "-I", "-c", code], cwd=REPO_ROOT, capture_output=True,
                                  text=True, env=env).stdout
        en = run({})
        self.assertIn("3 updates pending", en)
        self.assertIn("vendor 2.0 > installed 1.0 — quit the app so its updater can install it", en)
        pl = run({"L_SUMMARY_DETAIL_UPDATES_PENDING_FMT": "oczekujących aktualizacji: %s",
                  "L_SUMMARY_DETAIL_VENDOR_AHEAD_FMT": "dostawca %s > zainstalowana %s"})
        self.assertIn("oczekujących aktualizacji: 3", pl)
        self.assertIn("dostawca 2.0 > zainstalowana 1.0", pl)
        bad = run({"L_SUMMARY_DETAIL_UPDATES_PENDING_FMT": "%d broken %z"})
        self.assertIn("3 updates pending", bad)


class PromptReaskTests(unittest.TestCase):
    def sh(self, script: str, stdin: str, **env) -> subprocess.CompletedProcess:
        return subprocess.run(["/bin/bash", "-c", f'. "{REPO_ROOT}/lib/ui.sh"\n{script}'], input=stdin,
                              capture_output=True, text=True, env=shell_env(**env), timeout=40)

    def rc(self, stdin: str, tdef: str = "n", edef: str = "n") -> tuple[int, str]:
        res = self.sh(f"mac_update_prompt_yn 'q? ' {tdef} {edef}; echo rc=$?", stdin)
        return int(re.search(r"rc=(\d+)", res.stdout).group(1)), res.stdout

    def test_stray_character_is_asked_again_not_a_silent_no(self) -> None:
        rc, out = self.rc("x\ny\n", tdef="n", edef="n")
        self.assertEqual(rc, 0)
        self.assertEqual(out.count("q? "), 2)
        self.assertIn("Please answer y (yes) or n (no).", out)

    def test_two_reasks_then_the_timeout_default(self) -> None:
        rc, out = self.rc("a\nb\nc\ny\n", tdef="n", edef="y")
        self.assertEqual(rc, 1)                   # third invalid answer: timeout default, 'y' never read
        self.assertEqual(out.count("q? "), 3)
        self.assertEqual(out.count("Please answer"), 2)
        rc, _ = self.rc("a\nb\nc\n", tdef="y", edef="n")
        self.assertEqual(rc, 0)

    def test_input_ending_after_a_stray_answer_is_never_yes(self) -> None:
        rc, _ = self.rc("maybe\n", tdef="y", edef="y")
        self.assertEqual(rc, 1)

    def test_recognised_empty_and_timeout_behave_as_before(self) -> None:
        self.assertEqual(self.rc("n\n", "y", "y")[0], 1)
        self.assertEqual(self.rc("Y\n", "n", "n")[0], 0)
        self.assertEqual(self.rc("\n", "n", "y")[0], 0)
        self.assertEqual(self.rc("x\n\n", "n", "y")[0], 0)   # Enter after a re-ask is still the enter-default
        out = self.rc("y\n")[1]
        self.assertEqual(out.count("q? "), 1)
        self.assertNotIn("Please answer", out)

    def test_message_is_localized_and_stdin_pipe_is_never_drained(self) -> None:
        res = self.sh("L_PROMPT_INVALID_ANSWER='Odpowiedz t (tak) lub n (nie).'; mac_update_prompt_yn 'q? ' n n; echo rc=$?", "x\nt\n")
        self.assertIn("Odpowiedz t (tak) lub n (nie).", res.stdout)
        self.assertIn("rc=0", res.stdout)
        # type-ahead on a pipe (all of it) is consumed by the prompt, not discarded
        self.assertIn("rc=0", self.sh("mac_update_prompt_yn 'q? ' n n; echo rc=$?", "y\nignored\n").stdout)

    def test_typeahead_is_flushed_on_a_terminal_only(self) -> None:
        import pty
        import select
        pid, fd = pty.fork()
        if pid == 0:  # child: a script that starts its prompt after a delay
            os.execve("/bin/bash", ["bash", "-c",
                      f'. "{REPO_ROOT}/lib/ui.sh"; sleep 2; mac_update_prompt_yn "q? " n n; echo "RC=$?"'],
                      shell_env())
        os.write(fd, b"y\n")          # stray type-ahead typed before the prompt appears
        buf = b""
        deadline = time.time() + 6
        sent = False
        while time.time() < deadline:
            r, _, _ = select.select([fd], [], [], 0.2)
            if r:
                try:
                    chunk = os.read(fd, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                buf += chunk
                if b"q? " in buf and not sent:
                    sent = True
                    os.write(fd, b"n\n")
                if b"RC=" in buf and buf.rstrip().endswith(tuple(str(i).encode() for i in range(10))):
                    break
        try:
            os.waitpid(pid, 0)
        except ChildProcessError:
            pass
        text = buf.decode(errors="replace")
        # the early "y" was discarded, so the real answer "n" decided
        self.assertIn("RC=1", text, text)


if __name__ == "__main__":
    unittest.main()
