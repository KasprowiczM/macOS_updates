#!/usr/bin/env bash
# ============================================================
# build_inventory.sh — Build APPLICATIONS.md from this Mac only
# ============================================================
# Scans installed apps (Applications, mas, Homebrew) and writes or
# updates APPLICATIONS.md. Never installs apps or copies another user's
# catalog. Safe for new users after install.sh / setup.sh.
#
# Usage:
#   bash build_inventory.sh
#   bash build_inventory.sh --dry-run
#   bash build_inventory.sh --shadow [--dry-run] [--json] [--root PATH ...]
# ============================================================
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/lib/platform.sh"
mac_update_require_supported_platform || exit 1

if [ "${1:-}" = "--shadow" ]; then
    shift
    . "$SCRIPT_DIR/i18n/loader.sh"
    export L_SHADOW_REPORT L_SHADOW_NO_ACTIONS L_SHADOW_PARTIAL L_SHADOW_FAILED
    mac_update_tool_usable python3 || { printf '%s\n' "$L_SHADOW_FAILED"; exit 10; }
    python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || exit 10
    PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" python3 - "$SCRIPT_DIR" "$@" <<'PYEOF_SHADOW'
import sys
from inventory_shadow import main
sys.exit(main(sys.argv[1], sys.argv[2:]))
PYEOF_SHADOW
    exit $?
fi

if [ "${1:-}" = "--dry-run" ]; then
    export MAC_UPDATE_DRY_RUN=1
fi

export MAC_UPDATE_SKIP_SYSTEM=1
export MAC_UPDATE_SKIP_APPSTORE=1
export MAC_UPDATE_SKIP_NPM=1
export MAC_UPDATE_SKIP_BREW=1
export MAC_UPDATE_SKIP_INTERNET=1
export MAC_UPDATE_SKIP_POSTUPDATE=0
export MAC_UPDATE_SKIP_DOCTOR=1
export MAC_UPDATE_INVENTORY_ONLY=1
export MAC_UPDATE_YES=1

exec bash "$SCRIPT_DIR/update_all.sh" "$@"
