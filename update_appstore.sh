#!/usr/bin/env bash
# ============================================================
# SKRYPT 2: Aktualizacja aplikacji z Mac App Store
# ============================================================
# Autor: Antigravity AI | Zaktualizowano: 2026-03-31
set -o pipefail

# Jeśli MAC_UPDATE_SESSION_DIR jest ustawiony, zapisuje snapshoty
# mas list przed i po aktualizacji.
#
# Strategia dwutorowa:
#   TOR 1 — sudo mas upgrade
#     Aktualizuje wszystkie natywne aplikacje macOS z App Store.
#     Wymaga sudo (macOS 26.x, CVE-2025-43411).
#
#   TOR 2 — Automatyzacja GUI App Store (AppleScript)
#     Aktualizuje aplikacje iPad na Apple Silicon (np. UniFi,
#     WiFiman, myCANAL), których mas jawnie nie obsługuje.
#     Wymaga jednorazowego uprawnienia Accessibility dla terminala.
#
# Wymagania:
#   - Homebrew  (wykrywany automatycznie)
#   - mas 4.0+  (instalowany/aktualizowany automatycznie)
#   - sudo      (hasło przy mas upgrade)
#   - Accessibility dla terminala (sprawdzane i instruowane)
#
# Zmienne środowiskowe:
#   MAS_NO_AUTO_INDEX=1  — wyłącza auto-indeksowanie Spotlight przez mas
#     (domyślnie włączone tu, eliminuje ściany ostrzeżeń o niewindeksowanych
#      aplikacjach App Store przy każdym wywołaniu mas list/upgrade/outdated)
# ============================================================

# Kolory
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Katalog z skryptami
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

. "$SCRIPT_DIR/lib/platform.sh"
mac_update_require_apple_silicon || exit 1

# ── i18n: load language strings ──────────────────────────────
. "$SCRIPT_DIR/lib/cli.sh"
. "$SCRIPT_DIR/lib/ui.sh"
. "$SCRIPT_DIR/i18n/loader.sh"

