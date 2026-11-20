"""Conservative npm duplicate discovery for explicitly supported native CLIs."""

from __future__ import annotations

import json
from pathlib import Path

from vendor_feeds import version_compare

NATIVE_NPM_PACKAGES = {"claude": "@anthropic-ai/claude-code", "codex": "@openai/codex", "opencode": "opencode-ai"}


def supported_native_path(home: str, command: str, executable: str) -> bool:
    roots = {
        "claude": Path(home) / ".local/share/claude/versions",
        "codex": Path(home) / ".codex/packages/standalone/releases",
        "opencode": Path(home) / ".opencode/bin",
    }
    root = roots.get(command)
    if root is None:
        return False
    resolved = Path(executable).resolve()
    return resolved.is_file() and root.resolve() in resolved.parents and "node_modules" not in resolved.parts


def known_npm_prefixes(home: str, toolchain: str, brew_prefix: str = "") -> list[Path]:
    """Inspect known package roots; never walk arbitrary user directories."""
    roots = [Path(toolchain) / "npm-global", Path(toolchain) / "node"]
    roots.extend(sorted((Path(home) / ".nvm/versions/node").glob("v*")))
    if brew_prefix:
        roots.append(Path(brew_prefix))
    return list(dict.fromkeys(roots))


def npm_duplicates(prefixes: list[Path], command: str) -> list[tuple[Path, str]]:
    package = NATIVE_NPM_PACKAGES.get(command)
    if not package:
        return []
    result = []
    for prefix in prefixes:
        manifest = prefix / "lib/node_modules" / package / "package.json"
        try:
            # npm cleanup must not follow a package or node_modules symlink
            # into a different user-owned tree.
            if manifest.resolve().parent != prefix.resolve() / "lib/node_modules" / package:
                continue
            data = json.loads(manifest.read_text())
            if data.get("name") == package:
                result.append((prefix, str(data.get("version", ""))))
        except (OSError, ValueError):
            continue
    return result


def removal_allowed(native_version: str, package_version: str, process_listing: str | None, command: str) -> bool:
    """Uncertain versions/process state retain the fallback install."""
    relation = version_compare(native_version, package_version)
    if relation is None or relation < 0 or process_listing is None:
        return False
    # Match command/path tokens, not substrings (Codex desktop helpers do not
    # own npm CLI packages). Also catches npm's node-hosted wrapper scripts.
    package = NATIVE_NPM_PACKAGES.get(command, "")
    for line in process_listing.splitlines():
        tokens = line.split()
        if not tokens:
            continue
        executable = Path(tokens[0]).name
        if executable in (command, command + ".exe"):
            return False
        # Shell -c arguments can mention a command without running it. Only
        # actual interpreter script arguments prove ownership of npm files.
        if executable in ("node", "bun", "npm"):
            # Runtime flags can precede the wrapper (node --flag /path/bin).
            if any(Path(token).name in (command, command + ".exe") or (package and f"node_modules/{package}/" in token) for token in tokens[1:]):
                return False
        if executable in ("bash", "sh", "zsh") and "-c" not in tokens[1:]:
            scripts = [token for token in tokens[1:] if not token.startswith("-")]
            if scripts and (Path(scripts[0]).name in (command, command + ".exe") or (package and f"node_modules/{package}/" in scripts[0])):
                return False
    return True
