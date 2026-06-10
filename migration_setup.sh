#!/usr/bin/env bash
# ============================================================
# migration_setup.sh — macOS Updates: Migration Setup
# ============================================================
# Data: 2026-03-12 | Zaktualizowano: 2026-06-09
# Kompatybilność: bash 3.2+ · Apple Silicon (arm64) only
set -o pipefail
#
# URUCHOM JAKO PIERWSZY po skopiowaniu folderu na nowego MacBooka.
#
# Co robi ten skrypt:
#   1.  Wykrywa dane nowego systemu (użytkownik, macOS, architektura)
#   2.  Wykrywa stary username z plików .md i naprawia ścieżki
#   3.  Aktualizuje wersję macOS i arch w CLAUDE.md, AGENTS.md, GEMINI.md
#   4.  Sprawdza i instaluje Xcode Command Line Tools
#   5.  Sprawdza i instaluje Homebrew (z właściwą ścieżką arm64/Intel)
#   6.  Sprawdza i instaluje mas (App Store CLI)
#   7.  Sprawdza dostępność Python 3
#   8.  Sprawdza inne narzędzia: curl, git, jq
#   9.  Weryfikuje opcjonalne narzędzia: msupdate, docker, keystone
#   10. Nadaje chmod +x wszystkim skryptom *.sh
#   11. Sprawdza zalogowanie do App Store (mas)
#   12. Sprawdza uprawnienie Accessibility dla terminala (AppleScript)
#   13. Skanuje zainstalowane aplikacje → aktualizuje wersje w APPLICATIONS.md
#   14. Rejestruje migrację w UPDATES.md
#   15. Naprawia konfiguracje MCP (Gemini/Windsurf)
#   16. Wyświetla pełne podsumowanie z checklistą akcji manualnych
#
# Użycie:
#   bash migration_setup.sh
#   # lub po chmod +x:
#   ./migration_setup.sh
# ============================================================

# ── Kolory ───────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m'

# ── Funkcje pomocnicze ────────────────────────────────────────
print_banner() {
    local title="${1:-$L_MIGRATION_FIRST_RUN}"
    echo ""
    echo -e "${BLUE}${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}${BOLD}║                                                              ║${NC}"
    echo -e "${BLUE}${BOLD}║   🚀  ${title}${NC}"
    echo -e "${BLUE}${BOLD}║                                                              ║${NC}"
    echo -e "${BLUE}${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_section() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_ok()     { echo -e "  ${GREEN}✅  $1${NC}"; }
print_info()   { echo -e "  ${CYAN}ℹ️   $1${NC}"; }
print_warn()   { echo -e "  ${YELLOW}⚠️   $1${NC}"; }
print_error()  { echo -e "  ${RED}❌  $1${NC}"; }
print_step()   { echo -e "  ${MAGENTA}▶   $1${NC}"; }
print_action() { echo -e "  ${YELLOW}${BOLD}⬛ ${L_UI_REQUIRED_ACTION} $1${NC}"; }
print_fixed()  { echo -e "  ${GREEN}🔧  ${L_UI_FIXED} $1${NC}"; }
print_skip()   { echo -e "  ${CYAN}⏭️   ${L_UI_SKIPPED} $1${NC}"; }

# ── Śledzenie wyników do podsumowania ────────────────────────
ACTIONS_REQUIRED=""   # newline-separated list of required manual actions
FIXES_APPLIED=""      # newline-separated list of applied fixes
WARNINGS=""           # newline-separated list of warnings

add_action()  { ACTIONS_REQUIRED="${ACTIONS_REQUIRED}${1}\n"; }
add_fix()     { FIXES_APPLIED="${FIXES_APPLIED}${1}\n"; }
add_warning() { WARNINGS="${WARNINGS}${1}\n"; }

# Katalog skryptu (nowa lokalizacja na nowym Macu) — MUST BE EARLY for i18n loader
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

. "$SCRIPT_DIR/lib/platform.sh"
mac_update_require_apple_silicon || exit 1

# ── i18n: load language strings ──────────────────────────────
. "$SCRIPT_DIR/i18n/loader.sh"

MIGRATION_EXIT=0

# ============================================================
# PHASE 0a: LANGUAGE SELECTION (before localized banner)
# ============================================================
print_section "$L_MIGRATION_PHASE_0A"

if ! grep -q "^MAC_LANG=" "$SCRIPT_DIR/.mac_update_prefs" 2>/dev/null; then
    print_info "$L_LANG_PICKER_INTRO"
    CHOSEN_LANG=$(ask_language_picker)
    save_language_pref "$CHOSEN_LANG"
    MAC_LANG="$CHOSEN_LANG"
    # shellcheck disable=SC1090
    . "$SCRIPT_DIR/i18n/loader.sh"
    print_ok "$L_LANG_SET_TO $L_LANG_NAME"
else
    print_ok "$L_LANG_CURRENT $L_LANG_NAME ($MAC_LANG)"
    echo ""
    read -r -p "  $L_LANG_CHANGE_PROMPT [y/N]: " CHANGE_LANG
    CHANGE_LANG="${CHANGE_LANG:-N}"
    if [[ "$CHANGE_LANG" =~ ^[Yyt] ]]; then
        CHOSEN_LANG=$(ask_language_picker)
        save_language_pref "$CHOSEN_LANG"
        MAC_LANG="$CHOSEN_LANG"
        # shellcheck disable=SC1090
        . "$SCRIPT_DIR/i18n/loader.sh"
        print_ok "$L_LANG_CHANGED_TO $L_LANG_NAME"
    fi
fi

# ============================================================
print_banner "$L_MIGRATION_FIRST_RUN"
echo -e "  ${BOLD}$L_MIGRATION_CONFIRM${NC}"
echo ""
read -r -p "  $L_CONTINUE_PROMPT [T/n]: " CONFIRM_START
CONFIRM_START="${CONFIRM_START:-T}"
if [[ "$CONFIRM_START" =~ ^[Nn] ]]; then
    echo "  $L_CANCELED"
    exit 0
fi

# ============================================================
# PHASE 0b: CLOUD STORAGE PROVIDER SETUP
# ============================================================
print_section "$L_MIGRATION_PHASE_0B"

if [ ! -f "$SCRIPT_DIR/.dev_sync_config.json" ]; then
    print_info "$L_CLOUD_NOT_CONFIGURED"
    print_info "$L_CLOUD_BACKUP_HINT"
    echo ""
    if [ -f "$SCRIPT_DIR/dev_sync/provider_setup.sh" ]; then
        bash "$SCRIPT_DIR/dev_sync/provider_setup.sh" "$SCRIPT_DIR"
    else
        print_warn "$L_CLOUD_PROVIDER_MISSING: $SCRIPT_DIR/dev_sync/"
        print_info "$L_CLOUD_CONFIGURE_LATER"
    fi
else
    print_ok "$L_CLOUD_ALREADY_CONFIGURED"
fi

# ============================================================
# PHASE 1: SYSTEM DETECTION
# ============================================================
print_section "$L_PHASE_1_TITLE"
print_info "$L_INFO_PROJECT_DIR $SCRIPT_DIR"

NEW_USER="$(whoami)"
NEW_HOME="$HOME"
print_info "$L_INFO_USER $NEW_USER"
print_info "$L_INFO_HOME $NEW_HOME"

# macOS wersja
MACOS_VERSION="$(sw_vers -productVersion 2>/dev/null || echo 'unknown')"
MACOS_BUILD="$(sw_vers -buildVersion 2>/dev/null || echo 'unknown')"
MACOS_MAJOR="$(echo "$MACOS_VERSION" | cut -d. -f1)"
print_info "$L_INFO_MACOS $MACOS_VERSION (build: $MACOS_BUILD)"

# Architektura
ARCH="$(uname -m)"
if [ "$ARCH" = "arm64" ]; then
    ARCH_LABEL="$L_ARCH_APPLE_SILICON"
    BREW_PREFIX="/opt/homebrew"
else
    ARCH_LABEL="$L_ARCH_INTEL"
    BREW_PREFIX="/usr/local"
fi
print_info "$L_INFO_ARCH $ARCH_LABEL"
print_info "$L_INFO_BREW_PREFIX $BREW_PREFIX"

# Hostname
HOSTNAME_NEW="$(scutil --get ComputerName 2>/dev/null || hostname 2>/dev/null || echo 'unknown')"
print_info "$L_INFO_HOSTNAME $HOSTNAME_NEW"

# Powłoka domyślna
DEFAULT_SHELL="$(dscl . -read /Users/"$NEW_USER" UserShell 2>/dev/null | awk '{print $2}' || echo "$SHELL")"
print_info "$L_INFO_SHELL $DEFAULT_SHELL"

# Profil powłoki
if echo "$DEFAULT_SHELL" | grep -q "zsh"; then
    SHELL_PROFILE="$NEW_HOME/.zshrc"
elif echo "$DEFAULT_SHELL" | grep -q "bash"; then
    SHELL_PROFILE="$NEW_HOME/.bash_profile"
else
    SHELL_PROFILE="$NEW_HOME/.zshrc"
fi
print_info "$L_INFO_SHELL_PROFILE $SHELL_PROFILE"

# Wykryj terminal (dla Accessibility)
TERM_APP_NAME="Terminal.app"
case "${TERM_PROGRAM:-}" in
    "Apple_Terminal") TERM_APP_NAME="Terminal.app" ;;
    "iTerm.app") TERM_APP_NAME="iTerm.app" ;;
    "WarpTerminal") TERM_APP_NAME="Warp.app" ;;
    "vscode") TERM_APP_NAME="Visual Studio Code.app" ;;
    "Cursor") TERM_APP_NAME="Cursor.app" ;;
    "ghostty") TERM_APP_NAME="Ghostty.app" ;;
