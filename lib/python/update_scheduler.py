"""Bounded scheduling and durable per-user leases shared across checkouts.

Kernel locks serialize the registry only. An unresolved mutating helper keeps a
slot and its resources after its observer exits. PID absence is never proof that
an installer completed. No JSON field can execute a command.
"""

import contextlib
import copy
import datetime
import fcntl
import json
import os
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from inventory_store import _root, _open_regular, StoreError

MAX_MUTATIONS = 2


def resource_keys(action):
    """Derive conservative resources from existing manager and recipe actions."""
    resources = []
    target = action.get("expected_target") or action.get("target") or {}
    for path in [action.get("target_path")] + action.get("artifact_effects", []):
        if isinstance(path, str) and os.path.isabs(path):
            resources.append("path:" + os.path.realpath(path))
    source = action.get("expected_resolution", {}).get("source") or target.get(
        "manager"
    )
    if source in ("homebrew", "npm"):
        prefix = target.get("prefix")
        if not prefix or not os.path.isabs(prefix):
            return ["exclusive:unknown"]
        resources.append("manager:" + source + ":" + os.path.realpath(prefix))
    elif source == "app_store":
        resources.append("manager:app_store")
    elif source in ("mau", "google_updater"):
        resources.append("manager:" + source)
    for name in action.get("shared_resources", []):
        resources.append("shared:" + name)
    if action.get("adapter_id") == "system":
        resources.append("exclusive:system")
    return sorted(set(resources or ["exclusive:unknown"]))


def _resources(action):
    values = action.get("resources") or resource_keys(action)
    if (
        not isinstance(values, list)
        or not values
        or len(values) > 256
        or any(
            not isinstance(x, str)
            or not x
            or len(x) > 4096
            or any(ord(c) < 32 for c in x)
            for x in values
        )
    ):
        raise ValueError("invalid_action_resources")
    return sorted(set(values))


def _exclusive(action):
    return (
        action.get("scope_complete") is not True
        or action.get("parallel_safe") is not True
        or any(x == "system" or x.startswith("exclusive:") for x in _resources(action))
    )


def _conflicts(action, rows):
    resources = set(_resources(action))
    return bool(
        rows
        and (
            _exclusive(action)
            or any(
                row.get("exclusive") is True or resources.intersection(row["resources"])
                for row in rows
            )
        )
    )


def schedule_ready_actions(actions, resource_state, limits):
    """Pure deterministic admission; persistent claim must still run atomically."""
    if limits.get("cancelled"):
        return []
    cap = limits.get("mutations", MAX_MUTATIONS)
    if type(cap) is not int or not 1 <= cap <= MAX_MUTATIONS:
        raise ValueError("invalid_scheduler_limit")
    rows = copy.deepcopy(resource_state)
    selected = []
    for action in actions:
        if len(rows) >= cap:
            break
        if not _conflicts(action, rows):
            selected.append(action)
            rows.append(
                dict(resources=_resources(action), exclusive=_exclusive(action))
            )
    return selected


def _load(root):
    path = os.path.join(root, "scheduler.json")
    if not os.path.lexists(path):
        return dict(schema_version=1, leases=[])
    try:
        fd = _open_regular(path, os.O_RDONLY)
    except StoreError:
        raise ValueError("invalid_scheduler_registry") from None
    with os.fdopen(fd, "rb") as stream:
        raw = stream.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("scheduler_registry_limit")
    try:
        data = json.loads(raw)
        if data.get("schema_version") != 1 or not isinstance(data.get("leases"), list):
            raise ValueError("invalid_scheduler_registry")
        ids = set()
        actions = set()
        for row in data["leases"]:
            if (
                not isinstance(row, dict)
                or not isinstance(row.get("lease_id"), str)
                or not row["lease_id"]
                or row["lease_id"] in ids
                or not isinstance(row.get("action_id"), str)
                or not row["action_id"]
                or row["action_id"] in actions
                or not isinstance(row.get("resources"), list)
                or not row["resources"]
                or type(row.get("exclusive")) is not bool
                or row.get("status") not in ("active", "recovery_required", "pending")
            ):
                raise ValueError("invalid_scheduler_registry")
            _resources(row)
            ids.add(row["lease_id"])
            actions.add(row["action_id"])
        if len(data["leases"]) > MAX_MUTATIONS:
            raise ValueError("invalid_scheduler_registry")
        return data
    except (TypeError, KeyError, json.JSONDecodeError, AttributeError):
        raise ValueError("invalid_scheduler_registry") from None


