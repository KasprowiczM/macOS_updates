#!/usr/bin/env bash
# scripts/scan_update_feeds.sh — Detect update frameworks for installed apps
# Read-only — does NOT install or modify anything.
# Usage: bash scripts/scan_update_feeds.sh [--json]
set -o pipefail

JSON_MODE=0
[ "${1:-}" = "--json" ] && JSON_MODE=1

if [ "$JSON_MODE" -eq 0 ]; then
    printf "%-45s %-12s %s\n" "Application" "Framework" "Feed URL / Details"
    printf '%0.s─' {1..120}
    echo ""
fi

json_entries=""

scan_app() {
    local app_path="$1"
    local app_name
    app_name="$(basename "$app_path" .app)"

    local framework="none"
    local feed_url=""
    local details=""

    # Sparkle (SUFeedURL in Info.plist)
    local su_feed
    su_feed="$(defaults read "$app_path/Contents/Info" SUFeedURL 2>/dev/null || true)"
    if [ -n "$su_feed" ]; then
        framework="sparkle"
        feed_url="$su_feed"
    fi

    # Electron updater (app-update.yml)
    local electron_yml="$app_path/Contents/Resources/app-update.yml"
    if [ -f "$electron_yml" ]; then
        if [ "$framework" = "none" ]; then
            framework="electron"
        else
            framework="${framework}+electron"
        fi
        local provider
        provider="$(grep -m1 '^provider:' "$electron_yml" 2>/dev/null | sed 's/provider:[[:space:]]*//')"
        local url
        url="$(grep -m1 '^url:' "$electron_yml" 2>/dev/null | sed 's/url:[[:space:]]*//')"
        details="provider=$provider url=$url"
    fi

    # Google Keystone (KSUpdateURL in Info.plist)
    local ks_url
    ks_url="$(defaults read "$app_path/Contents/Info" KSUpdateURL 2>/dev/null || true)"
    if [ -n "$ks_url" ]; then
        if [ "$framework" = "none" ]; then
            framework="keystone"
        else
            framework="${framework}+keystone"
        fi
        feed_url="${feed_url:-$ks_url}"
    fi

    if [ "$JSON_MODE" -eq 1 ]; then
        local entry="{\"app\":\"$app_name\",\"framework\":\"$framework\",\"feed_url\":\"$feed_url\",\"details\":\"$details\"}"
        [ -n "$json_entries" ] && json_entries="$json_entries,"
        json_entries="$json_entries$entry"
    else
        local display="${feed_url:-$details}"
        [ -z "$display" ] && display="—"
        printf "%-45s %-12s %s\n" "$app_name" "$framework" "$display"
    fi
}

# Scan /Applications and ~/Applications
for dir in /Applications "${HOME}/Applications"; do
    [ -d "$dir" ] || continue
    for app in "$dir"/*.app; do
        [ -d "$app" ] || continue
        scan_app "$app"
    done
done

if [ "$JSON_MODE" -eq 1 ]; then
    echo "[$json_entries]"
fi
