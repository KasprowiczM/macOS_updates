"""Detect trailing non-OK streaks in run summary logs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STEPS = ("prescan", "appstore", "npmcli", "brew", "internet", "postupdate", "system")


def is_ok(status: Any) -> bool:
    if isinstance(status, dict):
        return status.get("code") == "ok"
    return str(status or "").startswith("OK")


def is_skipped(status: Any) -> bool:
    """A skipped step carries no evidence either way: it is neutral in a streak."""
    return isinstance(status, dict) and status.get("code") == "skipped"


def is_eligible_run(summary: dict[str, Any]) -> bool:
    """Dry-run and inventory-only runs execute nothing, so they are not evidence."""
    flags = summary.get("flags")
    if isinstance(flags, dict) and (flags.get("dry_run") or flags.get("inventory_only")):
        return False
    return True


def load_summaries(logs_dir: str, window: int) -> list[dict[str, Any]]:
    logs_path = Path(logs_dir)
    if not logs_path.is_dir() or window <= 0:
        return []

    files = sorted(
        path for path in logs_path.glob("run_summary_20*.json") if path.name != "run_summary_latest.json"
    )
    summaries: list[dict[str, Any]] = []
    for path in reversed(files):
        if len(summaries) >= window:
            break
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if (
            isinstance(data, dict)
            and data.get("run_status", "completed") == "completed"
            and is_eligible_run(data)
        ):
            summaries.append(data)
    summaries.reverse()  # oldest first
    return summaries


def find_chronic_streaks(logs_dir: str, window: int = 10, threshold: int = 3) -> list[dict[str, Any]]:
    summaries = load_summaries(logs_dir, window)
    if not summaries or threshold <= 0:
        return []

    hits: list[dict[str, Any]] = []
    for step in STEPS:
        streak = 0
        first_timestamp = ""
        for summary in reversed(summaries):
            steps = summary.get("steps")
            if not isinstance(steps, dict):
                steps = {}
            if step not in steps:
                break  # step absent from this run — trailing streak ends here
            status = steps.get(step, "")
            if is_skipped(status):
                continue  # neither extends nor ends the streak
            if is_ok(status):
                break
            streak += 1
            first_timestamp = str(summary.get("timestamp", "")) or ""
        if streak >= threshold:
            hits.append(
                {
                    "step": step,
                    "streak": streak,
                    "first_timestamp": first_timestamp,
                }
            )
    return hits
