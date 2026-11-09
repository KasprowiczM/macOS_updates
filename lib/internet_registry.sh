#!/usr/bin/env bash
# lib/internet_registry.sh — load config/internet_app_methods.txt (Bash 3.2+)

_internet_methods_config_path() {
    echo "${SCRIPT_DIR}/config/internet_app_methods.txt"
}

_INTERNET_REGISTRY_LOADED=0

# Populates INTERNET_METHOD_APPS[], INTERNET_METHOD_TYPES[], INTERNET_METHOD_STATUS[]
internet_registry_load() {
    [ "${_INTERNET_REGISTRY_LOADED:-0}" -eq 1 ] && return 0
    local cfg line app method status
    INTERNET_METHOD_APPS=()
    INTERNET_METHOD_TYPES=()
    INTERNET_METHOD_STATUS=()
    INTERNET_METHOD_FEEDS=()
    cfg="$(_internet_methods_config_path)"
    [ -f "$cfg" ] || return 1
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line%%#*}"
        line="${line#"${line%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"
        [ -n "$line" ] || continue
        # Validate: 3 or 4 pipe-delimited fields (AppName|method|STATUS_VAR[|feed_url])
        case "$line" in
            *\|*\|*\|*\|*)
                echo "internet_registry_load: malformed row (more than 4 fields): $line" >&2
                continue
                ;;
            *\|*\|*\|*) ;;
            *\|*\|*) ;;
            *)
                echo "internet_registry_load: malformed row (need 3 or 4 fields): $line" >&2
                continue
                ;;
        esac
        app="${line%%|*}"
        line="${line#*|}"
        method="${line%%|*}"
        line="${line#*|}"
        case "$line" in
            *\|*)
                status="${line%%|*}"
                feed_url="${line#*|}"
                ;;
            *)
                status="$line"
                feed_url=""
                ;;
        esac
        INTERNET_METHOD_APPS+=("$app")
        INTERNET_METHOD_TYPES+=("$method")
        INTERNET_METHOD_STATUS+=("$status")
        INTERNET_METHOD_FEEDS+=("$feed_url")
    done < "$cfg"
    _INTERNET_REGISTRY_LOADED=1
    return 0
}

internet_registry_method_for() {
    local name="$1"
    local i
    internet_registry_load || return 1
    i=0
    while [ "$i" -lt "${#INTERNET_METHOD_APPS[@]}" ]; do
        if [ "${INTERNET_METHOD_APPS[$i]}" = "$name" ]; then
            echo "${INTERNET_METHOD_TYPES[$i]}"
            return 0
        fi
        i=$((i + 1))
    done
    return 1
}

# internet_effective_method <app> <config_method>
# The method that actually decides an app's update, for reporting
# (logs/version_history.tsv). A row in config/vendor_feeds.txt makes the vendor
# feed the source of truth for silent_launch / docker_cli / sparkle_appcast apps:
# internet_handler_vendor_truth (or Docker's verified DMG path) compares versions
# and installs directly; the configured method is only the fallback when the
# feed is unusable. Same rule as scripts/report_update_coverage.sh (vendor_feed).
# Other methods are returned unchanged. Every returned name is either a config
# method (with a handler, rule 6a) or "vendor_feed" (internet_handler_vendor_truth).
internet_effective_method() {
    local app="$1" method="$2"
    case "$method" in
        silent_launch|docker_cli|sparkle_appcast)
            if command -v vendor_feed_row >/dev/null 2>&1 && vendor_feed_row "$app" >/dev/null 2>&1; then
                printf 'vendor_feed\n'
                return 0
            fi
            ;;
    esac
    printf '%s\n' "$method"
}

_internet_dispatch_config_path() {
    echo "${SCRIPT_DIR}/config/internet_dispatch_order.txt"
}

# Run ordered handler functions from config/internet_dispatch_order.txt
internet_dispatch_run_all() {
    local cfg line fn
    cfg="$(_internet_dispatch_config_path)"
    [ -f "$cfg" ] || return 1
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line%%#*}"
        line="${line#"${line%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"
        [ -n "$line" ] || continue
        fn="$line"
        if type "$fn" >/dev/null 2>&1; then
            "$fn"
        else
            print_warn "Missing internet handler: $fn"
            INTERNET_HARD_FAIL=1
            INTERNET_EXIT=1
        fi
    done < "$cfg"
    return 0
}
