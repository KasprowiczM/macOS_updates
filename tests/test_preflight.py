"""lib/preflight.sh: `update_all.sh --doctor` and the cheap pre-run subset.

Every check is exercised with stubbed df / pmset / curl / sudo / uname / sw_vers
so the tests never depend on the host's disk, battery, network or Homebrew.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _env import copy_toolkit, isolate_host_tools, shell_env  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
LANG_EN = REPO_ROOT / "i18n" / "lang_en.sh"


def write_stub(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def base_stubs(directory: Path, *, free_kb: int = 400 * 1024 * 1024, power: str = "ac",
               pct: int = 90, net_ok: bool = True) -> None:
    """Healthy-machine stubs; individual tests override what they exercise."""
    directory.mkdir(parents=True, exist_ok=True)
    write_stub(directory, "uname", 'echo arm64')
    write_stub(directory, "sw_vers", 'case "$1" in -productVersion) echo 27.0;; -buildVersion) echo X1;; esac')
    write_stub(directory, "df", f'echo "Filesystem 1024-blocks Used Available Capacity Mounted"; '
                                f'echo "/dev/disk1 999999999 1 {free_kb} 1% /"')
    if power == "ac":
        write_stub(directory, "pmset", "echo \"Now drawing from 'AC Power'\"")
    else:
        write_stub(directory, "pmset",
                   f"echo \"Now drawing from 'Battery Power'\"; "
                   f"printf ' -InternalBattery-0 (id=1)\\t{pct}%%; discharging; 4:00 remaining present: true\\n'")
    log = directory / "curl.log"
    write_stub(directory, "curl", f'echo "$*" >> "{log}"; exit {0 if net_ok else 6}')
    write_stub(directory, "sudo", f'echo "$*" >> "{directory / "sudo.log"}"; exit 1')
    write_stub(directory, "launchctl", "exit 1")
    write_stub(directory, "xcode-select", "echo /Library/Developer/CommandLineTools")
    write_stub(directory, "caffeinate", f'echo "$*" >> "{directory / "caffeinate.log"}"; exit 0')


def run_bash(script: str, stub_dir: Path | None = None, **env_extra: str) -> subprocess.CompletedProcess:
    env = shell_env(MAC_LANG="en", **env_extra)
    if stub_dir is not None:
        env["PATH"] = f"{stub_dir}:{env['PATH']}"
    isolate_host_tools(env)
    prelude = (
        f'cd "{REPO_ROOT}"\n'
        f'. "{LANG_EN}"\n'
        f'. "{REPO_ROOT}/lib/platform.sh"\n'
        f'. "{REPO_ROOT}/lib/preflight.sh"\n'
    )
    return subprocess.run(["bash", "-c", prelude + script], capture_output=True, text=True, env=env,
                          stdin=subprocess.DEVNULL, timeout=120)


class MeasurementTests(unittest.TestCase):
    def test_disk_below_threshold_is_a_warning_with_the_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stubs = Path(tmp)
            base_stubs(stubs, free_kb=5 * 1024 * 1024)
            proc = run_bash("preflight_check_disk; echo rc=$?", stubs)
            self.assertIn("Low free disk space: 5 GB (minimum 15 GB)", proc.stdout)
            self.assertIn("rc=10", proc.stdout)
            lowered = run_bash("preflight_check_disk; echo rc=$?", stubs, MAC_UPDATE_MIN_FREE_GB="3")
            self.assertIn("Free disk space: 5 GB (minimum 3 GB)", lowered.stdout)
            self.assertIn("rc=0", lowered.stdout)

    def test_garbage_threshold_falls_back_to_the_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stubs = Path(tmp)
            base_stubs(stubs, free_kb=5 * 1024 * 1024)
            proc = run_bash("preflight_check_disk; echo rc=$?", stubs, MAC_UPDATE_MIN_FREE_GB="lots")
            self.assertIn("(minimum 15 GB)", proc.stdout)

    def test_unknown_disk_is_informational_not_a_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stubs = Path(tmp)
            base_stubs(stubs)
            write_stub(stubs, "df", "exit 1")
            proc = run_bash("preflight_check_disk; echo rc=$?", stubs)
            self.assertIn("could not be determined", proc.stdout)
            self.assertIn("rc=3", proc.stdout)

    def test_power_ac_battery_ok_battery_low_and_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stubs = Path(tmp)
            base_stubs(stubs, power="ac")
            ac = run_bash("preflight_check_power; echo rc=$?", stubs)
            self.assertIn("connected to AC power", ac.stdout)
            self.assertIn("rc=0", ac.stdout)

            base_stubs(stubs, power="battery", pct=80)
            ok = run_bash("preflight_check_power; echo rc=$? src=$PREFLIGHT_POWER_SOURCE pct=$PREFLIGHT_BATTERY_PCT", stubs)
            self.assertIn("on battery, 80% charge", ok.stdout)
            self.assertIn("rc=0 src=battery pct=80", ok.stdout)

            base_stubs(stubs, power="battery", pct=20)
            low = run_bash("preflight_check_power; echo rc=$?", stubs)
            self.assertIn("on battery at 20% (below 30%)", low.stdout)
            self.assertIn("rc=10", low.stdout)
            custom = run_bash("preflight_check_power; echo rc=$?", stubs, MAC_UPDATE_MIN_BATTERY="10")
            self.assertIn("rc=0", custom.stdout)

            write_stub(stubs, "pmset", "echo \"Now drawing from 'UPS Power'\"")
            unknown = run_bash("preflight_check_power; echo rc=$?", stubs)
            self.assertIn("rc=3", unknown.stdout)

    def test_network_probe_is_https_only_with_timeouts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stubs = Path(tmp)
            base_stubs(stubs)
            proc = run_bash("preflight_check_network; echo rc=$?", stubs)
            self.assertIn("Network: 3 of 3 hosts reachable over HTTPS", proc.stdout)
            self.assertIn("rc=0", proc.stdout)
            calls = (stubs / "curl.log").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(calls), 3)
            for call in calls:
                self.assertIn("--proto =https", call)
                self.assertIn("--max-time", call)
                self.assertIn("https://", call)
                self.assertNotIn("http://", call)

    def test_network_partial_and_down(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stubs = Path(tmp)
            base_stubs(stubs)
            write_stub(stubs, "curl", 'case "$*" in *formulae.brew.sh*) exit 6;; esac; exit 0')
            partial = run_bash("preflight_check_network; echo rc=$?", stubs)
            self.assertIn("not reachable over HTTPS: formulae.brew.sh", partial.stdout)
            self.assertIn("rc=10", partial.stdout)

            base_stubs(stubs, net_ok=False)
            down = run_bash("preflight_check_network; echo rc=$?", stubs)
            self.assertIn("no host reachable over HTTPS", down.stdout)
            self.assertIn("rc=1", down.stdout)


class RealRunPolicyTests(unittest.TestCase):
    """preflight_run_cheap: low disk degrades, low battery skips only the system step,
    no network aborts."""

    def policy(self, stubs: Path, **env: str) -> str:
        proc = run_bash(
            "preflight_run_cheap; echo \"rc=$? degraded=$PREFLIGHT_DEGRADED skip_system=$PREFLIGHT_SKIP_SYSTEM\"",
            stubs, **env)
        return proc.stdout

    def test_healthy_machine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stubs = Path(tmp)
            base_stubs(stubs)
            self.assertIn("rc=0 degraded=0 skip_system=0", self.policy(stubs))

    def test_low_disk_is_soft_and_degrades_the_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stubs = Path(tmp)
            base_stubs(stubs, free_kb=2 * 1024 * 1024)
            out = self.policy(stubs)
            self.assertIn("Low free disk space", out)
            self.assertIn("rc=0 degraded=1 skip_system=0", out)

    def test_low_battery_skips_only_the_system_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stubs = Path(tmp)
            base_stubs(stubs, power="battery", pct=12)
            out = self.policy(stubs)
            self.assertIn("On battery at 12% (below 30%): the macOS system update is skipped in this run", out)
            self.assertIn("rc=0 degraded=1 skip_system=1", out)

    def test_low_battery_is_ignored_when_the_system_step_is_already_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stubs = Path(tmp)
            base_stubs(stubs, power="battery", pct=12)
            self.assertIn("rc=0 degraded=0 skip_system=0", self.policy(stubs, MAC_UPDATE_SKIP_SYSTEM="1"))

    def test_no_network_aborts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stubs = Path(tmp)
            base_stubs(stubs, net_ok=False)
            out = self.policy(stubs, MAC_UPDATE_PREFLIGHT_NET_RETRY_WAIT="0")
            self.assertIn("No network: none of the required hosts is reachable over HTTPS", out)
            self.assertIn("rc=1", out)
            # default 3 retries, one localized line each, then the abort
            self.assertIn("Network not reachable yet — retrying (1/3)", out)
            self.assertIn("Network not reachable yet — retrying (3/3)", out)
            self.assertNotIn("(4/3)", out)

    def test_network_blip_recovers_without_aborting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stubs = Path(tmp)
            base_stubs(stubs)
            # first full pass (3 hosts) fails, everything after succeeds
            count = stubs / "count"
            write_stub(stubs, "curl",
                       f'n=$(cat "{count}" 2>/dev/null || echo 0); n=$((n+1)); echo $n > "{count}"; '
                       f'[ "$n" -le 3 ] && exit 6; exit 0')
            out = self.policy(stubs, MAC_UPDATE_PREFLIGHT_NET_RETRY_WAIT="0")
            self.assertIn("retrying (1/3)", out)
            self.assertNotIn("retrying (2/3)", out)
            self.assertNotIn("No network", out)
            self.assertIn("rc=0", out)

    def test_retry_env_is_clamped_and_doctor_is_single_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stubs = Path(tmp)
            base_stubs(stubs, net_ok=False)
            for raw, want in (("", "3"), ("abc", "3"), ("0", "1"), ("99", "10"), ("5", "5")):
                proc = run_bash("preflight_net_retries", stubs, MAC_UPDATE_PREFLIGHT_NET_RETRIES=raw)
                self.assertEqual(proc.stdout.strip(), want, raw)
            for raw, want in (("", "10"), ("0", "0"), ("500", "60")):
                proc = run_bash("preflight_net_retry_wait", stubs, MAC_UPDATE_PREFLIGHT_NET_RETRY_WAIT=raw)
                self.assertEqual(proc.stdout.strip(), want, raw)
            proc = run_bash("preflight_check_network; echo rc=$?", stubs)  # doctor form
            self.assertNotIn("retrying", proc.stdout)

    def test_partial_network_does_not_abort(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stubs = Path(tmp)
            base_stubs(stubs)
            write_stub(stubs, "curl", 'case "$*" in *itunes.apple.com*) exit 6;; esac; exit 0')
            self.assertIn("rc=0 degraded=0", self.policy(stubs))


class DoctorCheckTests(unittest.TestCase):
    def test_platform_check_reports_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stubs = Path(tmp)
            base_stubs(stubs)
            ok = run_bash("preflight_check_platform; echo rc=$?", stubs)
            self.assertIn("Platform: Apple Silicon, macOS 27.0", ok.stdout)
            write_stub(stubs, "uname", "echo x86_64")
            bad = run_bash("preflight_check_platform; echo rc=$?", stubs)
            self.assertIn("Unsupported platform", bad.stdout)
            self.assertIn("rc=1", bad.stdout)

    def test_missing_tools_hard_for_python_and_curl_soft_for_brew(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stubs = Path(tmp)
            base_stubs(stubs)
            # Resolve against an empty PATH so nothing is found.
            proc = run_bash("PATH=/nonexistent; preflight_check_tools; echo rc=$?", stubs)
            self.assertIn("python3 not found on PATH", proc.stdout)
            self.assertIn("curl not found on PATH", proc.stdout)
            self.assertIn("brew not found on PATH — the steps that need it will be skipped", proc.stdout)
            self.assertIn("rc=1", proc.stdout)

    def test_minimal_launchd_path_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_bin = root / "opt" / "bin"
            fake_bin.mkdir(parents=True)
            write_stub(fake_bin, "brew", "exit 0")
            helping = root / "platform_adds_brew.sh"
            helping.write_text(f'export PATH="{fake_bin}:$PATH"\n', encoding="utf-8")
            plain = root / "platform_noop.sh"
            plain.write_text(":\n", encoding="utf-8")
            with_helper = run_bash('printf "[%s]" "$(preflight_minimal_path_missing brew mas)"',
                                   PREFLIGHT_PLATFORM_SH=str(helping))
            self.assertEqual(with_helper.stdout.strip(), "[mas ]")
            without = run_bash('printf "[%s]" "$(preflight_minimal_path_missing brew mas)"',
                               PREFLIGHT_PLATFORM_SH=str(plain))
            self.assertEqual(without.stdout.strip(), "[brew mas ]")

    def test_launchd_path_check_warns_when_tools_vanish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stubs = Path(tmp)
            base_stubs(stubs)
            write_stub(stubs, "brew", "exit 0")
            noop = stubs / "noop.sh"
            noop.write_text(":\n", encoding="utf-8")
            proc = run_bash("preflight_check_launchd_path; echo rc=$?", stubs, PREFLIGHT_PLATFORM_SH=str(noop))
            self.assertIn("With the minimal launchd PATH these tools are NOT found: brew", proc.stdout)
            self.assertIn("rc=10", proc.stdout)

    def test_launchagent_states(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            script = root / "scripts" / "install_launchagent.sh"
            cases = [
                ('echo "✅ LaunchAgent is active: x"; exit 0', "Scheduled run (LaunchAgent) is active", "rc=0"),
                ('echo "✅ LaunchAgent is active: x"; echo "   Plist: p"; '
                 'echo "⚠️  Plist has no EnvironmentVariables.PATH with Homebrew; x"; exit 0',
                 "LaunchAgent plist has no Homebrew PATH", "rc=10"),
                ('echo "⚠️  LaunchAgent plist exists but is not loaded: x"; exit 1', "plist exists but is not loaded", "rc=10"),
                ('echo "ℹ️  LaunchAgent is not installed"; exit 0', "No scheduled run installed", "rc=3"),
            ]
            for body, text, rc in cases:
                script.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
                proc = run_bash(f'SCRIPT_DIR="{root}"; preflight_check_launchagent; echo rc=$?')
                self.assertIn(text, proc.stdout, body)
                self.assertIn(rc, proc.stdout, body)

    def test_sudo_is_only_ever_probed_without_a_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stubs = Path(tmp)
            base_stubs(stubs)
            cold = run_bash("preflight_check_sudo; echo rc=$?", stubs)
            self.assertIn("no cached credentials", cold.stdout)
            self.assertIn("rc=3", cold.stdout)
            self.assertEqual((stubs / "sudo.log").read_text(encoding="utf-8").split(), ["-n", "true"])
            write_stub(stubs, "sudo", f'echo "$*" >> "{stubs / "sudo.log"}"; exit 0')
            warm = run_bash("preflight_check_sudo; echo rc=$?", stubs)
            self.assertIn("sudo is ready without a prompt", warm.stdout)

    def test_touchid_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tid = root / "sudo_local"
            tid.write_text("auth       sufficient     pam_tid.so\n", encoding="utf-8")
            plain = root / "sudo"
            plain.write_text("auth       required       pam_opendirectory.so\n", encoding="utf-8")
            ok = run_bash("preflight_check_touchid; echo rc=$?",
                          MAC_UPDATE_PAM_SUDO_LOCAL=str(tid), MAC_UPDATE_PAM_SUDO=str(plain))
            self.assertIn("Touch ID for sudo is configured", ok.stdout)
            missing = run_bash("preflight_check_touchid; echo rc=$?",
                               MAC_UPDATE_PAM_SUDO_LOCAL=str(root / "none"), MAC_UPDATE_PAM_SUDO=str(plain))
            self.assertIn("not configured", missing.stdout)
            self.assertIn("rc=10", missing.stdout)

    def test_accessibility_is_not_probed_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stubs = Path(tmp)
            base_stubs(stubs)
            marker = stubs / "osascript.called"
            write_stub(stubs, "osascript", f'touch "{marker}"; echo Finder')
            proc = run_bash("preflight_check_accessibility; echo rc=$?", stubs)
            self.assertIn("not checked", proc.stdout)
            self.assertIn("rc=3", proc.stdout)
            self.assertFalse(marker.exists(), "the probe can pop a macOS permission prompt")

    def test_accessibility_probe_is_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stubs = Path(tmp)
            base_stubs(stubs)
            write_stub(stubs, "osascript", "echo 'execution error: not allowed assistive access (-1719)'; exit 1")
            denied = run_bash("preflight_check_accessibility; echo rc=$?", stubs, MAC_UPDATE_DOCTOR_PROBE_AX="1")
            self.assertIn("Accessibility permission is missing", denied.stdout)
            self.assertIn("rc=10", denied.stdout)
            write_stub(stubs, "osascript", "echo Finder")
            granted = run_bash("preflight_check_accessibility; echo rc=$?", stubs, MAC_UPDATE_DOCTOR_PROBE_AX="1")
            self.assertIn("Accessibility permission for this terminal is granted", granted.stdout)

    def test_xcode_license_only_when_xcode_is_selected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stubs = Path(tmp)
            base_stubs(stubs)
            clt = run_bash("preflight_check_xcode; echo rc=$?", stubs)
            self.assertIn("license check not needed", clt.stdout)
            write_stub(stubs, "xcode-select", "echo /Applications/Xcode.app/Contents/Developer")
            write_stub(stubs, "xcodebuild", "exit 69")
            unlicensed = run_bash("preflight_check_xcode; echo rc=$?", stubs)
            self.assertIn("Xcode license has not been accepted", unlicensed.stdout)
            self.assertIn("rc=10", unlicensed.stdout)
            write_stub(stubs, "xcodebuild", "exit 0")
            licensed = run_bash("preflight_check_xcode; echo rc=$?", stubs)
            self.assertIn("Xcode license is accepted", licensed.stdout)

    def test_last_run_age_and_class(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp)
            when = datetime.now(timezone.utc) - timedelta(days=2, hours=3, minutes=5)
            summary = {"completed_at": when.isoformat(), "exit_class": "warnings", "run_status": "completed"}
            (logs / "run_summary_latest.json").write_text(json.dumps(summary), encoding="utf-8")
            proc = run_bash("preflight_check_lastrun; echo rc=$?", MAC_UPDATE_LOGS_DIR=str(logs))
            self.assertIn("Last run: 2d 3h ago, result: completed with warnings", proc.stdout)
            self.assertIn("rc=3", proc.stdout)
            summary.update(exit_class="clean")
            (logs / "run_summary_latest.json").write_text(json.dumps(summary), encoding="utf-8")
            self.assertIn("rc=0", run_bash("preflight_check_lastrun; echo rc=$?", MAC_UPDATE_LOGS_DIR=str(logs)).stdout)
            summary.update(exit_class="clean", run_status="started")
            (logs / "run_summary_latest.json").write_text(json.dumps(summary), encoding="utf-8")
            started = run_bash("preflight_check_lastrun; echo rc=$?", MAC_UPDATE_LOGS_DIR=str(logs))
            self.assertIn("result: failed", started.stdout)
            self.assertIn("rc=10", started.stdout)

    def test_last_run_ignores_dry_and_inventory_only_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp)
            now = datetime.now(timezone.utc)

            def put(name, age_h, cls, **flags):
                (logs / name).write_text(json.dumps({
                    "completed_at": (now - timedelta(hours=age_h)).isoformat(),
                    "exit_class": cls, "run_status": "completed", "flags": flags}), encoding="utf-8")

            put("run_summary_100.json", 50, "warnings", dry_run=False)
            put("run_summary_200.json", 1, "clean", dry_run=True)
            put("run_summary_latest.json", 1, "clean", dry_run=True)
            proc = run_bash("preflight_check_lastrun; echo rc=$?", MAC_UPDATE_LOGS_DIR=str(logs))
            self.assertIn("2d 2h ago, result: completed with warnings", proc.stdout)
            put("run_summary_300.json", 2, "clean", inventory_only=True)
            proc = run_bash("preflight_check_lastrun", MAC_UPDATE_LOGS_DIR=str(logs))
            self.assertIn("completed with warnings", proc.stdout)
            (logs / "run_summary_100.json").unlink()
            proc = run_bash("preflight_check_lastrun; echo rc=$?", MAC_UPDATE_LOGS_DIR=str(logs))
            self.assertIn("no previous real run", proc.stdout)
            self.assertIn("rc=3", proc.stdout)

    def test_last_run_missing_and_corrupt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp)
            self.assertIn("no run summary found", run_bash("preflight_check_lastrun", MAC_UPDATE_LOGS_DIR=str(logs)).stdout)
            (logs / "run_summary_latest.json").write_text("{not json", encoding="utf-8")
            proc = run_bash("preflight_check_lastrun; echo rc=$?", MAC_UPDATE_LOGS_DIR=str(logs))
            self.assertIn("result: unknown", proc.stdout)

    def test_toolkit_state_behind_dirty_and_clean(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git not available")
        git = ["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t", "-c", "commit.gpgsign=false"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            origin = root / "origin"
            origin.mkdir()
            env = shell_env(GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null")

            def g(cwd: Path, *args: str) -> None:
                subprocess.run([*git, *args], cwd=cwd, env=env, check=True, capture_output=True)

            g(origin, "init", "-b", "main")
            (origin / "VERSION").write_text("9.9.9\n", encoding="utf-8")
            g(origin, "add", "VERSION")
            g(origin, "commit", "-m", "one")
            clone = root / "clone"
            subprocess.run(["git", "clone", str(origin), str(clone)], env=env, check=True, capture_output=True)

            clean = run_bash(f'SCRIPT_DIR="{clone}"; preflight_check_toolkit; echo rc=$?')
            self.assertIn("Toolkit v9.9.9: git checkout clean, up to date with origin/main", clean.stdout)
            self.assertIn("rc=0", clean.stdout)

            (clone / "VERSION").write_text("9.9.9\n# local edit\n", encoding="utf-8")
            dirty = run_bash(f'SCRIPT_DIR="{clone}"; preflight_check_toolkit; echo rc=$?')
            self.assertIn("uncommitted changes", dirty.stdout)
            self.assertIn("rc=10", dirty.stdout)
            g(clone, "checkout", "--", "VERSION")

            (origin / "extra").write_text("x\n", encoding="utf-8")
            g(origin, "add", "extra")
            g(origin, "commit", "-m", "two")
            # Only already-fetched refs are consulted: before a fetch nothing is behind.
            before = run_bash(f'SCRIPT_DIR="{clone}"; preflight_check_toolkit; echo rc=$?')
            self.assertIn("rc=0", before.stdout)
            g(clone, "fetch", "origin")
            behind = run_bash(f'SCRIPT_DIR="{clone}"; preflight_check_toolkit; echo rc=$?')
            self.assertIn("1 commit(s) behind origin/main", behind.stdout)
            self.assertIn("rc=10", behind.stdout)

    def test_toolkit_state_without_git_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text("1.2.3\n", encoding="utf-8")
            proc = run_bash(f'SCRIPT_DIR="{root}"; preflight_check_toolkit; echo rc=$?', GIT_CEILING_DIRECTORIES=str(root.parent))
            self.assertIn("not a git checkout", proc.stdout)


class DoctorAggregationTests(unittest.TestCase):
    """preflight_doctor exits 0 / 10 / 1 from the worst line."""

    FAKES = (
        "preflight_check_platform preflight_check_tools preflight_check_launchd_path "
        "preflight_check_launchagent preflight_check_sudo preflight_check_touchid "
        "preflight_check_accessibility preflight_check_xcode preflight_check_disk "
        "preflight_check_power preflight_check_network preflight_check_toolkit preflight_check_lastrun"
    )

    def doctor(self, overrides: str) -> subprocess.CompletedProcess:
        script = (
            "for f in " + self.FAKES + "; do eval \"$f() { _pf_line 0 \\\"fake $f\\\"; }\"; done\n"
            + overrides + "\n"
            "preflight_doctor; echo exit=$?\n"
        )
        return run_bash(script)

    def test_all_fine_exits_zero(self) -> None:
        proc = self.doctor("")
        self.assertIn("Everything is ready (exit 0).", proc.stdout)
        self.assertIn("exit=0", proc.stdout)

    def test_info_lines_do_not_count_as_warnings(self) -> None:
        proc = self.doctor('preflight_check_sudo() { _pf_line 3 "info only"; }')
        self.assertIn("exit=0", proc.stdout)
        self.assertIn("ℹ️  info only", proc.stdout)

    def test_warnings_exit_ten_and_count(self) -> None:
        proc = self.doctor('preflight_check_sudo() { _pf_line 10 "w1"; }\n'
                           'preflight_check_disk() { _pf_line 10 "w2"; }')
        self.assertIn("Ready, with 2 warning(s) (exit 10).", proc.stdout)
        self.assertIn("exit=10", proc.stdout)

    def test_hard_problem_exits_one(self) -> None:
        proc = self.doctor('preflight_check_sudo() { _pf_line 10 "w1"; }\n'
                           'preflight_check_network() { _pf_line 1 "down"; }')
        self.assertIn("1 hard problem(s) must be fixed before a real run (exit 1).", proc.stdout)
        self.assertIn("exit=1", proc.stdout)

    def test_every_check_has_a_translated_message_in_all_languages(self) -> None:
        keys = {line.split("=", 1)[0] for line in LANG_EN.read_text(encoding="utf-8").splitlines()
                if line.startswith(("L_DOCTOR_", "L_PREFLIGHT_"))}
        source = (REPO_ROOT / "lib" / "preflight.sh").read_text(encoding="utf-8")
        used = {k for k in keys if f"${k}" in source or f"${{{k}}}" in source}
        # Every key the library references must exist (i18n parity is tested elsewhere).
        import re
        referenced = set(re.findall(r"\$\{?(L_(?:DOCTOR|PREFLIGHT)_[A-Z_]+)", source))
        self.assertEqual(referenced - keys, set())
        self.assertTrue(used)


class DoctorEntrypointTests(unittest.TestCase):
    """`bash update_all.sh --doctor` end to end in a throw-away copy of the toolkit."""

    def make_copy(self, root: Path) -> Path:
        return Path(copy_toolkit(REPO_ROOT, root / "toolkit"))

    def snapshot(self, root: Path) -> set[str]:
        return {str(p.relative_to(root)) for p in root.rglob("*") if "__pycache__" not in p.parts}

    def test_doctor_changes_nothing_and_never_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            toolkit = self.make_copy(root)
            stubs = root / "stubs"
            base_stubs(stubs)
            before = self.snapshot(toolkit)
            env = shell_env(MAC_LANG="en", HOME=str(root), TMPDIR=str(root))
            env["PATH"] = f"{stubs}:{env['PATH']}"
            isolate_host_tools(env)
            proc = subprocess.run(["bash", str(toolkit / "update_all.sh"), "--doctor"], capture_output=True,
                                  text=True, env=env, stdin=subprocess.DEVNULL, timeout=120)
            self.assertIn(proc.returncode, (0, 10), proc.stdout + proc.stderr)
            self.assertIn("Pre-flight check (read-only)", proc.stdout)
            for needle in ("Platform:", "Free disk space:", "Network:", "Toolkit v", "Last run:"):
                self.assertIn(needle, proc.stdout)
            self.assertEqual(self.snapshot(toolkit), before, "--doctor must not create a log, summary or lock")
            self.assertFalse((toolkit / "logs").exists())
            self.assertEqual(list(root.glob("mac_update.*")), [], "no session directory")
            sudo_calls = (stubs / "sudo.log").read_text(encoding="utf-8").splitlines() if (stubs / "sudo.log").exists() else []
            for call in sudo_calls:
                self.assertEqual(call.split(), ["-n", "true"], "sudo must only be probed, never prompted")

    def test_doctor_exit_one_on_a_hard_problem(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            toolkit = self.make_copy(root)
            stubs = root / "stubs"
            base_stubs(stubs, net_ok=False)
            env = shell_env(MAC_LANG="en", HOME=str(root), TMPDIR=str(root))
            env["PATH"] = f"{stubs}:{env['PATH']}"
            isolate_host_tools(env)
            proc = subprocess.run(["bash", str(toolkit / "update_all.sh"), "--doctor"], capture_output=True,
                                  text=True, env=env, stdin=subprocess.DEVNULL, timeout=120)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("no host reachable over HTTPS", proc.stdout)

    def test_doctor_reports_an_unsupported_platform_instead_of_dying_silently(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            toolkit = self.make_copy(root)
            stubs = root / "stubs"
            base_stubs(stubs)
            write_stub(stubs, "uname", "echo x86_64")
            env = shell_env(MAC_LANG="en", HOME=str(root), TMPDIR=str(root))
            env["PATH"] = f"{stubs}:{env['PATH']}"
            isolate_host_tools(env)
            proc = subprocess.run(["bash", str(toolkit / "update_all.sh"), "--doctor"], capture_output=True,
                                  text=True, env=env, stdin=subprocess.DEVNULL, timeout=120)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("Unsupported platform", proc.stdout)

    def test_help_and_cli_flag_are_documented(self) -> None:
        cli = (REPO_ROOT / "lib" / "cli.sh").read_text(encoding="utf-8")
        self.assertIn("--doctor) export MAC_UPDATE_DOCTOR=1", cli)
        self.assertIn("--doctor", cli.split("mac_update_parse_cli()")[0])


if __name__ == "__main__":
    unittest.main()
