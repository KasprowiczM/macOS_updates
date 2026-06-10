#!/usr/bin/env bash
# ============================================================
# SCRIPT 5: Update internet-downloaded applications
# ============================================================
# Autor: mk | Data: 2026-03-18 (zaktualizowano)
set -o pipefail

# Kompatybilność: bash 3.2+ (macOS domyślny shell, Apple Silicon arm64)
#
# Aplikacje objęte skryptem:
#   PRZEGLĄDARKI:     Google Chrome, Firefox Dev Edition, Brave, ChatGPT Atlas
#   AI:               ChatGPT, Claude, Gemini, Comet, Perplexity Desktop,
#                     Antigravity, Antigravity IDE, LM Studio, Codex, OpenCode Desktop
#   VPN/BEZP.:        ProtonVPN, KeePassXC
#   POCZTA/KOMUN.:    Proton Mail, Zoom
#   CHMURA:           Google Drive, MEGAsync, Proton Drive
#   MICROSOFT 365:    Word, Excel, PowerPoint, Outlook, OneNote, Teams (via msupdate)
#   DEV TOOLS:        VS Code, CodeEdit, Docker Desktop, Warp, Cursor, Ascendo
#   PRODUKTYWNOŚĆ:    AppCleaner, Obsidian
#   MULTIMEDIA:       Spotify
#   KRYPTO:           Ledger Live/Wallet, Trezor Suite
#   SIEĆ/IT:          Remote Desktop Manager
#
#   * = tylko powiadomienie/informacja, wymagana ręczna aktualizacja
#
# Metody aktualizacji:
#   - GitHub API + pobieranie DMG: Firefox Dev Edition, KeePassXC,
#     CodeEdit, Trezor Suite (arm64)
#   - Google Keystone agent: Google Chrome, Google Drive
#   - Microsoft AutoUpdate (msupdate CLI): cały pakiet Microsoft 365
#   - Docker Desktop CLI: docker desktop update (v4.37+)
#   - Wbudowany auto-updater (silent_launch_app → open -gjF): większość pozostałych
#     Apps są uruchamiane w tle ukryte; Sparkle/Squirrel/Omaha/Electron i tak
#     wykonują sprawdzenie aktualizacji przy starcie, bez aktywacji okna.
# ============================================================

# Kolory
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m'

# Katalog z skryptami
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Shared libraries ─────────────────────────────────────────
. "$SCRIPT_DIR/lib/internet_apps.sh"
. "$SCRIPT_DIR/lib/internet_registry.sh"
. "$SCRIPT_DIR/lib/internet_handlers.sh"
. "$SCRIPT_DIR/lib/github_release.sh"
. "$SCRIPT_DIR/lib/internet_i18n.sh"
. "$SCRIPT_DIR/lib/platform.sh"

mac_update_require_apple_silicon || exit 1
. "$SCRIPT_DIR/lib/ui.sh"

# ── i18n: load language strings ──────────────────────────────
. "$SCRIPT_DIR/i18n/loader.sh"

print_header() { ui_print_header "$1"; }

print_ok()    { echo -e "  ${GREEN}✅ $1${NC}"; }
print_info()  { echo -e "  ${CYAN}ℹ️  $1${NC}"; }
print_warn()  { echo -e "  ${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "  ${RED}❌ $1${NC}"; }
print_step()  { echo -e "  ${MAGENTA}▶  $1${NC}"; }

INTERNET_EXIT=0
INTERNET_TEMP_ROOT="${MAC_UPDATE_SESSION_DIR:-}"
INTERNET_TEMP_OWNED=0
if [ -z "$INTERNET_TEMP_ROOT" ]; then
    INTERNET_TEMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/mac_update_internet.XXXXXX")"
    INTERNET_TEMP_OWNED=1
fi
chmod 700 "$INTERNET_TEMP_ROOT" 2>/dev/null || true

cleanup_internet_temp() {
    if [ "$INTERNET_TEMP_OWNED" -eq 1 ]; then
        case "$INTERNET_TEMP_ROOT" in
            "${TMPDIR:-/tmp}"/mac_update_internet.*|/tmp/mac_update_internet.*)
                rm -rf "$INTERNET_TEMP_ROOT" 2>/dev/null || true
                ;;
        esac
    fi
}
trap cleanup_internet_temp EXIT

make_temp_dmg() {
    mktemp "$INTERNET_TEMP_ROOT/$1.XXXXXX.dmg"
}

verify_dmg() {
    local dmg_path="$1"
    hdiutil verify "$dmg_path" -quiet >/dev/null 2>&1
}

verify_app_signature() {
    local app_path="$1"
    spctl --assess --type execute "$app_path" >/dev/null 2>&1
}

