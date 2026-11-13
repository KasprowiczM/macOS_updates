"""First-install transactions use absent paths and never weaken update guards."""

from pathlib import Path
import plistlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib/python"))
import install_execution as execution
from install_plan import build_install_plan
from policy_runtime import utc_now


class InstallFixture:
    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.apps = self.root / "Applications"
        self.apps.mkdir()
        self.dest = self.apps / "Fixture.app"
        self.stage = self.root / "candidate.app"
        self.stage.mkdir()
        (self.stage / "version").write_text("2.0.0")
        self.state = self.root / "state"
        self.state.mkdir(mode=0o700)
        self.recipe = dict(
            id="fixture",
            product_id="fixture-gui",
            name="Fixture",
            edition="gui",
            sources=[
                dict(
                    source_id="vendor",
                    official_url="https://example.org/download",
                    architectures=["arm64"],
                )
            ],
            installation_source="vendor",
            revision="r1",
            version="2.0.0",
            channel="stable",
            bundle_id="fixture.app",
            team_id="TEAM",
            architectures=["arm64"],
            minimum_os="13",
            download_hosts=["example.org"],
            artifact_type="app",
            requires_administrator=False,
            destination=str(self.dest),
            artifact_effects=[str(self.dest)],
            requirements_known=True,
            requirements=[],
            install_adapter="vendor_bundle",
            first_install_acceptance=dict(
                status="passed",
                recipe_revision="r1",
                version="2.0.0",
                source_id="vendor",
            ),
        )
        self.recipes = {"recipes": [self.recipe]}
        self.snapshot = {"environment": {}, "instances": [], "packages": []}
        self.plan = build_install_plan(
            [dict(product_id="fixture-gui", source_id="vendor", edition="gui")],
            self.snapshot,
            self.recipes,
            utc_now(),
        )
        self.action = self.plan["actions"][0]
        self.consent = execution.make_install_consent(
            self.plan, [self.action["action_id"]], utc_now()
        )
        self.captures = []
        return self

    def __exit__(self, *args):
        self.temp.cleanup()

    def observe(self, path):
        p = Path(path)
        return dict(
            exists=p.is_dir(),
            good=p.is_dir(),
            receipt_present=False,
            running=False,
            bundle_id="fixture.app",
            team_id="TEAM",
            version=(p / "version").read_text() if p.is_dir() else None,
            architectures=["arm64"],
            minimum_os="13",
            host_os="26",
        )

    def capture(self, action, observed):
        self.captures.append((action["product_id"], observed["version"]))
        return dict(snapshot_id="new-snapshot", verified_path=action["destination"])

    def run(self, **extra):
        return execution.execute_install_action(
            self.plan,
            self.action["action_id"],
            self.consent,
            self.recipes,
            {},
            staged_app=str(self.stage),
            observe=self.observe,
            snapshot=self.snapshot,
            allowed_roots=[str(self.apps)],
            state_dir=str(self.state),
            snapshot_writer=self.capture,
            **extra,
        )


