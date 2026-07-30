#!/usr/bin/env bash
# ============================================================
# SKRYPT 1: Aktualizacja systemu macOS i aplikacji systemowych
# ============================================================
# Autor: Antigravity AI
# Data:  2026-03-02 (zaktualizowano)
set -o pipefail

# Jeśli MAC_UPDATE_SESSION_DIR jest ustawiony, zapisuje informacje
# o systemie przed i po aktualizacji.
# Kompatybilność: bash 3.2+ (macOS domyślny shell)
# Opis:  Aktualizuje system operacyjny macOS oraz wszystkie
#        aplikacje systemowe dostarczane przez Apple.
# ============================================================

# Kolory do wyświetlania komunikatów
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # Brak koloru

# Katalog z skryptami
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

. "$SCRIPT_DIR/lib/platform.sh"
mac_update_require_supported_platform || exit 1

# ── i18n: load language strings ──────────────────────────────
. "$SCRIPT_DIR/lib/cli.sh"
. "$SCRIPT_DIR/lib/ui.sh"
. "$SCRIPT_DIR/i18n/loader.sh"

print_header() { ui_print_header "$1"; }

print_ok() {
    echo -e "  ${GREEN}✅ $1${NC}"
}

print_info() {
    echo -e "  ${CYAN}ℹ️  $1${NC}"
}

print_warn() {
    echo -e "  ${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "  ${RED}❌ $1${NC}"
}

# ============================================================
# System check
# ============================================================
print_header "$L_SYSTEM_UPDATE_TITLE"
if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
    print_warn "DRY-RUN mode — system updates will not be installed"
fi

echo -e "${CYAN}$L_SYSTEM_CHECKING_VERSION${NC}"
sw_vers

# ── Snapshot systemu PRZED aktualizacją ──────────────────────
if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
    print_info "$L_SYSTEM_SAVING_BEFORE"
    sw_vers > "$MAC_UPDATE_SESSION_DIR/system_before.txt" 2>/dev/null || true
fi

echo ""
print_info "$L_SYSTEM_UPDATES_CHECK"
echo "    • macOS operating system"
echo "    • XProtect (antivirus protection)"
echo "    • Security features"
echo ""

# ============================================================
# Check available updates
# ============================================================
print_header "$L_SYSTEM_UPDATES_CHECK"

UPDATES_EXIT=0
UPDATES=$(LANG=C LC_ALL=C softwareupdate -l 2>&1) || UPDATES_EXIT=$?
echo "$UPDATES"

if [ "$UPDATES_EXIT" -ne 0 ]; then
    print_error "softwareupdate -l failed (exit $UPDATES_EXIT)"
    exit 1
fi

if echo "$UPDATES" | grep -q "No new software available"; then
    print_ok "$L_SYSTEM_UPDATES_NONE"
    echo ""
    exit 0
fi

# ============================================================
# User confirmation
# ============================================================
if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
    print_info "[DRY-RUN] Would run: sudo softwareupdate -ia -R --verbose"
    exit 0
fi

echo ""
print_warn "$L_SYSTEM_WARNING_TIME"
print_warn "$L_SYSTEM_WARNING_RESTART"
echo ""
if [ "${MAC_UPDATE_YES:-0}" != "1" ]; then
    read -r -p "  $L_CONTINUE_PROMPT [T/n]: " CONFIRM
    CONFIRM="${CONFIRM:-T}"
    if [[ "$CONFIRM" =~ ^[Nn] ]]; then
        print_info "$L_UPDATE_CANCELED"
        exit 0
    fi
fi

# ============================================================
# Install system updates
# ============================================================
print_header "$L_SOFTWAREUPDATE_RUN"

echo -e "${CYAN}$L_SYSTEM_PLEASE_WAIT${NC}"
echo ""

