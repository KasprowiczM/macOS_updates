#!/usr/bin/env bash
# ============================================================
# setup.sh — macOS Updates: Quick Setup for New Users
# ============================================================
# Data: 2026-04-14
# Kompatybilność: bash 3.2+ (macOS domyślny shell, Apple Silicon + Intel)
#
# URUCHOM JAKO PIERWSZY po sklonowaniu repozytorium:
#
#   git clone https://github.com/<user>/macOS_updates.git ~/Dev_Env/macOS_updates
#   cd ~/Dev_Env/macOS_updates
#   bash setup.sh
#
# Co robi ten skrypt:
#   0a. Wybór języka (opcjonalnie)
#   1.  Wykrywa dane systemu (użytkownik, macOS, architektura)
#   2.  Wykrywa stary username z plików .md i naprawia ścieżki
#   3.  Aktualizuje ścieżki w plikach dokumentacji (.md)
#   4.  Aktualizuje wersję macOS i arch w CLAUDE.md, AGENTS.md, GEMINI.md, CODEX.md
#   5.  Sprawdza i instaluje Xcode Command Line Tools
#   6.  Sprawdza i instaluje Homebrew (z właściwą ścieżką arm64/Intel)
#   7.  Sprawdza i instaluje mas (App Store CLI)
#   8.  Sprawdza dostępność Python 3
#   9.  Sprawdza inne narzędzia: curl, git
#   10. Weryfikuje opcjonalne narzędzia: msupdate, docker, keystone
#   11. Nadaje chmod +x wszystkim skryptom *.sh
#   12. Sprawdza zalogowanie do App Store (mas)
#   13. Sprawdza uprawnienie Accessibility dla terminala (AppleScript)
#
# Ten skrypt NIE wymaga żadnych prywatnych plików z cloud storage.
# Nie aktualizuje APPLICATIONS.md ani UPDATES.md.
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
    local title="${1:-macOS Updates — SETUP}"
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
print_action() { echo -e "  ${YELLOW}${BOLD}⬛ REQUIRED ACTION: $1${NC}"; }
print_fixed()  { echo -e "  ${GREEN}🔧  FIXED: $1${NC}"; }
print_skip()   { echo -e "  ${CYAN}⏭️   SKIPPED: $1${NC}"; }

# ── Śledzenie wyników do podsumowania ────────────────────────
ACTIONS_REQUIRED=""
FIXES_APPLIED=""
WARNINGS=""

add_action()  { ACTIONS_REQUIRED="${ACTIONS_REQUIRED}${1}\n"; }
add_fix()     { FIXES_APPLIED="${FIXES_APPLIED}${1}\n"; }
add_warning() { WARNINGS="${WARNINGS}${1}\n"; }

# Katalog skryptu
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAC_UPDATE_NONINTERACTIVE="${MAC_UPDATE_NONINTERACTIVE:-0}"

. "$SCRIPT_DIR/lib/platform.sh"
mac_update_require_apple_silicon || exit 1

# ── i18n: load language strings (English default until picker runs) ──
. "$SCRIPT_DIR/i18n/loader.sh"

# ============================================================
# PHASE 0a: LANGUAGE SELECTION (before localized banner)
# ============================================================
print_section "$L_SETUP_PHASE_0A"

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
    if [ "$MAC_UPDATE_NONINTERACTIVE" = "1" ]; then
        CHANGE_LANG="N"
    else
        read -r -p "  $L_LANG_CHANGE_PROMPT [y/N]: " CHANGE_LANG
        CHANGE_LANG="${CHANGE_LANG:-N}"
    fi
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
print_banner "$L_SETUP_BANNER_TITLE"
echo -e "  ${BOLD}${L_SETUP_INTRO}${NC}"
echo -e "  ${BOLD}${L_SETUP_NO_CLOUD}${NC}"
echo ""
if [ "$MAC_UPDATE_NONINTERACTIVE" = "1" ]; then
    CONFIRM_START="Y"
else
    read -r -p "  $L_CONTINUE_PROMPT [Y/n]: " CONFIRM_START
    CONFIRM_START="${CONFIRM_START:-Y}"