class InstallExecutionTests(unittest.TestCase):
    def test_positive_exclusive_install_and_snapshot_no_launch(self):
        with InstallFixture() as f:
            result = f.run()
            self.assertEqual(result["status"], "installed_verified")
            self.assertTrue(f.dest.is_dir())
            self.assertEqual((f.dest / "version").read_text(), "2.0.0")
            self.assertEqual(f.captures, [("fixture-gui", "2.0.0")])
            journals = list((f.state / "installation-transactions").glob("*.json"))
            self.assertEqual(len(journals), 1)
            self.assertEqual(journals[0].stat().st_mode & 0o777, 0o600)

    def test_appeared_destination_and_symlink_never_adopted(self):
        for symlink in (False, True):
            with self.subTest(symlink=symlink), InstallFixture() as f:
                if symlink:
                    f.dest.symlink_to(f.stage, target_is_directory=True)
                else:
                    f.dest.mkdir()
                    (f.dest / "foreign").write_text("keep")
                result = f.run()
                self.assertNotEqual(result["status"], "installed_verified")
                self.assertTrue(f.stage.is_dir())
                self.assertEqual(f.captures, [])
                self.assertTrue(
                    f.dest.is_symlink() if symlink else (f.dest / "foreign").exists()
                )

    def test_recipe_graph_plan_consent_expiry_changes_zero_mutation(self):
        for changed in ("recipe", "plan", "expiry", "consent", "graph"):
            with self.subTest(changed=changed), InstallFixture() as f:
                if changed == "recipe":
                    f.recipes["recipes"][0]["revision"] = "r2"
                if changed == "plan":
                    f.plan["actions"][0]["version"] = "3.0.0"
                if changed == "expiry":
                    f.consent["expires_at"] = "2000-01-01T00:00:00Z"
                if changed == "consent":
                    f.consent["action_ids"] = []
                if changed == "graph":
                    f.recipes["recipes"][0]["requirements"] = ["unknown"]
                result = f.run()
                self.assertFalse(f.dest.exists())
                self.assertNotEqual(result["status"], "installed_verified")

    def test_race_after_staging_exclusive_rename_preserves_new_app(self):
        with InstallFixture() as f:

            def fault(phase, journal):
                if phase == "before_commit":
                    f.dest.mkdir()
                    (f.dest / "foreign").write_text("keep")

            result = f.run(fault=fault)
            self.assertEqual((f.dest / "foreign").read_text(), "keep")
            self.assertNotEqual(result["status"], "installed_verified")
            self.assertFalse(list(f.apps.glob(".macupd-install-*")))

    def test_candidate_wrong_signature_arch_min_os_receipt_or_version_rejected(self):
        for changes in [
            dict(good=None),
            dict(team_id="OTHER"),
            dict(bundle_id="other"),
            dict(architectures=["x86_64"]),
            dict(minimum_os="99"),
            dict(receipt_present=True),
            dict(version="3.0.0"),
        ]:
            with self.subTest(changes=changes), InstallFixture() as f:
                observe = f.observe

                def altered(path):
                    value = observe(path)
                    value.update(changes)
                    return value

                f.observe = altered
                result = f.run()
                self.assertFalse(f.dest.exists())
                self.assertNotEqual(result["status"], "installed_verified")

    def test_failure_after_commit_preserves_app_and_requires_recovery(self):
        with InstallFixture() as f:

            def failed_capture(*args):
                raise ValueError("snapshot_failed")

            f.capture = failed_capture
            result = f.run()
            self.assertEqual(result["status"], "recovery_required")
            self.assertTrue(f.dest.exists())

    def test_manual_store_acquisition_requires_exact_consent_and_is_never_installed(
        self,
    ):
        with InstallFixture() as f:
            f.recipe["sources"].append(
                dict(
                    source_id="app_store",
                    official_url="https://apps.apple.com/app/id123",
                )
            )
            plan = build_install_plan(
                [dict(product_id="fixture-gui", source_id="app_store", edition="gui")],
                f.snapshot,
                f.recipes,
                utc_now(),
            )
            calls = []
            consent = execution.make_install_consent(
                plan, [plan["actions"][0]["action_id"]], utc_now()
            )
            result = execution.execute_install_action(
                plan,
                plan["actions"][0]["action_id"],
                consent,
                f.recipes,
                {},
                snapshot=f.snapshot,
                allowed_roots=[str(f.apps)],
                state_dir=str(f.state),
                opener=lambda url: calls.append(url),
            )
            self.assertEqual(calls, ["https://apps.apple.com/app/id123"])
            self.assertEqual(result["status"], "manual_acquisition_opened")
            self.assertFalse(result["verified"])
            self.assertFalse(f.dest.exists())

    def test_cancelled_plan_and_unlisted_action_never_open_browser(self):
        with InstallFixture() as f:
            f.consent["action_ids"] = []
            result = f.run()
            self.assertEqual(result["status"], "deferred")
            self.assertFalse(f.dest.exists())
            self.assertEqual(f.captures, [])


class InstallSafetyEdgeTests(unittest.TestCase):
    def test_source_conflict_at_another_path_blocks_install(self):
        with InstallFixture() as f:
            other = f.apps / "Other.app"
            (other / "Contents").mkdir(parents=True)
            (other / "Contents/Info.plist").write_bytes(
                plistlib.dumps(
                    dict(
                        CFBundleIdentifier="fixture.app",
                        CFBundleShortVersionString="1.0.0",
                    )
                )
            )
            result = f.run()
            self.assertFalse(f.dest.exists())
            self.assertEqual(result["reason_code"], "source_conflict")

    def test_external_bundle_symlink_and_opaque_adapter_cannot_install(self):
        for opaque in (False, True):
            with self.subTest(opaque=opaque), InstallFixture() as f:
                if opaque:
                    f.recipe["install_adapter"] = "vendor_shell"
                    f.plan = build_install_plan(
                        [
                            dict(
                                product_id="fixture-gui",
                                source_id="vendor",
                                edition="gui",
                            )
                        ],
                        f.snapshot,
                        f.recipes,
                        utc_now(),
                    )
                    f.action = f.plan["actions"][0]
                    f.consent = execution.make_install_consent(
                        f.plan, [f.action["action_id"]], utc_now()
                    )
                    # Public/manual acquisition may only open the official link.
                    result = execution.execute_install_action(
                        f.plan,
                        f.action["action_id"],
                        f.consent,
                        f.recipes,
                        {},
                        snapshot=f.snapshot,
                        allowed_roots=[str(f.apps)],
                        state_dir=str(f.state),
                        opener=lambda url: None,
                    )
                    self.assertEqual(result["status"], "manual_acquisition_opened")
                else:
                    (f.stage / "external").symlink_to(f.root / "outside")
                    result = f.run()
                    self.assertNotEqual(result["status"], "installed_verified")
                self.assertFalse(f.dest.exists())

    def test_partial_success_retains_first_app_and_never_removes_shared_dependency(
        self,
    ):
        with InstallFixture() as f:
            shared = f.root / "shared"
            shared.mkdir()
            (shared / "keep").write_text("existing")
            first = f.run()
            self.assertEqual(first["status"], "installed_verified")
            second = f.run()
            self.assertNotEqual(second["status"], "installed_verified")
            self.assertTrue(f.dest.exists())
            self.assertEqual((shared / "keep").read_text(), "existing")

    def test_recipe_does_not_serialize_credentials(self):
        from install_plan import build_install_plan

        with InstallFixture() as f:
            f.recipe["artifact_url"] = "https://user:secret@example.org/payload.zip"
            with self.assertRaises(ValueError):
                build_install_plan(
                    [dict(product_id="fixture-gui", source_id="vendor", edition="gui")],
                    f.snapshot,
                    f.recipes,
                    utc_now(),
                )


