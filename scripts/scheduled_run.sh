#!/usr/bin/env bash
# scripts/scheduled_run.sh — body of the scheduled (LaunchAgent) run.
#
# Order: optional delay after login -> skip checks (run in progress, low
# battery, recent successful run; each logs one line and exits 0) -> engine
# (update_all.sh --cli, non-interactive, event file) -> ONE notification.
#
# Environment:
#   MAC_UPDATE_DELAY_MIN                 wait until N minutes after login (0 = none)
#   MAC_UPDATE_MIN_BATTERY               skip on battery below this percent (default 30)
#   MAC_UPDATE_MIN_HOURS_BETWEEN_RUNS    skip when the last success is younger (default 12)
#   MAC_UPDATE_AUTOMATION_SYSTEM_UPDATES 1 = also let the run do macOS updates
#                                        (default: --skip-system, report only)
#   MAC_UPDATE_NOTIFY                    always | needs_you | never (legacy 0/1)
#   MAC_UPDATE_SCHEDULED_FORCE           1 = ignore the delay, battery and recency guards
#   MAC_UPDATE_STATE_DIR                 state dir (default ~/.local/state/mac-update)
# Test hooks: MAC_UPDATE_SCHEDULED_ENGINE (engine script), MAC_UPDATE_SLEEP_CMD,
#             MAC_UPDATE_SESSION_AGE_SECS.
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
[ -f "$SCRIPT_DIR/lib/paths.sh" ] && . "$SCRIPT_DIR/lib/paths.sh"
STATE_DIR="$(mu_state_dir 2>/dev/null || printf '%s' "${MAC_UPDATE_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/mac-update}")"
AUTO_DIR="$STATE_DIR/automation"
ENGINE="${MAC_UPDATE_SCHEDULED_ENGINE:-$SCRIPT_DIR/update_all.sh}"

exec </dev/null
umask 077
mkdir -p "$AUTO_DIR" "$STATE_DIR/logs" 2>/dev/null || true

log() { printf '%s [scheduled_run] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }

. "$SCRIPT_DIR/lib/run_lock.sh"
. "$SCRIPT_DIR/lib/notify_summary.sh"

_int() { case "$1" in ''|*[!0-9]*) echo "$2" ;; *) echo "$1" ;; esac; }

FORCE="${MAC_UPDATE_SCHEDULED_FORCE:-0}"

# ── 1. delay after login ────────────────────────────────────────────────────
# Remaining wait = N minutes minus the age of this login session (the per-user
# launchd, our parent). A calendar trigger hours after login therefore starts
# at once; a login trigger waits.
delay_min="$(_int "${MAC_UPDATE_DELAY_MIN:-}" 0)"
if [ "$FORCE" != "1" ] && [ "$delay_min" -gt 0 ]; then
    age="${MAC_UPDATE_SESSION_AGE_SECS:-}"
    if [ -z "$age" ]; then
        et="$(ps -o etime= -p "$PPID" 2>/dev/null | tr -d ' ')"
        age="$(printf '%s' "$et" | awk -F'[-:]' '{
            n=NF; s=$n+0; m=(n>1)?$(n-1)+0:0; h=(n>2)?$(n-2)+0:0; d=0
            if (index($0,"-")>0) d=$1+0
            print s+60*m+3600*h+86400*d }')"
        [ -n "$et" ] || age=0
    fi
    age="$(_int "$age" 0)"
    remaining=$((delay_min * 60 - age))
    if [ "$remaining" -gt 0 ]; then
        log "waiting ${remaining}s (login delay ${delay_min} min)"
        ${MAC_UPDATE_SLEEP_CMD:-sleep} "$remaining"
    fi
fi

# ── 2. skip conditions (all exit 0 with one line) ───────────────────────────
if lpid="$(mac_update_lock_holder "$SCRIPT_DIR")"; then
    log "skip: a run is already in progress (pid $lpid)"
    exit 0
fi

if [ "$FORCE" != "1" ]; then
    . "$SCRIPT_DIR/lib/preflight.sh"
    preflight_check_power quiet
    if [ "$?" -eq 10 ]; then
        log "skip: on battery at ${PREFLIGHT_BATTERY_PCT}% (minimum $(preflight_min_battery)%)"
        exit 0
    fi

    min_hours="$(_int "${MAC_UPDATE_MIN_HOURS_BETWEEN_RUNS:-}" 12)"
    last="$(cat "$AUTO_DIR/last_success" 2>/dev/null)"
    last="$(_int "$last" 0)"
    now="$(date +%s)"
    if [ "$last" -gt 0 ] && [ $((now - last)) -lt $((min_hours * 3600)) ]; then
        log "skip: last successful run was $(((now - last) / 60)) min ago (minimum ${min_hours} h)"
        exit 0
    fi
fi

# ── 3. the run ──────────────────────────────────────────────────────────────
run_id="sched-$(date +%Y%m%d-%H%M%S)-$$"
events="$AUTO_DIR/events-${run_id}.jsonl"
: > "$events" 2>/dev/null || true

notify_mode="${MAC_UPDATE_NOTIFY:-needs_you}"
args="--cli -y"
# First-run-careful: macOS upgrades are only reported unless the user opted in.
[ "${MAC_UPDATE_AUTOMATION_SYSTEM_UPDATES:-0}" = "1" ] || args="$args --skip-system"

log "starting: update_all.sh $args"
# The engine's own osascript notification is off; we send exactly one below.
# shellcheck disable=SC2086
MAC_UPDATE_NONINTERACTIVE=1 MAC_UPDATE_YES=1 MAC_UPDATE_NOTIFY=0 \
    MAC_UPDATE_EVENT_FILE="$events" MAC_UPDATE_RUN_ID="$run_id" \
    bash "$ENGINE" $args
rc=$?
log "engine exit code $rc"

[ "$rc" -eq 0 ] && date +%s > "$AUTO_DIR/last_success" 2>/dev/null

MAC_UPDATE_NOTIFY="$notify_mode" mu_notify_run_summary "$events" "$rc"

# Keep the 14 newest event files.
ls -1t "$AUTO_DIR"/events-*.jsonl 2>/dev/null | tail -n +15 | while IFS= read -r old; do
    rm -f -- "$old"
done
# Non-zero only when the engine failed; launchctl print shows it as last exit code.
exit "$rc"
