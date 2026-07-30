#!/usr/bin/env bash
# shellcheck disable=SC2329  # cleanup_brew is invoked through trap.
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
mac_update_require_supported_platform || exit 1

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
    if ! brew list --formula --versions 2>/dev/null > "$MAC_UPDATE_SESSION_DIR/brew_formulae_before.txt"; then
        print_warn "Could not save the pre-update formula snapshot."
        BREW_EXIT=1
    fi
    if ! brew list --cask --versions 2>/dev/null > "$MAC_UPDATE_SESSION_DIR/brew_casks_before.txt"; then
        print_warn "Could not save the pre-update cask snapshot."
        BREW_EXIT=1
    fi
fi

# ============================================================
# DRY-RUN: list outdated only — do not mutate brew refs
# ============================================================
if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
    print_header "$L_BREW_OUTDATED"
    echo -e "${CYAN}$L_BREW_OUTDATED_LIST${NC}"
    HOMEBREW_NO_AUTO_UPDATE=1 brew outdated --formula || exit 1
    echo ""
    echo -e "${CYAN}$L_BREW_CASKS_OUTDATED${NC}"
    HOMEBREW_NO_AUTO_UPDATE=1 brew outdated --cask --greedy || exit 1
    print_info "[DRY-RUN] Would run: brew update, brew upgrade, cleanup, doctor"
    exit "$BREW_EXIT"
fi

# ============================================================
# STEP 1: Update Homebrew itself
# ============================================================
print_header "$L_BREW_UPDATE"

if brew update; then
    print_ok "$L_BREW_UPDATED"
else
    print_error "brew update failed; refusing to use potentially stale metadata."
    exit 1
fi

# ============================================================
# STEP 2: Check outdated packages
# ============================================================
print_header "$L_BREW_OUTDATED"

echo -e "${CYAN}$L_BREW_OUTDATED_LIST${NC}"
if ! OUTDATED_FORMULAE=$(brew outdated --formula 2>&1); then
    print_error "brew outdated --formula failed; update state is unknown."
    [ -n "$OUTDATED_FORMULAE" ] && printf '%s\n' "$OUTDATED_FORMULAE"
    exit 1
fi
if [ -z "$OUTDATED_FORMULAE" ]; then
    print_ok "All formulae are up to date!"
else
    echo "$OUTDATED_FORMULAE"
fi

echo ""
echo -e "${CYAN}$L_BREW_CASKS_OUTDATED${NC}"
if ! OUTDATED_CASKS=$(brew outdated --cask --greedy 2>&1); then
    print_error "brew outdated --cask --greedy failed; update state is unknown."
    [ -n "$OUTDATED_CASKS" ] && printf '%s\n' "$OUTDATED_CASKS"
    exit 1
fi
if [ -z "$OUTDATED_CASKS" ]; then
    print_ok "All casks are up to date!"
else
    echo "$OUTDATED_CASKS"
fi

BREW_HAS_OUTDATED=1
if [ -z "$OUTDATED_FORMULAE" ] && [ -z "$OUTDATED_CASKS" ]; then
    BREW_HAS_OUTDATED=0
    echo ""
    print_ok "$L_BREW_SUMMARY"
fi

# ============================================================
# POTWIERDZENIE
# ============================================================
if [ "$BREW_HAS_OUTDATED" -eq 1 ]; then
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
BREW_EXIT_BEFORE_FORMULA=$BREW_EXIT
FORMULA_UPGRADE_FAILED=0

# Capture output so we can detect recoverable link conflicts
# (e.g., "Error: The `brew link` step did not complete successfully" for uv,
# which happens when an unmanaged binary squats on /opt/homebrew/bin/<name>).
BREW_UPGRADE_LOG=$(mktemp "${TMPDIR:-/tmp}/brew_upgrade.XXXXXX") || {
    print_error "Could not create the Homebrew upgrade diagnostic log."
    exit 1
}
if brew upgrade --formula 2>&1 | tee "$BREW_UPGRADE_LOG"; then
    print_ok "$L_BREW_FORMULAE_OK"
else
    print_warn "$L_BREW_FORMULAE_WARN"
    BREW_EXIT=1
    FORMULA_UPGRADE_FAILED=1
fi

