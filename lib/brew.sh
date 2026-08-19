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

# brew_outdated_casks
#   Same, for `brew outdated --cask --greedy-auto-updates`.
brew_outdated_casks() {
    local err_file rc out
    command -v brew >/dev/null 2>&1 || return 1
    err_file="$(mktemp "${TMPDIR:-/tmp}/mac_update_brew_outdated_cask.XXXXXX")" || return 1
    out="$(brew outdated --cask --greedy-auto-updates 2>"$err_file")"
    rc=$?
    if [ "$rc" -ne 0 ]; then
        cat "$err_file" >&2
    fi
    rm -f "$err_file" 2>/dev/null || true
    printf '%s' "$out" | grep -v '^==>' | grep -v '^✔' | grep -v '^[[:space:]]*$' || true
    return "$rc"
}
