"""Integration regressions using private fixtures, with no host mutations."""

import contextlib
import copy
import io
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib/python"))
import install_execution as installation
import policy_runtime as runtime
import recipe_adapters as adapters
import test_update_transaction as transaction_fixtures
from test_recipe_acceptance import recipe, record, environment
from test_verified_install import VerifiedInstallFixture
from update_scheduler import claim_action_resources, pending_sessions
from user_policy import digest


class RecipeRecoveryRegressions(unittest.TestCase):
    def test_appstore_retry_timeout_retains_the_original_mutation_lease(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = str(Path(temporary).resolve())
            action = dict(
                action_id="retry-fixture",
                target={"kind": "app", "id": "fixture"},
                expected_target={"name": "Fixture"},
                expected_resolution={"source": "app_store"},
                target_path=root + "/Fixture.app",
                artifact_effects=[],
                adapter_id="app_store",
                reason_codes=[],
                from_version="1",
            )
            plan = dict(actions=[action], plan_id="fixture")
            current = dict(version="1", presence="present", freshness="fresh")
            with (
                patch.object(runtime, "load_plan", return_value=plan),
                patch.object(runtime, "guard_action", return_value={"allowed": True}),
                patch.object(runtime, "reobserve_action", return_value=current),
                patch.object(
                    runtime,
                    "_prepare_command",
                    return_value=(["sudo", "-n", "mas", "upgrade", "123"], "2"),
                ),
                patch.object(runtime, "_run", return_value="123 Fixture (1 -> 2)"),
                patch.object(
                    runtime,
                    "_run_mutation",
                    side_effect=[None, ValueError("mutation_observation_timeout")],
                ) as mutate,
            ):
                self.assertEqual(runtime.run_adapter("fixture", "app_store", root), 10)
            self.assertEqual(mutate.call_count, 2)
            rows = pending_sessions(root)
            self.assertEqual([row["action_id"] for row in rows], [action["action_id"]])
            self.assertEqual(rows[0]["status"], "recovery_required")

    def test_direct_prejournal_authorization_denial_releases_without_phantom_recovery(
        self,
    ):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            apps = root / "apps"
            apps.mkdir()
            destination = apps / "Fixture.app"
            destination.mkdir()
            journal = root / "transactions"
            journal.mkdir(mode=0o700)
            stage = root / "stage"
            stage.mkdir()
            value = recipe()
            value["acceptance_records"]["update"] = [record(value)]
            facts = environment(value)
            target = dict(
                facts["target"],
                real_path=str(destination),
                path=str(destination),
                version="1.0",
                build="100",
                running=False,
                freshness="fresh",
            )
            prepared = adapters.prepare_recipe_action(value, target, "update", facts)
            self.assertTrue(prepared["allowed"], prepared)
            action = dict(
                action_id="direct-fixture",
                target={"kind": "app", "id": "fixture"},
                target_path=str(destination),
                action_scope="direct_update",
                adapter_id="github_dmg",
                expected_target=target,
                expected_resolution={"source": "vendor"},
                recipe=value,
                reason_codes=[],
                artifact_effects=[str(destination)],
            )

            class Observer:
                allowed_roots = [str(apps)]
                transaction_action = action
                permissions = iter([True, True, False])

                def authorize(self):
                    return next(self.permissions)

                def current(self):
                    raise AssertionError("denied before target observation")

                def observe_bundle(self, path):
                    raise AssertionError("denied before signature observation")

            def execute(*unused):
                return adapters.execute_recipe_action(
                    prepared, Observer(), str(journal)
                )

            with (
                patch.object(
                    runtime,
                    "load_plan",
                    return_value=dict(actions=[action], plan_id="fixture"),
                ),
                patch.object(runtime, "guard_action", return_value={"allowed": True}),
                patch.object(runtime, "_execute_reviewed_recipe", side_effect=execute),
                patch.object(
                    adapters,
                    "acquire_candidate",
                    return_value=dict(
                        staging_path=str(stage), bundle_path=str(stage / "Fixture.app")
                    ),
                ),
            ):
                self.assertEqual(
                    runtime.run_adapter("fixture", "vendor", str(root)), 10
                )
            self.assertTrue(destination.is_dir())
            self.assertFalse(list(journal.glob("*.json")))
            self.assertEqual(pending_sessions(str(root)), [])

    def test_direct_interrupted_backup_recovers_with_its_original_pending_lease(self):
        fixture = transaction_fixtures.TransactionTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        state = str(fixture.journals.parent)

        def interrupt(phase, journal):
            if phase == "backed_up":
                raise SystemExit("fixture interruption")

        with self.assertRaises(SystemExit):
            with claim_action_resources(fixture.action, state) as lease:
                with runtime.TargetLock(str(fixture.dest), state, lease.action_id):
                    fixture.run_tx(fault=interrupt)
        self.assertFalse(fixture.dest.exists())
        original = pending_sessions(state)
        self.assertEqual(
            [row["action_id"] for row in original], [fixture.action["action_id"]]
        )
        recovered = transaction_fixtures.tx.recover_pending_transactions(
            state, observe=fixture.observe, allowed_roots=[str(fixture.dest.parent)]
        )
        self.assertEqual(recovered[0]["state"], "rolled_back", recovered)
        self.assertEqual((fixture.dest / "version").read_text(), "1")
        self.assertEqual(pending_sessions(state), [])

    def test_prepared_or_unowned_commit_intent_never_adopts_an_external_install(self):
        for status in ("prepared", "install_commit_intent"):
            with self.subTest(status=status), VerifiedInstallFixture() as fixture:
                fixture.attach()
                fixture.plan()
                with zipfile.ZipFile(io.BytesIO(fixture.payload)) as archive:
                    archive.extractall(fixture.apps)
                directory = fixture.state / "installation-transactions"
                directory.mkdir(mode=0o700)
                journal = dict(
                    schema_version=1,
                    status=status,
                    action=copy.deepcopy(fixture.action),
                    action_fingerprint=digest(fixture.action),
                    destination=str(fixture.destination),
                )
                installation._atomic_json(str(directory / "fixture.json"), journal)
                recovered = installation.recover_installations(
                    str(fixture.state),
                    observe=fixture.observe,
                    allowed_roots=[str(fixture.apps)],
                    snapshot_writer=lambda *args: self.fail(
                        "external installation was adopted"
                    ),
                )
                self.assertFalse(recovered[0]["verified"], recovered)
                self.assertTrue(fixture.destination.exists())
                self.assertEqual(pending_sessions(str(fixture.state)), [])

    def test_install_recovery_rechecks_inode_after_acquiring_the_target_lock(self):
        with VerifiedInstallFixture() as fixture:
            fixture.attach()
            fixture.plan()

            def interrupt(phase, journal):
                if phase == "after_commit":
                    raise OSError("fixture interruption")

            self.assertEqual(
                fixture.run(fault=interrupt)["status"], "recovery_required"
            )
            original_lock = runtime.TargetLock

            @contextlib.contextmanager
            def replace_then_lock(*args, **kwargs):
                retained = fixture.apps / "Retained.app"
                os.rename(fixture.destination, retained)
                shutil.copytree(retained, fixture.destination)
                with original_lock(*args, **kwargs):
                    yield

            with patch.object(
                installation, "TargetLock", side_effect=replace_then_lock
            ):
                recovered = installation.recover_installations(
                    str(fixture.state),
                    observe=fixture.observe,
                    allowed_roots=[str(fixture.apps)],
                    snapshot_writer=lambda *args: self.fail(
                        "recreated installation was adopted"
                    ),
                )
            self.assertFalse(recovered[0]["verified"], recovered)
            self.assertTrue(fixture.destination.exists())
            self.assertEqual(len(pending_sessions(str(fixture.state))), 1)


if __name__ == "__main__":
    unittest.main()
