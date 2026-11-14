"""Integration boundaries for safe TUI recovery and truthful phase state."""

import copy
import io
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import terminal_app as app
from tui_backend import ACTIONS, DEFAULT_SETTINGS, GROUPS


ROOT = Path(__file__).resolve().parents[1]


class EventJob:
    def __init__(self, batches=()):
        self.batches = list(batches)
        self.running, self.secret_input = True, False
        self.returncode, self.started_at = None, 0.0

    def poll(self):
        return self.batches.pop(0) if self.batches else []

    def send(self, text):
        raise AssertionError("phase output must never submit an answer")

    def interrupt(self):
        raise AssertionError("a UI error must not interrupt its worker")


class TerminalIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name).resolve()
        (self.repo / "VERSION").write_text("1.8.0\n")
        for spec in ACTIONS.values():
            script = self.repo / spec["script"]
            script.parent.mkdir(parents=True, exist_ok=True)
            script.write_text("# Fixture only; this file must never execute.\n")

    def workspace(self, action="update", groups=GROUPS):
        settings = copy.deepcopy(DEFAULT_SETTINGS)
        settings.update(wizard_complete=True, language="en", groups=list(groups), auto_resize=False)
        result = app.Workspace(self.repo, settings=settings)
        result.job_action = action
        result.group_states = {g: "queued" if g in groups else "skipped" for g in GROUPS}
        return result

    def test_ui_exception_hands_same_worker_to_real_recovery_after_curses_restores(self):
        workspace = self.workspace()
        restored = []

        class ContinuingJob(EventJob):
            def poll(self):
                if not restored:
                    raise AssertionError("handoff ran before curses restored the terminal")
                self.running, self.returncode = False, 10
                return ["EXISTING_WORKER_CONTINUED\n"]

        workspace.job = ContinuingJob()

        class Display(io.StringIO):
            def isatty(self):
                return True

        output = Display()
        screen = SimpleNamespace(keypad=lambda value: None, timeout=lambda value: None)

        def wrapper(main):
            try:
                return main(screen)
            finally:
                restored.append(True)

        with patch.object(app, "Workspace", return_value=workspace), \
             patch.object(workspace, "tick", side_effect=RuntimeError("fixture UI failure")), \
             patch.object(app.curses, "wrapper", side_effect=wrapper), \
             patch.object(app.curses, "raw"), patch.object(app.curses, "noecho"), \
             patch.object(app.curses, "curs_set"), \
             patch.object(app.sys, "stdin", Display("y\n")), \
             patch.object(app.sys, "stdout", output), \
             patch.dict(os.environ, {"TERM": "xterm-256color"}), \
             patch("subprocess.Popen", side_effect=AssertionError("must not restart a worker")):
            self.assertEqual(app.run(self.repo), 10)
        self.assertIn("EXISTING_WORKER_CONTINUED", output.getvalue())
        self.assertFalse(workspace.job.running)

    def test_split_phase_markers_follow_observed_status_without_inferred_success(self):
        workspace = self.workspace()
        job = EventJob([["@@MAC_UPDATE_PHASE brew run"], ["ning\n"],
                        ["@@MAC_UPDATE_PHASE brew warn\n@@MAC_UPDATE_PHASE npmcli error\n"]])
        workspace.job = job
        workspace.tick()
        self.assertEqual(workspace.group_states["brew"], "queued")
        workspace.tick()
        self.assertEqual(workspace.group_states["brew"], "running")
        workspace.tick()
        job.running, job.returncode = False, 0
        workspace.tick()
        self.assertEqual(workspace.group_states["brew"], "warnings")
        self.assertEqual(workspace.group_states["npm"], "failed")
        self.assertEqual(workspace.group_states["appstore"], "unknown")
        self.assertFalse(any("@@MAC_UPDATE_PHASE" in line for line in workspace.log))

    def test_preview_cannot_claim_update_group_completion_from_output_markers(self):
        workspace = self.workspace(action="preview")
        workspace.group_states = {g: "idle" for g in GROUPS}
        workspace.job = EventJob([["@@MAC_UPDATE_PHASE system ok\n"]])
        workspace.tick()
        self.assertEqual(workspace.group_states["system"], "idle")

    def test_overall_progress_does_not_show_finished_while_final_phase_is_running(self):
        workspace = self.workspace()
        workspace.job = EventJob([["100% overall\n@@MAC_UPDATE_PHASE system running\n"]])
        workspace.tick()
        self.assertEqual(workspace.group_states["system"], "running")
        self.assertIsNotNone(workspace.progress)
        self.assertLess(workspace.progress, 100)

    def test_bash_phase_stop_reports_actual_status_only_for_tui_children(self):
        text = (ROOT / "update_all.sh").read_text()
        functions = text[text.index("tui_phase_event() {"):text.index("_fmt_duration() {")]
        for child, expected in (("0", ""), ("1", "@@MAC_UPDATE_PHASE brew warn\n")):
            with self.subTest(child=child):
                env = dict(os.environ, MAC_UPDATE_TUI_CHILD=child, MAC_UPDATE_DRY_RUN="1", STATUS_CODE_BREW="warn")
                result = subprocess.run(["/bin/bash", "-c", functions + "\nstep_timer_stop brew\n"],
                                        env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)

    def test_selected_system_skipped_by_preflight_emits_terminal_group_state(self):
        text = (ROOT / "update_all.sh").read_text()
        event = text[text.index("tui_phase_event() {"):text.index("step_timer_start() {")]
        start = text.index("# Prepare the final system update.")
        branch = text[start:text.index("# STEP 1: App Store update", start)]
        env = dict(os.environ, MAC_UPDATE_TUI_CHILD="1", MAC_UPDATE_SKIP_SYSTEM="0",
                   PREFLIGHT_SKIP_SYSTEM="1", MAC_UPDATE_DRY_RUN="0", SYSTEM_DEFERRED="0")
        result = subprocess.run(["/bin/bash", "-c", event + "\nprint_info() { :; }\n" + branch],
                                env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("@@MAC_UPDATE_PHASE system skipped\n", result.stdout)


if __name__ == "__main__":
    unittest.main()
