"""Guarded adapter fixture tests. Never invoke native tools or network."""

import copy
import json
import os
import plistlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib/python"))
import policy_runtime as runtime
from user_policy import make_decision, record_decision
from update_plan import build_plan
from inventory_providers import read_cli_manifests
from source_resolver import resolve_target

ROOT = Path(__file__).resolve().parents[1]


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.state = self.root / "state"
        self.state.mkdir(mode=0o700)
        self.prefix = self.root / "npm"
        self.manifest = self.prefix / "lib/node_modules/tool/package.json"
        self.manifest.parent.mkdir(parents=True)
        self.manifest.write_text('{"name":"tool","version":"1.0.0"}')
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "calls"
        self.npm_info = self.root / "npm-info.json"
        self.npm_info.write_text(json.dumps(dict(name="tool", version="2.0.0")))
        self.env = patch.dict(
            os.environ,
            dict(
                HOME=str(self.root),
                MAC_UPDATE_STATE_DIR=str(self.state),
                PATH=str(self.bin) + ":/usr/bin:/bin",
                CALL_LOG=str(self.log),
            ),
            clear=False,
        )
        self.env.start()
        self.tool("ps", "exit 0")
        self.tool(
            "npm",
            f"""echo "$*" >> "$CALL_LOG"
case "$1" in
 view) cat '{self.npm_info}' ;;
 view) cat '{self.npm_info}';;
prefix) echo '{self.prefix}' ;;
 outdated) echo '{{"tool":{{"current":"1.0.0","wanted":"2.0.0","latest":"2.0.0"}}}}'; exit 1 ;;
 install) printf '%s' '{{"name":"tool","version":"2.0.0"}}' > '{self.manifest}' ;;
 *) exit 1 ;;
esac""",
        )
        target = dict(
            read_cli_manifests(str(self.prefix))["items"][0],
            package_id="pkg1",
            prefix=str(self.prefix),
            presence="present",
            freshness="fresh",
            observed_at=runtime.utc_now(),
            related_instance_ids=[],
        )
        self.snapshot = dict(
            snapshot_id="s1",
            profile_id="p1",
            generation=1,
            instances=[],
            packages=[target],
            sources={},
        )
        self.res = resolve_target(target, self.snapshot, {"recipes": []})
        self.policies = record_decision(
            make_decision(
                target,
                self.res,
                "allow_update_same_source",
                "manager_update",
                runtime.utc_now(),
            ),
            {"profile_id": "p1"},
        )
        runtime.save_policies(self.policies, str(self.state))
        self.plan = build_plan(
            self.snapshot, [self.res], self.policies, runtime.utc_now()
        )
        self.path = self.root / "plan.json"
        runtime.save_plan(self.plan, str(self.path))

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def tool(self, name, body):
        p = self.bin / name
        p.write_text("#!/bin/sh\n" + body + "\n")
        p.chmod(0o755)

    def test_positive_exact_npm_prefix_update_and_verified_result(self):
        self.assertEqual(runtime.run_adapter(str(self.path), "npm"), 0)
        self.assertEqual(json.loads(self.manifest.read_text())["version"], "2.0.0")
        self.assertIn("--prefix " + str(self.prefix), self.log.read_text())
        results = [
            json.loads(l)
            for l in (self.state / "action-results.jsonl").read_text().splitlines()
        ]
        self.assertEqual(results[-1]["status"], "current_verified")

    def test_npm_new_commands_dependencies_or_scripts_are_not_authorized(self):
        for field, value in [
            ("bin", {"surprise": "cli.js"}),
            ("dependencies", {"extra": "*"}),
            ("scripts", {"postinstall": "touch outside"}),
        ]:
            with self.subTest(field=field):
                self.npm_info.write_text(
                    json.dumps(dict(name="tool", version="2.0.0", **{field: value}))
                )
                self.log.unlink(missing_ok=True)
                self.assertEqual(runtime.run_adapter(str(self.path), "npm"), 0)
                self.assertFalse(
                    any(
                        line.startswith("install ")
                        for line in self.log.read_text().splitlines()
                    )
                )
                self.assertEqual(
                    json.loads(self.manifest.read_text())["version"], "1.0.0"
                )

    def test_removed_after_plan_has_zero_mutations(self):
        self.manifest.unlink()
        self.assertEqual(runtime.run_adapter(str(self.path), "npm"), 10)
        self.assertFalse(self.log.exists())

    def test_policy_changed_has_zero_mutations(self):
        runtime.save_policies(
            record_decision(
                make_decision(
                    self.snapshot["packages"][0],
                    self.res,
                    "ignore",
                    "manager_update",
                    runtime.utc_now(),
                ),
                self.policies,
            ),
            str(self.state),
        )
        self.assertEqual(runtime.run_adapter(str(self.path), "npm"), 10)
        self.assertFalse(self.log.exists())

    def test_yes_without_plan_cannot_run_legacy_bootstrap(self):
        for script in ["update_brew.sh", "update_npm_cli.sh", "update_appstore.sh"]:
            with self.subTest(script=script):
                env = dict(os.environ, MAC_UPDATE_YES="1")
                env.pop("MAC_UPDATE_PLAN_PATH", None)
                p = subprocess.run(
                    ["/bin/bash", str(ROOT / script)],
                    env=env,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(p.returncode, 10, p.stdout + p.stderr)
                self.assertFalse(self.log.exists())

    def test_target_lock_is_cross_checkout_and_live_owner_is_not_stolen(self):
        with runtime.TargetLock(str(self.prefix)):
            code = "from policy_runtime import TargetLock; import sys\ntry:\n with TargetLock(sys.argv[1]): pass\nexcept Exception: sys.exit(10)"
            env = dict(os.environ, PYTHONPATH=str(ROOT / "lib/python"))
            proc = subprocess.run(
                [sys.executable, "-c", code, str(self.prefix)],
                env=env,
                capture_output=True,
                text=True,
                cwd=str(self.root),
            )
            self.assertEqual(proc.returncode, 10, proc.stderr)
        with runtime.TargetLock(str(self.prefix)):
            pass

    def test_guard_json_is_structured_and_no_mutation(self):
        r = runtime.guard_action(str(self.path), self.plan["actions"][0]["action_id"])
        self.assertTrue(r["allowed"], r)
        self.assertEqual(r["target"], dict(kind="package", id="pkg1"))
        self.assertFalse(self.log.exists())


class ManagerFixtureTests(unittest.TestCase):
    setUp = RuntimeTests.setUp
    tearDown = RuntimeTests.tearDown
    tool = RuntimeTests.tool

    def brew_fixture(self, kind="formula", artifacts=None):
        self.prefix = self.root / "brew"
        self.prefix.mkdir()
        self.artifacts = (
            artifacts if artifacts is not None else [{"app": ["Sample.app"]}]
        )
        if kind == "formula":
            receipt = self.prefix / "Cellar/sample/1.0.0/INSTALL_RECEIPT.json"
            receipt.parent.mkdir(parents=True)
            receipt.write_text('{"installed_on_request":true}')
        else:
            receipt = (
                self.prefix
                / "Caskroom/sample/.metadata/1.0.0/20261113/Casks/sample.json"
            )
            receipt.parent.mkdir(parents=True)
            receipt.write_text(
                json.dumps(dict(token="sample", artifacts=self.artifacts))
            )
            self.app = self.root / "Applications/Sample.app"
            (self.app / "Contents").mkdir(parents=True)
            with (self.app / "Contents/Info.plist").open("wb") as stream:
                plistlib.dump(
                    dict(
                        CFBundleIdentifier="fixture.sample",
                        CFBundleShortVersionString="1.0.0",
                    ),
                    stream,
                )
            staged = self.prefix / "Caskroom/sample/1.0.0/Sample.app"
            staged.parent.mkdir(parents=True)
            staged.symlink_to(self.app)
        bindir = self.prefix / "bin"
        bindir.mkdir()
        brew = bindir / "brew"
        row = (
            dict(name="sample", versions={"stable": "2.0.0"}, dependencies=[])
            if kind == "formula"
            else dict(token="sample", version="2.0.0", artifacts=self.artifacts)
        )
        info = json.dumps({"formulae" if kind == "formula" else "casks": [row]})
        if kind == "formula":
            update = f"""mkdir -p '{self.prefix}/Cellar/sample/2.0.0'; printf '%s' '{{"installed_on_request":true}}' > '{self.prefix}/Cellar/sample/2.0.0/INSTALL_RECEIPT.json'; rm '{receipt}'; rmdir '{receipt.parent}' """
        else:
            update = f"""mkdir -p '{self.prefix}/Caskroom/sample/.metadata/2.0.0/20261114/Casks' '{self.prefix}/Caskroom/sample/2.0.0'; cp '{receipt}' '{self.prefix}/Caskroom/sample/.metadata/2.0.0/20261114/Casks/sample.json'; ln -s '{self.app}' '{self.prefix}/Caskroom/sample/2.0.0/Sample.app'; /usr/bin/plutil -replace CFBundleShortVersionString -string 2.0.0 '{self.app}/Contents/Info.plist' """
        brew.write_text(
            '#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALL_LOG"\ncase "$1" in\ninfo) printf \'%s\' \''
            + info
            + "' ;;\nupgrade) "
            + update
            + ";;\n*) exit 1;;\nesac\n"
        )
        brew.chmod(0o755)
        from inventory_providers import read_brew_receipts
        from inventory_collect import read_bundle_static

        target = dict(
            read_brew_receipts(str(self.prefix))["items"][0],
            package_id="brew1",
            prefix=str(self.prefix),
            presence="present",
            freshness="fresh",
            observed_at=runtime.utc_now(),
            related_instance_ids=[],
        )
        apps = []
        if kind == "cask" and any(
            e.get("artifact_path") == str(self.app) for e in target["evidence"]
        ):
            app = dict(
                read_bundle_static(str(self.app))["items"][0],
                instance_id="app1",
                path=str(self.app),
                real_path=str(self.app),
                presence="present",
                freshness="fresh",
                scope="optional_root",
                parent_instance_id=None,
                observed_at=runtime.utc_now(),
            )
            app["evidence"].extend(target["evidence"])
            apps = [app]
            target["related_instance_ids"] = ["app1"]
        self.install_plan(target, apps)
        return target

    def install_plan(self, target, apps=None, resolution=None):
        snapshot = dict(
            snapshot_id="s1",
            profile_id="p1",
            generation=1,
            instances=apps or [],
            packages=[target] if "package_id" in target else [],
            sources={},
        )
        if "instance_id" in target:
            snapshot["instances"] = [target]
        resolutions = [
            resolve_target(t, snapshot, {"recipes": []})
            for t in snapshot["instances"] + snapshot["packages"]
        ]
        res = resolution or resolutions[-1]
        policies = record_decision(
            make_decision(
                target,
                res,
                "allow_update_same_source",
                "manager_update",
                runtime.utc_now(),
            ),
            {"profile_id": "p1"},
        )
        policies["revision"] = (
            runtime.load_policies(str(self.state)).get("revision", 0) + 1
        )
        runtime.save_policies(policies, str(self.state))
        self.plan = build_plan(snapshot, resolutions, policies, runtime.utc_now())
        self.path = self.root / (str(len(list(self.root.glob("plan*")))) + ".plan.json")
        runtime.save_plan(self.plan, str(self.path))

    def test_formula_update_is_one_explicit_token_and_no_cleanup(self):
        self.brew_fixture()
        self.assertEqual(runtime.run_adapter(str(self.path), "homebrew"), 0)
        calls = self.log.read_text().splitlines()
        self.assertEqual(
            [c for c in calls if c.startswith("upgrade")], ["upgrade --formula sample"]
        )
        self.assertFalse(
            any(c.startswith(("cleanup", "uninstall", "link", "update")) for c in calls)
        )

    def test_cask_update_reobserves_all_existing_app_artifacts(self):
        self.brew_fixture("cask")
        self.assertEqual(runtime.run_adapter(str(self.path), "homebrew"), 0)
        self.assertIn(
            "upgrade --cask --appdir=" + str(self.app.parent) + " sample",
            self.log.read_text(),
        )

    def test_cask_replaced_with_another_bundle_is_not_authorized(self):
        self.brew_fixture("cask")
        with (self.app / "Contents/Info.plist").open("wb") as stream:
            plistlib.dump(
                dict(
                    CFBundleIdentifier="unrelated.product",
                    CFBundleShortVersionString="1.0.0",
                ),
                stream,
            )
        self.assertEqual(runtime.run_adapter(str(self.path), "homebrew"), 10)
        self.assertFalse(self.log.exists())

    def test_cask_new_dependency_is_manual_without_upgrade(self):
        self.brew_fixture("cask")
        info = {
            "casks": [
                dict(
                    token="sample",
                    version="2.0.0",
                    artifacts=self.artifacts,
                    depends_on={"formula": ["surprise"]},
                )
            ]
        }
        with patch.object(runtime, "_brew_query", return_value=info):
            self.assertEqual(runtime.run_adapter(str(self.path), "homebrew"), 0)
        self.assertFalse(self.log.exists())

    def test_removed_cask_artifact_has_zero_upgrade(self):
        self.brew_fixture("cask")
        import shutil

        shutil.rmtree(self.app)
        self.assertEqual(runtime.run_adapter(str(self.path), "homebrew"), 10)
        self.assertFalse(self.log.exists())

    def test_cask_pkg_artifact_is_manual_and_never_executed(self):
        self.brew_fixture("cask", [{"pkg": ["opaque.pkg"]}])
        self.assertEqual(runtime.run_adapter(str(self.path), "homebrew"), 10)
        self.assertFalse(self.log.exists())

    def test_mas_only_local_id_and_outdated_id_can_update(self):
        from inventory_collect import read_bundle_static

        self.app = self.root / "Applications/Store.app"
        (self.app / "Contents/_MASReceipt").mkdir(parents=True)
        (self.app / "Contents/_MASReceipt/receipt").write_text("marker")
        info = self.app / "Contents/Info.plist"
        with info.open("wb") as stream:
            plistlib.dump(
                dict(
                    CFBundleIdentifier="fixture.store",
                    CFBundleShortVersionString="1.0.0",
                ),
                stream,
            )
        self.tool(
            "mas",
            f"""printf '%s\\n' "$*" >> "$CALL_LOG"
case "$1" in
 list) echo '[{{"id":123,"bundleID":"fixture.store","version":"1.0.0","name":"Store"}}]' ;;
 outdated) echo '123 Store (1.0.0 -> 2.0.0)' ;;
 upgrade) test "$2" = 123 || exit 7; /usr/bin/plutil -replace CFBundleShortVersionString -string 2.0.0 '{info}' ;;
 *) exit 1;;
esac""",
        )
        self.tool("sudo", 'test "$1" = -n || exit 3; shift; exec "$@"')
        target = dict(
            read_bundle_static(str(self.app))["items"][0],
            instance_id="mas1",
            path=str(self.app),
            real_path=str(self.app),
            presence="present",
            freshness="fresh",
            scope="optional_root",
            parent_instance_id=None,
            observed_at=runtime.utc_now(),
        )
        target["evidence"].append(
            dict(
                kind="mas",
                store_id="123",
                bundle_id="fixture.store",
                path=str(self.app),
            )
        )
        self.install_plan(target)
        self.assertEqual(runtime.run_adapter(str(self.path), "app_store"), 0)
        calls = self.log.read_text().splitlines()
        self.assertEqual([c for c in calls if c.startswith("upgrade")], ["upgrade 123"])
        self.assertFalse(any(c.startswith(("install", "get", "search")) for c in calls))


class RuntimeAdditionalTests(RuntimeTests):
    def test_reset_choice_revokes_saved_permission(self):
        plan = runtime.record_plan_decisions(
            self.plan, {self.plan["actions"][0]["action_id"]: "reset"}
        )
        self.assertIn("consent_required", plan["actions"][0]["reason_codes"])
        self.assertEqual(runtime.load_policies()["decisions"], [])

    def test_preview_writes_no_state_or_target_lock(self):
        before = {
            p.relative_to(self.state): p.read_bytes()
            for p in self.state.rglob("*")
            if p.is_file()
        }
        with patch.dict(os.environ, {"MAC_UPDATE_DRY_RUN": "1"}):
            self.assertEqual(runtime.run_adapter(str(self.path), "npm"), 0)
        after = {
            p.relative_to(self.state): p.read_bytes()
            for p in self.state.rglob("*")
            if p.is_file()
        }
        self.assertEqual(before, after)
        self.assertEqual(json.loads(self.manifest.read_text())["version"], "1.0.0")

    def test_stable_policy_rejects_prerelease_and_downgrade(self):
        for version in ["3.0.0-alpha.1", "0.5.0"]:
            self.tool(
                "npm",
                f"""case "$1" in
view) cat '{self.npm_info}';;
prefix) echo '{self.prefix}';;
outdated) echo '{{"tool":{{"current":"1.0.0","latest":"{version}"}}}}'; exit 1;;
*) echo mutation >> "$CALL_LOG";;
esac""",
            )
            self.assertEqual(runtime.run_adapter(str(self.path), "npm"), 10)
            self.assertFalse(self.log.exists())

    def test_unknown_manual_vendor_action_is_neutral(self):
        plan = copy.deepcopy(self.plan)
        a = plan["actions"][0]
        a.update(
            adapter_id="unknown",
            kind="manual",
            action_scope="local_observation",
            reason_codes=["manual_by_policy"],
        )
        a["expected_resolution"].update(source="unknown", capability="inventory_only")
        path = self.root / "manual.json"
        runtime.save_plan(plan, str(path))
        self.assertEqual(runtime.run_adapter(str(path), "vendor"), 0)
        lines = (self.state / "action-results.jsonl").read_text().splitlines()
        self.assertEqual(json.loads(lines[-1])["status"], "manual_by_policy")


class GuardMutationMatrixTests(RuntimeTests):
    def test_changed_observations_never_reach_mutation(self):
        current = runtime.reobserve_action(self.plan["actions"][0])
        observations = [
            dict(current, presence="absent"),
            dict(current, freshness="stale"),
            dict(current, running=True),
            dict(current, running=None),
            dict(current, prefix=str(self.root / "elsewhere")),
            dict(current, source_identity="other"),
            dict(current, resolution=dict(current["resolution"], source="unknown")),
            dict(current, resolution=dict(current["resolution"], source="conflict")),
        ]
        for observation in observations:
            with self.subTest(observation=observation):
                with patch.object(
                    runtime, "reobserve_action", return_value=observation
                ):
                    self.assertEqual(runtime.run_adapter(str(self.path), "npm"), 10)
                self.assertFalse(self.log.exists())

    def test_old_plan_never_reaches_native_command(self):
        self.plan["created_at"] = "2026-01-01T00:00:00Z"
        for action in self.plan["actions"]:
            action["plan_created_at"] = self.plan["created_at"]
        path = self.root / "old.json"
        runtime.save_plan(self.plan, str(path))
        self.assertEqual(runtime.run_adapter(str(path), "npm"), 10)
        self.assertFalse(self.log.exists())

    def test_native_stdout_failure_is_hard_even_if_later_action_defers(self):
        self.tool(
            "npm",
            f"""case "$1" in
view) cat '{self.npm_info}';;
prefix) echo '{self.prefix}';;
outdated) echo '{{"tool":{{"current":"1.0.0","latest":"2.0.0"}}}}'; exit 1;;
install) exit 1;;
esac""",
        )
        second = copy.deepcopy(self.plan["actions"][0])
        second["action_id"] = "second"
        second["kind"] = "manual"
        second["reason_codes"] = ["scan_partial"]
        self.plan["actions"].append(second)
        path = self.root / "mixed.json"
        runtime.save_plan(self.plan, str(path))
        self.assertEqual(runtime.run_adapter(str(path), "npm"), 1)


class PostMutationIdentityTests(RuntimeTests):
    def test_matching_version_with_changed_source_is_not_verified(self):
        observe = runtime.reobserve_action

        def changed(action):
            current = observe(action)
            if current.get("version") == "2.0.0":
                current["resolution"] = dict(current["resolution"], source="conflict")
                current["channel"] = "beta"
            return current

        with patch.object(runtime, "reobserve_action", side_effect=changed):
            self.assertEqual(runtime.run_adapter(str(self.path), "npm"), 10)
        self.assertEqual(
            json.loads(
                (self.state / "action-results.jsonl").read_text().splitlines()[-1]
            )["status"],
            "update_unverified",
        )
