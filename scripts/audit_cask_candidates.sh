#!/usr/bin/env bash
# scripts/audit_cask_candidates.sh — Audit silent_launch apps for Homebrew cask migration
# Read-only — does NOT install or modify anything.
# Usage: bash scripts/audit_cask_candidates.sh [--json]
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
JSON_MODE=0
[ "${1:-}" = "--json" ] && JSON_MODE=1

# Known app name → cask slug mappings (verified candidates)
cask_for_app() {
    local app="$1"
    case "$app" in
        "Brave Browser")                    echo "brave-browser" ;;
        "Cursor")                           echo "cursor" ;;
        "Obsidian")                         echo "obsidian" ;;
        "LM Studio")                        echo "lm-studio" ;;
        "ProtonVPN")                        echo "protonvpn" ;;
        "Proton Mail")                      echo "proton-mail" ;;
        "Proton Drive")                     echo "proton-drive" ;;
        "MEGAsync")                         echo "megasync" ;;
        "Warp")                             echo "warp" ;;
        "AppCleaner")                       echo "appcleaner" ;;
        "Spotify")                          echo "spotify" ;;
        "CapCut")                           echo "capcut" ;;
        "Claude")                           echo "claude" ;;
        "zoom.us")                          echo "zoom" ;;
        "Remote Desktop Manager")           echo "devolutions-remote-desktop-manager" ;;
        "Comet")                            echo "comet" ;;
        "ChatGPT / Codex"|"ChatGPT Atlas")  echo "chatgpt" ;;
        "Gemini")                           echo "gemini" ;;
        "Perplexity")                       echo "perplexity" ;;
        "Antigravity")                      echo "antigravity" ;;
        "Antigravity IDE")                  echo "antigravity-ide" ;;
        "Ascendo")                          echo "ascendo" ;;
        "OpenCode")                         echo "opencode" ;;
        *)                                  echo "" ;;
    esac
}

app_version() {
    local app_path="$1"
    defaults read "$app_path/Contents/Info" CFBundleShortVersionString 2>/dev/null \
        || defaults read "$app_path/Contents/Info" CFBundleVersion 2>/dev/null \
        || echo "?"
}

# Header
if [ "$JSON_MODE" -eq 0 ]; then
    printf "%-28s %-14s %-38s %-9s %-14s %-14s %-10s\n" \
        "App" "Installed" "Cask Candidate" "Exists?" "Cask Version" "auto_updates?" ":latest?"
    printf '%0.s─' {1..130}
    echo ""
fi

json_entries=""

while IFS='|' read -r app_name method status_var; do
    case "$app_name" in '#'*|'') continue ;; esac
    method="$(echo "$method" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    [ "$method" = "silent_launch" ] || continue

    app_name="$(echo "$app_name" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    candidate="$(cask_for_app "$app_name")"
    [ -z "$candidate" ] && candidate="$(echo "$app_name" | tr '[:upper:] ' '[:lower:]-' | sed 's/[^a-z0-9-]//g')"

    # Get installed version
    app_path="/Applications/${app_name}.app"
    [ -d "$app_path" ] || app_path="${HOME}/Applications/${app_name}.app"
    if [ -d "$app_path" ]; then
        installed="$(app_version "$app_path")"
    else
        installed="not found"
    fi

    # Check if cask exists
    cask_exists="❌"
    cask_version="—"
    auto_updates="—"
    version_latest="—"

    cask_info="$(brew info --cask "$candidate" 2>/dev/null)"
    if [ $? -eq 0 ] && [ -n "$cask_info" ]; then
        cask_exists="✅"
        cask_version="$(echo "$cask_info" | head -1 | awk '{print $2}' | sed 's/,$//')"
        if echo "$cask_info" | grep -q "auto_updates true"; then
            auto_updates="yes"
        else
            auto_updates="no"
        fi
        if [ "$cask_version" = ":latest" ] || echo "$cask_info" | grep -q "version :latest"; then
            version_latest="yes"
        else
            version_latest="no"
        fi
    fi

    if [ "$JSON_MODE" -eq 1 ]; then
        entry="{\"app\":\"$app_name\",\"installed\":\"$installed\",\"cask\":\"$candidate\",\"exists\":$([ "$cask_exists" = "✅" ] && echo true || echo false),\"cask_version\":\"$cask_version\",\"auto_updates\":\"$auto_updates\",\"version_latest\":\"$version_latest\"}"
        [ -n "$json_entries" ] && json_entries="$json_entries,"
        json_entries="$json_entries$entry"
    else
        printf "%-28s %-14s %-38s %-9s %-14s %-14s %-10s\n" \
            "$app_name" "$installed" "$candidate" "$cask_exists" "$cask_version" "$auto_updates" "$version_latest"
    fi
done < "$SCRIPT_DIR/config/internet_app_methods.txt"

if [ "$JSON_MODE" -eq 1 ]; then
    echo "[$json_entries]"
fi