# ============================================================
# KROK 3.5: OPT-IN RECOVERY DLA "BREW LINK DID NOT COMPLETE"
# Wykrywa kegi, które się zainstalowały, ale nie zostały zlinkowane
# (typowo przez kolizję z istniejącym binarnym w /opt/homebrew/bin lub
# /usr/local/bin). Recovery is disabled by default because --overwrite can
# replace an intentionally unmanaged command. It requires an explicit env opt-in.
# ============================================================
LINK_FAILED_KEGS=$(awk '
    # A per-formula header ("==> Upgrading uv") names a keg. Skip the
    # "==> Upgrading N outdated packages:" summary so its count is never
    # mistaken for a keg name. $3 stays the formula even if brew later adds
    # trailing "old -> new" version text to the header line.
    /^==> Upgrading / {
        if ($0 !~ /outdated package/) { kegname = $3 }
        next
    }
    /Error: The .brew link. step did not complete successfully/ {
        if (kegname != "") { print kegname; kegname = "" }
    }
' "$BREW_UPGRADE_LOG" 2>/dev/null | sort -u)
rm -f "$BREW_UPGRADE_LOG" 2>/dev/null || true

if [ -n "$LINK_FAILED_KEGS" ] && [ "${MAC_UPDATE_BREW_LINK_OVERWRITE:-0}" != "1" ]; then
    print_warn "Homebrew reported unlinked kegs. Automatic 'brew link --overwrite' is disabled."
    print_info "Inspect the conflicting files first; set MAC_UPDATE_BREW_LINK_OVERWRITE=1 only for an explicit recovery run."
elif [ -n "$LINK_FAILED_KEGS" ]; then
    print_warn "$L_BREW_LINK_RECOVERY_DETECTED"
    RELINKED=0
    RELINK_FAILED=0
    while IFS= read -r keg; do
        keg=$(echo "$keg" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        [ -z "$keg" ] && continue
        # Reject anything that isn't a plain formula name to keep `brew link` safe
        case "$keg" in
            ""|*[!a-zA-Z0-9@+_./-]*) continue ;;
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
        # Clear only the formula-upgrade failure; preserve earlier snapshot errors.
        if [ "$FORMULA_UPGRADE_FAILED" -eq 1 ]; then
            BREW_EXIT=$BREW_EXIT_BEFORE_FORMULA
        fi
        print_ok "$L_BREW_LINK_RECOVERY_OK"
    fi
fi

# ============================================================
# KROK 4: AKTUALIZACJA CASKS (APLIKACJE GUI)
# ============================================================
print_header "$L_BREW_CASKS_UPGRADE"

# Aktualizuj casks — flaga --no-quarantine usunięta w Homebrew 4.x (była przestarzała)
if brew upgrade --cask --greedy; then
    print_ok "$L_BREW_CASKS_OK"
else
    print_warn "$L_BREW_CASKS_WARN"
    BREW_EXIT=1
fi
fi

# A successful upgrade is not enough: query Homebrew again and fail if any
# formula or greedy cask remains outdated, or if verification itself fails.
print_header "$L_BREW_OUTDATED"
if ! REMAINING_FORMULAE=$(brew outdated --formula 2>&1); then
    print_error "Final brew outdated --formula verification failed."
    [ -n "$REMAINING_FORMULAE" ] && printf '%s\n' "$REMAINING_FORMULAE"
    BREW_EXIT=1
elif [ -n "$REMAINING_FORMULAE" ]; then
    print_error "Formulae still outdated after upgrade:"
    printf '%s\n' "$REMAINING_FORMULAE"
    BREW_EXIT=1
fi
if ! REMAINING_CASKS=$(brew outdated --cask --greedy 2>&1); then
    print_error "Final brew outdated --cask --greedy verification failed."
    [ -n "$REMAINING_CASKS" ] && printf '%s\n' "$REMAINING_CASKS"
    BREW_EXIT=1
elif [ -n "$REMAINING_CASKS" ]; then
    print_info "Casks listed in greedy outdated check (informational only):"
    printf '%s\n' "$REMAINING_CASKS"
fi
if [ "$BREW_EXIT" -eq 0 ]; then
    print_ok "$L_BREW_SUMMARY"
fi

# ============================================================
# KROK 5: SPRAWDZENIE PROBLEMÓW
# ============================================================
if [ "${MAC_UPDATE_SKIP_DOCTOR:-0}" = "1" ]; then
    print_info "Skipping brew doctor (--skip-doctor)"
else
print_header "$L_BREW_HEALTH_CHECKING"

# brew doctor returns non-zero for warnings. Keep the status so an unexpected
# diagnostic cannot be turned into a green result by output filtering.
DOCTOR_OUT=$(brew doctor 2>&1)
DOCTOR_EXIT=$?

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
if [ -n "$UNLINKED_KEGS" ] && [ "${MAC_UPDATE_BREW_LINK_OVERWRITE:-0}" != "1" ]; then
    print_warn "brew doctor found unlinked kegs; automatic overwrite recovery is disabled."
    print_info "Set MAC_UPDATE_BREW_LINK_OVERWRITE=1 only after reviewing the conflicts."
elif [ -n "$UNLINKED_KEGS" ]; then
    print_info "$L_BREW_DOCTOR_UNLINKED_FOUND"
    RELINKED2=0
    while IFS= read -r keg; do
        [ -z "$keg" ] && continue
        case "$keg" in
            ""|*[!a-zA-Z0-9@+_./-]*) continue ;;
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
        DOCTOR_OUT=$(brew doctor 2>&1)
        DOCTOR_EXIT=$?
    fi