esac
print_info "$L_INFO_TERMINAL $TERM_APP_NAME (TERM_PROGRAM=${TERM_PROGRAM:-$L_TERM_UNKNOWN})"

# ============================================================
# PHASE 2: Detect old user and paths
# ============================================================
print_section "$L_PHASE_2_TITLE"

OLD_USER=""
OLD_PATH=""

# Szukaj wzorca /Users/<username>/ w CLAUDE.md
if [ -f "$SCRIPT_DIR/CLAUDE.md" ]; then
    OLD_USER_RAW="$(grep -oE '/Users/[^/]+/' "$SCRIPT_DIR/CLAUDE.md" 2>/dev/null | head -1)"
    if [ -n "$OLD_USER_RAW" ]; then
        OLD_USER="$(echo "$OLD_USER_RAW" | sed 's|/Users/||' | sed 's|/||')"
    fi

    # Szukaj pełnej ścieżki projektu np. /Users/<USERNAME>/Dev_Env/macOS_updates
    OLD_PATH="$(grep -oE '`/Users/[^`]+`' "$SCRIPT_DIR/CLAUDE.md" 2>/dev/null | head -1 | tr -d '`')"
fi

if [ -n "$OLD_USER" ] && [ "$OLD_USER" != "$NEW_USER" ]; then
    print_info "$(printf "$L_MIG_OLD_USER" "$OLD_USER")"
    print_info "$(printf "$L_MIG_NEW_USER" "$NEW_USER")"
    print_info "$(printf "$L_MIG_OLD_PATH" "${OLD_PATH:-/Users/$OLD_USER/...}")"
    print_info "$(printf "$L_MIG_NEW_PATH" "$SCRIPT_DIR")"
elif [ -n "$OLD_USER" ] && [ "$OLD_USER" = "$NEW_USER" ]; then
    print_ok "$(printf "$L_MIG_USER_UNCHANGED" "$NEW_USER")"
    OLD_USER=""  # Nic do naprawienia w zakresie username
    # Sprawdź czy ścieżka projektu się zmieniła
    if [ -n "$OLD_PATH" ] && [ "$OLD_PATH" != "$SCRIPT_DIR" ]; then
        print_info "$L_MIG_PATH_MOVED"
        print_info "$(printf "$L_MIG_PATH_OLD" "$OLD_PATH")"
        print_info "$(printf "$L_MIG_PATH_NEW" "$SCRIPT_DIR")"
    fi
else
    print_info "$L_MIG_FRESH_INSTALL"
fi

# ============================================================
# FAZA 3: NAPRAWA ŚCIEŻEK W PLIKACH .md
# ============================================================
print_section "$L_PHASE_3_TITLE"

MD_CHANGED=0

for md_file in "$SCRIPT_DIR/CLAUDE.md" "$SCRIPT_DIR/AGENTS.md" "$SCRIPT_DIR/GEMINI.md" "$SCRIPT_DIR/UPDATES.md" "$SCRIPT_DIR/APPLICATIONS.md"; do
    [ -f "$md_file" ] || continue

    CHANGED=0
    TMPFILE="$(mktemp)"

    # Skopiuj oryginał do tmp
    cp "$md_file" "$TMPFILE"

    # 1. Zastąp stary username nowym (jeśli się różni)
    if [ -n "$OLD_USER" ] && [ "$OLD_USER" != "$NEW_USER" ]; then
        sed -i '' "s|/Users/${OLD_USER}/|/Users/${NEW_USER}/|g" "$TMPFILE"
        if ! diff -q "$md_file" "$TMPFILE" > /dev/null 2>&1; then
            CHANGED=1
        fi
    fi

    # 2. Zastąp stary path projektu nowym (jeśli się różni)
    if [ -n "$OLD_PATH" ] && [ "$OLD_PATH" != "$SCRIPT_DIR" ]; then
        # Escape special chars for sed
        OLD_PATH_ESC="$(echo "$OLD_PATH" | sed 's|/|\\/|g')"
        SCRIPT_DIR_ESC="$(echo "$SCRIPT_DIR" | sed 's|/|\\/|g')"
        sed -i '' "s|${OLD_PATH_ESC}|${SCRIPT_DIR_ESC}|g" "$TMPFILE"
        if ! diff -q "$md_file" "$TMPFILE" > /dev/null 2>&1; then
            CHANGED=1
        fi
    fi

    # 3. Zastąp ~/ ścieżki Homebrew jeśli arch się zmieniła (arm→intel lub odwrotnie)
    # (np. /usr/local/bin/brew → /opt/homebrew/bin/brew dla arm64)
    if [ "$ARCH" = "arm64" ]; then
        sed -i '' 's|/usr/local/bin/brew|/opt/homebrew/bin/brew|g' "$TMPFILE"
        sed -i '' 's|/usr/local/Cellar|/opt/homebrew/Cellar|g' "$TMPFILE"
    else
        sed -i '' 's|/opt/homebrew/bin/brew|/usr/local/bin/brew|g' "$TMPFILE"
        sed -i '' 's|/opt/homebrew/Cellar|/usr/local/Cellar|g' "$TMPFILE"
    fi
    if ! diff -q "$md_file" "$TMPFILE" > /dev/null 2>&1; then
        CHANGED=1
    fi

    if [ $CHANGED -eq 1 ]; then
        cp "$TMPFILE" "$md_file"
        FNAME="$(basename "$md_file")"
        print_fixed "$(printf "$L_MIG_PATHS_UPDATED" "$(basename "$md_file")")"
        add_fix "$(printf "$L_MIG_PATHS_FIX" "$FNAME" "$OLD_USER" "$NEW_USER" "$SCRIPT_DIR")"
        MD_CHANGED=$((MD_CHANGED + 1))
    else
        print_ok "$(printf "$L_MIG_PATHS_OK" "$(basename "$md_file")")"
    fi
    rm -f "$TMPFILE"
done

if [ $MD_CHANGED -eq 0 ]; then
    print_ok "$L_MIG_ALL_PATHS_OK"
fi

# ============================================================
# FAZA 4: AKTUALIZACJA WERSJI MACOS I ARCH W DOKUMENTACJI
# ============================================================
print_section "$L_PHASE_4_TITLE"

# Zbuduj nowy label macOS
# Codenames: 13 = Ventura, 14 = Sonoma, 15 = Sequoia, 26 = Tahoe
if [ "$MACOS_MAJOR" -ge 27 ]; then
    NEW_MACOS_LABEL="macOS ${MACOS_VERSION}"
elif [ "$MACOS_MAJOR" -eq 26 ]; then
    NEW_MACOS_LABEL="macOS ${MACOS_VERSION} Tahoe"
elif [ "$MACOS_MAJOR" -eq 15 ]; then
    NEW_MACOS_LABEL="macOS ${MACOS_VERSION} Sequoia"
