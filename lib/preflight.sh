#!/usr/bin/env bash
# lib/preflight.sh — read-only readiness checks (Bash 3.2+)
#
# Two consumers:
#   * `bash update_all.sh --doctor`  — preflight_doctor: every check, one
#     localized line each (✅ / ℹ️ / ⚠️ / ❌), exit 0 / 10 / 1.
#   * a real run                     — preflight_run_cheap: disk, power and
#     network only, before step 0. Policy: low disk => degraded run; low
#     battery with the macOS step enabled => that step is skipped softly;
#     no network at all => abort (exit 1) before any step.
#
# Contract: nothing here mutates the machine, nothing prompts. sudo is only
# ever probed with `sudo -n true` (critical_rules 6c). Network probes are
# HTTPS-only with short timeouts. Needs the i18n strings (L_DOCTOR_*,
# L_PREFLIGHT_*) to be loaded by the caller.
#
# Check functions print one line through _pf_line and return:
#   0 ok · 3 informational · 10 warning · 1 hard problem

_PF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_PF_REPO="$(cd "$_PF_DIR/.." && pwd)"

PREFLIGHT_WARNS=0
PREFLIGHT_FAILS=0
PREFLIGHT_DEGRADED=0
PREFLIGHT_SKIP_SYSTEM=0
PREFLIGHT_POWER_SOURCE="unknown"
PREFLIGHT_BATTERY_PCT=""
PREFLIGHT_NET_OK_COUNT=0
PREFLIGHT_NET_TOTAL=0
PREFLIGHT_NET_FAILED=""
PREFLIGHT_MINIMAL_PATH="/usr/bin:/bin:/usr/sbin:/sbin"

# Print one result line and return its code. Warnings and hard problems are
# counted in PREFLIGHT_WARNS / PREFLIGHT_FAILS (call it directly, never inside $(...)).
_pf_line() {
    local rc="$1" text="$2" icon
    case "$rc" in
        0)  icon="✅" ;;
        3)  icon="ℹ️ " ;;
        10) icon="⚠️ "; PREFLIGHT_WARNS=$((PREFLIGHT_WARNS + 1)) ;;
        *)  icon="❌"; PREFLIGHT_FAILS=$((PREFLIGHT_FAILS + 1)); rc=1 ;;
    esac
    printf '  %s %s\n' "$icon" "$text"
    return "$rc"
}

# Positive integer from an environment value, else the default.
_pf_int() {
    case "$1" in
        ''|*[!0-9]*) echo "$2" ;;
        *) echo "$1" ;;
    esac
}

preflight_min_free_gb() { _pf_int "${MAC_UPDATE_MIN_FREE_GB:-}" 15; }
preflight_min_battery() { _pf_int "${MAC_UPDATE_MIN_BATTERY:-}" 30; }
preflight_hosts() { echo "${MAC_UPDATE_PREFLIGHT_HOSTS:-api.github.com formulae.brew.sh itunes.apple.com}"; }

# ── Measurements (stub-friendly: they only call df / pmset / curl) ──────────

# Free GB (integer, rounded down) on the system volume; non-zero if unknown.
preflight_free_gb() {
    local path="${MAC_UPDATE_DISK_PATH:-/}" kb
    kb="$(df -Pk "$path" 2>/dev/null | awk 'NR==2 {print $4}')"
    case "$kb" in
        ''|*[!0-9]*) return 1 ;;
    esac
    echo $((kb / 1024 / 1024))
}

# Prints "<ac|battery|unknown> <percent|->" from `pmset -g batt`.
preflight_power() {
    local out src pct
    if ! out="$(pmset -g batt 2>/dev/null)"; then
        echo "unknown -"
        return 1
    fi
    case "$out" in
        *"AC Power"*) src="ac" ;;
        *"Battery Power"*) src="battery" ;;
        *) src="unknown" ;;
    esac
    pct="$(printf '%s\n' "$out" | grep -Eo '[0-9]+%' | head -n 1 | tr -d '%')"
    echo "$src ${pct:--}"
}

# HTTPS reachability of one host; any HTTP answer counts, TLS/connect failure does not.
preflight_net_reachable() {
    curl --proto '=https' --proto-redir '=https' -s -o /dev/null -I \
        --connect-timeout 4 --max-time 6 "https://$1/" >/dev/null 2>&1
}

