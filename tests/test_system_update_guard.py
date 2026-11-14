"""System lease fixtures execute temporary shells, never system update tools."""

import os
import shlex
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib/python"))
import system_update_guard as guard
from update_scheduler import pending_sessions, assert_resources_available


class SystemGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def child(self, mutation=False, verified=False, restart=False):
        script = self.root / "fixture.sh"
        body = "#!/bin/bash\n"
        if mutation:
            code = (
                "import sys; from system_update_guard import send_event; sys.exit(0 if send_event(int(sys.argv[1]), int(sys.argv[2]), 'mutation_started', {'labels':['Fixture-1'], 'restart':"
                + str(restart)
                + "}) else 10)"
            )
            body += (
                shlex.quote(sys.executable)
                + " -c "
                + shlex.quote(code)
                + ' "$$" "$PPID" || exit 10\n'
            )
        if verified:
            code = "import sys; from system_update_guard import send_event; sys.exit(0 if send_event(int(sys.argv[1]), int(sys.argv[2]), 'verified_nonrestart', {'query_exit':0, 'listing':'No new software available.'}) else 10)"
            body += (
                shlex.quote(sys.executable)
                + " -c "
                + shlex.quote(code)
                + ' "$$" "$PPID" || exit 10\n'
            )
        body += "exit 0\n"
        script.write_text(body)
        return script

    def run_child(self, script):
        env = dict(os.environ)
        env["PYTHONPATH"] = (
            str(ROOT / "lib/python") + os.pathsep + env.get("PYTHONPATH", "")
        )
        return guard.run_guarded(
            str(script),
            state_dir=str(self.root),
            env=env,
            boot_reader=lambda: "fixture-boot",
        )

    def test_no_mutation_releases_exclusive_lease(self):
        self.assertEqual(self.run_child(self.child()), 0)
        self.assertEqual(pending_sessions(str(self.root)), [])

    def test_unconfirmed_mutation_returns_10_and_retains_cross_checkout_barrier(self):
        self.assertEqual(self.run_child(self.child(mutation=True)), 10)
        self.assertTrue(pending_sessions(str(self.root)))
        with self.assertRaises(ValueError):
            assert_resources_available(["path:/fixture/Other.app"], str(self.root))

    def test_verified_nonrestart_selected_labels_absent_releases(self):
        self.assertEqual(self.run_child(self.child(mutation=True, verified=True)), 0)
        self.assertEqual(pending_sessions(str(self.root)), [])

    def test_restart_requires_changed_boot_and_fresh_target_proof(self):
        self.assertEqual(self.run_child(self.child(mutation=True, restart=True)), 10)
        context = guard.pending_system_sessions(str(self.root))[0]
        proof = dict(
            query_exit=0,
            listing="No new software available.",
            boot_identity="fixture-boot",
            target_os_verified=True,
        )
        self.assertFalse(
            guard.reconcile_system_session(context["context_id"], proof, str(self.root))
        )
        proof["boot_identity"] = "fixture-next-boot"
        self.assertTrue(
            guard.reconcile_system_session(context["context_id"], proof, str(self.root))
        )
        self.assertEqual(pending_sessions(str(self.root)), [])

    def test_failed_malformed_or_still_pending_listing_is_not_completion_proof(self):
        context = {"labels": ["Fixture-1"]}
        for proof in [
            dict(query_exit=1, listing="No new software available."),
            dict(query_exit=0, listing="Software Update found malformed output"),
            dict(query_exit=0, listing=""),
        ]:
            self.assertFalse(guard._labels_absent(context, proof))

    def test_new_mutation_invalidates_prior_completion_proof(self):
        script = self.child(mutation=True, verified=True)
        first_mutation_line = script.read_text().splitlines()[1]
        script.write_text(
            script.read_text().replace("exit 0\n", first_mutation_line + "\nexit 0\n")
        )
        self.assertEqual(self.run_child(script), 10)
        self.assertTrue(pending_sessions(str(self.root)))
