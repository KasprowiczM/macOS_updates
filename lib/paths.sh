#!/usr/bin/env bash
# lib/paths.sh - single source of truth for the three toolkit directories (Bash 3.2+).
#
# Shell twin of lib/python/mu_paths.py: identical input gives identical output
# (tests/test_paths.py compares them). Change both together.
#
#   program  replaced by an upgrade (program files only); nothing writes inside it at
#            runtime except the Node.js and npm tools update_npm_cli.sh keeps in the
#            default folder (node/, npm-global/), which upgrades and uninstall leave alone
#   config   user-owned settings, never touched by installers or upgrades
#   state    disposable: logs, caches, scan results, backups
#
# Resolution, first match wins:
#   program  $MAC_UPDATE_HOME
#            this toolkit's own root when it is a git checkout (developer mode)
#            or an installed tree (it carries .install-info)
#            ~/.local/share/mac-update
#   config   $MAC_UPDATE_CONFIG_DIR, $XDG_CONFIG_HOME/mac-update, ~/.config/mac-update
#   state    $MAC_UPDATE_STATE_DIR,  $XDG_STATE_HOME/mac-update,  ~/.local/state/mac-update
#
# MAC_UPDATE_* overrides must be absolute (a relative one is an error); XDG_*
# values that are not absolute are ignored. Trailing slashes are dropped.
#
# Library use (safe under set -u; sourcing prints nothing):
#   . "$SCRIPT_DIR/lib/paths.sh"
#   mu_program_dir | mu_config_dir | mu_state_dir | mu_program_mode
#   mu_ensure_dir config|state        # creates the directory with mode 0700
#   mu_paths_resolve [ROOT]           # sets MU_PROGRAM_DIR MU_CONFIG_DIR MU_STATE_DIR MU_PROGRAM_MODE
# Command line:
#   bash lib/paths.sh [print|program|config|state|mode|ensure config|ensure state]

_MU_PATHS_FILE="${BASH_SOURCE[0]:-$0}"

_mu_clean() {
    local p="$1"
    while [ "${p%/}" != "$p" ] && [ -n "${p%/}" ]; do
        p="${p%/}"
    done
    [ -n "$p" ] || p="/"
    printf '%s' "$p"
}

# Physical directory of the toolkit this file belongs to.
mu_toolkit_root() {
    ( cd "$(dirname "$_MU_PATHS_FILE")/.." 2>/dev/null && pwd -P )
}

# Resolve a path that may not exist yet: the deepest existing ancestor is made
# physical, the missing tail is appended unchanged.
_mu_physical() {
    local p="$1" tail="" base
    while [ ! -d "$p" ] && [ "$p" != "/" ] && [ -n "$p" ]; do
        base="${p##*/}"
        tail="/${base}${tail}"
        p="${p%/*}"
        [ -n "$p" ] || p="/"
    done
    p="$( cd "$p" 2>/dev/null && pwd -P )" || p="$1"
    [ "$p" = "/" ] && p=""
    printf '%s%s' "$p" "$tail"
}

