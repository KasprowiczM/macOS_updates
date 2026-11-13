#!/usr/bin/env bash
# ============================================================
# SKRYPT MASTER: Aktualizacja całego MacBooka
# ============================================================
# Autor: Antigravity AI

# Catch failures in pipelines (e.g. `cmd1 | cmd2` where cmd1 dies).
# We deliberately do NOT use `set -e` — orchestrator runs every step
# even on partial failure and reports per-step status at the end.
set -o pipefail
# Homebrew can remove /opt/homebrew/bin/python3 (or any other symlink) while
# this process is running. Without checkhash, bash keeps calling the stale
# hashed path ("No such file or directory") instead of re-searching PATH.
shopt -s checkhash

# Data:  2026-04-18 (zaktualizowano)
# Opis:  Uruchamia wszystkie skrypty aktualizacji po kolei:
#        0. Skanowanie i inwentarz wstępny
#        1. App Store
#        2. Native CLI + npm
#        3. Homebrew
#        4. Aplikacje z Internetu
#        5. Aktualizacja APPLICATIONS.md i UPDATES.md z wynikami
#        6. System macOS na końcu (restart-safe, zawsze z -R)
# Kompatybilność: bash 3.2+ (macOS domyślny shell)
# ============================================================

# Kolory
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Katalog z skryptami (ten sam co lokalizacja skryptu master)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Shared libraries ─────────────────────────────────────────
. "$SCRIPT_DIR/lib/cli.sh"
. "$SCRIPT_DIR/lib/ui.sh"
. "$SCRIPT_DIR/lib/internet_apps.sh"
. "$SCRIPT_DIR/lib/brew.sh"
. "$SCRIPT_DIR/lib/platform.sh"
. "$SCRIPT_DIR/lib/version.sh"
. "$SCRIPT_DIR/lib/run_lock.sh"
. "$SCRIPT_DIR/lib/preflight.sh"

save_step_status_codes() {
    if [ -n "${SESSION_DIR:-}" ] && [ -d "$SESSION_DIR" ]; then
        cat <<EOF > "$SESSION_DIR/step_status_codes.txt"
prescan=${STATUS_CODE_SCAN:-skipped}
appstore=${STATUS_CODE_APPSTORE:-skipped}
npmcli=${STATUS_CODE_NPMCLI:-skipped}
brew=${STATUS_CODE_BREW:-skipped}
internet=${STATUS_CODE_INTERNET:-skipped}
postupdate=${STATUS_CODE_MD:-skipped}
system=${STATUS_CODE_SYSTEM:-skipped}
EOF
    fi
}

write_machine_summary() {
    local status="${1:-completed}"
    local end_now rc
    [ -n "${SCRIPT_DIR:-}" ] && [ -n "${SESSION_DIR:-}" ] && [ -n "${START_TIME:-}" ] || return 0
    save_step_status_codes || true
    end_now="$(date +%s)"
    export MAC_UPDATE_RUN_STATUS="$status"
    if ! command -v python3 >/dev/null 2>&1; then
        echo "  run_summary: python3 not found on PATH — cannot write the machine summary" >&2
        return 127
    fi
    python3 -c '
import json, os, sys
sys.path.insert(0, os.path.join(sys.argv[1], "lib", "python"))
from run_summary import build_run_summary, write_run_summary, merge_pending, collect_run_items, format_terminal_summary, read_advisories, read_step_durations

script_dir = sys.argv[1]
session_dir = sys.argv[2]
start_time = int(sys.argv[3])
end_time = int(sys.argv[4])
overall_exit = int(sys.argv[5])
degraded = int(sys.argv[6])
blocking_exit = int(sys.argv[7])

step_results = {
    "prescan": sys.argv[8],
    "appstore": sys.argv[9],
    "npmcli": sys.argv[10],
    "brew": sys.argv[11],
    "internet": sys.argv[12],
    "postupdate": sys.argv[13],
    "system": sys.argv[14],
}

step_codes = {}
codes_path = os.path.join(session_dir, "step_status_codes.txt")
if os.path.isfile(codes_path):
    try:
        with open(codes_path, encoding="utf-8") as scf:
            for line in scf:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    step_codes[k.strip()] = v.strip()
    except Exception:
        pass

flags = {
    "dry_run": os.environ.get("MAC_UPDATE_DRY_RUN") == "1",
    "inventory_only": os.environ.get("MAC_UPDATE_INVENTORY_ONLY") == "1",
    "noninteractive": os.environ.get("MAC_UPDATE_NONINTERACTIVE") == "1",
}

counts = {}
counts_path = os.path.join(session_dir, "run_counts.json")
try:
    with open(counts_path, encoding="utf-8") as cf:
        loaded = json.load(cf)
    if isinstance(loaded, dict):
        counts = {k: int(v) for k, v in loaded.items() if isinstance(v, int)}
except (OSError, ValueError):
    counts = {}

counts, verification = merge_pending(counts, session_dir)
items = collect_run_items(
    session_dir,
    step_results=step_results,
    inventory_updated_count=counts.get("inventory_version_fields_changed", 0),
)
observed_updates = len([it for it in items if it.get("status") == "updated"])
counts["observed_package_changes"] = observed_updates
if "inventory_version_fields_changed" not in counts:
    counts["inventory_version_fields_changed"] = 0
summary = build_run_summary(
    counts=counts,
    start_time=start_time,
    end_time=end_time,
    overall_exit=overall_exit,
    degraded=degraded,
    blocking_exit=blocking_exit,
    step_results=step_results,
    flags=flags,
    session_dir=session_dir,
    verification=verification,
    run_status=os.environ.get("MAC_UPDATE_RUN_STATUS", "completed"),
    run_id=os.environ.get("MAC_UPDATE_RUN_ID"),
    items=items,
    step_codes=step_codes,
    advisories=read_advisories(session_dir),
    step_durations=read_step_durations(session_dir),
)

logs_dir = os.path.join(script_dir, "logs")
ts_str = os.environ.get("RUN_TIMESTAMP") or str(start_time)
out_file = os.path.join(logs_dir, f"run_summary_{ts_str}.json")
write_run_summary(out_file, summary)
latest_file = os.path.join(logs_dir, "run_summary_latest.json")
write_run_summary(latest_file, summary)

if os.environ.get("MAC_UPDATE_JSON_SUMMARY") == "1":
    if os.environ.get("MAC_UPDATE_RUN_STATUS") == "completed":
        print(json.dumps(summary, indent=2))
elif os.environ.get("MAC_UPDATE_RUN_STATUS") == "completed":
    lang = os.environ.get("MAC_LANG", "en")
    print("")
    print(format_terminal_summary(summary, lang=lang))
' "$SCRIPT_DIR" "$SESSION_DIR" "$START_TIME" "$end_now"       "${OVERALL_EXIT:-0}" "${DEGRADED:-0}" "${BLOCKING_EXIT:-0}"       "${RESULT_SCAN:-}" "${RESULT_APPSTORE:-}" "${RESULT_NPMCLI:-}" "${RESULT_BREW:-}"       "${RESULT_INTERNET:-}" "${RESULT_MD:-}" "${RESULT_SYSTEM:-}"
    rc=$?
    if [ "$rc" -ne 0 ]; then
        echo "  run_summary: python3 exited with status $rc while writing the $status summary" >&2
    fi
    if [ "$rc" -eq 0 ] && { [ "$status" = "completed" ] || [ "$status" = "interrupted" ]; }; then
        MAC_UPDATE_SUMMARY_DONE=1
    fi
    return "$rc"
}

