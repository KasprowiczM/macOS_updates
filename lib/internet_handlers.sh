#!/usr/bin/env bash
# lib/internet_handlers.sh — shared internet app update handlers (Bash 3.2+)
# Requires: i18n loaded, internet_i18n.sh, silent_launch_app, app_version, copy_verified_app
#
# Handlers communicate status via INTERNET_LAST_STATUS global — NEVER via
# stdout echo. This prevents UI output (print_info/print_step/print_warn)
# from polluting the status when called inside command substitution.
# See: BUG-1 fix (2026-08-05).

INTERNET_LAST_STATUS=""
_INTERNET_HANDLERS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$_INTERNET_HANDLERS_DIR/appstore_ios.sh" ]; then
    . "$_INTERNET_HANDLERS_DIR/appstore_ios.sh"
fi

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
    if [ -n "$app_path" ] && command -v app_store_managed >/dev/null 2>&1 && app_store_managed "$app_path"; then
        INTERNET_LAST_STATUS="$L_INTERNET_STATUS_MANAGED_APPSTORE"
        INTERNET_LAST_VERIFIED=1
        print_info "$L_INTERNET_STATUS_MANAGED_APPSTORE"
        return 0
    fi
    local ver
    ver="$(app_version "$app_path")"
    print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$ver")"
    # A vendor that ships no auto-updater is a permanent fact about that vendor, not
    # a fault in this run. Reported as information for the same reason Antigravity's
    # 404 feed was demoted on 2026-08-26: a warning the operator can never clear
    # trains them to ignore warnings that matter. The manual-update line below still
    # tells them exactly what to do.
    print_info "$(internet_msg "$L_INTERNET_NO_AUTO_UPDATER" "$app_display")"
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
        if command -v app_store_managed >/dev/null 2>&1 && app_store_managed "$APP_PATH"; then
            INTERNET_LAST_STATUS="$L_INTERNET_STATUS_MANAGED_APPSTORE"
            INTERNET_LAST_VERIFIED=1
            print_info "$L_INTERNET_STATUS_MANAGED_APPSTORE"
            internet_handler_set_status "$status_var" "$INTERNET_LAST_STATUS"
            return 0
        fi
        INTERNET_LAST_VERIFIED=0
        INTERNET_LAST_LAUNCH_OK=0
        if command -v vendor_feed_row >/dev/null 2>&1 && vendor_feed_row "$app_display" >/dev/null 2>&1; then
            internet_handler_vendor_truth "$app_display" "$APP_PATH" "$launch_target"
        elif internet_feed_source "$APP_PATH" >/dev/null 2>&1; then
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
    remote_ver=$(echo "$xml" | PYTHONPATH="$_INTERNET_HANDLERS_DIR/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import sys
from vendor_feeds import evaluate_feed

body = sys.stdin.read()
os_ver = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
res = evaluate_feed("sparkle", body, "-", os_version=os_ver)
if res and res.get("version"):
    print(res["version"])
' "-" "$(sw_vers -productVersion 2>/dev/null)"
    )

    local local_ver
    local_ver="$(app_version "$app_path")"

    if [ -z "$remote_ver" ]; then
        INTERNET_LAST_STATUS="$L_INTERNET_STATUS_UNKNOWN_VERSION"
        INTERNET_LAST_VERIFIED=0
    else
        local rel
        rel="$(version_cmp "$remote_ver" "$local_ver")"
        if [ "$rel" = "newer" ]; then
            INTERNET_LAST_STATUS="$(internet_msg "$L_INTERNET_STATUS_UPDATE_AVAILABLE_FMT" "$local_ver" "$remote_ver")"
            INTERNET_LAST_VERIFIED=1
        elif [ "$rel" = "equal" ]; then
            INTERNET_LAST_STATUS="$(internet_msg "$L_INTERNET_STATUS_CURRENT_FMT" "$local_ver")"
            INTERNET_LAST_VERIFIED=1
        elif [ "$rel" = "older" ]; then
            INTERNET_LAST_STATUS="$(internet_msg "$L_INTERNET_STATUS_FEED_STALE_FMT" "$remote_ver" "$local_ver")"
            INTERNET_LAST_VERIFIED=0
        else
            INTERNET_LAST_STATUS="$L_INTERNET_STATUS_UNKNOWN_VERSION"
            INTERNET_LAST_VERIFIED=0
        fi
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
        if command -v app_store_managed >/dev/null 2>&1 && app_store_managed "$APP_PATH"; then
            INTERNET_LAST_STATUS="$L_INTERNET_STATUS_MANAGED_APPSTORE"
            INTERNET_LAST_VERIFIED=1
            print_info "$L_INTERNET_STATUS_MANAGED_APPSTORE"
            internet_handler_set_status "$status_var" "$INTERNET_LAST_STATUS"
            return 0
        fi
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
    local feed_unreadable=0
    if [ -f "$app_update_yml" ]; then
        local base_url
        base_url="$(grep -E '^url:' "$app_update_yml" | head -1 | cut -d':' -f2- | tr -d ' "')"
        if [ -n "$base_url" ]; then
            base_url="${base_url%/}"
            local manifest_yml
            manifest_yml="$(curl -fsSL --max-time 15 --retry 2 "${base_url}/latest-mac.yml" 2>/dev/null || curl -fsSL --max-time 15 --retry 2 "${base_url}/latest.yml" 2>/dev/null || true)"
            if [ -n "$manifest_yml" ]; then
                remote_ver="$(echo "$manifest_yml" | grep -E '^version:' | head -1 | cut -d':' -f2 | tr -d ' "')"
            else
                # Not every electron-updater endpoint is a static manifest.
                # Antigravity's hub answers 404 to latest-mac.yml and
                # latest.yml because it expects platform and arch parameters,
                # so there is nothing to parse and nothing wrong either. That
                # is a fact about the feed, not a fault of this run.
                feed_unreadable=1
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
        if [ "$feed_unreadable" -eq 1 ]; then
            print_info "$(internet_msg "$L_INTERNET_FEED_NOT_MACHINE_READABLE_FMT" "$app_display")"
        else
            print_warn "$L_INTERNET_STATUS_UNKNOWN_VERSION"
        fi
        INTERNET_LAST_STATUS="$L_INTERNET_STATUS_UNKNOWN_VERSION"
        INTERNET_LAST_VERIFIED=0
    else
        local rel
        rel="$(version_cmp "$remote_ver" "$local_ver")"
        if [ "$rel" = "newer" ]; then
            INTERNET_LAST_STATUS="$(internet_msg "$L_INTERNET_STATUS_UPDATE_AVAILABLE_FMT" "$local_ver" "$remote_ver")"
            INTERNET_LAST_VERIFIED=1
        elif [ "$rel" = "equal" ]; then
            INTERNET_LAST_STATUS="$(internet_msg "$L_INTERNET_STATUS_CURRENT_FMT" "$local_ver")"
            INTERNET_LAST_VERIFIED=1
        elif [ "$rel" = "older" ]; then
            INTERNET_LAST_STATUS="$(internet_msg "$L_INTERNET_STATUS_FEED_STALE_FMT" "$remote_ver" "$local_ver")"
            INTERNET_LAST_VERIFIED=0
        else
            INTERNET_LAST_STATUS="$L_INTERNET_STATUS_UNKNOWN_VERSION"
            INTERNET_LAST_VERIFIED=0
        fi
    fi

    print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "$app_display")"
    if silent_launch_app "$launch_target"; then
        INTERNET_LAST_LAUNCH_OK=1
    else
        INTERNET_LAST_LAUNCH_OK=0
    fi
}

