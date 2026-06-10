#!/usr/bin/env bash
# ============================================================
# SKRYPT 4: Aktualizacja pakietów Homebrew
# ============================================================
# Autor: mk
# Data:  2026-03-18 (zaktualizowano)
set -o pipefail

# Kompatybilność: bash 3.2+ (macOS domyślny shell)
# Opis:  Aktualizuje wszystkie pakiety (formulae) i aplikacje
#        (casks) zainstalowane przez Homebrew.
#        Jeśli MAC_UPDATE_SESSION_DIR jest ustawiony, zapisuje
#        snapshoty wersji przed i po aktualizacji.
# ============================================================

# Kolory
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Katalog z skryptami
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

. "$SCRIPT_DIR/lib/platform.sh"
mac_update_require_apple_silicon || exit 1

# ── i18n: load language strings ──────────────────────────────
. "$SCRIPT_DIR/lib/cli.sh"
. "$SCRIPT_DIR/lib/ui.sh"
. "$SCRIPT_DIR/i18n/loader.sh"

cleanup_brew() {
    [ -f "${BREW_UPGRADE_LOG:-}" ] && rm -f "$BREW_UPGRADE_LOG" 2>/dev/null || true
}
trap cleanup_brew EXIT
trap 'cleanup_brew; exit 130' INT TERM

print_header() { ui_print_header "$1"; }

print_ok()   { echo -e "  ${GREEN}✅ $1${NC}"; }
print_info() { echo -e "  ${CYAN}ℹ️  $1${NC}"; }
print_warn() { echo -e "  ${YELLOW}⚠️  $1${NC}"; }
print_error(){ echo -e "  ${RED}❌ $1${NC}"; }

# ============================================================
print_header "$L_BREW_TITLE"
BREW_EXIT=0
if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
    print_warn "DRY-RUN mode — Homebrew upgrades will not run"
fi

# ============================================================
# Check if Homebrew is installed
# ============================================================
if ! command -v brew &> /dev/null; then
    print_error "$L_BREW_NOT_INSTALLED"
    print_info "Install Homebrew: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    exit 1
fi

BREW_VERSION=$(brew --version | head -1)
print_ok "$BREW_VERSION"
print_info "Location: $(which brew)"

# ── Snapshot of installed packages before update ──
if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
    print_info "$L_BREW_SAVING_BEFORE"
    brew list --formula --versions 2>/dev/null > "$MAC_UPDATE_SESSION_DIR/brew_formulae_before.txt" || true
    brew list --cask --versions 2>/dev/null > "$MAC_UPDATE_SESSION_DIR/brew_casks_before.txt" || true
fi

# ============================================================
# DRY-RUN: list outdated only — do not mutate brew refs
# ============================================================
if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
    print_header "$L_BREW_OUTDATED"
    echo -e "${CYAN}$L_BREW_OUTDATED_LIST${NC}"
    brew outdated --formula 2>/dev/null || true
    echo ""
    echo -e "${CYAN}$L_BREW_CASKS_OUTDATED${NC}"
    brew outdated --cask 2>/dev/null || true
    print_info "[DRY-RUN] Would run: brew update, brew upgrade, cleanup, doctor"
    exit 0
fi

# ============================================================
# STEP 1: Update Homebrew itself
# ============================================================
print_header "$L_BREW_UPDATE"

if brew update; then
    print_ok "$L_BREW_UPDATED"
else
    print_warn "brew update returned warning — continuing anyway."
fi

# ============================================================
# STEP 2: Check outdated packages
# ============================================================
print_header "$L_BREW_OUTDATED"

echo -e "${CYAN}$L_BREW_OUTDATED_LIST${NC}"
OUTDATED_FORMULAE=$(brew outdated --formula 2>/dev/null || echo "")
if [ -z "$OUTDATED_FORMULAE" ]; then
    print_ok "All formulae are up to date!"
else
    echo "$OUTDATED_FORMULAE"