# The start-of-run write leaves logs/run_summary_*.json at run_status "started".
# If the final write fails, that file must not masquerade as the run result:
# relabel it "failed" (sed on a same-directory temp file, then rename).
mark_stale_summary_failed() {
    local f tmp
    for f in "$SCRIPT_DIR/logs/run_summary_latest.json" \
             "$SCRIPT_DIR/logs/run_summary_${RUN_TIMESTAMP:-${LOG_TS:-}}.json"; do
        [ -f "$f" ] || continue
        grep -q '"run_status": "started"' "$f" 2>/dev/null || continue
        tmp="$(mktemp "$f.XXXXXX")" || continue
        if sed 's/"run_status": "started"/"run_status": "failed"/' "$f" > "$tmp"; then
            mv -f "$tmp" "$f" || rm -f "$tmp"
        else
            rm -f "$tmp"
        fi
    done
    return 0
}

# ── Per-step wall-clock durations ────────────────────────────
# Steps run strictly one after another, so a single start marker is enough.
# step_timer_stop appends "<key>=<seconds>" to $SESSION_DIR/step_durations.txt
# (read back by write_machine_summary and the closing summary lines). Dry runs
# and skipped steps never call it, so only steps that really ran carry a time.
_STEP_T0=0
step_timer_start() {
    _STEP_T0="$(date +%s)"
}
step_timer_stop() {
    local key="$1" now
    [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ] && return 0
    [ -n "${SESSION_DIR:-}" ] && [ -d "$SESSION_DIR" ] || return 0
    now="$(date +%s)"
    echo "$key=$((now - _STEP_T0))" >> "$SESSION_DIR/step_durations.txt"
}
_fmt_duration() {
    local s="$1"
    if [ "$s" -ge 60 ]; then
        printf '%dm %02ds' $((s / 60)) $((s % 60))
    else
        printf '%ds' "$s"
    fi
}
# " (1m 05s)" for a step that ran, nothing otherwise.
step_duration_suffix() {
    local secs
    [ -n "${SESSION_DIR:-}" ] && [ -f "$SESSION_DIR/step_durations.txt" ] || return 0
    secs="$(sed -n "s/^$1=//p" "$SESSION_DIR/step_durations.txt" | tail -n 1)"
    case "$secs" in
        ''|*[!0-9]*) return 0 ;;
    esac
    printf ' (%s)' "$(_fmt_duration "$secs")"
}

# Step banner. The parenthesised time is the TOTAL elapsed since the start of
# the run (the step's own duration is in the closing summary); the label says so.
step_header() {
    local step_num="$1" step_total="$2" title="$3" elapsed
    elapsed="$(printf "$L_ALL_STEP_ELAPSED_TOTAL_FMT" "$(ui_elapsed)")"
    if ui_is_tty; then
        echo ""
        echo -e "\033[0;36m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"
        echo -e "\033[0;36m  Step ${step_num}/${step_total}: ${title}\033[0m  \033[0;90m(${elapsed})\033[0m"
        echo -e "\033[0;36m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"
        echo ""
    else
        echo ""
        echo "=== Step ${step_num}/${step_total}: ${title} (${elapsed}) ==="
        echo ""
    fi
}

