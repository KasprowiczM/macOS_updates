#!/usr/bin/env bash
# shellcheck disable=SC2153  # L_* variables are loaded dynamically by i18n/loader.sh.
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
#     Wymaga sudo (macOS entitlement change, see https://github.com/orgs/Homebrew/discussions/6550).
#
#   TOR 2 — Automatyzacja GUI App Store (AppleScript)
#     Aktualizuje aplikacje iPad na Apple Silicon (np. UniFi,
#     WiFiman, myCANAL), których mas jawnie nie obsługuje.
#     Wymaga jednorazowego uprawnienia Accessibility dla terminala.
#
# Wymagania:
#   - Homebrew  (wykrywany automatycznie)
#   - mas 4.1+  (instalowany/aktualizowany automatycznie)
#   - sudo      (hasło przy mas upgrade)
#   - Accessibility dla terminala (sprawdzane i instruowane)
#
# Zmienne środowiskowe:
#   MAS_NO_AUTO_INDEX=1  — wyłącza auto-indeksowanie Spotlight przez mas
#   MAC_UPDATE_MAS_CHECK_TIMEOUT=120 — limit zapytania mas outdated (sekundy)
#   MAC_UPDATE_MAS_UPGRADE_TIMEOUT=1800 — limit sudo mas upgrade (sekundy)
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
mac_update_require_supported_platform || exit 1

# ── i18n: load language strings ──────────────────────────────
. "$SCRIPT_DIR/lib/cli.sh"
. "$SCRIPT_DIR/lib/ui.sh"
. "$SCRIPT_DIR/lib/severity.sh"
mac_update_severity_init
. "$SCRIPT_DIR/lib/proc.sh"

# Suppress mas Spotlight auto-indexing warnings
export MAS_NO_AUTO_INDEX=1
MAS_CHECK_TIMEOUT="${MAC_UPDATE_MAS_CHECK_TIMEOUT:-120}"
MAS_UPGRADE_TIMEOUT="${MAC_UPDATE_MAS_UPGRADE_TIMEOUT:-1800}"
case "$MAS_CHECK_TIMEOUT:$MAS_UPGRADE_TIMEOUT" in
    *[!0-9:]*|:*|*:) print_error "Invalid mas timeout configuration."; exit 1 ;;
esac
if [ "$MAS_CHECK_TIMEOUT" -le 0 ] || [ "$MAS_UPGRADE_TIMEOUT" -le 0 ]; then
    print_error "mas timeouts must be positive integers."
    exit 1
fi

# ============================================================
print_header "$L_SCRIPT_TITLE_APPSTORE"
if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
    print_warn "DRY-RUN mode — App Store updates will not run and no tools will be installed"
    if command -v mas >/dev/null 2>&1; then
        print_info "mas version: $(mas version 2>/dev/null || echo '?')"
        print_info "Installed App Store apps (read-only):"
        mas list 2>/dev/null || print_warn "mas list failed"
        print_info "Pending native updates (read-only, fast mode):"
        mas outdated 2>/dev/null || print_warn "mas outdated failed"
    else
        print_warn "mas is not installed; a live run would install it through Homebrew"
    fi
    print_info "[DRY-RUN] Would run: sudo mas upgrade"
    print_info "[DRY-RUN] Would run: App Store GUI automation (AppleScript)"
    exit 0
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
    if brew install mas; then
        print_ok "$L_MAS_INSTALLED"
    else
        print_error "Homebrew could not install mas."
        exit 1
    fi
fi

# Check version — only update if < 4.1 (avoid slow brew update)
MAS_VER=$(mas version 2>/dev/null || echo "0.0.0")
MAS_MAJOR=$(echo "$MAS_VER" | cut -d'.' -f1)
MAS_MINOR=$(echo "$MAS_VER" | cut -d'.' -f2)
MAS_MINOR=${MAS_MINOR:-0}
print_ok "$L_MAS_VERSION $MAS_VER"

case "$MAS_MAJOR" in
    ''|*[!0-9]*)
        print_error "Could not parse the installed mas version: $MAS_VER"
        exit 1
        ;;
esac
case "$MAS_MINOR" in
    ''|*[!0-9]*)
        MAS_MINOR=0
        ;;
esac

