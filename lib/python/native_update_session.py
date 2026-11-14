"""Native updater supervision with durable uncertainty and no forced termination.

Product drivers are code, not JSON commands. The production registry intentionally
stays empty until a reviewed immutable candidate and live acceptance exist.
"""

import copy
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

from inventory_store import _root, _open_regular, StoreError
from operation_receipts import phase_receipt
from update_scheduler import claim_action_resources, reconcile_session, pending_sessions


@dataclass(frozen=True)
class NativeDriver:
    observe: object
    trigger: object
    graceful_quit: object = None
    restart: object = None


NATIVE_DRIVERS = {}
IDENTITY_FIELDS = ("pid", "start_time", "bundle_id", "owner_session_id")
TERMINAL = {"completed", "reconciled"}


def may_control_process(action, observation):
    """A fresh identity-bound observation must prove ownership and no user work."""
    state = action
    permissions = state.get("action", action)
    reason = "process_ownership_unproved"
    owned = state.get("owned_process")
    process = observation.get("process")
    if observation.get("preexisting") is True:
        reason = "preexisting_user_process"
    elif observation.get("process_exists") is not True:
        reason = "process_not_observed"
    elif (
        observation.get("engagement_known") is not True
        or observation.get("user_engaged") is not False
        or observation.get("save_dialog") is not False
    ):
        reason = "user_engagement_or_unknown"
    elif permissions.get("allow_native_quit") is not True:
        reason = "quit_consent_missing"
    elif (
        isinstance(owned, dict)
        and isinstance(process, dict)
        and type(owned.get("pid")) is int
        and owned["pid"] > 0
        and all(isinstance(owned.get(k), str) and owned[k] for k in IDENTITY_FIELDS[1:])
        and all(owned.get(k) == process.get(k) for k in IDENTITY_FIELDS)
        and owned["owner_session_id"] == state.get("session_id")
        and owned["bundle_id"]
        == permissions.get("expected_target", {}).get("bundle_id")
    ):
        return dict(allowed=True, reason_code="owned_unengaged_process")
    return dict(allowed=False, reason_code=reason)


def _helpers_complete(observation):
    return (
        observation.get("helpers_observed") is True
        and observation.get("helpers_complete") is True
    )


def _target_verified(state, observation):
    candidate = state["action"].get("candidate", {})
    installed = observation.get("installed", {})
    expected = state["action"].get("expected_target", {})
    return bool(
        observation.get("target_reobserved") is True
        and observation.get("signature_verified") is True
        and observation.get("source_verified") is True
        and all(
            isinstance(candidate.get(k), str)
            and candidate[k]
            and installed.get(k) == candidate[k]
            for k in ("version", "build", "bundle_id", "team_id")
        )
        and all(candidate.get(k) == expected.get(k) for k in ("bundle_id", "team_id"))
    )


def advance_native_session(state, observation, now_monotonic):
    """Pure decision step. Readiness never establishes installation completion."""
    result = copy.deepcopy(state)
    result.update(operation="wait", verified=False)
    if state.get("state") in TERMINAL:
        return dict(result, operation="none", verified=state.get("verified", False))
    if (
        observation.get("resumed") is True
        or now_monotonic < state.get("started_monotonic", now_monotonic)
        or (
            state.get("observer_boot_id")
            and observation.get("boot_id")
            and state["observer_boot_id"] != observation["boot_id"]
        )
    ):
        return dict(
            result,
            state="recovery_required",
            operation="none",
            reason_code="observer_clock_or_boot_changed",
        )
    if now_monotonic >= state["deadline_monotonic"]:
        return dict(
            result,
            state="timeout_pending",
            operation="none",
            reason_code="observer_deadline",
        )
    if _target_verified(state, observation):
        if not _helpers_complete(observation):
            return dict(
                result, state="install_pending", reason_code="helpers_unconfirmed"
            )
        return dict(
            result,
            state="completed",
            operation="none",
            verified=True,
            reason_code="updated_verified",
        )
    if observation.get("download_ready") is True:
        if observation.get("defer_install") is True:
            return dict(
                result,
                state="install_pending",
                operation="none",
                reason_code="vendor_deferred_install",
            )
        if not state.get("quit_requested"):
            control = may_control_process(state, observation)
            if not control["allowed"]:
                return dict(
                    result,
                    state="restart_deferred",
                    operation="none",
                    reason_code=control["reason_code"],
                )
            return dict(
                result,
                state="ready",
                operation="graceful_quit",
                reason_code="vendor_ready",
            )
    if state.get("quit_requested"):
        return dict(
            result, state="install_pending", reason_code="installation_unconfirmed"
        )
    return result


