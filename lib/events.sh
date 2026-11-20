#!/usr/bin/env bash
# lib/events.sh — optional JSON-lines event channel for user interfaces.
#
#   mu_event <type> key=value ... key:=<json> ...
#
# When MAC_UPDATE_EVENT_FILE is set, one JSON object per call is appended to
# that file (keys: ts, type, run_id when MAC_UPDATE_RUN_ID is set, then the
# fields). "key=value" is always a JSON string; "key:=value" is parsed as JSON
# (numbers, arrays, null). When the variable is unset nothing happens. The
# channel never writes to stdout/stderr and never changes an exit status.
# Bash 3.2 compatible. JSON encoding is done by lib/python/mu_events.py, so
# arbitrary app names (quotes, backslashes, newlines, Unicode) stay valid.

_MU_EVENTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Item results are also kept in the session directory (item_events.jsonl), so
# the run summary carries the same ids, results and reasons as the UI saw.
_mu_events_wanted() {
    [ -n "${MAC_UPDATE_EVENT_FILE:-}" ] || { case "${1:-}" in item_start|item_end) [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] ;; *) false ;; esac; }
}

mu_event() {
    [ "$#" -ge 1 ] && [ -n "$1" ] || return 0
    _mu_events_wanted "$1" || return 0
    command -v python3 >/dev/null 2>&1 || return 0
    python3 "$_MU_EVENTS_DIR/python/mu_events.py" emit "${MAC_UPDATE_EVENT_FILE:-}" "$@" \
        </dev/null >/dev/null 2>&1 || true
    return 0
}

# mu_item_start <group> <id> [name] [from] [to] [source]
_MU_ITEMS_STARTED="|"
mu_item_start() {
    _mu_events_wanted item_start || return 0
    _MU_ITEMS_STARTED="${_MU_ITEMS_STARTED}$1/$2|"
    mu_event item_start "group=$1" "id=$2" "name=${3:-$2}" "from=${4:-}" "to=${5:-}" "source=${6:-}"
}

# mu_item_progress <group> <id> <checking|downloading|verifying|installing> [percent]
mu_item_progress() {
    [ -n "${MAC_UPDATE_EVENT_FILE:-}" ] || return 0
    if [ -n "${4:-}" ]; then
        mu_event item_progress "group=$1" "id=$2" "phase=$3" "percent:=$4"
    else
        mu_event item_progress "group=$1" "id=$2" "phase=$3"
    fi
}

# Reason codes understood by the terminal interface (tui_runner.REASON_CODES).
# preview_unchecked: a dry run could not check the item (result stays current).
MU_REASON_CODES="app_running signin_required needs_password needs_restart no_method checksum_mismatch download_failed feed_unreachable manual_mode major_upgrade_blocked disk_low battery_low timeout vendor_updater_opened still_installing updater_unconfirmed store_not_offered vendor_update_pending teams_via_own_updater requirement_missing preview_unchecked blocked_by_login_items unknown"

# mu_item_end <group> <id> <updated|available|current|needs_you|failed|skipped> [from] [to] [detail] [reason] [name] [handler_ended_at]
# handler_ended_at (UTC ISO 8601): when the item's handler returned, for items
# whose item_end is written later (provisional ones closed in the final pass);
# run_summary uses it instead of the item_end ts for the item's duration.
# "available" is the preview (dry-run) result: a real run would update the item.
# A needs_you or failed result without a known reason is reported as "unknown".
mu_item_end() {
    _mu_events_wanted item_end || return 0
    local reason="${7:-}"
    case "$3" in
        updated|available|current|needs_you|failed|skipped) ;;
        *) return 0 ;;
    esac
    # Every item_end has an item_start: paths that decide at once (user
    # overrides, battery, blocked major upgrades, already current) get one here.
    case "$_MU_ITEMS_STARTED" in
        *"|$1/$2|"*) ;;
        *) mu_item_start "$1" "$2" "${8:-$2}" "${4:-}" "${5:-}" ;;
    esac
    case " $MU_REASON_CODES " in *" $reason "*) ;; *) reason="" ;; esac
    if [ -z "$reason" ] && { [ "$3" = needs_you ] || [ "$3" = failed ]; }; then
        reason=unknown
    fi
    if [ -n "${9:-}" ]; then
        mu_event item_end "group=$1" "id=$2" "result=$3" "from=${4:-}" "to=${5:-}" "detail=${6:-}" "reason=$reason" "name=${8:-}" "handler_ended_at=$9"
    else
        mu_event item_end "group=$1" "id=$2" "result=$3" "from=${4:-}" "to=${5:-}" "detail=${6:-}" "reason=$reason" "name=${8:-}"
    fi
}

