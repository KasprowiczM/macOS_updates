#!/usr/bin/env bash
# ============================================================
# Shared process execution and timeout helpers across orchestrators
# ============================================================

run_with_timeout() {
    local seconds="$1"
    local command_pid command_exit elapsed grace
    shift
    if command -v timeout >/dev/null 2>&1; then
        started_at=$SECONDS
        timeout --kill-after=5 "$seconds" "$@"
        command_exit=$?
        elapsed=$(( SECONDS - started_at ))
        if [ "$command_exit" -eq 124 ]; then
            return 124
        fi
        if [ "$command_exit" -eq 137 ] && [ "$elapsed" -ge "$seconds" ]; then
            return 124
        fi
        return "$command_exit"
    elif command -v gtimeout >/dev/null 2>&1; then
        started_at=$SECONDS
        gtimeout --kill-after=5 "$seconds" "$@"
        command_exit=$?
        elapsed=$(( SECONDS - started_at ))
        if [ "$command_exit" -eq 124 ]; then
            return 124
        fi
        if [ "$command_exit" -eq 137 ] && [ "$elapsed" -ge "$seconds" ]; then
            return 124
        fi
        return "$command_exit"
    else
        "$@" &
        command_pid=$!
        elapsed=0
        while kill -0 "$command_pid" 2>/dev/null; do
            if [ "$elapsed" -ge "$seconds" ]; then
                kill -TERM "$command_pid" 2>/dev/null || true
                grace=0
                while kill -0 "$command_pid" 2>/dev/null && [ "$grace" -lt 5 ]; do
                    sleep 1
                    grace=$((grace + 1))
                done
                kill -KILL "$command_pid" 2>/dev/null || true
                wait "$command_pid" 2>/dev/null || true
                return 124
            fi
            sleep 1
            elapsed=$((elapsed + 1))
        done
        wait "$command_pid"
        command_exit=$?
        return "$command_exit"
    fi
}
