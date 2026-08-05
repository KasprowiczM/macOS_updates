#!/usr/bin/env bash
# lib/internet_handlers.sh — shared internet app update handlers (Bash 3.2+)
# Requires: i18n loaded, internet_i18n.sh, silent_launch_app, app_version, copy_verified_app
#
# Handlers communicate status via INTERNET_LAST_STATUS global — NEVER via
# stdout echo. This prevents UI output (print_info/print_step/print_warn)
# from polluting the status when called inside command substitution.
# See: BUG-1 fix (2026-08-05).

INTERNET_LAST_STATUS=""

# INTERNET_LAST_VERIFIED — 1 only when the handler actually compared a remote
# feed version against the installed one and wrote a version-bearing status
# (L_INTERNET_STATUS_CURRENT_FMT / L_INTERNET_STATUS_UPDATE_AVAILABLE_FMT).
# Anything else (no feed, feed unreachable, unparseable feed) leaves it 0 so a
# caller can never present an unverified check as verified.
INTERNET_LAST_VERIFIED=0

# INTERNET_LAST_LAUNCH_OK — 1 when the handler's trailing silent_launch_app
# succeeded. Lets a caller downgrade an unverified result to the honest
# "launched (unverified)" / "launch failed" pair without launching twice.
INTERNET_LAST_LAUNCH_OK=0

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
    INTERNET_LAST_VERIFIED=0
    print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$ver")"
    print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "$app_display")"
    if silent_launch_app "$launch_target"; then
        INTERNET_LAST_LAUNCH_OK=1
        if [ -n "$verify_hint" ]; then
            print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "$verify_hint")"
        fi
        INTERNET_LAST_STATUS="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
    else
        INTERNET_LAST_LAUNCH_OK=0
        print_warn "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "$app_display") — failed"
        INTERNET_LAST_STATUS="$L_INTERNET_STATUS_LAUNCH_FAILED"
    fi
}

# internet_feed_source — does this bundle expose a machine-readable version
# feed? Echoes "sparkle" or "electron" and returns 0; returns 1 when neither
# exists. Read-only: it never fetches, launches, or mutates anything.
internet_feed_source() {
    local app_path="$1"
    local feed_url
    [ -n "$app_path" ] && [ -d "$app_path" ] || return 1
    feed_url="$(defaults read "$app_path/Contents/Info" SUFeedURL 2>/dev/null || true)"
    if [ -n "$feed_url" ]; then
        echo "sparkle"
        return 0
    fi
    if [ -f "$app_path/Contents/Resources/app-update.yml" ]; then
        echo "electron"
        return 0
    fi
    return 1
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

# Google Keystone (Omaha) — Chrome and Google Drive ONLY.
# The agent is a Google-product updater: it reads its own ticket store and does
# nothing at all for a non-Google bundle. Never register a third-party app as
# `keystone` — running the agent for it would report a check that never
# happened (see Comet, fixed 2026-08-05).
#
# The status now follows the agent's exit code. It used to be hardcoded to
# L_INTERNET_STATUS_CHECKED_CLI on every path, so a missing agent or a failed
# run still printed "✅ Checked via CLI".
internet_handler_keystone() {
    local app_label="$1"
    local launch_name="$2"
    local verify_hint="$3"
    local keytone_label="$4"
    KEYSTONE_AGENT="/Library/Google/GoogleSoftwareUpdate/GoogleSoftwareUpdate.bundle/Contents/Resources/GoogleSoftwareUpdateAgent.app/Contents/MacOS/GoogleSoftwareUpdateAgent"
    INTERNET_LAST_VERIFIED=0
    if [ -f "$KEYSTONE_AGENT" ]; then
        if [ "$keytone_label" = "drive" ]; then
            print_step "$L_INTERNET_LAUNCHING_KEYSTONE_DRIVE"
        else
            print_step "$L_INTERNET_LAUNCHING_KEYSTONE"
        fi
        if run_with_timeout 180 "$KEYSTONE_AGENT" --runMode ondemand >/dev/null 2>&1; then
            print_ok "$(internet_msg "$L_INTERNET_KEYSTONE_STARTED" "$app_label")"
            INTERNET_LAST_STATUS="$L_INTERNET_STATUS_CHECKED_CLI"
        else
            print_warn "$L_INTERNET_STATUS_LAUNCH_FAILED"
            INTERNET_LAST_STATUS="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    else
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "$launch_name")"
        if silent_launch_app "$launch_name"; then
            INTERNET_LAST_LAUNCH_OK=1
            if [ -n "$verify_hint" ]; then
                print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "$verify_hint")"
            fi
            INTERNET_LAST_STATUS="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
        else
            INTERNET_LAST_LAUNCH_OK=0
            INTERNET_LAST_STATUS="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    fi
}