elif [ "$MACOS_MAJOR" -eq 14 ]; then
    NEW_MACOS_LABEL="macOS ${MACOS_VERSION} Sonoma"
elif [ "$MACOS_MAJOR" -eq 13 ]; then
    NEW_MACOS_LABEL="macOS ${MACOS_VERSION} Ventura"
else
    NEW_MACOS_LABEL="macOS ${MACOS_VERSION}"
fi

TODAY="$(date +%Y-%m-%d)"

for md_file in "$SCRIPT_DIR/CLAUDE.md" "$SCRIPT_DIR/AGENTS.md" "$SCRIPT_DIR/GEMINI.md" "$SCRIPT_DIR/CODEX.md"; do
    [ -f "$md_file" ] || continue
    CHANGED=0
    TMPFILE="$(mktemp)"
    cp "$md_file" "$TMPFILE"

    # Zastąp pełny label macOS (wersja + codename TitleCase, np. "macOS 26.5 Tahoe", "macOS 15.0 Sequoia")
    # Regex: dopasowuje kolejne wyrazy kodowe TitleCase (Tahoe, Sequoia, Sonoma, Ventura) ale nie CVE, Apple itp.
    sed -i '' "s|macOS [0-9][0-9]*\.[0-9.x]*[0-9x]\( [A-Z][a-z][a-z]*\)*|${NEW_MACOS_LABEL}|g" "$TMPFILE"

    # Zastąp architekturę
    if [ "$ARCH" = "arm64" ]; then
        sed -i '' 's|Intel x86_64|Apple Silicon arm64|g' "$TMPFILE"
    else
        sed -i '' 's|Apple Silicon arm64|Intel x86_64|g' "$TMPFILE"
    fi

    if ! diff -q "$md_file" "$TMPFILE" > /dev/null 2>&1; then
        cp "$TMPFILE" "$md_file"
        print_fixed "$(printf "$L_MIG_MACOS_UPDATED" "$(basename "$md_file")" "$NEW_MACOS_LABEL" "$ARCH_LABEL")"
        add_fix "$(printf "$L_MIG_MACOS_FIX" "$(basename "$md_file")" "$NEW_MACOS_LABEL" "$ARCH_LABEL")"
        CHANGED=1
    else
        print_ok "$(printf "$L_MIG_MACOS_CURRENT" "$(basename "$md_file")")"
    fi
    rm -f "$TMPFILE"
done

# Aktualizacja daty w APPLICATIONS.md
if [ -f "$SCRIPT_DIR/APPLICATIONS.md" ]; then
    sed -i '' "s|\*\*Analysis date:\*\* [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]|**Analysis date:** ${TODAY}|g" "$SCRIPT_DIR/APPLICATIONS.md"
    sed -i '' "s|\*Updated: [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]|*Updated: ${TODAY}|g" "$SCRIPT_DIR/APPLICATIONS.md"
    print_fixed "$(printf "$L_MIG_APPS_DATE" "$TODAY")"
fi

# ============================================================
# PHASE 5: XCODE COMMAND LINE TOOLS
# ============================================================
print_section "$L_PHASE_5_TITLE"

if xcode-select -p &>/dev/null 2>&1; then
    XCLT_PATH="$(xcode-select -p)"
    print_ok "$(printf "$L_MSG_XCODE_OK" "$XCLT_PATH")"
else
    print_warn "$L_MSG_XCODE_MISSING"
    print_step "$L_MSG_XCODE_LAUNCH"
    echo ""
    echo -e "  ${YELLOW}$L_MSG_XCODE_DIALOG${NC}"
    echo -e "  ${YELLOW}$L_MSG_XCODE_WAIT${NC}"
    echo ""
    xcode-select --install 2>/dev/null || true
    echo ""
    if [ "$MAC_UPDATE_NONINTERACTIVE" != "1" ]; then
        read -r -p "  $L_MSG_XCODE_PRESS_ENTER"
    else
        print_warn "Non-interactive mode: install Xcode CLT from the dialog, then re-run setup.sh if needed."
    fi
    if xcode-select -p &>/dev/null 2>&1; then
        print_ok "$L_MSG_XCODE_OK2"
        add_fix "$L_MSG_XCODE_FIX"
    else
        print_error "$L_MSG_XCODE_FAIL"
        add_action "$L_MSG_XCODE_ACTION"
    fi
fi

# ============================================================
# PHASE 6: HOMEBREW
# ============================================================
print_section "$L_PHASE_6_TITLE"

BREW_OK=0

if command -v brew &>/dev/null; then
    BREW_OK=1
elif [ -f "$BREW_PREFIX/bin/brew" ]; then
    eval "$($BREW_PREFIX/bin/brew shellenv)" 2>/dev/null || true
    command -v brew &>/dev/null && BREW_OK=1
fi

if [ $BREW_OK -eq 1 ]; then
    BREW_VER="$(brew --version | head -1)"
    BREW_PATH="$(command -v brew)"
    print_ok "$(printf "$L_MSG_BREW_OK" "$BREW_VER")"
    print_ok "$(printf "$L_MSG_BREW_LOC" "$BREW_PATH")"

    if [ -f "$SHELL_PROFILE" ]; then
        if grep -q "brew shellenv" "$SHELL_PROFILE" 2>/dev/null; then
            print_ok "$(printf "$L_MSG_BREW_SHELLENV_OK" "$SHELL_PROFILE")"
        else
            print_warn "$(printf "$L_MSG_BREW_SHELLENV_MISSING" "$SHELL_PROFILE")"
            print_step "$(printf "$L_MSG_BREW_SHELLENV_ADD" "$SHELL_PROFILE")"
            echo "" >> "$SHELL_PROFILE"
            echo "# Homebrew (added by setup.sh)" >> "$SHELL_PROFILE"
            echo "eval \"\$($BREW_PREFIX/bin/brew shellenv)\"" >> "$SHELL_PROFILE"
            print_fixed "$(printf "$L_MSG_BREW_SHELLENV_FIXED" "$SHELL_PROFILE")"
            add_fix "$(printf "$L_MSG_BREW_SHELLENV_FIX" "$SHELL_PROFILE" "$SHELL_PROFILE")"
        fi
    fi
else
    print_warn "$L_MSG_BREW_NOT_INSTALLED"
    echo ""
    if [ "$MAC_UPDATE_NONINTERACTIVE" = "1" ]; then
        INSTALL_BREW="Y"
    else
        read -r -p "  $L_MSG_BREW_INSTALL_PROMPT " INSTALL_BREW
        INSTALL_BREW="${INSTALL_BREW:-Y}"
    fi
    if [[ ! "$INSTALL_BREW" =~ ^[Nn] ]]; then
        print_step "$L_MSG_BREW_INSTALLING"
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        if [ -f "$BREW_PREFIX/bin/brew" ]; then
            eval "$($BREW_PREFIX/bin/brew shellenv)"
            command -v brew &>/dev/null && BREW_OK=1
        fi
        if [ $BREW_OK -eq 1 ]; then
            print_ok "$L_MSG_BREW_OK2"
            add_fix "$L_MSG_BREW_FIX"
            if [ -f "$SHELL_PROFILE" ] && ! grep -q "brew shellenv" "$SHELL_PROFILE" 2>/dev/null; then
                echo "" >> "$SHELL_PROFILE"
                echo "# Homebrew" >> "$SHELL_PROFILE"
                echo "eval \"\$($BREW_PREFIX/bin/brew shellenv)\"" >> "$SHELL_PROFILE"
                add_fix "$(printf "$L_MSG_BREW_SHELLENV_FIX2" "$SHELL_PROFILE")"
            fi
        else
            print_error "$L_MSG_BREW_FAIL"
            add_action "$L_MSG_BREW_ACTION"
        fi
    else
        print_warn "$L_MSG_BREW_SKIPPED"
        add_action "$L_MSG_BREW_ACTION2"
    fi
fi

# ============================================================
# PHASE 7: mas — App Store CLI
# ============================================================
print_section "$L_PHASE_7_TITLE"

