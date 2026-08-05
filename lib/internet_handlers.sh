#!/usr/bin/env bash
# lib/internet_handlers.sh — shared internet app update handlers (Bash 3.2+)
# Requires: i18n loaded, internet_i18n.sh, silent_launch_app, app_version, copy_verified_app
#
# Handlers communicate status via INTERNET_LAST_STATUS global — NEVER via
# stdout echo. This prevents UI output (print_info/print_step/print_warn)
# from polluting the status when called inside command substitution.
# See: BUG-1 fix (2026-08-05).

INTERNET_LAST_STATUS=""

internet_handler_app_installed() {
    local app_path="$1"
    [ -n "$app_path" ] && [ -d "$app_path" ]
}

internet_handler_silent_launch() {
    local app_display="$1"
    local launch_target="$2"
    local verify_hint="${3:-}"
    local app_path="$4"
    local ver
    ver="$(app_version "$app_path")"
    print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$ver")"
    print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "$app_display")"
    if silent_launch_app "$launch_target"; then
        if [ -n "$verify_hint" ]; then
            print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "$verify_hint")"
        fi
        INTERNET_LAST_STATUS="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
    else
        print_warn "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "$app_display") — failed"
        INTERNET_LAST_STATUS="$L_INTERNET_STATUS_LAUNCH_FAILED"
    fi
}

internet_handler_manual() {
    local app_display="$1"
    local download_url="$2"
    local app_path="$3"
    local ver
    ver="$(app_version "$app_path")"
    print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$ver")"
    print_warn "$(internet_msg "$L_INTERNET_NO_AUTO_UPDATER" "$app_display")"
    print_info "$(internet_msg "$L_INTERNET_DOWNLOAD_LATEST" "$download_url")"
    INTERNET_LAST_STATUS="$L_INTERNET_STATUS_MANUAL_UPDATE"
}

internet_handler_set_status() {
    local var_name="$1"
    local value="$2"
    # Guard: only allow STATUS_* variable names (defense against eval injection)
    case "$var_name" in
        STATUS_[A-Z0-9_]*) ;;
        *)
            echo "internet_handler_set_status: invalid var_name: $var_name" >&2
            return 1
            ;;
    esac
    eval "${var_name}=\"\${value}\""
}

internet_handler_fail_scan() {
    local status="$1"
    case "$status" in
        *"⚠️"*) return 1 ;;
    esac
    return 0
}

# Google Keystone (Omaha) — Chrome, Google Drive
internet_handler_keystone() {
    local app_label="$1"
    local launch_name="$2"
    local verify_hint="$3"
    local keytone_label="$4"
    KEYSTONE_AGENT="/Library/Google/GoogleSoftwareUpdate/GoogleSoftwareUpdate.bundle/Contents/Resources/GoogleSoftwareUpdateAgent.app/Contents/MacOS/GoogleSoftwareUpdateAgent"
    if [ -f "$KEYSTONE_AGENT" ]; then
        if [ "$keytone_label" = "drive" ]; then
            print_step "$L_INTERNET_LAUNCHING_KEYSTONE_DRIVE"
        else
            print_step "$L_INTERNET_LAUNCHING_KEYSTONE"
        fi
        "$KEYSTONE_AGENT" --runMode ondemand 2>/dev/null &
        sleep 2
        print_ok "$(internet_msg "$L_INTERNET_KEYSTONE_STARTED" "$app_label")"
    else
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "$launch_name")"
        if silent_launch_app "$launch_name"; then
            if [ -n "$verify_hint" ]; then
                print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "$verify_hint")"
            fi
        fi
    fi
    INTERNET_LAST_STATUS="$L_INTERNET_STATUS_CHECKED_CLI"
}

# Standard silent-launch block with optional extra info line
internet_dispatch_silent_launch() {
    local header="$1"
    local app_display="$2"
    local status_var="$3"
    local launch_target="$4"
    local verify_hint="${5:-}"
    local extra_info="${6:-}"
    print_header "$header"
    APP_PATH="$(capture_app_path "$app_display")"
    if [ -z "$APP_PATH" ] || [ ! -d "$APP_PATH" ]; then
        APP_PATH="/Applications/${app_display}.app"
    fi
    if [ -d "$APP_PATH" ]; then
        internet_handler_silent_launch "$app_display" "$launch_target" "$verify_hint" "$APP_PATH"
        if [ -n "$extra_info" ]; then
            print_info "$extra_info"
        fi
        internet_handler_set_status "$status_var" "$INTERNET_LAST_STATUS"
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "$app_display")"
    fi
}

# Sparkle Appcast verification handler
internet_handler_sparkle_check() {
    local app_display="$1"
    local app_path="$2"
    local launch_target="${3:-$app_display}"

    local feed_url
    feed_url="$(defaults read "$app_path/Contents/Info" SUFeedURL 2>/dev/null || true)"
    if [ -z "$feed_url" ]; then
        print_warn "$L_INTERNET_SPARKLE_FEED_MISSING"
        internet_handler_silent_launch "$app_display" "$launch_target" "" "$app_path"
        return
    fi
    print_info "$(internet_msg "$L_INTERNET_SPARKLE_FEED_FOUND" "$feed_url")"

    local xml
    xml="$(curl -fsSL --max-time 15 --retry 2 "$feed_url" 2>/dev/null || true)"
    if [ -z "$xml" ]; then
        print_warn "$L_INTERNET_STATUS_OFFLINE"
        INTERNET_LAST_STATUS="$L_INTERNET_STATUS_OFFLINE"
        return
    fi

    local remote_ver
    remote_ver="$(echo "$xml" | grep -o 'sparkle:shortVersionString="[^"]*"' | head -1 | cut -d'"' -f2 || true)"
    if [ -z "$remote_ver" ]; then
        remote_ver="$(echo "$xml" | grep -o 'sparkle:version="[^"]*"' | head -1 | cut -d'"' -f2 || true)"
    fi

    local local_ver
    local_ver="$(app_version "$app_path")"

    if [ -z "$remote_ver" ]; then
        INTERNET_LAST_STATUS="$L_INTERNET_STATUS_UNKNOWN_VERSION"
    else
        local rel
        rel="$(internet_version_relation "$remote_ver" "$local_ver")"
        if [ "$rel" = "newer" ]; then
            INTERNET_LAST_STATUS="$(internet_msg "$L_INTERNET_STATUS_UPDATE_AVAILABLE_FMT" "$local_ver" "$remote_ver")"
        else
            INTERNET_LAST_STATUS="$(internet_msg "$L_INTERNET_STATUS_CURRENT_FMT" "$local_ver")"
        fi
    fi

    print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "$app_display")"
    silent_launch_app "$launch_target" || true
}

internet_dispatch_sparkle_appcast() {
    local header="$1"
    local app_display="$2"
    local status_var="$3"
    local launch_target="$4"
    print_header "$header"
    APP_PATH="$(capture_app_path "$app_display")"
    if [ -z "$APP_PATH" ] || [ ! -d "$APP_PATH" ]; then
        APP_PATH="/Applications/${app_display}.app"
    fi
    if [ -d "$APP_PATH" ]; then
        internet_handler_sparkle_check "$app_display" "$APP_PATH" "$launch_target"
        internet_handler_set_status "$status_var" "$INTERNET_LAST_STATUS"
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "$app_display")"
    fi
}