fi
if [[ "$CONFIRM_START" =~ ^[Nn] ]]; then
    echo "  $L_CANCELED"
    exit 0
fi

# ============================================================
# PHASE 1: SYSTEM DETECTION
# ============================================================
print_section "$L_SETUP_PHASE_1"
print_info "$L_INFO_PROJECT_DIR $SCRIPT_DIR"

NEW_USER="$(whoami)"
NEW_HOME="$HOME"
print_info "$L_INFO_USER $NEW_USER"
print_info "$L_INFO_HOME $NEW_HOME"

MACOS_VERSION="$(sw_vers -productVersion 2>/dev/null || echo 'unknown')"
MACOS_BUILD="$(sw_vers -buildVersion 2>/dev/null || echo 'unknown')"
MACOS_MAJOR="$(echo "$MACOS_VERSION" | cut -d. -f1)"
print_info "$L_INFO_MACOS $MACOS_VERSION (build: $MACOS_BUILD)"

ARCH="$(uname -m)"
if [ "$ARCH" = "arm64" ]; then
    ARCH_LABEL="Apple Silicon arm64"
    BREW_PREFIX="/opt/homebrew"
else
    ARCH_LABEL="Intel x86_64"
    BREW_PREFIX="/usr/local"
fi
print_info "$L_INFO_ARCH $ARCH_LABEL"
print_info "$L_INFO_BREW_PREFIX $BREW_PREFIX"

HOSTNAME_NEW="$(scutil --get ComputerName 2>/dev/null || hostname 2>/dev/null || echo 'unknown')"
print_info "$L_INFO_HOSTNAME $HOSTNAME_NEW"

DEFAULT_SHELL="$(dscl . -read /Users/"$NEW_USER" UserShell 2>/dev/null | awk '{print $2}' || echo "$SHELL")"
print_info "$L_INFO_SHELL $DEFAULT_SHELL"

if echo "$DEFAULT_SHELL" | grep -q "zsh"; then
    SHELL_PROFILE="$NEW_HOME/.zshrc"
elif echo "$DEFAULT_SHELL" | grep -q "bash"; then
    SHELL_PROFILE="$NEW_HOME/.bash_profile"
else
    SHELL_PROFILE="$NEW_HOME/.zshrc"
fi
print_info "$L_INFO_SHELL_PROFILE $SHELL_PROFILE"

TERM_APP_NAME="Terminal.app"
case "${TERM_PROGRAM:-}" in
    "Apple_Terminal") TERM_APP_NAME="Terminal.app" ;;
    "iTerm.app") TERM_APP_NAME="iTerm.app" ;;
    "WarpTerminal") TERM_APP_NAME="Warp.app" ;;
    "vscode") TERM_APP_NAME="Visual Studio Code.app" ;;
    "Cursor") TERM_APP_NAME="Cursor.app" ;;
    "ghostty") TERM_APP_NAME="Ghostty.app" ;;
esac
print_info "$L_INFO_TERMINAL $TERM_APP_NAME (TERM_PROGRAM=${TERM_PROGRAM:-unknown})"

# ============================================================
# PHASE 2: DETECT OLD USER AND PATHS
# ============================================================
print_section "$L_SETUP_PHASE_2"

OLD_USER=""
OLD_PATH=""

if [ -f "$SCRIPT_DIR/CLAUDE.md" ]; then
    OLD_USER_RAW="$(grep -oE '/Users/[^/]+/' "$SCRIPT_DIR/CLAUDE.md" 2>/dev/null | head -1)"
    if [ -n "$OLD_USER_RAW" ]; then
        OLD_USER="$(echo "$OLD_USER_RAW" | sed 's|/Users/||' | sed 's|/||')"
    fi
    OLD_PATH="$(grep -oE '`/Users/[^`]+`' "$SCRIPT_DIR/CLAUDE.md" 2>/dev/null | head -1 | tr -d '`')"
fi

if [ -n "$OLD_USER" ] && [ "$OLD_USER" != "$NEW_USER" ]; then
    print_info "Detected previous user: $OLD_USER"
    print_info "New user:               $NEW_USER"
    print_info "Previous project path: ${OLD_PATH:-/Users/$OLD_USER/...}"
    print_info "New project path:      $SCRIPT_DIR"