if command -v mas &>/dev/null; then
    MAS_VER="$(mas version 2>/dev/null || echo '?')"
    MAS_MAJOR="$(echo "$MAS_VER" | cut -d. -f1)"
    print_ok "$(printf "$L_MSG_MAS_OK" "$MAS_VER")"

    if [ "${MAS_MAJOR:-0}" -lt 4 ] 2>/dev/null; then
        print_warn "$(printf "$L_MSG_MAS_OLD" "$MAS_VER")"
        if command -v brew &>/dev/null; then
            print_step "$L_MSG_MAS_UPGRADING"
            HOMEBREW_NO_AUTO_UPDATE=1 brew upgrade mas 2>/dev/null || brew upgrade mas
            MAS_VER="$(mas version 2>/dev/null || echo '?')"
            print_ok "$(printf "$L_MSG_MAS_UPGRADED" "$MAS_VER")"
            add_fix "$(printf "$L_MSG_MAS_FIX" "$MAS_VER")"
        fi
    fi
else
    print_warn "$L_MSG_MAS_MISSING"
    if command -v brew &>/dev/null; then
        print_step "$L_MSG_MAS_INSTALLING"
        brew install mas
        if command -v mas &>/dev/null; then
            MAS_VER="$(mas version 2>/dev/null || echo '?')"
            print_ok "$(printf "$L_MSG_MAS_OK" "$MAS_VER")"
            add_fix "$(printf "$L_MSG_MAS_INSTALLED_FIX" "$MAS_VER")"
        else
            print_error "$L_MSG_MAS_FAIL"
            add_action "$L_MSG_MAS_ACTION"
        fi
    else
        print_warn "$L_MSG_MAS_NO_BREW"
        add_action "$L_MSG_MAS_ACTION2"
    fi
fi

# ============================================================
# PHASE 8: PYTHON 3
# ============================================================
print_section "$L_PHASE_8_TITLE"

PYTHON3_OK=0
PYTHON3_PATH=""

for py_candidate in python3 "$BREW_PREFIX/bin/python3" \
    "$BREW_PREFIX/opt/python@3.11/bin/python3" \
    "$BREW_PREFIX/opt/python@3.14/bin/python3" \
    /usr/bin/python3; do
    if command -v "$py_candidate" &>/dev/null 2>&1; then
        PYTHON3_PATH="$(command -v "$py_candidate" 2>/dev/null || echo "$py_candidate")"
        PY_VER="$($py_candidate --version 2>&1 | head -1)"
        print_ok "$(printf "$L_MSG_PY_OK" "$PY_VER" "$PYTHON3_PATH")"
        PYTHON3_OK=1
        break
    fi
done

if [ $PYTHON3_OK -eq 0 ]; then
    print_warn "$L_MSG_PY_MISSING"
    if command -v brew &>/dev/null; then
        print_step "$L_MSG_PY_INSTALLING"
        brew install python@3.11
        if command -v python3 &>/dev/null || command -v "$BREW_PREFIX/bin/python3" &>/dev/null; then
            PYTHON3_PATH="$(command -v python3 2>/dev/null || echo "$BREW_PREFIX/bin/python3")"
            print_ok "$L_MSG_PY_OK2"
            add_fix "$L_MSG_PY_FIX"
            PYTHON3_OK=1
        else
            print_error "$L_MSG_PY_FAIL"
            add_action "$L_MSG_PY_ACTION"
        fi
    else
        print_warn "$L_MSG_PY_NO_BREW"
        add_action "$L_MSG_PY_ACTION"
    fi
fi

# ============================================================
# PHASE 9: ESSENTIAL TOOLS (curl, git)
# ============================================================
print_section "$L_PHASE_9_TITLE"

if command -v curl &>/dev/null; then
    CURL_VER="$(curl --version | head -1 | awk '{print $2}')"
    print_ok "$(printf "$L_MSG_CURL_OK" "$CURL_VER")"
else
    print_error "$L_MSG_CURL_FAIL"
    add_action "$L_MSG_CURL_ACTION"
fi

if command -v git &>/dev/null; then
    GIT_VER="$(git --version | awk '{print $3}')"
    print_ok "$(printf "$L_MSG_GIT_OK" "$GIT_VER")"
else
    print_warn "$L_MSG_GIT_WARN"
    add_action "$L_MSG_GIT_ACTION"
fi

# ============================================================
# PHASE 10: OPTIONAL UPDATE TOOLS (msupdate, Docker, Keystone)
# ============================================================
print_section "$L_PHASE_10_TITLE"

# ── msupdate (Microsoft AutoUpdate) ──────────────────────────
MSUPDATE_PATHS="/Library/Application Support/Microsoft/MAU2.0/Microsoft AutoUpdate.app/Contents/MacOS/msupdate"
MSUPDATE_ALT="/Applications/Microsoft AutoUpdate.app/Contents/MacOS/msupdate"

if [ -f "$MSUPDATE_PATHS" ]; then
    print_ok "$(printf "$L_MSG_MSUPDATE_OK" "$MSUPDATE_PATHS")"
elif [ -f "$MSUPDATE_ALT" ]; then
    print_ok "$(printf "$L_MSG_MSUPDATE_OK" "$MSUPDATE_ALT")"
elif command -v msupdate &>/dev/null; then
    print_ok "$L_MSG_MSUPDATE_PATH"
else
    MS_APPS_FOUND=0
    for ms_app in "/Applications/Microsoft Word.app" "/Applications/Microsoft Excel.app" \
        "/Applications/Microsoft Outlook.app" "/Applications/Microsoft PowerPoint.app" \
        "/Applications/Microsoft Teams.app" "/Applications/Microsoft OneNote.app"; do
        [ -d "$ms_app" ] && MS_APPS_FOUND=$((MS_APPS_FOUND + 1))
    done

    if [ $MS_APPS_FOUND -gt 0 ]; then
        print_warn "$(printf "$L_MSG_MSUPDATE_WARN" "$MS_APPS_FOUND")"
        print_info "$L_MSG_MSUPDATE_HINT1"
        print_info "$(printf "$L_MSG_MSUPDATE_HINT2" "$MSUPDATE_PATHS")"
        add_warning "$L_MSG_MSUPDATE_WARN2"
    else
        print_skip "$L_MSG_MSUPDATE_SKIP"
    fi
fi

# ── Docker Desktop CLI ────────────────────────────────────────
if command -v docker &>/dev/null; then
    DOCKER_VER="$(docker --version 2>/dev/null | awk '{print $3}' | tr -d ',')"
    DOCKER_MAJOR="$(echo "$DOCKER_VER" | cut -d. -f1)"
    DOCKER_MINOR="$(echo "$DOCKER_VER" | cut -d. -f2)"
    print_ok "$(printf "$L_MSG_DOCKER_OK" "$DOCKER_VER")"

    DOCKER_OK_VER=0
    if [ "${DOCKER_MAJOR:-0}" -gt 4 ] 2>/dev/null; then
        DOCKER_OK_VER=1
    elif [ "${DOCKER_MAJOR:-0}" -eq 4 ] && [ "${DOCKER_MINOR:-0}" -ge 37 ] 2>/dev/null; then
        DOCKER_OK_VER=1
    fi

    if [ $DOCKER_OK_VER -eq 1 ]; then
        print_ok "$L_MSG_DOCKER_VER_OK"
    else
        print_warn "$(printf "$L_MSG_DOCKER_VER_WARN" "$DOCKER_VER")"
        add_warning "$(printf "$L_MSG_DOCKER_WARN2" "$DOCKER_VER")"
    fi
elif [ -d "/Applications/Docker.app" ]; then
    print_warn "$L_MSG_DOCKER_NOPATH"
    print_info "$L_MSG_DOCKER_LAUNCH"
    add_action "$L_MSG_DOCKER_ACTION"
else
    print_skip "$L_MSG_DOCKER_SKIP"
fi

# ── Google Keystone (Chrome/Google Drive updater) ─────────────
KEYSTONE_AGENT="/Library/Google/GoogleSoftwareUpdate/GoogleSoftwareUpdate.bundle/Contents/Resources/GoogleSoftwareUpdateAgent.app/Contents/MacOS/GoogleSoftwareUpdateAgent"
if [ -f "$KEYSTONE_AGENT" ]; then
    print_ok "$L_MSG_KEYSTONE_OK"