# Standard silent-launch block with optional extra info line.
#
# Opportunistic verification: an app whose only documented update path is its
# own updater may still publish a machine-readable version feed (Sparkle
# SUFeedURL, or electron-updater Contents/Resources/app-update.yml). When one
# exists this reads it and reports the real comparison; when it does not — or
# the feed cannot be read — it degrades to the historical launch-and-report
# behaviour. It NEVER installs or replaces a bundle: the app's own updater
# still does all the installing.
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
        INTERNET_LAST_VERIFIED=0
        INTERNET_LAST_LAUNCH_OK=0
        if internet_feed_source "$APP_PATH" >/dev/null 2>&1; then
            internet_handler_vendor_latest "$app_display" "$APP_PATH" "$launch_target"
            if [ "$INTERNET_LAST_VERIFIED" -ne 1 ]; then
                # A feed exists but yielded no comparable version (unreachable,
                # or a shape this parser does not understand). Claim only what
                # actually happened — the launch — so the severity of this step
                # is unchanged from the pre-verification behaviour.
                if [ "$INTERNET_LAST_LAUNCH_OK" -eq 1 ]; then
                    INTERNET_LAST_STATUS="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
                else
                    INTERNET_LAST_STATUS="$L_INTERNET_STATUS_LAUNCH_FAILED"
                fi
            fi
        else
            print_info "$(internet_msg "$L_INTERNET_NO_FEED_FALLBACK" "$app_display")"
            internet_handler_silent_launch "$app_display" "$launch_target" "$verify_hint" "$APP_PATH"
        fi
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
    INTERNET_LAST_VERIFIED=0
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
        remote_ver="$(echo "$xml" | sed -n 's/.*<sparkle:shortVersionString>\([^<]*\)<\/sparkle:shortVersionString>.*/\1/p' | head -1 || true)"
    fi
    if [ -z "$remote_ver" ]; then
        remote_ver="$(echo "$xml" | grep -o 'sparkle:version="[^"]*"' | head -1 | cut -d'"' -f2 || true)"
    fi
    if [ -z "$remote_ver" ]; then
        remote_ver="$(echo "$xml" | sed -n 's/.*<sparkle:version>\([^<]*\)<\/sparkle:version>.*/\1/p' | head -1 || true)"
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
        INTERNET_LAST_VERIFIED=1
    fi

    print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "$app_display")"
    if silent_launch_app "$launch_target"; then
        INTERNET_LAST_LAUNCH_OK=1
    else
        INTERNET_LAST_LAUNCH_OK=0
    fi
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

# Vendor feed verification handler — the single feed-discovery implementation.
# Reached from internet_dispatch_silent_launch for any app that turns out to
# publish a feed (internet_feed_source). It only reads a feed, compares
# versions and reports; installing stays with the app's own updater.
internet_handler_vendor_latest() {
    local app_display="$1"
    local app_path="$2"
    local launch_target="${3:-$app_display}"
    local feed_url_override="${4:-}"

    local local_ver
    local_ver="$(app_version "$app_path")"
    INTERNET_LAST_VERIFIED=0
    print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$local_ver")"

    local remote_ver=""
    local feed_url=""

    # 1. Try Sparkle SUFeedURL from Info.plist
    feed_url="$(defaults read "$app_path/Contents/Info" SUFeedURL 2>/dev/null || true)"
    if [ -n "$feed_url" ]; then
        internet_handler_sparkle_check "$app_display" "$app_path" "$launch_target"
        return
    fi

    # 2. Try electron-updater (Contents/Resources/app-update.yml)
    local app_update_yml="$app_path/Contents/Resources/app-update.yml"
    if [ -f "$app_update_yml" ]; then
        local base_url
        base_url="$(grep -E '^url:' "$app_update_yml" | head -1 | cut -d':' -f2- | tr -d ' "')"
        if [ -n "$base_url" ]; then
            base_url="${base_url%/}"
            local manifest_yml
            manifest_yml="$(curl -fsSL --max-time 15 --retry 2 "${base_url}/latest-mac.yml" 2>/dev/null || curl -fsSL --max-time 15 --retry 2 "${base_url}/latest.yml" 2>/dev/null || true)"
            if [ -n "$manifest_yml" ]; then
                remote_ver="$(echo "$manifest_yml" | grep -E '^version:' | head -1 | cut -d':' -f2 | tr -d ' "')"
            fi
        fi
    fi

    # 3. Try custom feed_url override
    if [ -z "$remote_ver" ] && [ -n "$feed_url_override" ]; then
        local body
        body="$(curl -fsSL --max-time 15 --retry 2 "$feed_url_override" 2>/dev/null || true)"
        if [ -n "$body" ]; then
            remote_ver="$(echo "$body" | grep -o 'sparkle:shortVersionString="[^"]*"' | head -1 | cut -d'"' -f2 || true)"
            [ -z "$remote_ver" ] && remote_ver="$(echo "$body" | sed -n 's/.*<sparkle:shortVersionString>\([^<]*\)<\/sparkle:shortVersionString>.*/\1/p' | head -1 || true)"
            [ -z "$remote_ver" ] && remote_ver="$(echo "$body" | grep -E '^version:' | head -1 | cut -d':' -f2 | tr -d ' "')"
            [ -z "$remote_ver" ] && remote_ver="$(echo "$body" | grep -o '"version": "[^"]*"' | head -1 | cut -d'"' -f4 || true)"
        fi
    fi

    if [ -z "$remote_ver" ]; then
        print_warn "$L_INTERNET_STATUS_UNKNOWN_VERSION"
        INTERNET_LAST_STATUS="$L_INTERNET_STATUS_UNKNOWN_VERSION"
    else
        local rel
        rel="$(internet_version_relation "$remote_ver" "$local_ver")"
        if [ "$rel" = "newer" ]; then
            INTERNET_LAST_STATUS="$(internet_msg "$L_INTERNET_STATUS_UPDATE_AVAILABLE_FMT" "$local_ver" "$remote_ver")"
        else
            INTERNET_LAST_STATUS="$(internet_msg "$L_INTERNET_STATUS_CURRENT_FMT" "$local_ver")"
        fi
        INTERNET_LAST_VERIFIED=1
    fi

    print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "$app_display")"
    if silent_launch_app "$launch_target"; then
        INTERNET_LAST_LAUNCH_OK=1
    else
        INTERNET_LAST_LAUNCH_OK=0
    fi
}

