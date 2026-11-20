#!/usr/bin/env bash
# lib/fetch.sh — bounded HTTPS downloads (curl, HTTPS-only incl. redirects).
# fetch_reviewed_artifact is the plan-bound API of the optional policy engine;
# the update steps use fetch_to_file.
_FETCH_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

fetch_to_file() {
    local url="$1"
    local dest="$2"
    local timeout_s="${3:-60}"
    local max_bytes="${4:-10485760}"
    local tmp=""

    if [ -z "$url" ] || [ -z "$dest" ]; then
        return 1
    fi
    case "$url" in
        https://*) ;;
        *) return 1 ;;
    esac
    tmp="${dest}.part"
    rm -f "$tmp" "$dest"
    if ! curl -fsSL --proto =https --proto-redir =https --tlsv1.2 --max-filesize "$max_bytes" --max-time "$timeout_s" --retry 2 --retry-delay 1 \
        -o "$tmp" "$url"; then
        rm -f "$tmp"
        return 1
    fi
    if [ ! -s "$tmp" ]; then
        rm -f "$tmp"
        return 1
    fi
    if [ "$(wc -c < "$tmp" | tr -d ' ')" -gt "$max_bytes" ]; then
        rm -f "$tmp"
        return 1
    fi
    mv "$tmp" "$dest"
    return 0
}

# fetch_reviewed_artifact URL DEST TIMEOUT MAX_BYTES ACTION_ID ARTIFACT
# The reviewed catalog, never the response URL or caller host, sets the allowlist.
fetch_reviewed_artifact() {
    [ -n "${5:-}" ] && [ -n "${6:-}" ] && [ -n "${MAC_UPDATE_PLAN_PATH:-}" ] || return 10
    PYTHONPATH="$_FETCH_LIB_DIR/python${PYTHONPATH:+:$PYTHONPATH}" python3 - "$1" "$2" "$3" "$4" "$5" "$6" "$MAC_UPDATE_PLAN_PATH" "$_FETCH_LIB_DIR/../config/app_recipes.json" <<'PY'
import sys
from download_policy import download, reviewed_artifact_hosts
from app_recipes import load_recipes
from policy_runtime import load_plan, guard_action
try:
    plan=load_plan(sys.argv[7])
    actions=[a for a in plan['actions'] if a.get('action_id')==sys.argv[5]]
    if len(actions)!=1: sys.exit(10)
    action=actions[0]
    hosts=reviewed_artifact_hosts(action,load_recipes(sys.argv[8]),sys.argv[6])
    if not guard_action(sys.argv[7],sys.argv[5]).get('allowed'): sys.exit(10)
    download(sys.argv[1],sys.argv[2],hosts,timeout=int(sys.argv[3]),max_bytes=int(sys.argv[4]))
except Exception:
    sys.exit(10)
PY
}
