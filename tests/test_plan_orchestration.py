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
from plan_orchestration import format_preview, parse_choices, review_choices, review_internet_batch, prepare_run


class ChoiceTests(unittest.TestCase):
    class TTY(io.StringIO):
        def isatty(self):
            return True

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
        for value in ("a1,a1", "a0", "a2", "yes", "a1,garbage", "1,garbage", "1,a1", "all"):
            with self.assertRaises(ValueError):
                parse_choices(value, [self.action()])

    def review(self, actions, answer, preferences=False, ready=True):
        stream, output = self.TTY(answer), io.StringIO()
        env = {"MAC_UPDATE_YES": "0", "MAC_UPDATE_NONINTERACTIVE": "0",
               "MAC_UPDATE_PREFERENCES": "1" if preferences else "0"}
        with patch.dict(os.environ, env), patch(
            "plan_orchestration.select.select",
            return_value=([stream] if ready else [], [], []),
        ):
            result = review_choices({"actions": actions}, stream, output)
        return result, output.getvalue()

    def test_tui_prompt_is_explicit_and_cli_has_no_control_marker(self):
        for child in ('0', '1'):
            with patch.dict(os.environ, {'MAC_UPDATE_TUI_CHILD': child}):
                result, output = self.review([self.action()], 'a1\n')
            self.assertEqual(result, {'a': 'allow_update_same_source'})
            self.assertEqual('@@MAC_UPDATE_PROMPT' in output, child == '1')

    def numbered_actions(self, count, **changes):
        return [self.action(action_id="id%d" % n,
                            expected_target={"name": "Target%d" % n}, **changes)
                for n in range(1, count + 1)]

    def test_partial_scan_actions_are_summarized_without_impossible_choices(self):
        actions = self.numbered_actions(
            240, reason_codes=["scan_partial", "consent_required"]
        )
        result, output = self.review(actions, "a1\n", ready=False)
        self.assertEqual(result, {})
        self.assertEqual(output.count("Target"), 0)
        self.assertIn("240 targets cannot be approved", output)
        self.assertIn("--preferences", output)
        self.assertNotIn("Waiting for your choice", output)

    def test_normal_numbering_selects_only_eligible_actions(self):
        actions = [self.action(action_id="blocked", reason_codes=[
            "scan_partial", "consent_required"
        ])] + self.numbered_actions(2)
        result, output = self.review(actions, "a2\n")
        self.assertEqual(result, {"id2": "allow_update_same_source"})
        self.assertNotIn("scan_partial", output)
        self.assertIn("1: Target1", output)
        self.assertIn("2: Target2", output)

    def test_eligible_choices_are_paged_with_stable_global_numbers(self):
        result, output = self.review(self.numbered_actions(17), "n\na11\n")
        self.assertEqual(result, {"id11": "allow_update_same_source"})
        self.assertIn("Page 1/2", output)
        self.assertIn("Page 2/2", output)
        self.assertIn("11: Target11", output)

    def test_unseen_page_cannot_be_approved(self):
        for answer in ("a11\n", "11\n"):
            with self.subTest(answer=answer):
                result, output = self.review(self.numbered_actions(17), answer)
                self.assertEqual(result, {})
                self.assertNotIn("11: Target11", output)
                self.assertIn("Invalid selection", output)

    def test_plain_numbers_grant_only_explicit_displayed_scopes(self):
        result, _ = self.review(self.numbered_actions(3), "1,3\n")
        self.assertEqual(result, {"id1": "allow_update_same_source", "id3": "allow_update_same_source"})

    def test_review_uses_translated_human_labels_in_all_seven_languages(self):
        code = '''import io, json, os, sys
from unittest.mock import patch
from plan_orchestration import review_choices, format_preview
class TTY(io.StringIO):
    def isatty(self): return True
stream, output = TTY("a1\\n"), io.StringIO()
plan = json.loads(sys.argv[1])
with patch("plan_orchestration.select.select", return_value=([stream], [], [])):
    result = review_choices(plan, stream, output)
print(json.dumps(dict(result=result, review=output.getvalue(), preview=format_preview(plan),
    title=os.environ["L_PLAN_TITLE"], scope=os.environ["L_PLAN_SCOPE_MANAGER_FMT"] % "Homebrew",
    question=os.environ["L_PLAN_REVIEW_CHOICES"], waiting=os.environ["L_PLAN_WAITING_FMT"].split("%s")[0],
    summary=os.environ["L_PLAN_PREVIEW_SUMMARY_FMT"] % (0, 1, 0, 0),
    consent=os.environ["L_PLAN_PREVIEW_CONSENT"])))'''
        shell = 'SCRIPT_DIR="$1"; . "$SCRIPT_DIR/i18n/loader.sh"; PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c "$2" "$3"'
        for locale in ("en", "pl", "de", "fr", "es", "it", "pt"):
            with self.subTest(locale=locale):
                env = dict(os.environ, MAC_UPDATE_LANG=locale,
                           MAC_UPDATE_YES="0", MAC_UPDATE_NONINTERACTIVE="0", MAC_UPDATE_PREFERENCES="0")
                result = subprocess.run(
                    ["/bin/bash", "-c", shell, "review-fixture", str(ROOT), code,
                     json.dumps({"actions": [self.action()]})],
                    env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                data = json.loads(result.stdout)
                self.assertEqual(data["result"], {"a": "allow_update_same_source"})
                for key in ("title", "scope", "question", "waiting"):
                    self.assertIn(data[key], data["review"])
                for key in ("summary", "consent"):
                    self.assertIn(data[key], data["preview"])
                self.assertNotIn("consent_required", data["review"] + data["preview"])
                self.assertNotIn("manager_update", data["review"] + data["preview"])

    def test_preferences_keeps_manual_and_blocked_choices_through_paging(self):
        actions = self.numbered_actions(
            12, kind="manual", reason_codes=["manual_by_policy"]
        )
        result, output = self.review(actions, "n\nm11,r12\n", preferences=True)
        self.assertEqual(result, {"id11": "preserve_source", "id12": "reset"})
        self.assertIn("Page 2/2", output)
        self.assertIn("12: Target12", output)

    def test_cancel_empty_and_eof_report_no_new_permission_changes(self):
        for answer in ("q\n", "\n", ""):
            with self.subTest(answer=answer):
                result, output = self.review([self.action()], answer)
                self.assertEqual(result, {})
                self.assertIn("Choice cancelled. No new permissions changed.", output)

    def test_navigation_does_not_reset_the_timeout_budget(self):
        with patch("time.monotonic", side_effect=[0, 60, 121]):
            result, output = self.review(self.numbered_actions(17), "n\na11\n")
        self.assertEqual(result, {})
        self.assertIn("60 seconds remaining", output)
        self.assertIn("Choice timed out. No new permissions changed.", output)

    def test_short_preview_prioritizes_grantable_scope_over_blocked_targets(self):
        blocked = self.numbered_actions(240, reason_codes=["scan_partial", "consent_required"])
        eligible = self.action(action_id="eligible", expected_target={"name": "Eligible app"})
        manual = self.action(action_id="manual", kind="manual", reason_codes=["manual_by_policy"])
        output = format_preview({"actions": blocked + [eligible, manual]})
        self.assertIn("Eligible scopes: 0; need consent: 1; blocked: 240; manual or skipped: 1", output)
        self.assertLess(output.index("Eligible app"), output.index("Target1"))
        self.assertEqual(output.count("Target"), 9)
        self.assertNotIn("/fixture/Applications", output)
        self.assertNotIn("scan_partial", output)
        self.assertNotIn("manager_update", output)

    def test_timeout_is_explicit_without_granting_permission(self):
        result, output = self.review([self.action()], "a1\n", ready=False)
        self.assertEqual(result, {})
        self.assertIn("Waiting for your choice", output)
        self.assertIn("Choice timed out. No new permissions changed.", output)

    def batch_action(self, index=1, **changes):
        return self.action(action_id='batch%d' % index, kind='manual', adapter_id='vendor', action_scope='delegated_native_update',
                           reason_codes=['manual_by_policy'], expected_resolution={'source': 'vendor'},
                           expected_target={'name': 'Fixture%d' % index}, **changes)

    def batch_review(self, actions, answer, **environment):
        stream, output = self.TTY(answer), io.StringIO()
        env = {'MAC_UPDATE_YES': '0', 'MAC_UPDATE_NONINTERACTIVE': '0', **environment}
        with patch.dict(os.environ, env), patch('plan_orchestration.batch_approval_choice',
                side_effect=lambda action: 'allow_native_launch' if action['action_scope'] == 'delegated_native_update' and action['reason_codes'] in ([], ['manual_by_policy'], ['consent_required']) else None), \
             patch('plan_orchestration.select.select', return_value=([stream], [], [])):
            result = review_internet_batch({'actions': actions}, stream, output)
        return result, output.getvalue()

    def test_batch_requires_exact_explicit_word_and_all_pages_before_any_grant(self):
        actions = [self.batch_action(i) for i in range(1, 18)]
        choices, output = self.batch_review(actions, 'AUTO\n')
        self.assertEqual(choices, {})
        self.assertNotIn('Fixture11', output)
        choices, output = self.batch_review(actions, 'n\nAUTO\n')
        self.assertEqual(choices, {a['action_id']: 'allow_native_launch' for a in actions})
        self.assertIn('Fixture17', output)
        self.assertIn('/fixture/Applications/Example.app', output)
        self.assertIn('concurrently', output)
        self.assertIn('DeepSeek', output)

    def test_batch_cancel_yes_noninteractive_and_untrusted_stream_never_grant(self):
        actions = [self.batch_action()]
        for answer in ('', '\n', 'q\n', 'yes\n', '1\n', 'auto\n', 'AUTO,1\n'):
            self.assertEqual(self.batch_review(actions, answer)[0], {})
        for env in ({'MAC_UPDATE_YES': '1'}, {'MAC_UPDATE_NONINTERACTIVE': '1'}):
            self.assertEqual(self.batch_review(actions, 'AUTO\n', **env)[0], {})
        with patch('plan_orchestration.batch_approval_choice', return_value='allow_native_launch'):
            self.assertEqual(review_internet_batch({'actions': actions}, io.StringIO('AUTO\n'), io.StringIO()), {})

    def test_batch_does_not_offer_exclusions_or_other_manager_scopes(self):
        actions = [self.batch_action(), self.batch_action(2), self.batch_action(3)]
        actions[1]['reason_codes'] = ['ignored_by_policy']
        actions[2]['action_scope'] = 'manager_update'
        choices, output = self.batch_review(actions, 'AUTO\n')
        self.assertEqual(choices, {'batch1': 'allow_native_launch'})
        self.assertNotIn('Fixture2', output)
        self.assertNotIn('Fixture3', output)

    def test_declined_batch_defers_saved_grants_for_this_run_without_policy_writes(self):
        import copy
        import plan_orchestration as planner
        plan = {'actions': [self.batch_action()]}
        plan['actions'][0]['reason_codes'] = []
        with tempfile.TemporaryDirectory() as session, patch.dict(os.environ, {'MAC_UPDATE_AUTOMATIC_INTERNET_BATCH': '1'}), \
             patch.object(planner, 'batch_approval_choice', return_value='allow_native_launch'), \
             patch.object(planner, 'review_internet_batch', return_value={}), \
             patch.object(planner, 'review_choices', return_value={}) as ordinary, \
             patch.object(planner, 'build_runtime_plan', return_value=copy.deepcopy(plan)), \
             patch.object(planner, 'refresh_inventory'), patch('update_transaction.recover_pending_transactions', return_value=[]), \
             patch.object(planner, 'record_plan_decisions') as record, patch.object(planner, 'save_plan') as save, \
             patch.object(planner, 'emit_plan'):
            self.assertEqual(prepare_run('/fixture', session, self.TTY(''), io.StringIO()), 0)
            self.assertEqual(ordinary.call_args.args[0]['actions'], [])
            deferred = save.call_args.args[0]['actions'][0]
            self.assertIn('deferred_by_user', deferred['reason_codes'])
            self.assertEqual(deferred['kind'], 'skip')
            record.assert_not_called()
        self.assertEqual(plan['actions'][0]['reason_codes'], [])


    def test_batch_keeps_native_launch_and_replacement_permissions_distinct(self):
        from test_installed_native_updaters import target, plan_for
        native = plan_for(target(), 'preserve_source')[0]['actions'][0]
        installed = target('/Applications/KeePassXC.app')
        installed.update(instance_id='keepass', name='KeePassXC', bundle_id='org.keepassxc.keepassxc', team_id='FIXTURE123')
        installed['evidence'][0].update(bundle_id=installed['bundle_id'], team_id=installed['team_id'])
        replacement = plan_for(installed, 'preserve_source')[0]['actions'][0]
        stream, output = self.TTY('AUTO\n'), io.StringIO()
        with patch.dict(os.environ, {'MAC_UPDATE_YES': '0', 'MAC_UPDATE_NONINTERACTIVE': '0'}), \
             patch('plan_orchestration.select.select', return_value=([stream], [], [])):
            choices = review_internet_batch({'actions': [native, replacement]}, stream, output)
        self.assertEqual(choices[native['action_id']], 'allow_native_launch')
        self.assertEqual(choices[replacement['action_id']], 'allow_update_same_source')
        self.assertIn('download and replace', output.getvalue())
        self.assertIn('native updater', output.getvalue())
        self.assertEqual(native['reason_codes'], ['manual_by_policy'])
        self.assertEqual(replacement['reason_codes'], ['manual_by_policy'])
        google = target('/Applications/Google Chrome.app')
        google.update(instance_id='chrome', name='Google Chrome', bundle_id='com.google.Chrome', team_id='GOOGLEFIXT')
        google['evidence'][0].update(bundle_id=google['bundle_id'], team_id=google['team_id'])
        group = plan_for(google, 'preserve_source')[0]['actions'][0]
        stream, output = self.TTY('AUTO\n'), io.StringIO()
        with patch.dict(os.environ, {'MAC_UPDATE_YES':'0', 'MAC_UPDATE_NONINTERACTIVE':'0'}), \
             patch('plan_orchestration.select.select', return_value=([stream], [], [])):
            decisions = review_internet_batch({'actions':[group]}, stream, output)
        self.assertEqual(decisions, {group['action_id']:'allow_update_same_source'})
        self.assertIn('ALL registered Google products', output.getvalue())
        self.assertIn('complete registration list is unknown', output.getvalue())
        self.assertIn('broader than the listed apps', output.getvalue())

    def test_batch_navigation_uses_one_finite_timeout_budget(self):
        with patch('plan_orchestration.time.monotonic', side_effect=[0, 60, 121]):
            choices, output = self.batch_review([self.batch_action(i) for i in range(1, 18)], 'n\nAUTO\n')
        self.assertEqual(choices, {})
        self.assertIn('60 seconds remaining', output)
        self.assertIn('timed out', output)

    def test_fresh_batch_choices_record_once_before_other_manager_review(self):
        import copy
        import plan_orchestration as planner
        native = self.batch_action()
        manager = self.action(action_id='manager', adapter_id='homebrew')
        plan = {'actions': [native, manager]}
        events = []
        def record(current, choices):
            events.append(('record', choices))
            refreshed = copy.deepcopy(current)
            for action in refreshed['actions']:
                if action['action_id'] in choices:
                    action['reason_codes'] = []
            return refreshed
        def ordinary(current, stream, output):
            self.assertEqual([a['action_id'] for a in current['actions']], ['manager'])
            events.append(('ordinary', None))
            return {'manager': 'allow_update_same_source'}
        with tempfile.TemporaryDirectory() as session, patch.dict(os.environ, {'MAC_UPDATE_AUTOMATIC_INTERNET_BATCH': '1'}), \
             patch.object(planner, 'batch_approval_choice', side_effect=lambda a: 'allow_native_launch' if a['action_scope']=='delegated_native_update' else None), \
             patch.object(planner, 'review_internet_batch', return_value={'batch1':'allow_native_launch'}), \
             patch.object(planner, 'review_choices', side_effect=ordinary), \
             patch.object(planner, 'record_plan_decisions', side_effect=record), \
             patch.object(planner, 'build_runtime_plan', return_value=copy.deepcopy(plan)), \
             patch.object(planner, 'refresh_inventory'), patch('update_transaction.recover_pending_transactions', return_value=[]), \
             patch.object(planner, 'save_plan') as save, patch.object(planner, 'emit_plan'):
            self.assertEqual(prepare_run('/fixture', session, self.TTY(''), io.StringIO()), 0)
            self.assertEqual(events, [('record', {'batch1':'allow_native_launch'}), ('ordinary', None), ('record', {'manager':'allow_update_same_source'})])
            self.assertTrue(all(not a['reason_codes'] for a in save.call_args.args[0]['actions']))

    def test_batch_and_system_barrier_labels_exist_in_all_seven_languages(self):
        keys = ('L_PLAN_BATCH_TITLE_FMT', 'L_PLAN_BATCH_SCOPE', 'L_PLAN_BATCH_NONE',
                'L_PLAN_BATCH_QUESTION', 'L_PLAN_BATCH_READ_ALL', 'L_PLAN_SCOPE_LEGACY',
                'L_ALL_SYSTEM_NATIVE_PENDING', 'L_PLAN_SCOPE_GOOGLE_GROUP', 'L_PLAN_BATCH_PREVIEW')
        for language in ('en', 'pl', 'de', 'es', 'fr', 'it', 'pt'):
            text = (ROOT / 'i18n' / ('lang_'+language+'.sh')).read_text()
            for key in keys:
                self.assertEqual(sum(line.startswith(key+'=') for line in text.splitlines()), 1, (language,key))
            question = next(line for line in text.splitlines() if line.startswith('L_PLAN_BATCH_QUESTION='))
            self.assertIn('AUTO', question)



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
        self.assertIn("21 more targets in JSON", result.stdout)
        self.assertEqual(result.stdout.count("Manual review"), 10)
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
