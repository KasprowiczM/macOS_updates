#!/usr/bin/env bash
# ============================================================
# macOS Updates — i18n Language Loader
# ============================================================
# Provides:
#   1. Loads language strings from lang_${MAC_LANG}.sh
#   2. ask_language_picker() — interactive language selection
#   3. save_language_pref() — saves the language choice to <config>/lang
#      (a developer checkout that still has .mac_update_prefs keeps using it)
#
# Usage in scripts:
#   SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
#   . "$SCRIPT_DIR/i18n/loader.sh"
#
# Notes:
#   - Requires SCRIPT_DIR to be set before sourcing
#   - bash 3.2+ compatible (no associative arrays)
# ============================================================

# Ensure SCRIPT_DIR is set
if [ -z "$SCRIPT_DIR" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

# ── Preferences file ─────────────────────────────────────────
# Language lives in <config>/lang (lib/paths.sh). A developer checkout whose
# old .mac_update_prefs exists, while <config>/lang does not, keeps reading
# and writing the old file; nothing is moved automatically.
PREFS_FILE="$SCRIPT_DIR/.mac_update_prefs"
LANG_PREF_FILE=""
if [ -f "$SCRIPT_DIR/lib/paths.sh" ]; then
    type mu_data_resolve >/dev/null 2>&1 || . "$SCRIPT_DIR/lib/paths.sh"
    if mu_data_resolve 2>/dev/null; then
        LANG_PREF_FILE="$MU_LANG_FILE"
        [ -n "$MU_LEGACY_PREFS" ] && LANG_PREF_FILE=""
    fi
fi

# ── Load language preference ──────────────────────────────────
# Allow environment override via MAC_UPDATE_LANG or MAC_LANG
MAC_LANG="${MAC_UPDATE_LANG:-${MAC_LANG:-}}"

if [ -z "$MAC_LANG" ] && [ -n "$LANG_PREF_FILE" ] && [ -f "$LANG_PREF_FILE" ]; then
    IFS= read -r MAC_LANG < "$LANG_PREF_FILE" || true
    MAC_LANG="$(printf '%s' "$MAC_LANG" | tr -d '[:space:]')"
fi

if [ -z "$MAC_LANG" ] && [ -f "$PREFS_FILE" ]; then
    # Parse MAC_LANG from .mac_update_prefs
    # Simple key=value format: MAC_LANG=en (no spaces around =)
    while IFS='=' read -r key value; do
        # Remove leading/trailing whitespace without quote/backslash processing
        key="${key#"${key%%[![:space:]]*}"}"
        key="${key%"${key##*[![:space:]]}"}"
        value="${value#"${value%%[![:space:]]*}"}"
        value="${value%"${value##*[![:space:]]}"}"
        if [ "$key" = "MAC_LANG" ]; then
            MAC_LANG="$value"
            break
        fi
    done < "$PREFS_FILE"
fi

# Nothing explicit (MAC_UPDATE_LANG / MAC_LANG) and nothing saved: follow the
# system language, the same order as the terminal interface: the locale
# variables, then the first of the user's macOS preferred languages.
if [ -z "$MAC_LANG" ]; then
    _mu_loc="${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}"
    case "$_mu_loc" in
        ""|C|C.*|POSIX) _mu_loc="" ;;
    esac
    _mu_gp="${MAC_UPDATE_GLOBAL_PREFS:-$HOME/Library/Preferences/.GlobalPreferences.plist}"
    if [ -z "$_mu_loc" ] && [ -f "$_mu_gp" ] && command -v python3 >/dev/null 2>&1; then
        _mu_loc="$(python3 -c 'import plistlib,sys
try:
    with open(sys.argv[1], "rb") as f:
        langs = plistlib.load(f).get("AppleLanguages") or []
    print(str(langs[0]) if langs else "")
except Exception:
    pass' "$_mu_gp" 2>/dev/null)"
    fi
    unset _mu_gp
    MAC_LANG="$(printf '%s' "$_mu_loc" | cut -c1-2 | tr '[:upper:]' '[:lower:]')"
    unset _mu_loc
fi

# Validate language code
case "$MAC_LANG" in
    pl|en|es|it|pt|de|fr) ;;
    *)
        MAC_LANG="en"
        ;;