if [ "$MAS_MAJOR" -lt 4 ] || { [ "$MAS_MAJOR" -eq 4 ] && [ "$MAS_MINOR" -lt 1 ]; }; then
    print_warn "$L_MAS_VERSION_OLD"
    if ! HOMEBREW_NO_AUTO_UPDATE=1 brew upgrade mas 2>/dev/null \
        && ! brew upgrade mas; then
        print_error "Homebrew could not upgrade mas."
        exit 1
    fi
    MAS_VER=$(mas version 2>/dev/null || echo "?")
    MAS_MAJOR=$(echo "$MAS_VER" | cut -d'.' -f1)
    MAS_MINOR=$(echo "$MAS_VER" | cut -d'.' -f2)
    MAS_MINOR=${MAS_MINOR:-0}
    case "$MAS_MAJOR" in
        ''|*[!0-9]*)
            print_error "Could not parse the upgraded mas version: $MAS_VER"
            exit 1
            ;;
    esac
    case "$MAS_MINOR" in
        ''|*[!0-9]*)
            MAS_MINOR=0
            ;;
    esac
    if [ "$MAS_MAJOR" -lt 4 ] || { [ "$MAS_MAJOR" -eq 4 ] && [ "$MAS_MINOR" -lt 1 ]; }; then
        print_error "mas 4.1 or newer is required; detected: $MAS_VER"
        exit 1
    fi
    print_ok "$L_MAS_VERSION_UPDATED $MAS_VER"
fi

# ============================================================
# STEP 1: Check App Store login
# ============================================================
print_header "$L_APPSTORE_CHECK"

if mas account >/dev/null 2>&1; then
    print_ok "App Store account detected (identifier not displayed)"
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

# Numeric App Store IDs out of a `mas outdated` listing. Used to drive TRACK 1
# from the set this run actually measured, instead of letting `mas upgrade`
# re-enumerate it in root's context — see mas_upgrade_ids() below.
mas_outdated_ids() {
    printf '%s\n' "$1" | awk '$1 ~ /^[0-9]+$/ { print $1 }'
}

# One `mas outdated` probe, in whichever mode this mas build supports.
mas_probe_outdated() {
    if [ "$MAS_OUTDATED_MODE" = "accurate" ]; then
        run_with_timeout "$MAS_CHECK_TIMEOUT" mas outdated --accurate 2>&1
    else
        run_with_timeout "$MAS_CHECK_TIMEOUT" mas outdated 2>&1
    fi
}

MAS_OUTDATED_MODE="default"
if mas outdated --help 2>&1 | grep -q -- '--accurate'; then
    MAS_OUTDATED_MODE="accurate"
fi
if [ "$MAS_OUTDATED_MODE" = "accurate" ]; then
    NATIVE_OUTDATED=$(run_with_timeout "$MAS_CHECK_TIMEOUT" mas outdated --accurate 2>&1)
    MAS_OUTDATED_EXIT=$?
else
    NATIVE_OUTDATED=$(run_with_timeout "$MAS_CHECK_TIMEOUT" mas outdated 2>&1)
    MAS_OUTDATED_EXIT=$?
fi
if [ "$MAS_OUTDATED_EXIT" -ne 0 ]; then
    print_warn "mas outdated ($MAS_OUTDATED_MODE) failed; native App Store state is unknown."
    [ -n "$NATIVE_OUTDATED" ] && printf '%s\n' "$NATIVE_OUTDATED"
    SOFT_FAIL=1
    exit "$(mac_update_severity_exit_code)"
fi
if [ -z "$NATIVE_OUTDATED" ]; then
    print_ok "$L_APPSTORE_NO_UPDATES"
else
    print_info "Pending native App Store updates:"
    printf '%s\n' "$NATIVE_OUTDATED"
fi
if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ]; then
    {
        echo "=== mas outdated before TRACK 1 ==="
        printf '%s\n' "$NATIVE_OUTDATED"
    } >> "$MAC_UPDATE_SESSION_DIR/appstore_diag.txt" 2>/dev/null || true
fi

# ============================================================
# STEP 3: CONFIRMATION
# ============================================================
echo -e "${YELLOW}  $L_RUN_TWO_TRACKS${NC}"
echo "    $L_TOR_1_HEADER"
echo "    $L_TOR_2_HEADER"
echo ""
[ -n "$NATIVE_OUTDATED" ] && print_warn "$L_TOR_1_SUDO_MSG"
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