elif [ -n "$OLD_USER" ] && [ "$OLD_USER" = "$NEW_USER" ]; then
    print_ok "Username unchanged: $NEW_USER"
    OLD_USER=""
    if [ -n "$OLD_PATH" ] && [ "$OLD_PATH" != "$SCRIPT_DIR" ]; then
        print_info "Project path changed:"
        print_info "  Old: $OLD_PATH"
        print_info "  New: $SCRIPT_DIR"
    fi
else
    print_info "No previous configuration detected — treating as fresh install."
fi

# ============================================================
# PHASE 3: FIX PATHS IN DOCUMENTATION FILES
# ============================================================
print_section "$L_SETUP_PHASE_3"

# Only update public documentation files (not cloud-only private files)
MD_CHANGED=0

for md_file in "$SCRIPT_DIR/CLAUDE.md" "$SCRIPT_DIR/AGENTS.md" "$SCRIPT_DIR/GEMINI.md" "$SCRIPT_DIR/CODEX.md"; do
    [ -f "$md_file" ] || continue

    CHANGED=0
    TMPFILE="$(mktemp)"
    cp "$md_file" "$TMPFILE"

    if [ -n "$OLD_USER" ] && [ "$OLD_USER" != "$NEW_USER" ]; then
        sed -i '' "s|/Users/${OLD_USER}/|/Users/${NEW_USER}/|g" "$TMPFILE"
        if ! diff -q "$md_file" "$TMPFILE" > /dev/null 2>&1; then
            CHANGED=1
        fi
    fi

    if [ -n "$OLD_PATH" ] && [ "$OLD_PATH" != "$SCRIPT_DIR" ]; then
        OLD_PATH_ESC="$(echo "$OLD_PATH" | sed 's|/|\\/|g')"
        SCRIPT_DIR_ESC="$(echo "$SCRIPT_DIR" | sed 's|/|\\/|g')"
        sed -i '' "s|${OLD_PATH_ESC}|${SCRIPT_DIR_ESC}|g" "$TMPFILE"
        if ! diff -q "$md_file" "$TMPFILE" > /dev/null 2>&1; then
            CHANGED=1
        fi
    fi

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
        print_fixed "$(basename "$md_file") — paths updated"
        add_fix "Paths in $(basename "$md_file"): updated to /Users/$NEW_USER/ + $SCRIPT_DIR"
        MD_CHANGED=$((MD_CHANGED + 1))
    else
        print_ok "$(basename "$md_file") — paths are correct"
    fi
    rm -f "$TMPFILE"
done

if [ $MD_CHANGED -eq 0 ]; then
    print_ok "All documentation paths are correct."
fi

# ============================================================
# PHASE 4: UPDATE MACOS VERSION IN DOCUMENTATION
# ============================================================
print_section "$L_SETUP_PHASE_4"

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

for md_file in "$SCRIPT_DIR/CLAUDE.md" "$SCRIPT_DIR/AGENTS.md" "$SCRIPT_DIR/GEMINI.md" "$SCRIPT_DIR/CODEX.md"; do
    [ -f "$md_file" ] || continue
    TMPFILE="$(mktemp)"
    cp "$md_file" "$TMPFILE"

    # Replace full macOS label (version + TitleCase codename), e.g. "macOS 26.4 Sequoia", "macOS 26.4.1 Sequoia Sequoia"
    # Regex matches consecutive TitleCase codename words (Sequoia, Sonoma) but NOT CVE, Apple, etc.
    sed -i '' "s|macOS [0-9][0-9]*\.[0-9.x]*[0-9x]\( [A-Z][a-z][a-z]*\)*|${NEW_MACOS_LABEL}|g" "$TMPFILE"

    if [ "$ARCH" = "arm64" ]; then
        sed -i '' 's|Intel x86_64|Apple Silicon arm64|g' "$TMPFILE"
    else
        sed -i '' 's|Apple Silicon arm64|Intel x86_64|g' "$TMPFILE"
    fi

    if ! diff -q "$md_file" "$TMPFILE" > /dev/null 2>&1; then
        cp "$TMPFILE" "$md_file"
        print_fixed "$(basename "$md_file") — macOS: $NEW_MACOS_LABEL, arch: $ARCH_LABEL"
        add_fix "$(basename "$md_file"): updated macOS → $NEW_MACOS_LABEL, arch → $ARCH_LABEL"
    else
        print_ok "$(basename "$md_file") — system version already current"
    fi
    rm -f "$TMPFILE"