_mu_inside() {
    local path="$1" parent="$2"
    parent="${parent%/}"
    case "$path" in
        "$parent"|"$parent"/*) return 0 ;;
    esac
    return 1
}

mu_paths_resolve() {
    local root="${1:-}" home value base
    MU_PROGRAM_DIR="" MU_CONFIG_DIR="" MU_STATE_DIR="" MU_PROGRAM_MODE=""
    home="${HOME:-}"
    if [ -z "$home" ]; then
        echo "HOME is not set, so the toolkit folders cannot be located." >&2
        return 2
    fi
    case "$home" in
        /*) ;;
        *) echo "HOME must be an absolute path." >&2; return 2 ;;
    esac
    home="$(_mu_clean "$home")"
    if [ -n "$root" ]; then
        root="$( cd "$root" 2>/dev/null && pwd -P )" || root="$1"
    else
        root="$(mu_toolkit_root)"
    fi

    value="${MAC_UPDATE_HOME:-}"
    if [ -n "$value" ]; then
        case "$value" in
            /*) ;;
            *) echo "MAC_UPDATE_HOME must be an absolute path." >&2; return 2 ;;
        esac
        MU_PROGRAM_DIR="$(_mu_clean "$value")"
        MU_PROGRAM_MODE="env"
    elif [ -e "$root/.git" ]; then
        MU_PROGRAM_DIR="$root"
        MU_PROGRAM_MODE="checkout"
    elif [ -f "$root/.install-info" ]; then
        MU_PROGRAM_DIR="$root"
        MU_PROGRAM_MODE="installed"
    else
        MU_PROGRAM_DIR="$home/.local/share/mac-update"
        MU_PROGRAM_MODE="default"
    fi

    value="${MAC_UPDATE_CONFIG_DIR:-}"
    if [ -n "$value" ]; then
        case "$value" in
            /*) ;;
            *) echo "MAC_UPDATE_CONFIG_DIR must be an absolute path." >&2; return 2 ;;
        esac
        MU_CONFIG_DIR="$(_mu_clean "$value")"
    else
        base="$home/.config"
        case "${XDG_CONFIG_HOME:-}" in
            /*) base="$(_mu_clean "$XDG_CONFIG_HOME")" ;;
        esac
        MU_CONFIG_DIR="$base/mac-update"
    fi

    value="${MAC_UPDATE_STATE_DIR:-}"
    if [ -n "$value" ]; then
        case "$value" in
            /*) ;;
            *) echo "MAC_UPDATE_STATE_DIR must be an absolute path." >&2; return 2 ;;
        esac
        MU_STATE_DIR="$(_mu_clean "$value")"
    else
        base="$home/.local/state"
        case "${XDG_STATE_HOME:-}" in
            /*) base="$(_mu_clean "$XDG_STATE_HOME")" ;;
        esac
        MU_STATE_DIR="$base/mac-update"
    fi
    return 0
}

mu_program_dir() { mu_paths_resolve "${1:-}" && printf '%s\n' "$MU_PROGRAM_DIR"; }
mu_config_dir()  { mu_paths_resolve "${1:-}" && printf '%s\n' "$MU_CONFIG_DIR"; }
mu_state_dir()   { mu_paths_resolve "${1:-}" && printf '%s\n' "$MU_STATE_DIR"; }
mu_program_mode() { mu_paths_resolve "${1:-}" && printf '%s\n' "$MU_PROGRAM_MODE"; }

# Create the config or state directory (0700). Refuses a directory inside, or a
# symlink into, the program directory: that tree is replaced on every update.
mu_ensure_dir() {
    local kind="${1:-}" root="${2:-}" target
    case "$kind" in
        config|state) ;;
        *) echo "Only the config and state folders are created on demand." >&2; return 2 ;;
    esac
    mu_paths_resolve "$root" || return 2
    if [ "$kind" = config ]; then target="$MU_CONFIG_DIR"; else target="$MU_STATE_DIR"; fi
    if _mu_inside "$(_mu_physical "$target")" "$(_mu_physical "$MU_PROGRAM_DIR")"; then
        echo "The $kind folder is inside the program folder, which is replaced on every update." >&2
        return 2
    fi
    if [ ! -d "$target" ]; then
        ( umask 077; mkdir -p "$target" ) 2>/dev/null || {
            echo "The $kind folder $target cannot be created." >&2
            return 2
        }
        chmod 700 "$target" 2>/dev/null || true
    fi
    if _mu_inside "$(_mu_physical "$target")" "$(_mu_physical "$MU_PROGRAM_DIR")"; then
        echo "The $kind folder is a link into the program folder, which is replaced on every update." >&2
        return 2
    fi
    printf '%s\n' "$target"
}

# ---------------------------------------------------------------- data
# Where each kind of data lives (1.9.1):
#   logs        <state>/logs            (MAC_UPDATE_LOGS_DIR wins)
#   lock        <state>/lock
#   reports     <config>/reports/APPLICATIONS.md, <config>/reports/UPDATES.md
#               (outside the state folder: the inventory journal refuses a report there)
#   overrides   <config>/overrides.tsv  (MAC_UPDATE_OVERRIDES_FILE wins); read
#               falls back to <state>/user_overrides.tsv while the new file is missing
#   language    <config>/lang
# A developer checkout that still keeps data in the old places (<checkout>/logs,
# <checkout>/APPLICATIONS.md, <checkout>/UPDATES.md, <checkout>/.mac_update_prefs)
# keeps using them while the new location does not exist yet. Nothing is moved
# automatically; mu_legacy_notice prints one line pointing at `mac-update migrate`.
# Sets MU_LOGS_DIR MU_LOCK_FILE MU_APPLICATIONS_MD MU_UPDATES_MD MU_OVERRIDES_FILE
# MU_OVERRIDES_READ MU_LANG_FILE MU_LEGACY_PREFS MU_LEGACY_DATA.
mu_data_resolve() {
    local root="${1:-}" old
    mu_paths_resolve "$root" || return 2
    MU_LEGACY_DATA=""
    if [ -n "${MAC_UPDATE_LOGS_DIR:-}" ]; then
        MU_LOGS_DIR="$(_mu_clean "$MAC_UPDATE_LOGS_DIR")"
    else
        MU_LOGS_DIR="$MU_STATE_DIR/logs"
        old="$MU_PROGRAM_DIR/logs"
        if [ "$MU_PROGRAM_MODE" = checkout ] && [ -d "$old" ] && [ ! -L "$old" ] && [ ! -e "$MU_LOGS_DIR" ]; then
            MU_LOGS_DIR="$old"
            MU_LEGACY_DATA="${MU_LEGACY_DATA}${old}
"
        fi
    fi
    MU_LOCK_FILE="$MU_STATE_DIR/lock"
    MU_APPLICATIONS_MD="$MU_CONFIG_DIR/reports/APPLICATIONS.md"
    MU_UPDATES_MD="$MU_CONFIG_DIR/reports/UPDATES.md"
    if [ "$MU_PROGRAM_MODE" = checkout ]; then
        old="$MU_PROGRAM_DIR/APPLICATIONS.md"
        if [ -f "$old" ] && [ ! -e "$MU_APPLICATIONS_MD" ]; then
            MU_APPLICATIONS_MD="$old"
            MU_LEGACY_DATA="${MU_LEGACY_DATA}${old}
"
        fi
        old="$MU_PROGRAM_DIR/UPDATES.md"
        if [ -f "$old" ] && [ ! -e "$MU_UPDATES_MD" ]; then
            MU_UPDATES_MD="$old"
            MU_LEGACY_DATA="${MU_LEGACY_DATA}${old}
"
        fi
    fi
    if [ -n "${MAC_UPDATE_OVERRIDES_FILE:-}" ]; then
        MU_OVERRIDES_FILE="$MAC_UPDATE_OVERRIDES_FILE"
        MU_OVERRIDES_READ="$MAC_UPDATE_OVERRIDES_FILE"
    else
        MU_OVERRIDES_FILE="$MU_CONFIG_DIR/overrides.tsv"
        MU_OVERRIDES_READ="$MU_OVERRIDES_FILE"
        old="$MU_STATE_DIR/user_overrides.tsv"
        if [ ! -e "$MU_OVERRIDES_FILE" ] && [ -f "$old" ]; then
            MU_OVERRIDES_READ="$old"
            MU_LEGACY_DATA="${MU_LEGACY_DATA}${old}
"
        fi
    fi
    MU_LANG_FILE="$MU_CONFIG_DIR/lang"
    MU_LEGACY_PREFS=""
    old="$MU_PROGRAM_DIR/.mac_update_prefs"
    if [ "$MU_PROGRAM_MODE" = checkout ] && [ -f "$old" ] && [ ! -e "$MU_LANG_FILE" ]; then
        MU_LEGACY_PREFS="$old"
    fi
    return 0
}

mu_logs_dir()          { mu_data_resolve "${1:-}" && printf '%s\n' "$MU_LOGS_DIR"; }
mu_lock_file()         { mu_data_resolve "${1:-}" && printf '%s\n' "$MU_LOCK_FILE"; }
mu_applications_md()   { mu_data_resolve "${1:-}" && printf '%s\n' "$MU_APPLICATIONS_MD"; }
mu_updates_md()        { mu_data_resolve "${1:-}" && printf '%s\n' "$MU_UPDATES_MD"; }

# One line on stderr, once per process tree, when old-location data is in use.
mu_legacy_notice() {
    [ "${MU_LEGACY_NOTICE_SHOWN:-0}" = "1" ] && return 0
    mu_data_resolve "${1:-}" 2>/dev/null || return 0
    [ -n "$MU_LEGACY_DATA" ] || return 0
    MU_LEGACY_NOTICE_SHOWN=1
    export MU_LEGACY_NOTICE_SHOWN
    printf '%s\n' "Note: data from an older layout is still used in place ($(printf '%s' "$MU_LEGACY_DATA" | tr '\n' ' ' | sed 's/ $//')); run \`mac-update migrate\` to copy it to the new folders." >&2
}

mu_paths_print() {
    mu_paths_resolve "${1:-}" || return 2
    printf 'program=%s\nconfig=%s\nstate=%s\nmode=%s\n' \
        "$MU_PROGRAM_DIR" "$MU_CONFIG_DIR" "$MU_STATE_DIR" "$MU_PROGRAM_MODE"
}

_mu_paths_cli() {
    local root="" command="" arg1=""
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --root)
                [ -n "${2:-}" ] || { echo "--root needs a directory." >&2; return 2; }
                root="$2"; shift 2 ;;
            *)
                if [ -z "$command" ]; then command="$1"
                elif [ -z "$arg1" ]; then arg1="$1"
                else command="?"; fi
                shift ;;
        esac
    done
    case "${command:-print}" in
        print) mu_paths_print "$root" ;;
        program) mu_program_dir "$root" ;;
        config) mu_config_dir "$root" ;;
        state) mu_state_dir "$root" ;;
        mode) mu_program_mode "$root" ;;
        logs) mu_logs_dir "$root" ;;
        lock) mu_lock_file "$root" ;;
        ensure) [ -n "$arg1" ] || { echo "Usage: paths.sh ensure config|state" >&2; return 2; }
                mu_ensure_dir "$arg1" "$root" ;;
        *) echo "Usage: paths.sh [print|program|config|state|mode|ensure config|ensure state] [--root DIR]" >&2
           return 2 ;;
    esac
}

if [ "${BASH_SOURCE[0]:-}" = "$0" ]; then
    _mu_paths_cli "$@"
    exit $?
fi
