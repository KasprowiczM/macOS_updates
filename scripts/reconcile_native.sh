#!/usr/bin/env bash
# Explicit user-reported recovery for delegated native vendor updater sessions.
set -o pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
[ "$#" -eq 0 ] || exit 1
. "$SCRIPT_DIR/i18n/loader.sh"
. "$SCRIPT_DIR/lib/platform.sh"
mac_update_tool_usable python3 || { printf '%s\n' "$L_CATALOG_PYTHON_REQUIRED" >&2; exit 2; }
PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" \
    exec python3 -c 'import sys; from policy_runtime import main; sys.exit(main(["reconcile-native"]))'