# ============================================================
# TRACK 1: sudo mas upgrade (native macOS apps)
# ============================================================
print_header "$L_TOR_1_HEADER"
[ -n "$NATIVE_OUTDATED" ] && print_info "$L_TOR_1_SUDO_MSG"
echo ""

# ── mas snapshot BEFORE update ───────────────────────────────
if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
    print_info "$L_SNAPSHOT_BEFORE"
    if ! mas list 2>/dev/null > "$MAC_UPDATE_SESSION_DIR/mas_before.txt"; then
        print_warn "Could not save the pre-update App Store snapshot."
        SOFT_FAIL=1
    fi
fi

if [ -z "$NATIVE_OUTDATED" ]; then
    print_ok "$L_APPSTORE_NO_UPDATES — sudo mas upgrade skipped"
else
    if [ "${MAC_UPDATE_NO_SUDO:-0}" = "1" ] || { [ ! -t 0 ] && ! sudo -n true 2>/dev/null; }; then
        print_info "$L_APPSTORE_NO_SUDO_SKIPPED"
        SOFT_FAIL=1
    elif sudo -v; then
        # Explicit IDs, never a bare `mas upgrade`. A bare upgrade makes mas
        # re-enumerate the outdated set itself, and under `sudo` that
        # enumeration runs in root's context rather than the context this run
        # measured. On 2026-09-01 the pre-scan listed Copilot AND WhatsApp;
        # `sudo mas upgrade` upgraded Copilot, never mentioned WhatsApp, and the
        # run closed with "unverified" while WhatsApp sat at 26.33.73 with
        # 26.34.72 available. Driving the command from MAS_TOR1_IDS removes the
        # enumeration from the equation: what the run measured is what it acts
        # on, and anything left outdated afterwards is a real failure worth
        # reporting rather than a list that quietly differed.
        MAS_TOR1_IDS="$(mas_outdated_ids "$NATIVE_OUTDATED" | tr '\n' ' ')"
        MAS_TOR1_IDS="${MAS_TOR1_IDS% }"
        if [ -n "$MAS_TOR1_IDS" ]; then
            # shellcheck disable=SC2086  # IDs are numeric, word splitting is intended
            MAS_TOR1_OUT=$(run_with_timeout "$MAS_UPGRADE_TIMEOUT" \
                sudo -n env MAS_NO_AUTO_INDEX=1 mas upgrade $MAS_TOR1_IDS 2>&1)
            MAS_TOR1_EXIT=$?
        else
            MAS_TOR1_OUT=$(run_with_timeout "$MAS_UPGRADE_TIMEOUT" \
                sudo -n env MAS_NO_AUTO_INDEX=1 mas upgrade 2>&1)
            MAS_TOR1_EXIT=$?
        fi
    else
        MAS_TOR1_OUT="sudo authentication failed; native App Store updates were not started"
        MAS_TOR1_EXIT=1
    fi
    if [ "$MAS_TOR1_EXIT" -eq 0 ]; then
        printf '%s\n' "$MAS_TOR1_OUT"
        print_ok "mas upgrade command completed; the final queue check will verify installation."

        # Second measurement, then one retry in the INVOKING USER's session for
        # whatever the sudo pass left behind. App Store receipts and the signed-in
        # Apple ID belong to the user, not to root; `mas upgrade 310633997` run as
        # the user completed in three seconds on 2026-09-02 for the same WhatsApp
        # update the sudo pass had skipped. The retry is deliberately per-ID and
        # runs exactly once — it is a fallback for a context mismatch, not a loop,
        # and the final queue check still has the last word on what installed.
        MAS_TOR1_LEFT="$(mas_probe_outdated)"
        MAS_TOR1_LEFT_IDS="$(mas_outdated_ids "$MAS_TOR1_LEFT")"
        if [ -n "$MAS_TOR1_LEFT_IDS" ]; then
            print_warn "sudo mas upgrade left these App Store updates pending; retrying in the user session:"
            printf '%s\n' "$MAS_TOR1_LEFT"
            for MAS_RETRY_ID in $MAS_TOR1_LEFT_IDS; do
                MAS_RETRY_OUT=$(run_with_timeout "$MAS_UPGRADE_TIMEOUT" \
                    env MAS_NO_AUTO_INDEX=1 mas upgrade "$MAS_RETRY_ID" 2>&1)
                MAS_RETRY_EXIT=$?
                printf '%s\n' "$MAS_RETRY_OUT"
                if [ "$MAS_RETRY_EXIT" -ne 0 ]; then
                    print_warn "User-session retry failed for App Store id $MAS_RETRY_ID (exit=$MAS_RETRY_EXIT)"
                fi
                if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ]; then
                    {
                        echo "=== TRACK 1 user-session retry: $MAS_RETRY_ID (exit=$MAS_RETRY_EXIT) ==="
                        printf '%s\n' "$MAS_RETRY_OUT"
                    } >> "$MAC_UPDATE_SESSION_DIR/appstore_diag.txt" 2>/dev/null || true
                fi
            done
        fi
    else
        printf '%s\n' "$MAS_TOR1_OUT"
        if [ "$MAS_TOR1_EXIT" -eq 124 ]; then
            print_warn "sudo mas upgrade exceeded ${MAS_UPGRADE_TIMEOUT}s and was stopped."
        fi
        print_warn "$L_TOR_1_ERROR"
        HARD_FAIL=1
        if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ]; then
            {
                echo "=== TRACK 1 (sudo mas upgrade) FAILED ==="
                echo "exit=$MAS_TOR1_EXIT"
                echo "--- output ---"
                printf '%s\n' "$MAS_TOR1_OUT"
            } >> "$MAC_UPDATE_SESSION_DIR/appstore_diag.txt" 2>/dev/null || true
        fi
    fi