fi

# Suppress one narrowly-known false positive only when the complete dylib list
# contains exactly Cisco's libASAF.dylib. Any second path preserves the whole
# warning block, including its header and remediation text.
DOCTOR_FILTERED=$(printf '%s\n' "$DOCTOR_OUT" | awk '
    function emit_dylib_block() {
        if (!(dylib_paths == 1 && asaf_paths == 1)) {
            printf "%s", dylib_block
        }
        in_dylib_block = 0
        dylib_block = ""
        dylib_paths = 0
        asaf_paths = 0
    }
    /^Warning: Unbrewed dylibs were found in \/usr\/local\/lib/ {
        in_dylib_block = 1
        dylib_block = $0 ORS
        next
    }
    in_dylib_block && /^(Warning:|Error:)/ {
        emit_dylib_block()
        print
        next
    }
    in_dylib_block {
        dylib_block = dylib_block $0 ORS
        if ($0 ~ /^[[:space:]]+\/usr\/local\/lib\//) {
            dylib_path = $0
            sub(/^[[:space:]]+/, "", dylib_path)
            dylib_paths++
            if (dylib_path == "/usr/local/lib/libASAF.dylib") asaf_paths++
        }
        next
    }
    { print }
    END {
        if (in_dylib_block) emit_dylib_block()
    }
')

# Keep libASAF dylib filter in place for now.
# TODO(C2): libASAF dylib filter can be removed once severity is corrected across scripts.
ASAF_ONLY_FILTERED=0
if [ "$DOCTOR_FILTERED" != "$DOCTOR_OUT" ]; then
    ASAF_ONLY_FILTERED=1
fi
REAL_WARNINGS=$(printf '%s\n' "$DOCTOR_FILTERED" | grep '^Warning:' 2>/dev/null || true)
DOCTOR_ERRORS=$(printf '%s\n' "$DOCTOR_FILTERED" | grep '^Error:' 2>/dev/null || true)

if [ -n "$DOCTOR_ERRORS" ]; then
    [ -n "$DOCTOR_FILTERED" ] && printf '%s\n' "$DOCTOR_FILTERED"
    print_warn "$L_BREW_HEALTH_WARN"
    BREW_EXIT=1
elif [ -n "$REAL_WARNINGS" ]; then
    [ -n "$DOCTOR_FILTERED" ] && printf '%s\n' "$DOCTOR_FILTERED"
    print_info "brew doctor reported health advisories (warnings only)."
    print_ok "$L_BREW_HEALTH_OK"
else
    print_ok "$L_BREW_HEALTH_OK"
    if [ "$ASAF_ONLY_FILTERED" -eq 1 ]; then
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
if brew cleanup --prune=all 2>/dev/null || brew cleanup; then
    if [ -n "$CACHE_DIR" ] && [ -d "$CACHE_DIR" ]; then
        CACHE_SIZE=$(du -sh "$CACHE_DIR" 2>/dev/null | awk '{print $1}' || echo "?")
        print_ok "$L_BREW_CACHE_CLEANED (~$CACHE_SIZE)"
    else
        print_ok "$L_BREW_CACHE_CLEANED"
    fi
else
    print_warn "Homebrew cleanup failed."
    BREW_EXIT=1
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
    BREW_SNAPSHOT_OK=1
    if ! brew list --formula --versions 2>/dev/null > "$MAC_UPDATE_SESSION_DIR/brew_formulae_after.txt"; then
        print_warn "Could not save the post-update formula snapshot."
        BREW_SNAPSHOT_OK=0
        BREW_EXIT=1
    fi
    if ! brew list --cask --versions 2>/dev/null > "$MAC_UPDATE_SESSION_DIR/brew_casks_after.txt"; then
        print_warn "Could not save the post-update cask snapshot."
        BREW_SNAPSHOT_OK=0
        BREW_EXIT=1
    fi
    if [ "$BREW_SNAPSHOT_OK" -eq 1 ]; then
        print_ok "$L_BREW_SNAPSHOTS_SAVED_TO $MAC_UPDATE_SESSION_DIR"
    fi
fi

print_header "$L_BREW_SCRIPT_DONE"
if [ "$BREW_EXIT" -eq 0 ]; then
    echo -e "  ${GREEN}$L_BREW_ALL_DONE${NC}"
else
    print_error "Homebrew finished with errors. Review output above."
fi
echo ""
exit "$BREW_EXIT"
