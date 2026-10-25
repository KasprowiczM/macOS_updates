"""Regressions for the 2026-10-11 run log (v1.5.5).

Covers: stale command-hash after a Homebrew upgrade removed python3 (F1),
reporting-only step 5 must not defer macOS updates (F2), no false "files
updated" claim (F3), honest run-summary failure handling (F4), repeated
graceful quit for toolkit-launched apps (F5) and honest soft-warning
wording (F6).
"""
from __future__ import annotations

import os
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
LANGS = ("en", "pl", "es", "it", "pt", "de", "fr")


def read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def run_bash(script: str, env=None, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["/bin/bash", "-c", script],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env if env is not None else shell_env(),
        timeout=timeout,
    )


def checkhash_line() -> str:
    """The exact `shopt -s checkhash` line update_all.sh uses (test fails if removed)."""
    match = re.search(r"^shopt -s checkhash$", read("update_all.sh"), re.MULTILINE)
    if match is None:
        raise AssertionError("update_all.sh no longer enables `shopt -s checkhash`")
    return match.group(0)


class CheckhashTests(unittest.TestCase):
    """F1: bash must re-search PATH when a hashed binary disappears mid-run."""

    def _run(self, prelude: str) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            dir_a = Path(tmp) / "a"
            dir_b = Path(tmp) / "b"
            dir_a.mkdir()
            dir_b.mkdir()
            for d, label in ((dir_a, "A"), (dir_b, "B")):
                fake = d / "python3"
                fake.write_text(f"#!/bin/sh\necho {label}\n", encoding="utf-8")
                fake.chmod(0o755)
            script = (
                f"{prelude}\n"
                f'PATH="{dir_a}:{dir_b}:/usr/bin:/bin"\n'
                "python3\n"          # hashes python3 -> dir A
                f'rm -f "{dir_a}/python3"\n'  # Homebrew drops the unversioned link
                "python3\n"
            )
            return run_bash(script)

    def test_update_all_checkhash_line_falls_through_to_next_path_entry(self) -> None:
        proc = self._run(checkhash_line())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.split(), ["A", "B"])

    def test_without_checkhash_the_stale_path_fails(self) -> None:
        """Negative control: proves the scenario really reproduces the run-log failure."""
        proc = self._run(":")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("No such file or directory", proc.stderr)

    def test_checkhash_follows_pipefail_in_every_long_lived_script(self) -> None:
        scripts = (
            "update_all.sh",
            "update_appstore.sh",
            "update_brew.sh",
            "update_internet_apps.sh",
            "update_npm_cli.sh",
            "update_system.sh",
            "migration_setup.sh",
        )
        for name in scripts:
            with self.subTest(script=name):
                text = read(name)
                pipefail = text.index("set -o pipefail")
                checkhash = text.index("shopt -s checkhash")
                self.assertGreater(checkhash, pipefail)

    def test_update_all_forgets_hashed_paths_between_steps(self) -> None:
        text = read("update_all.sh")
        for step in (2, 3, 4, 5):
            with self.subTest(step=step):
                marker = f"ui_master_progress {step} 6\n"
                after = text[text.index(marker) + len(marker):]
                self.assertIn("hash -r", "\n".join(after.split("\n")[:5]))