# Run-log filter (P2-1): the terminal keeps its colours, the file does not.
# One process reads the combined stdout/stderr, echoes it unchanged to the
# original stdout and appends the same bytes minus ANSI escape sequences to the
# log. It reads with sysread (no line buffering), so prompts without a trailing
# newline still reach the terminal at once, and an escape sequence split across
# two reads is carried over instead of leaking into the log.
log_strip_ansi_tee() {
    perl -e '
        $| = 1;
        # An unwritable log must not stop the stream: without a log the filter
        # keeps passing output to the terminal (exiting would SIGPIPE the run).
        my $log;
        open($log, ">>", $ARGV[0]) or $log = undef;
        select((select($log), $| = 1)[0]) if $log;
        my $carry = "";
        while (sysread(STDIN, my $buf, 65536)) {
            print STDOUT $buf;
            my $text = $carry . $buf;
            $carry = "";
            $carry = $1 if $text =~ s/(\e(?:\[[0-9;?]*[ -\/]*)?)\z//;
            $text =~ s/\e\[[0-9;?]*[ -\/]*[@-~]//g;
            print $log $text if $log;
        }
        print $log $carry if $log && length $carry;
    ' "$1"
}

export UI_START_EPOCH=$(date +%s)
mac_update_parse_cli "$@"
if [ "${MAC_UPDATE_INVENTORY_ONLY:-0}" = "1" ]; then
    export MAC_UPDATE_SKIP_SYSTEM=1 MAC_UPDATE_SKIP_APPSTORE=1 MAC_UPDATE_SKIP_NPM=1
    export MAC_UPDATE_SKIP_BREW=1 MAC_UPDATE_SKIP_INTERNET=1 MAC_UPDATE_YES=1
fi

# --doctor: a read-only report. It runs before the platform guard (so an
# unsupported platform is reported, not just fatal) and before everything that
# mutates or records: no session dir, no run log, no lock, no sudo, no summary.
if [ "${MAC_UPDATE_DOCTOR:-0}" = "1" ]; then
    . "$SCRIPT_DIR/i18n/loader.sh"
    preflight_doctor
    exit $?
fi

mac_update_require_supported_platform || exit 1

# ── i18n: load language strings ──────────────────────────────
. "$SCRIPT_DIR/i18n/loader.sh"

# A preview exits before locks, logs, preferences, inventory and sudo.
if [ "${MAC_UPDATE_PLAN_ONLY:-0}" = "1" ] || [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
    PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import sys
from plan_orchestration import main
sys.exit(main(sys.argv[1], "preview"))' "$SCRIPT_DIR"
    exit $?
fi

print_banner() {
    # Dynamically size the box to fit the longest line (title or subtitle)
    local title="$L_BANNER_TITLE"
    local subtitle="$L_BANNER_SUBTITLE"
    local title_len=${#title}
    local subtitle_len=${#subtitle}
    local max_len=$title_len
    [ "$subtitle_len" -gt "$max_len" ] && max_len=$subtitle_len
    # Add 6 chars padding on each side (3 spaces + content + 3 spaces = inner_width)
    local inner_width=$((max_len + 6))

    # Build horizontal border: ═ repeated inner_width times
    local border=""
    local i=0
    while [ "$i" -lt "$inner_width" ]; do
        border="${border}═"
        i=$((i + 1))
    done

    # Center title and subtitle with padding
    local title_pad_total=$((inner_width - title_len))
    local title_pad_left=$((title_pad_total / 2))
    local title_pad_right=$((title_pad_total - title_pad_left))

    local sub_pad_total=$((inner_width - subtitle_len))
    local sub_pad_left=$((sub_pad_total / 2))
    local sub_pad_right=$((sub_pad_total - sub_pad_left))

    # Build padding strings
    local empty_line=""
    i=0; while [ "$i" -lt "$inner_width" ]; do empty_line="${empty_line} "; i=$((i + 1)); done

    local tl_pad=""; i=0; while [ "$i" -lt "$title_pad_left" ]; do tl_pad="${tl_pad} "; i=$((i + 1)); done
    local tr_pad=""; i=0; while [ "$i" -lt "$title_pad_right" ]; do tr_pad="${tr_pad} "; i=$((i + 1)); done
    local sl_pad=""; i=0; while [ "$i" -lt "$sub_pad_left" ]; do sl_pad="${sl_pad} "; i=$((i + 1)); done
    local sr_pad=""; i=0; while [ "$i" -lt "$sub_pad_right" ]; do sr_pad="${sr_pad} "; i=$((i + 1)); done

    echo ""
    echo -e "${BLUE}${BOLD}╔${border}╗${NC}"
    echo -e "${BLUE}${BOLD}║${empty_line}║${NC}"
    echo -e "${BLUE}${BOLD}║${tl_pad}${title}${tr_pad}║${NC}"
    echo -e "${BLUE}${BOLD}║${sl_pad}${subtitle}${sr_pad}║${NC}"
    echo -e "${BLUE}${BOLD}║${empty_line}║${NC}"
    echo -e "${BLUE}${BOLD}╚${border}╝${NC}"
    echo ""
}

print_section() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}



# ============================================================
# START
# ============================================================
print_banner
MAC_UPDATE_VER="$(mac_update_version)"
print_info "macOS Updates v${MAC_UPDATE_VER}"

if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
    print_warn "DRY-RUN mode — no system mutations will be performed"
fi

echo -e "  ${BOLD}$L_UPDATE_ALL_INTRO${NC}"
printf "%b\n" "$L_UPDATE_ALL_STEPS" | sed 's/^/    /'
echo ""
echo -e "  ${YELLOW}$L_UPDATE_ALL_DURATION${NC}"
echo ""

START_TIME=$(date +%s)

if [ "${MAC_UPDATE_YES:-0}" != "1" ]; then
    read -r -p "  $L_CONFIRM_UPDATE [T/n]: " CONFIRM
    CONFIRM="${CONFIRM:-T}"
    if [[ "$CONFIRM" =~ ^[Nn] ]]; then
        print_info "$L_UPDATE_CANCELED"
        exit 0
    fi
fi
# The master confirmation covers the whole run: children may skip their own
# redundant "continue? [Y/n]" questions when they see this (P1-5).
export MAC_UPDATE_PARENT_CONFIRMED=1

# ============================================================
# SESJA — katalog tymczasowy
# ============================================================
SESSION_DIR="$(mktemp -d "${TMPDIR:-/tmp}/mac_update.XXXXXX")"
chmod 700 "$SESSION_DIR" 2>/dev/null || true
export MAC_UPDATE_SESSION_DIR="$SESSION_DIR"
export MAS_NO_AUTO_INDEX=1

# First consent belongs to a concrete per-target plan, never to -y.
export MAC_UPDATE_PLAN_PATH="$SESSION_DIR/update-plan.json"
PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import sys
from plan_orchestration import main
sys.exit(main(sys.argv[1], "prepare", sys.argv[2]))' "$SCRIPT_DIR" "$SESSION_DIR"
PLAN_PREPARE_EXIT=$?
if [ "$PLAN_PREPARE_EXIT" -ne 0 ]; then
    print_warn "$L_PLAN_NO_CONSENT"
fi
print_info "$L_ALL_SESSION_DIR_MSG $SESSION_DIR"

# ============================================================
# LOGS — persisted run log (~/Dev_Env/macOS_updates/logs/)
# ============================================================
# Each invocation appends stdout+stderr to a timestamped file in logs/
# so failed runs can be diagnosed after the session dir is cleaned.
# Rotation keeps the last MAX_LOGS files (default 30).
LOGS_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOGS_DIR" 2>/dev/null || true
chmod 700 "$LOGS_DIR" 2>/dev/null || true
LOG_TS="$(date +%Y%m%d_%H%M%S)"
export RUN_TIMESTAMP="$LOG_TS"
LOG_FILE="$LOGS_DIR/update_all_${LOG_TS}.log"
MAX_LOGS="${MAC_UPDATE_MAX_LOGS:-30}"
case "$MAX_LOGS" in
    ''|*[!0-9]*|0)
        print_error "MAC_UPDATE_MAX_LOGS must be a positive integer (received: $MAX_LOGS)"
        rm -rf "$SESSION_DIR" 2>/dev/null || true
        exit 2
        ;;
esac

# Create the diagnostic log with private permissions before tee opens it.
# The directory is already mode 700, but an explicit 600 file mode also
# protects copied logs and non-standard umask configurations.
: > "$LOG_FILE" || {
    print_error "Cannot create run log: $LOG_FILE"
    rm -rf "$SESSION_DIR" 2>/dev/null || true
    exit 1
}
chmod 600 "$LOG_FILE" 2>/dev/null || {
    print_error "Cannot protect run log: $LOG_FILE"
    rm -f "$LOG_FILE" 2>/dev/null || true
    rm -rf "$SESSION_DIR" 2>/dev/null || true
    exit 1
}

# Rotate (lib/python/log_rotation.py): run logs keep the newest MAX_LOGS, run
# summaries at least 30 (the chronic-streak window reads them); stray summaries
# with non-timestamp names (e.g. run_summary_<epoch>.json) share that budget.
# run_summary_latest.json and version_history.tsv are never touched.
_keep_summaries=$((MAX_LOGS < 30 ? 30 : MAX_LOGS))
PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import sys
from log_rotation import rotate_logs
rotate_logs(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
' "$LOGS_DIR" "$MAX_LOGS" "$((_keep_summaries - 1))" 2>/dev/null || true

print_info "Run log: $LOG_FILE"

# ============================================================
# SUDO ACQUISITION — single decision point
# ============================================================
# Contract (2026-08-05 fix — "IDE prompted for Touch ID on every command"):
#
#   Exactly ONE place in this script may call an interactive `sudo`. It runs
#   at most once per invocation, and ONLY when all of the following hold:
#     1. a step that genuinely needs root will actually run (step 1 or step 6)
#     2. this is not a dry run (a preview must never ask for credentials)
#     3. stdin is a real TTY
#
#   Without a TTY we do NOT attempt `sudo -v`. A bare `sudo -v` in a non-TTY
#   context (IDE task runner, agent shell, launchd) escalates to the GUI
#   askpass/Touch ID dialog, which is why every command appeared to require
#   elevation. Instead we export MAC_UPDATE_NO_SUDO=1 so the child scripts
#   skip their root-only tracks and report soft (10) rather than failing.
#
#   Do NOT add a second sudo call anywhere. Do NOT reset SUDO_KEEPALIVE_PID
#   after the keep-alive has started — that orphans the refresher process and
#   leaves it running after the script exits.
SUDO_KEEPALIVE_PID=""

_needs_sudo=0
[ "${MAC_UPDATE_SKIP_APPSTORE:-0}" != "1" ] && _needs_sudo=1
[ "${MAC_UPDATE_SKIP_SYSTEM:-0}"   != "1" ] && _needs_sudo=1
[ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ] && _needs_sudo=0

if [ "$_needs_sudo" -eq 1 ] && [ ! -t 0 ]; then
    # No controlling terminal: never prompt. Tell the children to skip the
    # root-only tracks instead of failing on a password they cannot supply.
    export MAC_UPDATE_NO_SUDO=1
    print_info "$L_ALL_SUDO_NO_TTY"
    _needs_sudo=0
fi

if [ "$_needs_sudo" -eq 1 ]; then
    # Touch ID hint only where a prompt can actually appear.
    if [ -x "$SCRIPT_DIR/scripts/setup_touchid_sudo.sh" ] \
       && ! "$SCRIPT_DIR/scripts/setup_touchid_sudo.sh" --check >/dev/null 2>&1; then
        print_info "$L_ALL_TOUCHID_HINT"
    fi

    if sudo -n true 2>/dev/null; then
        : # timestamp already warm — do not prompt again
    elif [ "${MAC_UPDATE_JSON_SUMMARY:-0}" = "1" ]; then
        sudo -v 2>/dev/null || print_warn "$L_ALL_SUDO_PREAUTH_FAILED"
    else
        sudo -v || print_warn "$L_ALL_SUDO_PREAUTH_FAILED"
    fi

    # Keep the timestamp warm for the whole run. Started at most once; the PID
    # is killed in cleanup_session_dir() on every exit path including INT/TERM.
    # It also stops by itself as soon as this shell is gone, and after
    # MAC_UPDATE_SUDO_KEEPALIVE_MAX seconds (default 14400 = 4 h, clamped
    # 300-14400): a run that sat 51 minutes on an unanswered question must not
    # keep refreshing root credentials forever, yet update_system.sh uses
    # `sudo -n` per label at the end of a long run and needs a warm timestamp.
    _ka_max="${MAC_UPDATE_SUDO_KEEPALIVE_MAX:-14400}"
    case "$_ka_max" in
        ''|*[!0-9]*) _ka_max=14400 ;;
    esac
    [ "$_ka_max" -lt 300 ] && _ka_max=300
    [ "$_ka_max" -gt 14400 ] && _ka_max=14400
    if [ "${MAC_UPDATE_NO_SUDO_KEEPALIVE:-0}" != "1" ] && sudo -n true 2>/dev/null; then
        (
            _macupd_sleep_pid=""
            _macupd_parent=$$
            _macupd_deadline=$(( $(date +%s) + _ka_max ))
            trap '[ -n "$_macupd_sleep_pid" ] && kill "$_macupd_sleep_pid" 2>/dev/null; exit 0' INT TERM
            while true; do
                [ "$(date +%s)" -lt "$_macupd_deadline" ] || exit 0
                kill -0 "$_macupd_parent" 2>/dev/null || exit 0
                sudo -n true 2>/dev/null || exit 0
                sleep 50 &
                _macupd_sleep_pid=$!
                wait "$_macupd_sleep_pid" 2>/dev/null || exit 0
            done
        ) &
        SUDO_KEEPALIVE_PID=$!
    fi
fi

# Tee everything from this point to the log file. Note: this MUST come
# AFTER the interactive confirmation read above (tee on FD 0 is fine but
# we already consumed user input).
exec 3>&1 4>&2
if command -v perl >/dev/null 2>&1; then
    exec > >(log_strip_ansi_tee "$LOG_FILE") 2>&1
else
    # No perl: keep the log, colours included, rather than lose it.
    exec > >(tee -a "$LOG_FILE") 2>&1
fi
TEE_PID=$!
CAFFEINATE_PID=""

cleanup_session_dir() {
    # Kill sudo keep-alive first (BUG-3 fix) — must run on all exit paths
    # including INT/TERM to prevent orphaned sudo refresh processes.
    if [ -n "${SUDO_KEEPALIVE_PID:-}" ]; then
        kill "$SUDO_KEEPALIVE_PID" 2>/dev/null || true
        wait "$SUDO_KEEPALIVE_PID" 2>/dev/null || true
        SUDO_KEEPALIVE_PID=""
    fi
    # caffeinate -w $$ ends with this shell anyway; stop it now so it cannot
    # hold the log pipe open while we wait for the log filter to drain.
    if [ -n "${CAFFEINATE_PID:-}" ]; then
        kill "$CAFFEINATE_PID" 2>/dev/null || true
        CAFFEINATE_PID=""
    fi
    if [ "${MAC_UPDATE_SUMMARY_DONE:-0}" != "1" ] && [ -n "${START_TIME:-}" ] && [ -n "${SESSION_DIR:-}" ]; then
        write_machine_summary interrupted || true
    fi
    mac_update_lock_release "$SCRIPT_DIR"
    if [ "${MAC_UPDATE_JSON_SUMMARY:-0}" = "1" ]; then
        python3 - <<'PYJSON' 2>/dev/null || true
import json, os
print(json.dumps({
    "exit_code": int(os.environ.get("MAC_UPDATE_OVERALL_EXIT", "0")),
    # blocked_system is true only when a hard failure deferred the macOS step;
    # degraded is true when a soft warning was surfaced without blocking it.
    "blocked_system": os.environ.get("MAC_UPDATE_BLOCKING_EXIT", "0") != "0",
    "degraded": os.environ.get("MAC_UPDATE_DEGRADED", "0") != "0",
    "duration_sec": int(os.environ.get("MAC_UPDATE_DURATION_SEC", "0")),
    "dry_run": os.environ.get("MAC_UPDATE_DRY_RUN", "0") == "1",
    "results": {
        "prescan": os.environ.get("MAC_UPDATE_RESULT_SCAN", ""),
        "system": os.environ.get("MAC_UPDATE_RESULT_SYSTEM", ""),
        "appstore": os.environ.get("MAC_UPDATE_RESULT_APPSTORE", ""),
        "npm": os.environ.get("MAC_UPDATE_RESULT_NPMCLI", ""),
        "brew": os.environ.get("MAC_UPDATE_RESULT_BREW", ""),
        "internet": os.environ.get("MAC_UPDATE_RESULT_INTERNET", ""),
        "postupdate": os.environ.get("MAC_UPDATE_RESULT_MD", ""),
    },
    "log_file": os.environ.get("MAC_UPDATE_LOG_FILE", ""),
}, indent=2))
PYJSON
    fi
    # If we failed or finished degraded, dump session dir snapshots into the run
    # log before wipe. Full dump only when BLOCKING_EXIT!=0 or MAC_UPDATE_DEBUG=1.
    # On DEGRADED alone attach only *diag*.txt, *pending*.txt,
    # internet_status_codes.txt, brew_orphan_casks.txt.
    if [ -d "${SESSION_DIR:-/nonexistent}" ]; then
        if [ "${BLOCKING_EXIT:-0}" -ne 0 ] || [ "${MAC_UPDATE_DEBUG:-0}" = "1" ]; then
            {
                echo ""
                echo "=========================================="
                echo "SESSION DIR SNAPSHOTS (preserved on failure)"
                echo "Path: $SESSION_DIR"
                echo "=========================================="
                for f in "$SESSION_DIR"/*.txt "$SESSION_DIR"/appstore_diag.txt; do
                    [ -f "$f" ] || continue
                    echo ""
                    echo "--- ${f##*/} ---"
                    # Cap each snapshot at 200 lines to keep logs reasonable.
                    head -n 200 "$f" 2>/dev/null
                done
            } 2>/dev/null || true
        elif [ "${DEGRADED:-0}" -ne 0 ]; then
            {
                echo ""
                echo "=========================================="
                echo "SESSION DIR SNAPSHOTS (degraded run)"
                echo "Path: $SESSION_DIR"
                echo "=========================================="
                _seen_dumps=""
                for f in "$SESSION_DIR"/*diag*.txt "$SESSION_DIR"/*pending*.txt \
                         "$SESSION_DIR"/internet_status_codes.txt "$SESSION_DIR"/brew_orphan_casks.txt; do
                    [ -f "$f" ] || continue
                    fname="${f##*/}"
                    case " $_seen_dumps " in
                        *" $fname "*) continue ;;
                    esac
                    _seen_dumps="$_seen_dumps $fname"
                    echo ""
                    echo "--- $fname ---"
                    head -n 200 "$f" 2>/dev/null
                done
            } 2>/dev/null || true
        fi
    fi
    case "${SESSION_DIR:-}" in
        "${TMPDIR:-/tmp}"/mac_update.*|/tmp/mac_update.*)
            rm -rf "$SESSION_DIR" 2>/dev/null || true
            ;;
    esac
    exec 1>&3 2>&4
    [ -n "${TEE_PID:-}" ] && wait "$TEE_PID" 2>/dev/null || true
}
trap cleanup_session_dir EXIT
trap 'cleanup_session_dir; exit 130' INT TERM