# Sets PREFLIGHT_NET_OK_COUNT / _TOTAL / _FAILED. Returns 2 when curl is missing
# (undetermined — never a reason to abort).
preflight_net_probe() {
    local h
    PREFLIGHT_NET_OK_COUNT=0
    PREFLIGHT_NET_TOTAL=0
    PREFLIGHT_NET_FAILED=""
    command -v curl >/dev/null 2>&1 || return 2
    for h in $(preflight_hosts); do
        PREFLIGHT_NET_TOTAL=$((PREFLIGHT_NET_TOTAL + 1))
        if preflight_net_reachable "$h"; then
            PREFLIGHT_NET_OK_COUNT=$((PREFLIGHT_NET_OK_COUNT + 1))
        else
            PREFLIGHT_NET_FAILED="${PREFLIGHT_NET_FAILED:+$PREFLIGHT_NET_FAILED }$h"
        fi
    done
    return 0
}

# Tools of the given names that do NOT resolve under the minimal launchd PATH
# after lib/platform.sh has done whatever it does to PATH. Prints them space-separated.
preflight_minimal_path_missing() {
    /usr/bin/env -i HOME="${HOME:-/}" PATH="$PREFLIGHT_MINIMAL_PATH" \
        ${MAC_UPDATE_HOMEBREW_PREFIX:+MAC_UPDATE_HOMEBREW_PREFIX="$MAC_UPDATE_HOMEBREW_PREFIX"} \
        /bin/bash -c '
        . "$1" >/dev/null 2>&1
        shift
        for t in "$@"; do
            command -v "$t" >/dev/null 2>&1 || printf "%s " "$t"
        done
    ' _ "${PREFLIGHT_PLATFORM_SH:-$_PF_DIR/platform.sh}" "$@"
}

# "3d 4h" / "5h 12m" / "7m" from seconds.
_pf_age() {
    local s="$1" d h m
    case "$s" in ''|*[!0-9]*) echo "?"; return 0 ;; esac
    d=$((s / 86400)); h=$(((s % 86400) / 3600)); m=$(((s % 3600) / 60))
    if [ "$d" -gt 0 ]; then echo "${d}d ${h}h"
    elif [ "$h" -gt 0 ]; then echo "${h}h ${m}m"
    else echo "${m}m"
    fi
}

# ── Checks shared by --doctor and real runs ─────────────────────────────────

preflight_check_disk() {
    local gb min
    min="$(preflight_min_free_gb)"
    if ! gb="$(preflight_free_gb)"; then
        _pf_line 3 "$L_DOCTOR_DISK_UNKNOWN"
        return $?
    fi
    if [ "$gb" -lt "$min" ]; then
        _pf_line 10 "$(printf "$L_DOCTOR_DISK_LOW" "$gb" "$min")"
        return $?
    fi
    _pf_line 0 "$(printf "$L_DOCTOR_DISK_OK" "$gb" "$min")"
}

# Sets PREFLIGHT_POWER_SOURCE / PREFLIGHT_BATTERY_PCT. With an argument "quiet"
# only measures and returns 0 (ok / not on battery), 10 (battery below the
# minimum) or 3 (unknown) without printing.
preflight_check_power() {
    local quiet="${1:-}" reading min
    min="$(preflight_min_battery)"
    reading="$(preflight_power)"
    PREFLIGHT_POWER_SOURCE="${reading%% *}"
    PREFLIGHT_BATTERY_PCT="${reading#* }"
    [ "$PREFLIGHT_BATTERY_PCT" = "-" ] && PREFLIGHT_BATTERY_PCT=""
    case "$PREFLIGHT_POWER_SOURCE" in
        ac)
            [ "$quiet" = "quiet" ] && return 0
            _pf_line 0 "$L_DOCTOR_POWER_AC"
            ;;
        battery)
            case "$PREFLIGHT_BATTERY_PCT" in
                ''|*[!0-9]*)
                    [ "$quiet" = "quiet" ] && return 3
                    _pf_line 3 "$L_DOCTOR_POWER_UNKNOWN"
                    return $?
                    ;;
            esac
            if [ "$PREFLIGHT_BATTERY_PCT" -lt "$min" ]; then
                [ "$quiet" = "quiet" ] && return 10
                _pf_line 10 "$(printf "$L_DOCTOR_POWER_BATTERY_LOW" "$PREFLIGHT_BATTERY_PCT" "$min")"
                return $?
            fi
            [ "$quiet" = "quiet" ] && return 0
            _pf_line 0 "$(printf "$L_DOCTOR_POWER_BATTERY_OK" "$PREFLIGHT_BATTERY_PCT")"
            ;;
        *)
            [ "$quiet" = "quiet" ] && return 3
            _pf_line 3 "$L_DOCTOR_POWER_UNKNOWN"
            ;;
    esac
}