# mu_group_total <group> <total>
mu_group_total() {
    [ -n "${MAC_UPDATE_EVENT_FILE:-}" ] || return 0
    case "${2:-}" in ''|*[!0-9]*) return 0 ;; esac
    mu_event group_total "group=$1" "total:=$2"
}

# mu_group_checked <group> <count> — how many things the step looked at when
# only some of them get an item row (Homebrew formulae: only outdated ones are
# itemised). mu_group_end carries the latest value as "checked".
mu_group_checked() {
    [ -n "${MAC_UPDATE_EVENT_FILE:-}" ] || return 0
    case "${2:-}" in ''|*[!0-9]*) return 0 ;; esac
    mu_event group_checked "group=$1" "checked:=$2"
}

# mu_group_end <group> <result> <seconds> [checked] — counts are derived from
# the item_end events of this run and group already in the file. The optional
# checked count (or the latest mu_group_checked of the group) is added to
# group_end as "checked"; without either, group_end is unchanged.
mu_group_end() {
    [ -n "${MAC_UPDATE_EVENT_FILE:-}" ] || return 0
    command -v python3 >/dev/null 2>&1 || return 0
    if [ -n "${4:-}" ]; then
        python3 "$_MU_EVENTS_DIR/python/mu_events.py" group-end "$MAC_UPDATE_EVENT_FILE" \
            "$1" "$2" "${3:-0}" "$4" </dev/null >/dev/null 2>&1 || true
    else
        python3 "$_MU_EVENTS_DIR/python/mu_events.py" group-end "$MAC_UPDATE_EVENT_FILE" \
            "$1" "$2" "${3:-0}" </dev/null >/dev/null 2>&1 || true
    fi
    return 0
}

# mu_prompt <id> <yesno|sudo|choice> <text> [options-csv] [default] [timeout]
# Emitted immediately before a read or sudo prompt.
mu_prompt() {
    [ -n "${MAC_UPDATE_EVENT_FILE:-}" ] || return 0
    local opts_json="[]" item first=1 rest
    if [ -n "${4:-}" ]; then
        opts_json="["
        rest="$4,"
        while [ -n "$rest" ]; do
            item="${rest%%,*}"
            rest="${rest#*,}"
            case "$item" in *[!A-Za-z0-9_.-]*|'') continue ;; esac
            [ "$first" -eq 1 ] || opts_json="$opts_json,"
            opts_json="$opts_json\"$item\""
            first=0
        done
        opts_json="$opts_json]"
    fi
    local timeout_json="null"
    case "${6:-}" in ''|*[!0-9]*) ;; *) timeout_json="$6" ;; esac
    # Ids are unique per process and call, so a repeated question is shown again.
    local ident="$1"
    case "$ident" in *-"$$"-*) ;; *) ident="$ident-$$-$(date +%s)" ;; esac
    _MU_LAST_PROMPT_BASE="$1"
    _MU_LAST_PROMPT_ID="$ident"
    _MU_PROMPT_OPTS_JSON="$opts_json"
    _MU_PROMPT_TIMEOUT_JSON="$timeout_json"
    mu_event prompt "id=$ident" "kind=$2" "text=$3" "options:=$opts_json" "default=${5:-}" "timeout:=$timeout_json"
}

# mu_prompt_end <id> <yesno|sudo|choice> <text> [options-csv] [default] [timeout]
# Emitted immediately after the prompt was answered or the asking command
# returned (also after Touch ID). Same fields as the prompt event; the id is the
# one the matching mu_prompt call used, so an interface can close that prompt.
mu_prompt_end() {
    [ -n "${MAC_UPDATE_EVENT_FILE:-}" ] || return 0
    local ident="$1" opts_json="[]" timeout_json="null"
    if [ -n "${_MU_LAST_PROMPT_ID:-}" ] && [ "${_MU_LAST_PROMPT_BASE:-}" = "$1" ]; then
        ident="$_MU_LAST_PROMPT_ID"
        opts_json="${_MU_PROMPT_OPTS_JSON:-[]}"
        timeout_json="${_MU_PROMPT_TIMEOUT_JSON:-null}"
    else
        case "$ident" in *-"$$"-*) ;; *) ident="$ident-$$-$(date +%s)" ;; esac
    fi
    mu_event prompt_end "id=$ident" "kind=$2" "text=$3" "options:=$opts_json" "default=${5:-}" "timeout:=$timeout_json"
}
