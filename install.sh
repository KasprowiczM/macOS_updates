#!/usr/bin/env bash
# ============================================================
# install.sh — One-line installer for new macOS users
# ============================================================
#
# Copy and paste on a new Apple Silicon Mac:
#
#   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
#
# Optional environment variables:
#   MAC_UPDATE_DIR=/path/to/clone   (default: ~/Dev_Env/macOS_updates)
#   MAC_UPDATE_REPO=git URL         (default: GitHub repo below)
#   MAC_UPDATE_LANG=en              (skip language picker: en|pl|de|fr|es|it|pt)
#   MAC_UPDATE_SKIP_INVENTORY=1     (skip build_inventory.sh)
#
# Flow: pre-clone checks in English → clone → language picker (EN menu) →
#       localized messages for setup, inventory, and coverage report.
# ============================================================
set -o pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

MAC_UPDATE_REPO="${MAC_UPDATE_REPO:-https://github.com/KasprowiczM/macOS_updates.git}"
MAC_UPDATE_DIR="${MAC_UPDATE_DIR:-$HOME/Dev_Env/macOS_updates}"

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    echo "macOS Updates v1.0.21 — Automated update system (Bash 3.2+ with a Python 3 backend in dev_sync/ and inline pipeline helpers)"
    echo "Usage: bash install.sh [--help]"
    exit 0
fi

info()  { echo -e "  ${CYAN}ℹ️  $1${NC}"; }
ok()    { echo -e "  ${GREEN}✅ $1${NC}"; }
fail()  { echo -e "  ${RED}❌ $1${NC}"; exit 1; }

# Pre-clone messages stay English (i18n files not available yet).
echo ""
echo -e "${BOLD}macOS Updates — installer${NC}"
echo ""

ARCH="$(uname -m 2>/dev/null || echo unknown)"
if [ "$ARCH" != "arm64" ]; then
    fail "Apple Silicon (arm64) required. This toolkit does not support Intel Macs."
fi

MAJOR="$(sw_vers -productVersion 2>/dev/null | cut -d. -f1)"
if [ -n "$MAJOR" ] && [ "$MAJOR" -lt 13 ] 2>/dev/null; then
    fail "macOS 13 Ventura or later required."
fi

if ! command -v git >/dev/null 2>&1; then
    info "git not found — installing Xcode Command Line Tools (may open a dialog)..."
    xcode-select --install 2>/dev/null || true
    fail "Install Xcode Command Line Tools, then re-run the installer."
fi

PARENT_DIR="$(dirname "$MAC_UPDATE_DIR")"
mkdir -p "$PARENT_DIR" || fail "Cannot create $PARENT_DIR"

if [ -d "$MAC_UPDATE_DIR/.git" ]; then
    info "Updating existing clone: $MAC_UPDATE_DIR"
    git -C "$MAC_UPDATE_DIR" pull --ff-only origin main 2>/dev/null \
        || git -C "$MAC_UPDATE_DIR" pull --ff-only 2>/dev/null \
        || fail "git pull failed in $MAC_UPDATE_DIR"
else
    info "Cloning into $MAC_UPDATE_DIR"
    git clone "$MAC_UPDATE_REPO" "$MAC_UPDATE_DIR" || fail "git clone failed"
fi

cd "$MAC_UPDATE_DIR" || fail "Cannot cd to $MAC_UPDATE_DIR"

SCRIPT_DIR="$MAC_UPDATE_DIR"
export SCRIPT_DIR
. "$SCRIPT_DIR/i18n/loader.sh"

# Language: English default; picker menu is English; then reload chosen locale.
if [ -n "${MAC_UPDATE_LANG:-}" ]; then
    save_language_pref "$MAC_UPDATE_LANG"
    MAC_LANG="$MAC_UPDATE_LANG"
    # shellcheck disable=SC1090
    . "$SCRIPT_DIR/i18n/loader.sh"
elif ! grep -q "^MAC_LANG=" "$SCRIPT_DIR/.mac_update_prefs" 2>/dev/null; then
    print_info() { echo -e "  ${CYAN}ℹ️  $1${NC}"; }
    print_info "$L_LANG_PICKER_INTRO"
    CHOSEN_LANG=$(ask_language_picker)
    save_language_pref "$CHOSEN_LANG"
    MAC_LANG="$CHOSEN_LANG"
    # shellcheck disable=SC1090
    . "$SCRIPT_DIR/i18n/loader.sh"
fi

echo ""
echo -e "${BOLD}${L_INSTALLER_TITLE}${NC}"
echo ""

# Never import private overlay on fresh install — each user builds their own inventory.
if [ -f "$MAC_UPDATE_DIR/.dev_sync_config.json" ]; then
    info "$L_INSTALLER_SKIP_DEVSYNC"
fi

info "$L_INSTALLER_RUNNING_SETUP"
export MAC_UPDATE_NONINTERACTIVE=1
bash "$MAC_UPDATE_DIR/setup.sh" || fail "$L_INSTALLER_SETUP_FAILED"

if [ "${MAC_UPDATE_SKIP_INVENTORY:-0}" != "1" ]; then
    info "$L_INSTALLER_BUILDING_INVENTORY"
    bash "$MAC_UPDATE_DIR/build_inventory.sh" -y || fail "$L_INSTALLER_INVENTORY_FAILED"
fi

info "$L_INSTALLER_COVERAGE_REPORT"
bash "$MAC_UPDATE_DIR/scripts/report_update_coverage.sh" || true

VER="$(tr -d '[:space:]' < "$MAC_UPDATE_DIR/VERSION" 2>/dev/null || echo unknown)"
echo ""
ok "$(printf "$L_INSTALLER_READY" "$VER" "$MAC_UPDATE_DIR")"
echo ""
echo -e "  ${BOLD}${L_INSTALLER_NEXT_STEPS}${NC}"
echo "    cd $MAC_UPDATE_DIR"
echo "    bash update_all.sh --dry-run -y    # preview"
echo "    bash update_all.sh -y              # full update"
echo "    bash run_tests.sh                  # verify"
echo ""
echo "  $L_INSTALLER_ONLY_INSTALLED"
echo "  $(printf "$L_INSTALLER_ADD_APPS_HINT" "$MAC_LANG")"
echo ""