if ! mac_update_lock_acquire "$SCRIPT_DIR"; then
    exit 1
fi
export MAC_UPDATE_RUN_ID="${MAC_UPDATE_RUN_ID:-$(python3 -c 'import uuid; print(uuid.uuid4())' 2>/dev/null || echo "run-$LOG_TS")}"
write_machine_summary started || true

# ============================================================
# Track wyników
# ============================================================
RESULT_SCAN="$L_ALL_RESULT_SKIPPED"
RESULT_SYSTEM="$L_ALL_RESULT_SKIPPED"
RESULT_APPSTORE="$L_ALL_RESULT_SKIPPED"
RESULT_INTERNET="$L_ALL_RESULT_SKIPPED"
RESULT_NPMCLI="$L_ALL_RESULT_SKIPPED"
RESULT_BREW="$L_ALL_RESULT_SKIPPED"
RESULT_MD="$L_ALL_RESULT_SKIPPED"
STATUS_CODE_SCAN="skipped"
STATUS_CODE_SYSTEM="skipped"
STATUS_CODE_APPSTORE="skipped"
STATUS_CODE_INTERNET="skipped"
STATUS_CODE_NPMCLI="skipped"
STATUS_CODE_BREW="skipped"
STATUS_CODE_MD="skipped"
SYSTEM_HISTORY_PENDING="⏳ pending final step"
SYSTEM_DEFERRED=0

