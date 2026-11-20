#!/usr/bin/env bash
# lib/run_lock.sh — One run at a time: a lock with PID, start time, and stale release.
#
# The lock lives at <state>/lock (lib/paths.sh; MAC_UPDATE_LOCK_FILE wins), so
# every copy of the toolkit for this user shares it. A live holder of the old
# per-checkout lock (<checkout>/.mac-update.lock, written by 1.9.0 and older)
# is still respected; that old file is only read, never removed.

_MU_RUN_LOCK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mac_update_lock_path() {
    local root="${1:-.}" p=""
    if [ -n "${MAC_UPDATE_LOCK_FILE:-}" ]; then
        printf '%s' "$MAC_UPDATE_LOCK_FILE"
        return 0
    fi
    type mu_lock_file >/dev/null 2>&1 || . "$_MU_RUN_LOCK_DIR/paths.sh"
    p="$(mu_lock_file 2>/dev/null)" || p=""
    [ -n "$p" ] || p="$root/.mac-update.lock"
    printf '%s' "$p"
}

_mac_update_lock_pid() {
    awk -F= '/^pid=/{print $2; exit}' "$1" 2>/dev/null || true
}

# Prints the PID of a live run holding the lock (new or old location), if any.
mac_update_lock_holder() {
    local root="${1:-.}" f pid
    for f in "$(mac_update_lock_path "$root")" "$root/.mac-update.lock"; do
        [ -f "$f" ] || continue
        pid="$(_mac_update_lock_pid "$f")"
        if [ -n "$pid" ] && [ "$pid" != "$$" ] && kill -0 "$pid" 2>/dev/null; then
            printf '%s\n' "$pid"
            return 0
        fi
    done
    return 1
}

mac_update_lock_acquire() {
    local root="${1:-.}"
    local lock legacy
    local pid=""
    local started=""
    lock="$(mac_update_lock_path "$root")"
    legacy="$root/.mac-update.lock"

    if [ "$legacy" != "$lock" ] && [ -f "$legacy" ]; then
        pid="$(_mac_update_lock_pid "$legacy")"
        if [ -n "$pid" ] && [ "$pid" != "$$" ] && kill -0 "$pid" 2>/dev/null; then
            echo "Another macOS Updates run holds $legacy (pid=$pid)" >&2
            return 1
        fi
        pid=""
    fi
    ( umask 077; mkdir -p "$(dirname "$lock")" ) 2>/dev/null || true
    if [ -f "$lock" ]; then
        pid="$(_mac_update_lock_pid "$lock")"
        started="$(awk -F= '/^started=/{print $2; exit}' "$lock" 2>/dev/null || true)"
        if [ "$pid" = "$$" ]; then
            return 0
        fi
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo "Another macOS Updates run holds $lock (pid=$pid started=$started)" >&2
            return 1
        fi
        rm -f "$lock"
    fi
    if (set -C; umask 077; printf 'pid=%s\nstarted=%s\n' "$$" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$lock") 2>/dev/null; then
        return 0
    fi
    echo "Another macOS Updates run holds $lock" >&2
    return 1
}

mac_update_lock_release() {
    local root="${1:-.}"
    local lock
    local pid=""
    lock="$(mac_update_lock_path "$root")"
    [ -f "$lock" ] || return 0
    pid="$(awk -F= '/^pid=/{print $2; exit}' "$lock" 2>/dev/null || true)"
    if [ -z "$pid" ] || [ "$pid" = "$$" ]; then
        rm -f "$lock"
    fi
}

# Canonical per-user target locks span checkouts and live for the command.
# The kernel releases them after a crash; another live owner is never removed.
mac_update_target_lock_run() {
    local lock_lib_dir
    lock_lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    . "$lock_lib_dir/update_policy.sh"
    mac_update_target_lock_run "$@"
}
