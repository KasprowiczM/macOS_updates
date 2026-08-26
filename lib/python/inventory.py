#!/usr/bin/env python3
"""lib/python/inventory.py — Pure-function inventory & prescan helpers.

Contains parsing, normalization, version detection, and exclusion loading
used by update_all.sh prescan and postupdate stages.
"""

from __future__ import annotations

import os
import re
import unicodedata
import subprocess
from pathlib import Path


APP_ALIASES: dict[str, list[str]] = {
    "OpenCode": ["OpenCode", "opencode", "Opencode", "opencode Desktop"],
    "Ledger Live": ["Ledger Live", "Ledger Wallet"],
    "Docker": ["Docker", "Docker Desktop"],
    "Docker Desktop": ["Docker", "Docker Desktop"],
    "ChatGPT / Codex": ["ChatGPT / Codex", "ChatGPT", "Codex", "Codex Desktop (OpenAI)"],
    "ChatGPT": ["ChatGPT", "ChatGPT / Codex", "Codex", "Codex Desktop (OpenAI)"],
    "Codex": ["Codex", "ChatGPT", "ChatGPT / Codex", "Codex Desktop (OpenAI)"],
    "Comet": ["Comet", "Comet (Perplexity Browser)"],
    "Perplexity": ["Perplexity", "Perplexity Desktop"],
    "zoom.us": ["zoom.us", "Zoom"],
    "Visual Studio Code": ["Visual Studio Code", "VS Code"],
    "Brave Browser": ["Brave Browser", "Brave"],
    "Firefox Developer Edition": ["Firefox Developer Edition", "Firefox Dev Edition"],
    "Keynote Creator Studio": ["Keynote Creator Studio", "Keynote"],
    "Numbers Creator Studio": ["Numbers Creator Studio", "Numbers"],
    "Pages Creator Studio": ["Pages Creator Studio", "Pages"],
}

SYSTEM_APP_FRAGMENTS: list[str] = [
    "Installer", "Uninstaller", "Helper", "Agent", "Updater",
    "Shim", "Launcher", "Framework", "Plugin", "Extension",
    "Service", "Daemon", "XPC", "Feedback", "Handler",
]


def norm_name(s: str) -> str:
    """Normalize application name for loose comparisons.

    Markers the toolkit itself writes into APPLICATIONS.md must not change a
    name's identity. The prescan appends new applications to the "🆕" section
    as e.g. "GarageBand 🆕"; leaving the emoji in the normalized form meant the
    row never matched the installed "GarageBand" again, so every auto-appended
    app was re-reported as new on every subsequent run. Drop symbol, modifier
    and format characters (emoji and variation selectors) along with the
    separators.
    """
    stripped = "".join(
        ch for ch in s if unicodedata.category(ch) not in ("So", "Sk", "Cf")
    )
    return re.sub(r"[-_ .]", "", stripped.lower().strip())


def load_exclusions(config_path: str | Path) -> set[str]:
    """Load excluded application names from config/inventory_exclusions.txt."""
    exclusions = set(["Utilities"])
    path = Path(config_path)
    if not path.is_file():
        return exclusions

    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.split("#", 1)[0].strip()
                if line:
                    exclusions.add(line)
    except OSError:
        pass
    return exclusions


def load_appstore_gui_apps(methods_path: str | Path) -> set[str]:
    """Load application names configured for App Store GUI Track 2."""
    gui_apps: set[str] = set()
    path = Path(methods_path)
    if not path.is_file():
        return gui_apps

    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue
                fields = line.split("|")
                if len(fields) >= 2 and fields[1].strip() == "appstore_gui":
                    gui_apps.add(fields[0].strip())
    except OSError:
        pass
    return gui_apps


def row_exists(table_content: str, name: str, aliases: dict[str, list[str]] | None = None) -> bool:
    """Check if an application row exists in the markdown table content."""
    alias_map = aliases if aliases is not None else APP_ALIASES
    candidates = set(alias_map.get(name, [name]))
    for key, val_list in alias_map.items():
        if name == key or name in val_list:
            candidates.add(key)
            candidates.update(val_list)
    for candidate in sorted(candidates):
        pattern = (
            r"^\|\s*(?:\*\*)?" + re.escape(candidate)
            + r"(?:\*\*)?(?:\s+[^|]+)?\s*\|"
        )
        if re.search(pattern, table_content, re.MULTILINE) is not None:
            return True
    return False


def app_exists(
    name: str,
    aliases: dict[str, list[str]] | None = None,
    app_dirs: tuple[str, ...] | None = None,
) -> bool:
    """Check if an application bundle exists on the filesystem in /Applications."""
    alias_map = aliases if aliases is not None else APP_ALIASES
    candidates = set(alias_map.get(name, [name]))
    for key, val_list in alias_map.items():
        if name == key or name in val_list:
            candidates.add(key)
            candidates.update(val_list)
    search_dirs = (
        app_dirs
        if app_dirs is not None
        else ("/Applications", os.path.expanduser("~/Applications"))
    )
    for candidate in sorted(candidates):
        for applications_dir in search_dirs:
            if os.path.exists(os.path.join(applications_dir, candidate + ".app")):
                return True
    return False


def installed_app_version(app_path: str | Path) -> str:
    """Read installed application version with canonical fallback hierarchy.

    Order:
      1. defaults read CFBundleShortVersionString
      2. defaults read CFBundleVersion
      3. mdls -name kMDItemVersion -raw
    Cross-reference: lib/version.sh app_version()
    """
    path_str = str(app_path)
    info_path = os.path.join(path_str, "Contents", "Info")

    for key in ("CFBundleShortVersionString", "CFBundleVersion"):
        try:
            result = subprocess.run(
                ["defaults", "read", info_path, key],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass

    try:
        result = subprocess.run(
            ["mdls", "-name", "kMDItemVersion", "-raw", path_str],
            capture_output=True,
            text=True,
            timeout=5,
        )
        val = result.stdout.strip()
        if result.returncode == 0 and val not in ("", "(null)"):
            return val
    except Exception:
        pass

    return "?"


def scan_installed_app_paths(
    app_dirs: tuple[str, ...] | None = None,
) -> tuple[dict[str, str], list[str]]:
    """Scan /Applications and ~/Applications for installed .app bundles."""
    search_dirs = (
        app_dirs
        if app_dirs is not None
        else ("/Applications", os.path.expanduser("~/Applications"))
    )
    installed_app_paths: dict[str, str] = {}

    for applications_dir in search_dirs:
        try:
            for item in os.listdir(applications_dir):
                if item.endswith(".app"):
                    app_name = item[:-4]
                    installed_app_paths.setdefault(
                        app_name, os.path.join(applications_dir, item)
                    )
        except Exception:
            pass

    installed_apps = sorted(
        name
        for name in installed_app_paths
        if "|" not in name and not any(ord(char) < 32 or ord(char) == 127 for char in name)
    )
    return installed_app_paths, installed_apps