# ============================================================
# STEP SEVERITY CONTRACT (child exit code → orchestrator meaning)
# ============================================================
# Child update_*.sh scripts report severity through their exit status:
#
#   0   clean          — everything the step manages is verified up to date.
#   10  soft/degraded  — the step ran, mutated nothing dangerous, but could not
#                        VERIFY something (offline, a vendor updater did not
#                        answer, an app refused to launch). This is the normal
#                        healthy state for Sparkle/Electron self-updaters.
#   1   hard failure   — a real operational failure: a download or install
#                        actually broke, or a package manager / inventory write
#                        may have been left mid-transaction.
#   127 missing script — treated as a hard failure.
#
# Three orchestrator-level flags, deliberately kept separate:
#
#   OVERALL_EXIT  process exit status + "COMPLETED WITH ERRORS" banner. Only
#                 hard failures set it. Soft/degraded results do NOT, because a
#                 run where 24 self-updating apps are merely "launched
#                 (unverified)" is this project's normal healthy outcome and
#                 must not look like a failed run to cron/CI/dev_sync.
#   DEGRADED      at least one soft warning. Drives the third reporting state
#                 ("COMPLETED WITH WARNINGS") so warnings are never hidden.
#   BLOCKING_EXIT the ONLY flag allowed to defer the final macOS step (6).
#
# Blocking matrix — which hard failures may defer macOS system updates:
#   step 0 prescan     NOT blocking  — read-only scan, mutates nothing.
#   step 1 App Store   blocking      — sudo mas upgrade can stop mid-install.
#   step 2 CLI + npm   blocking      — can leave npm/bun mid-transaction.
#   step 3 Homebrew    blocking      — can leave a keg/cask mid-transaction.
#   step 4 internet    blocking ONLY on hard failure (bundle swap can be left
#                      mid-replacement). A SOFT result NEVER blocks — this is
#                      the 2026-07-26 regression: a misdetected Microsoft
#                      AutoUpdate check suppressed macOS security updates.
#   step 5 inventory   NOT blocking  — reporting only, mutates nothing; a failure
#                      still sets OVERALL_EXIT=1 but never defers macOS updates.
#   step 6 system      n/a           — nothing runs after it.
#
# Rationale: only a failure that can leave the machine mid-mutation, or that a
# reboot could make worse, earns the right to postpone macOS security updates.
MAC_UPDATE_SOFT_EXIT=10
OVERALL_EXIT=0
BLOCKING_EXIT=0
DEGRADED=0

# ============================================================
# VERIFY-ONLY MODE (--verify-only)
# ============================================================
if [ "${MAC_UPDATE_VERIFY_ONLY:-0}" = "1" ]; then
    step_header 0 0 "Verification of Installed Application Versions (--verify-only)"
    print_info "Capturing current application versions..."
    if ! internet_capture_versions "$SESSION_DIR/internet_verify.txt"; then
        print_error "Failed to capture current application versions"
        exit 1
    fi

    python3 -c '
import os, sys

script_dir = sys.argv[1]
session_dir = sys.argv[2]
history_file = os.path.join(script_dir, "logs", "version_history.tsv")
verify_file = os.path.join(session_dir, "internet_verify.txt")

current = {}
if os.path.isfile(verify_file):
    with open(verify_file, "r", encoding="utf-8") as f:
        for line in f:
            if "|" in line:
                name, ver = line.strip().split("|", 1)
                current[name] = ver

