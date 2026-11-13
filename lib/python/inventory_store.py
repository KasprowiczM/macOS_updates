"""Private shadow snapshot storage with locked compare-and-swap writes."""

import copy
import fcntl
import json
import os
import stat
import uuid
import time

MAX_SNAPSHOT_BYTES = 16 * 1024 * 1024
LOCK_TIMEOUT_SECONDS = 2.0
from inventory_model import validate_snapshot


class StoreError(Exception):
    pass


def default_root():
    return os.environ.get("MAC_UPDATE_STATE_DIR") or os.path.join(
        os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"),
        "mac-update",
    )


def _root(root, create=False):
    root = os.path.abspath(root or default_root())
    # macOS exposes /var as a system alias; resolve it before checking components.
    if root == "/var" or root.startswith("/var/"):
        root = "/private" + root
    parts = root.split(os.sep)
    for i in range(1, len(parts)):
        part = os.sep.join(parts[: i + 1]) or os.sep
        if os.path.islink(part):
            raise StoreError("unsafe state ancestor")
    if create:
        try:
            os.makedirs(root, mode=0o700, exist_ok=True)
        except OSError as exc:
            raise StoreError("cannot create state directory") from exc
    try:
        st = os.lstat(root)
        if (
            not stat.S_ISDIR(st.st_mode)
            or st.st_uid != os.getuid()
            or stat.S_IMODE(st.st_mode) != 0o700
        ):
            raise StoreError("unsafe state directory")
    except FileNotFoundError:
        if not create:
            return None
        raise
    return root


def _open_regular(path, flags, mode=0o600, dir_fd=None):
    try:
        fd = os.open(
            path,
            flags | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
            mode,
            dir_fd=dir_fd,
        )
        st = os.fstat(fd)
        if (
            not stat.S_ISREG(st.st_mode)
            or st.st_uid != os.getuid()
            or stat.S_IMODE(st.st_mode) != 0o600
            or st.st_nlink != 1
        ):
            os.close(fd)
            raise StoreError("unsafe state file")
        return fd
    except OSError as exc:
        raise StoreError("cannot open state file") from exc


def _load(root, dir_fd=None):
    path = (
        "inventory.json" if dir_fd is not None else os.path.join(root, "inventory.json")
    )
    try:
        os.stat(path, dir_fd=dir_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    fd = _open_regular(path, os.O_RDONLY, dir_fd=dir_fd)
    try:
        with os.fdopen(fd, "rb") as f:
            data = f.read(MAX_SNAPSHOT_BYTES + 1)
        if len(data) > MAX_SNAPSHOT_BYTES:
            raise ValueError("snapshot too large")
        value = json.loads(data.decode("utf-8"))
        validate_snapshot(value)
        return value
    except (ValueError, TypeError, OSError, RecursionError) as exc:
        raise StoreError("invalid snapshot") from exc


def load_snapshot(root=None):
    root = _root(root)
    return None if root is None else _load(root)


def save_snapshot(root, snapshot, expected_generation):
    try:
        validate_snapshot(snapshot)
    except (ValueError, TypeError) as exc:
        raise StoreError("invalid snapshot") from exc
    root = _root(root, True)
    try:
        directory = os.open(
            root,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
    except OSError as exc:
        raise StoreError("cannot open state directory") from exc
    st = os.fstat(directory)
    if (
        not stat.S_ISDIR(st.st_mode)
        or st.st_uid != os.getuid()
        or stat.S_IMODE(st.st_mode) != 0o700
    ):
        os.close(directory)
        raise StoreError("unsafe opened state directory")
    try:
        lock = _open_regular(
            ".inventory.lock", os.O_RDWR | os.O_CREAT, dir_fd=directory
        )
    except Exception:
        os.close(directory)
        raise
    try:
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise StoreError("state lock timeout")
                time.sleep(min(0.05, max(0, deadline - time.monotonic())))
        for guard in ('generation.json', '.migration-journal.json'):
            try:
                os.stat(guard, dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                continue
            raise StoreError('report transaction required')
        current = _load(root, directory)
        generation = current["generation"] if current else 0
        if generation != expected_generation or snapshot["generation"] != generation:
            raise StoreError("generation mismatch")
        if current and (
            snapshot["profile_id"] != current["profile_id"]
            or snapshot["previous_snapshot_id"] != current["snapshot_id"]
        ):
            raise StoreError("profile or ancestry mismatch")
        if not current and snapshot["previous_snapshot_id"] is not None:
            raise StoreError("foreign snapshot")
        saved = copy.deepcopy(snapshot)
        saved["generation"] = generation + 1
        try:
            serialized = json.dumps(
                saved, ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
        except (TypeError, ValueError, UnicodeError) as exc:
            raise StoreError("snapshot serialization failed") from exc
        if len(serialized) > MAX_SNAPSHOT_BYTES:
            raise StoreError("snapshot too large")
        temporary = ".inventory-" + uuid.uuid4().hex
        fd = os.open(
            temporary,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=directory,
        )
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(serialized)
                f.flush()
                os.fsync(f.fileno())
            os.replace(
                temporary, "inventory.json", src_dir_fd=directory, dst_dir_fd=directory
            )
        finally:
            try:
                os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass
        return saved
    except OSError as exc:
        raise StoreError("snapshot write failed") from exc
    finally:
        os.close(lock)
        os.close(directory)


from contextlib import contextmanager


@contextmanager
def locked_state(root):
    """Share the snapshot writer lock with multi-file report transactions."""
    root = _root(root, True)
    directory = os.open(root, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_NOFOLLOW', 0))
    lock = None
    try:
        opened = os.fstat(directory)
        if (not stat.S_ISDIR(opened.st_mode) or opened.st_uid != os.getuid()
                or stat.S_IMODE(opened.st_mode) != 0o700):
            raise StoreError('unsafe opened state directory')
        lock = _open_regular('.inventory.lock', os.O_RDWR | os.O_CREAT, dir_fd=directory)
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise StoreError('state lock timeout')
                time.sleep(0.01)
        yield root
    except OSError as exc:
        raise StoreError('state transaction failed') from exc
    finally:
        if lock is not None:
            os.close(lock)
        os.close(directory)


def reconcile_inventory(previous, snapshot):
    """Compatibility export for the pure typed observation reconciler."""
    from inventory_collect import reconcile_inventory as reconcile
    return reconcile(previous, snapshot)