copy_verified_app() {
    if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
        print_warn "[DRY-RUN] skip copy: $2"
        return 0
    fi
    local app_path="$1"
    local app_label="$2"
    if ! verify_app_signature "$app_path"; then
        print_warn "$(internet_msg "$L_INTERNET_GATEKEEPER_REJECTED" "$app_label")"
        return 1
    fi
    local dest="/Applications/$app_label"
    if [ -d "$dest" ]; then
        rm -rf "$dest" || true
    fi
    cp -R "$app_path" "$dest" 2>/dev/null
}

run_with_timeout() {
    local seconds="$1"
    shift
    if command -v timeout >/dev/null 2>&1; then
        timeout "$seconds" "$@"
    elif command -v gtimeout >/dev/null 2>&1; then
        gtimeout "$seconds" "$@"
    else
        "$@"
    fi
}

# silent_launch_app — trigger a Mac app's built-in auto-updater without
# bringing windows to the foreground.
#   -g : background launch (does not activate; no Dock bounce)
#   -j : launches with the Hidden flag set (no visible windows)
#   -F : opens "fresh" — no window/state restoration from previous session
# Sparkle / Squirrel / Omaha / Electron updaters all run on launch
# regardless of foreground state, so apps still self-update silently.
# Accepts either an app name (-a) or a path; falls back if -F is rejected.
silent_launch_app() {
    local target="$1"
    if [ -z "$target" ]; then
        return 1
    fi
    # Path vs name detection: a leading "/" means full path
    case "$target" in
        /*)
            open -gjF "$target" 2>/dev/null \
                || open -gj "$target" 2>/dev/null \
                || open "$target" 2>/dev/null \
                || return 1
            ;;
        *)
            open -gjF -a "$target" 2>/dev/null \
                || open -gj -a "$target" 2>/dev/null \
                || open -a "$target" 2>/dev/null \
                || return 1
            ;;
    esac
    return 0
}

# ── Pomocnik: wersja aplikacji ──────────────────────────────
app_version() {
    local app_path="$1"
    defaults read "$app_path/Contents/Info" CFBundleShortVersionString 2>/dev/null \
        || defaults read "$app_path/Contents/Info" CFBundleVersion 2>/dev/null \
        || echo "$L_INTERNET_VERSION_UNKNOWN"
}

capture_app_path() {
    internet_app_path "$1"
}

firefox_dev_version() {
    internet_firefox_snapshot_version
}

capture_internet_app_versions() {
    internet_capture_versions "$1"
}

# ── Snapshot PRZED aktualizacją ───────────────────────────────
if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
    : > "$MAC_UPDATE_SESSION_DIR/internet_diag.txt"
    internet_diag_section "Internet apps update start"
    print_info "$L_INTERNET_SNAPSHOT_BEFORE"
    capture_internet_app_versions "$MAC_UPDATE_SESSION_DIR/internet_before.txt"
fi

# ============================================================
print_header "$L_SCRIPT_TITLE_INTERNET"
if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
    print_warn "$L_INTERNET_DRY_RUN"
fi
print_info "$L_INTERNET_CHECKING_APPS"
if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
    print_info "[DRY-RUN] Would check all apps in config/internet_apps.txt (no downloads, mounts, or copies)"
    internet_diag_section "DRY-RUN"
    internet_diag_log "Dry-run: skipped all internet app mutations"
    print_header "$L_INTERNET_SCRIPT_DONE"
    exit 0
fi
echo ""

# ── Inicjalizacja statusów (bash 3.2 — bez tablic asocjacyjnych) ──
STATUS_CHROME="$L_INTERNET_STATUS_SKIPPED"
STATUS_FIREFOX="$L_INTERNET_STATUS_SKIPPED"
STATUS_BRAVE="$L_INTERNET_STATUS_SKIPPED"
STATUS_ATLAS="$L_INTERNET_STATUS_SKIPPED"
STATUS_CHATGPT="$L_INTERNET_STATUS_SKIPPED"
STATUS_CLAUDE_APP="$L_INTERNET_STATUS_SKIPPED"
STATUS_GEMINI="$L_INTERNET_STATUS_SKIPPED"
STATUS_COMET="$L_INTERNET_STATUS_SKIPPED"
STATUS_PERPLEXITY="$L_INTERNET_STATUS_SKIPPED"
STATUS_ANTIGRAVITY="$L_INTERNET_STATUS_SKIPPED"
STATUS_ANTIGRAVITY_IDE="$L_INTERNET_STATUS_SKIPPED"
STATUS_LMSTUDIO="$L_INTERNET_STATUS_SKIPPED"
STATUS_CODEX="$L_INTERNET_STATUS_SKIPPED"
STATUS_PROTONVPN="$L_INTERNET_STATUS_SKIPPED"
STATUS_KEEPASSXC="$L_INTERNET_STATUS_SKIPPED"
STATUS_PROTONMAIL="$L_INTERNET_STATUS_SKIPPED"
STATUS_PROTONDRIVE="$L_INTERNET_STATUS_SKIPPED"
STATUS_ZOOM="$L_INTERNET_STATUS_SKIPPED"
STATUS_GOOGLEDRIVE="$L_INTERNET_STATUS_SKIPPED"
STATUS_MEGASYNC="$L_INTERNET_STATUS_SKIPPED"
STATUS_MICROSOFT="$L_INTERNET_STATUS_SKIPPED"
STATUS_VSCODE="$L_INTERNET_STATUS_SKIPPED"
STATUS_CODEEDIT="$L_INTERNET_STATUS_SKIPPED"
STATUS_DOCKER="$L_INTERNET_STATUS_SKIPPED"
STATUS_WARP="$L_INTERNET_STATUS_SKIPPED"
STATUS_CURSOR="$L_INTERNET_STATUS_SKIPPED"
STATUS_ASCENDO="$L_INTERNET_STATUS_SKIPPED"
STATUS_APPCLEANER="$L_INTERNET_STATUS_SKIPPED"
STATUS_OBSIDIAN="$L_INTERNET_STATUS_SKIPPED"
STATUS_SPOTIFY="$L_INTERNET_STATUS_SKIPPED"
STATUS_LEDGER="$L_INTERNET_STATUS_SKIPPED"
STATUS_TREZOR="$L_INTERNET_STATUS_SKIPPED"
STATUS_IPMIVIEW="$L_INTERNET_STATUS_SKIPPED"
STATUS_RDMANAGER="$L_INTERNET_STATUS_SKIPPED"
STATUS_OPENCODE="$L_INTERNET_STATUS_SKIPPED"
STATUS_INKSCAPE="$L_INTERNET_STATUS_SKIPPED"

# ============================================================
# App handlers — config/internet_dispatch_order.txt
# ============================================================
. "$SCRIPT_DIR/lib/internet_app_updates.sh"
internet_dispatch_run_all

# ── Snapshot PO aktualizacji ──────────────────────────────────
if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
    print_info "$L_INTERNET_SNAPSHOT_AFTER"
    sleep 15  # Daj czas auto-updatrom na zaktualizowanie Info.plist
    capture_internet_app_versions "$MAC_UPDATE_SESSION_DIR/internet_after.txt"
    print_ok "$(internet_msg "$L_INTERNET_SNAPSHOTS_SAVED" "$MAC_UPDATE_SESSION_DIR")"
fi

# ============================================================
# PODSUMOWANIE
# ============================================================
print_header "$L_INTERNET_SUMMARY_TITLE"

echo -e "  ${BOLD}$L_INTERNET_SECTION_BROWSERS${NC}"
printf "  %-32s %s\n" "Google Chrome:"            "$STATUS_CHROME"
printf "  %-32s %s\n" "Firefox Dev Edition:"      "$STATUS_FIREFOX"
printf "  %-32s %s\n" "Brave Browser:"            "$STATUS_BRAVE"
printf "  %-32s %s\n" "ChatGPT Atlas:"            "$STATUS_ATLAS"
echo ""

echo -e "  ${BOLD}$L_INTERNET_SECTION_AI${NC}"
printf "  %-32s %s\n" "ChatGPT:"                  "$STATUS_CHATGPT"
printf "  %-32s %s\n" "Claude Desktop:"           "$STATUS_CLAUDE_APP"
printf "  %-32s %s\n" "Gemini Desktop:"           "$STATUS_GEMINI"
printf "  %-32s %s\n" "Comet (Perplexity Browser):" "$STATUS_COMET"
printf "  %-32s %s\n" "Perplexity Desktop:"       "$STATUS_PERPLEXITY"
printf "  %-32s %s\n" "Antigravity:"              "$STATUS_ANTIGRAVITY"
printf "  %-32s %s\n" "Antigravity IDE:"          "$STATUS_ANTIGRAVITY_IDE"
printf "  %-32s %s\n" "LM Studio:"                "$STATUS_LMSTUDIO"
printf "  %-32s %s\n" "Codex Desktop:"            "$STATUS_CODEX"
printf "  %-32s %s\n" "OpenCode Desktop:"         "$STATUS_OPENCODE"
echo ""

echo -e "  ${BOLD}$L_INTERNET_SECTION_VPN${NC}"
printf "  %-32s %s\n" "ProtonVPN:"                "$STATUS_PROTONVPN"
printf "  %-32s %s\n" "KeePassXC:"                "$STATUS_KEEPASSXC"
echo ""

echo -e "  ${BOLD}$L_INTERNET_SECTION_MAIL${NC}"
printf "  %-32s %s\n" "Proton Mail:"              "$STATUS_PROTONMAIL"
printf "  %-32s %s\n" "Zoom:"                     "$STATUS_ZOOM"
echo ""

echo -e "  ${BOLD}$L_INTERNET_SECTION_CLOUD${NC}"
printf "  %-32s %s\n" "Google Drive:"             "$STATUS_GOOGLEDRIVE"
printf "  %-32s %s\n" "MEGAsync:"                 "$STATUS_MEGASYNC"
printf "  %-32s %s\n" "Proton Drive:"             "$STATUS_PROTONDRIVE"
echo ""

echo -e "  ${BOLD}$L_INTERNET_SECTION_MICROSOFT${NC}"
printf "  %-32s %s\n" "Microsoft 365 (msupdate):" "$STATUS_MICROSOFT"
echo ""

echo -e "  ${BOLD}$L_INTERNET_SECTION_DEV${NC}"
printf "  %-32s %s\n" "Visual Studio Code:"       "$STATUS_VSCODE"
printf "  %-32s %s\n" "CodeEdit:"                 "$STATUS_CODEEDIT"
printf "  %-32s %s\n" "Docker Desktop:"           "$STATUS_DOCKER"
printf "  %-32s %s\n" "Warp:"                     "$STATUS_WARP"
printf "  %-32s %s\n" "Cursor:"                   "$STATUS_CURSOR"
printf "  %-32s %s\n" "Ascendo:"                  "$STATUS_ASCENDO"
echo ""

echo -e "  ${BOLD}$L_INTERNET_SECTION_PRODUCTIVITY${NC}"
printf "  %-32s %s\n" "AppCleaner:"               "$STATUS_APPCLEANER"
printf "  %-32s %s\n" "Obsidian:"                 "$STATUS_OBSIDIAN"
echo ""

echo -e "  ${BOLD}$L_INTERNET_SECTION_MULTIMEDIA${NC}"
printf "  %-32s %s\n" "Spotify:"                  "$STATUS_SPOTIFY"
printf "  %-32s %s\n" "Inkscape:"                 "$STATUS_INKSCAPE"
echo ""

echo -e "  ${BOLD}$L_INTERNET_SECTION_CRYPTO${NC}"
printf "  %-32s %s\n" "Ledger Live/Wallet:"       "$STATUS_LEDGER"
printf "  %-32s %s\n" "Trezor Suite:"             "$STATUS_TREZOR"
echo ""

echo -e "  ${BOLD}$L_INTERNET_SECTION_NETWORK${NC}"
printf "  %-32s %s\n" "Remote Desktop Manager:"   "$STATUS_RDMANAGER"
printf "  %-32s %s\n" "IPMIView:"                 "$STATUS_IPMIVIEW"

echo ""
echo -e "  ${YELLOW}──────────────────────────────────────────────────────${NC}"
print_info "$L_INTERNET_CHECKED_NOTE"
print_info "$L_INTERNET_INSTRUCTIONS"

for status in \
    "$STATUS_CHROME" "$STATUS_FIREFOX" "$STATUS_BRAVE" "$STATUS_ATLAS" \
    "$STATUS_CHATGPT" "$STATUS_CLAUDE_APP" "$STATUS_GEMINI" "$STATUS_COMET" "$STATUS_PERPLEXITY" \
    "$STATUS_ANTIGRAVITY" "$STATUS_ANTIGRAVITY_IDE" "$STATUS_LMSTUDIO" "$STATUS_CODEX" "$STATUS_OPENCODE" \
    "$STATUS_PROTONVPN" "$STATUS_KEEPASSXC" "$STATUS_PROTONMAIL" "$STATUS_ZOOM" \
    "$STATUS_GOOGLEDRIVE" "$STATUS_MEGASYNC" "$STATUS_PROTONDRIVE" "$STATUS_MICROSOFT" \
    "$STATUS_VSCODE" "$STATUS_CODEEDIT" "$STATUS_DOCKER" "$STATUS_WARP" "$STATUS_CURSOR" "$STATUS_ASCENDO" \
    "$STATUS_APPCLEANER" "$STATUS_OBSIDIAN" "$STATUS_SPOTIFY" \
    "$STATUS_LEDGER" "$STATUS_TREZOR" \
    "$STATUS_RDMANAGER" "$STATUS_IPMIVIEW" "$STATUS_INKSCAPE"
do
    case "$status" in
        *"⚠️"*)
            INTERNET_EXIT=1
            ;;
    esac
done

if [ "$INTERNET_EXIT" -ne 0 ]; then
    print_warn "$L_INTERNET_PARTIAL_FAILURE"
fi
print_header "$L_INTERNET_SCRIPT_DONE"
exit "$INTERNET_EXIT"
