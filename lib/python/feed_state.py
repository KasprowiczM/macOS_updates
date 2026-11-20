"""Persistent per-app vendor feed state (pure functions + one atomic writer).

The state remembers, per internet app, what the vendor feed last said and the
highest version it has ever published. Two decisions use it:

* Cached proof (P1-1): a feed fetch failed this run, but a successful fetch no
  older than a bounded TTL listed exactly the installed version. The app is
  reported "current per cached check" instead of being blind-launched. This is
  weaker evidence than a live comparison and is reported with its own status.
* High-water mark (P1-2): the feed now lists a version older than the installed
  one, but the vendor already published a version >= the installed one. The
  feed regressed on the vendor side; the app is current, never an install target.

Format (JSON, mode 0600)::

    {"format": 1, "apps": {"Proton Mail": {
        "last_ok_version": "1.16.1", "last_ok_at": 1762600000,
        "high_water_version": "1.16.1", "high_water_at": 1762400000,
        "last_error": "fetch", "last_error_at": 1762700000}}}

Timestamps are integer Unix seconds. Unknown/corrupt files load as empty state,
so a damaged file can only cost one run of cached evidence, never a wrong answer.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

try:
    from vendor_feeds import version_compare
except ImportError:  # pragma: no cover - imported as lib.python.feed_state
    from .vendor_feeds import version_compare  # type: ignore

FORMAT = 1
DEFAULT_TTL_H = 24.0
MAX_TTL_H = 168.0


def empty_state() -> dict[str, Any]:
    return {"format": FORMAT, "apps": {}}


def load_state(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Read the state file; anything missing, unreadable or malformed is empty state."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return empty_state()
    if not isinstance(data, dict) or data.get("format") != FORMAT or not isinstance(data.get("apps"), dict):
        return empty_state()
    apps = {k: v for k, v in data["apps"].items() if isinstance(k, str) and isinstance(v, dict)}
    return {"format": FORMAT, "apps": apps}


def save_state(path: str | os.PathLike[str], state: dict[str, Any]) -> None:
    """Atomic same-directory write (mkstemp + fsync + os.replace), file mode 0600."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(prefix=".feed_state.", suffix=".tmp", dir=str(target.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=1, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _entry(state: dict[str, Any], app: str) -> dict[str, Any]:
    apps = state.setdefault("apps", {})
    entry = apps.get(app)
    if not isinstance(entry, dict):
        entry = {}
        apps[app] = entry
    return entry


def record_success(state: dict[str, Any], app: str, version: str, now: float) -> dict[str, Any]:
    """Remember a successful feed observation and raise the high-water mark if needed."""
    if not app or not version or version_compare(version, version) is None:
        return state
    entry = _entry(state, app)
    ts = int(now)
    entry["last_ok_version"] = version
    entry["last_ok_at"] = ts
    hw = entry.get("high_water_version")
    cmp = version_compare(version, hw) if isinstance(hw, str) and hw else None
    if cmp is None or cmp > 0:
        entry["high_water_version"] = version
        entry["high_water_at"] = ts
    entry.pop("last_error", None)
    entry.pop("last_error_at", None)
    return state


def record_failure(state: dict[str, Any], app: str, reason: str, now: float) -> dict[str, Any]:
    """Remember why the latest fetch failed ("fetch" or "parse"); keeps the good observations."""
    if not app:
        return state
    entry = _entry(state, app)
    entry["last_error"] = reason if reason in ("fetch", "parse") else "fetch"
    entry["last_error_at"] = int(now)
    return state


def clamp_ttl(value: Any, default: float = DEFAULT_TTL_H, maximum: float = MAX_TTL_H) -> float:
    """TTL in hours from an env-style value: non-numeric -> default, clamped to [0, maximum]."""
    try:
        ttl = float(str(value).strip())
    except (TypeError, ValueError):
        return default
    if math.isnan(ttl):
        return default
    return max(0.0, min(maximum, ttl))


def format_age_h(age_h: float) -> str:
    """Human age in whole hours; anything under one hour is "<1"."""
    if age_h < 1.0:
        return "<1"
    return str(int(age_h))


def cached_proof(
    state: dict[str, Any], app: str, installed: str, ttl_h: float, now: float
) -> dict[str, Any] | None:
    """A successful observation younger than ttl_h whose version equals the installed one."""
    if ttl_h <= 0 or not installed:
        return None
    entry = state.get("apps", {}).get(app)
    if not isinstance(entry, dict):
        return None
    version, seen = entry.get("last_ok_version"), entry.get("last_ok_at")
    if not isinstance(version, str) or not isinstance(seen, (int, float)):
        return None
    age_h = (now - float(seen)) / 3600.0
    if age_h < 0 or age_h > ttl_h:
        return None
    if version_compare(version, installed) != 0:
        return None
    return {"version": version, "age_h": age_h, "seen_at": int(seen)}


def high_water_covers(state: dict[str, Any], app: str, installed: str) -> dict[str, Any] | None:
    """The highest vendor version ever seen, when it is >= the installed version."""
    if not installed:
        return None
    entry = state.get("apps", {}).get(app)
    if not isinstance(entry, dict):
        return None
    hw = entry.get("high_water_version")
    if not isinstance(hw, str) or not hw:
        return None
    cmp = version_compare(hw, installed)
    if cmp is None or cmp < 0:
        return None
    return {"version": hw, "seen_at": entry.get("high_water_at")}
