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
    "Google Chrome": ["Google Chrome", "Chrome"],
    "Chrome": ["Chrome", "Google Chrome"],
    "Microsoft Word": ["Microsoft Word", "Word"],
    "Word": ["Word", "Microsoft Word"],
    "Microsoft Excel": ["Microsoft Excel", "Excel"],
    "Excel": ["Excel", "Microsoft Excel"],
    "Microsoft PowerPoint": ["Microsoft PowerPoint", "PowerPoint"],
    "PowerPoint": ["PowerPoint", "Microsoft PowerPoint"],
    "Microsoft Outlook": ["Microsoft Outlook", "Outlook"],
    "Outlook": ["Outlook", "Microsoft Outlook"],
    "Microsoft OneNote": ["Microsoft OneNote", "OneNote"],
    "OneNote": ["OneNote", "Microsoft OneNote"],
}

SYSTEM_APP_FRAGMENTS: list[str] = [
    "Installer", "Uninstaller", "Helper", "Agent", "Updater",
    "Shim", "Launcher", "Framework", "Plugin", "Extension",
    "Service", "Daemon", "XPC", "Feedback", "Handler",
]


def default_app_dirs() -> tuple[str, ...]:
    """Application directories to scan: MAC_UPDATE_APP_DIRS (colon-separated,
    used by tests and hermetic runs) or /Applications plus ~/Applications."""
    override = os.environ.get("MAC_UPDATE_APP_DIRS", "").strip()
    if override:
        dirs = tuple(d for d in override.split(":") if d)
        if dirs:
            return dirs
    return ("/Applications", os.path.expanduser("~/Applications"))


