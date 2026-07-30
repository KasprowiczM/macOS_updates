#!/usr/bin/env bash
# ============================================================
# macOS Updates — i18n Language Loader
# ============================================================
# Provides:
#   1. Loads language strings from lang_${MAC_LANG}.sh
#   2. ask_language_picker() — interactive language selection
#   3. save_language_pref() — saves language choice to .mac_update_prefs
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
PREFS_FILE="$SCRIPT_DIR/.mac_update_prefs"

# ── Load language preference ──────────────────────────────────
MAC_LANG="en"  # Default language

if [ -f "$PREFS_FILE" ]; then
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

    # Create or update .mac_update_prefs
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
