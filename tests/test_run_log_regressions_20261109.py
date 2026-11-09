"""Regressions for the 2026-11-08/09 run-log and ultra-review findings handled in WP4.

P1-5 (master side)  one confirmation exported to children, capped sudo keep-alive
P1-6 (master side)  advisories.txt -> run summary + closing "Advisories" block
P1-7                build_inventory.sh reported "0 changed fields" after 11 changes
P1-9 / F2           pre-run checks and caffeinate
F4                  installed version + suggested update method for new apps
P2-1                ANSI escape sequences in run logs
P2-4                per-step durations
P2-13               logs/ rotation
P2-2/3              text defects in the closing lines
"""
from __future__ import annotations

import json
import os
import plistlib
import re
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import copy_toolkit, isolate_host_tools, shell_env  # noqa: E402
from test_preflight import base_stubs, write_stub  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))

from inventory import detect_update_method  # noqa: E402
from inventory_sync import minimal_template  # noqa: E402
from log_rotation import plan_rotation, rotate_logs  # noqa: E402
from run_summary import (  # noqa: E402
    build_run_summary,
    format_terminal_summary,
    migrate_run_summary,
    read_advisories,
    read_step_durations,
)

LANGS = ("en", "pl", "es", "it", "pt", "de", "fr")


def read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def lang_keys(lang: str) -> dict[str, str]:
    out = {}
    for line in read(f"i18n/lang_{lang}.sh").splitlines():
        m = re.match(r'^(L_[A-Z0-9_]+)="(.*)"$', line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def make_toolkit_copy(root: Path) -> Path:
    """Tracked toolkit files only (tests/_env.py:copy_toolkit); never private or untracked content."""
    return Path(copy_toolkit(REPO_ROOT, root / "toolkit"))


# ── real runs in a throw-away copy (all steps but the final system step skipped) ──

class RealRunTests(unittest.TestCase):
    SKIPS = ["--skip-appstore", "--skip-npm", "--skip-brew", "--skip-internet", "--skip-prescan", "--skip-postupdate"]

    def run_toolkit(self, root: Path, stubs: Path, args: list[str], system_stub: bool = True, **env_extra: str):
        toolkit = make_toolkit_copy(root)
        marker = root / "system_marker.txt"
        if system_stub:
            (toolkit / "update_system.sh").write_text(
                "#!/usr/bin/env bash\n"
                f'echo "parent_confirmed=${{MAC_UPDATE_PARENT_CONFIRMED:-unset}}" > "{marker}"\n'
                'printf "brew_doctor|info|icu4c@78 is outdated\\n'
                'brew_doctor|security|Root certificates in the system store can trust compromised CAs\\n" '
                '>> "$MAC_UPDATE_SESSION_DIR/advisories.txt"\n'
                "sleep 1\nexit 0\n", encoding="utf-8")
        env = shell_env(MAC_LANG="en", HOME=str(root), TMPDIR=str(root), **env_extra)
        env["PATH"] = f"{stubs}:{env['PATH']}"
        isolate_host_tools(env)
        proc = subprocess.run(["bash", str(toolkit / "update_all.sh"), *args], capture_output=True, text=True,
                              env=env, stdin=subprocess.DEVNULL, timeout=180)
        return toolkit, marker, proc

    def summary(self, toolkit: Path) -> dict:
        return json.loads((toolkit / "logs" / "run_summary_latest.json").read_text(encoding="utf-8"))

    def test_healthy_run_confirmed_logged_without_ansi_advisories_and_durations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stubs = root / "stubs"
            base_stubs(stubs)
            toolkit, marker, proc = self.run_toolkit(root, stubs, ["-y", *self.SKIPS])
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            # P1-5: the master confirmation is exported to the children.
            self.assertEqual(marker.read_text(encoding="utf-8").strip(), "parent_confirmed=1")
            # P2-1: colours on the terminal stream, none in the file.
            self.assertIn("\x1b[", proc.stdout)
            log = next((toolkit / "logs").glob("update_all_*.log")).read_text(encoding="utf-8")
            self.assertNotIn("\x1b", log)
            self.assertIn("Step 6/6", log)
            self.assertIn("ALL UPDATES COMPLETE", log)
            # P2-4: the header time is labelled as total, the step's own time is in the summary line.
            self.assertRegex(proc.stdout, r"Step 6/6: .* \(total \d+s\)")
            self.assertRegex(proc.stdout, r"6\. macOS System:\s+OK.* \(\d+s\)")
            data = self.summary(toolkit)
            self.assertGreaterEqual(data["steps"]["system"]["duration_seconds"], 1)
            self.assertNotIn("duration_seconds", data["steps"]["appstore"], "skipped steps carry no duration")
            # P1-6: advisories reach the machine summary and the closing block, security first.
            self.assertEqual(data["format_version"], 4)
            self.assertEqual([a["severity"] for a in data["advisories"]], ["info", "security"])
            self.assertEqual(data["advisories"][1]["source"], "brew_doctor")
            self.assertIn("Advisories:", proc.stdout)
            self.assertIn("🔒 [SECURITY] Root certificates", proc.stdout)
            block = proc.stdout[proc.stdout.index("Advisories:"):]
            self.assertLess(block.index("[SECURITY]"), block.index("icu4c@78 is outdated"))
            # ...without touching exit codes or the degraded flag.
            self.assertEqual(data["exit_code"], 0)
            self.assertFalse(data["degraded"])

    def test_caffeinate_is_started_for_the_run_and_bound_to_the_shell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stubs = root / "stubs"
            base_stubs(stubs)
            toolkit, marker, proc = self.run_toolkit(root, stubs, ["-y", *self.SKIPS])
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            calls = (stubs / "caffeinate.log").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(calls), 1)
            self.assertRegex(calls[0], r"^-i -w \d+$")

    def test_caffeinate_opt_out_and_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stubs = root / "stubs"
            base_stubs(stubs)
            _, _, proc = self.run_toolkit(root, stubs, ["-y", *self.SKIPS], MAC_UPDATE_NO_CAFFEINATE="1")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertFalse((stubs / "caffeinate.log").exists())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stubs = root / "stubs"
            base_stubs(stubs, net_ok=False, power="battery", pct=5)
            _, _, proc = self.run_toolkit(root, stubs, ["--dry-run", "-y"])
            self.assertEqual(proc.returncode, 0, "dry-run skips every pre-flight check, even a dead network")
            self.assertFalse((stubs / "caffeinate.log").exists())
            self.assertNotIn("No network", proc.stdout)

    def test_low_battery_skips_only_the_system_step_softly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stubs = root / "stubs"
            base_stubs(stubs, power="battery", pct=12)
            toolkit, marker, proc = self.run_toolkit(root, stubs, ["-y", *self.SKIPS])
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertFalse(marker.exists(), "update_system.sh must not run on a nearly empty battery")
            self.assertIn("the macOS system update is skipped in this run", proc.stdout)
            self.assertIn("skipped: battery too low", proc.stdout)
            data = self.summary(toolkit)
            self.assertEqual(data["steps"]["system"]["code"], "skipped")
            self.assertTrue(data["degraded"])
            self.assertEqual(data["exit_code"], 0)
            self.assertNotIn("Step 6/6", proc.stdout)

    def test_battery_check_does_not_apply_when_the_system_step_is_skipped_anyway(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stubs = root / "stubs"
            base_stubs(stubs, power="battery", pct=12)
            toolkit, _, proc = self.run_toolkit(root, stubs, ["-y", "--skip-system", *self.SKIPS])
            self.assertEqual(proc.returncode, 0)
            self.assertFalse(self.summary(toolkit)["degraded"])

    def test_low_disk_degrades_the_run_but_does_not_abort(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stubs = root / "stubs"
            base_stubs(stubs, free_kb=2 * 1024 * 1024)
            toolkit, marker, proc = self.run_toolkit(root, stubs, ["-y", *self.SKIPS])
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertTrue(marker.exists(), "a low disk is a warning, the system step still runs")
            self.assertIn("Low free disk space: 2 GB", proc.stdout)
            data = self.summary(toolkit)
            self.assertTrue(data["degraded"])
            self.assertEqual(data["exit_code"], 0)
            self.assertIn("COMPLETED WITH WARNINGS", proc.stdout)

    def test_no_network_aborts_before_any_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stubs = root / "stubs"
            base_stubs(stubs, net_ok=False)
            toolkit, marker, proc = self.run_toolkit(root, stubs, ["-y", *self.SKIPS])
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("No network: none of the required hosts is reachable over HTTPS", proc.stdout)
            self.assertNotIn("Step 1/6", proc.stdout)
            self.assertFalse(marker.exists())
            self.assertFalse((stubs / "caffeinate.log").exists(), "nothing is kept awake for a run that never starts")

    def test_summary_text_marks_battery_skip_in_the_chronic_summary_not_as_ok(self) -> None:
        # The skipped system step must never be reported as OK.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stubs = root / "stubs"
            base_stubs(stubs, power="battery", pct=12)
            _, _, proc = self.run_toolkit(root, stubs, ["-y", *self.SKIPS])
            self.assertNotRegex(proc.stdout, r"6\. macOS System:\s+OK")


# ── P1-5: sudo keep-alive cap ──

class SudoKeepAliveCapTests(unittest.TestCase):
    def block(self) -> str:
        text = read("update_all.sh")
        return text[text.index("# SUDO ACQUISITION"):text.index("# Tee everything from this point")]

    def clamp(self, value: str | None) -> str:
        text = read("update_all.sh")
        start = text.index('_ka_max="${MAC_UPDATE_SUDO_KEEPALIVE_MAX:-3600}"')
        end = text.index('[ "$_ka_max" -gt 14400 ] && _ka_max=14400') + len('[ "$_ka_max" -gt 14400 ] && _ka_max=14400')
        env = shell_env(MAC_UPDATE_SUDO_KEEPALIVE_MAX=value)
        proc = subprocess.run(["bash", "-c", text[start:end] + '\necho "$_ka_max"'], capture_output=True,
                              text=True, env=env)
        return proc.stdout.strip()

    def test_default_and_clamping(self) -> None:
        self.assertEqual(self.clamp(None), "3600")
        self.assertEqual(self.clamp(""), "3600")
        self.assertEqual(self.clamp("abc"), "3600")
        self.assertEqual(self.clamp("10"), "300")
        self.assertEqual(self.clamp("900"), "900")
        self.assertEqual(self.clamp("999999"), "14400")

    def test_loop_checks_the_deadline_and_keeps_the_rules(self) -> None:
        block = self.block()
        self.assertIn("_macupd_deadline=$(( $(date +%s) + _ka_max ))", block)
        self.assertIn('[ "$(date +%s)" -lt "$_macupd_deadline" ] || exit 0', block)
        # Rules of critical_rules 6c are untouched.
        self.assertEqual(block.count("SUDO_KEEPALIVE_PID=$!"), 1)
        self.assertEqual(block.count('SUDO_KEEPALIVE_PID=""'), 1)
        self.assertIn('[ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ] && _needs_sudo=0', block)
        self.assertIn("export MAC_UPDATE_NO_SUDO=1", block)

    def test_caffeinate_stays_outside_the_sudo_block(self) -> None:
        self.assertNotIn("caffeinate", self.block())
        text = read("update_all.sh")
        self.assertIn("caffeinate -i -w $$", text)
        self.assertIn('"${MAC_UPDATE_NO_CAFFEINATE:-0}" != "1"', text)
        self.assertIn("kill \"$CAFFEINATE_PID\"", text)

    def test_parent_confirmation_is_exported_after_the_confirm_block(self) -> None:
        text = read("update_all.sh")
        confirm = text.index('read -r -p "  $L_CONFIRM_UPDATE [T/n]: " CONFIRM')
        export = text.index("export MAC_UPDATE_PARENT_CONFIRMED=1")
        cancel = text.index('print_info "$L_UPDATE_CANCELED"')
        self.assertLess(confirm, cancel)
        self.assertLess(cancel, export, "a cancelled run exits before the export")


# ── P2-1: ANSI-free run log ──

class LogFilterTests(unittest.TestCase):
    def function(self) -> str:
        m = re.search(r"log_strip_ansi_tee\(\) \{.*?\n\}\n", read("update_all.sh"), re.DOTALL)
        self.assertIsNotNone(m)
        return m.group(0)

    @unittest.skipUnless(shutil.which("perl"), "perl not available")
    def test_strips_escapes_streams_prompts_and_handles_split_sequences(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "run.log"
            log.write_text("", encoding="utf-8")
            proc = subprocess.Popen(
                ["bash", "-c", self.function() + f'\nlog_strip_ansi_tee "{log}"'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            assert proc.stdin and proc.stdout
            chunks = [b"Plain \x1b[1mbold\x1b[0m\n", b"\x1b[0;3", b"4mblue\x1b[0m\n", b"ask? "]
            echoed = b""
            for chunk in chunks:
                proc.stdin.write(chunk)
                proc.stdin.flush()
                if chunk == b"ask? ":
                    ready, _, _ = select.select([proc.stdout], [], [], 5)
                    self.assertTrue(ready, "a prompt without a newline must reach the terminal at once")
                time.sleep(0.05)
            proc.stdin.close()
            echoed = proc.stdout.read()
            proc.stdout.close()
            proc.wait(timeout=10)
            self.assertEqual(echoed, b"".join(chunks), "the terminal stream is byte-identical")
            self.assertEqual(log.read_text(encoding="utf-8"), "Plain bold\nblue\nask? ")

    def test_perl_fallback_keeps_a_log(self) -> None:
        text = read("update_all.sh")
        self.assertIn('exec > >(log_strip_ansi_tee "$LOG_FILE") 2>&1', text)
        self.assertIn('exec > >(tee -a "$LOG_FILE") 2>&1', text)


# ── P2-13: rotation ──

class LogRotationTests(unittest.TestCase):
    def touch(self, path: Path, age: int, now: float) -> None:
        path.write_text("x", encoding="utf-8")
        os.utime(path, (now - age, now - age))

    def test_rotation_covers_logs_summaries_strays_and_protects_state(self) -> None:
        now = time.time()
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp)
            for i in range(5):
                self.touch(logs / f"update_all_2026110{i}_100000.log", 100 * (5 - i), now)
            stamped = [f"run_summary_2026110{i}_100000.json" for i in range(4)]
            for i, name in enumerate(stamped):
                self.touch(logs / name, 100 * (10 - i), now)
            self.touch(logs / "run_summary_1786703174.json", 5000, now)  # epoch-named stray, oldest
            self.touch(logs / "run_summary_debug.json", 4000, now)
            self.touch(logs / "run_summary_latest.json", 99999, now)
            self.touch(logs / "version_history.tsv", 99999, now)
            self.touch(logs / "notes.txt", 99999, now)
            self.touch(logs / ".run_summary_x.json.tmp", 3 * 86400, now)
            self.touch(logs / ".run_summary_y.json.tmp", 60, now)
            removed = set(rotate_logs(logs, keep_logs=3, keep_summaries=3, now=now))
            self.assertEqual(
                removed,
                {"update_all_20261100_100000.log", "update_all_20261101_100000.log",
                 "run_summary_1786703174.json", "run_summary_debug.json", stamped[0], ".run_summary_x.json.tmp"},
            )
            for kept in ("run_summary_latest.json", "version_history.tsv", "notes.txt", ".run_summary_y.json.tmp"):
                self.assertTrue((logs / kept).exists(), kept)
            self.assertEqual(len(list(logs.glob("update_all_*.log"))), 3)
            self.assertEqual(len(list(logs.glob("run_summary_20*.json"))), 3)

    def test_plan_is_read_only_and_missing_directory_is_fine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(plan_rotation(Path(tmp) / "missing", 3, 3), [])
            logs = Path(tmp)
            for i in range(4):
                (logs / f"update_all_{i}.log").write_text("x", encoding="utf-8")
            self.assertEqual(len(plan_rotation(logs, 2, 30)), 2)
            self.assertEqual(len(list(logs.glob("update_all_*.log"))), 4)

    def test_summaries_keep_at_least_thirty_history(self) -> None:
        text = read("update_all.sh")
        self.assertIn("_keep_summaries=$((MAX_LOGS < 30 ? 30 : MAX_LOGS))", text)
        self.assertIn("from log_rotation import rotate_logs", text)
        self.assertNotIn("ls -1t \"$LOGS_DIR\"/update_all_*.log", text)


# ── P1-6 / P2-4: summary fields ──

class SummaryFieldTests(unittest.TestCase):
    def test_read_advisories_tolerates_garbage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(read_advisories(tmp), [])
            self.assertEqual(read_advisories(None), [])
            (Path(tmp) / "advisories.txt").write_text(
                "brew_doctor|security|Root certificates | can trust compromised CAs\n"
                "\n# comment\n"
                "no-separators\n"
                "brew_doctor|security|Root certificates | can trust compromised CAs\n"
                "brew_doctor|weird|unknown severity becomes info\n"
                "||\n"
                "only|two\n", encoding="utf-8")
            got = read_advisories(tmp)
            self.assertEqual(got, [
                {"source": "brew_doctor", "severity": "security", "text": "Root certificates | can trust compromised CAs"},
                {"source": "brew_doctor", "severity": "info", "text": "unknown severity becomes info"},
            ])

    def test_read_step_durations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(read_step_durations(tmp), {})
            (Path(tmp) / "step_durations.txt").write_text("brew=65\nbad=x\ninternet=7\n=3\nbrew=70\n", encoding="utf-8")
            self.assertEqual(read_step_durations(tmp), {"brew": 70, "internet": 7})

    def test_build_run_summary_adds_advisories_and_durations_additively(self) -> None:
        steps = {"brew": "OK", "appstore": "skipped"}
        data = build_run_summary(
            start_time=1, end_time=100, overall_exit=0, degraded=0, blocking_exit=0, step_results=steps,
            step_codes={"brew": "ok", "appstore": "skipped"},
            advisories=[{"source": "s", "severity": "info", "text": "t"}],
            step_durations={"brew": 65, "appstore": 3, "ghost": 9},
        )
        self.assertEqual(data["format_version"], 4)
        self.assertEqual(data["advisories"], [{"source": "s", "severity": "info", "text": "t"}])
        self.assertEqual(data["steps"]["brew"]["duration_seconds"], 65)
        self.assertNotIn("duration_seconds", data["steps"]["appstore"])
        self.assertNotIn("ghost", data["steps"])
        bare = build_run_summary(start_time=1, end_time=2, overall_exit=0, degraded=0, blocking_exit=0, step_results={})
        self.assertEqual(bare["advisories"], [])
        migrated = migrate_run_summary({"steps": {"brew": {"code": "ok", "text": "OK", "duration_seconds": 5}}})
        self.assertEqual(migrated["steps"]["brew"]["duration_seconds"], 5)

    def test_terminal_summary_lists_security_advisories_first_and_marks_them(self) -> None:
        summary = {"items": [], "counts": {}, "flags": {}, "advisories": [
            {"source": "brew_doctor", "severity": "info", "text": "icu4c@78 is deprecated"},
            {"source": "brew_doctor", "severity": "security", "text": "Root certificates can trust compromised CAs"},
        ]}
        out = format_terminal_summary(summary, lang="en")
        self.assertIn("Advisories:", out)
        self.assertLess(out.index("[SECURITY]"), out.index("icu4c@78"))
        self.assertIn("🔒 [SECURITY] Root certificates can trust compromised CAs (brew_doctor)", out)
        pl = format_terminal_summary(summary, lang="pl")
        self.assertIn("Zalecenia:", pl)
        self.assertIn("[BEZPIECZEŃSTWO]", pl)
        self.assertNotIn("Advisories", format_terminal_summary({"items": [], "counts": {}, "flags": {}}, lang="en"))

    def test_inventory_only_terminal_summary_reports_changes_not_updates(self) -> None:
        summary = {"items": [], "flags": {"inventory_only": True},
                   "counts": {"inventory_version_fields_changed": 5,
                              "inventory_entries_added": 2, "inventory_entries_removed": 1}}
        out = format_terminal_summary(summary, lang="en")
        self.assertIn("Inventory version fields changed: 5", out)
        self.assertIn("Inventory entries added: 2, removed: 1", out)
        self.assertNotIn("Updated:", out)
        self.assertNotIn("Still pending", out)


# ── F4: update-method detection ──

class UpdateMethodDetectionTests(unittest.TestCase):
    def bundle(self, root: Path, name: str, info: dict | None = None) -> Path:
        app = root / f"{name}.app"
        (app / "Contents").mkdir(parents=True)
        if info is not None:
            with open(app / "Contents" / "Info.plist", "wb") as handle:
                plistlib.dump(info, handle)
        return app

    def test_sparkle_feed_reports_host_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = self.bundle(Path(tmp), "A", {"SUFeedURL": "https://updates.example.com/path/appcast.xml?token=secret"})
            got = detect_update_method(app)
            self.assertEqual(got["method"], "sparkle")
            self.assertEqual(got["label"], "sparkle (feed updates.example.com)")
            self.assertNotIn("secret", got["label"])

    def test_sparkle_framework_without_feed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = self.bundle(Path(tmp), "A", {})
            (app / "Contents" / "Frameworks" / "Sparkle.framework").mkdir(parents=True)
            self.assertEqual(detect_update_method(app)["method"], "sparkle")

    def test_electron_updater_reports_provider_and_host_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = self.bundle(Path(tmp), "E", {})
            res = app / "Contents" / "Resources"
            res.mkdir(parents=True)
            (res / "app-update.yml").write_text(
                "provider: generic\nurl: https://dl.example.org/releases/secret-path\nupdaterCacheDirName: x\n",
                encoding="utf-8")
            got = detect_update_method(app)
            self.assertEqual(got["method"], "electron-updater")
            self.assertEqual(got["label"], "electron-updater (generic dl.example.org)")
            self.assertNotIn("secret-path", got["label"])
            (res / "app-update.yml").write_text("provider: github\nowner: someone\nrepo: thing\n", encoding="utf-8")
            self.assertEqual(detect_update_method(app)["label"], "electron-updater (github)")

    def test_squirrel_mas_and_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sq = self.bundle(root, "S", {})
            (sq / "Contents" / "Frameworks" / "Squirrel.framework").mkdir(parents=True)
            self.assertEqual(detect_update_method(sq)["method"], "squirrel")
            mas = self.bundle(root, "M", {"SUFeedURL": "https://ignored.example.com/x"})
            (mas / "Contents" / "_MASReceipt").mkdir()
            self.assertEqual(detect_update_method(mas)["method"], "mas")
            self.assertEqual(detect_update_method(self.bundle(root, "U", {}))["method"], "unknown")
            self.assertEqual(detect_update_method(root / "Missing.app")["label"], "unknown")

    def test_detection_never_executes_or_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = self.bundle(Path(tmp), "A", {"SUFeedURL": "https://x.example.com/a"})
            before = sorted(str(p) for p in Path(tmp).rglob("*"))
            detect_update_method(app)
            self.assertEqual(sorted(str(p) for p in Path(tmp).rglob("*")), before)


# ── P1-7: the inventory-only counts (root cause) ──

class InventoryHonestyTests(unittest.TestCase):
    """Drives the real prescan.py / postupdate.py heredocs of update_all.sh."""

    @staticmethod
    def heredoc(name: str) -> str:
        text = read("update_all.sh")
        return text.split(f"cat > \"$SESSION_DIR/{name}.py\" << 'PYEOF'\n")[1].split("\nPYEOF")[0]

    def setup_workspace(self, root: Path) -> tuple[Path, Path, Path, dict]:
        script_dir = root / "toolkit"
        copy_toolkit(REPO_ROOT, script_dir)
        (script_dir / "config" / "npm_global_clis.txt").write_text("# no CLIs in the fixture\n", encoding="utf-8")
        apps = root / "Applications"
        apps.mkdir()
        bundles = {
            "Newbie": {"CFBundleShortVersionString": "3.1", "SUFeedURL": "https://updates.example.com/appcast.xml"},
            "Zed": {"CFBundleShortVersionString": "1.1"},
        }
        for name, info in bundles.items():
            (apps / f"{name}.app" / "Contents").mkdir(parents=True)
            with open(apps / f"{name}.app" / "Contents" / "Info.plist", "wb") as handle:
                plistlib.dump(info, handle)
        (apps / "Electro.app" / "Contents" / "Resources").mkdir(parents=True)
        (apps / "Electro.app" / "Contents" / "Resources" / "app-update.yml").write_text(
            "provider: generic\nurl: https://dl.example.org/x\n", encoding="utf-8")
        md = minimal_template(script_dir=str(script_dir), user="u", os_label="macOS 27", build="X",
                              home="/h", today="2026-01-01")
        md = md.replace("| Nazwa | Wersja |\n|-------|--------|\n",
                        "| Nazwa | Wersja |\n|-------|--------|\n| Calc | 1.0 |\n| Zed | 1.0 |\n", 1)
        (script_dir / "APPLICATIONS.md").write_text(md, encoding="utf-8")
        session = root / "session"
        session.mkdir()
        env = isolate_host_tools(shell_env(HOME=str(root), MAC_UPDATE_APP_DIRS=str(apps), MAC_UPDATE_INVENTORY_ONLY="1"))
        for key, value in lang_keys("en").items():
            env[key] = value
        return script_dir, session, apps, env

    def run_py(self, code: str, args: list, env: dict) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-c", code, *args], capture_output=True, text=True, env=env, timeout=120)

    def test_inventory_only_writes_real_counts_and_new_app_hints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script_dir, session, apps, env = self.setup_workspace(root)
            prescan = session / "prescan.py"
            prescan.write_text(self.heredoc("prescan"), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(prescan), str(script_dir), str(session)],
                                  capture_output=True, text=True, env=env, timeout=120)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            # F4: the console line carries the suggested update method.
            self.assertRegex(proc.stdout, r"→ Newbie.* — suggested update method: sparkle \(feed updates\.example\.com\)")
            self.assertRegex(proc.stdout, r"→ Electro.* — suggested update method: electron-updater \(generic dl\.example\.org\)")
            md = (script_dir / "APPLICATIONS.md").read_text(encoding="utf-8")
            row = next(line for line in md.splitlines() if line.startswith("| Newbie"))
            self.assertIn("🆕 do skategoryzowania", row, "column 2 keeps the marker the removed-app check relies on")
            self.assertIn("sparkle (feed updates.example.com)", row)
            self.assertEqual(len([c for c in row.split("|") if c.strip()]), 3, "still a 3-column row")
            self.assertEqual(
                json.loads((session / "inventory_apps.json").read_text(encoding="utf-8"))["added"],
                ["app:Electro", "app:Newbie"])

            # Step 5 snapshot: Zed 1.0 -> 1.1, Calc 1.0 -> 2.0 and the two new rows (their marker must survive).
            (session / "installed_apps_after.txt").write_text("Calc|2.0\nNewbie|3.1\nZed|1.1\nElectro|?\n", encoding="utf-8")
            postupdate = session / "postupdate.py"
            postupdate.write_text(self.heredoc("postupdate"), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(postupdate), str(script_dir), str(session), "a", "b", "c", "d", "e"],
                                  capture_output=True, text=True, env=env, timeout=120)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("zmieniono 2 wersji", proc.stdout)
            counts = json.loads((session / "run_counts.json").read_text(encoding="utf-8"))
            # The bug: this file was never written in inventory-only mode, so the summary said 0.
            self.assertEqual(counts["inventory_version_fields_changed"], 2)
            self.assertEqual(counts["inventory_entries_added"], 2)
            self.assertEqual(counts["inventory_entries_removed"], 0)
            self.assertEqual((session / "inventory_counts.txt").read_text(encoding="utf-8").split(), ["2", "2", "0"])
            final_md = (script_dir / "APPLICATIONS.md").read_text(encoding="utf-8")
            self.assertIn("| Newbie | 🆕 do skategoryzowania |", final_md, "a new row is not a changed version field")

    def test_postupdate_writes_counts_before_the_inventory_only_exit(self) -> None:
        text = read("update_all.sh")
        exit_at = text.index("if os.environ.get('MAC_UPDATE_INVENTORY_ONLY') == '1':\n    _write_run_counts()")
        self.assertLess(text.index("def _write_run_counts():"), exit_at)
        # The counts block no longer lives after the early exit.
        self.assertNotIn('_counts_path = os.path.join(session_dir, "run_counts.json")', text)

    def test_banner_and_closing_line_are_inventory_specific_and_localized(self) -> None:
        text = read("update_all.sh")
        self.assertIn('_summary_msg="$L_ALL_INVENTORY_BANNER"', text)
        self.assertIn("L_ALL_INVENTORY_DONE_FMT", text)
        self.assertNotIn("Inventory refreshed: APPLICATIONS.md (UPDATES.md", text)
        for lang in LANGS:
            keys = lang_keys(lang)
            self.assertNotEqual(keys["L_ALL_INVENTORY_BANNER"], keys["L_UPDATE_ALL_SUCCESS"], lang)
        self.assertIn("Inventory refreshed", lang_keys("en")["L_ALL_INVENTORY_DONE_FMT"])
        self.assertNotIn("Inventory refreshed", lang_keys("pl")["L_ALL_INVENTORY_DONE_FMT"])

    @unittest.skipUnless(shutil.which("defaults") and shutil.which("lipo"), "macOS tools required")
    def test_build_inventory_end_to_end_reports_the_real_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script_dir, _, apps, _ = self.setup_workspace(root)
            toolkit = make_toolkit_copy(root / "run")  # fresh copy with the shell side
            (toolkit / "APPLICATIONS.md").write_text((script_dir / "APPLICATIONS.md").read_text(encoding="utf-8"), encoding="utf-8")
            (toolkit / "config" / "npm_global_clis.txt").write_text("# none\n", encoding="utf-8")
            stubs = root / "stubs"
            base_stubs(stubs)
            write_stub(stubs, "brew", "exit 0")
            write_stub(stubs, "mas", "exit 1")
            env = shell_env(MAC_LANG="en", HOME=str(root), TMPDIR=str(root), MAC_UPDATE_APP_DIRS=str(apps))
            env["PATH"] = f"{stubs}:{env['PATH']}"
            proc = subprocess.run(["bash", str(toolkit / "build_inventory.sh")], capture_output=True, text=True,
                                  env=env, stdin=subprocess.DEVNULL, timeout=180)
            out = proc.stdout
            self.assertEqual(proc.returncode, 0, out + proc.stderr)
            self.assertIn("INVENTORY REFRESHED", out)
            self.assertNotIn("ALL UPDATES COMPLETE", out)
            self.assertRegex(out, r"Inventory refreshed: [1-9]\d* version field\(s\) changed, 2 new entries added, 0 removed")
            self.assertRegex(out, r"Inventory version fields changed: [1-9]")
            self.assertIn("Inventory entries added: 2, removed: 0", out)
            self.assertNotIn("Inventory version fields changed: 0", out)


class CopyToolkitHelperTests(unittest.TestCase):
    """tests/_env.py:copy_toolkit must not depend on whatever else lives in the checkout."""

    def build_checkout(self, root: Path) -> Path:
        repo = root / "checkout"
        for rel, body in {
            "update_all.sh": "#!/bin/sh\n", "VERSION": "1.0.0\n", "lib/a.sh": "a\n", "lib/python/m.py": "m\n",
            "config/c.txt": "c\n", "i18n/lang_en.sh": "L_X=1\n", "scripts/s.sh": "s\n", "templates/t": "t\n",
            "tests/t.py": "t\n", "docs/d.md": "d\n",
            # private / untracked-style content that must never be copied
            "APPLICATIONS.md": "private\n", "UPDATES.md": "private\n", ".env": "SECRET=1\n", ".env.local": "x\n",
            "logs/run.log": "log\n", "scratch/n.txt": "n\n", ".claude/settings.json": "{}\n",
            "skills/live/x/SKILL.md": "x\n", ".antigravitycli/1.json": "{}\n",
        }.items():
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        os.symlink(root / "does-not-exist", repo / "lib" / "dangling")
        os.symlink(root / "does-not-exist", repo / "skills" / "dangling")
        os.symlink(root / "does-not-exist", repo / ".agents-skills")
        return repo

    def assert_copy(self, out: Path) -> None:
        for rel in ("update_all.sh", "VERSION", "lib/a.sh", "lib/python/m.py", "config/c.txt",
                    "i18n/lang_en.sh", "scripts/s.sh", "templates/t"):
            self.assertTrue((out / rel).is_file(), rel)
        for rel in ("APPLICATIONS.md", "UPDATES.md", ".env", ".env.local", "logs", "scratch", ".claude",
                    "skills", ".antigravitycli", "tests", "docs", "lib/dangling", ".agents-skills"):
            self.assertFalse(os.path.lexists(out / rel), rel)

    def test_fallback_without_git_ignores_private_content_and_dangling_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.build_checkout(Path(tmp))  # not a git repository: allowlist path
            self.assert_copy(Path(copy_toolkit(repo, Path(tmp) / "out")))

    @unittest.skipUnless(shutil.which("git"), "git not available")
    def test_tracked_files_only_when_git_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.build_checkout(Path(tmp))
            env = shell_env(GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null")
            for args in (["init", "-q"], ["add", "update_all.sh", "VERSION", "lib/a.sh", "lib/python/m.py",
                                           "config/c.txt", "i18n/lang_en.sh", "scripts/s.sh", "templates/t",
                                           "APPLICATIONS.md", "logs/run.log"]):
                subprocess.run(["git", "-C", str(repo), *args], env=env, check=True, capture_output=True)
            out = Path(copy_toolkit(repo, Path(tmp) / "out"))
            self.assert_copy(out)  # tracked-but-private files (APPLICATIONS.md, logs/) are still refused
            (repo / "lib" / "untracked.sh").write_text("u\n", encoding="utf-8")
            again = Path(copy_toolkit(repo, Path(tmp) / "out2"))
            self.assertFalse((again / "lib" / "untracked.sh").exists(), "untracked files are never copied")


class TextAndDocsTests(unittest.TestCase):
    def test_new_keys_exist_in_every_language_with_matching_placeholders(self) -> None:
        en = lang_keys("en")
        wanted = [k for k in en if k.startswith(("L_DOCTOR_", "L_PREFLIGHT_"))] + [
            "L_ALL_SYSTEM_SKIPPED_BATTERY", "L_ALL_STEP_ELAPSED_TOTAL_FMT", "L_ALL_INVENTORY_BANNER",
            "L_ALL_INVENTORY_BANNER_WARN", "L_ALL_INVENTORY_BANNER_ERROR", "L_ALL_INVENTORY_DONE_FMT",
            "L_ALL_SUMMARY_INVENTORY_APPS", "L_ALL_SUMMARY_ADVISORIES_TITLE", "L_ALL_SUMMARY_ADVISORY_SECURITY_TAG",
        ]
        self.assertGreater(len(wanted), 40)
        for lang in LANGS:
            keys = lang_keys(lang)
            for key in wanted:
                self.assertIn(key, keys, f"{lang} missing {key}")
                self.assertEqual(keys[key].count("%s"), en[key].count("%s"), f"{lang} {key}")
                self.assertTrue(keys[key].strip(), f"{lang} {key} is empty")

    def test_prescan_new_app_method_keys_exist(self) -> None:
        for lang in LANGS:
            keys = lang_keys(lang)
            self.assertEqual(keys["L_PRESCAN_NEW_APP_METHOD_FMT"].count("%s"), 1)
            self.assertNotIn("%s", keys["L_PRESCAN_NEW_APP_METHOD_UNKNOWN"])

    def test_new_files_and_env_vars_are_documented(self) -> None:
        doc = read("docs/agents/scripts.md")
        for needle in ("lib/preflight.sh", "lib/python/log_rotation.py", "MAC_UPDATE_MIN_FREE_GB",
                       "MAC_UPDATE_MIN_BATTERY", "MAC_UPDATE_NO_CAFFEINATE", "MAC_UPDATE_SUDO_KEEPALIVE_MAX",
                       "MAC_UPDATE_PARENT_CONFIRMED", "--doctor"):
            self.assertIn(needle, doc)


if __name__ == "__main__":
    unittest.main()
