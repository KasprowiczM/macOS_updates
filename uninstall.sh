#!/usr/bin/env bash
# ============================================================
# uninstall.sh — Remove macOS Updates from this Mac
# ============================================================
# Does NOT uninstall Homebrew, mas, or any applications.
# Removes only this repository clone and optional local prefs.
#
# Usage:
#   bash uninstall.sh
#   bash uninstall.sh --purge   # also remove .mac_update_prefs in repo
# ============================================================
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PURGE=0
[ "${1:-}" = "--purge" ] && PURGE=1

. "$SCRIPT_DIR/i18n/loader.sh"

echo ""
echo "  $L_UNINSTALL_TITLE"
echo "  $L_UNINSTALL_REPO $SCRIPT_DIR"
echo ""
echo "  $L_UNINSTALL_NOTE"
echo ""
read -r -p "  $L_UNINSTALL_CONFIRM [y/N]: " CONFIRM
CONFIRM="${CONFIRM:-N}"
if ! [[ "$CONFIRM" =~ ^[Yy] ]]; then
    echo "  $L_CANCELED"
    exit 0
fi

if [ "$PURGE" = "1" ] && [ -f "$SCRIPT_DIR/.mac_update_prefs" ]; then
    rm -f "$SCRIPT_DIR/.mac_update_prefs"
    echo "  $L_UNINSTALL_PURGED"
fi

PARENT="$SCRIPT_DIR"
cd "$(dirname "$SCRIPT_DIR")" || exit 1
# Safety guard: refuse to rm -rf if PARENT is root, home, or too shallow
case "$PARENT" in
    ""|"/"|"/Users"|"/Users/"*[!/]*[!/]) ;;  # these are fine (specific subdirectories)
    *)
        # Additional check: require at least 3 path components (e.g. /Users/mk/something)
        _depth=$(echo "$PARENT" | tr -cd '/' | wc -c)
        if [ "$_depth" -lt 3 ]; then
            echo "  SAFETY: refusing to rm -rf '$PARENT' (too shallow)"
            exit 1
        fi
        ;;
esac
if [ -z "$PARENT" ] || [ "$PARENT" = "/" ]; then
    echo "  SAFETY: refusing to delete root or empty path"
    exit 1
fi
rm -rf "$PARENT" 2>/dev/null || rm -rf "$SCRIPT_DIR" 2>/dev/null || {
    echo "  $L_UNINSTALL_MANUAL"
    echo "    rm -rf $SCRIPT_DIR"
    exit 1
}

echo "  $L_UNINSTALL_DONE"
echo ""