# ── Vendor Truth Handler (v1.5.0) ───────────────────────────
# Consults the vendor feed first, launches updater only if needed,
# and supports vendor direct download/installation when configured.
internet_handler_vendor_truth() {
    local app="$1"
    local app_path="$2"
    local launch_target="${3:-$app}"

    local I
    I="$(app_version "$app_path")"
    INTERNET_LAST_VERIFIED=0
    INTERNET_LAST_LAUNCH_OK=0

    local row
    row="$(vendor_feed_lookup "$app" 2>/dev/null || true)"
    if [ -z "$row" ]; then
        print_warn "$(printf "${L_INTERNET_VENDOR_FEED_UNREACHABLE_FMT:-Vendor feed for %s unreachable}" "$app")"
        internet_handler_silent_launch "$app" "$launch_target" "" "$app_path"
        return
    fi

    local R URL CK CS ART HOST
    IFS='|' read -r R URL CK CS ART HOST <<EOF
$row
EOF

    local rel
    rel="$(version_cmp "$R" "$I")"
    if [ "$rel" = "equal" ]; then
        INTERNET_LAST_STATUS="$(printf "$L_INTERNET_STATUS_VENDOR_CURRENT_FMT" "$I")"
        INTERNET_LAST_VERIFIED=1
        return 0
    elif [ "$rel" = "older" ]; then
        INTERNET_LAST_STATUS="$(printf "$L_INTERNET_STATUS_FEED_STALE_FMT" "$R" "$I")"
        INTERNET_LAST_VERIFIED=0
        return 0
    elif [ "$rel" = "unknown" ]; then
        INTERNET_LAST_STATUS="$L_INTERNET_STATUS_UNKNOWN_VERSION"
        INTERNET_LAST_VERIFIED=0
        return 0
    elif [ "$rel" = "newer" ]; then
        if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ] || [ "${MAC_UPDATE_VERIFY_ONLY:-0}" = "1" ]; then
            INTERNET_LAST_STATUS="$(printf "$L_INTERNET_STATUS_UPDATE_AVAILABLE_FMT" "$I" "$R")"
            INTERNET_LAST_VERIFIED=1
            return 0
        fi

        local BID=""
        if command -v internet_app_bundle_id >/dev/null 2>&1; then
            BID="$(internet_app_bundle_id "$app_path")"
        fi
        if [ -n "$BID" ] && command -v internet_app_is_running >/dev/null 2>&1 && internet_app_is_running "$BID"; then
            INTERNET_LAST_STATUS="$(printf "$L_INTERNET_STATUS_NEEDS_RESTART_FMT" "$I" "$R")"
            INTERNET_LAST_VERIFIED=1
            return 0
        fi

        local WAIT="${MAC_UPDATE_STAGE_WAIT:-90}"
        case "$WAIT" in ''|*[!0-9]*) WAIT=90 ;; esac
        [ "$WAIT" -lt 0 ] && WAIT=0
        [ "$WAIT" -gt 600 ] && WAIT=600

        if [ "$WAIT" -gt 0 ]; then
            printf "$L_INTERNET_LAUNCH_CYCLE_FMT\n" "$app" "$R"
            silent_launch_app "$launch_target"
            sleep "$WAIT"
            if [ -n "$BID" ] && command -v internet_app_is_running >/dev/null 2>&1 && internet_app_is_running "$BID"; then
                if command -v internet_app_quit_gracefully >/dev/null 2>&1; then
                    internet_app_quit_gracefully "$BID" 2>/dev/null || true
                fi
            fi
            local poll_elapsed=0
            local I2="$I"
            while [ "$poll_elapsed" -lt 60 ]; do
                I2="$(app_version "$app_path")"
                if [ "$I2" != "$I" ]; then
                    break
                fi
                sleep 5
                poll_elapsed=$((poll_elapsed + 5))
            done
            local rel2
            rel2="$(version_cmp "$R" "$I2")"
            if [ "$rel2" = "equal" ] || [ "$rel2" = "older" ]; then
                INTERNET_LAST_STATUS="$(printf "$L_INTERNET_STATUS_UPDATED_FMT" "$I2")"
                INTERNET_LAST_VERIFIED=1
                return 0
            fi
        fi

        if [ "$ART" != "-" ] && [ "${MAC_UPDATE_VENDOR_DIRECT:-1}" != "0" ]; then
            local still_running=0
            if [ -n "$BID" ] && command -v internet_app_is_running >/dev/null 2>&1 && internet_app_is_running "$BID"; then
                still_running=1
            fi
            if [ "$still_running" -eq 0 ] && command -v vendor_direct_install >/dev/null 2>&1; then
                printf "$L_INTERNET_VENDOR_DIRECT_FMT\n" "$app" "$R" "$HOST"
                vendor_direct_install "$app_path" "$URL" "$ART" "$CK" "$CS" "$HOST" "$R"
                local vrc=$?
                if [ "$vrc" -eq 0 ]; then
                    local I3
                    I3="$(app_version "$app_path")"
                    local rel3
                    rel3="$(version_cmp "$R" "$I3")"
                    if [ "$rel3" = "equal" ] || [ "$rel3" = "older" ]; then
                        INTERNET_LAST_STATUS="$(printf "$L_INTERNET_STATUS_UPDATED_FMT" "$I3")"
                        INTERNET_LAST_VERIFIED=1
                        return 0
                    else
                        INTERNET_LAST_STATUS="$(printf "$L_INTERNET_STATUS_BEHIND_FMT" "$I3" "$R")"
                        INTERNET_LAST_VERIFIED=1
                        return 0
                    fi
                elif [ "$vrc" -eq 3 ]; then
                    INTERNET_LAST_STATUS="$L_INTERNET_STATUS_INSTALL_ERROR"
                    INTERNET_LAST_VERIFIED=0
                    INTERNET_HARD_FAIL=1
                    return 1
                else
                    INTERNET_LAST_STATUS="$L_INTERNET_STATUS_DOWNLOAD_ERROR"
                    INTERNET_LAST_VERIFIED=0
                    INTERNET_SOFT_FAIL=1
                    return 0
                fi
            fi
        fi

        INTERNET_LAST_STATUS="$(printf "$L_INTERNET_STATUS_BEHIND_FMT" "$I" "$R")"
        INTERNET_LAST_VERIFIED=1
        return 0
    fi
}