# Aktualizuje wszystkie dostępne pakiety systemowe
# Wymaga sudo — system poprosi o hasło
#
# WAŻNE: flaga -R (--restart) jest wymagana dla aktualizacji macOS!
# Bez niej softwareupdate pobiera pliki aktualizacji, ale NIE ustawia
# metadanych rozruchowych potrzebnych do ich zastosowania podczas restartu.
# Flaga -R powoduje, że macOS zamknie aplikacje, wyloguje użytkownika
# i zrestartuje komputer przez właściwy mechanizm aktualizacji.
#
# BŁĄD: "sudo reboot" to surowy restart jądra — omija mechanizm
# aktualizacji macOS i dlatego aktualizacje nie są stosowane przy restarcie.

# Sprawdź czy któraś aktualizacja wymaga restartu (użyj już pobranego wyniku,
# zamiast ponownie odpytywać softwareupdate).
NEEDS_RESTART=false
if echo "$UPDATES" | grep -qi "restart"; then
    NEEDS_RESTART=true
fi

if [ "$NEEDS_RESTART" = true ]; then
    echo ""
    print_warn "$L_SYSTEM_RESTART_REQUIRED"
    print_info "$L_SYSTEM_RESTART_AFTER_INFO"
    if [ "${MAC_UPDATE_YES:-0}" = "1" ]; then
        AUTO_RESTART="T"
    else
        read -r -p "  $L_SYSTEM_CONFIRM_RESTART " AUTO_RESTART
        AUTO_RESTART="${AUTO_RESTART:-T}"
    fi
    if [[ "$AUTO_RESTART" =~ ^[Nn] ]]; then
        print_error "Restart-required macOS updates will not be installed without softwareupdate -R."
        print_info "$L_SYSTEM_RESTART_MECHANISM"
        print_warn "$L_SYSTEM_REMEMBER_RESTART"
        exit 1
    else
        print_info "$L_SYSTEM_RESTART_MECHANISM"
        # -R uruchamia właściwy restart macOS (nie surowy reboot),
        # który stosuje aktualizację podczas ponownego uruchomienia
        if sudo softwareupdate -ia -R --verbose; then
            print_ok "$L_SYSTEM_RESTARTING"
        else
            print_warn "$L_SYSTEM_SOME_FAILED"
            exit 1
        fi
    fi
else
    # Brak aktualizacji wymagających restartu — zwykła instalacja
    # Project rule: keep -R on every install. softwareupdate only restarts when required.
    if sudo softwareupdate -ia -R --verbose; then
        print_ok "$L_SYSTEM_DONE_OK"
    else
        print_warn "$L_SYSTEM_SOME_FAILED"
        exit 1
    fi
    print_ok "$L_SYSTEM_NO_RESTART_NEEDED"
fi

# ── Snapshot systemu PO aktualizacji ─────────────────────────
if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
    print_info "$L_SYSTEM_SAVING_AFTER"
    sw_vers > "$MAC_UPDATE_SESSION_DIR/system_after.txt" 2>/dev/null || true
    # Check if version changed
    if [ -f "$MAC_UPDATE_SESSION_DIR/system_before.txt" ]; then
        BEFORE_VER=$(grep ProductVersion "$MAC_UPDATE_SESSION_DIR/system_before.txt" | awk '{print $2}' 2>/dev/null || echo "?")
        AFTER_VER=$(sw_vers -productVersion 2>/dev/null || echo "?")
        if [ "$BEFORE_VER" != "$AFTER_VER" ]; then
            print_ok "$L_SYSTEM_UPGRADED $BEFORE_VER → $AFTER_VER"
            echo "${BEFORE_VER}|${AFTER_VER}" > "$MAC_UPDATE_SESSION_DIR/system_upgrade.txt"
        else
            # Version unchanged: check if an update was staged and requires restart
            if [ "$NEEDS_RESTART" = true ]; then
                print_info "$L_SYSTEM_UPDATE_STAGED $AFTER_VER"
                print_warn "$L_SYSTEM_RESTART_REQUIRED_TO_APPLY"
            else
                print_info "$L_SYSTEM_VERSION_UNCHANGED $AFTER_VER"
            fi
        fi
    fi
fi

echo ""
print_header "$L_SYSTEM_SCRIPT_DONE"
