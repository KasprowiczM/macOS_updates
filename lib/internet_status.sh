#!/bin/bash
# ============================================================
# lib/internet_status.sh — Internet app status codes and summary (v1.5.0)
# POSIX / Bash 3.2 compatible.
# ============================================================

internet_status_code() {
    local text="$1"
    [ -n "$text" ] || { echo "unknown"; return 0; }

    # 1. Exact matches for static constants (no %s)
    case "$text" in
        "$L_INTERNET_STATUS_VENDOR_NOUPDATE") echo "current_vendor"; return 0 ;;
        "$L_INTERNET_STATUS_CHECKED_CLI") echo "current_vendor"; return 0 ;;
        "$L_INTERNET_STATUS_CURRENT") echo "current_verified"; return 0 ;;
        "$L_INTERNET_STATUS_CASK_CURRENT") echo "current_cask_only"; return 0 ;;
        "$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"|\
        "$L_INTERNET_STATUS_UPDATER_TRIGGERED"|\
        "$L_INTERNET_STATUS_UPDATE_IN_PROGRESS") echo "unverified"; return 0 ;;
        "$L_INTERNET_STATUS_MANAGED_BREW") echo "managed_brew"; return 0 ;;
        "$L_INTERNET_STATUS_MANAGED_APPSTORE") echo "managed_appstore"; return 0 ;;
        "$L_INTERNET_STATUS_MANUAL_UPDATE") echo "manual"; return 0 ;;
        "$L_INTERNET_STATUS_SKIPPED") echo "skipped"; return 0 ;;
        "$L_INTERNET_STATUS_INSTALL_ERROR"|\
        "$L_INTERNET_STATUS_MOUNT_ERROR"|\
        "$L_INTERNET_STATUS_EXTRACT_ERROR") echo "error_hard"; return 0 ;;
        "$L_INTERNET_STATUS_OFFLINE"|\
        "$L_INTERNET_STATUS_NO_URL"|\
        "$L_INTERNET_STATUS_DOWNLOAD_ERROR"|\
        "$L_INTERNET_STATUS_CHECK_MAU"|\
        "$L_INTERNET_STATUS_MAU_MISSING"|\
        "$L_INTERNET_STATUS_MAU_QUARANTINED"|\
        "$L_INTERNET_STATUS_MAU_OPENED"|\
        "$L_INTERNET_STATUS_UNKNOWN_VERSION"|\
        "$L_INTERNET_STATUS_CASK_MISSING"|\
        "$L_INTERNET_STATUS_LAUNCH_FAILED") echo "error_soft"; return 0 ;;
    esac

    # 2. Longest matching prefix among *_FMT patterns
    local best_code="unknown"
    local max_len=0
    local item c fmt p len

    for item in \
        "updated|$L_INTERNET_STATUS_UPDATED_FMT" \
        "current_verified|$L_INTERNET_STATUS_CURRENT_FMT" \
        "current_verified|$L_INTERNET_STATUS_VENDOR_CURRENT_FMT" \
        "current_vendor|$L_INTERNET_STATUS_OMAHA_RECENT_FMT" \
        "rollout_hold|$L_INTERNET_STATUS_ROLLOUT_HOLD_FMT" \
        "update_available|$L_INTERNET_STATUS_UPDATE_AVAILABLE_FMT" \
        "behind|$L_INTERNET_STATUS_BEHIND_FMT" \
        "behind|$L_INTERNET_STATUS_CASK_BEHIND_FMT" \
        "needs_restart|$L_INTERNET_STATUS_NEEDS_RESTART_FMT" \
        "feed_stale|$L_INTERNET_STATUS_FEED_STALE_FMT"
    do
        c="${item%%|*}"
        fmt="${item#*|}"
        [ -n "$fmt" ] || continue
        p="${fmt%%\%s*}"
        [ -n "$p" ] || continue
        case "$text" in
            "$p"*)
                len=${#p}
                if [ "$len" -gt "$max_len" ]; then
                    max_len=$len
                    best_code="$c"
                fi
                ;;
        esac
    done

    echo "$best_code"
}

_CURRENT_SECTION_HEADER=""
_CURRENT_SECTION_PRINTED=0

internet_summary_section() {
    if [ "$_CURRENT_SECTION_PRINTED" -eq 1 ]; then
        echo ""
    fi
    _CURRENT_SECTION_HEADER="$1"
    _CURRENT_SECTION_PRINTED=0
}

internet_summary_row() {
    local label="$1" status_val="$2" app_reg="$3"
    local app_p
    if [ "$app_reg" = "Microsoft AutoUpdate" ]; then
        app_p="${MAC_UPDATE_MAU_APP:-/Library/Application Support/Microsoft/MAU2.0/Microsoft AutoUpdate.app}"
    else
        app_p="$(internet_app_path "$app_reg" 2>/dev/null || true)"
    fi
    if [ -z "$app_p" ] || [ ! -d "$app_p" ]; then
        return 0
    fi
    if [ -n "$_CURRENT_SECTION_HEADER" ] && [ "$_CURRENT_SECTION_PRINTED" -eq 0 ]; then
        echo -e "  ${BOLD}${_CURRENT_SECTION_HEADER}${NC}"
        _CURRENT_SECTION_PRINTED=1
    fi
    printf "  %-32s %s\n" "$label" "$status_val"
}

internet_summary_end() {
    if [ "$_CURRENT_SECTION_PRINTED" -eq 1 ]; then
        echo ""
    fi
    _CURRENT_SECTION_HEADER=""
    _CURRENT_SECTION_PRINTED=0
}
