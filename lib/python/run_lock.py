"""Per-repository lock with PID, creation time, and stale-PID release."""

from __future__ import annotations

import errno
import os
import time
from pathlib import Path


class LockError(RuntimeError):
    pass


def lock_path(repo_root: Path) -> Path:
    return Path(repo_root) / ".mac-update.lock"


def acquire(repo_root: Path, *, stale_after_seconds: int = 3600) -> Path:
    path = lock_path(repo_root)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(path), flags, 0o600)
    except FileExistsError:
        payload = _read(path)
        pid = payload.get("pid")
        if pid == os.getpid():
            return path
        started = payload.get("started_unix", 0.0)
        if pid and _pid_alive(pid):
            raise LockError(f"Lock held by pid {pid} since {payload.get('started')}")
        if pid and not _pid_alive(pid):
            path.unlink(missing_ok=True)
        elif time.time() - float(started or 0) > stale_after_seconds:
            path.unlink(missing_ok=True)
        else:
            raise LockError(f"Lock file exists at {path}")
        try:
            fd = os.open(str(path), flags, 0o600)
        except FileExistsError as exc:
            raise LockError(f"Lock file exists at {path}") from exc
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(
            f"pid={os.getpid()}\n"
            f"started={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
            f"started_unix={time.time()}\n"
        )
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def release(repo_root: Path) -> None:
    path = lock_path(repo_root)
    if not path.exists():
        return
    payload = _read(path)
    pid = payload.get("pid")
    if pid in (None, os.getpid()):
        path.unlink(missing_ok=True)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as exc:
        if getattr(exc, "errno", None) == errno.ESRCH:
            return False
        if getattr(exc, "errno", None) == errno.EPERM:
            return True
        return False


def _read(path: Path) -> dict:
    data: dict = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key == "pid":
                try:
                    data["pid"] = int(value)
                except ValueError:
                    data["pid"] = None
            elif key == "started_unix":
                try:
                    data["started_unix"] = float(value)
                except ValueError:
                    data["started_unix"] = 0.0
            else:
                data[key] = value
    except OSError:
        return {}
    return data