fi

echo ""
echo -e "${CYAN}$L_BREW_CASKS_OUTDATED${NC}"
OUTDATED_CASKS=$(brew outdated --cask 2>/dev/null || echo "")
if [ -z "$OUTDATED_CASKS" ]; then
    print_ok "All casks are up to date!"
else
    echo "$OUTDATED_CASKS"
fi

# Check if there's anything to update
if [ -z "$OUTDATED_FORMULAE" ] && [ -z "$OUTDATED_CASKS" ]; then
    echo ""
    print_ok "$L_BREW_SUMMARY"

    # Still run cleanup
    print_header "$L_BREW_CLEANUP"
    brew cleanup --prune=all 2>/dev/null || brew cleanup
    print_ok "Cleanup completed!"

    # Snapshot PO (identyczny z PRZED — nic się nie zmieniło)
    if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
        brew list --formula --versions 2>/dev/null > "$MAC_UPDATE_SESSION_DIR/brew_formulae_after.txt" || true
        brew list --cask --versions 2>/dev/null > "$MAC_UPDATE_SESSION_DIR/brew_casks_after.txt" || true
    fi

    print_header "$L_BREW_CURRENT"
    exit 0
fi

# ============================================================
# POTWIERDZENIE
# ============================================================
echo ""
if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
    print_info "[DRY-RUN] Would run: brew upgrade --formula / --cask, cleanup, doctor"
    exit 0
fi
print_warn "$L_BREW_PACKAGES_FOUND"
if [ "${MAC_UPDATE_YES:-0}" != "1" ]; then
    read -r -p "  $L_BREW_CONFIRM_UPDATE " CONFIRM
    CONFIRM="${CONFIRM:-T}"
    if [[ "$CONFIRM" =~ ^[Nn] ]]; then
        print_info "$L_BREW_UPDATE_CANCELED"
        exit 0
    fi
fi

# ============================================================
# KROK 3: AKTUALIZACJA FORMULAE
# ============================================================
print_header "$L_BREW_UPGRADE_FORMULAE"

# Capture output so we can detect recoverable link conflicts
# (e.g., "Error: The `brew link` step did not complete successfully" for uv,
# which happens when an unmanaged binary squats on /opt/homebrew/bin/<name>).
BREW_UPGRADE_LOG=$(mktemp "${TMPDIR:-/tmp}/brew_upgrade.XXXXXX")
if brew upgrade --formula 2>&1 | tee "$BREW_UPGRADE_LOG"; then
    print_ok "$L_BREW_FORMULAE_OK"
else
    print_warn "$L_BREW_FORMULAE_WARN"
    BREW_EXIT=1
fi

# ============================================================
# KROK 3.5: AUTO-RECOVERY DLA "BREW LINK DID NOT COMPLETE"
# Wykrywa kegi, które się zainstalowały, ale nie zostały zlinkowane
# (typowo przez kolizję z istniejącym binarnym w /opt/homebrew/bin lub
# /usr/local/bin). Linkowanie z --overwrite jest bezpieczne, bo nadpisuje
# tylko symlink, który i tak należy do tego kega po stronie Cellar.
# ============================================================
LINK_FAILED_KEGS=$(awk '
    /^==> Upgrading / { kegname = $3; sub(/[[:space:]]*$/, "", kegname); next }
    /Error: The .brew link. step did not complete successfully/ {
        if (kegname != "") { print kegname; kegname = "" }
    }
' "$BREW_UPGRADE_LOG" 2>/dev/null | sort -u)
rm -f "$BREW_UPGRADE_LOG" 2>/dev/null || true

if [ -n "$LINK_FAILED_KEGS" ]; then
    print_warn "$L_BREW_LINK_RECOVERY_DETECTED"
    RELINKED=0
    RELINK_FAILED=0
    while IFS= read -r keg; do
        keg=$(echo "$keg" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        [ -z "$keg" ] && continue
        # Reject anything that isn't a plain formula name to keep `brew link` safe
        case "$keg" in
            [a-zA-Z0-9]*) ;;
            *) continue ;;
        esac
        echo -e "  ${CYAN}→ brew link --overwrite $keg${NC}"
        if brew link --overwrite "$keg" >/dev/null 2>&1; then
            print_ok "$L_BREW_LINK_RECOVERED $keg"
            RELINKED=$((RELINKED + 1))
        else
            print_warn "$L_BREW_LINK_FAILED $keg"
            RELINK_FAILED=$((RELINK_FAILED + 1))
        fi
    done <<EOF