# ── Omaha / Chromium Updaters (v1.5.0) ──────────────────────
omaha_read_increment() {
    local log_file="$1"
    local init_size="${2:-0}"
    [ -f "$log_file" ] || return 0
    local cur_size
    cur_size=$(wc -c < "$log_file" 2>/dev/null | tr -d ' ' || echo 0)
    if [ "$cur_size" -lt "$init_size" ]; then
        local old_file="${log_file}.old"
        if [ -f "$old_file" ]; then
            tail -c +$((init_size + 1)) "$old_file" 2>/dev/null || true
        fi
        cat "$log_file" 2>/dev/null || true
    elif [ "$cur_size" -gt "$init_size" ]; then
        tail -c +$((init_size + 1)) "$log_file" 2>/dev/null || true
    fi
}

evaluate_omaha_status() {
    local app="$1"
    local app_path="$2"
    local log_inc="$3"
    local appid="$4"

    local st=""
    if [ -n "$log_inc" ]; then
        st=$(printf '%s\n' "$log_inc" | PYTHONPATH="$_INTERNET_HANDLERS_DIR/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import sys
from vendor_feeds import omaha_last_status
log = sys.stdin.read()
appid = sys.argv[1]
res = omaha_last_status(log, appid)
print(res if res else "")
' "$appid" 2>/dev/null || true)
    fi

    if [ "$st" = "noupdate" ]; then
        if [ "$appid" = "com.google.chrome" ]; then
            local vh_url="https://versionhistory.googleapis.com/v1/chrome/platforms/mac_arm64/channels/stable/versions/all/releases?filter=endtime=none"
            local vh_json=""
            vh_json="$(curl -fsSL --max-time 15 "$vh_url" 2>/dev/null || true)"
            local pub_ver=""
            if [ -n "$vh_json" ]; then
                pub_ver="$(printf '%s\n' "$vh_json" | PYTHONPATH="$_INTERNET_HANDLERS_DIR/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import sys
from vendor_feeds import version_history_public
print(version_history_public(sys.stdin.read()) or "")
' 2>/dev/null || true)"
            fi
            local inst_ver
            inst_ver="$(app_version "$app_path")"
            if [ -n "$pub_ver" ] && [ "$(version_cmp "$pub_ver" "$inst_ver")" = "newer" ]; then
                INTERNET_LAST_STATUS="$(printf "$L_INTERNET_STATUS_ROLLOUT_HOLD_FMT" "$inst_ver" "$pub_ver")"
                INTERNET_LAST_VERIFIED=1
                return 0
            fi
        fi
        INTERNET_LAST_STATUS="$L_INTERNET_STATUS_VENDOR_NOUPDATE"
        INTERNET_LAST_VERIFIED=1
        return 0
    elif [ "$st" = "ok" ]; then
        local initial_ver
        initial_ver="$(app_version "$app_path")"
        local cur_ver="$initial_ver"
        local elapsed=0
        while [ "$elapsed" -lt 60 ]; do
            sleep 5
            elapsed=$((elapsed + 5))
            cur_ver="$(app_version "$app_path")"
            if [ "$cur_ver" != "$initial_ver" ] && [ -n "$cur_ver" ]; then
                INTERNET_LAST_STATUS="$(printf "$L_INTERNET_STATUS_UPDATED_FMT" "$cur_ver")"
                INTERNET_LAST_VERIFIED=1
                return 0
            fi
        done
        INTERNET_LAST_STATUS="$L_INTERNET_STATUS_UPDATE_IN_PROGRESS"
        INTERNET_LAST_VERIFIED=0
        return 0
    else
        local user_log="${MAC_UPDATE_GOOGLE_USER_LOG:-$HOME/Library/Application Support/Google/GoogleUpdater/updater.log}"
        local sys_log="${MAC_UPDATE_GOOGLE_SYS_LOG:-/Library/Application Support/Google/GoogleUpdater/updater.log}"
        local max_age="${MAC_UPDATE_OMAHA_MAX_AGE_H:-6}"
        local recent_result=""
        recent_result=$(PYTHONPATH="$_INTERNET_HANDLERS_DIR/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import sys, os
from vendor_feeds import omaha_recent_status

user_log = sys.argv[1]
sys_log = sys.argv[2]
appid = sys.argv[3]
try:
    max_age = float(sys.argv[4])
except Exception:
    max_age = 6.0
log_inc = sys.argv[5] if len(sys.argv) > 5 else ""

chunks = []
for p in [user_log + ".old", user_log, sys_log + ".old", sys_log]:
    if os.path.isfile(p):
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                chunks.append(f.read())
        except Exception:
            pass
if log_inc:
    chunks.append(log_inc)

full_text = "\n".join(chunks)
res = omaha_recent_status(full_text, appid, max_age_h=max_age)
if res:
    print(f"{res[0]} {res[1]}")
' "$user_log" "$sys_log" "$appid" "$max_age" "$log_inc" 2>/dev/null || true)

        if [ -n "$recent_result" ]; then
            local r_st="${recent_result%% *}"
            local r_time="${recent_result#* }"
            if [ "$r_st" = "noupdate" ]; then
                INTERNET_LAST_STATUS="$(printf "$L_INTERNET_STATUS_OMAHA_RECENT_FMT" "$r_time")"
                INTERNET_LAST_VERIFIED=1
                return 0
            fi
        fi

        INTERNET_LAST_STATUS="$L_INTERNET_STATUS_UPDATER_TRIGGERED"
        INTERNET_LAST_VERIFIED=0
        return 0
    fi
}

internet_handler_chromium_updater() {
    local app="$1"
    local app_path="$2"
    local bin="$3"
    local log="$4"
    local appid="$5"

    INTERNET_LAST_VERIFIED=0
    INTERNET_LAST_LAUNCH_OK=0

    if [ ! -d "$app_path" ]; then
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "$app")"
        return 0
    fi

    if [ ! -x "$bin" ]; then
        internet_handler_silent_launch "$app" "$app" "" "$app_path"
        return 0
    fi

    local init_size=0
    [ -f "$log" ] && init_size=$(wc -c < "$log" 2>/dev/null | tr -d ' ' || echo 0)

    print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "$app")"
    if ! run_with_timeout 120 "$bin" --wake-all >/dev/null 2>&1; then
        print_warn "$L_INTERNET_STATUS_LAUNCH_FAILED"
        INTERNET_LAST_STATUS="$L_INTERNET_STATUS_LAUNCH_FAILED"
        INTERNET_LAST_LAUNCH_OK=0
        return 0
    fi
    INTERNET_LAST_LAUNCH_OK=1

    local wait_limit="${MAC_UPDATE_OMAHA_WAIT:-45}"
    case "$wait_limit" in ''|*[!0-9]*) wait_limit=45 ;; esac
    [ "$wait_limit" -lt 0 ] && wait_limit=0
    [ "$wait_limit" -gt 180 ] && wait_limit=180

    local elapsed=0
    local inc=""
    while [ "$elapsed" -lt "$wait_limit" ]; do
        sleep 3
        elapsed=$((elapsed + 3))
        inc=$(omaha_read_increment "$log" "$init_size")
        if echo "$inc" | grep -E -q '"updatecheck"\s*:\s*\{"status"' 2>/dev/null; then
            break
        fi
    done
    inc=$(omaha_read_increment "$log" "$init_size")

    if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -d "$MAC_UPDATE_SESSION_DIR" ]; then
        printf '%s\n' "$inc" >> "$MAC_UPDATE_SESSION_DIR/chromium_updater_log.txt"
    fi

    evaluate_omaha_status "$app" "$app_path" "$inc" "$appid"
}



