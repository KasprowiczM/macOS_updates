"""Private operation timings and explicit evidence classes, never inferred success."""
import contextlib
import datetime
import json
import hashlib
import os
import re
import stat
import subprocess
import time
from pathlib import Path

MAX_BYTES = 4 * 1024 * 1024
FIELDS = ("run_id", "action_id", "recipe_revision", "phase", "start", "end",
          "elapsed_ms", "outcome", "evidence_type")
WAIT_BUDGETS = {
    "MAC_UPDATE_STAGE_WAIT": (90, 0, 600),
    "MAC_UPDATE_QUIT_WAIT": (60, 0, 300),
    "MAC_UPDATE_QUIT_MIN_AGE": (30, 0, 300),
    "MAC_UPDATE_QUIT_RESEND": (10, 1, 60),
    "MAC_UPDATE_INTERNET_SETTLE_SECONDS": (15, 0, 120),
    "MAC_UPDATE_OMAHA_WAIT": (45, 0, 180),
}


def evidence_freshness(evidence_type):
    if evidence_type in {"live_version_comparison", "installed_version_observation",
                         "process_exit_observation", "signature_verification"}:
        return "fresh"
    if evidence_type == "updater_history":
        return "historical"
    if evidence_type in {"quit_request", "launch_request"}:
        return "unconfirmed"
    return "unknown"


def _token(value):
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:@+-]{1,128}", value) else "unknown"


def public_receipt(event):
    """Allowlisted export excludes private paths, commands and free-form diagnostics."""
    result = {k: event[k] for k in FIELDS if k in event}
    for key in set(result) - {"start", "end", "elapsed_ms"}:
        result[key] = _token(result[key])
    for key in ("start", "end"):
        try:
            datetime.datetime.fromisoformat(result.get(key, ""))
        except (ValueError, TypeError):
            result[key] = "unknown"
    result["evidence_freshness"] = evidence_freshness(result.get("evidence_type"))
    return result


def _validate(event):
    if not isinstance(event, dict) or any(key not in event for key in FIELDS):
        raise ValueError("incomplete_phase_event")
    if type(event["elapsed_ms"]) is not int or event["elapsed_ms"] < 0:
        raise ValueError("invalid_elapsed_time")
    for key in FIELDS:
        if key != "elapsed_ms" and not isinstance(event[key], str):
            raise ValueError("invalid_phase_event")
    for key in ("start", "end"):
        try:
            value = datetime.datetime.fromisoformat(event[key])
            if value.tzinfo is None:
                raise ValueError("missing_timezone")
        except (ValueError, TypeError) as exc:
            raise ValueError("invalid_phase_time") from exc
    return dict(event, evidence_freshness=evidence_freshness(event["evidence_type"]))


def append_phase_event(session_dir, event):
    value = _validate(event)
    payload = (json.dumps(value, ensure_ascii=True) + "\n").encode()
    if len(payload) > 65536:
        raise ValueError("phase_event_too_large")
    path = Path(session_dir) / "operation-receipts.jsonl"
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_EX)
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1
            or info.st_size + len(payload) > MAX_BYTES):
            raise ValueError("invalid_receipt_file")
        os.fchmod(fd, 0o600)
        if os.write(fd, payload) != len(payload):
            raise OSError("incomplete_receipt_write")
    finally:
        os.close(fd)


def _read_private(path):
    fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("invalid_receipt_file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("receipt_file_too_large")
        return data.decode("utf-8")
    finally:
        os.close(fd)


def read_phase_events(session_dir):
    if not session_dir:
        return []
    try:
        raw = _read_private(Path(session_dir) / "operation-receipts.jsonl")
    except (OSError, ValueError, UnicodeError):
        return []
    events = []
    for line in raw.splitlines()[:20000]:
        try:
            events.append(_validate(json.loads(line)))
        except (ValueError, TypeError):
            continue
    return events


@contextlib.contextmanager
def phase_receipt(session_dir, *, run_id, action_id, recipe_revision, phase, evidence_type="none"):
    started = time.monotonic()
    event = dict(run_id=run_id, action_id=action_id, recipe_revision=recipe_revision,
                 phase=phase, start=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 outcome="unknown", evidence_type=evidence_type)
    try:
        yield event
    except BaseException:
        event["outcome"] = "error"
        raise
    finally:
        event.update(end=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                     elapsed_ms=max(0, round((time.monotonic() - started) * 1000)))
        append_phase_event(session_dir, event)


def capture_provenance(toolkit_root, env=None):
    """Read local source identity once; missing Git information remains unknown."""
    env = os.environ if env is None else env
    version = "unknown"
    try:
        candidate = _read_private(Path(toolkit_root) / "VERSION").strip()
        if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?", candidate):
            version = candidate
    except (OSError, ValueError, UnicodeError):
        pass
    sha, dirty = "unknown", None
    try:
        result = subprocess.run(["git", "-C", str(toolkit_root), "rev-parse", "HEAD"],
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=3)
        if result.returncode == 0 and re.fullmatch(r"[0-9a-f]{40,64}", result.stdout.strip()):
            sha = result.stdout.strip()
        result = subprocess.run(["git", "-C", str(toolkit_root), "status", "--porcelain", "--untracked-files=no"],
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            dirty = bool(result.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    budgets = {}
    for key, (default, low, high) in WAIT_BUDGETS.items():
        raw = env.get(key, str(default))
        value = int(raw) if isinstance(raw, str) and re.fullmatch(r"[0-9]{1,9}", raw) else default
        budgets[key] = min(high, max(low, value))
    return dict(toolkit_version=version, git_sha=sha, dirty=dirty, effective_wait_budgets=budgets)


def write_provenance(session_dir, provenance):
    fd = os.open(str(Path(session_dir) / "run-provenance.json"),
                 os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(provenance, stream)


def read_provenance(session_dir):
    if session_dir:
        try:
            value = json.loads(_read_private(Path(session_dir) / "run-provenance.json"))
            if isinstance(value, dict):
                return {k: value.get(k) for k in ("toolkit_version", "git_sha", "dirty", "effective_wait_budgets")}
        except (OSError, ValueError, UnicodeError):
            pass
    return dict(toolkit_version="unknown", git_sha="unknown", dirty=None, effective_wait_budgets={})


def write_source_diagnostics(session_dir, snapshot):
    """Keep source-level failures visible without exporting prefix/root locations."""
    issues = []
    for key, source in snapshot.get("sources", {}).items():
        if source.get("status") == "ok" and source.get("complete"):
            continue
        issues.append(dict(source_kind=_token(key.split(":", 1)[0]),
                           source_ref=hashlib.sha256(key.encode()).hexdigest()[:12],
                           status=_token(source.get("status")), complete=False,
                           reason_code=_token(source.get("reason_code")),
                           observed_items=len(source.get("items", [])),
                           issues=[dict(reason_code=_token(issue.get("reason_code")), count=issue["count"])
                                   for issue in source.get("issues", [])
                                   if isinstance(issue, dict) and type(issue.get("count")) is int and issue["count"] > 0]))
    fd = os.open(str(Path(session_dir) / "inventory-source-issues.json"),
                 os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(issues, stream)


def read_source_diagnostics(session_dir):
    if session_dir:
        try:
            issues = json.loads(_read_private(Path(session_dir) / "inventory-source-issues.json"))
            if isinstance(issues, list) and all(isinstance(issue, dict) for issue in issues):
                return issues
        except (OSError, ValueError, UnicodeError):
            pass
    return []
