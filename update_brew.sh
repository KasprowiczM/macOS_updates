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
. "$SCRIPT_DIR/lib/severity.sh"
. "$SCRIPT_DIR/lib/internet_apps.sh"
. "$SCRIPT_DIR/lib/brew.sh"
. "$SCRIPT_DIR/lib/version.sh"
. "$SCRIPT_DIR/lib/internet_i18n.sh"
mac_update_severity_init

cleanup_brew() {
    [ -f "${BREW_UPGRADE_LOG:-}" ] && rm -f "$BREW_UPGRADE_LOG" 2>/dev/null || true
}
trap cleanup_brew EXIT
trap 'cleanup_brew; exit 130' INT TERM

strip_ansi() {
    sed $'s/\033\\[[0-9;]*[a-zA-Z]//g'
}

print_header() { ui_print_header "$1"; }



# ============================================================
print_header "$L_BREW_TITLE"
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
    if ! brew list --formula --versions 2>/dev/null | strip_ansi > "$MAC_UPDATE_SESSION_DIR/brew_formulae_before.txt"; then
        print_warn "Could not save the pre-update formula snapshot."
        SOFT_FAIL=1
    fi
    if ! brew_cask_versions | strip_ansi > "$MAC_UPDATE_SESSION_DIR/brew_casks_before.txt"; then
        print_warn "Could not save the pre-update cask snapshot."
        SOFT_FAIL=1
    fi
fi

# ============================================================
# DRY-RUN: list outdated only — do not mutate brew refs
# ============================================================
if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
    print_header "$L_BREW_OUTDATED"
    echo -e "${CYAN}$L_BREW_OUTDATED_LIST${NC}"
    HOMEBREW_NO_AUTO_UPDATE=1 brew outdated --formula || true
    echo ""
    echo -e "${CYAN}$L_BREW_CASKS_OUTDATED${NC}"
    HOMEBREW_NO_AUTO_UPDATE=1 brew outdated --cask --greedy-auto-updates || true
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
    print_warn "brew update failed; refusing to use potentially stale metadata."
    SOFT_FAIL=1
    exit "$(mac_update_severity_exit_code)"
fi

# ============================================================
# STEP 2: Check outdated packages
# ============================================================
print_header "$L_BREW_OUTDATED"

echo -e "${CYAN}$L_BREW_OUTDATED_LIST${NC}"
if ! OUTDATED_FORMULAE=$(brew_outdated_formulae); then
    print_warn "brew outdated --formula failed; update state is unknown."
    [ -n "$OUTDATED_FORMULAE" ] && printf '%s\n' "$OUTDATED_FORMULAE"
    SOFT_FAIL=1
    exit "$(mac_update_severity_exit_code)"
fi
if [ -z "$OUTDATED_FORMULAE" ]; then
    print_ok "All formulae are up to date!"
else
    echo "$OUTDATED_FORMULAE"
fi

echo ""
echo -e "${CYAN}$L_BREW_CASKS_OUTDATED${NC}"
if ! OUTDATED_CASKS=$(brew_outdated_casks); then
    print_warn "brew outdated --cask --greedy-auto-updates failed; update state is unknown."
    [ -n "$OUTDATED_CASKS" ] && printf '%s\n' "$OUTDATED_CASKS"
    SOFT_FAIL=1
    exit "$(mac_update_severity_exit_code)"
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
FORMULA_UPGRADE_FAILED=0

# Capture output so we can detect recoverable link conflicts
BREW_UPGRADE_LOG=$(mktemp "${TMPDIR:-/tmp}/brew_upgrade.XXXXXX") || {
    print_error "Could not create the Homebrew upgrade diagnostic log."
    exit 1
}
if brew upgrade --formula 2>&1 | tee "$BREW_UPGRADE_LOG"; then
    print_ok "$L_BREW_FORMULAE_OK"
else
    print_warn "$L_BREW_FORMULAE_WARN"
    HARD_FAIL=1
    FORMULA_UPGRADE_FAILED=1
fi