done

# ============================================================
# PHASE 5: XCODE COMMAND LINE TOOLS
# ============================================================
print_section "$L_SETUP_PHASE_5"

if xcode-select -p &>/dev/null 2>&1; then
    XCLT_PATH="$(xcode-select -p)"
    print_ok "Xcode CLT installed: $XCLT_PATH"
else
    print_warn "Xcode Command Line Tools not installed!"
    print_step "Launching Xcode CLT installer..."
    echo ""
    echo -e "  ${YELLOW}A dialog will appear — click 'Install'.${NC}"
    echo -e "  ${YELLOW}Installation may take a few minutes.${NC}"
    echo ""
    xcode-select --install 2>/dev/null || true
    echo ""
    if [ "$MAC_UPDATE_NONINTERACTIVE" != "1" ]; then
        read -r -p "  Press ENTER after Xcode CLT installation completes..."
    else
        print_warn "Non-interactive mode: install Xcode CLT from the dialog, then re-run setup.sh if needed."
    fi
    if xcode-select -p &>/dev/null 2>&1; then
        print_ok "Xcode CLT installed successfully!"
        add_fix "Installed Xcode Command Line Tools"
    else
        print_error "Xcode CLT still unavailable — check manually."
        add_action "Install Xcode CLT: xcode-select --install"
    fi
fi

# ============================================================
# PHASE 6: HOMEBREW
# ============================================================
print_section "$L_SETUP_PHASE_6"

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
    print_ok "Homebrew installed: $BREW_VER"
    print_ok "Location: $BREW_PATH"

    if [ -f "$SHELL_PROFILE" ]; then
        if grep -q "brew shellenv" "$SHELL_PROFILE" 2>/dev/null; then
            print_ok "Homebrew shellenv in $SHELL_PROFILE — PATH configured"
        else
            print_warn "Homebrew shellenv NOT in $SHELL_PROFILE"
            print_step "Adding Homebrew shellenv to $SHELL_PROFILE..."
            echo "" >> "$SHELL_PROFILE"
            echo "# Homebrew (added by setup.sh)" >> "$SHELL_PROFILE"
            echo "eval \"\$($BREW_PREFIX/bin/brew shellenv)\"" >> "$SHELL_PROFILE"
            print_fixed "Added Homebrew shellenv to $SHELL_PROFILE"
            add_fix "Homebrew PATH added to $SHELL_PROFILE — run: source $SHELL_PROFILE"
        fi
    fi
else
    print_warn "Homebrew not installed."
    echo ""
    if [ "$MAC_UPDATE_NONINTERACTIVE" = "1" ]; then
        INSTALL_BREW="Y"
    else
        read -r -p "  Install Homebrew now? [Y/n]: " INSTALL_BREW
        INSTALL_BREW="${INSTALL_BREW:-Y}"
    fi
    if [[ ! "$INSTALL_BREW" =~ ^[Nn] ]]; then
        print_step "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        if [ -f "$BREW_PREFIX/bin/brew" ]; then
            eval "$($BREW_PREFIX/bin/brew shellenv)"
            command -v brew &>/dev/null && BREW_OK=1
        fi
        if [ $BREW_OK -eq 1 ]; then
            print_ok "Homebrew installed successfully!"
            add_fix "Installed Homebrew"
            if [ -f "$SHELL_PROFILE" ] && ! grep -q "brew shellenv" "$SHELL_PROFILE" 2>/dev/null; then
                echo "" >> "$SHELL_PROFILE"
                echo "# Homebrew" >> "$SHELL_PROFILE"
                echo "eval \"\$($BREW_PREFIX/bin/brew shellenv)\"" >> "$SHELL_PROFILE"
                add_fix "Homebrew shellenv added to $SHELL_PROFILE"
            fi
        else
            print_error "Homebrew installation failed. Install manually: https://brew.sh"
            add_action "Install Homebrew manually: https://brew.sh"
        fi
    else
        print_warn "Homebrew skipped. Most update_* scripts will NOT work without Homebrew."
        add_action "Install Homebrew: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    fi
