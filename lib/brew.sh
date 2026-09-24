#!/usr/bin/env bash
# ============================================================
# lib/brew.sh — resilient Homebrew query helpers (Bash 3.2+)
# ============================================================
# Why this file exists:
#   Homebrew regressed `brew list --cask --versions` upstream
#   (6.0.18-48-gad5738c, 2026-08-19):
#       Error: uninitialized constant Cask::CaskLoader
#   `brew list --cask` (names only) still works, and the Caskroom
#   layout ($(brew --prefix)/Caskroom/<token>/<version>) has been
#   stable for years. Every caller in this repo must go through the
#   helpers below so a single upstream `brew` bug can never turn a
#   healthy machine into a blocking pipeline failure again.
# ============================================================
_BREW_SH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# brew_cask_versions
#   Prints one "<cask-token> <version>" line per installed cask.
#   Return 0 when the cask inventory is trustworthy (including the
#   legitimately empty case), 1 when Homebrew could not be queried at all.
brew_cask_versions() {
    local out names prefix room ver

    command -v brew >/dev/null 2>&1 || return 1

    out="$(brew list --cask --versions 2>/dev/null)"
    if [ -n "$out" ]; then
        printf '%s\n' "$out"
        return 0
    fi

    names="$(brew list --cask 2>/dev/null)"
    if [ -z "$names" ]; then
        # Either no casks at all, or brew itself is broken. Only the
        # first case is a success.
        if brew list --cask >/dev/null 2>&1; then
            return 0
        fi
        return 1
    fi

    prefix="$(brew --prefix 2>/dev/null)"
    [ -n "$prefix" ] || prefix="/opt/homebrew"

    printf '%s\n' "$names" | while IFS= read -r name; do
        [ -n "$name" ] || continue
        ver=""
        room="$prefix/Caskroom/$name"
        if [ -d "$room" ]; then
            # shellcheck disable=SC2010,SC2012  # cask tokens and version dirs are
            # [a-z0-9.,_-] by Homebrew's own naming rules; newest-first ordering is
            # what we want and a glob cannot express it in Bash 3.2.
            ver="$(ls -1t "$room" 2>/dev/null | grep -v '^\.' | head -1)"
        fi
        printf '%s %s\n' "$name" "${ver:-latest}"
    done
    return 0
}

# brew_formula_versions
#   Same contract as brew_cask_versions, for formulae. Kept here so
#   callers have one import for both halves of the inventory.
brew_formula_versions() {
    command -v brew >/dev/null 2>&1 || return 1
    brew list --formula --versions 2>/dev/null
}

# brew_outdated_formulae
#   Prints only real outdated-formula lines on stdout. `brew outdated`
#   writes progress chatter ("==> Downloading Homebrew API data",
#   "✔︎ JSON API ...") to stderr; capturing it with 2>&1 made the
#   post-upgrade verification treat that chatter as outstanding
#   formulae and hard-fail the whole run (2026-08-19 regression).
#   Return 0 on success, 1 when the query itself failed.
brew_outdated_formulae() {
    local err_file rc out
    command -v brew >/dev/null 2>&1 || return 1
    err_file="$(mktemp "${TMPDIR:-/tmp}/mac_update_brew_outdated.XXXXXX")" || return 1
    out="$(brew outdated --formula 2>"$err_file")"
    rc=$?
    if [ "$rc" -ne 0 ]; then
        cat "$err_file" >&2
    fi
    rm -f "$err_file" 2>/dev/null || true
    printf '%s' "$out" | grep -v '^==>' | grep -v '^✔' | grep -v '^[[:space:]]*$' || true
    return "$rc"
}

