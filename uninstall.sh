#!/usr/bin/env bash
# ============================================================
# uninstall.sh - remove mac-update from this Mac
# ============================================================
# Run it as `mac-update uninstall`, or `bash uninstall.sh` from the program folder.
#
# It removes only these known places, nothing else:
#   - the scheduled-run LaunchAgent(s) that belong to mac-update (stopped first)
#   - the launchers ~/.local/bin/mac-update and ~/.local/bin/macos-update
#   - the program folder, its .previous copy and leftovers of an interrupted update,
#     except the Node.js and npm tools mac-update manages in it (node/,
#     npm-global/), which your PATH may use: kept unless you pass --purge-tools
#   - the state folder (logs, caches, backups)      default: removed
#   - the config folder (your settings)             default: kept
# It never removes Homebrew, mas, any app, or a shell profile, never uses sudo,
# and refuses any path that resolves outside your home folder.
# ============================================================

usage() {
    cat <<'USAGE_TEXT'
Usage: uninstall.sh [options]

  --yes, -y        do not ask; keep settings and remove the state folder unless told otherwise
  --keep-config    keep the settings folder (the default)
  --purge          also remove the settings folder
  --keep-state     keep the state folder (logs, caches, backups)
  --purge-tools    also remove the Node.js and npm tools mac-update manages in the
                   program folder (node/, npm-global/); kept by default
  --dir DIR        program folder (default: where mac-update is installed)
  --dry-run        show what would be removed; remove nothing
  -h, --help       show this help
USAGE_TEXT
}