class PostupdateNonBlockingTests(unittest.TestCase):
    """F2/F3: step 5 is reporting-only."""

    def test_postupdate_failure_branch_is_not_blocking(self) -> None:
        text = read("update_all.sh")
        match = re.search(
            r"(    # Step 5 is a reporting step.*?    OVERALL_EXIT=1\n)", text, re.DOTALL
        )
        self.assertIsNotNone(match, "step 5 failure branch not found")
        branch = match.group(1)
        self.assertNotIn("BLOCKING_EXIT=1", branch)
        script = (
            'L_STATUS_ERROR="ERR"; BLOCKING_EXIT=0; OVERALL_EXIT=0\n'
            f"{branch}\n"
            'echo "blocking=$BLOCKING_EXIT overall=$OVERALL_EXIT code=$STATUS_CODE_MD result=$RESULT_MD"\n'
        )
        proc = run_bash(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "blocking=0 overall=1 code=error result=ERR")

    def test_blocking_matrix_documents_step5_as_non_blocking(self) -> None:
        text = read("update_all.sh")
        self.assertRegex(text, r"step 5 inventory\s+NOT blocking")

    def _summary_message(self, status_code: str, inventory_only: str = "0") -> str:
        text = read("update_all.sh")
        start = text.index('if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then\n    print_info "DRY-RUN')
        end = text.index('if [ "${MAC_UPDATE_INVENTORY_ONLY:-0}" != "1" ]; then\n    print_info "$L_ALL_RESTART_CHECK_MSG"')
        snippet = text[start:end]
        script = (
            "print_info() { echo \"INFO: $*\"; }\n"
            'L_ALL_FILES_UPDATED_MSG="FILES_UPDATED"\n'
            f'STATUS_CODE_MD="{status_code}"\n'
            f"MAC_UPDATE_INVENTORY_ONLY={inventory_only}\n"
            "MAC_UPDATE_DRY_RUN=0\n"
            f"{snippet}\n"
        )
        proc = run_bash(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def test_files_updated_message_only_after_successful_step5(self) -> None:
        self.assertIn("FILES_UPDATED", self._summary_message("ok"))
        self.assertNotIn("FILES_UPDATED", self._summary_message("error"))
        self.assertNotIn("FILES_UPDATED", self._summary_message("skipped"))

    def test_inventory_only_claim_also_requires_success(self) -> None:
        self.assertIn("Inventory refreshed", self._summary_message("ok", "1"))
        self.assertNotIn("Inventory refreshed", self._summary_message("error", "1"))

    def test_soft_step_messages_say_warnings_not_unverified(self) -> None:
        text = read("update_all.sh")
        self.assertNotIn("reported unverified updates (soft)", text)
        # 2026-10-25: the wording moved into one localized format key.
        self.assertEqual(text.count("L_ALL_STEP_SOFT_WARNINGS_FMT"), 4)
        for lang in LANGS:
            lang_text = read(f"i18n/lang_{lang}.sh")
            self.assertRegex(lang_text, r'(?m)^L_ALL_STEP_SOFT_WARNINGS_FMT="[^"]*%s[^"]*"$')
        self.assertIn("reported warnings (soft) — macOS step not blocked", read("i18n/lang_en.sh"))


class RunSummaryFailureTests(unittest.TestCase):
    """F4: a failed summary write names its cause and never leaves a 'started' result."""

    def _function(self, name: str) -> str:
        text = read("update_all.sh")
        if name == "write_machine_summary":
            match = re.search(r"write_machine_summary\(\) \{.*?\n    return \"\$rc\"\n\}\n", text, re.DOTALL)
        else:
            match = re.search(name + r"\(\) \{.*?\n\}\n", text, re.DOTALL)
        self.assertIsNotNone(match, f"{name} not found")
        return match.group(0)

    def test_missing_python3_is_named_in_the_error(self) -> None:
        func = self._function("write_machine_summary")
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            date_bin = shutil.which("date")
            self.assertIsNotNone(date_bin)
            (bin_dir / "date").symlink_to(date_bin)
            script = (
                "save_step_status_codes() { :; }\n"
                f'SCRIPT_DIR="{tmp}"; SESSION_DIR="{tmp}"; START_TIME=1\n'
                f"{func}\n"
                f'PATH="{bin_dir}"\n'
                "write_machine_summary completed\n"
                "echo rc=$?\n"
            )
            proc = run_bash(script)
        self.assertIn("rc=127", proc.stdout)
        self.assertIn("python3 not found on PATH", proc.stderr)

    def test_stale_started_summary_is_relabelled_failed(self) -> None:
        func = self._function("mark_stale_summary_failed")
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp) / "logs"
            logs.mkdir()
            started = '{\n  "run_status": "started",\n  "run_id": "x"\n}\n'
            completed = '{\n  "run_status": "completed"\n}\n'
            (logs / "run_summary_latest.json").write_text(started, encoding="utf-8")
            (logs / "run_summary_20261011_111237.json").write_text(started, encoding="utf-8")
            other = logs / "run_summary_20250101_000000.json"
            other.write_text(completed, encoding="utf-8")
            script = (
                f'SCRIPT_DIR="{tmp}"; RUN_TIMESTAMP="20261011_111237"\n'
                f"{func}\n"
                "mark_stale_summary_failed\n"
            )
            proc = run_bash(script)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            for name in ("run_summary_latest.json", "run_summary_20261011_111237.json"):
                content = (logs / name).read_text(encoding="utf-8")
                self.assertIn('"run_status": "failed"', content)
                self.assertNotIn('"started"', content)
            self.assertEqual(other.read_text(encoding="utf-8"), completed)
            self.assertEqual(len(list(logs.iterdir())), 3, "no temp files left behind")

    def test_failure_branch_marks_stale_summary(self) -> None:
        text = read("update_all.sh")
        branch = text[text.index("if ! write_machine_summary completed; then"):]
        branch = branch[: branch.index("fi\n")]
        self.assertIn("mark_stale_summary_failed", branch)
        self.assertIn("OVERALL_EXIT=1", branch)