fi

# ============================================================
# PHASE 7: mas — App Store CLI
# ============================================================
print_section "$L_SETUP_PHASE_7"

if command -v mas &>/dev/null; then
    MAS_VER="$(mas version 2>/dev/null || echo '?')"
    MAS_MAJOR="$(echo "$MAS_VER" | cut -d. -f1)"
    print_ok "mas installed: $MAS_VER"

    if [ "${MAS_MAJOR:-0}" -lt 4 ] 2>/dev/null; then
        print_warn "mas $MAS_VER < 4.0 — upgrade required for macOS 26.x"
        if command -v brew &>/dev/null; then
            print_step "Upgrading mas..."
            HOMEBREW_NO_AUTO_UPDATE=1 brew upgrade mas 2>/dev/null || brew upgrade mas
            MAS_VER="$(mas version 2>/dev/null || echo '?')"
            print_ok "mas upgraded to: $MAS_VER"
            add_fix "mas upgraded to $MAS_VER (required >= 4.0 for macOS 26.x)"
        fi
    fi
else
    print_warn "mas not installed."
    if command -v brew &>/dev/null; then
        print_step "Installing mas via Homebrew..."
        brew install mas
        if command -v mas &>/dev/null; then
            MAS_VER="$(mas version 2>/dev/null || echo '?')"
            print_ok "mas installed: $MAS_VER"
            add_fix "Installed mas $MAS_VER"
        else
            print_error "mas installation failed."
            add_action "Install mas manually: brew install mas"
        fi
    else
        print_warn "Homebrew unavailable — cannot install mas automatically."
        add_action "Install mas after Homebrew: brew install mas"
    fi
fi

# ============================================================
# PHASE 8: PYTHON 3
# ============================================================
print_section "$L_SETUP_PHASE_8"

PYTHON3_OK=0
PYTHON3_PATH=""

for py_candidate in python3 "$BREW_PREFIX/bin/python3" \
    "$BREW_PREFIX/opt/python@3.11/bin/python3" \
    "$BREW_PREFIX/opt/python@3.14/bin/python3" \
    /usr/bin/python3; do
    if command -v "$py_candidate" &>/dev/null 2>&1; then
        PYTHON3_PATH="$(command -v "$py_candidate" 2>/dev/null || echo "$py_candidate")"
        PY_VER="$($py_candidate --version 2>&1 | head -1)"
        print_ok "Python 3 available: $PY_VER ($PYTHON3_PATH)"
        PYTHON3_OK=1
        break
    fi
done

if [ $PYTHON3_OK -eq 0 ]; then
    print_warn "Python 3 not available."
    if command -v brew &>/dev/null; then
        print_step "Installing python@3.11 via Homebrew..."
        brew install python@3.11
        if command -v python3 &>/dev/null || command -v "$BREW_PREFIX/bin/python3" &>/dev/null; then
            PYTHON3_PATH="$(command -v python3 2>/dev/null || echo "$BREW_PREFIX/bin/python3")"
            print_ok "Python 3 installed."
            add_fix "Installed Python 3 via Homebrew"
            PYTHON3_OK=1
        else
            print_error "Python 3 installation failed."
            add_action "Install Python 3: brew install python@3.11"
        fi
    else
        print_warn "Homebrew unavailable — install Python 3 manually."
        add_action "Install Python 3: brew install python@3.11"
    fi
fi

# ============================================================
# PHASE 9: ESSENTIAL TOOLS (curl, git)
# ============================================================
print_section "$L_SETUP_PHASE_9"

if command -v curl &>/dev/null; then
    CURL_VER="$(curl --version | head -1 | awk '{print $2}')"
    print_ok "curl: $CURL_VER"
else
    print_error "curl unavailable! Required by update_internet_apps.sh (GitHub API)."
    add_action "curl missing — usually built into macOS. Check: which curl"
fi

if command -v git &>/dev/null; then
    GIT_VER="$(git --version | awk '{print $3}')"
    print_ok "git: $GIT_VER"