def spawn_native_trigger(argv, *, popen=None):
    """Only a code-owned driver supplies argv; no shell, timeout kill or wait."""
    if (
        not isinstance(argv, tuple)
        or not argv
        or any(not isinstance(x, str) or not x or "\0" in x for x in argv)
    ):
        raise ValueError("code_command_required")
    return (popen or subprocess.Popen)(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        start_new_session=True,
    )


def _directory(state_dir, create=False):
    root = _root(state_dir, create)
    if root is None:
        return None
    path = os.path.join(root, "native-sessions")
    if create:
        return _root(path, True)
    return _root(path, False)


def _write(state_dir, state):
    directory = _directory(state_dir, True)
    session_id = state.get("session_id")
    try:
        uuid.UUID(session_id)
    except (ValueError, TypeError, AttributeError):
        raise ValueError("invalid_native_session_id") from None
    fd, temporary = tempfile.mkstemp(prefix=".native-", dir=directory)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(state, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, os.path.join(directory, session_id + ".json"))
        directory_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def recover_native_sessions(state_dir=None):
    """Read durable journals only. Recovery never launches or blindly retriggers."""
    directory = _directory(state_dir)
    if directory is None:
        return []
    states = []
    paths = sorted(Path(directory).glob("*.json"))
    if len(paths) > 1000:
        return [dict(state="recovery_required", reason_code="native_journal_limit")]
    for path in paths:
        try:
            fd = _open_regular(str(path), os.O_RDONLY)
            with os.fdopen(fd, "rb") as stream:
                raw = stream.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise ValueError("native_journal_limit")
            state = json.loads(raw)
            if (
                not isinstance(state, dict)
                or state.get("schema_version") != 1
                or not isinstance(state.get("action"), dict)
                or not isinstance(state.get("session_id"), str)
            ):
                raise ValueError("invalid_native_journal")
            if state.get("state") not in TERMINAL:
                states.append(dict(state, state="recovery_required", operation="none"))
        except (StoreError, OSError, ValueError):
            states.append(
                dict(state="recovery_required", reason_code="native_journal_unreadable")
            )
    return states


def reconcile_native_session(session_id, observation, state_dir=None):
    """Release a durable barrier only after fresh target/source/helper proof.

    The caller supplies trusted driver observations; this function executes no
    command and cannot launch a second updater during recovery.
    """
    try:
        uuid.UUID(session_id)
        directory = _directory(state_dir)
        if directory is None:
            return False
        fd = _open_regular(os.path.join(directory, session_id + ".json"), os.O_RDONLY)
        with os.fdopen(fd, "rb") as stream:
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            return False
        state = json.loads(raw)
        if state.get("schema_version") != 1 or state.get("session_id") != session_id:
            return False
        expected = state["action"]["expected_target"]
        installed = observation.get("installed", {})
        if not (
            _helpers_complete(observation)
            and observation.get("target_reobserved") is True
            and observation.get("signature_verified") is True
            and observation.get("source_verified") is True
            and all(
                isinstance(installed.get(k), str) and installed[k]
                for k in ("version", "build")
            )
            and all(
                expected.get(k) and installed.get(k) == expected[k]
                for k in ("bundle_id", "team_id")
            )
        ):
            return False
        state.update(
            state="reconciling",
            operation="none",
            recovery_proof=dict(
                target_reobserved=True,
                source_verified=True,
                signature_verified=True,
                helpers_complete=True,
            ),
        )
        _write(state_dir, state)
        released = reconcile_session(
            state["lease_id"],
            dict(
                helpers_complete=True,
                target_reobserved=True,
                action_id=state["action"]["action_id"],
            ),
            state_dir,
        )
        if not released and any(
            row.get("lease_id") == state["lease_id"]
            for row in pending_sessions(state_dir)
        ):
            return False
        state.update(state="reconciled", verified=_target_verified(state, observation))
        _write(state_dir, state)
        return True
    except (StoreError, OSError, ValueError, TypeError, KeyError, AttributeError):
        return False


def _result(action, status, reason, verified=False, session_id=None):
    return dict(
        target=action.get("target"),
        action_id=action.get("action_id"),
        status=status,
        reason_code=reason,
        verified=verified,
        session_id=session_id,
        before=action.get("expected_target", {}).get("short_version"),
        after=action.get("candidate", {}).get("version") if verified else None,
        recovery_required=status == "recovery_required",
        evidence_type="live_version_comparison" if verified else "unknown",
    )


