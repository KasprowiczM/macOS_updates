#!/usr/bin/env bash
# lib/run_lock.sh — Per-repository lock with PID, start time, and stale release.

mac_update_lock_path() {
    local root="${1:-.}"
    printf '%s' "$root/.mac-update.lock"
}

mac_update_lock_acquire() {
    local root="${1:-.}"
    local lock
    local pid=""
    local started=""
    lock="$(mac_update_lock_path "$root")"

    if [ -f "$lock" ]; then
        pid="$(awk -F= '/^pid=/{print $2; exit}' "$lock" 2>/dev/null || true)"
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
