"""Guarded workspace model tests: no terminal jobs or system clipboards run."""

import copy
import curses
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib/python"))
import terminal_app as app
from inventory_store import StoreError
from tui_backend import ACTIONS, DEFAULT_SETTINGS, GROUPS, build_command
from tui_i18n import LANGUAGES


class MemoryJob:
    """Only the process boundary is replaced; real command planning stays active."""
    instances = []

    def __init__(self, repo, action, groups, settings):
        self.command = build_command(repo, action, groups, settings)
        self.running, self.secret_input, self.returncode = False, False, None
        self.started_at = None
        self.answers, self.chunks, self.sizes = [], [], []
        self.interrupted = False
        self.instances.append(self)

    def start(self):
        self.running = True
        self.started_at = time.monotonic()

    def resize(self, rows, cols):
        self.sizes.append((rows, cols))

    def poll(self):
        chunks, self.chunks = self.chunks, []
        return chunks

    def send(self, value):
        self.answers.append(value)

    def interrupt(self):
        self.interrupted = True


class CanvasTests(unittest.TestCase):
    def test_unicode_width_clipping_and_control_sequences(self):
        self.assertEqual(app.cell_width("\x1b[31m界e\u0301\x1b[0m"), 3)
        self.assertEqual(app.clip("A界e\u0301Z", 3), "A界")
        self.assertEqual(app.clip("界", 1), "")
        self.assertEqual(app.clip("abc", -1), "")
        self.assertNotIn("\x1b", app.plain("\x1b]52;c;unsafe\x07\x1b[31mhello"))
        canvas = app.Canvas(1, 6)
        canvas.put(0, 0, "A界Be\u0301")
        self.assertEqual(canvas.lines(), ["A界Bé "])
        canvas.put(0, 5, "界")
        self.assertEqual(canvas.lines(), ["A界Bé "])

    def test_wrapped_wide_text_fits_cells_without_losing_characters(self):
        lines = app.wrapped("界" * 6, 4)
        self.assertEqual("".join(lines), "界" * 6)
        self.assertTrue(all(app.cell_width(line) <= 4 for line in lines), lines)

    def test_partial_overwrite_of_wide_glyph_keeps_canvas_cell_width(self):
        canvas = app.Canvas(1, 4)
        canvas.put(0, 0, "界")
        canvas.put(0, 1, "X")
        self.assertEqual(app.cell_width(canvas.lines()[0]), 4)
        self.assertIn("X", canvas.lines()[0])


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name).resolve()
        (self.repo / "VERSION").write_text("1.8.0\n")
        for spec in ACTIONS.values():
            script = self.repo / spec["script"]
            script.parent.mkdir(parents=True, exist_ok=True)
            script.write_text("# Fixture only. This file must never execute.\n")
        MemoryJob.instances = []
        self.worker_patch = patch.object(app, "TerminalJob", MemoryJob)
        self.worker_patch.start()
        self.addCleanup(self.worker_patch.stop)
        self.clipboard_calls = []

        def clipboard_run(command, **kwargs):
            self.clipboard_calls.append((command, kwargs))
            return SimpleNamespace(stdout="PASTED\nANSWER", returncode=0)

        for target, replacement in (("shutil.which", lambda name: "/fixture/" + name),
                                     ("subprocess.run", clipboard_run)):
            patched = patch("terminal_app." + target, replacement)
            patched.start()
            self.addCleanup(patched.stop)

    def workspace(self, lang="en", view="home", **changes):
        settings = copy.deepcopy(DEFAULT_SETTINGS)
        settings.update(language=lang, wizard_complete=True)
        settings.update(changes)
        return app.Workspace(str(self.repo), view, settings)

    def attach_job(self, workspace, secret=False):
        job = MemoryJob(str(self.repo), "preview", list(GROUPS), workspace.settings)
        job.start()
        job.secret_input = secret
        workspace.job, workspace.job_action = job, "preview"
        return job

    def test_all_languages_views_and_supported_viewports_render_bounded_navigation(self):
        for lang in LANGUAGES:
            for view in app.VIEWS:
                for height, width in ((24, 80), (30, 120), (40, 160)):
                    with self.subTest(lang=lang, view=view, size=(height, width)):
                        workspace = self.workspace(lang, view)
                        canvas = workspace.frame(height, width)
                        self.assertEqual(len(canvas.lines()), height)
                        self.assertTrue(all(app.cell_width(line) == width for line in canvas.lines()))
                        left = 23 if width >= 110 else 20
                        selected = app.clip("> " + workspace.t("nav_" + view), left - 4)
                        self.assertTrue(any(selected in "".join(row[:left]) for row in canvas.cells))
                        self.assertEqual(workspace.view, view)
        self.assertEqual(MemoryJob.instances, [])
        self.assertEqual(self.clipboard_calls, [])

    def test_small_viewport_reports_resize_and_escape_exits_without_starting(self):
        for height, width in ((23, 80), (24, 79), (8, 25)):
            workspace = self.workspace()
            text = "\n".join(workspace.frame(height, width).lines())
            self.assertIn(app.clip(workspace.t("resize"), width), text)
            workspace.key("\x1b")
            self.assertTrue(workspace.should_exit)
        self.assertEqual(MemoryJob.instances, [])

    def test_answer_dialog_keeps_the_question_and_scope_visible(self):
        workspace = self.workspace()
        self.attach_job(workspace)
        workspace.log = ["Example Editor: update through Homebrew", "Which displayed scope do you approve?"]
        workspace.key("i")
        frame = "\n".join(workspace.frame(38, 140).lines())
        self.assertIn("Example Editor: update through Homebrew", frame)
        self.assertIn("Which displayed scope do you approve?", frame)
        self.assertIn("PgUp / PgDn", frame)
        self.assertEqual(workspace.job.answers, [])

    def test_log_focus_wraps_long_scopes_instead_of_hiding_the_suffix(self):
        workspace = self.workspace()
        workspace.focus = 2
        workspace.log = ["Scope: " + "long reviewed name " * 8 + "ONLY THIS SCOPE"]
        frame = "\n".join(workspace.frame(38, 140).lines())
        self.assertIn("ONLY THIS SCOPE", frame)

    def test_ascii_frame_uses_ascii_borders(self):
        workspace = self.workspace(ascii=True)
        text = "\n".join(workspace.frame(24, 80).lines())
        self.assertNotIn("╭", text)
        self.assertNotIn("│", text)
        self.assertIn("+", text)

    def test_small_viewport_cannot_start_an_operation_through_an_invisible_confirmation(self):
        workspace = self.workspace()
        workspace.frame(8, 25)
        workspace.key("r")
        workspace.key("y")
        self.assertEqual(MemoryJob.instances, [])
        self.assertIsNone(workspace.job)

    def test_navigation_palette_search_and_escape_never_start_jobs(self):
        workspace = self.workspace()
        workspace.key(curses.KEY_DOWN)
        self.assertEqual(workspace.view, "updates")
        workspace.key("\t")
        self.assertEqual(workspace.focus, 1)
        workspace.key("\x10")
        for key in "readiness":
            workspace.key(key)
        self.assertEqual(workspace.palette_actions(), ["doctor"])
        workspace.key("\x1b")
        self.assertIsNone(workspace.modal)
        workspace.key(curses.KEY_F1)
        self.assertEqual(workspace.view, "help")
        self.assertEqual(MemoryJob.instances, [])

    def test_selected_groups_produce_only_explicit_skip_flags(self):
        workspace = self.workspace(view="updates")
        workspace.focus = 1
        for group in ("appstore", "npm", "system"):
            workspace.selected = workspace.items().index(("group", group))
            workspace.key(" ")
        self.assertEqual(workspace.settings["groups"], ["brew", "internet"])
        workspace.request_action("update")
        self.assertEqual(workspace.modal, "confirm")
        self.assertEqual(MemoryJob.instances, [])
        workspace.key("y")
        self.assertEqual(workspace.job.command[-3:], ["--skip-appstore", "--skip-npm", "--skip-system"])
        self.assertNotIn("--yes", workspace.job.command)

    def test_empty_group_selection_blocks_updates_without_silently_restoring_defaults(self):
        workspace = self.workspace(groups=[])
        workspace.request_action("update")
        self.assertEqual(workspace.settings["groups"], [])
        self.assertIsNone(workspace.modal)
        self.assertEqual(MemoryJob.instances, [])

    def test_current_log_tail_and_progress_remain_visible_in_operation_views(self):
        for lang in LANGUAGES:
            for view in app.VIEWS:
                if view == "help":
                    continue
                for height, width in ((24, 80), (30, 120), (40, 160)):
                    with self.subTest(lang=lang, view=view, size=(height, width)):
                        workspace = self.workspace(lang, view)
                        self.attach_job(workspace)
                        workspace.log = ["LOG-FIXTURE-BEGIN", "LOG-FIXTURE-END"]
                        workspace.progress = 42
                        text = "\n".join(workspace.frame(height, width).lines())
                        self.assertIn("LOG-FIXTURE-END", text)
                        self.assertIn("42%", text)

    def test_wizard_progress_persists_completion_only_at_finish(self):
        workspace = self.workspace(wizard_complete=False)
        self.assertEqual(workspace.view, "wizard")
        stored = []
        with patch.object(app, "save_settings", side_effect=lambda root, value: stored.append(copy.deepcopy(value))):
            for expected in range(1, len(app.STEPS)):
                workspace.selected = workspace.items().index(("wizard", "next"))
                workspace.activate()
                self.assertEqual(workspace.wizard_step, expected)
                self.assertFalse(workspace.settings["wizard_complete"])
                self.assertEqual(stored, [])
            workspace.selected = workspace.items().index(("wizard", "finish"))
            workspace.activate()
        self.assertEqual(len(stored), 1)
        self.assertTrue(stored[0]["wizard_complete"])
        self.assertEqual(workspace.view, "home")
        self.assertEqual(MemoryJob.instances, [])

    def test_settings_store_failure_leaves_wizard_incomplete_and_reports_error(self):
        workspace = self.workspace(wizard_complete=False)
        with patch.object(app, "save_settings", side_effect=StoreError("unsafe fixture state")):
            workspace.save(complete=True)
        self.assertFalse(workspace.settings["wizard_complete"])
        self.assertEqual(workspace.view, "wizard")
        self.assertIn("unsafe fixture state", workspace.notice)
        self.assertNotIn("{message}", workspace.notice)

    def test_every_mutating_operation_requires_deliberate_confirmation(self):
        for action, spec in ACTIONS.items():
            if not spec["mutating"]:
                continue
            with self.subTest(action=action):
                workspace = self.workspace()
                before = len(MemoryJob.instances)
                workspace.request_action(action)
                self.assertEqual(workspace.modal, "confirm")
                workspace.key("\n")
                self.assertIsNone(workspace.modal)
                self.assertEqual(len(MemoryJob.instances), before)
                workspace.request_action(action)
                workspace.key("y")
                self.assertTrue(workspace.job.running)
                self.assertEqual(len(MemoryJob.instances), before + 1)

    def test_answers_submit_only_on_explicit_enter_and_cancel_clears_them(self):
        workspace = self.workspace()
        job = self.attach_job(workspace)
        workspace.key("i")
        for key in "yes":
            workspace.key(key)
        self.assertEqual(job.answers, [])
        workspace.key("\x1b")
        self.assertEqual(workspace.buffer, "")
        workspace.key("i")
        workspace.key("y")
        workspace.key("\n")
        self.assertEqual(job.answers, ["y\n"])
        self.assertIsNone(workspace.modal)
        self.assertEqual(workspace.buffer, "")

    def test_secret_answer_is_masked_and_never_copied(self):
        workspace = self.workspace()
        job = self.attach_job(workspace, secret=True)
        workspace.key("i")
        workspace.buffer = "FIXTURE-SECRET"
        text = "\n".join(workspace.frame(24, 80).lines())
        self.assertNotIn("FIXTURE-SECRET", text)
        self.assertIn("*" * len(workspace.buffer), text)
        workspace.copy()
        self.assertEqual(self.clipboard_calls, [])
        self.assertEqual(job.answers, [])

    def test_secret_mask_stays_latched_until_explicit_submission_or_cancel(self):
        for closing_key in ("\n", "\x1b"):
            with self.subTest(closing_key=closing_key):
                workspace = self.workspace()
                job = self.attach_job(workspace, secret=True)
                workspace.key("i")
                workspace.buffer = "FIXTURE-LATCHED-SECRET"
                first = "\n".join(workspace.frame(24, 80).lines())
                self.assertNotIn("FIXTURE-LATCHED-SECRET", first)
                job.secret_input = False
                second = "\n".join(workspace.frame(24, 80).lines())
                self.assertNotIn("FIXTURE-LATCHED-SECRET", second)
                self.assertIn("*" * len(workspace.buffer), second)
                workspace.copy()
                self.assertEqual(self.clipboard_calls, [])
                workspace.key(closing_key)
                self.assertEqual(workspace.buffer, "")
                self.assertIsNone(workspace.modal)
                self.assertEqual(job.answers, ["FIXTURE-LATCHED-SECRET\n"] if closing_key == "\n" else [])
                workspace.key("i")
                workspace.buffer = "PUBLIC-ANSWER"
                reopened = "\n".join(workspace.frame(24, 80).lines())
                self.assertIn("PUBLIC-ANSWER", reopened)

    def test_clipboard_runs_only_on_explicit_copy_or_answer_dialog_paste(self):
        workspace = self.workspace()
        workspace.key("\x16")
        workspace.frame(30, 120)
        self.assertEqual(self.clipboard_calls, [])
        workspace.focus = 1
        workspace.key("c")
        self.assertEqual(self.clipboard_calls[0][0], ["/fixture/pbcopy"])
        self.assertIn("--dry-run", self.clipboard_calls[0][1]["input"])
        job = self.attach_job(workspace)
        workspace.key("i")
        workspace.key("\x16")
        self.assertEqual(self.clipboard_calls[-1][0], ["/fixture/pbpaste"])
        self.assertEqual(workspace.buffer, "PASTED ANSWER")
        self.assertEqual(job.answers, [])

    def test_bracketed_and_unbracketed_paste_never_execute_shortcuts_or_submit(self):
        for bracketed in (False, True):
            workspace = self.workspace()
            payload = list("\x1b[200~ry\n\x1b[201~" if bracketed else "ry\n")
            before = len(MemoryJob.instances)
            workspace.feed_keys(payload)
            self.assertEqual(len(MemoryJob.instances), before)
            self.assertIsNone(workspace.modal)
            self.assertFalse(workspace.should_exit)
            job = self.attach_job(workspace)
            workspace.key("i")
            workspace.feed_keys(payload)
            self.assertEqual(workspace.buffer, "ry ")
            self.assertEqual(job.answers, [])
            self.assertEqual(workspace.modal, "input")

    def test_escape_bearing_paste_never_runs_shortcuts_or_approves_existing_confirmation(self):
        for confirmation_open in (False, True):
            for payload in ("\x1b[31mry", "ry\x1b", "\x1b[200~TEXT\x1b[201~ry"):
                with self.subTest(confirmation_open=confirmation_open, payload=repr(payload)):
                    workspace = self.workspace()
                    if confirmation_open:
                        workspace.request_action("update")
                        self.assertEqual(workspace.modal, "confirm")
                    before = len(MemoryJob.instances)
                    workspace.feed_keys(list(payload))
                    self.assertEqual(len(MemoryJob.instances), before)
                    self.assertIsNone(workspace.job)

    def test_progress_waiting_and_warning_exit_keep_distinct_results(self):
        workspace = self.workspace()
        job = self.attach_job(workspace)
        job.chunks = ["\x1b[31m42% overall\x1b[0m\nAnswer?"]
        workspace.tick()
        self.assertEqual(workspace.progress, 42)
        self.assertEqual(workspace.status, "waiting")
        self.assertNotIn("\x1b", "\n".join(workspace.log) + workspace.partial)
        job.running, job.returncode = False, 10
        workspace.tick()
        self.assertEqual(workspace.status, "warnings")
        self.assertEqual(workspace.last_returncode, 10)
        self.assertIn("10", workspace.notice)
        self.assertNotIn("{code}", workspace.notice)

    def test_active_job_prevents_second_job_and_interruption_requires_confirmation(self):
        workspace = self.workspace()
        job = self.attach_job(workspace)
        workspace.request_action("doctor")
        self.assertEqual(len(MemoryJob.instances), 1)
        self.assertEqual(workspace.notice, workspace.t("busy"))
        workspace.key("x")
        workspace.key("\n")
        self.assertFalse(job.interrupted)
        workspace.key("x")
        workspace.key("y")
        self.assertTrue(job.interrupted)
        self.assertFalse(workspace.should_exit)


if __name__ == "__main__":
    unittest.main()