# 0 all hosts reachable · 10 some unreachable · 1 none reachable · 3 undetermined (no curl).
preflight_check_network() {
    local hosts
    hosts="$(preflight_hosts)"
    preflight_net_probe
    if [ "$?" -eq 2 ]; then
        return 3
    fi
    if [ "$PREFLIGHT_NET_OK_COUNT" -eq "$PREFLIGHT_NET_TOTAL" ]; then
        _pf_line 0 "$(printf "$L_DOCTOR_NET_OK" "$PREFLIGHT_NET_OK_COUNT" "$PREFLIGHT_NET_TOTAL")"
    elif [ "$PREFLIGHT_NET_OK_COUNT" -eq 0 ]; then
        _pf_line 1 "$(printf "$L_DOCTOR_NET_DOWN" "$hosts")"
    else
        _pf_line 10 "$(printf "$L_DOCTOR_NET_PARTIAL" "$PREFLIGHT_NET_FAILED")"
    fi
}

# Cheap subset for a real run. Sets PREFLIGHT_DEGRADED (low disk) and
# PREFLIGHT_SKIP_SYSTEM (battery too low while the macOS step is enabled).
# Returns 1 when the run must abort (no network at all), else 0.
preflight_run_cheap() {
    local rc min
    PREFLIGHT_DEGRADED=0
    PREFLIGHT_SKIP_SYSTEM=0
    min="$(preflight_min_battery)"

    preflight_check_disk
    [ "$?" -eq 10 ] && PREFLIGHT_DEGRADED=1

    preflight_check_power quiet
    rc=$?
    if [ "$rc" -eq 10 ] && [ "${MAC_UPDATE_SKIP_SYSTEM:-0}" != "1" ]; then
        PREFLIGHT_SKIP_SYSTEM=1
        PREFLIGHT_DEGRADED=1
        _pf_line 10 "$(printf "$L_PREFLIGHT_SYSTEM_BATTERY_SKIP" "$PREFLIGHT_BATTERY_PCT" "$min")"
    elif [ "$PREFLIGHT_POWER_SOURCE" = "ac" ]; then
        _pf_line 0 "$L_DOCTOR_POWER_AC"
    elif [ "$PREFLIGHT_POWER_SOURCE" = "battery" ] && [ -n "$PREFLIGHT_BATTERY_PCT" ]; then
        _pf_line 0 "$(printf "$L_DOCTOR_POWER_BATTERY_OK" "$PREFLIGHT_BATTERY_PCT")"
    fi

    preflight_check_network
    rc=$?
    if [ "$rc" -eq 1 ]; then
        _pf_line 1 "$L_PREFLIGHT_NET_ABORT"
        return 1
    fi
    return 0
}

# ── Doctor-only checks ──────────────────────────────────────────────────────

preflight_check_platform() {
    local out ver
    if out="$(mac_update_require_supported_platform 2>&1)"; then
        ver="$(sw_vers -productVersion 2>/dev/null)"
        _pf_line 0 "$(printf "$L_DOCTOR_PLATFORM_OK" "${ver:-?}")"
    else
        out="$(printf '%s\n' "$out" | head -n 1 | sed 's/^ERROR: *//')"
        _pf_line 1 "$(printf "$L_DOCTOR_PLATFORM_FAIL" "$out")"
    fi
}

# Resolved the way the pipeline resolves them: plain `command -v` on PATH.
preflight_check_tools() {
    local t p worst=0
    for t in python3 curl git brew mas; do
        p="$(command -v "$t" 2>/dev/null)"
        if [ -n "$p" ]; then
            _pf_line 0 "$(printf "$L_DOCTOR_TOOL_OK" "$t" "$p")"
            continue
        fi
        case "$t" in
            python3|curl)
                _pf_line 1 "$(printf "$L_DOCTOR_TOOL_MISSING_HARD" "$t")"
                worst=1
                ;;
            *)
                _pf_line 10 "$(printf "$L_DOCTOR_TOOL_MISSING_SOFT" "$t")"
                [ "$worst" -eq 0 ] && worst=10
                ;;
        esac
    done
    return "$worst"
}