else
    print_warn "git unavailable (normally installed with Xcode CLT)."
    add_action "Install git: xcode-select --install or brew install git"
fi

# ============================================================
# PHASE 10: OPTIONAL UPDATE TOOLS (msupdate, Docker, Keystone)
# ============================================================
print_section "$L_SETUP_PHASE_10"

# ── msupdate (Microsoft AutoUpdate) ──────────────────────────
MSUPDATE_PATHS="/Library/Application Support/Microsoft/MAU2.0/Microsoft AutoUpdate.app/Contents/MacOS/msupdate"
MSUPDATE_ALT="/Applications/Microsoft AutoUpdate.app/Contents/MacOS/msupdate"

if [ -f "$MSUPDATE_PATHS" ]; then
    print_ok "msupdate available: $MSUPDATE_PATHS"
elif [ -f "$MSUPDATE_ALT" ]; then
    print_ok "msupdate available: $MSUPDATE_ALT"
elif command -v msupdate &>/dev/null; then
    print_ok "msupdate available in PATH"
else
    MS_APPS_FOUND=0
    for ms_app in "/Applications/Microsoft Word.app" "/Applications/Microsoft Excel.app" \
        "/Applications/Microsoft Outlook.app" "/Applications/Microsoft PowerPoint.app" \
        "/Applications/Microsoft Teams.app" "/Applications/Microsoft OneNote.app"; do
        [ -d "$ms_app" ] && MS_APPS_FOUND=$((MS_APPS_FOUND + 1))
    done

    if [ $MS_APPS_FOUND -gt 0 ]; then
        print_warn "msupdate NOT found, but $MS_APPS_FOUND Microsoft 365 app(s) are installed."
        print_info "msupdate is usually installed with the first MS365 app."
        print_info "Expected location: $MSUPDATE_PATHS"
        add_warning "msupdate unavailable — Microsoft 365 updates may not work. Launch any MS365 app and retry."
    else
        print_skip "msupdate — Microsoft 365 apps not installed"
    fi
fi

# ── Docker Desktop CLI ────────────────────────────────────────
if command -v docker &>/dev/null; then
    DOCKER_VER="$(docker --version 2>/dev/null | awk '{print $3}' | tr -d ',')"
    DOCKER_MAJOR="$(echo "$DOCKER_VER" | cut -d. -f1)"
    DOCKER_MINOR="$(echo "$DOCKER_VER" | cut -d. -f2)"
    print_ok "Docker CLI: $DOCKER_VER"

    DOCKER_OK_VER=0
    if [ "${DOCKER_MAJOR:-0}" -gt 4 ] 2>/dev/null; then
        DOCKER_OK_VER=1
    elif [ "${DOCKER_MAJOR:-0}" -eq 4 ] && [ "${DOCKER_MINOR:-0}" -ge 37 ] 2>/dev/null; then
        DOCKER_OK_VER=1
    fi

    if [ $DOCKER_OK_VER -eq 1 ]; then
        print_ok "Docker Desktop >= 4.37 — 'docker desktop update' available"
    else
        print_warn "Docker Desktop $DOCKER_VER < 4.37 — 'docker desktop update' may not work"
        add_warning "Docker Desktop $DOCKER_VER may be too old. Recommended >= 4.37."
    fi
elif [ -d "/Applications/Docker.app" ]; then
    print_warn "Docker Desktop installed but 'docker' not in PATH."
    print_info "Launch Docker Desktop once to activate the CLI."
    add_action "Launch Docker Desktop once to activate 'docker' in PATH"
else
    print_skip "Docker Desktop — not installed"
fi

# ── Google Keystone (Chrome/Google Drive updater) ─────────────
KEYSTONE_AGENT="/Library/Google/GoogleSoftwareUpdate/GoogleSoftwareUpdate.bundle/Contents/Resources/GoogleSoftwareUpdateAgent.app/Contents/MacOS/GoogleSoftwareUpdateAgent"
if [ -f "$KEYSTONE_AGENT" ]; then
    print_ok "Google Keystone agent available (Chrome + Google Drive)"
