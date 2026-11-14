import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib/python"))
from test_recipe_acceptance import recipe, record
from source_resolver import resolve_target
from update_plan import build_plan
from user_policy import make_decision, record_decision, source_fingerprint
import policy_runtime as runtime
import update_transaction as tx
import native_update_session as native


class RecipePolicyTests(unittest.TestCase):
    def setUp(self):
        self.r = recipe()
        self.r["acceptance_records"]["update"] = [record(self.r)]
        self.target = dict(
            instance_id="fixture",
            path="/fixture/apps/Fixture.app",
            real_path="/fixture/apps/Fixture.app",
            bundle_id=self.r["candidate"]["bundle_id"],
            team_id=self.r["candidate"]["team_id"],
            channel="stable",
            presence="present",
            freshness="fresh",
            running=False,
            short_version="1.0",
            build_version="100",
            architectures=["arm64"],
            evidence=[
                dict(
                    kind="vendor_signature",
                    bundle_id=self.r["candidate"]["bundle_id"],
                    team_id=self.r["candidate"]["team_id"],
                )
            ],
        )
        self.snapshot = dict(
            snapshot_id="s",
            profile_id="p",
            generation=1,
            instances=[self.target],
            packages=[],
            sources={},
            os_version="15.1",
        )
        self.catalog = dict(recipes=[], verified_recipes=[self.r])

    def test_accepted_v2_recipe_reaches_plan_and_binds_consent(self):
        r = resolve_target(self.target, self.snapshot, self.catalog)
        self.assertEqual(r["capability"], "reviewed_direct")
        p = build_plan(self.snapshot, [r], {}, "2026-11-14T00:00:00Z")
        a = p["actions"][0]
        self.assertEqual(a["recipe"]["candidate"]["version"], "2.0")
        self.assertEqual(a["to_version"], "2.0")
        old = source_fingerprint(self.target, r)
        self.r["revision"] = 2
        new = resolve_target(self.target, self.snapshot, self.catalog)
        self.assertNotEqual(old, source_fingerprint(self.target, new))

    def test_receipt_and_channel_conflicts_never_get_vendor_authority(self):
        self.target["evidence"].append(dict(kind="app_store_receipt"))
        r = resolve_target(self.target, self.snapshot, self.catalog)
        self.assertNotEqual(r["capability"], "reviewed_direct")
        self.target["evidence"].pop()
        self.target["channel"] = "unknown"
        self.assertNotEqual(
            resolve_target(self.target, self.snapshot, self.catalog)["capability"],
            "reviewed_direct",
        )

    def test_unaccepted_recipe_only_advises(self):
        self.r["acceptance_records"]["update"] = []
        self.assertNotEqual(
            resolve_target(self.target, self.snapshot, self.catalog)["capability"],
            "reviewed_direct",
        )

    def test_native_pending_barrier_blocks_manager_guard(self):
        from update_scheduler import claim_action_resources

        with tempfile.TemporaryDirectory() as d:
            root = str(Path(d).resolve())
            os.chmod(root, 0o700)
            lease = claim_action_resources(
                dict(
                    action_id="native",
                    resources=["path:/fixture/apps/Fixture.app"],
                    scope_complete=True,
                    parallel_safe=True,
                ),
                root,
            )
            plan = dict(
                profile_id="p",
                actions=[
                    dict(
                        action_id="manager",
                        target={"kind": "app", "id": "fixture"},
                        target_path="/fixture/apps/Fixture.app",
                        expected_target=self.target,
                    )
                ],
            )
            with (
                patch.object(runtime, "load_plan", return_value=plan),
                patch.object(runtime, "load_policies", return_value={}),
                patch.object(runtime, "_check_binding"),
                patch.object(runtime, "_append"),
                patch.object(
                    runtime,
                    "reobserve_action",
                    side_effect=AssertionError("pending writer must stop"),
                ),
            ):
                result = runtime.guard_action("fixture", "manager", root)
            self.assertFalse(result["allowed"])
            self.assertEqual(result["reason_code"], "pending_updater_session")
            lease.finish("not_started", helpers_complete=True)

    def test_native_plan_dispatches_only_registered_accepted_driver_and_separate_controls(
        self,
    ):
        from update_scheduler import claim_action_resources, pending_sessions

        self.r.update(
            adapter_id="silent_launch",
            update_mechanism="native_updater",
            requirement_graph=dict(nodes=[], edges=[]),
        )
        self.r["effect_scope"]["update"] = ["native_update"]
        self.r["effect_scope"]["lifecycle"] = ["launch_app", "quit_owned_app"]
        permissions = ["native_update", "launch_app", "quit_owned_app"]
        self.r["acceptance_records"]["update"] = [
            record(self.r, permissions=permissions)
        ]
        self.r["acceptance_records"]["lifecycle"] = [
            record(self.r, "lifecycle", permissions=permissions)
        ]
        calls = []

        def observe(action, state):
            value = dict(
                application_running=False,
                helpers_observed=True,
                helpers_complete=True,
                target_reobserved=True,
                signature_verified=True,
                source_verified=True,
            )
            if calls:
                value["installed"] = self.r["candidate"]
            return value

        driver = native.NativeDriver(
            observe=observe, trigger=lambda *_: calls.append("trigger")
        )
        with (
            tempfile.TemporaryDirectory() as d,
            patch.dict(native.NATIVE_DRIVERS, {"silent_launch": driver}),
        ):
            root = str(Path(d).resolve())
            os.chmod(root, 0o700)
            resolution = resolve_target(self.target, self.snapshot, self.catalog)
            self.assertEqual(resolution["capability"], "reviewed_native")
            decision = make_decision(
                self.target,
                resolution,
                "allow_native_launch",
                "native_launch",
                "2026-11-14T00:00:00Z",
                lifecycle_permissions=["quit_owned_app"],
            )
            policy = record_decision(decision, {})
            plan = build_plan(
                self.snapshot, [resolution], policy, "2026-11-14T00:00:00Z"
            )
            action = plan["actions"][0]
            self.assertTrue(action["allow_native_quit"])
            self.assertFalse(action["allow_native_restart"])
            current = dict(self.target, resolution=resolution)
            observed = dict(
                good=True,
                receipt_present=False,
                running=False,
                bundle_id=self.target["bundle_id"],
                team_id=self.target["team_id"],
                version="1.0",
                build="100",
                architectures=["arm64"],
                host_os="15.1",
            )
            with (
                claim_action_resources(action, root) as lease,
                patch.object(runtime, "load_plan", return_value=plan),
                patch.object(runtime, "load_policies", return_value=policy),
                patch.object(runtime, "_check_binding"),
                patch.object(runtime, "guard_action", return_value={"allowed": True}),
                patch.object(runtime, "utc_now", return_value="2026-11-14T00:00:01Z"),
                patch.object(runtime, "reobserve_action", return_value=current),
                patch.object(tx, "observe_bundle", return_value=observed),
            ):
                result = runtime._execute_reviewed_recipe(
                    "fixture", action, root, lease
                )
            self.assertTrue(result["verified"], result)
            self.assertEqual(calls, ["trigger"])
            self.assertEqual(pending_sessions(root), [])

    def test_initial_launch_consent_never_grants_quit_or_restart(self):
        resolution = resolve_target(self.target, self.snapshot, self.catalog)
        decision = make_decision(
            self.target,
            resolution,
            "allow_native_launch",
            "native_launch",
            "2026-11-14T00:00:00Z",
        )
        self.assertNotIn("lifecycle_permissions", decision)
        with self.assertRaises(ValueError):
            make_decision(
                self.target,
                resolution,
                "allow_update_same_source",
                "direct_update",
                "2026-11-14T00:00:00Z",
                lifecycle_permissions=["quit_owned_app"],
            )


if __name__ == "__main__":
    unittest.main()
