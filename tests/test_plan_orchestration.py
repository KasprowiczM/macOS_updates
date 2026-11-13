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
            ["bash", str(self.repo / "update_all.sh"), *args],
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