def norm_name(s: str) -> str:
    """Normalize application name for loose comparisons.

    Markers the toolkit itself writes into APPLICATIONS.md must not change a
    name's identity. The prescan appends new applications to the "🆕" section
    as e.g. "GarageBand 🆕" or architecture markers like "[x86_64]"; leaving
    markers in the normalized form meant the row never matched the installed
    app again. Drop architecture markers, symbol, modifier and format characters
    (emoji and variation selectors) along with separators.
    """
    cleaned = _ARCH_MARKER_RE.sub("", s)
    stripped = "".join(
        ch for ch in cleaned if unicodedata.category(ch) not in ("So", "Sk", "Cf")
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


_ARCH_MARKER_RE = re.compile(r"\[(x86_64(?:-only)?|arm64|universal|unknown)\]", re.IGNORECASE)


def strip_inventory_markers(name: str) -> str:
    """Return the application name without markers the toolkit writes into APPLICATIONS.md.

    New applications are recorded as e.g. "HyperFrames [arm64] 🆕". The removed-app
    check used that raw cell as a bundle name, so "HyperFrames [arm64].app" never
    existed and the next run deleted the row (2026-11-02: HyperFrames, Superset).
    """
    cleaned = _ARCH_MARKER_RE.sub("", name)
    cleaned = "".join(ch for ch in cleaned if unicodedata.category(ch) not in ("So", "Sk", "Cf"))
    return re.sub(r"\s+", " ", cleaned).strip()


def app_exists(
    name: str,
    aliases: dict[str, list[str]] | None = None,
    app_dirs: tuple[str, ...] | None = None,
) -> bool:
    """Check if an application bundle exists on the filesystem in /Applications."""
    alias_map = aliases if aliases is not None else APP_ALIASES
    name = strip_inventory_markers(name)
    candidates = set(alias_map.get(name, [name]))
    for key, val_list in alias_map.items():
        if name == key or name in val_list:
            candidates.add(key)
            candidates.update(val_list)
    search_dirs = app_dirs if app_dirs is not None else default_app_dirs()
    for candidate in sorted(candidates):
        for applications_dir in search_dirs:
            if os.path.exists(os.path.join(applications_dir, candidate + ".app")):
                return True
    return False


NEW_APPS_HEADING = "### 🆕 Nowo wykryte aplikacje"


def append_rows_to_new_section(content: str, rows: str) -> str | None:
    """Insert table rows after the last row of the 🆕 section's own table.

    The section ends at the next "##"/"###" heading. The previous regex needed a
    blank line before the "> **Uwaga:**" note; without one it ran on into the 4a
    Formulae table of GROUP 4, where sync_formulae deleted the rows as uninstalled
    formulae (2026-11-02: HyperFrames and Superset never appeared). None when the
    section or its table is missing.
    """
    start = content.find(NEW_APPS_HEADING)
    if start < 0:
        return None
    body_start = content.find("\n", start)
    if body_start < 0:
        return None
    nxt = re.search(r"^#{2,3} ", content[body_start + 1:], re.MULTILINE)
    end = body_start + 1 + nxt.start() if nxt else len(content)
    last_row_end = None
    for m in re.finditer(r"^\|[^\n]*\|[ \t]*(?:\n|$)", content[body_start + 1:end], re.MULTILINE):
        last_row_end = body_start + 1 + m.end()
    if last_row_end is None:
        return None
    insert = rows if content[last_row_end - 1:last_row_end] == "\n" else "\n" + rows
    return content[:last_row_end] + insert + content[last_row_end:]


OPEN_DESIGN_BUNDLE_ID = "io.open-design.desktop"
HYPERFRAMES_BUNDLE_ID = "dev.hyperframes.desktop"


def _read_plist(path: str) -> dict:
    import plistlib

    try:
        with open(path, "rb") as handle:
            data = plistlib.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def open_design_payload_version(app_path: str | Path, home: str | None = None) -> str | None:
    """Version of the payload the Open Design launcher actually runs.

    The bundle in /Applications is a launcher whose own version never changes
    (0.21.1); its native updater activates payloads under Application Support and
    records the active one in runtime.json. install.json must name this bundle,
    otherwise the payload belongs to another installation.
    """
    import json

    base = os.path.join(
        home or os.path.expanduser("~"),
        "Library", "Application Support", "Open Design", "launcher", "channels",
    )
    try:
        channels = sorted(os.listdir(base))
    except OSError:
        return None
    target = os.path.realpath(str(app_path))
    for channel in channels:
        ns_root = os.path.join(base, channel, "namespaces")
        try:
            namespaces = sorted(os.listdir(ns_root))
        except OSError:
            continue
        for namespace in namespaces:
            ns_dir = os.path.join(ns_root, namespace)
            try:
                with open(os.path.join(ns_dir, "install.json"), encoding="utf-8") as handle:
                    install = json.load(handle)
                with open(os.path.join(ns_dir, "runtime.json"), encoding="utf-8") as handle:
                    runtime = json.load(handle)
            except (OSError, ValueError):
                continue
            launch = install.get("launchPath") if isinstance(install, dict) else None
            if not launch or os.path.realpath(launch) != target:
                continue
            active = runtime.get("active") if isinstance(runtime, dict) else None
            version = active.get("version") if isinstance(active, dict) else None
            if isinstance(version, str) and version.strip():
                return version.strip()
    return None


def vendor_installed_version(app_path: str | Path, home: str | None = None) -> str | None:
    """Installed version where CFBundleShortVersionString is not the updater's identity.

    - Open Design: the active launcher payload (see open_design_payload_version).
    - HyperFrames: HFBuildLabel ("b637"); the bundle stays 0.1.0 while its native
      updater ships numbered builds that latest.json names the same way.
    None for every other application.
    """
    info = _read_plist(os.path.join(str(app_path), "Contents", "Info.plist"))
    bundle_id = info.get("CFBundleIdentifier")
    if bundle_id == OPEN_DESIGN_BUNDLE_ID:
        return open_design_payload_version(app_path, home=home)
    if bundle_id == HYPERFRAMES_BUNDLE_ID:
        label = info.get("HFBuildLabel")
        if isinstance(label, str) and re.fullmatch(r"b\d+", label.strip()):
            return label.strip()
    return None


def installed_app_version(app_path: str | Path) -> str:
    """Read installed application version with canonical fallback hierarchy.

    Order:
      0. vendor_installed_version (Open Design payload, HyperFrames build label)
      1. defaults read CFBundleShortVersionString
      2. defaults read CFBundleVersion
      3. mdls -name kMDItemVersion -raw
    Cross-reference: lib/version.sh app_version()
    """
    path_str = str(app_path)
    override = vendor_installed_version(path_str)
    if override:
        return override
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


def app_architecture(app_path: str | Path) -> str:
    """Determine application architecture using lipo -archs on CFBundleExecutable.

    Returns: "arm64" | "universal" | "x86_64-only" | "unknown"
    """
    path = Path(app_path)
    if not path.exists():
        return "unknown"

    exe_path: Path | None = None
    info_plist = path / "Contents" / "Info.plist"
    exe_name: str | None = None

    if info_plist.is_file():
        try:
            import plistlib
            with open(info_plist, "rb") as fp:
                plist = plistlib.load(fp)
                if isinstance(plist, dict):
                    exe_name = plist.get("CFBundleExecutable")
        except Exception:
            pass

    if not exe_name:
        try:
            res = subprocess.run(
                ["defaults", "read", str(path / "Contents" / "Info"), "CFBundleExecutable"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0 and res.stdout.strip():
                exe_name = res.stdout.strip()
        except Exception:
            pass

    if exe_name:
        candidate = path / "Contents" / "MacOS" / exe_name
        if candidate.is_file():
            exe_path = candidate

    if not exe_path:
        macos_dir = path / "Contents" / "MacOS"
        if macos_dir.is_dir():
            try:
                files = [f for f in macos_dir.iterdir() if f.is_file()]
                if len(files) == 1:
                    exe_path = files[0]
                elif (macos_dir / path.stem).is_file():
                    exe_path = macos_dir / path.stem
            except Exception:
                pass

    if not exe_path or not exe_path.is_file():
        return "unknown"

    try:
        res = subprocess.run(
            ["lipo", "-archs", str(exe_path)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0 and res.stdout.strip():
            archs = set(res.stdout.strip().split())
            has_arm = any("arm64" in a for a in archs)
            has_intel = any("x86_64" in a or "i386" in a for a in archs)
            if has_arm and has_intel:
                return "universal"
            elif has_arm:
                return "arm64"
            elif has_intel:
                return "x86_64-only"
    except Exception:
        pass

    return "unknown"


# ── Update-method detection for newly found applications (read-only) ─────────

_SANITIZE_RE = re.compile(r"[|\r\n\t]+")


def _clean(text: str) -> str:
    return _SANITIZE_RE.sub(" ", str(text)).strip()


def _host_of(url: str) -> str:
    from urllib.parse import urlparse

    try:
        return urlparse(str(url).strip()).hostname or ""
    except ValueError:
        return ""


def _electron_updater_details(yml_path: str) -> tuple[str, str]:
    """(provider, host) from an electron-builder app-update.yml; never the full URL."""
    provider = host = ""
    try:
        with open(yml_path, encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                line = raw.strip()
                if line.startswith("provider:") and not provider:
                    provider = line.split(":", 1)[1].strip().strip("\"'")
                elif line.startswith("url:") and not host:
                    host = _host_of(line.split(":", 1)[1].strip().strip("\"'"))
                elif line.startswith("host:") and not host:
                    host = line.split(":", 1)[1].strip().strip("\"'")
    except OSError:
        pass
    return provider, host


def detect_update_method(app_path: str | Path) -> dict[str, str]:
    """Suggest how an installed application updates itself, from its bundle only.

    Read-only: reads Info.plist, app-update.yml and looks for framework/receipt
    directories; nothing is executed or fetched. Returns
    {"method", "detail", "label"} where method is one of "mas", "sparkle",
    "electron-updater", "squirrel", "unknown" and label is a short sanitized
    string safe for a Markdown table cell (provider/host only, never a full URL).
    """
    app = str(app_path)
    contents = os.path.join(app, "Contents")

    def result(method: str, detail: str = "") -> dict[str, str]:
        detail = _clean(detail)
        label = f"{method} ({detail})" if detail else method
        return {"method": method, "detail": detail, "label": label}

    if os.path.isdir(os.path.join(contents, "_MASReceipt")) or os.path.isfile(
        os.path.join(app, "Wrapper", "iTunesMetadata.plist")
    ):
        return result("mas", "Mac App Store")

    info = _read_plist(os.path.join(contents, "Info.plist"))
    feed = info.get("SUFeedURL")
    if isinstance(feed, str) and feed.strip():
        return result("sparkle", "feed " + (_host_of(feed) or "set"))

    yml = os.path.join(contents, "Resources", "app-update.yml")
    if os.path.isfile(yml):
        provider, host = _electron_updater_details(yml)
        detail = " ".join(part for part in (provider, host) if part)
        return result("electron-updater", detail)

    frameworks = os.path.join(contents, "Frameworks")
    if os.path.isdir(os.path.join(frameworks, "Squirrel.framework")):
        return result("squirrel")
    if os.path.isdir(os.path.join(frameworks, "Sparkle.framework")):
        return result("sparkle", "framework, no feed URL in Info.plist")
    return result("unknown")


def scan_installed_app_paths(
    app_dirs: tuple[str, ...] | None = None,
) -> tuple[dict[str, str], list[str]]:
    """Scan /Applications and ~/Applications for installed .app bundles."""
    search_dirs = app_dirs if app_dirs is not None else default_app_dirs()
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


def __getattr__(name: str):
    """Dynamically re-export inventory_sync functions without circular import."""
    import inventory_sync
    if hasattr(inventory_sync, name):
        return getattr(inventory_sync, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