history = {}
if os.path.isfile(history_file):
    with open(history_file, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 3:
                history[parts[1]] = parts[2]

header_app = "Application"
header_rec = "Recorded Version"
header_cur = "Current Version"
dash_char = "-"

print("\n" + "=" * 70)
print(f"{header_app:<30} | {header_rec:<18} | {header_cur:<18}")
print("-" * 70)

unverified = 0
for app, curr_ver in sorted(current.items()):
    hist_ver = history.get(app, dash_char)
    if curr_ver == "?" or curr_ver == "unknown":
        status = "⏳ unverified"
        unverified += 1
    elif hist_ver != dash_char and hist_ver != curr_ver:
        status = f"🚀 updated ({hist_ver} -> {curr_ver})"
    else:
        status = f"✅ verified ({curr_ver})"
    print(f"{app:<30} | {hist_ver:<18} | {curr_ver:<18} | {status}")

print("=" * 70)
print(f"Total checked: {len(current)} | Unverified: {unverified}")
if unverified > 0:
    sys.exit(10)
sys.exit(0)
' "$SCRIPT_DIR" "$SESSION_DIR"
    _verify_rc=$?
    if [ "$_verify_rc" -eq 10 ]; then
        print_warn "Verification completed with soft unverified apps (exit 10)"
        exit 10
    elif [ "$_verify_rc" -ne 0 ]; then
        print_error "Verification failed (exit 1)"
        exit 1
    else
        print_ok "All application versions verified successfully"
        exit 0
    fi
fi

# ============================================================
# PRE-FLIGHT (real runs only): cheap read-only checks before any step
# ============================================================
# Policy (lib/preflight.sh): low free disk => degraded run; battery below
# MAC_UPDATE_MIN_BATTERY with the macOS step enabled => that step is skipped
# softly; no network at all => abort here with exit 1 before anything runs.
# Dry runs and the inventory-only path (build_inventory.sh) skip all of it.
if [ "${MAC_UPDATE_DRY_RUN:-0}" != "1" ] && [ "${MAC_UPDATE_INVENTORY_ONLY:-0}" != "1" ]; then
    if ! preflight_run_cheap; then
        OVERALL_EXIT=1
        exit 1
    fi
    [ "${PREFLIGHT_DEGRADED:-0}" = "1" ] && DEGRADED=1
    # Keep the Mac awake for the whole run. Started outside the sudo block on
    # purpose (it has nothing to do with the sudo keep-alive rules), detached
    # from the log pipe, and bound to this shell with -w so it cannot outlive it.
    if [ "${MAC_UPDATE_NO_CAFFEINATE:-0}" != "1" ] && command -v caffeinate >/dev/null 2>&1; then
        caffeinate -i -w $$ </dev/null >/dev/null 2>&1 &
        CAFFEINATE_PID=$!
        print_info "$L_PREFLIGHT_AWAKE"
    fi
fi

# ============================================================
# STEP 0: Local structured inventory (prepared before first consent)
# ============================================================
ui_master_progress 0 6
if [ "${MAC_UPDATE_SKIP_PRESCAN:-0}" = "1" ]; then
    RESULT_SCAN="$L_ALL_RESULT_SKIPPED"
    STATUS_CODE_SCAN="skipped"
elif [ "${PLAN_PREPARE_EXIT:-10}" -eq 0 ]; then
    RESULT_SCAN="$L_ALL_RESULT_OK"
    STATUS_CODE_SCAN="ok"
else
    RESULT_SCAN="$L_ALL_RESULT_WARN"
    STATUS_CODE_SCAN="warn"
    DEGRADED=1
fi

# ============================================================
# Prepare the final system update. It is deliberately not presented as an
# early step: a framework-managed reboot must not interrupt application work.
# ============================================================
if [ "${MAC_UPDATE_SKIP_SYSTEM:-0}" = "1" ]; then
    print_info "Skipped final macOS step (--skip-system)"
    RESULT_SYSTEM="$L_ALL_RESULT_SKIPPED"
    STATUS_CODE_SYSTEM="skipped"
elif [ "${PREFLIGHT_SKIP_SYSTEM:-0}" = "1" ]; then
    # Pre-flight found the battery below MAC_UPDATE_MIN_BATTERY (it already
    # printed why and marked the run degraded). Only this step is skipped.
    RESULT_SYSTEM="$L_ALL_SYSTEM_SKIPPED_BATTERY"
    STATUS_CODE_SYSTEM="skipped"
else
    SYSTEM_DEFERRED=1
    if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
        RESULT_SYSTEM="[DRY-RUN] pending final step"
        STATUS_CODE_SYSTEM="skipped"
    else
        RESULT_SYSTEM="$SYSTEM_HISTORY_PENDING"
        STATUS_CODE_SYSTEM="unconfirmed"
    fi
fi

# ============================================================
# STEP 1: App Store update
# ============================================================
ui_master_progress 1 6
if [ "${MAC_UPDATE_SKIP_APPSTORE:-0}" = "1" ]; then
    print_info "Skipped step 1 (--skip-appstore)"
    RESULT_APPSTORE="$L_ALL_RESULT_SKIPPED"
    STATUS_CODE_APPSTORE="skipped"
else
step_header 1 6 "$L_SCRIPT_TITLE_APPSTORE"
step_timer_start

if [ -f "$SCRIPT_DIR/update_appstore.sh" ]; then
    chmod +x "$SCRIPT_DIR/update_appstore.sh"
    APPSTORE_EXIT=0
    if mac_update_dry_run_msg "update_appstore.sh"; then
        RESULT_APPSTORE="[DRY-RUN] skipped"
        STATUS_CODE_APPSTORE="skipped"
    elif bash "$SCRIPT_DIR/update_appstore.sh"; then
        RESULT_APPSTORE="$L_ALL_RESULT_OK"
        STATUS_CODE_APPSTORE="ok"
    else
        APPSTORE_EXIT=$?
        if [ "$APPSTORE_EXIT" -eq 2 ] && [ "${MAC_UPDATE_TREAT_APPSTORE_AX_AS_WARNING:-0}" = "1" ]; then
            RESULT_APPSTORE="⚠️  $L_ALL_RESULT_AX_REQUIRED"
            STATUS_CODE_APPSTORE="warn"
            DEGRADED=1
            print_warn "App Store exit 2 (Accessibility) treated as warning"
        elif [ "$APPSTORE_EXIT" -eq "$MAC_UPDATE_SOFT_EXIT" ]; then
            RESULT_APPSTORE="⚠️  ${L_ALL_RESULT_DEGRADED:-completed with warnings}"
            STATUS_CODE_APPSTORE="warn"
            DEGRADED=1
            print_warn "$(printf "$L_ALL_STEP_SOFT_WARNINGS_FMT" "App Store")"
        else
            RESULT_APPSTORE="$L_STATUS_ERROR"
            STATUS_CODE_APPSTORE="error"
            OVERALL_EXIT=1
            BLOCKING_EXIT=1
        fi
    fi
else
    print_error "File not found: update_appstore.sh"
    RESULT_APPSTORE="$L_STATUS_ERROR: $L_ALL_RESULT_MISSING_FILE"
    STATUS_CODE_APPSTORE="error"
    OVERALL_EXIT=1
    BLOCKING_EXIT=1
fi
step_timer_stop appstore
fi

# ============================================================
# STEP 2: Native CLI & npm update
# ============================================================
ui_master_progress 2 6
# The previous child may have changed what is installed (Homebrew can drop
# python3/node links); forget cached command paths before the next step.
hash -r 2>/dev/null || true
if [ "${MAC_UPDATE_SKIP_NPM:-0}" = "1" ]; then
    print_info "Skipped step 2 (--skip-npm)"
    RESULT_NPMCLI="$L_ALL_RESULT_SKIPPED"
    STATUS_CODE_NPMCLI="skipped"
else
step_header 2 6 "Native CLI + npm"
step_timer_start
if mac_update_dry_run_msg "update_npm_cli.sh"; then
    RESULT_NPMCLI="[DRY-RUN] skipped"
    STATUS_CODE_NPMCLI="skipped"
elif mac_update_run_child "update_npm_cli.sh" "update_npm_cli.sh"; then
    RESULT_NPMCLI="$L_ALL_RESULT_OK"
    STATUS_CODE_NPMCLI="ok"
else
    # mac_update_run_child ends with `bash <child>`, so the child's exit status
    # reaches us unchanged and 10 stays distinguishable from 1 / 127.
    NPMCLI_EXIT=$?
    if [ "$NPMCLI_EXIT" -eq "$MAC_UPDATE_SOFT_EXIT" ]; then
        RESULT_NPMCLI="⚠️  ${L_ALL_RESULT_DEGRADED:-completed with warnings}"
        STATUS_CODE_NPMCLI="warn"
        DEGRADED=1
        print_warn "$(printf "$L_ALL_STEP_SOFT_WARNINGS_FMT" "Native CLI + npm")"
    else
        RESULT_NPMCLI="$L_STATUS_ERROR"
        STATUS_CODE_NPMCLI="error"
        OVERALL_EXIT=1
        BLOCKING_EXIT=1
    fi
fi
step_timer_stop npmcli
fi

# ============================================================
# STEP 3: Homebrew update
# ============================================================
ui_master_progress 3 6
# The previous child may have changed what is installed (Homebrew can drop
# python3/node links); forget cached command paths before the next step.
hash -r 2>/dev/null || true
if [ "${MAC_UPDATE_SKIP_BREW:-0}" = "1" ]; then
    print_info "Skipped step 3 (--skip-brew)"
    RESULT_BREW="$L_ALL_RESULT_SKIPPED"
    STATUS_CODE_BREW="skipped"
else
step_header 3 6 "$L_SCRIPT_TITLE_BREW"
step_timer_start

if mac_update_dry_run_msg "update_brew.sh"; then
    RESULT_BREW="[DRY-RUN] skipped"
    STATUS_CODE_BREW="skipped"
elif [ -f "$SCRIPT_DIR/update_brew.sh" ]; then
    chmod +x "$SCRIPT_DIR/update_brew.sh"
    if bash "$SCRIPT_DIR/update_brew.sh"; then
        RESULT_BREW="$L_ALL_RESULT_OK"
        STATUS_CODE_BREW="ok"
    else
        BREW_EXIT=$?
        if [ "$BREW_EXIT" -eq "$MAC_UPDATE_SOFT_EXIT" ]; then
            RESULT_BREW="⚠️  ${L_ALL_RESULT_DEGRADED:-completed with warnings}"
            STATUS_CODE_BREW="warn"
            DEGRADED=1
            print_warn "$(printf "$L_ALL_STEP_SOFT_WARNINGS_FMT" "Homebrew")"
        else
            RESULT_BREW="$L_STATUS_ERROR"
            STATUS_CODE_BREW="error"
            OVERALL_EXIT=1
            BLOCKING_EXIT=1
        fi
    fi
else
    print_error "File not found: update_brew.sh"
    RESULT_BREW="$L_STATUS_ERROR: $L_ALL_RESULT_MISSING_FILE"
    STATUS_CODE_BREW="error"
    OVERALL_EXIT=1
    BLOCKING_EXIT=1
fi
step_timer_stop brew
fi

# ============================================================
# STEP 4: Internet-downloaded apps update
# ============================================================
ui_master_progress 4 6
# The previous child may have changed what is installed (Homebrew can drop
# python3/node links); forget cached command paths before the next step.
hash -r 2>/dev/null || true
if [ "${MAC_UPDATE_SKIP_INTERNET:-0}" = "1" ]; then
    print_info "Skipped step 4 (--skip-internet)"
    RESULT_INTERNET="$L_ALL_RESULT_SKIPPED"
    STATUS_CODE_INTERNET="skipped"
else
step_header 4 6 "$L_SCRIPT_TITLE_INTERNET"
step_timer_start

if mac_update_dry_run_msg "update_internet_apps.sh"; then
    RESULT_INTERNET="[DRY-RUN] skipped"
    STATUS_CODE_INTERNET="skipped"
elif [ -f "$SCRIPT_DIR/update_internet_apps.sh" ]; then
    chmod +x "$SCRIPT_DIR/update_internet_apps.sh"
    if bash "$SCRIPT_DIR/update_internet_apps.sh"; then
        RESULT_INTERNET="$L_ALL_RESULT_OK"
        STATUS_CODE_INTERNET="ok"
    else
        INTERNET_EXIT=$?
        # A soft result means "could not verify" — offline, a vendor updater did
        # not answer, an app refused to launch. Nothing is mid-mutation, so it
        # must never postpone macOS security updates (2026-07-26 regression).
        if [ "$INTERNET_EXIT" -eq "$MAC_UPDATE_SOFT_EXIT" ]; then
            RESULT_INTERNET="⚠️  ${L_ALL_RESULT_DEGRADED:-completed with warnings}"
            STATUS_CODE_INTERNET="warn"
            DEGRADED=1
            print_warn "$(printf "$L_ALL_STEP_SOFT_WARNINGS_FMT" "$L_ALL_STEP_INTERNET_NAME")"
        else
            RESULT_INTERNET="$L_STATUS_ERROR"
            STATUS_CODE_INTERNET="error"
            OVERALL_EXIT=1
            BLOCKING_EXIT=1
        fi
    fi
else
    print_error "File not found: update_internet_apps.sh"
    RESULT_INTERNET="$L_STATUS_ERROR: $L_ALL_RESULT_MISSING_FILE"
    STATUS_CODE_INTERNET="error"
    OVERALL_EXIT=1
    BLOCKING_EXIT=1
fi
step_timer_stop internet
fi

# ============================================================
# STEP 5: Reobserve and transactionally render local inventory
# ============================================================
ui_master_progress 5 6
hash -r 2>/dev/null || true
if [ "${MAC_UPDATE_SKIP_POSTUPDATE:-0}" = "1" ]; then
    RESULT_MD="$L_ALL_RESULT_SKIPPED"
    STATUS_CODE_MD="skipped"
else
    step_header 5 6 "$L_ALL_STEP5_DESC"
    step_timer_start
    if PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import sys
from plan_orchestration import main
sys.exit(main(sys.argv[1], "refresh"))' "$SCRIPT_DIR"; then
        RESULT_MD="$L_ALL_RESULT_OK"
        STATUS_CODE_MD="ok"
    else
        RESULT_MD="$L_ALL_RESULT_WARN"
        STATUS_CODE_MD="warn"
        DEGRADED=1
    fi
    step_timer_stop postupdate
fi

# ============================================================
# FINAL MUTATING STEP: macOS system update
# ============================================================
if [ "$SYSTEM_DEFERRED" -eq 1 ]; then
    ui_master_progress 6 6
    step_header 6 6 "$L_SYSTEM_UPDATE_TITLE"
    step_timer_start
    if mac_update_dry_run_msg "update_system.sh (final step)"; then
        RESULT_SYSTEM="[DRY-RUN] skipped"
        STATUS_CODE_SYSTEM="skipped"
    elif [ "$BLOCKING_EXIT" -ne 0 ]; then
        # Only a blocking hard failure may defer macOS updates. Soft/degraded
        # results (exit 10) never reach this branch — see the severity contract.
        RESULT_SYSTEM="${L_ALL_SYSTEM_DEFERRED:-⏭️ skipped because a blocking update step failed}"
        STATUS_CODE_SYSTEM="skipped"
        print_warn "Skipping the final macOS update because a blocking step failed (the machine may be mid-transaction); fix it and rerun."
    elif mac_update_run_child "update_system.sh" "update_system.sh (final step)"; then
        RESULT_SYSTEM="$L_ALL_RESULT_OK"
        STATUS_CODE_SYSTEM="ok"
    else
        SYS_EXIT=$?
        if [ "$SYS_EXIT" -eq "${MAC_UPDATE_SOFT_EXIT:-10}" ]; then
            if [ -f "$SESSION_DIR/system_skipped_by_user" ]; then
                if [ -f "$SESSION_DIR/system_prompt_timeout" ]; then
                    RESULT_SYSTEM="${L_ALL_RESULT_SKIPPED_NO_ANSWER:-skipped: no answer}"
                else
                    RESULT_SYSTEM="${L_ALL_RESULT_SKIPPED_BY_USER:-pominięte przez użytkownika}"
                fi
                STATUS_CODE_SYSTEM="skipped_by_user"
            else
                RESULT_SYSTEM="⚠️  ${L_ALL_RESULT_DEGRADED:-completed with warnings}"
                STATUS_CODE_SYSTEM="warn"
                DEGRADED=1
            fi
        else
            RESULT_SYSTEM="$L_STATUS_ERROR"
            STATUS_CODE_SYSTEM="error"
            OVERALL_EXIT=1
        fi
    fi

    step_timer_stop system

    # Postupdate runs before the reboot-capable system step. If softwareupdate
    # returns normally, replace the pending marker in the newest history entry.
    if [ -f "$SCRIPT_DIR/UPDATES.md" ] && [ "${STATUS_CODE_MD:-}" = "ok" ]; then
        if ! python3 - "$SCRIPT_DIR/UPDATES.md" "$SYSTEM_HISTORY_PENDING" "$RESULT_SYSTEM" <<'PYEOF'
import os
import sys
import tempfile

path, pending, result = sys.argv[1:4]
with open(path, encoding='utf-8') as handle:
    content = handle.read()
old = f"| 🍎 System macOS | {pending} |"
new = f"| 🍎 System macOS | {result} |"
if old in content:
    content = content.replace(old, new, 1)
    fd, temp_path = tempfile.mkstemp(prefix='.mac-update.', dir=os.path.dirname(path), text=True)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        os.chmod(path, 0o600)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
PYEOF
        then
            # Non-blocking by construction: nothing runs after the system step.
            print_error "Could not finalize the macOS result in UPDATES.md."
            OVERALL_EXIT=1
        fi
    fi
fi

ui_master_progress 6 6

# ============================================================
# Final summary
# ============================================================
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
# Use DURATION_SECS instead of SECONDS — SECONDS is a bash built-in that
# auto-increments and would be clobbered by this assignment on some shells.
DURATION_SECS=$((DURATION % 60))

echo ""
# Three honest reporting states: clean / completed-with-warnings / failed.
# The inventory-only path (build_inventory.sh) updates nothing, so it never
# says "ALL UPDATES COMPLETE" — it has its own banners.
_summary_msg="$L_UPDATE_ALL_SUCCESS"
if [ "${MAC_UPDATE_INVENTORY_ONLY:-0}" = "1" ]; then
    _summary_msg="$L_ALL_INVENTORY_BANNER"
    if [ "$OVERALL_EXIT" -ne 0 ]; then
        _summary_msg="$L_ALL_INVENTORY_BANNER_ERROR"
    elif [ "$DEGRADED" -ne 0 ]; then
        _summary_msg="$L_ALL_INVENTORY_BANNER_WARN"
    fi
elif [ "$OVERALL_EXIT" -ne 0 ]; then
    _summary_msg="${L_ALL_SUMMARY_ERROR:-UPDATE COMPLETED WITH ERRORS}"
elif [ "$DEGRADED" -ne 0 ]; then
    _summary_msg="${L_ALL_SUMMARY_WARN:-UPDATE COMPLETED WITH WARNINGS}"
fi
ui_print_box "$_summary_msg"
echo ""
printf '  %-26s %s%s\n' "$L_ALL_LABEL_SCAN" "$RESULT_SCAN" "$(step_duration_suffix prescan)"
printf '  %-26s %s%s\n' "$L_ALL_LABEL_APPSTORE" "$RESULT_APPSTORE" "$(step_duration_suffix appstore)"
printf '  %-26s %s%s\n' "$L_ALL_LABEL_NPMCLI" "$RESULT_NPMCLI" "$(step_duration_suffix npmcli)"
printf '  %-26s %s%s\n' "$L_ALL_LABEL_BREW" "$RESULT_BREW" "$(step_duration_suffix brew)"
printf '  %-26s %s%s\n' "$L_ALL_LABEL_INTERNET" "$RESULT_INTERNET" "$(step_duration_suffix internet)"
printf '  5. %-23s %s%s\n' "$L_ALL_UPDATE_APPS_LABEL" "$RESULT_MD" "$(step_duration_suffix postupdate)"
printf '  %-26s %s%s\n' "$L_ALL_LABEL_SYSTEM" "$RESULT_SYSTEM" "$(step_duration_suffix system)"
echo ""
echo -e "  $(printf "$L_ALL_DURATION_FMT" "$MINUTES" "$DURATION_SECS")"
echo ""
if [ "$OVERALL_EXIT" -ne 0 ]; then
    print_error "One or more update steps failed. Review the step summary above and session logs before rerunning."
elif [ "$DEGRADED" -ne 0 ]; then
    # Distinguish "only informational warnings (e.g. a stale manufacturer feed)" from
    # "something could not be verified / is still pending".
    save_step_status_codes || true
    if [ -n "${SESSION_DIR:-}" ] && PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" \
        python3 -c 'import sys; from run_summary import degraded_is_warnings_only as f; sys.exit(0 if f(sys.argv[1]) else 1)' "$SESSION_DIR" 2>/dev/null; then
        print_warn "$L_ALL_WARNINGS_ONLY"
    else
        print_warn "${L_ALL_WARN_NOT_BLOCKING:-Some updates could not be verified. This did not block the macOS system update.}"
    fi
elif [ "${MAC_UPDATE_INVENTORY_ONLY:-0}" = "1" ]; then
    print_ok "$L_ALL_INVENTORY_BANNER"
else
    print_ok "$L_UPDATE_ALL_SUCCESS"
fi
if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
    print_info "DRY-RUN: no applications, inventory, or history files were changed."
elif [ "${STATUS_CODE_MD:-}" = "ok" ]; then
    # Only claim written files when step 5 really succeeded (a skipped or
    # failed inventory step must not be reported as having updated them).
    if [ "${MAC_UPDATE_INVENTORY_ONLY:-0}" = "1" ]; then
        # Real numbers from step 5 (inventory_counts.txt: changed added removed).
        _inv_changed=0; _inv_added=0; _inv_removed=0
        if [ -f "$SESSION_DIR/inventory_counts.txt" ]; then
            read -r _inv_changed _inv_added _inv_removed < "$SESSION_DIR/inventory_counts.txt" || true
        fi
        print_info "$(printf "$L_ALL_INVENTORY_DONE_FMT" "${_inv_changed:-0}" "${_inv_added:-0}" "${_inv_removed:-0}")"
    else
        print_info "$L_ALL_FILES_UPDATED_MSG"
    fi
fi
if [ "${MAC_UPDATE_INVENTORY_ONLY:-0}" != "1" ]; then
    print_info "$L_ALL_RESTART_CHECK_MSG"
fi
echo ""

export MAC_UPDATE_OVERALL_EXIT="$OVERALL_EXIT"
export MAC_UPDATE_BLOCKING_EXIT="$BLOCKING_EXIT"
export MAC_UPDATE_DEGRADED="$DEGRADED"
export MAC_UPDATE_DURATION_SEC="$DURATION"
export MAC_UPDATE_RESULT_SCAN="$RESULT_SCAN"
export MAC_UPDATE_RESULT_SYSTEM="$RESULT_SYSTEM"
export MAC_UPDATE_RESULT_APPSTORE="$RESULT_APPSTORE"
export MAC_UPDATE_RESULT_INTERNET="$RESULT_INTERNET"
export MAC_UPDATE_RESULT_NPMCLI="$RESULT_NPMCLI"
export MAC_UPDATE_RESULT_BREW="$RESULT_BREW"
export MAC_UPDATE_RESULT_MD="$RESULT_MD"
export MAC_UPDATE_LOG_FILE="$LOG_FILE"
export RUN_TIMESTAMP="${RUN_TIMESTAMP:-$LOG_TS}"

if ! write_machine_summary completed; then
    print_error "Could not write run_summary JSON (see the run_summary line above for the cause)"
    mark_stale_summary_failed
    OVERALL_EXIT=1
fi


bash "$SCRIPT_DIR/scripts/report_chronic_warnings.sh" || true

_ui_summary="$(printf '%s %s\n' \
    "$L_ALL_LABEL_SCAN" "$RESULT_SCAN$(step_duration_suffix prescan)" \
    "$L_ALL_LABEL_APPSTORE" "$RESULT_APPSTORE$(step_duration_suffix appstore)" \
    "$L_ALL_LABEL_NPMCLI" "$RESULT_NPMCLI$(step_duration_suffix npmcli)" \
    "$L_ALL_LABEL_BREW" "$RESULT_BREW$(step_duration_suffix brew)" \
    "$L_ALL_LABEL_INTERNET" "$RESULT_INTERNET$(step_duration_suffix internet)" \
    "5. $L_ALL_UPDATE_APPS_LABEL" "$RESULT_MD$(step_duration_suffix postupdate)" \
    "$L_ALL_LABEL_SYSTEM" "$RESULT_SYSTEM$(step_duration_suffix system)"
    printf '%s\n' "$(printf "$L_ALL_DURATION_FMT" "$MINUTES" "$DURATION_SECS")")"
ui_summary_table "$_ui_summary"

if [ "${MAC_UPDATE_NOTIFY:-0}" = "1" ]; then
    if command -v osascript >/dev/null 2>&1; then
        _notif_status="SUCCESS"
        [ "$DEGRADED" -ne 0 ] && _notif_status="WARNINGS"
        [ "$OVERALL_EXIT" -ne 0 ] && _notif_status="ERRORS"
        _notif_body="Duration: ${MINUTES}m ${DURATION_SECS}s. Status: ${_notif_status}"
        osascript -e "display notification \"${_notif_body}\" with title \"macOS Updates\" subtitle \"${_summary_msg}\"" 2>/dev/null || true
    fi
fi

exit "$OVERALL_EXIT"