fi

# ============================================================
# TRACK 2: App Store GUI automation (iPad apps and others)
# ============================================================
print_header "$L_TOR_2_HEADER"

if [ "${MAC_UPDATE_NONINTERACTIVE:-0}" = "1" ] || [ ! -t 0 ]; then
    print_info "$L_APPSTORE_NONINTERACTIVE_SKIPPED"
    print_header "$L_SCRIPT_2_COMPLETE"
    exit 0
fi

print_info "$L_TOR_2_IPAD_NOTE"
print_info "$L_TOR_2_SOLUTION"
echo ""
print_step "$L_AX_PERMISSION_CHECK"

AX_TEST=$(osascript -e 'tell application "System Events" to return name of first process whose frontmost is true' 2>&1)

# `--` terminates option parsing: the AppleScript error number -1743
# (errAEEventNotPermitted) begins with a dash and would otherwise be consumed as
# grep options ("grep: invalid option -- \" on BSD grep), which silently turned a
# denied-permission probe into a pass.
if printf '%s\n' "$AX_TEST" | grep -qi -e '(-1743)' -e 'not allowed' -e 'assistive' -e 'accessibility' -e 'not authorized'; then
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

GUI_TIMEOUT="${MAC_UPDATE_APPSTORE_GUI_TIMEOUT:-180}"
AS_SCRIPT_DIR="${MAC_UPDATE_SESSION_DIR:-}"
if [ -n "$AS_SCRIPT_DIR" ] && [ -d "$AS_SCRIPT_DIR" ]; then
    AS_SCRIPT_FILE="$AS_SCRIPT_DIR/appstore_track2.scpt"
else
    AS_SCRIPT_FILE="$(mktemp "${TMPDIR:-/tmp}/mac_update_as.XXXXXX")"
fi

cat <<'APPLESCRIPT' > "$AS_SCRIPT_FILE"

tell application "App Store" to activate
delay 2
open location "macappstores://showUpdatesPage"
delay 6

tell application "System Events"
    tell process "App Store"
        set frontmost to true
        delay 2

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

        set updateCount to 0
        try
            set allElems to entire contents of window 1
            repeat with elem in allElems
                try
                    if class of elem is button then
                        set btnName to name of elem
                        if btnName is "Update" or btnName is "Aktualizuj" or btnName is "Aktualisieren" or btnName is "Actualizar" or btnName is "Aggiorna" or btnName is "Atualizar" or btnName is "Actualiser" then
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

if ! AS_RESULT=$(run_with_timeout "$GUI_TIMEOUT" osascript "$AS_SCRIPT_FILE" 2>&1); then
    print_warn "Track 2 (App Store GUI) timed out or failed; review window manually"
    mac_update_severity_register "error" "Track 2 (App Store GUI) timed out or failed"
    if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
        echo "STATUS_FAILED: Track 2 GUI automation failed" >> "$MAC_UPDATE_SESSION_DIR/update_appstore_results.txt"
    fi
    SOFT_FAIL=1
    AS_RESULT="TIMEOUT_OR_FAILED: $AS_RESULT"