print_header() { ui_print_header "$1"; }
print_ok()    { echo -e "  ${GREEN}✅ $1${NC}"; }
print_info()  { echo -e "  ${CYAN}ℹ️  $1${NC}"; }
print_warn()  { echo -e "  ${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "  ${RED}❌ $1${NC}"; }
print_step()  { echo -e "  ${BOLD}▶  $1${NC}"; }

# Suppress mas Spotlight auto-indexing warnings
# (apps not yet indexed in Spotlight trigger noisy warnings on every mas call)
export MAS_NO_AUTO_INDEX=1
APPSTORE_EXIT=0

# ============================================================
print_header "$L_SCRIPT_TITLE_APPSTORE"
if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
    print_warn "DRY-RUN mode — App Store updates will not run"
fi

# ============================================================
# STEP 0: Check and install mas
# ============================================================
print_header "Checking mas tool..."

if ! command -v brew &> /dev/null; then
    print_error "$L_HOMEBREW_NOT_FOUND"
    print_info "$L_INSTALL_HOMEBREW_URL"
    exit 1
fi

if ! command -v mas &> /dev/null; then
    print_warn "$L_MAS_INSTALLING"
    brew install mas
    print_ok "$L_MAS_INSTALLED"
fi

# Check version — only update if < 4.0 (avoid slow brew update)
MAS_VER=$(mas version 2>/dev/null || echo "0.0.0")
MAS_MAJOR=$(echo "$MAS_VER" | cut -d'.' -f1)
print_ok "$L_MAS_VERSION $MAS_VER"

if [ "${MAS_MAJOR:-0}" -lt 4 ] 2>/dev/null; then
    print_warn "$L_MAS_VERSION_OLD"
    HOMEBREW_NO_AUTO_UPDATE=1 brew upgrade mas 2>/dev/null || brew upgrade mas
    MAS_VER=$(mas version 2>/dev/null || echo "?")
    print_ok "$L_MAS_VERSION_UPDATED $MAS_VER"
fi

# ============================================================
# STEP 1: Check App Store login
# ============================================================
print_header "$L_APPSTORE_CHECK"

# mas account is unstable on macOS 26.x — use mas list as test
ACCOUNT=$(mas account 2>/dev/null || echo "")
if [ -n "$ACCOUNT" ]; then
    print_ok "$L_APPSTORE_LOGIN_CHECK $ACCOUNT"
else
    print_warn "$L_APPSTORE_LOGIN_UNSTABLE"
    print_info "$L_APPSTORE_VERIFY_ACCESS"
fi

if ! mas list &> /dev/null; then
    print_error "$L_APPSTORE_NO_ACCESS"
    print_info "$L_APPSTORE_LOGIN_MANUALLY"
    open -a "App Store"
    exit 1
fi
print_ok "$L_APPSTORE_ACCESS_CONFIRMED"

# ============================================================
# STEP 2: LIST INSTALLED APPS
# ============================================================
print_header "$L_INSTALLED_APPS"
print_info "$L_IPAD_APPS_NOTE"
echo ""
mas list
echo ""

# ============================================================
# STEP 3: CONFIRMATION
# ============================================================
echo -e "${YELLOW}  $L_RUN_TWO_TRACKS${NC}"
echo "    $L_TOR_1_HEADER"
echo "    $L_TOR_2_HEADER"
echo ""
print_warn "$L_TOR_1_SUDO_MSG"
print_warn "$L_AX_PERMISSION_CHECK"
echo ""
if [ "${MAC_UPDATE_YES:-0}" != "1" ]; then
    read -r -p "  $L_CONFIRM_UPDATE [T/n]: " CONFIRM
    CONFIRM="${CONFIRM:-T}"
    if [[ "$CONFIRM" =~ ^[Nn] ]]; then
        print_info "$L_UPDATE_CANCELED"
        exit 0
    fi
fi

if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
    print_info "[DRY-RUN] Would run: sudo mas upgrade"
    print_info "[DRY-RUN] Would run: App Store GUI automation (AppleScript)"
    exit 0
fi

# ============================================================
# TRACK 1: sudo mas upgrade (native macOS apps)
# ============================================================
print_header "$L_TOR_1_HEADER"
print_info "$L_TOR_1_SUDO_MSG"
echo ""

# ── mas snapshot BEFORE update ───────────────────────────────
if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
    print_info "$L_SNAPSHOT_BEFORE"
    mas list 2>/dev/null > "$MAC_UPDATE_SESSION_DIR/mas_before.txt" || true
fi

MAS_TOR1_OUT=$(sudo env MAS_NO_AUTO_INDEX=1 mas upgrade 2>&1)
MAS_TOR1_EXIT=$?
if [ "$MAS_TOR1_EXIT" -eq 0 ]; then
    printf '%s\n' "$MAS_TOR1_OUT"
    print_ok "$L_TOR_1_COMPLETE"
else
    printf '%s\n' "$MAS_TOR1_OUT"
    print_warn "$L_TOR_1_ERROR"
    APPSTORE_EXIT=1
    if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ]; then
        {
            echo "=== TRACK 1 (sudo mas upgrade) FAILED ==="
            echo "exit=$MAS_TOR1_EXIT"
            echo "--- output ---"
            printf '%s\n' "$MAS_TOR1_OUT"
        } >> "$MAC_UPDATE_SESSION_DIR/appstore_diag.txt" 2>/dev/null || true
    fi
fi

# ============================================================
# TRACK 2: App Store GUI automation (iPad apps and others)
# ============================================================
print_header "$L_TOR_2_HEADER"
print_info "$L_TOR_2_IPAD_NOTE"
print_info "$L_TOR_2_SOLUTION"
echo ""
print_step "$L_AX_PERMISSION_CHECK"

# Test uprawnień Accessibility (szybki, nieinwazyjny)
AX_TEST=$(osascript -e 'tell application "System Events" to return name of first process whose frontmost is true' 2>&1)