$LINK_FAILED_KEGS
EOF
    if [ "$RELINKED" -gt 0 ] && [ "$RELINK_FAILED" -eq 0 ]; then
        # Pełny sukces auto-recovery — wyczyść błąd ustawiony przez brew upgrade
        BREW_EXIT=0
        print_ok "$L_BREW_LINK_RECOVERY_OK"
    fi
fi

# ============================================================
# KROK 4: AKTUALIZACJA CASKS (APLIKACJE GUI)
# ============================================================
print_header "$L_BREW_CASKS_UPGRADE"

# Aktualizuj casks — flaga --no-quarantine usunięta w Homebrew 4.x (była przestarzała)
if brew upgrade --cask; then
    print_ok "$L_BREW_CASKS_OK"
else
    print_warn "$L_BREW_CASKS_WARN"
    BREW_EXIT=1
fi

# ============================================================
# KROK 5: SPRAWDZENIE PROBLEMÓW
# ============================================================
if [ "${MAC_UPDATE_SKIP_DOCTOR:-0}" = "1" ]; then
    print_info "Skipping brew doctor (--skip-doctor)"
else
print_header "$L_BREW_HEALTH_CHECKING"

# brew doctor zwraca kod błędu przy ostrzeżeniach — to normalne.
# Na Apple Silicon (arm64) Homebrew używa /opt/homebrew; /usr/local/ należy do
# innych programów (np. Cisco ASAF/AnyConnect → libASAF.dylib). To jest
# normalny stan i nie wymaga żadnej interwencji.

DOCTOR_OUT=$(brew doctor 2>&1 || true)

# Druga warstwa auto-recovery: brew doctor czasem zgłasza "unlinked kegs" nawet
# kiedy brew upgrade nie pokazał Error (np. keg od poprzedniej sesji).
# Wyciągnij nazwy ze sekcji "You have unlinked kegs in your Cellar".
UNLINKED_KEGS=$(echo "$DOCTOR_OUT" | awk '
    /You have unlinked kegs in your Cellar/ { in_block = 1; next }
    in_block && /^$/ { in_block = 0; next }
    in_block && /^Leaving kegs unlinked/ { next }
    in_block && /^Run .brew link./ { next }
    in_block && /^  [a-zA-Z]/ { gsub(/^[[:space:]]+|[[:space:]]+$/, ""); print }
')
if [ -n "$UNLINKED_KEGS" ]; then
    print_info "$L_BREW_DOCTOR_UNLINKED_FOUND"
    RELINKED2=0
    while IFS= read -r keg; do
        [ -z "$keg" ] && continue
        case "$keg" in
            [a-zA-Z0-9]*) ;;
            *) continue ;;
        esac
        if brew link --overwrite "$keg" >/dev/null 2>&1; then
            print_ok "$L_BREW_LINK_RECOVERED $keg"
            RELINKED2=$((RELINKED2 + 1))
        fi
    done <<EOF
$UNLINKED_KEGS
EOF
    if [ "$RELINKED2" -gt 0 ]; then
        # Re-run doctor po naprawie, żeby aktualne wyjście nie zawierało już tej sekcji
        DOCTOR_OUT=$(brew doctor 2>&1 || true)
    fi
fi

