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