def _write(root, data):
    fd, tmp = tempfile.mkstemp(prefix=".scheduler-", dir=root)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, os.path.join(root, "scheduler.json"))
        dfd = os.open(root, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextlib.contextmanager
def _registry(state_dir=None, create=True):
    root = _root(state_dir, create)
    if root is None:
        yield None, dict(schema_version=1, leases=[])
        return
    if not create:
        yield root, _load(root)
        return
    fd = _open_regular(os.path.join(root, "scheduler.lock"), os.O_RDWR | os.O_CREAT)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield root, _load(root)
    finally:
        os.close(fd)


def pending_sessions(state_dir=None):
    with _registry(state_dir, False) as (_, data):
        return copy.deepcopy(data["leases"])


def assert_resources_available(resources, state_dir=None, owner_action_id=None):
    action = dict(resources=resources, scope_complete=True, parallel_safe=True)
    with _registry(state_dir, False) as (_, data):
        if owner_action_id is not None:
            owners = [x for x in data["leases"] if x["action_id"] == owner_action_id]
            if len(owners) != 1 or not set(resources).issubset(owners[0]["resources"]):
                raise ValueError("mutation_lease_lost")
        rows = [x for x in data["leases"] if x["action_id"] != owner_action_id]
        if _conflicts(action, rows):
            raise ValueError("pending_updater_session")


class ResourceLease:
    def __init__(self, lease_id, action_id, state_dir):
        self.lease_id = lease_id
        self.action_id = action_id
        self.state_dir = state_dir
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if not self.closed:
            self.pending("observer_exited")

    def pending(self, reason):
        with _registry(self.state_dir) as (root, data):
            for row in data["leases"]:
                if row["lease_id"] == self.lease_id:
                    row["status"] = "recovery_required"
                    row["reason"] = "observer_incomplete"
            _write(root, data)

    def finish(self, outcome, helpers_complete=False):
        if helpers_complete is not True:
            self.pending("helpers_unconfirmed")
            raise ValueError("helper_completion_required")
        with _registry(self.state_dir) as (root, data):
            rows = [r for r in data["leases"] if r["lease_id"] != self.lease_id]
            if len(rows) == len(data["leases"]):
                raise ValueError("lease_missing")
            data["leases"] = rows
            _write(root, data)
        self.closed = True


def claim_action_resources(action, state_dir=None):
    action_id = action.get("action_id")
    if not isinstance(action_id, str) or not action_id or len(action_id) > 256:
        raise ValueError("invalid_action_id")
    resources = _resources(action)
    with _registry(state_dir) as (root, data):
        rows = data["leases"]
        if any(r["action_id"] == action_id for r in rows) or _conflicts(action, rows):
            raise ValueError("resource_conflict")
        if len(rows) >= MAX_MUTATIONS:
            raise ValueError("mutation_capacity_reached")
        lease_id = str(uuid.uuid4())
        rows.append(
            dict(
                lease_id=lease_id,
                action_id=action_id,
                resources=resources,
                exclusive=_exclusive(action),
                status="active",
                owner_pid=os.getpid(),
                created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )
        )
        _write(root, data)
    return ResourceLease(lease_id, action_id, state_dir)


def reconcile_session(lease_id, proof, state_dir=None):
    if (
        proof.get("helpers_complete") is not True
        or proof.get("target_reobserved") is not True
    ):
        return False
    with _registry(state_dir) as (root, data):
        row = next((r for r in data["leases"] if r["lease_id"] == lease_id), None)
        if row is None or row["action_id"] != proof.get("action_id"):
            return False
        data["leases"].remove(row)
        _write(root, data)
    return True


def claim_recovery_resources(
    action, original_action_id, no_mutating_helpers, state_dir=None
):
    """Atomically retain an interrupted writer's slot for observed recovery.

    Callers prove their synchronous copy completed durably and must acquire the
    target's kernel lock before observing or changing it. Native/system helpers
    cannot use this path. A recovered slot is never briefly released to a third
    writer between the interrupted operation and recovery.
    """
    if no_mutating_helpers is not True:
        raise ValueError("recovery_helpers_unconfirmed")
    resources = _resources(action)
    with _registry(state_dir) as (root, data):
        existing = next(
            (r for r in data["leases"] if r["action_id"] == original_action_id), None
        )
        if existing is not None:
            if existing["exclusive"] is not True or not set(resources).issubset(
                existing["resources"]
            ):
                raise ValueError("recovery_scope_changed")
            # Keep ownership metadata until the target lock has been acquired;
            # a still-running writer retains its kernel lock and wins that race.
            existing["status"] = "recovery_required"
            _write(root, data)
            return ResourceLease(existing["lease_id"], original_action_id, state_dir)
    return claim_action_resources(action, state_dir)


def execute_queue(actions, execute, state_dir=None, cancelled=None):
    """Run bounded independent callbacks; only the supervisor aggregates results.

    execute(action, lease) must explicitly finish a proved-complete lease; an
    exception or unresolved helper preserves it. Public recipes remain serial
    until their independent-effect contract passes live acceptance.
    """
    actions = list(actions)
    if len({a["action_id"] for a in actions}) != len(actions):
        raise ValueError("duplicate_action_id")
    waiting = list(actions)
    active = {}
    results = []

    def run(action, lease):
        with lease:
            return execute(action, lease)

    with ThreadPoolExecutor(max_workers=MAX_MUTATIONS) as pool:
        while waiting or active:
            stopped = bool(cancelled and cancelled())
            ready = (
                []
                if stopped
                else schedule_ready_actions(
                    waiting, pending_sessions(state_dir), {"mutations": 2}
                )
            )
            for action in ready:
                try:
                    lease = claim_action_resources(action, state_dir)
                except ValueError:
                    continue
                waiting.remove(action)
                active[pool.submit(run, action, lease)] = action
            if not active:
                for action in waiting:
                    results.append(
                        dict(
                            action_id=action["action_id"],
                            status="deferred_by_user",
                            reason_code="cancelled" if stopped else "resources_pending",
                            verified=False,
                        )
                    )
                break
            completed, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in completed:
                action = active.pop(future)
                try:
                    value = future.result()
                except Exception:
                    value = dict(
                        status="recovery_required",
                        reason_code="executor_interrupted",
                        verified=False,
                    )
                results.append(dict(value, action_id=action["action_id"]))
    by_id = {r["action_id"]: r for r in results}
    return [by_id[a["action_id"]] for a in actions]
