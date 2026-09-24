#!/usr/bin/env python3
"""lib/python/brew_casks.py — Pure helpers for Homebrew casks (v1.5.0).

Functions for parsing app targets, detecting orphaned casks, and identifying
casks requiring administrator / sudo privileges.
"""

from __future__ import annotations

import json
import os
from typing import Callable


def cask_guard_facts(text: str) -> str:
    """'version|installed|A.app;B.app' from `brew info --json=v2 --cask <t>`; '' on any parse error."""
    try:
        cask = json.loads(text)["casks"][0]
    except (ValueError, KeyError, IndexError, TypeError):
        return ""
    version = str(cask.get("version") or "")
    installed = str(cask.get("installed") or "")
    return "|".join((version, installed, ";".join(app_targets(cask))))


def cask_primary_app(text: str) -> str:
    """First app target name ('X.app') or ''."""
    try:
        targets = app_targets(json.loads(text)["casks"][0])
    except (ValueError, KeyError, IndexError, TypeError):
        return ""
    return targets[0] if targets else ""


def app_targets(cask: dict) -> list[str]:
    """From artifacts {"app": [...]}; string -> basename; dict -> target basename."""
    targets: list[str] = []
    for art in cask.get("artifacts", []):
        if isinstance(art, dict) and "app" in art:
            items = art["app"]
            if isinstance(items, (str, dict)):
                items = [items]
            for item in items:
                if isinstance(item, str):
                    name = os.path.basename(item)
                    if name:
                        targets.append(name)
                elif isinstance(item, dict) and "target" in item:
                    name = os.path.basename(item["target"])
                    if name:
                        targets.append(name)
    return targets


def find_orphan_casks(
    info_json: dict,
    app_dirs: list[str],
    exists: Callable[[str], bool] = os.path.exists,
) -> list[str]:
    """Cask has >= 1 app target and NONE exist in any of app_dirs."""
    orphans: list[str] = []
    for cask in info_json.get("casks", []):
        targets = app_targets(cask)
        if not targets:
            continue
        found = False
        for target in targets:
            for app_dir in app_dirs:
                if exists(os.path.join(app_dir, target)):
                    found = True
                    break
            if found:
                break
        if not found:
            token = cask.get("token")
            if token:
                orphans.append(token)
    return orphans


def cask_requires_sudo(cask: dict) -> bool:
    """Artifacts contain key 'pkg' or 'installer', or uninstall stanza contains 'pkgutil', 'launchctl' or 'kext'."""
    for art in cask.get("artifacts", []):
        if not isinstance(art, dict):
            continue
        if "pkg" in art or "installer" in art:
            return True
        if "uninstall" in art:
            uninst = art["uninstall"]
            if isinstance(uninst, dict):
                uninst = [uninst]
            if isinstance(uninst, list):
                for item in uninst:
                    if isinstance(item, dict):
                        for k in ("pkgutil", "launchctl", "kext"):
                            if k in item:
                                return True
    return False
