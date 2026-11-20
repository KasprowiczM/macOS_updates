"""Pure helpers for choosing a Node.js release from nodejs.org/dist/index.json."""

from __future__ import annotations

import re

_STABLE = re.compile(r"^v\d+\.\d+\.\d+$")


def latest_stable_node(index: list) -> str | None:
    """Newest stable release ("vX.Y.Z") from the dist index, which is newest-first.

    2026-10-29: index.json started with v27.0.0-alpha.0.0.0; taking arr[0] moved the
    managed toolchain onto an alpha that npm 12 does not support. Pre-releases
    (alpha/beta/rc/nightly suffixes) are never install targets."""
    for entry in index or []:
        ver = entry.get("version") if isinstance(entry, dict) else None
        if isinstance(ver, str) and _STABLE.match(ver):
            return ver
    return None

