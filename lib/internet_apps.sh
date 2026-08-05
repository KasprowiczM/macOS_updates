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
        line="${line#"${line%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"
        [ -n "$line" ] || continue
        INTERNET_APPS_LIST+=("$line")
    done < "$cfg"
    return 0
}

internet_cask_name_for_app() {
    local app="$1"
    case "$app" in
        "Brave Browser")          echo "brave-browser" ;;
        "Claude")                 echo "claude" ;;
        "Comet")                  echo "comet" ;;
        "Perplexity")             echo "perplexity" ;;
        "Antigravity")            echo "antigravity" ;;
        "Antigravity IDE")        echo "antigravity-ide" ;;
        "LM Studio")              echo "lm-studio" ;;
        "Cursor")                 echo "cursor" ;;
        "Obsidian")               echo "obsidian" ;;
        "ProtonVPN")              echo "protonvpn" ;;
        "Proton Mail")            echo "proton-mail" ;;
        "zoom.us")                echo "zoom" ;;
        "MEGAsync")               echo "megasync" ;;
        "Proton Drive")           echo "proton-drive" ;;
        "Warp")                   echo "warp" ;;
        "AppCleaner")             echo "appcleaner" ;;
        "Spotify")                echo "spotify" ;;
        "CapCut")                 echo "capcut" ;;
        "Inkscape")               echo "inkscape" ;;
        *)                        echo "$app" | tr '[:upper:] ' '[:lower:]-' | sed 's/[^a-z0-9-]//g' ;;
    esac
}

