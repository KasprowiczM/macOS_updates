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

if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
    echo "$UPDATES" > "$MAC_UPDATE_SESSION_DIR/system_available.txt" 2>/dev/null || true
fi

if [ "$UPDATES_EXIT" -ne 0 ]; then
    print_error "softwareupdate -l failed (exit $UPDATES_EXIT)"
    if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
        echo "unknown" > "$MAC_UPDATE_SESSION_DIR/pending_system" 2>/dev/null || true
    fi
    exit 1
fi

if echo "$UPDATES" | grep -q "No new software available"; then
    print_ok "$L_SYSTEM_UPDATES_NONE"
    if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
        echo "0" > "$MAC_UPDATE_SESSION_DIR/pending_system" 2>/dev/null || true
    fi
    echo ""
    exit 0
fi

# Parse and classify available updates
CURRENT_VERSION="$(sw_vers -productVersion 2>/dev/null || echo '0.0.0')"
SYSTEM_PARSED_FILE="$(mktemp "${TMPDIR:-/tmp}/mac_update_sys_parsed.XXXXXX")" || exit 1
python3 - "$SCRIPT_DIR" "$UPDATES" "$CURRENT_VERSION" > "$SYSTEM_PARSED_FILE" <<'PYEOF'
import sys
from pathlib import Path

repo_dir = Path(sys.argv[1])
sys.path.insert(0, str(repo_dir / "lib" / "python"))
from system_updates import classify_updates, parse_softwareupdate_list

raw_text = sys.argv[2]
cur_ver = sys.argv[3]
items = parse_softwareupdate_list(raw_text)
classified = classify_updates(items, cur_ver)

print(f"COUNT_TOTAL={len(items)}")
print(f"COUNT_SAME={len(classified['same_major'])}")
print(f"COUNT_MAJOR={len(classified['major'])}")
print(f"COUNT_OTHER={len(classified['other'])}")

for it in classified['same_major']:
    print(f"SAME\t{it['label']}\t{it['title']}\t{it['version']}\t{1 if it['restart'] else 0}")
for it in classified['other']:
    print(f"OTHER\t{it['label']}\t{it['title']}\t{it['version']}\t{1 if it['restart'] else 0}")
for it in classified['major']:
    print(f"MAJOR\t{it['label']}\t{it['title']}\t{it['version']}\t{1 if it['restart'] else 0}")
PYEOF

COUNT_TOTAL="$(grep '^COUNT_TOTAL=' "$SYSTEM_PARSED_FILE" | cut -d= -f2)"
if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
    echo "${COUNT_TOTAL:-unknown}" > "$MAC_UPDATE_SESSION_DIR/pending_system" 2>/dev/null || true
fi

# Major upgrade policy check
ALLOW_MAJOR="${MAC_UPDATE_ALLOW_MAJOR_UPGRADE:-0}"
MAJOR_ALLOWED=0
if grep -q '^MAJOR' "$SYSTEM_PARSED_FILE"; then
    while IFS=$'\t' read -r kind label title version req_restart; do
        [ "$kind" = "MAJOR" ] || continue
        print_warn "$(printf "$L_SYSTEM_MAJOR_AVAILABLE" "$title" "$version")"
        if [ "$ALLOW_MAJOR" = "1" ] && [ "${MAC_UPDATE_NONINTERACTIVE:-0}" != "1" ]; then
            if [ "${MAC_UPDATE_YES:-0}" = "1" ]; then
                MAJOR_ALLOWED=1
            elif [ -t 0 ]; then
                read -r -p "  $(printf "$L_SYSTEM_MAJOR_CONFIRM" "$title")" CONFIRM_MAJOR
                CONFIRM_MAJOR="${CONFIRM_MAJOR:-T}"
                if [[ "$CONFIRM_MAJOR" =~ ^[TtYy]$ ]]; then
                    MAJOR_ALLOWED=1
                fi
            fi
        fi
    done < "$SYSTEM_PARSED_FILE"
fi