if echo "$AX_TEST" | grep -qi "not allowed\|assistive\|accessibility\|access"; then
    echo ""
    print_error "$L_AX_PERMISSION_DENIED"
    echo ""
    echo -e "  ${BOLD}$L_AX_FIX_STEPS${NC}"
    echo "    $L_AX_FIX_STEP_1"
    echo "    $L_AX_FIX_STEP_2"
    echo "       • Terminal.app  → /Applications/Utilities/Terminal.app"
    echo "       • Warp.app      → /Applications/Warp.app"
    echo "       • iTerm.app     → /Applications/iTerm.app"
    echo "    $L_AX_FIX_STEP_3"
    echo ""
    print_info "$L_AX_OPEN_SETTINGS"
    open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
    echo ""
    print_warn "$L_AX_RERUN_SCRIPT"
    print_warn "$L_SCRIPT_2_SUMMARY_TOR1"
    echo ""
    print_header "⚠️  SCRIPT 2 FINISHED — ACCESSIBILITY CONFIGURATION REQUIRED"
    exit 2
fi

print_ok "$L_AX_COMPLETE"
echo ""
print_step "$L_APPSTORE_OPEN"

# AppleScript: otwórz App Store Updates i kliknij "Update All" lub indywidualne "Update"
AS_RESULT=$(osascript 2>&1 <<'APPLESCRIPT'

-- Otwórz App Store i przejdź do sekcji Uaktualnienia
tell application "App Store" to activate
delay 2
open location "macappstores://showUpdatesPage"
delay 6

tell application "System Events"
    tell process "App Store"
        set frontmost to true
        delay 2

        -- ── PASS 1: szybkie szukanie "Update All" w top-level i grupach ──
        set candidates to {}
        try
            set candidates to candidates & (buttons of window 1)
        end try
        try
            repeat with grp in (groups of window 1)
                try
                    set candidates to candidates & (buttons of grp)
                end try
            end repeat
        end try

        repeat with btn in candidates
            try
                if name of btn contains "Update All" then
                    click btn
                    delay 2
                    return "UPDATE_ALL_CLICKED"
                end if
            end try
        end repeat

        -- ── PASS 2: głębsze szukanie przez cały drzewko UI (wolniejsze) ──
        set found to false
        try
            set allElems to entire contents of window 1
            repeat with elem in allElems
                try
                    if class of elem is button then
                        if name of elem contains "Update All" then
                            click elem
                            set found to true
                            delay 2
                            exit repeat
                        end if
                    end if
                end try
            end repeat
        end try
        if found then return "UPDATE_ALL_DEEP"

        -- ── PASS 3: klikaj indywidualne przyciski "Update" ──
        set updateCount to 0
        try
            set allElems to entire contents of window 1
            repeat with elem in allElems
                try
                    if class of elem is button then
                        set btnName to name of elem
                        -- klikaj "Update" w każdym języku obsługiwanym przez i18n
                        if btnName is "Update" or btnName is "Aktualizuj" or btnName is "Aktualisieren" or btnName is "Actualizar" or btnName is "Aggiorna" or btnName is "Atualizar" or btnName is "Actualiser" or btnName contains "Update" then
                            click elem
                            set updateCount to updateCount + 1
                            delay 1
                        end if
                    end if
                end try
            end repeat
        end try

        if updateCount > 0 then
            return "INDIVIDUAL_UPDATES:" & updateCount
        end if

        return "NO_UPDATES_FOUND"
    end tell
end tell

APPLESCRIPT
)

# ── Interpret result ──
echo ""
APPSTORE_TOR2_BRANCH="unexpected"
if echo "$AS_RESULT" | grep -q "not allowed\|assistive\|Accessibility"; then
    APPSTORE_TOR2_BRANCH="ax_revoked"
    print_warn "$L_APPSTORE_AX_REVOKED"
    print_info "$L_APPSTORE_CHECK_PREFS"
    open "macappstores://showUpdatesPage"

