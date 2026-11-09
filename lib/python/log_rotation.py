"""lib/python/log_rotation.py — rotation of the files update_all.sh writes to logs/.

Pure functions (no globals, no prompts). Only two families of files are ever
considered; everything else in logs/ is left alone:

* ``update_all_*.log``      run logs      — newest ``keep_logs`` survive
* ``run_summary_*.json``    run summaries — newest ``keep_summaries`` survive

Summaries are ranked by modification time together with any stray names such as
``run_summary_<epoch>.json`` or ``run_summary_debug.json`` (they used to escape
rotation entirely). ``run_summary_latest.json`` and ``version_history.tsv`` are
never deleted. Leftover ``.run_summary_*.tmp`` files of an interrupted atomic
write are removed once they are a day old.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

PROTECTED_NAMES = frozenset({"run_summary_latest.json", "version_history.tsv"})
STALE_TMP_SECONDS = 24 * 3600


def _ranked(paths: list[Path]) -> list[Path]:
    """Newest first: modification time, then name (both descending)."""
    def key(path: Path) -> tuple[float, str]:
        try:
            return (path.lstat().st_mtime, path.name)
        except OSError:
            return (0.0, path.name)

    return sorted(paths, key=key, reverse=True)


def plan_rotation(
    logs_dir: str | Path,
    keep_logs: int,
    keep_summaries: int,
    now: float | None = None,
) -> list[Path]:
    """Files that rotation would delete (nothing is touched)."""
    root = Path(logs_dir)
    if not root.is_dir():
        return []
    keep_logs = max(1, int(keep_logs))
    keep_summaries = max(1, int(keep_summaries))
    now = time.time() if now is None else now

    def regular(pattern: str) -> list[Path]:
        found = []
        for path in root.glob(pattern):
            if path.name in PROTECTED_NAMES:
                continue
            try:
                if path.is_file() or path.is_symlink():
                    found.append(path)
            except OSError:
                continue
        return found

    doomed: list[Path] = []
    doomed.extend(_ranked(regular("update_all_*.log"))[keep_logs:])
    doomed.extend(_ranked(regular("run_summary_*.json"))[keep_summaries:])
    for tmp in regular(".run_summary_*.tmp"):
        try:
            if now - tmp.lstat().st_mtime > STALE_TMP_SECONDS:
                doomed.append(tmp)
        except OSError:
            continue
    return doomed


def rotate_logs(
    logs_dir: str | Path,
    keep_logs: int,
    keep_summaries: int,
    now: float | None = None,
) -> list[str]:
    """Delete what plan_rotation selects; returns the removed file names."""
    removed: list[str] = []
    for path in plan_rotation(logs_dir, keep_logs, keep_summaries, now=now):
        try:
            os.unlink(path)
        except OSError:
            continue
        removed.append(path.name)
    return removed
