#!/usr/bin/env bash
# scripts/check_vendor_feeds.sh — Query vendor feeds and Omaha updaters (Bash 3.2+)
# Read-only — does NOT install, download, or modify anything.
# Usage: bash scripts/check_vendor_feeds.sh [--json]
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Source libraries
# shellcheck source=lib/ui.sh
. "$SCRIPT_DIR/lib/ui.sh"
# shellcheck source=lib/vendor_feeds.sh
. "$SCRIPT_DIR/lib/vendor_feeds.sh"
# shellcheck source=lib/internet_apps.sh
. "$SCRIPT_DIR/lib/internet_apps.sh"
# shellcheck source=lib/version.sh
. "$SCRIPT_DIR/lib/version.sh"

JSON_MODE=0
for arg in "$@"; do
    case "$arg" in
        --json) JSON_MODE=1 ;;
    esac
done

CFG_FILE="$(vendor_feed_config_path)"
if [ ! -f "$CFG_FILE" ]; then
    print_error "Configuration file not found: $CFG_FILE"
    exit 0
fi

# Python helper to inspect Omaha logs
get_omaha_status() {
    local appid="$1"
    shift
    PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" python3 - "$appid" "$@" <<'PYEOF_OMAHA'
import sys
from pathlib import Path
from vendor_feeds import omaha_last_status

appid = sys.argv[1]
log_paths = sys.argv[2:]

status = None
for p_str in log_paths:
    p = Path(p_str)
    p_old = Path(f"{p_str}.old")
    txt_parts = []
    if p_old.is_file():
        try:
            txt_parts.append(p_old.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            pass
    if p.is_file():
        try:
            txt_parts.append(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            pass
    if txt_parts:
        st = omaha_last_status("".join(txt_parts), appid)
        if st:
            status = st
            break

print(status or "-")
PYEOF_OMAHA
}

# Collect vendor feed data for installed apps
# Data format: app|installed|vendor|relation|artifact_host
DATA_LINES=()

while IFS= read -r line || [ -n "$line" ]; do
    line_clean=$(printf '%s' "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    case "$line_clean" in
        ''|'#'*) continue ;;
    esac
    IFS='|' read -r app_name kind url arg artifact host <<EOF
$line_clean
EOF
    [ -n "$app_name" ] || continue

    app_path="$(internet_app_path "$app_name")"
    if [ ! -d "$app_path" ]; then
        continue
    fi

    inst_ver="$(internet_app_snapshot_version "$app_path")"
    [ -z "$inst_ver" ] && inst_ver="-"

    vf_res="$(vendor_feed_lookup "$app_name" 2>/dev/null || true)"
    vend_ver="-"
    relation="unknown"
    art_host="${host:--}"

    if [ -n "$vf_res" ]; then
        IFS='|' read -r v_ver v_url v_ck_kind v_ck v_art v_host <<EOF
$vf_res
EOF
        [ -n "$v_ver" ] && [ "$v_ver" != "-" ] && vend_ver="$v_ver"
        [ -n "$v_host" ] && [ "$v_host" != "-" ] && art_host="$v_host"

        if [ "$inst_ver" != "-" ] && [ "$vend_ver" != "-" ]; then
            cmp_res="$(version_cmp "$inst_ver" "$vend_ver" 2>/dev/null || echo "unknown")"
            case "$cmp_res" in
                newer) relation="feed_stale" ;;
                equal) relation="equal" ;;
                older) relation="behind" ;;
                *) relation="unknown" ;;
            esac
        fi
    fi

    DATA_LINES+=("$app_name|$inst_ver|$vend_ver|$relation|$art_host")
done < "$CFG_FILE"

# Omaha apps: Chrome, Gemini, Google Drive, Comet
GOOGLE_LOG_USER="$HOME/Library/Application Support/Google/GoogleUpdater/updater.log"
GOOGLE_LOG_SYS="/Library/Application Support/Google/GoogleUpdater/updater.log"
COMET_LOG_USER="$HOME/Library/Application Support/Perplexity/CometUpdater/updater.log"

OMAHA_APPS=(
    "Google Chrome|com.google.chrome|$GOOGLE_LOG_USER|$GOOGLE_LOG_SYS"
    "Gemini|com.google.geminimacos|$GOOGLE_LOG_USER|$GOOGLE_LOG_SYS"
    "Google Drive|com.google.drivefs|$GOOGLE_LOG_USER|$GOOGLE_LOG_SYS"
    "Comet|ai.perplexity.comet|$COMET_LOG_USER"
)

OMAHA_DATA=()
for row in "${OMAHA_APPS[@]}"; do
    IFS='|' read -r o_name o_appid o_l1 o_l2 <<EOF
$row
EOF
    o_status="$(get_omaha_status "$o_appid" "$o_l1" "${o_l2:-}")"
    o_path="$(internet_app_path "$o_name")"
    o_inst="-"
    if [ -d "$o_path" ]; then
        o_inst="$(internet_app_snapshot_version "$o_path")"
        [ -z "$o_inst" ] && o_inst="-"
    fi
    OMAHA_DATA+=("$o_name|$o_inst|$o_appid|$o_status")
done

if [ "$JSON_MODE" -eq 1 ]; then
    PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" python3 - <<'PYEOF_JSON' "${DATA_LINES[@]}" "---OMAHA---" "${OMAHA_DATA[@]}"
import sys
import json

args = sys.argv[1:]
idx = args.index("---OMAHA---") if "---OMAHA---" in args else len(args)
vendor_rows = args[:idx]
omaha_rows = args[idx+1:] if idx < len(args) else []

items = []
for row in vendor_rows:
    parts = row.split("|")
    if len(parts) >= 5:
        items.append({
            "app": parts[0],
            "installed": parts[1] if parts[1] != "-" else None,
            "vendor": parts[2] if parts[2] != "-" else None,
            "relation": parts[3] if parts[3] != "unknown" else None,
            "artifact_host": parts[4] if parts[4] != "-" else None,
            "omaha_status": None,
        })

for row in omaha_rows:
    parts = row.split("|")
    if len(parts) >= 4:
        items.append({
            "app": parts[0],
            "installed": parts[1] if parts[1] != "-" else None,
            "appid": parts[2],
            "vendor": None,
            "relation": None,
            "artifact_host": None,
            "omaha_status": parts[3] if parts[3] != "-" else None,
        })

print(json.dumps(items, indent=2))
PYEOF_JSON
    exit 0
fi

# Text / Table Output
echo "=========================================================================================="
echo "Vendor Feeds Truth Table"
echo "=========================================================================================="
printf "%-25s | %-15s | %-15s | %-12s | %s\n" "App" "installed" "vendor" "relation" "artifact host"
printf '%0.s─' {1..90}
echo ""

for row in "${DATA_LINES[@]}"; do
    IFS='|' read -r a_name a_inst a_vend a_rel a_host <<EOF
$row
EOF
    printf "%-25s | %-15s | %-15s | %-12s | %s\n" "$a_name" "$a_inst" "$a_vend" "$a_rel" "$a_host"
done

echo ""
echo "=========================================================================================="
echo "Omaha Updater Status (Google / Perplexity)"
echo "=========================================================================================="
printf "%-18s | %-15s | %-25s | %s\n" "App" "installed" "App ID" "Last Omaha Status"
printf '%0.s─' {1..80}
echo ""

for row in "${OMAHA_DATA[@]}"; do
    IFS='|' read -r o_name o_inst o_appid o_status <<EOF
$row
EOF
    printf "%-18s | %-15s | %-25s | %s\n" "$o_name" "$o_inst" "$o_appid" "$o_status"
done

exit 0
