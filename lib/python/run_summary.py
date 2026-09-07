#!/usr/bin/env python3
"""lib/python/run_summary.py — Machine-readable run summary generator (JSON).

Composes and writes logs/run_summary_<timestamp>.json for automation & monitoring.
"""

from __future__ import annotations

import datetime
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any


FORMAT_VERSION = 2

PENDING_FILES = (
    ("pending_after_run_appstore", "pending_appstore"),
    ("pending_after_run_brew_formulae", "pending_brew_formulae"),
    ("pending_after_run_brew_casks", "pending_brew_casks"),
    ("pending_after_run_mau", "pending_mau"),
)


def determine_exit_class(overall_exit: int, degraded: int) -> str:
    """Classify run outcome into clean (0), warnings (10/degraded), or error (1)."""
    if overall_exit != 0:
        return "error"
    if degraded != 0:
        return "warnings"
    return "clean"


def merge_pending(counts: dict[str, Any], session_dir: str) -> tuple[dict[str, Any], dict[str, str]]:
    """Attach pending-* measurements. Missing/corrupt values stay unknown, not 0."""
    merged = dict(counts)
    verification: dict[str, str] = {}
    for key, filename in PENDING_FILES:
        path = Path(session_dir) / filename
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            merged[key] = None
            verification[key] = "missing"
            continue
        if text == "":
            merged[key] = None
            verification[key] = "empty"
            continue
        if text in {"unknown", "null"}:
            merged[key] = None
            verification[key] = "unknown"
            continue
        try:
            merged[key] = int(text)
            verification[key] = "verified"
        except ValueError:
            merged[key] = None
            verification[key] = "invalid"
    return merged, verification


def build_run_summary(
    start_time: int,
    end_time: int,
    overall_exit: int,
    degraded: int,
    blocking_exit: int,
    step_results: dict[str, str],
    counts: dict[str, Any] | None = None,
    flags: dict[str, Any] | None = None,
    session_dir: str | None = None,
    verification: dict[str, str] | None = None,
    run_status: str = "completed",
    run_id: str | None = None,
) -> dict[str, Any]:
    """Compose the structured run summary dict."""
    duration = max(0, end_time - start_time)
    minutes = duration // 60
    secs = duration % 60

    start_iso = datetime.datetime.fromtimestamp(start_time, tz=datetime.timezone.utc).isoformat()
    end_iso = datetime.datetime.fromtimestamp(end_time, tz=datetime.timezone.utc).isoformat()

    summary: dict[str, Any] = {
        "format_version": FORMAT_VERSION,
        "run_id": run_id or str(uuid.uuid4()),
        "run_status": run_status,
        "timestamp": start_iso,
        "completed_at": end_iso if run_status == "completed" else None,
        "duration_seconds": duration,
        "duration_formatted": f"{minutes}m {secs}s",
        "exit_code": overall_exit,
        "exit_class": determine_exit_class(overall_exit, degraded),
        "degraded": bool(degraded),
        "blocking_exit": blocking_exit,
        "steps": step_results,
        "counts": counts or {},
        "verification": verification or {},
        "flags": flags or {},
    }
    if session_dir:
        summary["session_dir"] = session_dir
        summary["session_dir_note"] = "ephemeral; not a durable archive"
    return summary


def write_run_summary(output_path: str | Path, summary_data: dict[str, Any]) -> str:
    """Atomically serialize summary_data as formatted JSON to output_path."""
    target_path = Path(output_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    json_str = json.dumps(summary_data, indent=2, ensure_ascii=False) + "\n"

    tmp_dir = target_path.parent
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target_path.name}.", suffix=".tmp", dir=tmp_dir)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(json_str)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_name, target_path)
        os.chmod(target_path, 0o600)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return str(target_path)