# Select labels to install
INSTALL_LABELS=()
ANY_RESTART=false
while IFS=$'\t' read -r kind label title version req_restart; do
    case "$kind" in
        SAME|OTHER)
            INSTALL_LABELS+=("$label")
            [ "$req_restart" = "1" ] && ANY_RESTART=true
            ;;
        MAJOR)
            if [ "$MAJOR_ALLOWED" -eq 1 ]; then
                INSTALL_LABELS+=("$label")
                [ "$req_restart" = "1" ] && ANY_RESTART=true
            fi
            ;;
    esac
done < "$SYSTEM_PARSED_FILE"
rm -f "$SYSTEM_PARSED_FILE" 2>/dev/null || true

if [ "${#INSTALL_LABELS[@]}" -eq 0 ]; then
    print_ok "$L_SYSTEM_UPDATES_NONE"
    exit 0
fi

# ============================================================
# User confirmation & DRY-RUN
# ============================================================
if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
    for lbl in "${INSTALL_LABELS[@]}"; do
        print_info "[DRY-RUN] Would run: sudo softwareupdate -i \"$lbl\" -R --verbose"
    done
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
        if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
            touch "$MAC_UPDATE_SESSION_DIR/system_skipped_by_user" 2>/dev/null || true
        fi
        exit 10
    fi
fi

if [ "$ANY_RESTART" = true ]; then
    echo ""
    print_warn "$L_SYSTEM_RESTART_REQUIRED"
    print_info "$L_SYSTEM_RESTART_AFTER_INFO"
    if [ "${MAC_UPDATE_YES:-0}" != "1" ]; then
        read -r -p "  $L_SYSTEM_CONFIRM_RESTART " AUTO_RESTART
        AUTO_RESTART="${AUTO_RESTART:-T}"
        if [[ "$AUTO_RESTART" =~ ^[Nn] ]]; then
            print_error "Restart-required macOS updates will not be installed without softwareupdate -R."
            print_info "$L_SYSTEM_RESTART_MECHANISM"
            print_warn "$L_SYSTEM_REMEMBER_RESTART"
            exit 1
        fi
    fi
fi

# ============================================================
# Install system updates
# ============================================================
print_header "$L_SOFTWAREUPDATE_RUN"
echo -e "${CYAN}$L_SYSTEM_PLEASE_WAIT${NC}"
echo ""

sudo -v 2>/dev/null || true
INSTALL_FAILED=0
for lbl in "${INSTALL_LABELS[@]}"; do
    print_step "Installing: $lbl..."
    if ! sudo softwareupdate -i "$lbl" -R --verbose; then
        INSTALL_FAILED=1
        print_warn "Failed to install: $lbl"
    else
        if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
            echo "$lbl" >> "$MAC_UPDATE_SESSION_DIR/system_installed_labels.txt" 2>/dev/null || true
        fi
    fi
done

if [ "$INSTALL_FAILED" -ne 0 ]; then
    print_warn "$L_SYSTEM_SOME_FAILED"
    exit 1
fi

if [ "$ANY_RESTART" = true ]; then
    print_ok "$L_SYSTEM_RESTARTING"
else
    print_ok "$L_SYSTEM_DONE_OK"
    print_ok "$L_SYSTEM_NO_RESTART_NEEDED"
    # Remeasure pending updates after install without restart
    if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
        POST_UPDATES=$(LANG=C LC_ALL=C softwareupdate -l 2>&1) || true
        echo "$POST_UPDATES" > "$MAC_UPDATE_SESSION_DIR/system_available.txt" 2>/dev/null || true
        if echo "$POST_UPDATES" | grep -q "No new software available"; then
            echo "0" > "$MAC_UPDATE_SESSION_DIR/pending_system" 2>/dev/null || true
        else
            rem_cnt=$(python3 - "$SCRIPT_DIR" "$POST_UPDATES" <<'PYEOF'
import sys
from pathlib import Path
repo_dir = Path(sys.argv[1])
sys.path.insert(0, str(repo_dir / "lib" / "python"))
from system_updates import parse_softwareupdate_list
raw_text = sys.argv[2]
print(len(parse_softwareupdate_list(raw_text)))
PYEOF
)
            echo "${rem_cnt:-unknown}" > "$MAC_UPDATE_SESSION_DIR/pending_system" 2>/dev/null || true
        fi
    fi
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