esac

# ── Source language file (set -a auto-exports all L_* assignments) ─
LANG_FILE="$SCRIPT_DIR/i18n/lang_${MAC_LANG}.sh"

if [ -f "$LANG_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$LANG_FILE"
    set +a
else
    # Fallback to English if language file not found
    echo "Warning: Language file not found: $LANG_FILE" >&2
    LANG_FILE="$SCRIPT_DIR/i18n/lang_en.sh"
    if [ -f "$LANG_FILE" ]; then
        set -a
        # shellcheck disable=SC1090
        . "$LANG_FILE"
        set +a
    else
        echo "Error: English language file not found. Aborting." >&2
        return 1
    fi
fi

# MAC_LANG is set in this file, not in lang_*.sh — export it explicitly
export MAC_LANG


# ============================================================
# ask_language_picker() — Interactive language selection
# ============================================================
ask_language_picker() {
    # Displays language menu to stderr (so it shows even inside $(...) capture)
    # Echoes only the chosen language code to stdout for capture
    # Usage: CHOSEN_LANG=$(ask_language_picker)

    echo "" >&2
    echo "════════════════════════════════════════════════" >&2
    echo "  Select your language:" >&2
    echo "════════════════════════════════════════════════" >&2
    echo "  1) English" >&2
    echo "  2) Polski         (Polish)" >&2
    echo "  3) Español        (Spanish)" >&2
    echo "  4) Italiano       (Italian)" >&2
    echo "  5) Português      (Portuguese — Brazilian)" >&2
    echo "  6) Deutsch        (German)" >&2
    echo "  7) Français       (French)" >&2
    echo "════════════════════════════════════════════════" >&2
    echo "" >&2
    # read -p sends prompt to stderr automatically in bash
    read -p "  Enter number [1-7] (default: 1 — English): " LANG_CHOICE </dev/tty
    LANG_CHOICE="${LANG_CHOICE:-1}"
    echo "" >&2

    case "$LANG_CHOICE" in
        1) echo "en" ;;
        2) echo "pl" ;;
        3) echo "es" ;;
        4) echo "it" ;;
        5) echo "pt" ;;
        6) echo "de" ;;
        7) echo "fr" ;;
        *) echo "en" ;;
    esac
}

# ============================================================
# save_language_pref() — Save language choice to .mac_update_prefs
# ============================================================
save_language_pref() {
    local lang_code="$1"

    if [ -z "$lang_code" ]; then
        return 1
    fi

    if [ -n "$LANG_PREF_FILE" ]; then
        case "$lang_code" in pl|en|es|it|pt|de|fr) ;; *) return 1 ;; esac
        ( umask 077; mkdir -p "$(dirname "$LANG_PREF_FILE")" && printf '%s\n' "$lang_code" > "$LANG_PREF_FILE" ) || return 1
        return 0
    fi

    # Developer checkout with the old file: create or update .mac_update_prefs
    # NOTE: macOS sed returns 0 even when the regex doesn't match, so a plain
    # `sed ... || fallback` never triggers the fallback when the file exists
    # but lacks a MAC_LANG= line. Check presence explicitly before replacing.
    if [ -f "$PREFS_FILE" ]; then
        if grep -q "^MAC_LANG=" "$PREFS_FILE" 2>/dev/null; then
            sed -i '' "s/^MAC_LANG=.*/MAC_LANG=$lang_code/" "$PREFS_FILE" || return 1
        else
            echo "MAC_LANG=$lang_code" >> "$PREFS_FILE"
        fi
    else
        # Create new file
        cat > "$PREFS_FILE" << EOF
MAC_LANG=$lang_code
MAC_CLOUD_PROVIDER=protondrive
MAC_CLOUD_PATH=
MAC_CLOUD_RCLONE_REMOTE=
EOF
    fi

    return 0
}

# ============================================================
# Language already loaded via . "$LANG_FILE" above
# All L_ variables are now available to scripts
# ============================================================