elif [ -d "/Applications/Google Chrome.app" ] || [ -d "/Applications/Google Drive.app" ]; then
    print_warn "$L_MSG_KEYSTONE_WARN"
    print_info "$(printf "$L_MSG_KEYSTONE_EXPECT" "$KEYSTONE_AGENT")"
    print_info "$L_MSG_KEYSTONE_HINT"
    add_warning "$L_MSG_KEYSTONE_WARN2"
else
    print_skip "$L_MSG_KEYSTONE_SKIP"
fi

# ============================================================
# PHASE 11: SCRIPT PERMISSIONS
# ============================================================
print_section "$L_PHASE_11_TITLE"

CHMOD_COUNT=0
for sh_file in "$SCRIPT_DIR"/*.sh "$SCRIPT_DIR/dev-sync"/*.sh; do
    [ -f "$sh_file" ] || continue
    if [ ! -x "$sh_file" ]; then
        chmod +x "$sh_file"
        print_fixed "$(printf "$L_MSG_CHMOD_FIXED" "$(basename "$sh_file")")"
        CHMOD_COUNT=$((CHMOD_COUNT + 1))
    else
        print_ok "$(printf "$L_MSG_CHMOD_OK" "$(basename "$sh_file")")"
    fi
done

if [ $CHMOD_COUNT -gt 0 ]; then
    add_fix "$(printf "$L_MSG_CHMOD_FIX" "$CHMOD_COUNT")"
else
    print_ok "$L_MSG_CHMOD_ALL_OK"
fi

# ============================================================
# PHASE 12: APP STORE LOGIN CHECK
# ============================================================
print_section "$L_PHASE_12_TITLE"

if command -v mas &>/dev/null; then
    APPLE_ID="$(mas account 2>/dev/null || echo '')"
    if [ -n "$APPLE_ID" ]; then
        print_ok "$(printf "$L_MSG_APPSTORE_OK" "$APPLE_ID")"
    else
        print_info "$L_MSG_APPSTORE_MAS_LIMIT"
    fi

    if mas list &>/dev/null 2>&1; then
        print_ok "$L_MSG_APPSTORE_ACCESS"
        MAS_APP_COUNT="$(mas list 2>/dev/null | wc -l | tr -d ' ')"
        print_info "$(printf "$L_MSG_APPSTORE_COUNT" "$MAS_APP_COUNT")"
    else
        print_error "$L_MSG_APPSTORE_FAIL"
        print_info "$L_MSG_APPSTORE_SIGNIN"
        open -a "App Store" 2>/dev/null || true
        add_action "$L_MSG_APPSTORE_ACTION"
    fi
else
    print_warn "$L_MSG_APPSTORE_NO_MAS"
fi

# ============================================================
# PHASE 13: ACCESSIBILITY PERMISSION (AppleScript / Track 2)
# ============================================================
print_section "$L_PHASE_13_TITLE"

print_info "$(printf "$L_MSG_AX_TEST" "$TERM_APP_NAME")"
AX_TEST="$(osascript -e 'tell application "System Events" to return name of first process whose frontmost is true' 2>&1 || echo 'FAILED')"

if echo "$AX_TEST" | grep -qi "not allowed\|assistive\|accessibility\|access\|FAILED"; then
    print_warn "$(printf "$L_MSG_AX_DENIED" "$TERM_APP_NAME")"
    echo ""
    echo -e "  ${YELLOW}${BOLD}$L_MSG_AX_TRACK2${NC}"
    echo ""
    echo -e "  ${BOLD}$L_MSG_AX_HOW${NC}"
    echo "    1. $L_AX_FIX_STEP_1"
    echo "    2. $L_AX_FIX_STEP_2"
    echo "       ${TERM_APP_NAME}"
    echo "    3. $L_AX_FIX_STEP_3"
    echo ""

    read -r -p "  $L_MSG_AX_OPEN_PREFS " OPEN_PREFS
    OPEN_PREFS="${OPEN_PREFS:-Y}"
    if [[ ! "$OPEN_PREFS" =~ ^[Nn] ]]; then
        open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
        print_info "$L_MSG_AX_OPENED"
    fi

    add_action "$(printf "$L_MSG_AX_ACTION" "$TERM_APP_NAME")"
else
    print_ok "$(printf "$L_MSG_AX_OK" "$TERM_APP_NAME")"
fi

# ============================================================
# FAZA 14: SKANOWANIE APLIKACJI → AKTUALIZACJA PROGRAMY.MD
# ============================================================
print_section "$L_PHASE_14_TITLE"

if [ ! -f "$SCRIPT_DIR/APPLICATIONS.md" ]; then
    print_info "$L_MIG_APPS_MISSING"
    sed \
        -e "s/USER/$NEW_USER/g" \
        -e "s/YYYY-MM-DD/$TODAY/g" \
        -e "s/BUILD/$MACOS_BUILD/g" \
        -e "s|~/Dev_Env/macOS_updates|$SCRIPT_DIR|g" \
        -e "s/Apple Silicon (arm64)/$ARCH_LABEL/" \
        -e "s/macOS VERSION/$NEW_MACOS_LABEL/g" \
        "$SCRIPT_DIR/templates/APPLICATIONS.md.template" > "$SCRIPT_DIR/APPLICATIONS.md"
    print_ok "$L_MIG_APPS_TEMPLATE_OK"
    add_fix "$L_MIG_APPS_TEMPLATE_FIX"
fi

if [ $PYTHON3_OK -eq 1 ]; then
    print_step "$L_MIG_SCAN_START"
    SCAN_SESSION_DIR="$(mktemp -d "${TMPDIR:-/tmp}/mac_update_scan.XXXXXX")"
    chmod 700 "$SCAN_SESSION_DIR" 2>/dev/null || true

    # Zapisz listę brew formulae (jeśli brew dostępny)
    if command -v brew &>/dev/null; then
        brew list --formula --versions 2>/dev/null > "$SCAN_SESSION_DIR/brew_formulae.txt" || true
        brew list --cask --versions 2>/dev/null > "$SCAN_SESSION_DIR/brew_casks.txt" || true
    fi

    # Zapisz listę mas apps (jeśli mas dostępny)
    if command -v mas &>/dev/null; then
        mas list 2>/dev/null > "$SCAN_SESSION_DIR/mas_list.txt" || true
    fi

    # Uruchom Python inline do aktualizacji APPLICATIONS.md
    env MAC_LANG="$MAC_LANG" python3 - "$SCRIPT_DIR" "$SCAN_SESSION_DIR" "$TODAY" "$MAC_LANG" << 'PYEOF'
import os, re, sys, subprocess
from datetime import datetime

script_dir  = sys.argv[1]
session_dir = sys.argv[2]
today       = sys.argv[3]
lang        = sys.argv[4] if len(sys.argv) > 4 else 'en'

SCAN_MSG = {
    'en': {
        'no_cfg': '  ⚠️  Missing config/internet_apps.txt — skipping internet app scan',
        'scan': '  Scanning /Applications...',
        'found': '  Found: %s internet apps',
        'missing': '  Missing: %s apps',
        'check_new': '  Checking for new apps...',
        'update': '  Updating versions in APPLICATIONS.md...',
        'added': '  Added %s new apps to APPLICATIONS.md',
        'done': '  ✅ APPLICATIONS.md updated:',
        'ver': '     Versions updated:  %s',
        'brew': '     Brew formulae/casks: %s',
        'internet': '     Internet apps:       %s',
        'not_inst': '     Missing apps:        %s',
        'new': '     New to categorize: %s',
    },
    'pl': {
        'no_cfg': '  ⚠️  Brak config/internet_apps.txt — pomijam skan aplikacji internetowych',
        'scan': '  Skanowanie /Applications...',
        'found': '  Znaleziono: %s aplikacji internetowych',
        'missing': '  Brak:       %s aplikacji',
        'check_new': '  Sprawdzanie nowych aplikacji...',
        'update': '  Aktualizuję wersje w APPLICATIONS.md...',
        'added': '  Dodano %s nowych aplikacji do APPLICATIONS.md',
        'done': '  ✅ APPLICATIONS.md zaktualizowany:',
        'ver': '     Zaktualizowano wersji:  %s',
        'brew': '     Brew formulae/casks:    %s',
        'internet': '     Aplikacje internetowe:  %s',
        'not_inst': '     Brakujące aplikacje:    %s',
        'new': '     Nowe do skategoryz.:  %s',
    },
}

def S(key, *args):
    d = SCAN_MSG.get(lang, SCAN_MSG['en'])
    msg = d.get(key, SCAN_MSG['en'].get(key, key))
    return msg % args if args else msg


programy_path = os.path.join(script_dir, 'APPLICATIONS.md')

def read_file(path):
    try:
        with open(path, 'r') as f:
            return f.read()
    except:
        return ''

APP_ALIASES = {
    'OpenCode': ['OpenCode', 'opencode', 'Opencode', 'opencode Desktop'],
    'Ledger Live': ['Ledger Live', 'Ledger Wallet'],
    'Docker': ['Docker', 'Docker Desktop'],
    'Docker Desktop': ['Docker', 'Docker Desktop'],
    'Codex': ['Codex', 'Codex Desktop (OpenAI)'],
    'Comet': ['Comet', 'Comet (Perplexity Browser)'],
    'Perplexity': ['Perplexity', 'Perplexity Desktop'],
    'Keynote Creator Studio': ['Keynote Creator Studio', 'Keynote'],
    'Numbers Creator Studio': ['Numbers Creator Studio', 'Numbers'],
    'Pages Creator Studio': ['Pages Creator Studio', 'Pages'],
}

def row_exists(table_content, name):
    for candidate in APP_ALIASES.get(name, [name]):
        pattern = r'^\| ' + re.escape(candidate) + r' \|'
        if re.search(pattern, table_content, re.MULTILINE) is not None:
            return True
    return False

def app_version(app_name):
    """Read CFBundleShortVersionString from app bundle."""
    candidates = APP_ALIASES.get(app_name, [app_name])
    app_root = None
    for candidate in candidates:
        if os.path.exists(f'/Applications/{candidate}.app'):
            app_root = f'/Applications/{candidate}.app'
            break
    if app_root is None:
        return None
    try:
        r = subprocess.run(['defaults', 'read',
                            f'{app_root}/Contents/Info',
                            'CFBundleShortVersionString'],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
        r2 = subprocess.run(['defaults', 'read',
                             f'{app_root}/Contents/Info',
                             'CFBundleVersion'],
                            capture_output=True, text=True, timeout=5)
        if r2.returncode == 0 and r2.stdout.strip():
            return r2.stdout.strip()
    except:
        pass
    return '?'

# ── Load brew versions ────────────────────────────────────────
brew_versions = {}
brew_f = os.path.join(session_dir, 'brew_formulae.txt')
brew_c = os.path.join(session_dir, 'brew_casks.txt')
for fp in [brew_f, brew_c]:
    for line in read_file(fp).splitlines():
        parts = line.strip().split()
        if len(parts) >= 2:
            brew_versions[parts[0]] = parts[1]

# ── Load mas apps ────────────────────────────────────────────
mas_installed_ids = set()
mas_installed_names = set()
for line in read_file(os.path.join(session_dir, 'mas_list.txt')).splitlines():
    match = re.match(r'^(\d+)\s+(.+?)\s+\(([^()]+)\)$', line.strip())
    if match:
        mas_installed_ids.add(match.group(1))
        mas_installed_names.add(match.group(2).lower())

# ── Internet apps to scan (canonical list: config/internet_apps.txt) ──
INTERNET_APPS = []
_internet_cfg = os.path.join(script_dir, 'config', 'internet_apps.txt')
if os.path.isfile(_internet_cfg):
    with open(_internet_cfg, 'r', encoding='utf-8') as _icf:
        for _line in _icf:
            _line = _line.split('#', 1)[0].strip()
            if _line:
                INTERNET_APPS.append(_line)
else:
    print(S('no_cfg'))

internet_versions = {}
apps_not_installed = []
print(S('scan'))
for app in INTERNET_APPS:
    ver = app_version(app)
    if ver is None:
        apps_not_installed.append(app)
    elif ver != '?':
        internet_versions[app] = ver

print(S('found', len(internet_versions)))
print(S('missing', len(apps_not_installed)))

# ── Merge all versions for APPLICATIONS.md update ─────────────────
all_versions = {}
all_versions.update(brew_versions)
all_versions.update(internet_versions)

# ── Scan /Applications for NEW apps not in APPLICATIONS.md ────────
print(S('check_new'))
content = read_file(programy_path)
try:
    installed_all = sorted([
        item[:-4] for item in os.listdir('/Applications')
        if item.endswith('.app')
    ])
except:
    installed_all = []

new_apps_unknown = []
# POPRAWKA: szukaj tylko w GRUPACH 1-3, nie w sekcji Homebrew (GRUPA 4)
# Zapobiega fałszywym dopasowaniom CLI brew z aplikacjami Desktop (np. brew 'opencode' vs opencode.app)
grupo_1_3_match = re.search(r'^(.*?)(?=^## GRUPA 4)', content, re.DOTALL | re.MULTILINE)
grupo_1_3_content = grupo_1_3_match.group(1) if grupo_1_3_match else content

# Pomijaj pomocnicze komponenty aplikacji
SYSTEM_SKIP_FRAGMENTS = [
    'Installer', 'Uninstaller', 'Helper', 'Agent', 'Updater',
    'Shim', 'Launcher', 'Framework', 'Plugin', 'Extension',
    'Service', 'Daemon', 'XPC', 'Feedback',
]
SKIP_DISCOVERY_APPS = set(['WiFiman', 'Picsart', 'Utilities'])
for app in installed_all:
    if any(frag.lower() in app.lower() for frag in SYSTEM_SKIP_FRAGMENTS):
        continue
    if app in SKIP_DISCOVERY_APPS:
        continue
    if not row_exists(grupo_1_3_content, app):
        new_apps_unknown.append(app)

# ── Update version numbers in APPLICATIONS.md ─────────────────────
print(S('update'))
lines = content.split('\n')
new_lines = []
updated_count = 0

for line in lines:
    m = re.match(r'^(\| )(\S.*?\S|\S)( \| )([^\|]+?)( \| )(.+?)( \|)\s*$', line)
    if m:
        name = m.group(2).strip()
        if name in all_versions:
            old_ver = m.group(4).strip()
            new_ver = all_versions[name]
            if old_ver != new_ver and new_ver not in ('?', ''):
                line = f"{m.group(1)}{name}{m.group(3)}{new_ver}{m.group(5)}{m.group(6)}{m.group(7)}"
                updated_count += 1
    new_lines.append(line)

content = '\n'.join(new_lines)

# ── Add new unknown apps section ──────────────────────────────
if new_apps_unknown:
    NEW_HDR = {
        'en': ('### 🆕 Newly detected apps — migration (categorize)\n\n', '| Name | Publisher | Update URL |\n', '|-------|-----------|-------------|\n'),
        'pl': ('### 🆕 Nowo wykryte aplikacje — migracja (do skategoryzowania)\n\n', '| Nazwa | Producent | Strona aktualizacji |\n', '|-------|-----------|---------------------|\n'),
        'de': ('### 🆕 Neu erkannte Apps — Migration (kategorisieren)\n\n', '| Name | Hersteller | Update-URL |\n', '|-------|------------|------------|\n'),
        'fr': ('### 🆕 Apps nouvellement détectées — migration\n\n', '| Nom | Éditeur | URL de mise à jour |\n', '|-----|---------|-------------------|\n'),
        'es': ('### 🆕 Apps detectadas — migración (categorizar)\n\n', '| Nombre | Editor | URL de actualización |\n', '|--------|--------|---------------------|\n'),
        'it': ('### 🆕 App rilevate — migrazione (categorizzare)\n\n', '| Nome | Editore | URL aggiornamento |\n', '|------|---------|-------------------|\n'),
        'pt': ('### 🆕 Apps detetadas — migração (categorizar)\n\n', '| Nome | Editor | URL de atualização |\n', '|------|--------|---------------------|\n'),
    }
    hdr = NEW_HDR.get(lang, NEW_HDR['en'])
    new_section = '\n' + hdr[0] + hdr[1] + hdr[2]
    for app in new_apps_unknown:
        new_section += f'| {app} | 🆕 NOWY | — |\n'
    new_section += '\n'
    marker = {'en':'### Cloud storage','pl':'### ☁️ Przechowywanie w chmurze','de':'### Cloud-Speicher','fr':'### Stockage cloud','es':'### Almacenamiento en la nube','it':'### Cloud storage','pt':'### Armazenamento na nuvem'}.get(lang, '### Cloud storage')
    if marker in content:
        content = content.replace(marker, new_section + marker)
        print(S('added', len(new_apps_unknown)))
    else:
        # Dodaj na końcu pliku
        content = content.rstrip() + '\n\n' + new_section

# ── Update date ───────────────────────────────────────────────
content = re.sub(
    r'(\*\*Analysis date:\*\* )\d{4}-\d{2}-\d{2}',
    r'\g<1>' + today, content
)
content = re.sub(
    r'(\*Updated: )\d{4}-\d{2}-\d{2}',
    r'\g<1>' + today, content
)

# ── Write back ────────────────────────────────────────────────
with open(programy_path, 'w') as f:
    f.write(content)

print(S('done'))
print(S('ver', updated_count))
print(S('brew', len(brew_versions)))
print(S('internet', len(internet_versions)))
print(S('not_inst', len(apps_not_installed)))
if new_apps_unknown:
    print(S('new', len(new_apps_unknown)))
PYEOF

    PYTHON_EXIT=$?

    if [ $PYTHON_EXIT -eq 0 ]; then
        print_ok "$L_MIG_SCAN_OK"
        add_fix "$L_MIG_SCAN_FIX"
    else
        print_warn "$L_MIG_SCAN_WARN"
        add_warning "$L_MIG_SCAN_WARN2"
    fi
    case "$SCAN_SESSION_DIR" in
        "${TMPDIR:-/tmp}"/mac_update_scan.*|/tmp/mac_update_scan.*)
            rm -rf "$SCAN_SESSION_DIR" 2>/dev/null || true
            ;;
    esac
else
    print_warn "$L_MIG_SCAN_NO_PY"
    add_action "$L_MIG_SCAN_ACTION"
fi

# ============================================================
# FAZA 15/16: NAPRAWA KONFIGURACJI MCP (Gemini/Windsurf)
# ============================================================
print_section "$L_MIGRATION_PHASE_15_MCP"

if [ -f "$SCRIPT_DIR/fix_mcp_all.sh" ]; then
    print_step "$L_MIG_MCP_START"
    bash "$SCRIPT_DIR/fix_mcp_all.sh"
    if [ $? -eq 0 ]; then
        add_fix "$L_MIG_MCP_FIX"
    else
        add_warning "$L_MIG_MCP_WARN"
    fi
else
    print_warn "$L_MIG_MCP_MISSING"
fi

# ============================================================
# FAZA 16: WPIS MIGRACJI W AKTUALIZACJE.MD
# ============================================================
print_section "$L_MIGRATION_PHASE_16_REGISTER"

if [ $PYTHON3_OK -eq 1 ]; then
    NOW="$(date '+%Y-%m-%d %H:%M')"

    env MAC_LANG="$MAC_LANG" python3 - "$SCRIPT_DIR" "$NOW" "$TODAY" \
        "$NEW_USER" "$NEW_HOME" "$MACOS_VERSION" "$ARCH_LABEL" \
        "$HOSTNAME_NEW" "$SCRIPT_DIR" << 'PYEOF'
import sys, re, os

script_dir   = sys.argv[1]
now          = sys.argv[2]
today        = sys.argv[3]
new_user     = sys.argv[4]
new_home     = sys.argv[5]
macos_ver    = sys.argv[6]
arch_label   = sys.argv[7]
hostname     = sys.argv[8]
project_dir  = sys.argv[9]
lang         = os.environ.get("MAC_LANG", "en")

MIG = {
    'en': {
        'title': '### 🚀 Migration to new MacBook: {now}',
        'param': 'Parameter', 'value': 'Value',
        'host': '🖥️ New computer', 'user': '👤 User', 'macos': '🍎 macOS',
        'arch': '💻 Architecture', 'path': '📂 Project path', 'date': '📅 Migration date',
        'footer': '*Migration performed by migration_setup.sh — paths, versions, and dependencies updated.*',
        'history': '## 📅 Update session history',
        'fallback_title': '# UPDATES',
    },
    'pl': {
        'title': '### 🚀 Migracja na nowy MacBook: {now}',
        'param': 'Parametr', 'value': 'Wartość',
        'host': '🖥️ Nowy komputer', 'user': '👤 Użytkownik', 'macos': '🍎 macOS',
        'arch': '💻 Architektura', 'path': '📂 Ścieżka projektu', 'date': '📅 Data migracji',
        'footer': '*Migracja wykonana przez migration_setup.sh — ścieżki, wersje i zależności zaktualizowane.*',
        'history': '## 📅 Historia sesji aktualizacji',
        'fallback_title': '# AKTUALIZACJE',
    },
    'de': {
        'title': '### 🚀 Migration auf neuen MacBook: {now}',
        'param': 'Parameter', 'value': 'Wert',
        'host': '🖥️ Neuer Computer', 'user': '👤 Benutzer', 'macos': '🍎 macOS',
        'arch': '💻 Architektur', 'path': '📂 Projektpfad', 'date': '📅 Migrationsdatum',
        'footer': '*Migration durch migration_setup.sh — Pfade, Versionen und Abhängigkeiten aktualisiert.*',
        'history': '## 📅 Update-Sitzungsverlauf',
        'fallback_title': '# UPDATES',
    },
    'fr': {
        'title': '### 🚀 Migration vers un nouveau MacBook : {now}',
        'param': 'Paramètre', 'value': 'Valeur',
        'host': '🖥️ Nouvel ordinateur', 'user': '👤 Utilisateur', 'macos': '🍎 macOS',
        'arch': '💻 Architecture', 'path': '📂 Chemin du projet', 'date': '📅 Date de migration',
        'footer': '*Migration effectuée par migration_setup.sh — chemins, versions et dépendances mis à jour.*',
        'history': '## 📅 Historique des sessions de mise à jour',
        'fallback_title': '# UPDATES',
    },
    'es': {
        'title': '### 🚀 Migración a nuevo MacBook: {now}',
        'param': 'Parámetro', 'value': 'Valor',
        'host': '🖥️ Nuevo ordenador', 'user': '👤 Usuario', 'macos': '🍎 macOS',
        'arch': '💻 Arquitectura', 'path': '📂 Ruta del proyecto', 'date': '📅 Fecha de migración',
        'footer': '*Migración realizada por migration_setup.sh — rutas, versiones y dependencias actualizadas.*',
        'history': '## 📅 Historial de sesiones de actualización',
        'fallback_title': '# UPDATES',
    },
    'it': {
        'title': '### 🚀 Migrazione su nuovo MacBook: {now}',
        'param': 'Parametro', 'value': 'Valore',
        'host': '🖥️ Nuovo computer', 'user': '👤 Utente', 'macos': '🍎 macOS',
        'arch': '💻 Architettura', 'path': '📂 Percorso progetto', 'date': '📅 Data migrazione',
        'footer': '*Migrazione eseguita da migration_setup.sh — percorsi, versioni e dipendenze aggiornati.*',
        'history': '## 📅 Cronologia sessioni di aggiornamento',
        'fallback_title': '# UPDATES',
    },
    'pt': {
        'title': '### 🚀 Migração para novo MacBook: {now}',
        'param': 'Parâmetro', 'value': 'Valor',
        'host': '🖥️ Novo computador', 'user': '👤 Utilizador', 'macos': '🍎 macOS',
        'arch': '💻 Arquitetura', 'path': '📂 Caminho do projeto', 'date': '📅 Data da migração',
        'footer': '*Migração executada por migration_setup.sh — caminhos, versões e dependências atualizados.*',
        'history': '## 📅 Histórico de sessões de atualização',
        'fallback_title': '# UPDATES',
    },
}
t = MIG.get(lang, MIG['en'])

ak_path = os.path.join(script_dir, 'UPDATES.md')

try:
    with open(ak_path, 'r') as f:
        ak_content = f.read()
except:
    ak_content = t['fallback_title'] + '\n\n' + t['history'] + '\n'

migration_entry = f"""
{t['title'].format(now=now)}

| {t['param']} | {t['value']} |
|----------|---------|
| {t['host']} | {hostname} |
| {t['user']} | {new_user} |
| {t['macos']} | {macos_ver} |
| {t['arch']} | {arch_label} |
| {t['path']} | {project_dir} |
| {t['date']} | {today} |

{t['footer']}

"""

HISTORY_MARKER = t['history']
if HISTORY_MARKER in ak_content:
    ak_content = ak_content.replace(
        HISTORY_MARKER + '\n',
        HISTORY_MARKER + '\n' + migration_entry
    )
else:
    ak_content = ak_content.rstrip() + f'\n\n---\n\n{HISTORY_MARKER}\n{migration_entry}'

ak_content = re.sub(r'(\*\*Data:\*\* )\d{4}-\d{2}-\d{2}', r'\g<1>' + today, ak_content)
ak_content = re.sub(r'(\*Zaktualizowano: )\d{4}-\d{2}-\d{2}', r'\g<1>' + today, ak_content)

with open(ak_path, 'w') as f:
    f.write(ak_content)

print("  ✅ " + {"en":"Migration registered in UPDATES.md","pl":"Migracja zarejestrowana w UPDATES.md","de":"Migration in UPDATES.md registriert","fr":"Migration enregistrée dans UPDATES.md","es":"Migración registrada en UPDATES.md","it":"Migrazione registrata in UPDATES.md","pt":"Migração registada em UPDATES.md"}.get(lang, "Migration registered in UPDATES.md"))
PYEOF

else
    print_skip "$L_MIG_UPDATES_SKIP"
fi

# ============================================================
# PODSUMOWANIE KOŃCOWE
# ============================================================
echo ""
echo -e "${BLUE}${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}${BOLD}║                $L_MIGRATION_SUMMARY                     ║${NC}"
echo -e "${BLUE}${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}$(printf "$L_MIG_SYSTEM_LINE" "$MACOS_VERSION" "$ARCH_LABEL")${NC}"
echo -e "  ${BOLD}$L_INFO_USER $NEW_USER | $L_INFO_PROJECT_DIR $SCRIPT_DIR${NC}"
echo ""

# Wyświetl naprawione elementy
if [ -n "$FIXES_APPLIED" ]; then
    echo -e "  ${GREEN}${BOLD}✅ $L_MIG_SUMMARY_FIXED${NC}"
    echo -e "$FIXES_APPLIED" | while IFS= read -r line; do
        [ -n "$line" ] && echo -e "     ${GREEN}• $line${NC}"
    done
    echo ""
fi

# Wyświetl ostrzeżenia
if [ -n "$WARNINGS" ]; then
    echo -e "  ${YELLOW}${BOLD}⚠️  $L_MIG_SUMMARY_WARN${NC}"
    echo -e "$WARNINGS" | while IFS= read -r line; do
        [ -n "$line" ] && echo -e "     ${YELLOW}• $line${NC}"
    done
    echo ""
fi

# Wyświetl wymagane akcje manualne
if [ -n "$ACTIONS_REQUIRED" ]; then
    echo -e "  ${RED}${BOLD}⬛ $L_MIG_SUMMARY_ACTIONS${NC}"
    echo -e "$ACTIONS_REQUIRED" | while IFS= read -r line; do
        [ -n "$line" ] && echo -e "     ${RED}• $line${NC}"
    done
    echo ""
fi

# Checklist gotowości
echo -e "  ${BOLD}🏁 $L_MIG_CHECKLIST${NC}"
echo ""

# Homebrew
if command -v brew &>/dev/null; then
    echo -e "  ${GREEN}✅ $(printf "$L_MIG_CHECK_OK" "Homebrew")${NC}"
else
    echo -e "  ${RED}❌ $L_MIG_CHECK_BREW_FAIL${NC}"
fi

# mas
if command -v mas &>/dev/null; then
    echo -e "  ${GREEN}✅ $(printf "$L_MIG_CHECK_OK" "mas (App Store CLI)")${NC}"
else
    echo -e "  ${YELLOW}⚠️  $L_MIG_CHECK_MAS_WARN${NC}"
fi

# Python 3
if [ $PYTHON3_OK -eq 1 ]; then
    echo -e "  ${GREEN}✅ $(printf "$L_MIG_CHECK_OK" "Python 3")${NC}"
else
    echo -e "  ${YELLOW}⚠️  $L_MIG_CHECK_PY_WARN${NC}"
fi

# curl
if command -v curl &>/dev/null; then
    echo -e "  ${GREEN}✅ $(printf "$L_MIG_CHECK_OK" "curl")${NC}"
else
    echo -e "  ${RED}❌ $L_MIG_CHECK_CURL_FAIL${NC}"
fi

# Skrypty .sh
SCRIPTS_OK=1
for sh in update_all.sh update_system.sh update_appstore.sh update_internet_apps.sh update_brew.sh; do
    [ -x "$SCRIPT_DIR/$sh" ] || SCRIPTS_OK=0
done
if [ $SCRIPTS_OK -eq 1 ]; then
    echo -e "  ${GREEN}✅ $L_MIG_CHECK_SCRIPTS_OK${NC}"
else
    echo -e "  ${YELLOW}⚠️  $(printf "$L_MIG_CHECK_SCRIPTS_WARN" "$SCRIPT_DIR")${NC}"
fi

# App Store
if command -v mas &>/dev/null && mas list &>/dev/null 2>&1; then
    echo -e "  ${GREEN}✅ $L_MIG_CHECK_APPSTORE_OK${NC}"
else
    echo -e "  ${YELLOW}⚠️  $L_MIG_CHECK_APPSTORE_WARN${NC}"
fi

# Accessibility
if ! echo "$AX_TEST" | grep -qi "not allowed\|assistive\|accessibility\|FAILED" 2>/dev/null; then
    echo -e "  ${GREEN}✅ $(printf "$L_MIG_CHECK_AX_OK" "$TERM_APP_NAME")${NC}"
else
    echo -e "  ${YELLOW}⚠️  $L_MIG_CHECK_AX_WARN${NC}"
fi

echo ""
echo -e "  ${BOLD}📂 $L_MIG_PRIVATE_STATUS${NC}"
if [ -f "$SCRIPT_DIR/CLAUDE.md" ]; then
    echo -e "     ${GREEN}✅ $(printf "$L_MIG_DOCS_OK" "$MACOS_VERSION")${NC}"
else
    echo -e "     ${YELLOW}⚠️  $L_MIG_DOCS_MISSING${NC}"
fi
if [ -f "$SCRIPT_DIR/APPLICATIONS.md" ]; then
    echo -e "     ${GREEN}✅ $L_MIG_APPS_OK${NC}"
else
    echo -e "     ${YELLOW}⚠️  $L_MIG_APPS_MISSING2${NC}"
fi
if [ -f "$SCRIPT_DIR/UPDATES.md" ]; then
    echo -e "     ${GREEN}✅ $L_MIG_UPDATES_OK${NC}"
else
    echo -e "     ${YELLOW}⚠️  $L_MIG_UPDATES_MISSING${NC}"
fi
echo ""
echo -e "  ${BOLD}$L_NEXT_STEPS${NC}"
if [ ! -f "$SCRIPT_DIR/APPLICATIONS.md" ]; then
    echo -e "     ${CYAN}$L_MIG_NEXT_RESTORE${NC}"
    echo -e "        ${GREEN}cd $SCRIPT_DIR && bash dev-sync-import.sh${NC}"
    echo -e "     ${CYAN}$L_MIG_NEXT_RERUN${NC}"
    echo -e "        ${GREEN}cd $SCRIPT_DIR && bash migration_setup.sh${NC}"
    echo -e "     ${CYAN}$L_MIG_NEXT_UPDATE${NC}"
    echo -e "        ${GREEN}cd $SCRIPT_DIR && bash update_all.sh${NC}"
else
    echo -e "     ${GREEN}cd $SCRIPT_DIR && bash update_all.sh${NC}"
fi
echo ""
echo -e "${BLUE}${BOLD}══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  ✅  $L_MIG_COMPLETE_BANNER  ${NC}"
echo -e "${BLUE}${BOLD}══════════════════════════════════════════════════════════════${NC}"
echo ""

if [ ! -f "$SCRIPT_DIR/APPLICATIONS.md" ] || [ ! -f "$SCRIPT_DIR/UPDATES.md" ]; then
    MIGRATION_EXIT=1
fi
exit "$MIGRATION_EXIT"