class InstallRecoveryTests(unittest.TestCase):
    def test_crash_after_rename_before_checkpoint_is_observation_only_and_idempotent(
        self,
    ):
        from unittest.mock import patch

        with InstallFixture() as f:
            rename = execution._rename_exclusive

            def crash(source, destination):
                rename(source, destination)
                raise SystemExit("crash")

            with patch.object(execution, "_rename_exclusive", side_effect=crash):
                with self.assertRaises(SystemExit):
                    f.run()
            self.assertTrue(f.dest.exists())
            recovered = execution.recover_installations(
                str(f.state),
                observe=f.observe,
                allowed_roots=[str(f.apps)],
                snapshot_writer=f.capture,
            )
            self.assertEqual(recovered[0]["status"], "installed_verified")
            self.assertEqual(len(f.captures), 1)
            self.assertEqual(
                execution.recover_installations(
                    str(f.state),
                    observe=f.observe,
                    allowed_roots=[str(f.apps)],
                    snapshot_writer=f.capture,
                ),
                [],
            )

    def test_crash_after_checkpoint_and_absent_or_bad_destination_never_resume_install(
        self,
    ):
        for state in ("good", "missing", "bad"):
            with self.subTest(state=state), InstallFixture() as f:

                def crash(phase, journal):
                    if phase == "after_commit":
                        raise SystemExit("crash")

                with self.assertRaises(SystemExit):
                    f.run(fault=crash)
                observe = f.observe
                if state == "missing":
                    __import__("shutil").rmtree(f.dest)
                if state == "bad":

                    def observe(path):
                        value = f.observe(path)
                        value["team_id"] = "OTHER"
                        return value

                recovered = execution.recover_installations(
                    str(f.state),
                    observe=observe,
                    allowed_roots=[str(f.apps)],
                    snapshot_writer=f.capture,
                )
                self.assertEqual(
                    recovered[0]["status"],
                    "installed_verified"
                    if state == "good"
                    else "deferred"
                    if state == "missing"
                    else "recovery_required",
                )
                self.assertEqual(f.dest.exists(), state != "missing")
                self.assertTrue(f.stage.exists())

    def test_symlink_or_foreign_journal_cannot_reconcile_arbitrary_target(self):
        with InstallFixture() as f:
            directory = f.state / "installation-transactions"
            directory.mkdir(mode=0o700)
            foreign = f.root / "foreign.json"
            foreign.write_text("{}")
            (directory / "linked.json").symlink_to(foreign)
            result = execution.recover_installations(
                str(f.state),
                observe=f.observe,
                allowed_roots=[str(f.apps)],
                snapshot_writer=f.capture,
            )
            self.assertTrue(all(row["status"] == "recovery_required" for row in result))
            self.assertEqual(foreign.read_text(), "{}")
            self.assertFalse(f.dest.exists())


class InstallStagingSafetyTests(unittest.TestCase):
    def test_raced_external_link_in_copied_bundle_is_rejected(self):
        from unittest.mock import patch

        with InstallFixture() as f:
            copytree = execution.shutil.copytree

            def raced(source, destination, **kwargs):
                result = copytree(source, destination, **kwargs)
                (Path(destination) / "external").symlink_to(f.root / "outside")
                return result

            with patch.object(execution.shutil, "copytree", side_effect=raced):
                result = f.run()
            self.assertFalse(f.dest.exists())
            self.assertNotEqual(result["status"], "installed_verified")

    def test_cleanup_does_not_remove_recreated_foreign_staging_directory(self):
        with InstallFixture() as f:
            created = []

            def race(phase, journal):
                if phase == "before_commit":
                    stage = Path(journal["created_paths"][0])
                    stage.rename(f.root / "moved-owned-stage")
                    stage.mkdir()
                    (stage / "foreign").write_text("keep")
                    created.append(stage)

            result = f.run(fault=race)
            self.assertNotEqual(result["status"], "installed_verified")
            self.assertEqual((created[0] / "foreign").read_text(), "keep")
            self.assertFalse(f.dest.exists())