class GracefulQuitTests(unittest.TestCase):
    """F5: re-send the graceful quit while a toolkit-launched app keeps running."""

    def _run_quit(self, running_polls: int, env_extra: str = "") -> "tuple[subprocess.CompletedProcess, int, bool]":
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            state = Path(tmp) / "polls"
            quits = Path(tmp) / "quits.log"
            forbidden = Path(tmp) / "forbidden.log"
            state.write_text("0", encoding="utf-8")
            osascript = bin_dir / "osascript"
            osascript.write_text(
                "#!/bin/bash\n"
                'cmd="$2"\n'
                'case "$cmd" in\n'
                "  *'is running'*)\n"
                f'    n=$(cat "{state}"); n=$((n + 1)); echo "$n" > "{state}"\n'
                f'    if [ "$n" -le {running_polls} ]; then echo true; else echo false; fi ;;\n'
                f"  *'to quit'*) echo quit >> \"{quits}\" ;;\n"
                "esac\n"
                "exit 0\n",
                encoding="utf-8",
            )
            osascript.chmod(0o755)
            for name in ("kill", "killall", "pkill"):
                trap = bin_dir / name
                trap.write_text(f'#!/bin/bash\necho "{name} $*" >> "{forbidden}"\n', encoding="utf-8")
                trap.chmod(0o755)
            script = (
                f'export PATH="{bin_dir}:$PATH"\n'
                f"{env_extra}\n"
                f'. "{REPO_ROOT}/lib/vendor_direct.sh"\n'
                "sleep() { :; }\n"
                'run_with_timeout() { shift; "$@"; }\n'
                "internet_app_quit_gracefully com.test.app\n"
                "echo rc=$?\n"
            )
            proc = run_bash(script)
            count = len(quits.read_text(encoding="utf-8").split()) if quits.exists() else 0
            return proc, count, forbidden.exists()

    def test_quit_is_resent_while_app_keeps_running_then_returns_zero(self) -> None:
        proc, quits, forbidden = self._run_quit(running_polls=14)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("rc=0", proc.stdout)
        self.assertGreater(quits, 1, "an updater-relaunched instance must receive another quit")
        self.assertFalse(forbidden, "force-kill helpers must never be used")

    def test_app_that_never_exits_gets_repeated_quits_and_is_left_running(self) -> None:
        proc, quits, forbidden = self._run_quit(
            running_polls=10_000, env_extra="export MAC_UPDATE_QUIT_WAIT=30 MAC_UPDATE_QUIT_RESEND=10"
        )
        self.assertIn("rc=1", proc.stdout)
        self.assertGreaterEqual(quits, 3)
        self.assertFalse(forbidden)

    def test_app_not_running_needs_no_quit(self) -> None:
        proc, quits, _ = self._run_quit(running_polls=0)
        self.assertIn("rc=0", proc.stdout)
        self.assertEqual(quits, 0)

    def test_zero_wait_sends_a_single_quit(self) -> None:
        proc, quits, _ = self._run_quit(running_polls=10_000, env_extra="export MAC_UPDATE_QUIT_WAIT=0")
        self.assertIn("rc=1", proc.stdout)
        self.assertEqual(quits, 1)

    def test_wait_setting_is_clamped(self) -> None:
        script = (
            f'. "{REPO_ROOT}/lib/vendor_direct.sh"\n'
            "for v in '' abc 7 9999; do MAC_UPDATE_QUIT_WAIT=\"$v\" internet_quit_wait_seconds; done\n"
        )
        proc = run_bash(script)
        self.assertEqual(proc.stdout.split(), ["60", "60", "7", "300"])

    def test_function_never_force_kills(self) -> None:
        text = read("lib/vendor_direct.sh")
        func = text[text.index("internet_app_quit_gracefully() {"):text.index("vendor_direct_host_allowed()")]
        self.assertNotRegex(func, r"\b(kill|killall|pkill)\b\s")


