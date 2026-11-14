"""Exclusive system-update supervision shared by standalone and parent runs.

The inherited socket and private context bind permissions to one live supervisor,
one child shell and its durable lease. An environment boolean grants nothing.
"""

import hashlib
import json
import os
from pathlib import Path
import secrets
import select
import socket
import subprocess
import tempfile
import time
import uuid

from inventory_store import _root, _open_regular, StoreError
from system_updates import parse_softwareupdate_list
from update_scheduler import claim_action_resources, pending_sessions, reconcile_session

CONTINUE_GUARDED_CHILD = 96
MAX_BYTES = 128 * 1024


def _directory(state_dir=None, create=False):
    root = _root(state_dir, create)
    return _root(os.path.join(root, "system-sessions"), create) if root else None


def _read(path):
    fd = _open_regular(str(path), os.O_RDONLY)
    with os.fdopen(fd, "rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("system_context_limit")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("invalid_system_context")
    return value


def _write(path, value):
    fd, temporary = tempfile.mkstemp(prefix=".system-", dir=str(Path(path).parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(str(Path(path).parent), os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_boot_identity():
    result = subprocess.run(
        ["sysctl", "-n", "kern.boottime"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    if result.returncode != 0 or not result.stdout.strip() or len(result.stdout) > 4096:
        return "unknown"
    return hashlib.sha256(result.stdout.strip().encode()).hexdigest()


def _labels_absent(context, proof):
    listing = proof.get("listing")
    if (
        proof.get("query_exit") != 0
        or not isinstance(listing, str)
        or len(listing) > MAX_BYTES
        or not (
            "No new software available" in listing or "Software Update found" in listing
        )
    ):
        return False
    rows = parse_softwareupdate_list(listing)
    if "No new software available" not in listing and (
        not rows or listing.count("* Label:") != len(rows)
    ):
        return False
    remaining = {row["label"] for row in rows}
    return not remaining.intersection(context.get("labels", []))


def send_event(shell_pid, parent_pid, operation, payload=None):
    """Authenticated local child-to-supervisor request; never starts an update."""
    try:
        if os.getppid() != shell_pid:
            return False
        path = os.environ.get("MAC_UPDATE_SYSTEM_GUARD_CONTEXT", "")
        directory = _directory()
        if not directory or str(Path(path).parent) != directory:
            return False
        deadline = time.monotonic() + 2
        while True:
            try:
                context = _read(path)
                break
            except (FileNotFoundError, StoreError):
                if time.monotonic() >= deadline:
                    return False
                time.sleep(0.01)
        if (
            context.get("child_pid") != shell_pid
            or context.get("wrapper_pid") != parent_pid
        ):
            return False
        lease = next(
            (
                row
                for row in pending_sessions()
                if row["lease_id"] == context["lease_id"]
            ),
            None,
        )
        if (
            not lease
            or lease.get("owner_pid") != parent_pid
            or lease.get("resources") != ["exclusive:system"]
        ):
            return False
        channel = socket.socket(
            fileno=os.dup(int(os.environ["MAC_UPDATE_SYSTEM_GUARD_FD"]))
        )
        try:
            channel.settimeout(5)
            request = dict(
                operation=operation,
                payload=payload or {},
                nonce=context["nonce"],
                shell_pid=shell_pid,
            )
            channel.sendall((json.dumps(request) + "\n").encode())
            raw = b""
            while b"\n" not in raw and len(raw) <= MAX_BYTES:
                block = channel.recv(4096)
                if not block:
                    return False
                raw += block
            response = json.loads(raw.split(b"\n", 1)[0])
            return response.get("allowed") is True and secrets.compare_digest(
                response.get("nonce", ""), context["nonce"]
            )
        finally:
            channel.close()
    except (StoreError, OSError, ValueError, KeyError, TypeError):
        return False


def guard_entry(script, shell_pid, parent_pid):
    if send_event(shell_pid, parent_pid, "enter"):
        return CONTINUE_GUARDED_CHILD
    return run_guarded(script)


def _pending_marker(context):
    session = os.environ.get("MAC_UPDATE_SESSION_DIR")
    if session:
        try:
            fd = os.open(
                os.path.join(session, "system_helper_pending"),
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
            )
            with os.fdopen(fd, "w") as stream:
                stream.write(context["context_id"] + "\n")
        except OSError:
            pass


def run_guarded(script, *, state_dir=None, env=None, boot_reader=None):
    action = dict(
        action_id="system-" + str(uuid.uuid4()),
        adapter_id="system",
        resources=["exclusive:system"],
        scope_complete=True,
        parallel_safe=False,
    )
    try:
        lease = claim_action_resources(action, state_dir)
    except (StoreError, ValueError):
        print(
            "System update deferred: another updater session requires completion or reconciliation.",
            flush=True,
        )
        return 10
    context_id = str(uuid.uuid4())
    path = Path(_directory(state_dir, True)) / (context_id + ".json")
    parent, child = socket.socketpair()
    context = dict(
        schema_version=1,
        context_id=context_id,
        lease_id=lease.lease_id,
        action_id=action["action_id"],
        wrapper_pid=os.getpid(),
        child_pid=None,
        nonce=secrets.token_hex(32),
        state="observing",
        mutation_started=False,
        labels=[],
        restart_required=False,
        boot_identity="unknown",
        verified_nonrestart=False,
    )
    process = None
    try:
        child_env = dict(
            os.environ if env is None else env,
            MAC_UPDATE_STATE_DIR=_root(state_dir, True),
            MAC_UPDATE_SYSTEM_GUARD_CONTEXT=str(path),
            MAC_UPDATE_SYSTEM_GUARD_FD=str(child.fileno()),
        )
        process = subprocess.Popen(
            ["/bin/bash", str(script)], env=child_env, pass_fds=(child.fileno(),)
        )
        child.close()
        context["child_pid"] = process.pid
        _write(path, context)
        buffer = b""
        while process.poll() is None:
            ready, _, _ = select.select([parent], [], [], 0.05)
            if not ready:
                continue
            block = parent.recv(4096)
            if not block:
                continue
            buffer += block
            if len(buffer) > MAX_BYTES:
                raise ValueError("system_control_limit")
            while b"\n" in buffer:
                raw, buffer = buffer.split(b"\n", 1)
                request = json.loads(raw)
                allowed = request.get(
                    "shell_pid"
                ) == process.pid and secrets.compare_digest(
                    request.get("nonce", ""), context["nonce"]
                )
                payload = request.get("payload", {})
                operation = request.get("operation")
                if allowed and operation == "mutation_started":
                    labels = payload.get("labels")
                    allowed = (
                        isinstance(labels, list)
                        and bool(labels)
                        and len(labels) <= 128
                        and all(
                            isinstance(label, str) and label and len(label) <= 4096
                            for label in labels
                        )
                        and type(payload.get("restart")) is bool
                    )
                    if allowed:
                        context.update(
                            mutation_started=True,
                            state="mutation_started",
                            verified_nonrestart=False,
                        )
                        context["labels"] = sorted(set(context["labels"] + labels))
                        context["restart_required"] |= payload["restart"]
                        if payload["restart"] and context["boot_identity"] == "unknown":
                            try:
                                context["boot_identity"] = (
                                    boot_reader or read_boot_identity
                                )()
                            except (OSError, ValueError, subprocess.SubprocessError):
                                pass
                        _write(path, context)
                elif allowed and operation == "verified_nonrestart":
                    allowed = (
                        context["mutation_started"]
                        and not context["restart_required"]
                        and _labels_absent(context, payload)
                    )
                    if allowed:
                        context.update(
                            verified_nonrestart=True, state="verified_nonrestart"
                        )
                        _write(path, context)
                elif operation != "enter":
                    allowed = False
                parent.sendall(
                    (
                        json.dumps(dict(allowed=bool(allowed), nonce=context["nonce"]))
                        + "\n"
                    ).encode()
                )
        code = process.returncode
        if not context["mutation_started"] or (
            context["verified_nonrestart"] and code in (0, 10)
        ):
            context.update(state="completed", child_exit_code=code)
            _write(path, context)
            lease.finish(
                (
                    "system_verified"
                    if context["mutation_started"]
                    else "no_system_mutation"
                ),
                helpers_complete=True,
            )
            return code
        context.update(state="recovery_required", child_exit_code=code)
        _write(path, context)
        lease.pending("system_completion_unconfirmed")
        _pending_marker(context)
        print(
            "System update remains pending. Its exclusive lease is retained; fresh completion proof is required to reconcile it.",
            flush=True,
        )
        return 10 if code == 0 else code
    except BaseException:
        context["state"] = "recovery_required"
        try:
            _write(path, context)
        finally:
            lease.pending("system_observer_interrupted")
        raise
    finally:
        parent.close()
        child.close()


def pending_system_sessions(state_dir=None):
    directory = _directory(state_dir)
    if not directory:
        return []
    result = []
    for path in sorted(Path(directory).glob("*.json"))[:1000]:
        context = _read(path)
        if context.get("state") != "completed":
            result.append(
                {key: value for key, value in context.items() if key != "nonce"}
            )
    return result


def reconcile_system_session(context_id, proof, state_dir=None):
    """Trusted read-only proof API; this never installs, restarts or guesses expiry."""
    try:
        uuid.UUID(context_id)
        directory = _directory(state_dir)
        if not directory:
            return False
        path = Path(directory) / (context_id + ".json")
        context = _read(path)
        if (
            context.get("context_id") != context_id
            or proof.get("target_os_verified") is not True
            or not _labels_absent(context, proof)
        ):
            return False
        if context.get("restart_required") and (
            context.get("boot_identity") == "unknown"
            or not isinstance(proof.get("boot_identity"), str)
            or proof["boot_identity"] in ("unknown", context["boot_identity"])
        ):
            return False
        released = reconcile_session(
            context["lease_id"],
            dict(
                action_id=context["action_id"],
                target_reobserved=True,
                helpers_complete=True,
            ),
            state_dir,
        )
        if not released and any(
            row["lease_id"] == context["lease_id"]
            for row in pending_sessions(state_dir)
        ):
            return False
        context["state"] = "completed"
        _write(path, context)
        return True
    except (StoreError, OSError, ValueError, TypeError, KeyError):
        return False
