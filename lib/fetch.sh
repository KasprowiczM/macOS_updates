#!/usr/bin/env bash
# Bounded public HTTPS metadata transport. Reviewed artifacts use a distinct API.
_FETCH_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

fetch_to_file() {
    [ -n "${1:-}" ] && [ -n "${2:-}" ] || return 1
    PYTHONPATH="$_FETCH_LIB_DIR/python${PYTHONPATH:+:$PYTHONPATH}" python3 - "$1" "$2" "${3:-60}" "${4:-10485760}" <<'PY'
import sys
from download_policy import download
try:
    download(sys.argv[1],sys.argv[2],None,timeout=int(sys.argv[3]),max_bytes=int(sys.argv[4]))
except Exception:
    # Request URLs can carry credentials; neither URL nor transport exceptions
    # are diagnostic output.
    sys.exit(1)
PY
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