class HonestWarningWordingTests(unittest.TestCase):
    """F6: 'not verified or updated' only when something really is unverified."""

    def _kind(self, soft: int, warn: int, unverified: int) -> str:
        script = (
            f'. "{REPO_ROOT}/lib/internet_status.sh"\n'
            f"internet_soft_summary_kind {soft} {warn} {unverified}\n"
        )
        return run_bash(script).stdout.strip()

    def test_kind_classification(self) -> None:
        self.assertEqual(self._kind(0, 1, 0), "warnings_only")   # feed_stale / quit timeout only
        self.assertEqual(self._kind(0, 1, 2), "generic")         # + an unverified app
        self.assertEqual(self._kind(1, 0, 0), "generic")         # behind / error-class cause
        self.assertEqual(self._kind(1, 1, 0), "generic")
        self.assertEqual(self._kind(0, 0, 0), "none")

    def _closing_block(self, soft=0, stale=0, quit_timeout=0, hard=0, unverified=0) -> subprocess.CompletedProcess:
        text = read("update_internet_apps.sh")
        start = text.index("_warn_only=0\n")
        end = text.index('print_header "$L_INTERNET_SCRIPT_DONE"', start)
        block = text[start:end]
        script = (
            f'. "{REPO_ROOT}/i18n/lang_en.sh"\n'
            f'. "{REPO_ROOT}/lib/internet_status.sh"\n'
            "print_warn() { echo \"WARN: $*\"; }\n"
            "print_info() { echo \"INFO: $*\"; }\n"
            "print_error() { echo \"ERROR: $*\"; }\n"
            f"INTERNET_SOFT_EXIT=10; INTERNET_EXIT=0; INTERNET_HARD_FAIL={hard}\n"
            f"INTERNET_SOFT_FAIL={soft}; INTERNET_FEED_STALE={stale}; INTERNET_QUIT_TIMEOUT={quit_timeout}\n"
            f"_cnt_unverified={unverified}\n"
            f"{block}\n"
            'echo "EXIT=$INTERNET_EXIT"\n'
        )
        proc = run_bash(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc

    def test_feed_stale_only_prints_specific_line_and_stays_soft(self) -> None:
        out = self._closing_block(stale=1).stdout
        self.assertIn("finished with warnings", out)
        self.assertNotIn("was not verified or updated", out)
        self.assertIn("EXIT=10", out)

    def test_quit_timeout_only_prints_specific_line_and_stays_soft(self) -> None:
        out = self._closing_block(quit_timeout=1).stdout
        self.assertIn("finished with warnings", out)
        self.assertNotIn("was not verified or updated", out)
        self.assertIn("EXIT=10", out)

    def test_unverified_app_keeps_generic_line(self) -> None:
        out = self._closing_block(stale=1, unverified=1).stdout
        self.assertIn("was not verified or updated", out)
        self.assertIn("EXIT=10", out)

    def test_real_soft_failure_keeps_generic_line(self) -> None:
        out = self._closing_block(soft=1).stdout
        self.assertIn("was not verified or updated", out)
        self.assertIn("EXIT=10", out)

    def test_clean_run_prints_nothing_and_exits_zero(self) -> None:
        out = self._closing_block().stdout
        self.assertNotIn("WARN", out)
        self.assertIn("EXIT=0", out)

    def test_hard_failure_still_exits_one(self) -> None:
        self.assertIn("EXIT=1", self._closing_block(hard=1, stale=1).stdout)

    def test_feed_stale_code_no_longer_sets_the_generic_soft_flag(self) -> None:
        text = read("update_internet_apps.sh")
        loop = text[text.index("# ── Compute and Persist Internet Counts ──"):text.index("[ \"$_soft_fail_from_codes\"")]
        match = re.search(r"behind\|needs_restart\)\s*\n\s*_soft_fail_from_codes=1", loop)
        self.assertIsNotNone(match, "behind/needs_restart must remain real soft causes")
        stale = re.search(r"feed_stale\)[^;]*?INTERNET_FEED_STALE=1", loop, re.DOTALL)
        self.assertIsNotNone(stale, "feed_stale must only set the warning-only flag")
        self.assertNotIn("feed_stale)\n            _soft_fail_from_codes", loop)

    def test_quit_timeout_does_not_use_the_generic_soft_flag(self) -> None:
        text = read("update_internet_apps.sh")
        quit_fn = text[text.index("quit_toolkit_launched_apps() {"):]
        quit_fn = quit_fn[: quit_fn.index("\n}\n")]
        self.assertIn("INTERNET_QUIT_TIMEOUT=1", quit_fn)
        self.assertNotIn("INTERNET_SOFT_FAIL", quit_fn)

    def test_i18n_keys_present_in_all_languages(self) -> None:
        for lang in LANGS:
            with self.subTest(lang=lang):
                text = read(f"i18n/lang_{lang}.sh")
                self.assertRegex(text, r'(?m)^L_INTERNET_WARNINGS_ONLY="[^"]+"$')
                fmt = re.search(r'(?m)^L_INTERNET_APP_STILL_RUNNING_FMT="([^"]+)"$', text)
                self.assertIsNotNone(fmt)
                self.assertEqual(fmt.group(1).count("%s"), 2, "bundle id and wait seconds")


if __name__ == "__main__":
    unittest.main()
