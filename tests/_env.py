"""Helper for subprocess environments in tests: strips PYTHONPATH so child shell processes do not inherit it."""
from __future__ import annotations

import os
from typing import Any


_FEED_STATE_SEQ = [0]


def fresh_feed_state_file() -> str:
    """A new, not-yet-existing vendor feed state path (lib/python/feed_state.py).

    Each call returns a distinct path so one test's feed observations can never
    become another test's cached proof or high-water mark."""
    _FEED_STATE_SEQ[0] += 1
    return os.path.join(host_stub_dir(), f"feed_state_{os.getpid()}_{_FEED_STATE_SEQ[0]}.json")


def shell_env(**extra: Any) -> dict[str, str]:
    """Return a copy of os.environ without PYTHONPATH, plus extra environment variables.

    MAC_UPDATE_FEED_STATE_FILE always points at a fresh per-call path unless the
    caller passes one (tests must never share, or touch the real, feed state)."""
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["MAC_UPDATE_FEED_STATE_FILE"] = fresh_feed_state_file()
    for k, v in extra.items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = str(v)
    return env


_HOST_STUB_DIR: str | None = None
# Read-only on the host today, but a test must not depend on the real Homebrew/mas
# (its answer differs per Mac) or reach it at all. Exit 1 = "brew unavailable".
_HOST_STUBS = ("brew", "mas")


def host_stub_dir() -> str:
    """A per-process directory of failing stubs for host tools tests must not reach."""
    global _HOST_STUB_DIR
    if _HOST_STUB_DIR is None:
        import atexit
        import shutil
        import tempfile

        _HOST_STUB_DIR = tempfile.mkdtemp(prefix="mac_update_hoststub_")
        atexit.register(shutil.rmtree, _HOST_STUB_DIR, True)
        for tool in _HOST_STUBS:
            p = os.path.join(_HOST_STUB_DIR, tool)
            with open(p, "w", encoding="utf-8") as f:
                f.write("#!/bin/sh\nexit 1\n")
            os.chmod(p, 0o755)
    return _HOST_STUB_DIR


def isolate_host_tools(env: dict[str, str]) -> dict[str, str]:
    """Insert the stub dir between a test's own mock dirs and the inherited PATH.

    Test mocks prepended to os.environ["PATH"] still win; anything they do not
    mock resolves to a failing stub instead of the real host tool."""
    inherited = os.environ.get("PATH", "")
    path = env.get("PATH", inherited)
    stub = host_stub_dir()
    if inherited and path.endswith(inherited):
        env["PATH"] = path[: len(path) - len(inherited)] + stub + ":" + inherited
    else:
        env["PATH"] = stub + ":" + path
    return env


def install_app_state_stubs(bin_dir) -> None:
    """Stub `defaults` (CFBundleIdentifier only) and `osascript` (is-running probe).

    Fake `.app` directories carry no Info.plist, so the bundle id is derived from
    the directory name (`Foo Bar.app` -> `com.test.FooBar`). The probe answers from
    environment variables: FAKE_RUNNING_IDS (space-separated ids -> true),
    FAKE_UNKNOWN_IDS (ids whose probe fails -> unknown); everything else -> false.
    Other queries fail closed; no real defaults executable is called."""
    from pathlib import Path

    d = Path(bin_dir)
    (d / "defaults").write_text(
        "#!/bin/bash\n"
        'case "$*" in\n'
        "  *CFBundleIdentifier*)\n"
        '    for a in "$@"; do p="$q"; q="$a"; done; p="${p%/Contents/Info}"\n'
        '    n="$(basename "$p" .app | tr -d " ")"\n'
        '    echo "com.test.$n"; exit 0 ;;\n'
        "esac\n"
        'exit 1\n',
        encoding="utf-8",
    )
    (d / "osascript").write_text(
        "#!/bin/bash\n"
        'id="$(printf "%s" "$*" | sed -n \'s/.*application id "\\([^"]*\\)".*/\\1/p\')"\n'
        'for u in $FAKE_UNKNOWN_IDS; do [ "$u" = "$id" ] && exit 1; done\n'
        'for r in $FAKE_RUNNING_IDS; do [ "$r" = "$id" ] && { echo true; exit 0; }; done\n'
        "echo false\n",
        encoding="utf-8",
    )
    for n in ("defaults", "osascript"):
        (d / n).chmod(0o755)


# ── Throw-away copy of the toolkit for end-to-end shell tests ───────────────
# Never copy the checkout wholesale: an owner's checkout also holds private and
# untracked content (APPLICATIONS.md, logs/, skills/, dangling symlinks, agent
# directories) that must not leak into a test and can make copytree fail.
_COPY_EXCLUDED_TOP = frozenset({
    ".git", ".claude", ".agents", ".antigravitycli", "logs", "scratch", "tests", "docs", "skills",
    "APPLICATIONS.md", "UPDATES.md", ".dev_sync_config.json", ".mac_update_prefs", ".mac-update.lock",
})
_COPY_FALLBACK_TOP_DIRS = ("lib", "config", "i18n", "scripts", "templates", "dev_sync")


def _copy_allowed(rel: str) -> bool:
    parts = rel.split("/")
    top = parts[0]
    if top in _COPY_EXCLUDED_TOP or top.startswith(".env") or "__pycache__" in parts:
        return False
    return not (len(parts) == 1 and top.startswith(".") and top != ".shellcheckrc")


def _tracked_files(repo_root: str) -> "list[str] | None":
    """Names from `git ls-files -z`, or None when git or the repository is unavailable."""
    import subprocess

    try:
        proc = subprocess.run(["git", "-C", repo_root, "ls-files", "-z"], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    return [p for p in proc.stdout.decode("utf-8", "surrogateescape").split("\0") if p]


def copy_toolkit(repo_root: Any, dest: Any) -> str:
    """Copy only what the toolkit needs into ``dest`` and return it as a string.

    Prefers the tracked files; without git it falls back to the top-level scripts
    plus lib/, config/, i18n/, scripts/, templates/, dev_sync/ and VERSION.
    Untracked or ignored content, private files and dangling symlinks are never
    copied; a tracked symlink is recreated as one.
    """
    import shutil

    root = os.fspath(repo_root)
    out = os.fspath(dest)
    names = _tracked_files(root)
    if names is None:
        names = []
        for entry in sorted(os.listdir(root)):
            full = os.path.join(root, entry)
            if os.path.isfile(full) and (entry.endswith(".sh") or entry == "VERSION"):
                names.append(entry)
        for top in _COPY_FALLBACK_TOP_DIRS:
            for base, dirs, files in os.walk(os.path.join(root, top)):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                names.extend(os.path.relpath(os.path.join(base, f), root) for f in files)
    os.makedirs(out, exist_ok=True)
    for rel in names:
        if not _copy_allowed(rel):
            continue
        src = os.path.join(root, rel)
        dst = os.path.join(out, rel)
        try:
            if os.path.islink(src):
                if not os.path.exists(src):
                    continue  # dangling
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                os.symlink(os.readlink(src), dst)
            elif os.path.isfile(src):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
        except OSError:
            continue  # vanished while copying: not part of the toolkit
    return out