# ============================================================
# KROK 3.5: OPT-IN RECOVERY DLA "BREW LINK DID NOT COMPLETE"
# ============================================================
LINK_FAILED_KEGS=$(awk '
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
        if [ "$FORMULA_UPGRADE_FAILED" -eq 1 ]; then
            HARD_FAIL=0
        fi
        print_ok "$L_BREW_LINK_RECOVERY_OK"
    elif [ "$RELINK_FAILED" -gt 0 ]; then
        SOFT_FAIL=1
    fi
fi

# Guard against cask downgrades (when cask formula version < installed app version)
UPGRADEABLE_CASKS=""
if [ -n "$OUTDATED_CASKS" ]; then
    for cask in $(echo "$OUTDATED_CASKS" | awk '{print $1}'); do
        cask_json=$(brew info --json=v2 --cask "$cask" 2>/dev/null || true)
        cask_ver=""
        cask_app_name=""
        cask_recorded_ver=""
        if [ -n "$cask_json" ]; then
            parsed=$(python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    c = d["casks"][0]
    v = c.get("version", "")
    installed = c.get("installed") or ""
    app = ""
    for art in c.get("artifacts", []):
        if isinstance(art, dict) and "app" in art:
            apps = art["app"]
            app = apps[0] if isinstance(apps, list) and apps else (apps if isinstance(apps, str) else "")
            break
    print(f"{v}|{app}|{installed}")
except Exception:
    pass
' <<< "$cask_json" 2>/dev/null || true)
            cask_ver=$(echo "$parsed" | cut -d'|' -f1)
            cask_app_name=$(echo "$parsed" | cut -d'|' -f2)
            cask_recorded_ver=$(echo "$parsed" | cut -d'|' -f3)
        fi

        # Homebrew's own record of what it installed is the only like-for-like
        # operand for the cask version. Prefer it; the bundle version is a
        # fallback and may use a different scheme entirely.
        if [ -n "$cask_recorded_ver" ] && [ -n "$cask_ver" ]; then
            if [ "$(internet_version_relation "$cask_recorded_ver" "$cask_ver")" = "newer" ]; then
                print_warn "$(internet_msg "$L_BREW_CASK_WOULD_DOWNGRADE_FMT" "$cask" "$cask_ver" "$cask_recorded_ver")"
                SOFT_FAIL=1
                continue
            fi
        fi

        cask_app_path=""
        if [ -n "$cask_app_name" ]; then
            cask_app_path="/Applications/$cask_app_name"
        fi
        if [ -z "$cask_app_path" ] || [ ! -d "$cask_app_path" ]; then
            cask_app_path="/Applications/$cask.app"
        fi
        if [ ! -d "$cask_app_path" ]; then
            cask_app_path=$(find "/opt/homebrew/Caskroom/$cask" -maxdepth 3 -name "*.app" 2>/dev/null | head -1)
        fi

        if [ -n "$cask_app_path" ] && [ -d "$cask_app_path" ]; then
            installed_ver=$(app_version "$cask_app_path")
            if [ -n "$installed_ver" ] && [ -n "$cask_ver" ]; then
                # Scheme-aware: a bundle version such as Brave's
                # "151.1.93.138" carries the Chromium major in front of the
                # cask's own "1.93.138.0". Comparing them digit by digit read
                # the app as newer and skipped the upgrade on every run.
                rel=$(app_vs_package_version_relation "$installed_ver" "$cask_ver" 2>/dev/null || echo "unknown")
                if [ "$rel" = "newer" ]; then
                    print_warn "$(internet_msg "$L_BREW_CASK_WOULD_DOWNGRADE_FMT" "$cask" "$cask_ver" "$installed_ver")"
                    SOFT_FAIL=1
                    continue
                fi
                if [ "$rel" = "unknown" ]; then
                    print_info "$(internet_msg "$L_BREW_CASK_VERSION_SCHEME_INFO_FMT" "$cask" "$installed_ver" "$cask_ver")"
                fi
            fi
        fi
        UPGRADEABLE_CASKS="$UPGRADEABLE_CASKS $cask"
    done
fi

if [ -n "$UPGRADEABLE_CASKS" ]; then
    if brew upgrade --cask $UPGRADEABLE_CASKS; then
        print_ok "$L_BREW_CASKS_OK"
    else
        print_warn "$L_BREW_CASKS_WARN"
        HARD_FAIL=1
    fi
else
    print_ok "$L_BREW_CASKS_OK"
fi
fi

# A successful upgrade is not enough: query Homebrew again and fail if any
# formula or greedy cask remains outdated, or if verification itself fails.
print_header "$L_BREW_OUTDATED"
if ! REMAINING_FORMULAE=$(brew_outdated_formulae | strip_ansi); then
    print_warn "Final brew outdated --formula verification failed."
    [ -n "$REMAINING_FORMULAE" ] && printf '%s\n' "$REMAINING_FORMULAE"
    SOFT_FAIL=1
elif [ -n "$REMAINING_FORMULAE" ]; then
    print_error "Formulae still outdated after upgrade:"
    printf '%s\n' "$REMAINING_FORMULAE"
    HARD_FAIL=1
fi
if ! REMAINING_CASKS=$(brew_outdated_casks | strip_ansi); then
    print_warn "Final brew outdated --cask --greedy-auto-updates verification failed."
    [ -n "$REMAINING_CASKS" ] && printf '%s\n' "$REMAINING_CASKS"
    SOFT_FAIL=1
elif [ -n "$REMAINING_CASKS" ]; then
    print_info "Casks listed in greedy outdated check (informational only):"
    printf '%s\n' "$REMAINING_CASKS"
fi
if [ "$HARD_FAIL" -eq 0 ] && [ "$SOFT_FAIL" -eq 0 ]; then
    print_ok "$L_BREW_SUMMARY"
fi

# ============================================================
# KROK 5: SPRAWDZENIE PROBLEMÓW
# ============================================================
if [ "${MAC_UPDATE_SKIP_DOCTOR:-0}" = "1" ]; then
    print_info "Skipping brew doctor (--skip-doctor)"
else
print_header "$L_BREW_HEALTH_CHECKING"

DOCTOR_OUT=$(brew doctor 2>&1 | strip_ansi)
DOCTOR_EXIT=$?

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
        DOCTOR_OUT=$(brew doctor 2>&1)
        DOCTOR_EXIT=$?
    fi
fi

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
    SOFT_FAIL=1
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
CLEANUP_OUT=$(brew cleanup --prune=all 2>&1 | strip_ansi)
CLEANUP_EXIT=$?
if [ -n "$MAC_UPDATE_SESSION_DIR" ] && [ -n "$CLEANUP_OUT" ]; then
    echo "$CLEANUP_OUT" >> "$MAC_UPDATE_SESSION_DIR/brew_cleanup.log"
fi
if [ "$CLEANUP_EXIT" -eq 0 ]; then
    if echo "$CLEANUP_OUT" | grep -qi "warning"; then
        print_warn "Homebrew cleanup completed with warnings."
    elif [ -z "$CLEANUP_OUT" ] || echo "$CLEANUP_OUT" | grep -qi "Nothing to remove"; then
        print_info "Homebrew cleanup: no obsolete cache to clean."
    else
        if [ -n "$CACHE_DIR" ] && [ -d "$CACHE_DIR" ]; then
            CACHE_SIZE=$(du -sh "$CACHE_DIR" 2>/dev/null | awk '{print $1}' || echo "?")
            print_ok "$L_BREW_CACHE_CLEANED (~$CACHE_SIZE)"
        else
            print_ok "$L_BREW_CACHE_CLEANED"
        fi
    fi
else
    print_warn "Homebrew cleanup failed."
    SOFT_FAIL=1
fi

# ============================================================
# PODSUMOWANIE
# ============================================================
print_header "$L_BREW_INSTALLED_TITLE"

echo -e "${CYAN}Formulae:${NC}"
brew list --formula --versions 2>/dev/null | column -t || brew list --formula --versions

echo ""
echo -e "${CYAN}Casks:${NC}"
brew_cask_versions | column -t || brew_cask_versions

# ── Snapshot wersji zainstalowanych pakietów PO aktualizacji ──
if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
    print_info "$L_BREW_SAVING_SNAPSHOT"
    BREW_SNAPSHOT_OK=1
    if ! brew list --formula --versions 2>/dev/null | strip_ansi > "$MAC_UPDATE_SESSION_DIR/brew_formulae_after.txt"; then
        print_warn "Could not save the post-update formula snapshot."
        BREW_SNAPSHOT_OK=0
        SOFT_FAIL=1
    fi
    if ! brew_cask_versions | strip_ansi > "$MAC_UPDATE_SESSION_DIR/brew_casks_after.txt"; then
        print_warn "Could not save the post-update cask snapshot."
        BREW_SNAPSHOT_OK=0
        SOFT_FAIL=1
    fi
    if [ "$BREW_SNAPSHOT_OK" -eq 1 ]; then
        print_ok "$L_BREW_SNAPSHOTS_SAVED_TO $MAC_UPDATE_SESSION_DIR"
    fi
fi

BREW_FINAL_EXIT="$(mac_update_severity_exit_code)"
if [ "$BREW_FINAL_EXIT" -eq 0 ]; then
    print_header "$L_BREW_SCRIPT_DONE"
    echo -e "  ${GREEN}$L_BREW_ALL_DONE${NC}"
else
    # Never print the "COMPLETED SUCCESSFULLY" banner above a non-zero exit —
    # the 2026-08-19 run log showed "SKRYPT 4 ZAKOŃCZONY POMYŚLNIE" directly
    # above "Homebrew finished with errors", which sends the reader hunting in
    # the wrong place.
    print_header "🍺 Homebrew"
    if [ "$BREW_FINAL_EXIT" -eq "$MAC_UPDATE_SOFT_EXIT" ]; then
        print_warn "Homebrew finished with soft warnings (non-blocking). Review output above."
    else
        print_error "Homebrew finished with errors. Review output above."
    fi
fi
echo ""
exit "$BREW_FINAL_EXIT"