# Filtruj znane fałszywie pozytywne ostrzeżenia specyficzne dla Apple Silicon
# oraz informacyjne caveat-y po brew upgrade (PATH shadowing dla relinkowanych kegów).
DOCTOR_FILTERED=$(echo "$DOCTOR_OUT" \
    | grep -v "Unbrewed dylibs were found in /usr/local/lib" \
    | grep -v "If you didn't put them there on purpose" \
    | grep -v "building Homebrew formulae and may need to be deleted" \
    | grep -v "Unexpected dylibs:" \
    | grep -v "libASAF\.dylib" \
    | grep -v "/usr/local/lib/lib" \
    | grep -v "Please note that these warnings are just used" \
    | grep -v "with debugging if you file an issue" \
    | grep -v "If everything you use Homebrew for is working fine" \
    | grep -v "please don't worry or file an issue; just ignore this" \
    | grep -v "shadowed by other commands earlier in your PATH" \
    | grep -v "HOMEBREW_NO_PATH_SHADOW_CHECK" \
    || true)

# Sprawdź czy po filtrowaniu zostały prawdziwe ostrzeżenia (linie "Warning:")
REAL_WARNINGS=$(echo "$DOCTOR_FILTERED" | grep "^Warning:" 2>/dev/null | grep -v "^$" || true)

if [ -n "$REAL_WARNINGS" ]; then
    # Są prawdziwe ostrzeżenia — pokaż pełny output
    echo "$DOCTOR_OUT"
    print_warn "$L_BREW_HEALTH_WARN"
else
    # No real warnings (or only known false positives)
    print_ok "$L_BREW_HEALTH_OK"
    # Info about filtered known warnings
    if echo "$DOCTOR_OUT" | grep -q "libASAF\|/usr/local/lib"; then
        print_info "$L_BREW_DYLIB_FILTERED_INFO"
        print_info "$L_BREW_DYLIB_INFO"
    fi
fi
fi

# ============================================================
# KROK 6: CZYSZCZENIE
# ============================================================
print_header "$L_BREW_CACHE_CLEANING"

CACHE_DIR=$(brew --cache 2>/dev/null || echo "")
brew cleanup --prune=all 2>/dev/null || brew cleanup

if [ -n "$CACHE_DIR" ] && [ -d "$CACHE_DIR" ]; then
    CACHE_SIZE=$(du -sh "$CACHE_DIR" 2>/dev/null | awk '{print $1}' || echo "?")
    print_ok "$L_BREW_CACHE_CLEANED (~$CACHE_SIZE)"
else
    print_ok "$L_BREW_CACHE_CLEANED"
fi

# ============================================================
# PODSUMOWANIE
# ============================================================
print_header "$L_BREW_INSTALLED_TITLE"

echo -e "${CYAN}Formulae:${NC}"
brew list --formula --versions 2>/dev/null | column -t || brew list --formula --versions

echo ""
echo -e "${CYAN}Casks:${NC}"
brew list --cask --versions 2>/dev/null | column -t || brew list --cask --versions

# ── Snapshot wersji zainstalowanych pakietów PO aktualizacji ──
if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
    print_info "$L_BREW_SAVING_SNAPSHOT"
    brew list --formula --versions 2>/dev/null > "$MAC_UPDATE_SESSION_DIR/brew_formulae_after.txt" || true
    brew list --cask --versions 2>/dev/null > "$MAC_UPDATE_SESSION_DIR/brew_casks_after.txt" || true
    print_ok "$L_BREW_SNAPSHOTS_SAVED_TO $MAC_UPDATE_SESSION_DIR"
fi

print_header "$L_BREW_SCRIPT_DONE"
if [ "$BREW_EXIT" -eq 0 ]; then
    echo -e "  ${GREEN}$L_BREW_ALL_DONE${NC}"
else
    print_error "Homebrew finished with upgrade errors. Review output above."
fi
echo ""
exit "$BREW_EXIT"
