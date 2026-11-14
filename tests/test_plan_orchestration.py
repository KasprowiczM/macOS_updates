"""Master planning and fresh consent stay observational until explicitly chosen."""

import json
import os
import plistlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import io
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib/python"))
from plan_orchestration import parse_choices, review_choices


class ChoiceTests(unittest.TestCase):
    def action(self, **changes):
        action = dict(
            action_id="a",
            kind="update",
            action_scope="manager_update",
            reason_codes=["consent_required"],
            expected_target={"name": "Example"},
            expected_resolution={"source": "homebrew"},
            target_path="/fixture/Applications/Example.app",
            artifact_effects=[],
        )
        action.update(changes)
        return action

    def test_only_explicit_selection_grants_narrow_scope(self):
        self.assertEqual(parse_choices("", [self.action()]), {})
        self.assertEqual(
            parse_choices("a1", [self.action()]), {"a": "allow_update_same_source"}
        )
        self.assertEqual(parse_choices("r1", [self.action()]), {"a": "reset"})

    def test_conflict_cannot_be_approved_but_can_remain_manual(self):
        action = self.action(reason_codes=["source_conflict"])
        with self.assertRaises(ValueError):
            parse_choices("a1", [action])
        self.assertEqual(parse_choices("m1", [action]), {"a": "preserve_source"})

    def test_non_tty_and_yes_never_grant_new_permission(self):
        class TTY(io.StringIO):
            def isatty(self):
                return True

        plan = {"actions": [self.action()]}
        self.assertEqual(review_choices(plan, io.StringIO("a1\n"), io.StringIO()), {})
        with patch.dict(os.environ, {"MAC_UPDATE_YES": "1"}):
            self.assertEqual(review_choices(plan, TTY("a1\n"), io.StringIO()), {})

    def test_saved_manual_choice_is_not_asked_again(self):
        output = io.StringIO()
        plan = {
            "actions": [self.action(kind="manual", reason_codes=["manual_by_policy"])]
        }
        self.assertEqual(review_choices(plan, io.StringIO("a1"), output), {})
        self.assertNotIn("1: Example", output.getvalue())

    def test_duplicate_or_unbounded_selection_cannot_partially_approve(self):
        for value in ("a1,a1", "a0", "a2", "yes", "a1,garbage"):
            with self.assertRaises(ValueError):
                parse_choices(value, [self.action()])


class PlanOrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.repo = self.base / "repo"
        self.repo.mkdir()
        shutil.copy(ROOT / "update_all.sh", self.repo)
        shutil.copy(ROOT / "VERSION", self.repo)
        for folder in ("lib", "i18n", "config"):
            shutil.copytree(ROOT / folder, self.repo / folder)
        self.home = self.base / "home"
        self.home.mkdir()
        self.apps = self.base / "Applications"
        contents = self.apps / "Example.app/Contents"
        contents.mkdir(parents=True)
        (contents / "Info.plist").write_bytes(
            plistlib.dumps(
                {
                    "CFBundleIdentifier": "test.example",
                    "CFBundleName": "Example",
                    "CFBundleShortVersionString": "1",
                }
            )
        )
        self.prefix = self.base / "prefix"
        (self.prefix / "Cellar").mkdir(parents=True)
        self.bin = self.base / "bin"
        self.bin.mkdir()
        for name, body in [
            ("uname", "echo arm64"),
            ("sw_vers", "echo 14.0"),
            ("mas", "exit 0"),
        ]:
            path = self.bin / name
            path.write_text("#!/bin/sh\n" + body + "\n")
            path.chmod(0o755)
        self.state = self.base / "state"
        self.env = dict(
            os.environ,
            HOME=str(self.home),
            PATH=str(self.bin) + ":" + os.environ["PATH"],
            MAC_LANG="en",
            MAC_UPDATE_APP_DIRS=str(self.apps),
            MAC_UPDATE_STATE_DIR=str(self.state),
            MAC_UPDATE_HOMEBREW_PREFIX=str(self.prefix),
            MAC_UPDATE_BREW_PREFIXES=str(self.prefix),
            MAC_UPDATE_CLI_PREFIXES=str(self.prefix),
        )

    def run_master(self, *args):
        return subprocess.run(
            ["/bin/bash", str(self.repo / "update_all.sh"), *args],
            env=self.env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=20,
        )

    def test_plan_reports_unknown_target_without_state_or_markdown_writes(self):
        result = self.run_master("--plan")
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertTrue(plan["actions"])
        self.assertNotIn("update", {a["kind"] for a in plan["actions"]})
        self.assertFalse(self.state.exists())
        self.assertFalse((self.repo / "APPLICATIONS.md").exists())
        self.assertFalse((self.repo / ".mac_update_prefs").exists())

    def test_dry_run_uses_same_decisions_without_consent(self):
        first = self.run_master("--plan")
        second = self.run_master("--dry-run", "--json-summary", "-y")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        planned, preview = json.loads(first.stdout), json.loads(second.stdout)
        self.assertEqual(
            [(x["kind"], x["action_scope"]) for x in planned["actions"]],
            [(x["kind"], x["action_scope"]) for x in preview["actions"]],
        )
        self.assertFalse(self.state.exists())

    def test_plain_dry_run_is_readable_unicode_and_leaves_no_run_state(self):
        info = self.apps / "Example.app/Contents/Info.plist"
        metadata = plistlib.loads(info.read_bytes())
        metadata["CFBundleName"] = "Żółw 测试"
        info.write_bytes(plistlib.dumps(metadata))
        self.env.update(LC_ALL="C", LANG="C")
        before = info.read_bytes()
        result = self.run_master("--dry-run", "-y")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Local update plan", result.stdout)
        self.assertIn("Żółw 测试", result.stdout)
        self.assertNotIn("\\u", result.stdout)
        self.assertFalse(result.stdout.lstrip().startswith("{"))
        self.assertIn("--json-summary", result.stdout)
        self.assertEqual(info.read_bytes(), before)
        for path in (self.state, self.repo / "logs", self.repo / "APPLICATIONS.md",
                     self.repo / "UPDATES.md", self.repo / ".mac_update_prefs"):
            self.assertFalse(path.exists(), str(path))
        self.env["PYTHONIOENCODING"] = "ascii"
        ascii_result = self.run_master("--dry-run")
        self.assertEqual(ascii_result.returncode, 0, ascii_result.stderr)
        self.assertNotIn("Traceback", ascii_result.stderr)
        self.assertIn("Local update plan", ascii_result.stdout)

    def test_all_preview_languages_leave_existing_inventory_unchanged(self):
        plan = json.loads(self.run_master("--plan").stdout)
        snapshot = dict(
            schema_version=1, snapshot_id=plan["snapshot_id"],
            profile_id=plan["profile_id"], generation=0,
            previous_snapshot_id=None, created_at=plan["created_at"], sources={},
            instances=[a["expected_target"] for a in plan["actions"]], packages=[],
        )
        self.state.mkdir(mode=0o700)
        inventory = self.state / "inventory.json"
        inventory.write_text(json.dumps(snapshot), encoding="utf-8")
        inventory.chmod(0o600)
        before = inventory.read_bytes()
        titles = {"en": "Local update plan", "pl": "Plan aktualizacji",
                  "es": "Plan", "it": "Piano", "pt": "Plano",
                  "de": "Plan", "fr": "Plan"}
        for locale, title in titles.items():
            with self.subTest(locale=locale):
                self.env["MAC_UPDATE_LANG"] = locale
                result = self.run_master("--dry-run", "-y")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(title, result.stdout)
                self.assertIn("--json-summary", result.stdout)
                self.assertEqual(inventory.read_bytes(), before)
                self.assertEqual(list(self.state.iterdir()), [inventory])
                self.assertFalse((self.repo / "logs").exists())

    def test_terminal_preview_is_bounded_but_json_keeps_every_target(self):
        for number in range(30):
            shutil.copytree(self.apps / "Example.app", self.apps / ("App%02d.app" % number))
        result = self.run_master("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Local targets: 31", result.stdout)
        self.assertIn("6 more targets in JSON", result.stdout)
        self.assertEqual(result.stdout.count("Manual review"), 25)
        machine = self.run_master("--dry-run", "--json-summary")
        self.assertEqual(machine.returncode, 0, machine.stderr)
        self.assertEqual(len(json.loads(machine.stdout)["actions"]), 31)
        self.assertFalse(self.state.exists())

    def test_localized_preview_error_survives_ascii_output(self):
        self.state.mkdir(mode=0o755)
        self.state.chmod(0o755)  # Invalid private state must remain untouched.
        self.env.update(PYTHONIOENCODING="ascii", MAC_UPDATE_LANG="pl")
        result = self.run_master("--dry-run")
        self.assertEqual(result.returncode, 10, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertTrue(result.stderr.strip())
        self.assertEqual(list(self.state.iterdir()), [])
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o755)

    def test_preview_closed_pipe_does_not_emit_traceback(self):
        # Flush even short previews against a pipe with no reader, without a
        # shell pipeline whose final command could hide the producer status.
        read_fd, write_fd = os.pipe()
        os.close(read_fd)
        try:
            result = subprocess.run(
                ["/bin/bash", str(self.repo / "update_all.sh"), "--dry-run"],
                env=self.env, stdin=subprocess.DEVNULL, stdout=write_fd,
                stderr=subprocess.PIPE, text=True, timeout=20,
            )
        finally:
            os.close(write_fd)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("BrokenPipeError", result.stderr)
        self.assertFalse(self.state.exists())