elif [ -d "/Applications/Google Chrome.app" ] || [ -d "/Applications/Google Drive.app" ]; then
    print_warn "Google Chrome/Drive installed but Keystone agent NOT found."
    print_info "Expected: $KEYSTONE_AGENT"
    print_info "Keystone is installed automatically with Chrome. Launch Chrome once."
    add_warning "Google Keystone agent missing — Chrome/Google Drive updates via Keystone won't work. Launch Chrome."
else
    print_skip "Google Keystone — Chrome/Google Drive not installed"
fi

# ============================================================
# PHASE 11: SCRIPT PERMISSIONS
# ============================================================
print_section "$L_SETUP_PHASE_11"

CHMOD_COUNT=0
for sh_file in "$SCRIPT_DIR"/*.sh "$SCRIPT_DIR/dev-sync"/*.sh; do
    [ -f "$sh_file" ] || continue
    if [ ! -x "$sh_file" ]; then
        chmod +x "$sh_file"
        print_fixed "chmod +x $(basename "$sh_file")"
        CHMOD_COUNT=$((CHMOD_COUNT + 1))
    else
        print_ok "$(basename "$sh_file") — executable ✓"
    fi
done

if [ $CHMOD_COUNT -gt 0 ]; then
    add_fix "chmod +x applied to $CHMOD_COUNT script(s)"
else
    print_ok "All scripts already have execute permissions."
fi

# ============================================================
# PHASE 12: APP STORE LOGIN CHECK
# ============================================================
print_section "$L_SETUP_PHASE_12"

if command -v mas &>/dev/null; then
    APPLE_ID="$(mas account 2>/dev/null || echo '')"
    if [ -n "$APPLE_ID" ]; then
        print_ok "Signed in to App Store as: $APPLE_ID"
    else
        print_info "mas account returned no ID (known macOS 26.x limitation) — testing via mas list..."
    fi

    if mas list &>/dev/null 2>&1; then
        print_ok "App Store access confirmed (mas list works)"
        MAS_APP_COUNT="$(mas list 2>/dev/null | wc -l | tr -d ' ')"
        print_info "Installed App Store apps: $MAS_APP_COUNT"
    else
        print_error "No App Store access via mas!"
        print_info "Sign in to the App Store manually, then re-run this script."
        open -a "App Store" 2>/dev/null || true
        add_action "Sign in to App Store (Apple menu → App Store → Account)"
    fi
else
    print_warn "mas unavailable — cannot check App Store."
fi

# ============================================================
# PHASE 13: ACCESSIBILITY PERMISSION (AppleScript / Track 2)
# ============================================================
print_section "$L_SETUP_PHASE_13"

print_info "Testing Accessibility permission for: $TERM_APP_NAME"
AX_TEST="$(osascript -e 'tell application "System Events" to return name of first process whose frontmost is true' 2>&1 || echo 'FAILED')"

if echo "$AX_TEST" | grep -qi "not allowed\|assistive\|accessibility\|access\|FAILED"; then
    print_warn "Accessibility permission NOT granted for: $TERM_APP_NAME"
    echo ""
    echo -e "  ${YELLOW}${BOLD}Track 2 (iPad apps via App Store) will NOT work without this.${NC}"
    echo ""
    echo -e "  ${BOLD}How to fix (one-time, ~30 seconds):${NC}"
    echo "    1. Open System Settings → Privacy & Security → Accessibility"
    echo "    2. Click '+' and add your terminal:"
    echo "       ${TERM_APP_NAME}"
    echo "    3. Make sure the checkbox is enabled"
    echo ""

    if [ "$MAC_UPDATE_NONINTERACTIVE" = "1" ]; then
        OPEN_PREFS="N"
    else
        read -r -p "  Open System Settings → Accessibility now? [Y/n]: " OPEN_PREFS
        OPEN_PREFS="${OPEN_PREFS:-Y}"
    fi
    if [[ ! "$OPEN_PREFS" =~ ^[Nn] ]]; then
        open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
        print_info "System Settings opened."
    fi

    add_action "Grant Accessibility for $TERM_APP_NAME: System Settings → Privacy → Accessibility"
else
    print_ok "Accessibility granted for $TERM_APP_NAME — Track 2 (iPad apps) will work"
fi

# ============================================================
# FINAL SUMMARY
# ============================================================
echo ""
echo -e "${BLUE}${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}${BOLD}║                    📊  SETUP SUMMARY                        ║${NC}"
echo -e "${BLUE}${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}System: macOS $MACOS_VERSION — $ARCH_LABEL${NC}"
echo -e "  ${BOLD}User: $NEW_USER | Project: $SCRIPT_DIR${NC}"
echo ""

if [ -n "$FIXES_APPLIED" ]; then
    echo -e "  ${GREEN}${BOLD}✅ FIXED / INSTALLED:${NC}"
    echo -e "$FIXES_APPLIED" | while IFS= read -r line; do
        [ -n "$line" ] && echo -e "     ${GREEN}• $line${NC}"
    done
    echo ""
fi

if [ -n "$WARNINGS" ]; then
    echo -e "  ${YELLOW}${BOLD}⚠️  WARNINGS:${NC}"
    echo -e "$WARNINGS" | while IFS= read -r line; do
        [ -n "$line" ] && echo -e "     ${YELLOW}• $line${NC}"
    done
    echo ""
fi

if [ -n "$ACTIONS_REQUIRED" ]; then
    echo -e "  ${RED}${BOLD}⬛ REQUIRED MANUAL ACTIONS:${NC}"
    echo -e "$ACTIONS_REQUIRED" | while IFS= read -r line; do
        [ -n "$line" ] && echo -e "     ${RED}• $line${NC}"
    done
    echo ""
fi

echo -e "  ${BOLD}🏁 READINESS CHECKLIST:${NC}"
echo ""

if command -v brew &>/dev/null; then
    echo -e "  ${GREEN}✅ Homebrew — OK${NC}"
else
    echo -e "  ${RED}❌ Homebrew — installation required${NC}"
fi

if command -v mas &>/dev/null; then
    echo -e "  ${GREEN}✅ mas (App Store CLI) — OK${NC}"
else
    echo -e "  ${YELLOW}⚠️  mas — missing (brew install mas)${NC}"
fi

if [ $PYTHON3_OK -eq 1 ]; then
    echo -e "  ${GREEN}✅ Python 3 — OK${NC}"
else
    echo -e "  ${YELLOW}⚠️  Python 3 — missing (brew install python@3.11)${NC}"
fi

if command -v curl &>/dev/null; then
    echo -e "  ${GREEN}✅ curl — OK${NC}"
else
    echo -e "  ${RED}❌ curl — missing${NC}"
fi

SCRIPTS_OK=1
for sh in update_all.sh update_system.sh update_appstore.sh update_internet_apps.sh update_brew.sh; do
    [ -x "$SCRIPT_DIR/$sh" ] || SCRIPTS_OK=0
done
if [ $SCRIPTS_OK -eq 1 ]; then
    echo -e "  ${GREEN}✅ Scripts (chmod +x) — OK${NC}"
else
    echo -e "  ${YELLOW}⚠️  Scripts — run: chmod +x $SCRIPT_DIR/*.sh${NC}"
fi

if command -v mas &>/dev/null && mas list &>/dev/null 2>&1; then
    echo -e "  ${GREEN}✅ App Store — signed in${NC}"
else
    echo -e "  ${YELLOW}⚠️  App Store — verify sign-in manually${NC}"
fi

if ! echo "$AX_TEST" | grep -qi "not allowed\|assistive\|accessibility\|FAILED" 2>/dev/null; then
    echo -e "  ${GREEN}✅ Accessibility ($TERM_APP_NAME) — OK${NC}"
else
    echo -e "  ${YELLOW}⚠️  Accessibility — grant permission: Settings → Privacy → Accessibility${NC}"
fi

echo ""
echo -e "  ${BOLD}🚀 NEXT STEPS:${NC}"
echo -e "     ${GREEN}cd $SCRIPT_DIR && bash update_all.sh${NC}"
echo ""
echo -e "${BLUE}${BOLD}══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  ✅  SETUP COMPLETE — macOS Updates ready!          ${NC}"
echo -e "${BLUE}${BOLD}══════════════════════════════════════════════════════════════${NC}"
echo ""