preflight_check_launchd_path() {
    local present="" t missing
    for t in brew mas; do
        command -v "$t" >/dev/null 2>&1 && present="${present:+$present }$t"
    done
    [ -n "$present" ] || return 0
    # shellcheck disable=SC2086  # word splitting of the tool list is intended
    missing="$(preflight_minimal_path_missing $present)"
    missing="${missing% }"
    if [ -n "$missing" ]; then
        _pf_line 10 "$(printf "$L_DOCTOR_LAUNCHD_PATH_WARN" "$missing")"
    else
        _pf_line 0 "$(printf "$L_DOCTOR_LAUNCHD_PATH_OK" "$present")"
    fi
}

# install_launchagent.sh --check: exit 1 = plist exists but is not loaded.
preflight_check_launchagent() {
    local script out rc
    script="${SCRIPT_DIR:-$_PF_REPO}/scripts/install_launchagent.sh"
    if [ ! -f "$script" ]; then
        _pf_line 3 "$L_DOCTOR_LAUNCHAGENT_NONE"
        return $?
    fi
    out="$(bash "$script" --check 2>&1)"
    rc=$?
    if [ "$rc" -eq 1 ]; then
        _pf_line 10 "$L_DOCTOR_LAUNCHAGENT_NOT_LOADED"
        return $?
    fi
    case "$out" in
        *"✅"*|*[Aa]ctive*)
            _pf_line 0 "$L_DOCTOR_LAUNCHAGENT_ACTIVE"
            # `--check` appends a warning line (exit stays 0) when the plist lacks
            # EnvironmentVariables.PATH with Homebrew: surface it as its own warning.
            if printf '%s\n' "$out" | grep -q '^⚠️'; then
                _pf_line 10 "$L_DOCTOR_LAUNCHAGENT_PATH_WARN"
                return 10
            fi
            return 0
            ;;
        *) _pf_line 3 "$L_DOCTOR_LAUNCHAGENT_NONE" ;;
    esac
}

# `sudo -n true` only: it can never prompt.
preflight_check_sudo() {
    if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
        _pf_line 0 "$L_DOCTOR_SUDO_OK"
    else
        _pf_line 3 "$L_DOCTOR_SUDO_COLD"
    fi
}

preflight_check_touchid() {
    local local_pam="${MAC_UPDATE_PAM_SUDO_LOCAL:-/etc/pam.d/sudo_local}"
    local main_pam="${MAC_UPDATE_PAM_SUDO:-/etc/pam.d/sudo}"
    if grep -qs 'pam_tid' "$local_pam" "$main_pam"; then
        _pf_line 0 "$L_DOCTOR_TOUCHID_OK"
    else
        _pf_line 10 "$L_DOCTOR_TOUCHID_MISSING"
    fi
}

# The only probe the toolkit has is an osascript call against System Events,
# which can pop a macOS permission prompt — a side effect — so it is opt-in.
preflight_check_accessibility() {
    local probe
    if [ "${MAC_UPDATE_DOCTOR_PROBE_AX:-0}" != "1" ] || ! command -v osascript >/dev/null 2>&1; then
        _pf_line 3 "$L_DOCTOR_AX_NOT_CHECKED"
        return $?
    fi
    if ! type run_with_timeout >/dev/null 2>&1; then
        # shellcheck source=lib/proc.sh
        . "$_PF_DIR/proc.sh"
    fi
    probe="$(run_with_timeout 10 osascript -e 'tell application "System Events" to return name of first process whose frontmost is true' 2>&1)"
    if printf '%s\n' "$probe" | grep -qi -e '(-1743)' -e 'not allowed' -e 'assistive' -e 'accessibility' -e 'not authorized'; then
        _pf_line 10 "$L_DOCTOR_AX_DENIED"
    else
        _pf_line 0 "$L_DOCTOR_AX_OK"
    fi
}

preflight_check_xcode() {
    local dev_path
    dev_path="$(xcode-select -p 2>/dev/null)"
    case "$dev_path" in
        *.app/Contents/Developer*)
            if ! type brew_xcode_license_ok >/dev/null 2>&1; then
                # shellcheck source=lib/brew.sh
                . "$_PF_DIR/brew.sh"
            fi
            if brew_xcode_license_ok; then
                _pf_line 0 "$L_DOCTOR_XCODE_OK"
            else
                _pf_line 10 "$L_DOCTOR_XCODE_LICENSE"
            fi
            ;;
        *) _pf_line 3 "$L_DOCTOR_XCODE_NONE" ;;
    esac
}

