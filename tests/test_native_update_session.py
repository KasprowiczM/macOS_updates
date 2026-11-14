"""Native lifecycle fixtures: no GUI process, installer or host helper is started."""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib/python"))
import native_update_session as native
from update_scheduler import assert_resources_available, pending_sessions


class Clock:
    def __init__(self):
        self.now = 10.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class NativeSessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.action = dict(
            action_id="fixture-action",
            action_scope="native_launch",
            target={"kind": "app", "id": "fixture"},
            target_path=str(self.root / "Fixture.app"),
            recipe_revision="fixture-v1",
            expected_target={
                "bundle_id": "example.fixture",
                "team_id": "FIXTURETEAM",
                "channel": "stable",
            },
            candidate={
                "version": "2.0",
                "build": "200",
                "bundle_id": "example.fixture",
                "team_id": "FIXTURETEAM",
            },
            timeout_seconds=5,
            allow_native_quit=True,
            allow_native_restart=False,
            resources=["fixture:app"],
            parallel_safe=True,
            scope_complete=True,
        )
        self.process = dict(
            pid=41,
            start_time="fixture-start",
            bundle_id="example.fixture",
            owner_session_id="fixture-session",
        )
        self.state = dict(
            session_id="fixture-session",
            action=copy.deepcopy(self.action),
            state="observing",
            trigger_attempted=True,
            owned_process=self.process,
            deadline_monotonic=15.0,
            observer_boot_id="fixture-boot",
        )
        self.observation = dict(
            process_exists=True,
            process=copy.deepcopy(self.process),
            source_verified=True,
            user_engaged=False,
            engagement_known=True,
            save_dialog=False,
            helpers_observed=True,
            helpers_complete=True,
            boot_id="fixture-boot",
        )

    def test_user_process_pid_reuse_takeover_or_unknown_engagement_blocks_quit(self):
        cases = [
            dict(preexisting=True),
            dict(process=dict(self.process, start_time="reused")),
            dict(user_engaged=True),
            dict(engagement_known=False),
            dict(save_dialog=True),
            dict(process=dict(self.process, owner_session_id="someone-else")),
        ]
        for changes in cases:
            with self.subTest(changes=changes):
                observation = dict(self.observation, **changes)
                self.assertFalse(
                    native.may_control_process(self.state, observation)["allowed"]
                )

    def test_ready_immediately_requests_one_owned_graceful_quit(self):
        state = native.advance_native_session(
            self.state, dict(self.observation, download_ready=True), 10.0
        )
        self.assertEqual(state["operation"], "graceful_quit")
        self.assertEqual(state["state"], "ready")

    def test_no_ready_and_defer_install_never_request_restart(self):
        for observation in [
            self.observation,
            dict(self.observation, download_ready=True, defer_install=True),
        ]:
            state = native.advance_native_session(self.state, observation, 11.0)
            self.assertNotIn(state["operation"], ("graceful_quit", "restart"))

    def test_real_deadline_and_suspend_keep_pending_barrier(self):
        timed = native.advance_native_session(
            self.state, dict(self.observation, download_ready=True), 20.0
        )
        self.assertEqual(timed["state"], "timeout_pending")
        resumed = native.advance_native_session(
            self.state, dict(self.observation, boot_id="different-boot"), 11.0
        )
        self.assertEqual(resumed["state"], "recovery_required")

    def test_updater_relaunch_does_not_transfer_process_ownership(self):
        observation = dict(
            self.observation,
            download_ready=True,
            process=dict(self.process, pid=99, start_time="new"),
        )
        state = native.advance_native_session(self.state, observation, 11.0)
        self.assertEqual(state["state"], "restart_deferred")

    def test_live_helper_prevents_install_complete_and_release(self):
        observation = dict(
            self.observation,
            installed=self.action["candidate"],
            signature_verified=True,
            target_reobserved=True,
            helpers_complete=False,
        )
        state = native.advance_native_session(self.state, observation, 11.0)
        self.assertEqual(state["state"], "install_pending")
        self.assertFalse(state.get("verified", False))

    def authorization(self, action, observation):
        return dict(
            allowed=True,
            consent_valid=True,
            source_verified=True,
            candidate_verified=True,
            quit_authorized=True,
            restart_authorized=True,
            authorized_candidate=copy.deepcopy(action["candidate"]),
        )

    def driver(self, observations, calls, clock=None, block_observation=False):
        def observe(action, state):
            if block_observation:
                clock.now += 10
            if observations:
                current = observations.pop(0)
                if "process" in current:
                    current["process"]["owner_session_id"] = state["session_id"]
                return current
            return dict(
                application_running=False,
                helpers_observed=False,
                helpers_complete=False,
            )

        def trigger(action, state):
            journals = native.recover_native_sessions(str(self.root))
            self.assertTrue(any(j["trigger_attempted"] for j in journals))
            calls.append("trigger")
            return {
                "owned_process": dict(
                    self.process, owner_session_id=state["session_id"]
                )
            }

        return native.NativeDriver(
            observe=observe,
            trigger=trigger,
            graceful_quit=lambda action, state, observation: calls.append("quit"),
            restart=lambda action, state: calls.append("restart"),
        )

    def run_fixture(self, observations, calls, **kwargs):
        clock = Clock()
        driver = self.driver(
            observations, calls, clock, kwargs.pop("block_observation", False)
        )
        with patch.dict(native.NATIVE_DRIVERS, {"fixture": driver}):
            return native.run_native_session(
                self.action,
                "fixture",
                authorize=kwargs.pop("authorize", self.authorization),
                state_dir=str(self.root),
                clock=clock,
                sleep=clock.sleep,
                **kwargs,
            )

    def test_journal_precedes_trigger_and_success_quits_once_and_verifies_identity(
        self,
    ):
        calls = []
        installed = dict(
            application_running=False,
            process_exists=False,
            target_reobserved=True,
            installed=self.action["candidate"],
            signature_verified=True,
            source_verified=True,
            helpers_observed=True,
            helpers_complete=True,
        )
        result = self.run_fixture(
            [
                dict(
                    application_running=False,
                    helpers_observed=True,
                    helpers_complete=True,
                ),
                dict(self.observation, download_ready=True),
                dict(self.observation, download_ready=True),
                installed,
            ],
            calls,
        )
        self.assertEqual(calls, ["trigger", "quit"])
        self.assertEqual(result["status"], "current_verified")
        self.assertEqual(pending_sessions(str(self.root)), [])

    def test_wrong_candidate_or_missing_consent_has_zero_trigger(self):
        calls = []
        bad = lambda action, observation: dict(
            self.authorization(action, observation),
            authorized_candidate={"version": "3.0"},
        )
        result = self.run_fixture(
            [
                dict(
                    application_running=False,
                    helpers_observed=True,
                    helpers_complete=True,
                )
            ],
            calls,
            authorize=bad,
        )
        self.assertEqual(calls, [])
        self.assertEqual(result["status"], "deferred_by_user")

    def test_unknown_or_live_helpers_before_launch_have_zero_trigger(self):
        for changes in [dict(helpers_observed=False), dict(helpers_complete=False)]:
            calls = []
            result = self.run_fixture(
                [dict(application_running=False, **changes)], calls
            )
            self.assertEqual(calls, [])
            self.assertEqual(result["status"], "deferred_by_user")

    def test_already_running_app_is_never_triggered_or_closed(self):
        calls = []
        result = self.run_fixture([dict(application_running=True)], calls)
        self.assertEqual(calls, [])
        self.assertEqual(result["status"], "restart_deferred")

    def test_already_installed_candidate_is_verified_without_a_trigger(self):
        calls = []
        observation = dict(
            application_running=False,
            target_reobserved=True,
            installed=self.action["candidate"],
            signature_verified=True,
            source_verified=True,
            helpers_observed=True,
            helpers_complete=True,
        )
        result = self.run_fixture([observation], calls)
        self.assertEqual(calls, [])
        self.assertEqual(result["reason_code"], "current_verified")

    def test_timeout_retains_durable_lease_and_recovery_never_retriggers(self):
        calls = []
        result = self.run_fixture(
            [
                dict(
                    application_running=False,
                    helpers_observed=True,
                    helpers_complete=True,
                )
            ],
            calls,
        )
        self.assertEqual(result["status"], "recovery_required")
        self.assertEqual(calls, ["trigger"])
        with self.assertRaises(ValueError):
            assert_resources_available(["fixture:app"], str(self.root))
        sessions = native.recover_native_sessions(str(self.root))
        self.assertEqual(sessions[0]["state"], "recovery_required")
        result = self.run_fixture(
            [
                dict(
                    application_running=False,
                    helpers_observed=True,
                    helpers_complete=True,
                )
            ],
            calls,
        )
        self.assertEqual(calls, ["trigger"])
        self.assertEqual(result["status"], "recovery_required")

    def test_blocking_observation_consumes_observer_deadline_before_any_trigger(self):
        calls = []
        result = self.run_fixture(
            [
                dict(
                    application_running=False,
                    helpers_observed=True,
                    helpers_complete=True,
                )
            ],
            calls,
            block_observation=True,
        )
        self.assertEqual(calls, [])
        self.assertEqual(result["status"], "deferred_by_user")

    def test_process_supervisor_does_not_wait_with_timeout_or_kill_child(self):
        class Child:
            def poll(self):
                return None

            def kill(self):
                raise AssertionError("must not kill updater")

            def wait(self, **kwargs):
                raise AssertionError("must not wait on updater")

        calls = []

        def popen(argv, **kwargs):
            calls.append((argv, kwargs))
            return Child()

        child = native.spawn_native_trigger(
            ("/fixture/code-owned-updater", "--defer-install"), popen=popen
        )
        self.assertIsNone(child.poll())
        self.assertFalse(calls[0][1].get("shell", False))
        self.assertNotIn("timeout", calls[0][1])

    def test_quit_requires_separate_consent_even_after_launch_permission(self):
        calls = []
        permission = lambda action, observation: dict(
            self.authorization(action, observation), quit_authorized=False
        )
        result = self.run_fixture(
            [
                dict(
                    application_running=False,
                    helpers_observed=True,
                    helpers_complete=True,
                ),
                dict(self.observation, download_ready=True),
            ],
            calls,
            authorize=permission,
        )
        self.assertEqual(calls, ["trigger"])
        self.assertEqual(result["status"], "restart_deferred")

    def test_authorization_call_time_is_counted_before_graceful_quit(self):
        clock, calls = Clock(), []
        observations = [
            dict(
                application_running=False, helpers_observed=True, helpers_complete=True
            ),
            dict(self.observation, download_ready=True),
            dict(self.observation, download_ready=True),
        ]
        driver = self.driver(observations, calls, clock)

        def permission(action, observation):
            if observation.get("download_ready"):
                clock.now += 10
            return self.authorization(action, observation)

        with patch.dict(native.NATIVE_DRIVERS, {"fixture": driver}):
            result = native.run_native_session(
                self.action,
                "fixture",
                authorize=permission,
                state_dir=str(self.root),
                clock=clock,
                sleep=clock.sleep,
            )
        self.assertEqual(calls, ["trigger"])
        self.assertEqual(result["status"], "restart_deferred")

    def test_document_opened_between_ready_and_quit_reobservation_blocks_control(self):
        calls = []
        observations = [
            dict(
                application_running=False, helpers_observed=True, helpers_complete=True
            ),
            dict(self.observation, download_ready=True),
            dict(self.observation, download_ready=True, user_engaged=True),
        ]
        result = self.run_fixture(observations, calls)
        self.assertEqual(calls, ["trigger"])
        self.assertEqual(result["status"], "restart_deferred")

    def test_wrong_signature_or_candidate_build_never_proves_install_complete(self):
        for change in (
            dict(source_verified=False),
            dict(signature_verified=False),
            dict(installed=dict(self.action["candidate"], build="different")),
        ):
            observation = dict(
                self.observation,
                installed=self.action["candidate"],
                signature_verified=True,
                target_reobserved=True,
            )
            observation.update(change)
            self.assertFalse(
                native.advance_native_session(self.state, observation, 11).get(
                    "verified", False
                )
            )

    def test_crash_after_trigger_preserves_journal_and_lease(self):
        calls = []
        clock = Clock()
        driver = self.driver(
            [
                dict(
                    application_running=False,
                    helpers_observed=True,
                    helpers_complete=True,
                )
            ],
            calls,
        )

        def crash(action, state):
            raise KeyboardInterrupt()

        driver = native.NativeDriver(observe=driver.observe, trigger=crash)
        with patch.dict(native.NATIVE_DRIVERS, {"fixture": driver}):
            with self.assertRaises(KeyboardInterrupt):
                native.run_native_session(
                    self.action,
                    "fixture",
                    authorize=self.authorization,
                    state_dir=str(self.root),
                    clock=clock,
                    sleep=clock.sleep,
                )
        self.assertTrue(native.recover_native_sessions(str(self.root)))
        with self.assertRaises(ValueError):
            assert_resources_available(["fixture:app"], str(self.root))

    def test_explicit_restart_is_reobserved_and_never_grants_a_second_trigger(self):
        self.action["allow_native_restart"] = True
        calls = []
        installed = dict(
            application_running=False,
            process_exists=False,
            target_reobserved=True,
            installed=self.action["candidate"],
            signature_verified=True,
            source_verified=True,
            helpers_observed=True,
            helpers_complete=True,
        )
        after_restart = dict(installed, helpers_complete=False)
        result = self.run_fixture(
            [
                dict(
                    application_running=False,
                    helpers_observed=True,
                    helpers_complete=True,
                ),
                dict(self.observation, download_ready=True),
                dict(self.observation, download_ready=True),
                installed,
                after_restart,
            ],
            calls,
        )
        self.assertEqual(calls, ["trigger", "quit", "restart"])
        self.assertEqual(result["status"], "recovery_required")
        self.assertTrue(pending_sessions(str(self.root)))

    def test_production_driver_registry_has_no_unaccepted_product_trigger(self):
        self.assertEqual(native.NATIVE_DRIVERS, {})

    def test_sanitized_control_observations_remain_noncontrolling(self):
        path = (
            Path(__file__).parent / "fixtures/native_updaters/control-observations.json"
        )
        for fixture in json.loads(path.read_text()):
            with self.subTest(case=fixture["case"]):
                observation = dict(self.observation, **fixture["changes"])
                self.assertFalse(
                    native.may_control_process(self.state, observation)["allowed"]
                )

    def test_reconciliation_needs_helpers_source_and_target_proof(self):
        calls = []
        self.run_fixture(
            [
                dict(
                    application_running=False,
                    helpers_observed=True,
                    helpers_complete=True,
                )
            ],
            calls,
        )
        session = native.recover_native_sessions(str(self.root))[0]
        proof = dict(
            target_reobserved=True,
            signature_verified=True,
            source_verified=True,
            installed=self.action["candidate"],
            helpers_observed=True,
            helpers_complete=True,
        )
        self.assertFalse(
            native.reconcile_native_session(
                session["session_id"],
                dict(proof, helpers_complete=False),
                str(self.root),
            )
        )
        self.assertTrue(pending_sessions(str(self.root)))
        self.assertTrue(
            native.reconcile_native_session(
                session["session_id"], proof, str(self.root)
            )
        )
        self.assertEqual(pending_sessions(str(self.root)), [])
        self.assertEqual(native.recover_native_sessions(str(self.root)), [])

    def test_cli_exit_zero_does_not_prove_helper_completion_or_kill_on_timeout(self):
        clock, calls, process_calls = Clock(), [], []
        driver = self.driver(
            [
                dict(
                    application_running=False,
                    helpers_observed=True,
                    helpers_complete=True,
                )
            ],
            calls,
        )

        class Child:
            def poll(self):
                process_calls.append("poll")
                return 0

            def kill(self):
                process_calls.append("kill")

            def wait(self, **kwargs):
                process_calls.append("wait")

        original_trigger = driver.trigger

        def trigger(action, state):
            return dict(original_trigger(action, state), process=Child())

        driver = native.NativeDriver(observe=driver.observe, trigger=trigger)
        with patch.dict(native.NATIVE_DRIVERS, {"fixture": driver}):
            result = native.run_native_session(
                self.action,
                "fixture",
                authorize=self.authorization,
                state_dir=str(self.root),
                clock=clock,
                sleep=clock.sleep,
            )
        self.assertEqual(result["status"], "recovery_required")
        self.assertIn("poll", process_calls)
        self.assertNotIn("kill", process_calls)
        self.assertNotIn("wait", process_calls)
        self.assertTrue(pending_sessions(str(self.root)))

    def test_reconcile_retry_after_registry_release_does_not_deadlock(self):
        self.run_fixture(
            [
                dict(
                    application_running=False,
                    helpers_observed=True,
                    helpers_complete=True,
                )
            ],
            [],
        )
        session = native.recover_native_sessions(str(self.root))[0]
        proof = dict(
            target_reobserved=True,
            signature_verified=True,
            source_verified=True,
            installed=self.action["candidate"],
            helpers_observed=True,
            helpers_complete=True,
        )
        write = native._write

        def interrupted(state_dir, state):
            if state["state"] == "reconciled":
                raise OSError("fixture disk interruption")
            return write(state_dir, state)

        with patch.object(native, "_write", side_effect=interrupted):
            self.assertFalse(
                native.reconcile_native_session(
                    session["session_id"], proof, str(self.root)
                )
            )
        self.assertTrue(
            native.reconcile_native_session(
                session["session_id"], proof, str(self.root)
            )
        )