internet_get_app_days_unchanged() {
    local app_name="$1"
    local history_file="${SCRIPT_DIR}/logs/version_history.tsv"
    [ -f "$history_file" ] || { echo "0"; return; }

    python3 - "$app_name" "$history_file" <<'PYEOF'
import sys, datetime

app_target = sys.argv[1]
tsv_path = sys.argv[2]

entries = []
try:
    with open(tsv_path, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 3 and parts[1] == app_target:
                try:
                    dt = datetime.datetime.strptime(parts[0], "%Y-%m-%d %H:%M:%S")
                    entries.append((dt, parts[2]))
                except ValueError:
                    pass
except Exception:
    print("0")
    sys.exit(0)

if not entries:
    print("0")
    sys.exit(0)

entries.sort(key=lambda x: x[0])
latest_ver = entries[-1][1]
start_dt = entries[-1][0]
for dt, ver in reversed(entries):
    if ver == latest_ver:
        start_dt = dt
    else:
        break

days = (datetime.datetime.utcnow() - start_dt).days
print(max(0, days))
PYEOF
}

internet_rotate_version_history() {
    local history_file="${SCRIPT_DIR}/logs/version_history.tsv"
    [ -f "$history_file" ] || return 0

    python3 - "$history_file" <<'PYEOF'
import sys, datetime

tsv_path = sys.argv[1]
cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=365)
keep = []

try:
    with open(tsv_path, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 1:
                try:
                    dt = datetime.datetime.strptime(parts[0], "%Y-%m-%d %H:%M:%S")
                    if dt >= cutoff:
                        keep.append(line)
                except ValueError:
                    keep.append(line)
    if len(keep) > 5000:
        keep = keep[-5000:]
    with open(tsv_path, 'w', encoding='utf-8') as f:
        f.writelines(keep)
except Exception:
    pass
PYEOF
}

internet_app_path() {
    local app_name="$1" candidate bundle_id
    case "$app_name" in
        "ChatGPT / Codex")
            # OpenAI renamed the Codex desktop bundle to ChatGPT.app while
            # retaining com.openai.codex.  Match the bundle ID so the legacy
            # com.openai.chat (ChatGPT Classic) is never treated as this target.
            for candidate in \
                "/Applications/ChatGPT.app" \
                "${HOME}/Applications/ChatGPT.app" \
                "/Applications/Codex.app" \
                "${HOME}/Applications/Codex.app"
            do
                [ -d "$candidate" ] || continue
                bundle_id=$(defaults read "$candidate/Contents/Info" CFBundleIdentifier 2>/dev/null \
                    || mdls -raw -name kMDItemCFBundleIdentifier "$candidate" 2>/dev/null \
                    || true)
                if [ "$bundle_id" = "com.openai.codex" ]; then
                    echo "$candidate"
                    return 0
                fi
            done
            return 1
            ;;
        "ChatGPT Atlas")
            for candidate in \
                "/Applications/ChatGPT Atlas.app" \
                "${HOME}/Applications/ChatGPT Atlas.app" \
                "/Applications/Atlas.app" \
                "${HOME}/Applications/Atlas.app"
            do
                [ -d "$candidate" ] && echo "$candidate" && return 0
            done
            ;;
        "OpenCode")
            for candidate in \
                "/Applications/OpenCode.app" \
                "${HOME}/Applications/OpenCode.app" \
                "/Applications/opencode.app" \
                "${HOME}/Applications/opencode.app" \
                "/Applications/Opencode.app" \
                "${HOME}/Applications/Opencode.app" \
                "/Applications/opencode Desktop.app" \
                "${HOME}/Applications/opencode Desktop.app"
            do
                [ -d "$candidate" ] && echo "$candidate" && return 0
            done
            ;;
        "Ledger Live")
            [ -d "/Applications/Ledger Live.app" ] && echo "/Applications/Ledger Live.app" && return 0
            [ -d "/Applications/Ledger Wallet.app" ] && echo "/Applications/Ledger Wallet.app" && return 0
            [ -d "${HOME}/Applications/Ledger Live.app" ] && echo "${HOME}/Applications/Ledger Live.app" && return 0
            [ -d "${HOME}/Applications/Ledger Wallet.app" ] && echo "${HOME}/Applications/Ledger Wallet.app" && return 0
            ;;
        "Docker Desktop")
            [ -d "/Applications/Docker.app" ] && echo "/Applications/Docker.app" && return 0
            [ -d "${HOME}/Applications/Docker.app" ] && echo "${HOME}/Applications/Docker.app" && return 0
            ;;
        "DJI Assistant 2")
            for candidate in \
                "/Applications/DJI Assistant 2(Consumer Drones Series).app" \
                "${HOME}/Applications/DJI Assistant 2(Consumer Drones Series).app" \
                "/Applications/DJI Assistant 2.app" \
                "${HOME}/Applications/DJI Assistant 2.app"
            do
                [ -d "$candidate" ] && echo "$candidate" && return 0
            done
            ;;
    esac
    for candidate in "/Applications/${app_name}.app" "${HOME}/Applications/${app_name}.app"; do
        [ -d "$candidate" ] && echo "$candidate" && return 0
    done
    echo "/Applications/${app_name}.app"
}

internet_app_snapshot_version() {
    local app_path="$1" ver
    ver=$(defaults read "$app_path/Contents/Info" CFBundleShortVersionString 2>/dev/null \
        || defaults read "$app_path/Contents/Info" CFBundleVersion 2>/dev/null \
        || true)
    if [ -z "$ver" ]; then
        # iOS/iPadOS apps on Apple Silicon can be wrapped without a
        # Contents/Info plist. Spotlight still exposes their version.
        ver=$(mdls -raw -name kMDItemVersion "$app_path" 2>/dev/null || true)
        [ "$ver" = "(null)" ] && ver=""
    fi
    [ -n "$ver" ] && echo "$ver" || echo "?"
}

internet_firefox_snapshot_version() {
    local ini="/Applications/Firefox Developer Edition.app/Contents/Resources/application.ini"
    if [ -f "$ini" ]; then
        grep "^Version=" "$ini" 2>/dev/null | head -1 | cut -d= -f2
    else
        internet_app_snapshot_version "/Applications/Firefox Developer Edition.app"
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
                ver="$(internet_app_snapshot_version "$app_path")"
            fi
            echo "${app_name}|${ver}" >> "$outfile"
        fi
    done
}
