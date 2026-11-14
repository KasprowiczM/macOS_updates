#!/usr/bin/env bash
# ============================================================
# Shared process execution and timeout helpers across orchestrators
# ============================================================

run_with_timeout() {
    local seconds="$1"
    local command_pid command_exit elapsed
    shift
    if command -v timeout >/dev/null 2>&1 && [ "${MAC_UPDATE_FORCE_TIMEOUT_FALLBACK:-0}" != "1" ]; then
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
    elif command -v gtimeout >/dev/null 2>&1 && [ "${MAC_UPDATE_FORCE_TIMEOUT_FALLBACK:-0}" != "1" ]; then
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
        if command -v python3 >/dev/null 2>&1; then
            python3 -c 'import os, sys
os.setpgrp()
os.execvp(sys.argv[1], sys.argv[1:])
' "$@" &
        else
            "$@" &
        fi
        command_pid=$!
        elapsed=0
        while kill -0 "$command_pid" 2>/dev/null; do
            if [ "$elapsed" -ge "$seconds" ]; then
                # TERM-ignoring parents keep children alive; kill the process
                # group immediately after TERM so leftover work cannot finish.
                kill -TERM -"$command_pid" 2>/dev/null || kill -TERM "$command_pid" 2>/dev/null || true
                kill -KILL -"$command_pid" 2>/dev/null || kill -KILL "$command_pid" 2>/dev/null || true
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
