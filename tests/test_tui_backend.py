"""The TUI launches only fixed fixture commands and never owns host operations."""

import json
import os
from pathlib import Path
import stat
import tempfile
import time
import unittest
from unittest.mock import patch

from inventory_store import StoreError

from tui_backend import (
    ACTIONS, GROUPS, TerminalJob, build_command, load_settings, recent_runs,
    save_settings,
)


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        for item in ACTIONS.values():
            script = self.repo / item["script"]
            script.parent.mkdir(parents=True, exist_ok=True)
            script.write_text("#!/bin/bash\nexit 0\n")
        self.settings = load_settings(self.root / "absent")

    def fixture(self, body):
        (self.repo / "update_all.sh").write_text("#!/bin/bash\n" + body + "\n")

    def collect(self, job, until=None):
        output = ""
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            output += "".join(job.poll())
            if until and until(output):
                return output
            if not job.running:
                output += "".join(job.poll())
                return output
            time.sleep(0.01)
        self.fail("fixture PTY did not finish; output=" + repr(output[-200:]))

    def test_group_scope_is_fixed_and_empty_update_cannot_mean_all(self):
        command = build_command(self.repo, "update", ["brew"], self.settings)
        self.assertEqual(command[:3], ["/bin/bash", str(self.repo / "update_all.sh"), "--cli"])
        self.assertIn("--skip-system", command)
        self.assertIn("--skip-appstore", command)
        self.assertIn("--skip-npm", command)
        self.assertIn("--skip-internet", command)
        self.assertNotIn("--skip-brew", command)
        with self.assertRaises(ValueError):
            build_command(self.repo, "update", [], self.settings)
        for action, groups in [("update; touch marker", GROUPS), ("update", ["brew;touch marker"]), ("update", "brew")]:
            with self.assertRaises(ValueError):
                build_command(self.repo, action, groups, self.settings)

    def test_preferences_cannot_dispatch_saved_update_permissions(self):
        command = build_command(self.repo, "preferences", GROUPS, self.settings)
        self.assertIn("--preferences-only", command)
        self.assertNotIn("--preferences", command)

    def test_script_symlink_cannot_escape_the_selected_repository(self):
        outside = self.root / "outside.sh"
        outside.write_text("exit 0\n")
        script = self.repo / "update_all.sh"
        script.unlink()
        script.symlink_to(outside)
        with self.assertRaises(ValueError):
            build_command(self.repo, "update", GROUPS, self.settings)

    def test_settings_are_private_atomic_and_round_trip_without_grants(self):
        state = self.root / "state"
        settings = dict(self.settings, language="pl", groups=["brew"], ascii=True,
                        theme="light", wizard_complete=True)
        save_settings(state, settings)
        self.assertEqual(load_settings(state), settings)
        self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o700)
        path = state / "tui-settings.json"
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        previous_umask = os.umask(0o777)
        try:
            save_settings(state, settings)
        finally:
            os.umask(previous_umask)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            save_settings(state, dict(settings, language="pl;exit 0"))
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual([p.name for p in state.iterdir()], ["tui-settings.json"])
        for changes in ({"approve_all": True}, {"ascii": 1}, {"groups": ["unknown"]}, {"theme": "system"}):
            with self.assertRaises(ValueError):
                save_settings(state, dict(settings, **changes))

    def test_settings_refuse_symlinks_hardlinks_unsafe_modes_and_malformed_data(self):
        state = self.root / "state"
        save_settings(state, self.settings)
        path = state / "tui-settings.json"
        outside = self.root / "outside.json"
        outside.write_text("{}")
        outside.chmod(0o600)
        path.unlink()
        path.symlink_to(outside)
        for operation in (lambda: load_settings(state), lambda: save_settings(state, self.settings)):
            with self.assertRaises((ValueError, OSError, StoreError)):
                operation()
        self.assertEqual(outside.read_text(), "{}")
        path.unlink()
        os.link(outside, path)
        with self.assertRaises((ValueError, OSError, StoreError)):
            load_settings(state)
        path.unlink()
        path.write_text("not json")
        path.chmod(0o600)
        with self.assertRaises(ValueError):
            load_settings(state)
        path.write_text("{}")
        path.chmod(0o644)
        with self.assertRaises((ValueError, OSError, StoreError)):
            load_settings(state)

    def test_settings_replace_failure_preserves_previous_bytes_without_temp_files(self):
        state = self.root / "state"
        save_settings(state, self.settings)
        before = (state / "tui-settings.json").read_bytes()
        with patch("tui_backend.os.replace", side_effect=OSError("fixture write failure")):
            with self.assertRaises(OSError):
                save_settings(state, dict(self.settings, language="pl"))
        self.assertEqual((state / "tui-settings.json").read_bytes(), before)
        self.assertEqual([p.name for p in state.iterdir()], ["tui-settings.json"])

    def test_settings_cannot_follow_an_ancestor_alias_or_repair_unsafe_state(self):
        state = self.root / "state"
        state.mkdir(mode=0o755)
        state.chmod(0o755)
        with self.assertRaises(StoreError):
            save_settings(state, self.settings)
        self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o755)
        alias = self.root / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(StoreError):
            save_settings(alias / "new-state", self.settings)
        self.assertFalse((self.root / "new-state").exists())

    def test_history_reads_bounded_metadata_and_never_follows_symlinks(self):
        logs = self.repo / "logs"
        logs.mkdir()
        summary = dict(format_version=4, timestamp="2026-11-14T00:00:00Z", run_status="completed",
                       duration_seconds=2, exit_code=0, exit_class="clean", items=[{"secret": "hidden"}])
        good = logs / "run_summary_20261114_010000.json"
        good.write_text(json.dumps(summary))
        good.chmod(0o600)
        (logs / "run_summary_20261114_020000.json").symlink_to(good)
        rows = recent_runs(self.repo, limit=1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["run_status"], "completed")
        self.assertNotIn("hidden", json.dumps(rows))
        self.assertNotIn("items", rows[0])

    def test_child_has_controlling_tty_and_explicit_input_without_global_flags(self):
        self.fixture('t0=no; t1=no; t2=no; [ -t 0 ] && t0=yes; [ -t 1 ] && t1=yes; [ -t 2 ] && t2=yes\n'
                     'printf "TTY:%s:%s:%s\\n" "$t0" "$t1" "$t2"\n'
                     'printf "ENV:%s:%s:%s:%s\\n" "$MAC_UPDATE_TUI_CHILD" "$MAC_UPDATE_LANG" "${MAC_UPDATE_YES-unset}" "${MAC_UPDATE_NONINTERACTIVE-unset}"\n'
                     'printf "READY\\n"\nIFS= read -r answer </dev/tty\nprintf "ANSWER:%s\\n" "$answer"')
        with patch.dict(os.environ, {"MAC_UPDATE_YES": "1", "MAC_UPDATE_NONINTERACTIVE": "1"}):
            job = TerminalJob(self.repo, "update", GROUPS, dict(self.settings, language="pl"))
            job.start()
        first = self.collect(job, lambda output: "READY" in output)
        self.assertTrue(job.running)
        self.assertIn("TTY:yes:yes:yes", first)
        self.assertIn("ENV:1:pl:unset:unset", first)
        job.send("deliberate\n")
        rest = self.collect(job)
        self.assertIn("ANSWER:deliberate", rest)
        self.assertEqual(job.returncode, 0)
        self.assertIsInstance(job.pid, int)
        self.assertIsInstance(job.started_at, float)

    def test_secret_input_echo_state_is_detected_and_input_is_not_logged(self):
        self.fixture('printf "PASSWORD\\n"\nIFS= read -r -s secret\nprintf "\\nLENGTH:%s\\n" "${#secret}"')
        job = TerminalJob(self.repo, "update", GROUPS, self.settings)
        job.start()
        first = self.collect(job, lambda output: "PASSWORD" in output and job.secret_input)
        self.assertTrue(job.secret_input)
        job.send("fixture-secret\n")
        rest = self.collect(job)
        self.assertIn("LENGTH:14", rest)
        self.assertNotIn("fixture-secret", first + rest)
        self.assertFalse(job.secret_input)

    def test_split_osc_clipboard_and_title_sequences_are_removed(self):
        self.fixture("printf 'safe\\033]52;c;secret'; sleep 0.03; printf '\\aafter\\033]0;title\\033'; sleep 0.03; printf '\\\\done\\n'")
        job = TerminalJob(self.repo, "update", GROUPS, self.settings)
        job.start()
        output = self.collect(job)
        self.assertIn("safeafterdone", output)
        self.assertNotIn("secret", output)
        self.assertNotIn("title", output)
        self.assertNotIn("\033]", output)

    def test_resize_and_explicit_interrupt_are_forwarded_only_to_fixture_pty(self):
        size_query = "python3 -c 'import fcntl,struct,termios; size=struct.unpack(\"HHHH\",fcntl.ioctl(0,termios.TIOCGWINSZ,b\"\\0\"*8)); print(\"SIZE:%d:%d\" % size[:2])'"
        self.fixture("trap 'printf INTERRUPTED; exit 130' INT\n" + size_query
                     + "\nprintf 'READY\\n'\nIFS= read -r answer\n" + size_query + "\nIFS= read -r answer")
        job = TerminalJob(self.repo, "update", GROUPS, self.settings)
        job.resize(35, 111)
        job.start()
        first = self.collect(job, lambda output: "READY" in output)
        self.assertIn("SIZE:35:111", first)
        job.resize(40, 120)
        job.send("\n")
        changed = self.collect(job, lambda output: "SIZE:40:120" in output)
        self.assertIn("SIZE:40:120", changed)
        self.assertTrue(job.running)
        job.interrupt()
        output = self.collect(job)
        self.assertIn("INTERRUPTED", output)
        self.assertEqual(job.returncode, 130)

    def test_noisy_child_output_is_bounded_per_poll_and_utf8_chunks_are_retained(self):
        self.fixture("python3 -c 'import sys; sys.stdout.write(\"x\" * 150000 + \"Żółw\"); sys.stdout.flush()'")
        job = TerminalJob(self.repo, "update", GROUPS, self.settings)
        job.start()
        chunks = []
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            batch = job.poll()
            self.assertLessEqual(sum(len(x) for x in batch), 65536)
            chunks.extend(batch)
            if not job.running:
                chunks.extend(job.poll())
                break
            time.sleep(0.01)
        output = "".join(chunks)
        self.assertEqual(output, "x" * 150000 + "Żółw")
        self.assertEqual(job.returncode, 0)


if __name__ == "__main__":
    unittest.main()