fi
rm -f "$AS_SCRIPT_FILE"

echo ""
APPSTORE_TOR2_BRANCH="unexpected"
APPSTORE_TOR2_BACKGROUND=0
if echo "$AS_RESULT" | grep -q "not allowed\|assistive\|Accessibility"; then
    APPSTORE_TOR2_BRANCH="ax_revoked"
    print_warn "$L_APPSTORE_AX_REVOKED"
    print_info "$L_APPSTORE_CHECK_PREFS"
    open "macappstores://showUpdatesPage"
    SOFT_FAIL=1

elif echo "$AS_RESULT" | grep -q "^UPDATE_ALL_CLICKED\|^UPDATE_ALL_DEEP"; then
    APPSTORE_TOR2_BRANCH="update_all"
    APPSTORE_TOR2_BACKGROUND=1
    print_ok "$L_APPSTORE_UPDATE_ALL_CLICKED"
    print_info "$L_APPSTORE_BG_INSTALL"
    print_warn "$L_APPSTORE_WAIT_PROMPT"
    osascript -e 'tell application "System Events" to set visible of process "App Store" to false' >/dev/null 2>&1 || true

elif echo "$AS_RESULT" | grep -q "^INDIVIDUAL_UPDATES:"; then
    APPSTORE_TOR2_BRANCH="individual"
    APPSTORE_TOR2_BACKGROUND=1
    COUNT="${AS_RESULT#INDIVIDUAL_UPDATES:}"
    print_ok "$L_APPSTORE_INDIVIDUAL_UPDATES ($COUNT)"
    print_info "$L_APPSTORE_INSTALLING_BG"
    osascript -e 'tell application "System Events" to set visible of process "App Store" to false' >/dev/null 2>&1 || true

elif echo "$AS_RESULT" | grep -q "^NO_UPDATES_FOUND"; then
    APPSTORE_TOR2_BRANCH="no_updates"
    print_ok "$L_APPSTORE_NO_UPDATES"
    osascript -e 'tell application "App Store" to quit' >/dev/null 2>&1 || true

else
    APPSTORE_TOR2_BRANCH="unexpected"
    print_warn "$L_APPSTORE_UNEXPECTED $AS_RESULT"
    print_info "$L_APPSTORE_MANUAL_UPDATE"
    open "macappstores://showUpdatesPage"
    SOFT_FAIL=1
fi

if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ]; then
    {
        echo ""
        echo "=== TRACK 2 AppleScript ==="
        echo "branch=$APPSTORE_TOR2_BRANCH"
        echo "--- AS_RESULT ---"
        printf '%s\n' "$AS_RESULT"
    } >> "$MAC_UPDATE_SESSION_DIR/appstore_diag.txt" 2>/dev/null || true
fi

# ============================================================
# FINAL VERIFICATION
# ============================================================
print_header "$L_FINAL_CHECK"
if [ "$MAS_OUTDATED_MODE" = "accurate" ]; then
    if ! STILL_OUTDATED=$(run_with_timeout "$MAS_CHECK_TIMEOUT" mas outdated --accurate 2>&1); then
        print_warn "mas outdated --accurate failed; native App Store state is unknown."
        [ -n "$STILL_OUTDATED" ] && printf '%s\n' "$STILL_OUTDATED"
        if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ]; then
            printf 'FINAL native verification failed (mode=accurate):\n%s\n' "$STILL_OUTDATED" \
                >> "$MAC_UPDATE_SESSION_DIR/appstore_diag.txt" 2>/dev/null || true
        fi
        SOFT_FAIL=1
        STILL_OUTDATED=""
    fi
else
    if ! STILL_OUTDATED=$(run_with_timeout "$MAS_CHECK_TIMEOUT" mas outdated 2>&1); then
        print_warn "mas outdated failed; native App Store state is unknown."
        [ -n "$STILL_OUTDATED" ] && printf '%s\n' "$STILL_OUTDATED"
        if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ]; then
            printf 'FINAL native verification failed (mode=default):\n%s\n' "$STILL_OUTDATED" \
                >> "$MAC_UPDATE_SESSION_DIR/appstore_diag.txt" 2>/dev/null || true
        fi
        SOFT_FAIL=1
        STILL_OUTDATED=""
    fi