main() {
    local SCRIPT_DIR
    SCRIPT_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)"

    local ASSUME_YES=0 PURGE=0 KEEP_CONFIG_FLAG=0 KEEP_STATE=0 PURGE_TOOLS=0 DRY_RUN=0 OPT_DIR=""
    local GREEN="" YELLOW="" RED="" BOLD="" NC=""
    if [ -t 1 ] && [ -z "${NO_COLOR:-}" ] && [ "${TERM:-dumb}" != dumb ]; then
        GREEN=$'\033[0;32m'; YELLOW=$'\033[0;33m'; RED=$'\033[0;31m'; BOLD=$'\033[1m'; NC=$'\033[0m'
    fi
    row_ok()   { printf '  %s\xe2\x9c\x93%s %s\n' "$GREEN" "$NC" "$1"; }
    row_warn() { printf '  %s!%s %s\n' "$YELLOW" "$NC" "$1"; }
    row_note() { printf '    %s\n' "$1"; }
    row_plan() { printf '  %s\xe2\x86\x92%s %s\n' "$BOLD" "$NC" "$1"; }
    die() { # die "what happened." "what to do." [code]
        printf '  %s\xe2\x9c\x97%s %s\n' "$RED" "$NC" "$1" >&2
        printf '    %s\n' "$2" >&2
        exit "${3:-1}"
    }

    while [ "$#" -gt 0 ]; do
        case "$1" in
            --yes|-y) ASSUME_YES=1; shift ;;
            --keep-config) KEEP_CONFIG_FLAG=1; shift ;;
            --purge) PURGE=1; shift ;;
            --keep-state) KEEP_STATE=1; shift ;;
            --purge-tools) PURGE_TOOLS=1; shift ;;
            --dry-run) DRY_RUN=1; shift ;;
            --dir)
                [ -n "${2:-}" ] || die "--dir needs a folder." "For example: --dir \$HOME/.local/share/mac-update" 2
                OPT_DIR="$2"; shift 2 ;;
            --dir=*) OPT_DIR="${1#--dir=}"; shift ;;
            -h|--help) usage; return 0 ;;
            *) die "Unknown option: $1" "Run it with --help to see the options." 2 ;;
        esac
    done
    if [ "$PURGE" = 1 ] && [ "$KEEP_CONFIG_FLAG" = 1 ]; then
        die "--purge and --keep-config contradict each other." "Choose one of them." 2
    fi

    # ---- where things are: the one resolver ----
    if [ ! -f "$SCRIPT_DIR/lib/paths.sh" ]; then
        die "lib/paths.sh is missing next to this script, so the folders cannot be located safely." \
            "Run \"mac-update uninstall\" from an installed copy, or download the release again."
    fi
    # shellcheck disable=SC1091
    . "$SCRIPT_DIR/lib/paths.sh"
    mu_paths_resolve "$SCRIPT_DIR" || die "The toolkit folders could not be located." "Check that HOME and any MAC_UPDATE_* settings are absolute paths."
    local PROGRAM="$MU_PROGRAM_DIR" CONFIG="$MU_CONFIG_DIR" STATE="$MU_STATE_DIR"
    if [ -n "$OPT_DIR" ]; then
        case "$OPT_DIR" in
            /*) PROGRAM="$(_mu_clean "$OPT_DIR")" ;;
            *) die "--dir must be an absolute path." "Pass something like --dir \"\$HOME/.local/share/mac-update\"." 2 ;;
        esac
    fi

    local HOME_DIR="${HOME%/}" HOME_PHYS
    HOME_PHYS="$(_mu_physical "$HOME_DIR")"
    local LAUNCHER="$HOME_DIR/.local/bin/mac-update"
    local ALIAS="$HOME_DIR/.local/bin/macos-update"

    # Toolkit-managed data inside the program folder. update_npm_cli.sh keeps the managed
    # Node.js (node/) and the global npm packages (npm-global/) in ~/.local/share/mac-update,
    # which is also the default program folder, and briefly node.staging.* / node.backup.*
    # while it replaces Node; *.older.* are older copies the installer set aside. People's
    # PATH points into them, so uninstall keeps them unless --purge-tools is given.
    # One name per word, shell patterns allowed, matched without regard to case (APFS is
    # case-insensitive); a new name is one more word here.
    # Keep in step with MANAGED_DATA_NAMES in install.sh (a test compares them).
    local MANAGED_DATA_NAMES='node npm-global node.staging.* node.backup.* node.older.* npm-global.older.*'
    # Finder metadata that may sit next to them: left with them.
    local IGNORED_NAMES='.DS_Store'
    name_in() { # name_in NAME "PATTERNS" : NAME matches one of the patterns, ignoring case
        local name="$1" pat hit=1 had=0
        shopt -q nocasematch && had=1
        shopt -s nocasematch
        set -f
        for pat in $2; do
            case "$name" in $pat) hit=0; break ;; esac
        done
        set +f
        [ "$had" = 1 ] || shopt -u nocasematch
        return "$hit"
    }
    is_kept_name() { name_in "$1" "$MANAGED_DATA_NAMES $IGNORED_NAMES"; }
    managed_in() { # managed_in DIR : the managed data names in a real folder DIR, comma separated
        local e n out=""
        [ -d "$1" ] && [ ! -L "$1" ] || return 0
        for e in "$1"/* "$1"/.[!.]* "$1"/..?*; do
            [ -e "$e" ] || [ -L "$e" ] || continue
            n="${e##*/}"
            if name_in "$n" "$MANAGED_DATA_NAMES"; then out="${out:+$out, }$n"; fi
        done
        printf '%s' "$out"
    }
    # managed_deep PATH : where managed data sits in PATH, in its subfolders and in theirs
    # (a staging folder holds a toolkit copy one or two levels down); it does not look
    # inside managed folders themselves.
    managed_deep() {
        local a b m out=""
        m="$(managed_in "$1")"
        [ -z "$m" ] || out="${1}: ${m}"
        for a in "$1"/* "$1"/.[!.]* "$1"/..?*; do
            [ -d "$a" ] && [ ! -L "$a" ] || continue
            ! name_in "${a##*/}" "$MANAGED_DATA_NAMES" || continue
            m="$(managed_in "$a")"
            [ -z "$m" ] || out="${out:+$out; }${a}: ${m}"
            for b in "$a"/* "$a"/.[!.]* "$a"/..?*; do
                [ -d "$b" ] && [ ! -L "$b" ] || continue
                ! name_in "${b##*/}" "$MANAGED_DATA_NAMES" || continue
                m="$(managed_in "$b")"
                [ -z "$m" ] || out="${out:+$out; }${b}: ${m}"
            done
        done
        printf '%s' "$out"
    }
    clear_except_kept() { # clear_except_kept DIR : remove everything in DIR but the kept names
        local e failed=0
        for e in "$1"/* "$1"/.[!.]* "$1"/..?*; do
            [ -e "$e" ] || [ -L "$e" ] || continue
            is_kept_name "${e##*/}" && continue
            rm -rf "$e" 2>/dev/null
            if [ -e "$e" ] || [ -L "$e" ]; then failed=1; fi
        done
        return "$failed"
    }
    local AGENT_DIR="$HOME_DIR/Library/LaunchAgents"
    local USER_NAME UID_NUM
    USER_NAME="$(id -un 2>/dev/null || echo user)"
    UID_NUM="$(id -u 2>/dev/null || echo 0)"
    local LABELS="io.github.mac-update com.${USER_NAME}.macos-updates"

    # ---- path safety: refuse before anything is touched ----
    # safe_path LABEL PATH KIND   (KIND: program | data)
    safe_path() {
        local label="$1" p="$2" kind="$3" phys base
        case "$p" in
            /*) ;;
            *) die "The ${label} folder (${p}) is not an absolute path." "Nothing was removed." ;;
        esac
        case "$p" in
            */..|*/../*|*/.|*/./*) die "The ${label} folder (${p}) contains . or .. parts." "Nothing was removed." ;;
        esac
        if [ "$p" = "/" ] || [ "$p" = "$HOME_DIR" ]; then
            die "Refusing to remove ${p}: that is not a mac-update folder." "Nothing was removed."
        fi
        phys="$(_mu_physical "$p")"
        if [ "$phys" = "$HOME_PHYS" ] || ! _mu_inside "$phys" "$HOME_PHYS"; then
            die "The ${label} folder (${p}) is outside your home folder, so it will not be removed." \
                "Nothing was removed. Remove it yourself if it really belongs to mac-update."
        fi
        if [ -L "$p" ] && ! _mu_inside "$phys" "$HOME_PHYS"; then
            die "The ${label} folder (${p}) is a link that leaves your home folder." "Nothing was removed."
        fi
        base="${p##*/}"
        if [ "$kind" = program ]; then
            if [ -e "$p/.git" ]; then
                die "${p} is a git checkout (developer mode), and uninstall will not delete a working copy." \
                    "Nothing was removed. Delete the checkout yourself if you want it gone."
            fi
            if [ -e "$p" ] && [ ! -f "$p/.install-info" ] && [ "$base" != "mac-update" ]; then
                die "${p} was not created by the mac-update installer, so it will not be removed." \
                    "Nothing was removed. Remove it yourself if it really belongs to mac-update."
            fi
        else
            if [ "$base" != "mac-update" ]; then
                die "The ${label} folder (${p}) is not named mac-update, so it will not be removed." \
                    "Nothing was removed. Remove it yourself, or rename it to mac-update first."
            fi
        fi
        return 0
    }
    safe_path program "$PROGRAM" program
    safe_path state "$STATE" data
    safe_path config "$CONFIG" data
    local item
    for item in "$CONFIG" "$STATE"; do
        if _mu_inside "$(_mu_physical "$item")" "$(_mu_physical "$PROGRAM")"; then
            die "${item} is inside the program folder, so removing the program would remove it too." \
                "Nothing was removed. Move it out of ${PROGRAM} first."
        fi
    done

    # ---- an installer that is running right now owns these folders ----
    local LOCK="${PROGRAM}.lock" lock_pid=""
    if [ -d "$LOCK" ]; then
        lock_pid="$(head -n 1 "$LOCK/pid" 2>/dev/null)"
        case "$lock_pid" in ''|*[!0-9]*) lock_pid="" ;; esac
        if [ -n "$lock_pid" ] && kill -0 "$lock_pid" 2>/dev/null; then
            die "The mac-update installer is running right now (process ${lock_pid})." \
                "Nothing was removed. Wait for it to finish, then run uninstall again."
        fi
    fi

    # ---- decisions ----
    local KEEP_CONFIG=1 REMOVE_STATE=1
    [ "$PURGE" = 1 ] && KEEP_CONFIG=0
    [ "$KEEP_STATE" = 1 ] && REMOVE_STATE=0

    ask() { # ask QUESTION DEFAULT(y|n) : returns 0 for yes
        local question="$1" default="$2" answer hint
        if [ "$default" = y ]; then hint="[Y/n]"; else hint="[y/N]"; fi
        printf '  %s %s ' "$question" "$hint"
        IFS= read -r answer || answer=""
        [ -n "$answer" ] || answer="$default"
        case "$answer" in y|Y|yes|YES|Yes) return 0 ;; esac
        return 1
    }

    printf '\n%smac-update uninstall%s\n\n' "$BOLD" "$NC"
    if [ "$DRY_RUN" = 0 ] && [ "$ASSUME_YES" = 0 ]; then
        [ -t 0 ] || die "There is no terminal to ask you anything." "Run it in Terminal, or add --yes (and --purge to remove your settings too)."
        row_plan "This removes the program (${PROGRAM}) and the mac-update and macos-update launchers."
        local tools_here
        tools_here="$(managed_in "$PROGRAM")"
        if [ -n "$tools_here" ] && [ "$PURGE_TOOLS" = 0 ]; then
            row_note "It keeps ${tools_here} in ${PROGRAM}: the Node.js and npm tools mac-update manages (--purge-tools removes them)."
        fi
        if [ "$PURGE" = 0 ] && [ "$KEEP_CONFIG_FLAG" = 0 ]; then
            if ask "Keep your settings in ${CONFIG}?" y; then KEEP_CONFIG=1; else KEEP_CONFIG=0; fi
        fi
        if [ "$KEEP_STATE" = 0 ]; then
            if ask "Keep logs, caches and backups in ${STATE}?" n; then REMOVE_STATE=0; else REMOVE_STATE=1; fi
        fi
        ask "Remove mac-update now?" n || { row_note "Nothing was removed."; return 0; }
        echo
    fi

    # ---- 1. scheduled runs ----
    local label plist
    for label in $LABELS; do
        plist="$AGENT_DIR/${label}.plist"
        [ -e "$plist" ] || continue
        if ! grep -q -e 'mac-update' -e 'update_all.sh' -e 'macos-updates' "$plist" 2>/dev/null; then
            row_warn "${plist} does not look like a mac-update schedule, so it was left alone."
            continue
        fi
        if [ "$DRY_RUN" = 1 ]; then
            row_plan "Stop the scheduled run ${label} and remove ${plist}."
            continue
        fi
        if command -v launchctl >/dev/null 2>&1; then
            launchctl bootout "gui/${UID_NUM}/${label}" >/dev/null 2>&1 \
                || launchctl bootout "gui/${UID_NUM}" "$plist" >/dev/null 2>&1 || true
        fi
        if rm -f "$plist" 2>/dev/null; then
            row_ok "Stopped and removed the scheduled run ${label}"
        else
            row_warn "Could not remove ${plist}."
            row_note "Remove it yourself: rm \"${plist}\""
        fi
    done

    # ---- 2. launchers: mac-update and its long name macos-update ----
    local link cur link_dir owned
    for link in "$LAUNCHER" "$ALIAS"; do
        owned=0
        if [ -L "$link" ]; then
            cur="$(readlink "$link")"
            link_dir="${cur%/bin/mac-update}"
            if [ "$cur" = "$PROGRAM/bin/mac-update" ] || { [ "$link_dir" != "$cur" ] && { [ -f "$link_dir/.install-info" ] || [ ! -e "$cur" ]; }; }; then
                owned=1
            fi
        elif [ -f "$link" ] && grep -q 'mac-update launcher' "$link" 2>/dev/null; then
            owned=1
        fi
        if [ -L "$link" ] || [ -e "$link" ]; then
            if [ "$owned" = 1 ]; then
                if [ "$DRY_RUN" = 1 ]; then
                    row_plan "Remove the launcher ${link}."
                elif rm -f "$link" 2>/dev/null; then
                    row_ok "Removed the launcher ${link}"
                else
                    row_warn "Could not remove ${link}."
                    row_note "Remove it yourself: rm \"${link}\""
                fi
            else
                row_warn "${link} is not the mac-update launcher, so it was left alone."
            fi
        fi
    done

    # ---- 3. program folder and leftovers ----
    local leftover found=0 tools deep
    for leftover in "$PROGRAM" "${PROGRAM}.previous" "${PROGRAM}.swap-old" "${PROGRAM}".tmp.* "${PROGRAM}.lock"; do
        if [ -e "$leftover" ] || [ -L "$leftover" ]; then
            [ "$leftover" = "${PROGRAM}.lock" ] || found=1
            tools="$(managed_in "$leftover")"
            deep="$(managed_deep "$leftover")"
            if [ -n "$deep" ] && [ "$deep" != "${leftover}: ${tools}" ] && [ "$PURGE_TOOLS" = 0 ]; then
                # managed data below the top level (for example inside an interrupted update's
                # staging folder): keep the whole folder rather than guess what belongs to it
                if [ "$DRY_RUN" = 1 ]; then
                    row_plan "Keep ${leftover}: it holds Node.js or npm tools mac-update manages (${deep})."
                else
                    row_warn "Kept ${leftover}: it holds Node.js or npm tools mac-update manages (${deep})."
                    row_note "Move what you need, then delete it by hand, or run uninstall again with --purge-tools."
                fi
                continue
            fi
            if [ -n "$tools" ] && [ "$PURGE_TOOLS" = 0 ]; then
                # Never rm -rf a folder that holds the managed tools: remove the rest around them.
                if [ "$DRY_RUN" = 1 ]; then
                    row_plan "Remove the program files in ${leftover}, but keep ${tools} (the Node.js and npm tools mac-update manages; --purge-tools removes them too)."
                elif clear_except_kept "$leftover"; then
                    row_ok "Removed the program files from ${leftover}"
                    row_ok "Kept ${tools} in ${leftover}: the Node.js and npm tools mac-update manages, which your PATH may use. Remove them with --purge-tools."
                else
                    row_warn "Could not remove every program file from ${leftover}; ${tools} were kept."
                    row_note "Remove the rest yourself, but not ${tools} unless you mean to."
                fi
                continue
            fi
            if [ "$DRY_RUN" = 1 ]; then
                row_plan "Remove ${leftover}."
            elif rm -rf "$leftover" 2>/dev/null && [ ! -e "$leftover" ]; then
                row_ok "Removed ${leftover}"
            else
                row_warn "Could not remove ${leftover}."
                row_note "Remove it yourself: rm -rf \"${leftover}\""
            fi
        fi
    done
    [ "$found" = 1 ] || row_ok "No program folder found at ${PROGRAM}"

    # ---- 4. state ----
    if [ "$REMOVE_STATE" = 1 ]; then
        if [ -e "$STATE" ] || [ -L "$STATE" ]; then
            if [ "$DRY_RUN" = 1 ]; then
                row_plan "Remove the state folder ${STATE} (logs, caches, backups)."
            elif rm -rf "$STATE" 2>/dev/null && [ ! -e "$STATE" ]; then
                row_ok "Removed the state folder ${STATE}"
            else
                row_warn "Could not remove ${STATE}."
                row_note "Remove it yourself: rm -rf \"${STATE}\""
            fi
        fi
    elif [ -e "$STATE" ]; then
        row_ok "Kept the state folder ${STATE}"
    fi

    # ---- 5. config ----
    if [ "$KEEP_CONFIG" = 0 ]; then
        if [ -e "$CONFIG" ] || [ -L "$CONFIG" ]; then
            if [ "$DRY_RUN" = 1 ]; then
                row_plan "Remove your settings folder ${CONFIG}."
            elif rm -rf "$CONFIG" 2>/dev/null && [ ! -e "$CONFIG" ]; then
                row_ok "Removed your settings folder ${CONFIG}"
            else
                row_warn "Could not remove ${CONFIG}."
                row_note "Remove it yourself: rm -rf \"${CONFIG}\""
            fi
        fi
    elif [ -e "$CONFIG" ]; then
        if [ "$DRY_RUN" = 1 ]; then
            row_plan "Keep your settings folder ${CONFIG}."
        else
            row_ok "Kept your settings folder ${CONFIG}"
        fi
    fi

    # ---- shell profile hint (never edited by uninstall) ----
    local rc
    for rc in "$HOME_DIR/.zshrc" "$HOME_DIR/.bash_profile"; do
        if [ -f "$rc" ] && grep -q '^# >>> mac-update >>>' "$rc" 2>/dev/null; then
            row_note "${rc} still has a small PATH block between \"# >>> mac-update >>>\" and \"# <<< mac-update <<<\"; delete those lines if you like."
        fi
    done

    echo
    if [ "$DRY_RUN" = 1 ]; then
        printf '  %sDry run: nothing was removed.%s\n\n' "$BOLD" "$NC"
    else
        printf '  %sDone.%s Homebrew, the App Store tools and your apps were not touched.\n\n' "$BOLD" "$NC"
    fi
    return 0
}

main "$@"; exit $?