def _call(driver_call, action, state, receipt_dir, phase, *args):
    if not receipt_dir:
        return driver_call(action, state, *args)
    with phase_receipt(
        receipt_dir,
        run_id=action.get("run_id", "unknown"),
        action_id=action["action_id"],
        recipe_revision=str(action.get("recipe_revision", "unknown")),
        phase=phase,
    ) as event:
        result = driver_call(action, state, *args)
        event["outcome"] = "observed" if phase == "observe" else "requested"
        return result


def _authorized(action, permission, control=None):
    candidate = action.get("candidate")
    expected = action.get("expected_target", {})
    return bool(
        isinstance(permission, dict)
        and isinstance(candidate, dict)
        and all(
            permission.get(key) is True
            for key in (
                "allowed",
                "consent_valid",
                "source_verified",
                "candidate_verified",
            )
        )
        and permission.get("authorized_candidate") == candidate
        and all(
            isinstance(candidate.get(key), str) and candidate[key]
            for key in ("version", "build", "bundle_id", "team_id")
        )
        and all(candidate[key] == expected.get(key) for key in ("bundle_id", "team_id"))
        and (control is None or permission.get(control + "_authorized") is True)
    )


def run_native_session(
    action,
    driver_id,
    *,
    authorize,
    state_dir=None,
    receipt_dir=None,
    lease=None,
    clock=time.monotonic,
    sleep=time.sleep,
):
    """Supervise one authorized candidate; unresolved work preserves its lease."""
    driver = NATIVE_DRIVERS.get(driver_id)
    if driver is None:
        if lease is not None:
            lease.finish("not_triggered", helpers_complete=True)
        return _result(action, "manual_by_policy", "native_driver_unaccepted")
    for session in recover_native_sessions(state_dir):
        previous = session.get("action", {})
        if (
            not previous
            or previous.get("action_id") == action.get("action_id")
            or previous.get("target_path") == action.get("target_path")
        ):
            if lease is not None:
                lease.finish("not_triggered", helpers_complete=True)
            return _result(action, "recovery_required", "pending_native_session")
    try:
        lease = lease or claim_action_resources(action, state_dir)
    except (ValueError, StoreError):
        return _result(action, "recovery_required", "pending_updater_session")
    started = clock()
    timeout = action.get("timeout_seconds", 90)
    if type(timeout) not in (int, float) or not 0 < timeout <= 600:
        lease.finish("invalid_native_budget", helpers_complete=True)
        return _result(action, "deferred_by_user", "invalid_native_budget")
    state = dict(
        schema_version=1,
        session_id=str(uuid.uuid4()),
        action=copy.deepcopy(action),
        state="prepared",
        trigger_attempted=False,
        started_monotonic=started,
        deadline_monotonic=started + timeout,
        lease_id=lease.lease_id,
    )
    triggered = False
    try:
        initial = _call(driver.observe, action, state, receipt_dir, "observe")
        permission = authorize(action, initial)
        if clock() >= state["deadline_monotonic"] or not _authorized(
            action, permission
        ):
            lease.finish("not_triggered", helpers_complete=True)
            return _result(
                action, "deferred_by_user", "native_authorization_or_deadline"
            )
        if _target_verified(state, initial) and _helpers_complete(initial):
            lease.finish("already_current", helpers_complete=True)
            return _result(
                action, "current_verified", "current_verified", verified=True
            )
        if initial.get("application_running") is not False:
            lease.finish("not_triggered", helpers_complete=True)
            return _result(action, "restart_deferred", "preexisting_or_unknown_process")
        if not _helpers_complete(initial):
            lease.finish("not_triggered", helpers_complete=True)
            return _result(action, "deferred_by_user", "preexisting_or_unknown_helpers")
        if action.get("action_scope") != "native_launch":
            lease.finish("not_triggered", helpers_complete=True)
            return _result(action, "deferred_by_user", "native_launch_consent_required")
        state.update(
            state="triggering",
            trigger_attempted=True,
            observer_boot_id=initial.get("boot_id"),
        )
        _write(state_dir, state)
        if clock() >= state["deadline_monotonic"]:
            state.update(state="reconciled", trigger_attempted=False, verified=False)
            _write(state_dir, state)
            lease.finish("not_triggered", helpers_complete=True)
            return _result(action, "deferred_by_user", "native_observer_deadline")
        triggered = True
        launched = _call(driver.trigger, action, state, receipt_dir, "trigger")
        trigger_process = None
        if isinstance(launched, dict):
            state["owned_process"] = launched.get("owned_process")
            trigger_process = launched.get("process")
        state["state"] = "observing"
        _write(state_dir, state)
        while True:
            if trigger_process is not None:
                # Exit of this CLI is diagnostic only; vendor helpers may survive it.
                exit_code = trigger_process.poll()
                if type(exit_code) is int:
                    state["trigger_exit_code"] = exit_code
            observation = _call(driver.observe, action, state, receipt_dir, "observe")
            state = advance_native_session(state, observation, clock())
            _write(state_dir, state)
            if state["state"] == "completed":
                if action.get("allow_native_restart") is True and state.get(
                    "quit_requested"
                ):
                    permission = authorize(action, observation)
                    if (
                        not callable(driver.restart)
                        or observation.get("process_exists") is not False
                        or not _authorized(action, permission, "restart")
                        or clock() >= state["deadline_monotonic"]
                    ):
                        lease.finish("updated_restart_deferred", helpers_complete=True)
                        return _result(
                            action,
                            "restart_deferred",
                            "updated_restart_unconfirmed",
                            verified=True,
                            session_id=state["session_id"],
                        )
                    state.update(state="restarting", operation="restart")
                    _write(state_dir, state)
                    _call(driver.restart, action, state, receipt_dir, "restart")
                    restarted = _call(
                        driver.observe, action, state, receipt_dir, "observe"
                    )
                    if not (
                        _target_verified(state, restarted)
                        and _helpers_complete(restarted)
                        and clock() < state["deadline_monotonic"]
                    ):
                        state.update(
                            state="recovery_required",
                            operation="none",
                            verified=False,
                            reason_code="restart_completion_unconfirmed",
                        )
                        _write(state_dir, state)
                        lease.pending("restart_completion_unconfirmed")
                        return _result(
                            action,
                            "recovery_required",
                            "restart_completion_unconfirmed",
                            session_id=state["session_id"],
                        )
                    state.update(state="completed", operation="none", verified=True)
                    _write(state_dir, state)
                lease.finish("updated_verified", helpers_complete=True)
                return _result(
                    action,
                    "current_verified",
                    "updated_verified",
                    verified=True,
                    session_id=state["session_id"],
                )
            if state["operation"] == "graceful_quit":
                # Readiness is not a reusable process-control capability. Check
                # again for document/save UI, PID reuse and updater relaunch.
                observation = _call(
                    driver.observe, action, state, receipt_dir, "observe"
                )
                permission = authorize(action, observation)
                if (
                    _target_verified(state, observation)
                    and _helpers_complete(observation)
                    and clock() < state["deadline_monotonic"]
                ):
                    state.update(state="completed", operation="none", verified=True)
                    _write(state_dir, state)
                    lease.finish("updated_verified", helpers_complete=True)
                    return _result(
                        action,
                        "current_verified",
                        "updated_verified",
                        verified=True,
                        session_id=state["session_id"],
                    )
                if (
                    not _authorized(action, permission, "quit")
                    or not callable(driver.graceful_quit)
                    or clock() >= state["deadline_monotonic"]
                    or observation.get("download_ready") is not True
                    or observation.get("defer_install") is True
                    or not may_control_process(state, observation)["allowed"]
                ):
                    state.update(
                        state="restart_deferred",
                        operation="none",
                        reason_code="quit_authorization_unconfirmed",
                    )
                else:
                    state.update(state="quit_requested", quit_requested=True)
                    _write(state_dir, state)
                    _call(
                        driver.graceful_quit,
                        action,
                        state,
                        receipt_dir,
                        "quit",
                        observation,
                    )
            if (
                state["state"]
                in ("restart_deferred", "timeout_pending", "recovery_required")
                or state["operation"] == "none"
            ):
                _write(state_dir, state)
                lease.pending(state.get("reason_code", "native_incomplete"))
                status = (
                    "restart_deferred"
                    if state["state"] == "restart_deferred"
                    else "recovery_required"
                )
                return _result(
                    action,
                    status,
                    state.get("reason_code", "native_incomplete"),
                    session_id=state["session_id"],
                )
            remaining = state["deadline_monotonic"] - clock()
            if remaining > 0:
                sleep(min(0.25, remaining))
    except BaseException as exc:
        if triggered:
            state.update(
                state="recovery_required",
                operation="none",
                reason_code="native_observer_interrupted",
            )
            try:
                _write(state_dir, state)
            finally:
                lease.pending("native_observer_interrupted")
        else:
            lease.finish("not_triggered", helpers_complete=True)
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        return _result(
            action,
            "recovery_required" if triggered else "deferred_by_user",
            "native_observer_interrupted",
            session_id=state["session_id"],
        )