elif echo "$AS_RESULT" | grep -q "^UPDATE_ALL_CLICKED\|^UPDATE_ALL_DEEP"; then
    APPSTORE_TOR2_BRANCH="update_all"
    print_ok "$L_APPSTORE_UPDATE_ALL_CLICKED"
    print_info "$L_APPSTORE_BG_INSTALL"
    print_warn "$L_APPSTORE_WAIT_PROMPT"
    # Send App Store to background; updates continue installing while it's hidden.
    # `hide` keeps the process running (vs. `quit` which would cancel installs).
    osascript -e 'tell application "System Events" to set visible of process "App Store" to false' >/dev/null 2>&1 || true

elif echo "$AS_RESULT" | grep -q "^INDIVIDUAL_UPDATES:"; then
    APPSTORE_TOR2_BRANCH="individual"
    COUNT="${AS_RESULT#INDIVIDUAL_UPDATES:}"
    print_ok "$L_APPSTORE_INDIVIDUAL_UPDATES ($COUNT)"
    print_info "$L_APPSTORE_INSTALLING_BG"
    osascript -e 'tell application "System Events" to set visible of process "App Store" to false' >/dev/null 2>&1 || true

elif echo "$AS_RESULT" | grep -q "^NO_UPDATES_FOUND"; then
    APPSTORE_TOR2_BRANCH="no_updates"
    print_ok "$L_APPSTORE_NO_UPDATES"
    # Nothing to install — quit App Store so it doesn't linger on screen
    osascript -e 'tell application "App Store" to quit' >/dev/null 2>&1 || true

else
    APPSTORE_TOR2_BRANCH="unexpected"
    print_warn "$L_APPSTORE_UNEXPECTED $AS_RESULT"
    print_info "$L_APPSTORE_MANUAL_UPDATE"
    open "macappstores://showUpdatesPage"
fi

# Persist TRACK 2 diagnostic when AppleScript hit a non-success branch
if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] \
    && [ "$APPSTORE_TOR2_BRANCH" != "update_all" ] \
    && [ "$APPSTORE_TOR2_BRANCH" != "individual" ] \
    && [ "$APPSTORE_TOR2_BRANCH" != "no_updates" ]; then
    {
        echo ""
        echo "=== TRACK 2 (App Store GUI automation) branch=$APPSTORE_TOR2_BRANCH ==="
        echo "--- AS_RESULT ---"
        printf '%s\n' "$AS_RESULT"
    } >> "$MAC_UPDATE_SESSION_DIR/appstore_diag.txt" 2>/dev/null || true
fi

# ============================================================
# FINAL VERIFICATION
# ============================================================
print_header "$L_FINAL_CHECK"
STILL_OUTDATED=$(mas outdated 2>/dev/null || echo "")
if [ -z "$STILL_OUTDATED" ]; then
    print_ok "$L_APPSTORE_NO_UPDATES"
else
    print_warn "$L_STILL_OUTDATED"
    echo "$STILL_OUTDATED"
    APPSTORE_EXIT=1
    if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ]; then
        {
            echo ""
            echo "=== FINAL: mas outdated still reports updates ==="
            printf '%s\n' "$STILL_OUTDATED"
        } >> "$MAC_UPDATE_SESSION_DIR/appstore_diag.txt" 2>/dev/null || true
    fi
fi

# ── mas snapshot AFTER update ────────────────────────────────
if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
    print_info "$L_SNAPSHOT_AFTER"
    sleep 3
    mas list 2>/dev/null > "$MAC_UPDATE_SESSION_DIR/mas_after.txt" || true
    print_ok "$L_SNAPSHOTS_SAVED $MAC_UPDATE_SESSION_DIR"
fi

print_header "$L_SCRIPT_2_COMPLETE"
print_info "$L_SCRIPT_2_SUMMARY_TOR1"
print_info "$L_SCRIPT_2_SUMMARY_TOR2"
print_warn "$L_SCRIPT_2_CHECK_WINDOW"
echo ""
exit "$APPSTORE_EXIT"