# brew_outdated_casks [greedy_tokens...]
#   Queries outdated casks. Runs `brew outdated --cask` plus, when greedy tokens
#   are provided, `brew outdated --cask --greedy-auto-updates <tokens>`.
#   Returns unique union by the first field (cask token).
brew_outdated_casks() {
    local err_file rc out out_greedy
    command -v brew >/dev/null 2>&1 || return 1
    err_file="$(mktemp "${TMPDIR:-/tmp}/mac_update_brew_outdated_cask.XXXXXX")" || return 1
    out="$(brew outdated --cask 2>"$err_file")"
    rc=$?
    if [ "$rc" -ne 0 ]; then
        cat "$err_file" >&2
        rm -f "$err_file" 2>/dev/null || true
        return "$rc"
    fi
    if [ $# -gt 0 ]; then
        out_greedy="$(brew outdated --cask --greedy-auto-updates "$@" 2>"$err_file")"
        rc=$?
        if [ "$rc" -ne 0 ]; then
            cat "$err_file" >&2
            rm -f "$err_file" 2>/dev/null || true
            return "$rc"
        fi
    else
        out_greedy=""
    fi
    rm -f "$err_file" 2>/dev/null || true
    printf '%s\n%s\n' "$out" "$out_greedy" | grep -v '^==>' | grep -v '^✔' | grep -v '^[[:space:]]*$' | awk '!seen[$1]++' || true
    return 0
}

# brew_orphan_casks
#   Prints tokens of installed casks whose app targets do not exist in
#   /Applications or $HOME/Applications.
#   Returns 0 on success, 1 on query failure (never assumes all are orphans).
brew_orphan_casks() {
    command -v brew >/dev/null 2>&1 || return 1
    local installed_casks
    installed_casks="$(brew list --cask 2>/dev/null)" || return 1
    [ -n "$installed_casks" ] || return 0

    local err_file
    err_file="$(mktemp "${TMPDIR:-/tmp}/mac_update_brew_orphan_err.XXXXXX")" || return 1

    PYTHONPATH="$_BREW_SH_DIR/python${PYTHONPATH:+:$PYTHONPATH}" python3 - "$err_file" "$HOME" $installed_casks <<'PYEOF_ORPHANS'
import json, os, subprocess, sys
from brew_casks import find_orphan_casks

err_file = sys.argv[1]
home = sys.argv[2]
tokens = sys.argv[3:]
if not tokens:
    sys.exit(0)

try:
    with open(err_file, "w", encoding="utf-8") as ef:
        res = subprocess.run(
            ["brew", "info", "--json=v2", "--cask"] + tokens,
            stdout=subprocess.PIPE,
            stderr=ef,
            text=True,
            check=False,
        )
    if res.returncode != 0 or not res.stdout.strip():
        sys.exit(1)
    data = json.loads(res.stdout)
    app_dirs = ["/Applications", os.path.join(home, "Applications")]
    orphans = find_orphan_casks(data, app_dirs)
    for o in orphans:
        print(o)
except Exception:
    sys.exit(1)
PYEOF_ORPHANS
    local rc=$?
    rm -f "$err_file" 2>/dev/null || true
    return "$rc"
}

# brew_casks_requiring_sudo <tokens...>
#   Prints tokens among the given cask tokens that require administrator / sudo
#   privileges for installation or uninstallation.
brew_casks_requiring_sudo() {
    [ $# -gt 0 ] || return 0
    command -v brew >/dev/null 2>&1 || return 1
    local err_file
    err_file="$(mktemp "${TMPDIR:-/tmp}/mac_update_brew_sudo_err.XXXXXX")" || return 1

    PYTHONPATH="$_BREW_SH_DIR/python${PYTHONPATH:+:$PYTHONPATH}" python3 - "$err_file" "$@" <<'PYEOF_SUDO'
import json, subprocess, sys
from brew_casks import cask_requires_sudo

err_file = sys.argv[1]
tokens = sys.argv[2:]
if not tokens:
    sys.exit(0)

try:
    with open(err_file, "w", encoding="utf-8") as ef:
        res = subprocess.run(
            ["brew", "info", "--json=v2", "--cask"] + tokens,
            stdout=subprocess.PIPE,
            stderr=ef,
            text=True,
            check=False,
        )
    if res.returncode != 0 or not res.stdout.strip():
        sys.exit(1)
    data = json.loads(res.stdout)
    for c in data.get("casks", []):
        if cask_requires_sudo(c):
            tok = c.get("token")
            if tok:
                print(tok)
except Exception:
    sys.exit(1)
PYEOF_SUDO
    local rc=$?
    rm -f "$err_file" 2>/dev/null || true
    return "$rc"
}

# brew_xcode_license_ok
#   Returns 0 if xcode-select does not point to Xcode.app or if xcodebuild
#   license check succeeds. Returns 1 if Xcode.app is selected and license
#   has not been agreed to. Does not invoke brew.
brew_xcode_license_ok() {
    local dev_path
    command -v xcode-select >/dev/null 2>&1 || return 0
    dev_path="$(xcode-select -p 2>/dev/null)"
    case "$dev_path" in
        *.app/Contents/Developer*)
            if command -v xcodebuild >/dev/null 2>&1; then
                xcodebuild -license check >/dev/null 2>&1 || return 1
            fi
            ;;
    esac
    return 0
}

# brew_cask_latest_versions
#   Queries Homebrew for the latest version of one or more casks (read-only oracle).
#   Prints "token<TAB>version" lines to stdout.
#   Returns 0 on success, 1 on failure.
brew_cask_latest_versions() {
    [ $# -gt 0 ] || return 0
    command -v brew >/dev/null 2>&1 || return 1
    local err_file rc
    err_file="$(mktemp "${TMPDIR:-/tmp}/mac_update_brew_cask_info.XXXXXX")" || return 1
    python3 - "$err_file" "$@" <<'PYEOF'
import json
import subprocess
import sys

err_file = sys.argv[1]
tokens = sys.argv[2:]
if not tokens:
    sys.exit(0)

def query_casks(cask_list):
    try:
        with open(err_file, "w", encoding="utf-8") as ef:
            res = subprocess.run(
                ["brew", "info", "--json=v2", "--cask"] + cask_list,
                stdout=subprocess.PIPE,
                stderr=ef,
                text=True,
                check=False,
            )
        if res.stdout and res.stdout.strip():
            return json.loads(res.stdout).get("casks", [])
    except Exception:
        pass
    return None

casks = query_casks(tokens)
if casks is None:
    casks = []
    for tok in tokens:
        res = query_casks([tok])
        if res:
            casks.extend(res)

seen = set()
for cask in casks:
    tok = cask.get("token") or ""
    ver = cask.get("version") or ""
    if tok and ver and tok not in seen:
        seen.add(tok)
        print(f"{tok}\t{ver}")
    for old_tok in cask.get("old_tokens", []):
        if old_tok and ver and old_tok not in seen:
            seen.add(old_tok)
            print(f"{old_tok}\t{ver}")
PYEOF
    rc=$?
    rm -f "$err_file" 2>/dev/null || true
    return "$rc"
}

