#!/usr/bin/env python3
"""lib/python/run_summary.py — Machine-readable run summary generator (JSON).

Composes and writes logs/run_summary_<timestamp>.json for automation & monitoring.
"""

from __future__ import annotations

import datetime
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def determine_exit_class(overall_exit: int, degraded: int) -> str:
    """Classify run outcome into clean (0), warnings (10/degraded), or error (1)."""
    if overall_exit != 0:
        return "error"
    if degraded != 0:
        return "warnings"
    return "clean"


def build_run_summary(
    start_time: int,
    end_time: int,
    overall_exit: int,
    degraded: int,
    blocking_exit: int,
    step_results: dict[str, str],
    counts: dict[str, int] | None = None,
    flags: dict[str, Any] | None = None,
    session_dir: str | None = None,
) -> dict[str, Any]:
    """Compose the structured run summary dict."""
    duration = max(0, end_time - start_time)
    minutes = duration // 60
    secs = duration % 60

    start_iso = datetime.datetime.fromtimestamp(start_time, tz=datetime.timezone.utc).isoformat()
    end_iso = datetime.datetime.fromtimestamp(end_time, tz=datetime.timezone.utc).isoformat()

    summary: dict[str, Any] = {
        "timestamp": start_iso,
        "completed_at": end_iso,
        "duration_seconds": duration,
        "duration_formatted": f"{minutes}m {secs}s",
        "exit_code": overall_exit,
        "exit_class": determine_exit_class(overall_exit, degraded),
        "degraded": bool(degraded),
        "blocking_exit": blocking_exit,
        "steps": step_results,
        "counts": counts or {},
        "flags": flags or {},
    }
    if session_dir:
        summary["session_dir"] = session_dir
    return summary


def write_run_summary(output_path: str | Path, summary_data: dict[str, Any]) -> str:
    """Atomically serialize summary_data as formatted JSON to output_path."""
    target_path = Path(output_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    json_str = json.dumps(summary_data, indent=2, ensure_ascii=False) + "\n"

    tmp_dir = target_path.parent
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=tmp_dir, delete=False, suffix=".tmp"
    ) as tmp_file:
        tmp_file.write(json_str)
        tmp_name = tmp_file.name

    os.replace(tmp_name, target_path)
    os.chmod(target_path, 0o644)
    return str(target_path)