# Git state from refs that are already fetched — never touches the network.
preflight_check_toolkit() {
    local root ver branch behind
    root="${SCRIPT_DIR:-$_PF_REPO}"
    ver="$(tr -d '[:space:]' < "$root/VERSION" 2>/dev/null)"
    ver="${ver:-?}"
    if ! git -C "$root" rev-parse --git-dir >/dev/null 2>&1; then
        _pf_line 3 "$(printf "$L_DOCTOR_TOOLKIT_NOGIT" "$ver")"
        return $?
    fi
    branch="$(git -C "$root" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null)"
    branch="${branch#origin/}"
    if [ -z "$branch" ]; then
        for branch in main master; do
            git -C "$root" rev-parse --verify --quiet "refs/remotes/origin/$branch" >/dev/null 2>&1 && break
            branch=""
        done
    fi
    if [ -n "$branch" ]; then
        behind="$(git -C "$root" rev-list --count "HEAD..refs/remotes/origin/$branch" 2>/dev/null)"
        case "$behind" in
            ''|*[!0-9]*) behind=0 ;;
        esac
        if [ "$behind" -gt 0 ]; then
            _pf_line 10 "$(printf "$L_DOCTOR_TOOLKIT_BEHIND" "$ver" "$behind" "$branch")"
            return $?
        fi
    fi
    if [ -n "$(git -C "$root" status --porcelain --untracked-files=no 2>/dev/null)" ]; then
        _pf_line 10 "$(printf "$L_DOCTOR_TOOLKIT_DIRTY" "$ver")"
        return $?
    fi
    _pf_line 0 "$(printf "$L_DOCTOR_TOOLKIT_OK" "$ver" "${branch:-origin}")"
}

# Age and result class of logs/run_summary_latest.json.
preflight_check_lastrun() {
    local file parsed age cls word
    file="${MAC_UPDATE_LOGS_DIR:-${SCRIPT_DIR:-$_PF_REPO}/logs}/run_summary_latest.json"
    if [ ! -f "$file" ]; then
        _pf_line 3 "$L_DOCTOR_LASTRUN_NONE"
        return $?
    fi
    parsed="$(python3 -c '
import datetime, json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as fh:
        data = json.load(fh)
    stamp = data.get("completed_at") or data.get("timestamp") or ""
    when = datetime.datetime.fromisoformat(stamp)
    if when.tzinfo is None:
        when = when.replace(tzinfo=datetime.timezone.utc)
    age = int((datetime.datetime.now(datetime.timezone.utc) - when).total_seconds())
    cls = str(data.get("exit_class") or "unknown")
    if str(data.get("run_status", "completed")) != "completed":
        cls = "error"
    print(max(age, 0), cls)
except Exception:
    print("? unknown")
' "$file" 2>/dev/null)"
    age="${parsed%% *}"
    cls="${parsed#* }"
    case "$cls" in
        clean)    word="$L_DOCTOR_CLASS_CLEAN" ;;
        warnings) word="$L_DOCTOR_CLASS_WARNINGS" ;;
        error)    word="$L_DOCTOR_CLASS_ERROR" ;;
        *)        word="$L_DOCTOR_CLASS_UNKNOWN" ;;
    esac
    local text rc=3
    text="$(printf "$L_DOCTOR_LASTRUN_FMT" "$(_pf_age "$age")" "$word")"
    case "$cls" in
        clean) rc=0 ;;
        error) rc=10 ;;
    esac
    _pf_line "$rc" "$text"
}

# Full read-only report. Exit 0 all fine, 10 warnings only, 1 a hard problem.
preflight_doctor() {
    local check
    PREFLIGHT_WARNS=0
    PREFLIGHT_FAILS=0
    echo ""
    echo "  $L_DOCTOR_TITLE"
    echo ""
    for check in \
        preflight_check_platform \
        preflight_check_tools \
        preflight_check_launchd_path \
        preflight_check_launchagent \
        preflight_check_sudo \
        preflight_check_touchid \
        preflight_check_accessibility \
        preflight_check_xcode \
        preflight_check_disk \
        preflight_check_power \
        preflight_check_network \
        preflight_check_toolkit \
        preflight_check_lastrun; do
        "$check"
    done
    echo ""
    if [ "$PREFLIGHT_FAILS" -gt 0 ]; then
        echo "  $(printf "$L_DOCTOR_RESULT_FAIL" "$PREFLIGHT_FAILS")"
        return 1
    elif [ "$PREFLIGHT_WARNS" -gt 0 ]; then
        echo "  $(printf "$L_DOCTOR_RESULT_WARN" "$PREFLIGHT_WARNS")"
        return 10
    fi
    echo "  $L_DOCTOR_RESULT_OK"
    return 0
}
