import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib/python"))
try:
    import update_scheduler as scheduler
except ImportError:
    scheduler = None


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(scheduler, "shared scheduler missing")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = str(Path(self.tmp.name).resolve())
        os.chmod(self.root, 0o700)

    def action(self, name, resources=None, scope=True):
        return dict(
            action_id=name,
            resources=resources or ["path:/fixture/apps/" + name + ".app"],
            scope_complete=scope,
            parallel_safe=True,
        )

    def test_two_checkouts_share_two_slots_including_unresolved_helpers(self):
        a = scheduler.claim_action_resources(self.action("a"), self.root)
        b = scheduler.claim_action_resources(self.action("b"), self.root)
        a.pending("observer_timeout")
        with self.assertRaisesRegex(ValueError, "capacity"):
            scheduler.claim_action_resources(self.action("c"), self.root)
        b.finish("verified", helpers_complete=True)
        c = scheduler.claim_action_resources(self.action("c"), self.root)
        with self.assertRaisesRegex(ValueError, "pending"):
            scheduler.assert_resources_available(
                self.action("a")["resources"], self.root
            )
        c.finish("verified", helpers_complete=True)
        self.assertEqual(len(scheduler.pending_sessions(self.root)), 1)

    def test_shared_manager_or_helper_never_overlaps(self):
        a = scheduler.claim_action_resources(
            self.action("a", ["manager:brew:/fixture"]), self.root
        )
        with self.assertRaisesRegex(ValueError, "resource"):
            scheduler.claim_action_resources(
                self.action("b", ["manager:brew:/fixture"]), self.root
            )
        a.finish("verified", helpers_complete=True)

    def test_nested_effect_paths_conflict_but_sibling_names_do_not(self):
        first = scheduler.claim_action_resources(self.action("a", ["path:/fixture/apps/Foo.app"]), self.root)
        with self.assertRaisesRegex(ValueError, "resource"):
            scheduler.claim_action_resources(self.action("b", ["path:/fixture/apps/Foo.app/Contents"]), self.root)
        sibling = scheduler.claim_action_resources(self.action("c", ["path:/fixture/apps/Foo.app2"]), self.root)
        sibling.finish("verified", helpers_complete=True)
        first.finish("verified", helpers_complete=True)

    def test_manager_serializes_across_prefixes(self):
        first = scheduler.claim_action_resources(self.action("a", ["manager:npm:/fixture/one"]), self.root)
        with self.assertRaisesRegex(ValueError, "resource"):
            scheduler.claim_action_resources(self.action("b", ["manager:npm:/fixture/two"]), self.root)
        first.finish("verified", helpers_complete=True)

    def test_shared_updater_conflicts_across_resource_spellings(self):
        first = scheduler.claim_action_resources(self.action("a", ["manager:google_updater"]), self.root)
        with self.assertRaisesRegex(ValueError, "resource"):
            scheduler.claim_action_resources(self.action("b", ["shared:google_updater"]), self.root)
        first.finish("verified", helpers_complete=True)

    def test_unconfirmed_helper_keeps_its_product_resource(self):
        def execute(action, lease):
            lease.pending("vendor_completion_unconfirmed")
            return {"status": "triggered_unconfirmed", "verified": False}
        first = self.action("first", ["path:/fixture/app/A.app"])
        result = scheduler.execute_queue([first], execute, self.root)
        self.assertEqual(result[0]['status'], 'triggered_unconfirmed')
        with self.assertRaisesRegex(ValueError, 'resource'):
            scheduler.claim_action_resources(self.action("next", ["path:/fixture/app/A.app"]), self.root)

    def test_unknown_scope_and_system_are_exclusive(self):
        action = self.action("system", ["system"], False)
        a = scheduler.claim_action_resources(action, self.root)
        with self.assertRaises(ValueError):
            scheduler.claim_action_resources(self.action("b"), self.root)
        a.finish("verified", helpers_complete=True)

    def test_exception_and_cli_exit_do_not_release_pending_lease(self):
        with self.assertRaises(RuntimeError):
            with scheduler.claim_action_resources(self.action("a"), self.root):
                raise RuntimeError("crash")
        with self.assertRaises(ValueError):
            scheduler.claim_action_resources(self.action("a"), self.root)
        rows = scheduler.pending_sessions(self.root)
        self.assertEqual(rows[0]["status"], "recovery_required")

    def test_explicit_proof_required_to_reconcile(self):
        lease = scheduler.claim_action_resources(self.action("a"), self.root)
        with self.assertRaises(ValueError):
            lease.finish("verified", helpers_complete=False)
        self.assertFalse(scheduler.reconcile_session(lease.lease_id, {}, self.root))
        self.assertTrue(
            scheduler.reconcile_session(
                lease.lease_id,
                dict(helpers_complete=True, target_reobserved=True, action_id="a"),
                self.root,
            )
        )
        self.assertEqual(scheduler.pending_sessions(self.root), [])

    def test_three_concurrent_claimants_cannot_exceed_two(self):
        barrier = threading.Barrier(3)

        def claim(n):
            barrier.wait()
            try:
                return scheduler.claim_action_resources(self.action(str(n)), self.root)
            except ValueError:
                return None

        with ThreadPoolExecutor(max_workers=3) as pool:
            leases = list(pool.map(claim, range(3)))
        self.assertEqual(sum(x is not None for x in leases), 2)
        for lease in leases:
            if lease:
                lease.finish("verified", helpers_complete=True)

    def test_deterministic_ready_queue_and_cancel(self):
        actions = [self.action("a"), self.action("b"), self.action("c")]
        self.assertEqual(
            [
                a["action_id"]
                for a in scheduler.schedule_ready_actions(actions, [], {"mutations": 2})
            ],
            ["a", "b"],
        )
        self.assertEqual(
            scheduler.schedule_ready_actions(
                actions, [], {"mutations": 2, "cancelled": True}
            ),
            [],
        )
        actions[1]["resources"] = actions[0]["resources"][:]
        self.assertEqual(
            [
                a["action_id"]
                for a in scheduler.schedule_ready_actions(actions, [], {"mutations": 2})
            ],
            ["a", "c"],
        )

    def test_corrupt_or_symlink_registry_fail_closed(self):
        Path(self.root, "scheduler.json").write_text("{")
        with self.assertRaises(ValueError):
            scheduler.claim_action_resources(self.action("a"), self.root)
        Path(self.root, "scheduler.json").unlink()
        Path(self.root, "scheduler.json").symlink_to("/nonexistent")
        with self.assertRaises((ValueError, OSError)):
            scheduler.claim_action_resources(self.action("a"), self.root)

    def test_read_only_barrier_creates_no_state(self):
        absent = str(Path(self.root, "absent"))
        self.assertEqual(scheduler.pending_sessions(absent), [])
        scheduler.assert_resources_available(["path:/fixture/apps/A.app"], absent)
        self.assertFalse(Path(absent).exists())

    def test_queue_overlaps_only_independent_actions_with_same_results(self):
        gate = threading.Barrier(2)
        effects = []
        mutex = threading.Lock()
        actions = [self.action("a"), self.action("b")]

        def execute(action, lease):
            gate.wait(timeout=5)  # A serial implementation cannot satisfy this.
            with mutex:
                effects.append(action["action_id"])
            lease.finish("verified", helpers_complete=True)
            return dict(status="updated_verified", verified=True)

        parallel = scheduler.execute_queue(actions, execute, self.root)
        sequential = []
        for action in actions:
            with scheduler.claim_action_resources(action, self.root) as lease:
                lease.finish("verified", helpers_complete=True)
                sequential.append(
                    dict(
                        status="updated_verified",
                        verified=True,
                        action_id=action["action_id"],
                    )
                )
        self.assertEqual(parallel, sequential)
        self.assertEqual(sorted(effects), ["a", "b"])
        self.assertEqual(scheduler.pending_sessions(self.root), [])

    def test_batch_launches_all_callbacks_and_keeps_global_barrier(self):
        gate = threading.Barrier(2)
        actions = [self.action("a", ["path:/fixture/apps/A.app"]),
                   self.action("b", ["path:/fixture/apps/B.app"])]
        def launch(action, lease):
            gate.wait(timeout=5)
            return {"status": "triggered_unconfirmed", "verified": False,
                    "mutation_started": True, "recovery_required": True}
        results = scheduler.execute_exclusive_batch(actions, launch, self.root)
        self.assertEqual([r['status'] for r in results], ['triggered_unconfirmed'] * 2)
        leases = scheduler.pending_sessions(self.root)
        self.assertEqual(len(leases), 1)
        self.assertEqual(leases[0]['status'], 'recovery_required')
        with self.assertRaises(ValueError):
            scheduler.claim_action_resources(self.action('other'), self.root)

    def test_batch_serializes_shared_updater_without_blocking_other_windows(self):
        gate = threading.Barrier(2)
        active, overlap, members, lock = [], [], [], threading.Lock()
        actions = [dict(self.action('google-a'), legacy_manager_group='google'),
                   dict(self.action('google-b'), legacy_manager_group='google'), self.action('other')]
        def launch(action, lease):
            if action.get('legacy_manager_group'):
                members.extend(member['action_id'] for member in action['batch_group_actions'])
                with lock:
                    overlap.append(bool(active))
                    active.append(action['action_id'])
                if action['action_id'] == 'google-a':
                    gate.wait(timeout=5)
                with lock:
                    active.pop()
            else:
                gate.wait(timeout=5)
            return {'status': 'deferred_by_user', 'mutation_started': False, 'recovery_required': False}
        scheduler.execute_exclusive_batch(actions, launch, self.root)
        self.assertEqual(overlap, [False])
        self.assertEqual(members, ["google-a", "google-b"])

    def test_batch_member_requires_live_owner_and_exact_membership(self):
        checked = []
        def callback(action, lease):
            scheduler.assert_active_batch_member(lease.action_id, action['action_id'], self.root)
            with self.assertRaises(ValueError):
                scheduler.assert_active_batch_member(lease.action_id, 'not-a-member', self.root)
            checked.append(lease.action_id)
            return {'status': 'deferred_by_user', 'mutation_started': False, 'recovery_required': False}
        scheduler.execute_exclusive_batch([self.action('a'), self.action('b')], callback, self.root)
        self.assertEqual(len(checked), 2)
        for owner in (checked[0], 'fake-owner'):
            with self.assertRaises(ValueError):
                scheduler.assert_active_batch_member(owner, 'a', self.root)

    def test_active_lease_with_dead_owner_is_rejected(self):
        lease = scheduler.claim_action_resources(self.action('a'), self.root)
        from unittest.mock import patch
        with patch.object(scheduler.os, 'kill', side_effect=ProcessLookupError):
            with self.assertRaises(ValueError):
                scheduler.assert_active_batch_member('a', 'a', self.root)
        lease.finish('not_triggered', helpers_complete=True)

    def test_individual_member_rejects_recovery_and_other_actions(self):
        lease = scheduler.claim_action_resources(self.action('a'), self.root)
        scheduler.assert_active_batch_member('a', 'a', self.root)
        with self.assertRaises(ValueError):
            scheduler.assert_active_batch_member('a', 'b', self.root)
        lease.pending('unconfirmed')
        with self.assertRaises(ValueError):
            scheduler.assert_active_batch_member('a', 'a', self.root)

    def test_batch_callbacks_share_one_observation_deadline(self):
        seen = []
        actions = [self.action('a'), self.action('b')]
        def launch(action, lease):
            seen.append(action['batch_observation_deadline_monotonic'])
            return {'status': 'deferred_by_user', 'mutation_started': False, 'recovery_required': False}
        scheduler.execute_exclusive_batch(actions, launch, self.root)
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[0], seen[1])

    def test_batch_without_any_launch_releases_barrier(self):
        actions = [self.action('a')]
        result = scheduler.execute_exclusive_batch(actions, lambda action, lease: {
            'status': 'deferred_by_user', 'mutation_started': False,
            'recovery_required': False}, self.root)
        self.assertEqual(result[0]['status'], 'deferred_by_user')
        self.assertEqual(scheduler.pending_sessions(self.root), [])

    def test_fixture_independent_manager_callbacks_overlap(self):
        # Hypothetical admitted fixtures do not certify real manager effects.
        gate = threading.Barrier(2)
        actions = [self.action("a", ["manager:fixture_a", "path:/fixture/a"]),
                   self.action("b", ["manager:fixture_b", "path:/fixture/b"])]
        def execute(action, lease):
            gate.wait(timeout=5)
            lease.finish("verified", helpers_complete=True)
            return {"status": "updated_verified", "verified": True}
        self.assertTrue(all(row["verified"] for row in scheduler.execute_queue(actions, execute, self.root)))

    def test_cancel_stops_next_action_without_killing_active_worker(self):
        cancelled = threading.Event()
        actions = [
            self.action("a", ["manager:shared"]),
            self.action("b", ["manager:shared"]),
        ]
        ran = []

        def execute(action, lease):
            cancelled.set()
            ran.append(action["action_id"])
            lease.finish("verified", helpers_complete=True)
            return dict(status="updated_verified", verified=True)

        results = scheduler.execute_queue(actions, execute, self.root, cancelled.is_set)
        self.assertEqual(ran, ["a"])
        self.assertTrue(results[0]["verified"])
        self.assertEqual(results[1]["reason_code"], "cancelled")

    def test_duplicate_action_ids_rejected_before_any_effect(self):
        with self.assertRaisesRegex(ValueError, "duplicate_action"):
            scheduler.execute_queue(
                [self.action("a"), self.action("a")], lambda *_: self.fail(), self.root
            )


if __name__ == "__main__":
    unittest.main()