fi
if [ -z "$STILL_OUTDATED" ] && [ "$HARD_FAIL" -eq 0 ] && [ "$SOFT_FAIL" -eq 0 ]; then
    print_ok "$L_APPSTORE_NO_UPDATES"
elif [ -n "$STILL_OUTDATED" ]; then
    print_warn "$L_STILL_OUTDATED"
    echo "$STILL_OUTDATED"
    SOFT_FAIL=1
    if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ]; then
        {
            echo ""
            echo "=== FINAL: mas outdated still reports updates ==="
            printf '%s\n' "$STILL_OUTDATED"
        } >> "$MAC_UPDATE_SESSION_DIR/appstore_diag.txt" 2>/dev/null || true
    fi
fi
if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ]; then
    {
        echo ""
        echo "=== mas outdated after both tracks ==="
        printf '%s\n' "${STILL_OUTDATED:-none}"
    } >> "$MAC_UPDATE_SESSION_DIR/appstore_diag.txt" 2>/dev/null || true
fi

if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ]; then
    PENDING_APPSTORE="$(mas_outdated_ids "$STILL_OUTDATED" | wc -l | tr -d ' ')"
    printf '%s\n' "${PENDING_APPSTORE:-0}" > "$MAC_UPDATE_SESSION_DIR/pending_appstore"
fi

if [ "$APPSTORE_TOR2_BACKGROUND" -eq 1 ]; then
    print_warn "Track 2 is still installing in the background; its completion is not verified by mas ($MAS_OUTDATED_MODE checks native apps only)."
    SOFT_FAIL=1
    if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ]; then
        {
            echo ""
            echo "=== TRACK 2 BACKGROUND_UNVERIFIED ==="
            echo "branch=$APPSTORE_TOR2_BRANCH"
            echo "Native verification mode=$MAS_OUTDATED_MODE"
        } >> "$MAC_UPDATE_SESSION_DIR/appstore_diag.txt" 2>/dev/null || true
    fi
fi

# ── mas snapshot AFTER update ────────────────────────────────
if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
    print_info "$L_SNAPSHOT_AFTER"
    sleep 3
    if mas list 2>/dev/null > "$MAC_UPDATE_SESSION_DIR/mas_after.txt"; then
        print_ok "$L_SNAPSHOTS_SAVED $MAC_UPDATE_SESSION_DIR"
    else
        print_warn "Could not save the post-update App Store snapshot."
        SOFT_FAIL=1
    fi
fi

APPSTORE_EXIT="$(mac_update_severity_exit_code)"
if [ "$APPSTORE_EXIT" -eq 0 ]; then
    print_header "$L_SCRIPT_2_COMPLETE"
    if [ -z "$NATIVE_OUTDATED" ]; then
        print_info "Track 1 (mas): no pending native updates; sudo was not requested."
    else
        print_info "$L_SCRIPT_2_SUMMARY_TOR1"
    fi
    if [ "$APPSTORE_TOR2_BRANCH" = "no_updates" ]; then
        print_info "Track 2 (App Store UI): no pending GUI updates were found."
    else
        print_info "$L_SCRIPT_2_SUMMARY_TOR2"
        print_warn "$L_SCRIPT_2_CHECK_WINDOW"
    fi
elif [ "$APPSTORE_EXIT" -eq "$MAC_UPDATE_SOFT_EXIT" ]; then
    # Soft is the expected outcome whenever Track 2 queued installs: the App Store
    # keeps downloading in the background and `mas outdated` still lists those apps
    # until it finishes. Reporting that as an error trained users to ignore the
    # banner, so the three states are kept distinct here exactly as update_all.sh
    # does: clean / warnings / errors.
    print_header "⚠️  SCRIPT 2 FINISHED WITH WARNINGS"
    if [ "$APPSTORE_TOR2_BACKGROUND" -eq 1 ]; then
        print_info "App Store is still installing in the background; mas cannot confirm those apps until it finishes. Re-run later to verify."
    else
        print_info "Some App Store state could not be verified; review the diagnostics above. Nothing was left mid-install."
    fi
else
    print_header "❌ SCRIPT 2 FINISHED WITH ERRORS"
    print_info "An App Store operation failed; review the diagnostics above."
fi
echo ""
exit "$APPSTORE_EXIT"
