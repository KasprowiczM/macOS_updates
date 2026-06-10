#!/usr/bin/env bash
# lib/internet_apps.sh — canonical internet-app inventory helpers (Bash 3.2+)
# Requires: SCRIPT_DIR set by caller; config/internet_apps.txt in repo root.

_internet_apps_config_path() {
    echo "${SCRIPT_DIR}/config/internet_apps.txt"
}

internet_apps_load_config() {
    local cfg line
    INTERNET_APPS_LIST=()
    cfg="$(_internet_apps_config_path)"
    if [ ! -f "$cfg" ]; then
        return 1
    fi
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line%%#*}"
        line="$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        [ -n "$line" ] || continue
        INTERNET_APPS_LIST+=("$line")
    done < "$cfg"
    return 0
}

internet_app_path() {
    local app_name="$1"
    case "$app_name" in
        "OpenCode")
            for candidate in \
                "/Applications/OpenCode.app" \
                "/Applications/opencode.app" \
                "/Applications/Opencode.app" \
                "/Applications/opencode Desktop.app"
            do
                [ -d "$candidate" ] && echo "$candidate" && return 0
            done
            ;;
        "Ledger Live")
            [ -d "/Applications/Ledger Live.app" ] && echo "/Applications/Ledger Live.app" && return 0
            [ -d "/Applications/Ledger Wallet.app" ] && echo "/Applications/Ledger Wallet.app" && return 0
            ;;
        "Docker Desktop")
            [ -d "/Applications/Docker.app" ] && echo "/Applications/Docker.app" && return 0
            ;;
    esac
    echo "/Applications/${app_name}.app"
}

internet_firefox_snapshot_version() {
    local ini="/Applications/Firefox Developer Edition.app/Contents/Resources/application.ini"
    if [ -f "$ini" ]; then
        grep "^Version=" "$ini" 2>/dev/null | head -1 | cut -d= -f2
    else
        defaults read "/Applications/Firefox Developer Edition.app/Contents/Info" CFBundleShortVersionString 2>/dev/null \
            || defaults read "/Applications/Firefox Developer Edition.app/Contents/Info" CFBundleVersion 2>/dev/null \
            || echo "?"
    fi
}

internet_capture_versions() {
    local outfile="$1"
    local app_name app_path ver
    : > "$outfile"
    internet_apps_load_config || return 1
    for app_name in "${INTERNET_APPS_LIST[@]}"; do
        app_path="$(internet_app_path "$app_name")"
        if [ -d "$app_path" ]; then
            if [ "$app_name" = "Firefox Developer Edition" ]; then
                ver="$(internet_firefox_snapshot_version)"
            else
                ver=$(defaults read "$app_path/Contents/Info" CFBundleShortVersionString 2>/dev/null \
                    || defaults read "$app_path/Contents/Info" CFBundleVersion 2>/dev/null \
                    || echo "?")
            fi
            echo "${app_name}|${ver}" >> "$outfile"
        fi
    done
}
