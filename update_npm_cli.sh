#!/usr/bin/env bash
# ============================================================
# SKRYPT 3: Aktualizacja natywnych runtime'ów i CLI przez npm
# ============================================================
# Data: 2026-04-18
set -o pipefail
# Homebrew can remove /opt/homebrew/bin/python3 (or any other symlink) while
# this process is running. Without checkhash, bash keeps calling the stale
# hashed path ("No such file or directory") instead of re-searching PATH.
shopt -s checkhash

# Kompatybilność: bash 3.2+ (macOS domyślny shell)
# Opis:
#   - Instaluje/aktualizuje Node.js latest przez `n` (bez Homebrew)
#   - Instaluje/aktualizuje npm, pnpm i wybrane CLI przez `npm`
#   - Instaluje/aktualizuje Bun natywnie (bez Homebrew)
#   - Aktualizuje CLI z własnym updaterem, np. Agy (`agy update`)
#   - Migruje wybrane CLI z Homebrew do npm/native
#   - Zapisuje snapshoty wersji przed i po aktualizacji
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MANIFEST_PATH="${MANIFEST_PATH:-$SCRIPT_DIR/config/npm_global_clis.txt}"
BUN_VERSION_PATH="$SCRIPT_DIR/config/bun_version.txt"

. "$SCRIPT_DIR/lib/platform.sh"
mac_update_require_supported_platform || exit 1

. "$SCRIPT_DIR/lib/cli.sh"
. "$SCRIPT_DIR/lib/ui.sh"
. "$SCRIPT_DIR/i18n/loader.sh"
. "$SCRIPT_DIR/lib/severity.sh"
. "$SCRIPT_DIR/lib/github_release.sh"
. "$SCRIPT_DIR/lib/brew.sh"
. "$SCRIPT_DIR/lib/events.sh"
. "$SCRIPT_DIR/lib/overrides.sh"
mac_update_severity_init

# cli_override_gate <display> <package> <command> <from> <event-id> [latest-version-fn]
# lib/overrides.sh group "cli"; the terminal interface writes the package name
# (npm) or the command name (native tools), and display/package/command all
# match. manual/skip emit their item_end here and return 1 (caller skips the
# install). For manual, a cheap existing check (latest-version-fn) still
# reports "update available". Sets CLI_EVENT_ID/CLI_EVENT_NAME for cli_item_result.
CLI_EVENT_ID=""
CLI_EVENT_NAME=""
cli_override_gate() {
    local display="$1" package="$2" command="$3" from="${4:-}" mode latest=""
    CLI_EVENT_ID="${5:-$display}"
    CLI_EVENT_NAME="$display"
    mode="$(mu_override_mode cli "$CLI_EVENT_ID" "$display" "$package" "$command")"
    case "$mode" in
        skip)
            cli_end "$CLI_EVENT_ID" skipped "$from" "" "user override: skip" "" "$display"
            return 1
            ;;
        manual)
            [ -n "${6:-}" ] && latest="$("$6" 2>/dev/null | head -n 1 | tr -d '[:space:]')"
            if [ -n "$latest" ] && [ -n "$from" ] && [ "$latest" = "$from" ]; then
                cli_end "$CLI_EVENT_ID" current "$from" "$latest" "manual by user override" "" "$display"
            elif [ -n "$latest" ]; then
                print_info "${display}: update available ${from:-?} → ${latest} (manual by user override)"
                cli_end "$CLI_EVENT_ID" needs_you "$from" "$latest" "update available (manual)" manual_mode "$display"
            else
                print_info "${display}: automatic update off (manual by user override)"
                cli_end "$CLI_EVENT_ID" needs_you "$from" "" "manual by user override" manual_mode "$display"
            fi
            return 1
            ;;
    esac
    return 0
}

# Every manifest tool gets exactly one item_end per run. cli_end records the
# ids that ended; cli_skip_item reports a tool that is not installed (or not
# checked) as skipped; cli_finalize_items closes anything still open.
CLI_ENDED="|"
CLI_STARTED="|"
cli_end() {
    case "$CLI_ENDED" in *"|$1|"*) return 0 ;; esac
    CLI_ENDED="${CLI_ENDED}$1|"
    mu_item_end cli "$@"
}
# cli_skip_item <id> <display> <detail> [method]
cli_skip_item() {
    case "$CLI_ENDED" in *"|$1|"*) return 0 ;; esac
    mu_item_start cli "$1" "$2" "" "" "${4:-}"
    cli_end "$1" skipped "" "" "${3:-}" "" "$2"
}
# cli_manifest_id <package> <method> <command> — the id each tool reports under.
cli_manifest_id() {
    case "$2" in
        npm) printf '%s' "$1" ;;
        native-node) printf 'node' ;;
        native-bun) printf 'bun' ;;
        *) printf '%s' "$3" ;;
    esac
}
# cli_manifest_total — number of tracked tools in the manifest.
cli_manifest_total() {
    awk -F'|' '$1 == "" || $1 ~ /^#/ { next } { n++ } END { print n + 0 }' "$MANIFEST_PATH" 2>/dev/null
}
# cli_finalize_items — a tool nothing reported on (toolchain unavailable, step
# skipped) still gets a row.
cli_finalize_items() {
    local display package method brew_formula command id
    while IFS='|' read -r display package method brew_formula command; do
        case "$display" in ""|\#*) continue ;; esac
        id="$(cli_manifest_id "$package" "$method" "$command")"
        case "$CLI_ENDED" in *"|$id|"*) continue ;; esac
        if [ "$id" = opencode ] && [ "${OPENCODE_NATIVE_TRIED:-0}" = 1 ]; then
            cli_end opencode failed "" "" "native update did not complete" unknown "$display"
            continue
        fi
        cli_skip_item "$id" "$display" "not checked in this run" "$method"
    done < "$MANIFEST_PATH"
}

# cli_item_result <display> <before> <after> <command-exit>
# Success = the command exited 0 AND the re-read version is real.
cli_item_result() {
    local before="$2" after="$3" rc="$4" id="${CLI_EVENT_ID:-$1}"
    if [ "$rc" -ne 0 ] || [ -z "$after" ] || [ "$after" = "?" ]; then
        cli_end "$id" failed "$before" "$after" "update command failed or version unreadable" unknown "$1"
    elif [ -n "$before" ] && [ "$before" = "$after" ]; then
        cli_end "$id" current "$before" "$after" "" "" "$1"
    else
        cli_end "$id" updated "$before" "$after" "" "" "$1"
    fi
}

TOOLCHAIN_HOME="${MAC_UPDATE_TOOLCHAIN_HOME:-$HOME/.local/share/mac-update}"
N_PREFIX="$TOOLCHAIN_HOME/node"
NPM_GLOBAL_PREFIX="$TOOLCHAIN_HOME/npm-global"
NPM_GLOBAL_BIN="$NPM_GLOBAL_PREFIX/bin"
LOCAL_BIN="$HOME/.local/bin"

cleanup_npm_cli() {
    rm -rf "${TMPDIR:-/tmp}"/mac_update_node.* 2>/dev/null || true
    rm -rf "$TOOLCHAIN_HOME"/node.staging.* 2>/dev/null || true
}
BUN_HOME="${BUN_INSTALL:-$HOME/.bun}"
BUN_BIN="${BUN_BIN:-$BUN_HOME/bin}"
NPMRC_PATH="$HOME/.npmrc"

print_header() { ui_print_header "$1"; }



sanitize_npm_stderr() {
    awk '
        {
            lower = tolower($0)
            if (lower ~ /(_authtoken|_auth[[:space:]]*[:=]|authorization[[:space:]]*[:=]|npm_token[[:space:]]*[:=]|password[[:space:]]*[:=]|token[[:space:]]*[:=])/) {
                print "[REDACTED sensitive diagnostic line]"
                next
            }
            if ($0 ~ /https?:\/\/[^[:space:]\/@]+@/) {
                print "[REDACTED URL credentials]"
                next
            }
            print substr($0, 1, 500)
        }
    '
}

run_quiet_with_error_log() {
    local label="$1"
    shift
    local log_root="${TMPDIR:-/tmp}"
    local stderr_file
    local command_exit

    if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -d "$MAC_UPDATE_SESSION_DIR" ]; then
        log_root="$MAC_UPDATE_SESSION_DIR"
    fi
    stderr_file="$(mktemp "$log_root/npm_cli_stderr.XXXXXX")" || return 1

    "$@" </dev/null >/dev/null 2>"$stderr_file"
    command_exit=$?
    if [ "$command_exit" -ne 0 ]; then
        if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -d "$MAC_UPDATE_SESSION_DIR" ]; then
            {
                printf '=== %s (exit=%s) ===\n' "$label" "$command_exit"
                # Keep diagnostics useful but bounded: npm can emit thousands of lines.
                tail -n 30 "$stderr_file" | sanitize_npm_stderr
                echo ""
            } >> "$MAC_UPDATE_SESSION_DIR/npm_cli_errors.log" 2>/dev/null || true
        else
            printf '  Diagnostic (%s):\n' "$label" >&2
            tail -n 12 "$stderr_file" | sanitize_npm_stderr >&2
        fi
    fi
    rm -f "$stderr_file" 2>/dev/null || true
    return "$command_exit"
}

find_shell_profile() {
    local default_shell
    default_shell="$(dscl . -read /Users/"$USER" UserShell 2>/dev/null | awk '{print $2}' || echo "$SHELL")"
    if echo "$default_shell" | grep -q "zsh"; then
        echo "$HOME/.zshrc"
    elif echo "$default_shell" | grep -q "bash"; then
        echo "$HOME/.bash_profile"
    else
        echo "$HOME/.zshrc"
    fi
}

resolve_target_file() {
    local target="$1"
    if [ -L "$target" ]; then
        local link_dest
        link_dest="$(readlink "$target")" || link_dest=""
        if [ -n "$link_dest" ]; then
            if [ "${link_dest#/}" = "$link_dest" ]; then
                target="$(dirname "$target")/$link_dest"
            else
                target="$link_dest"
            fi
            if [ -L "$target" ]; then
                print_warn "$(printf "$L_NPM_DEEP_SYMLINK_CHAIN" "$1" "$target")"
            fi
        fi
    fi
    echo "$target"
}

declare_profile_backup() {
    local raw_target="$1"
    local real_target
    # Edits applied to a staging copy (see ensure_toolchain_paths) never back up.
    [ "${_MACUPD_PROFILE_STAGING:-0}" = "1" ] && return 0
    real_target="$(resolve_target_file "$raw_target")"
    [ -f "$real_target" ] || return 0

    local backup_key
    backup_key="$(echo "$real_target" | tr -c 'a-zA-Z0-9_' '_')"
    local backed_up=0
    eval "backed_up=\${_MACUPD_BACKED_UP_${backup_key}:-0}"
    if [ "$backed_up" -ne 1 ]; then
        local ts backup_path
        ts="$(date +%Y%m%d%H%M%S)"
        backup_path="${real_target}.macupd-backup-${ts}"
        if cp "$real_target" "$backup_path" 2>/dev/null; then
            chmod 600 "$backup_path" 2>/dev/null || true
            print_info "$(printf "$L_NPM_PROFILE_BACKUP_FMT" "$backup_path")"
            eval "_MACUPD_BACKED_UP_${backup_key}=1"
            prune_profile_backups "$real_target"
        fi
    fi
}

# Keep only the newest MAC_UPDATE_MAX_PROFILE_BACKUPS copies (default 5).
# Every run used to leave one behind forever; on the 2026-08-19 machine that
# was 36 copies of ~/.zshrc, each carrying whatever secrets the live profile
# happened to hold at the time. An un-rotated backup is a secret with a long
# tail — rotate it like the run logs.
prune_profile_backups() {
    local real_target="$1"
    local keep="${MAC_UPDATE_MAX_PROFILE_BACKUPS:-5}"
    case "$keep" in
        ''|*[!0-9]*) keep=5 ;;
    esac
    [ "$keep" -lt 1 ] && keep=1

    local total
    # shellcheck disable=SC2012  # our own backup names: <profile>.macupd-backup-<14 digits>
    total="$(ls -1t "${real_target}".macupd-backup-* 2>/dev/null | wc -l | tr -d ' ')"
    [ -n "$total" ] || return 0
    [ "$total" -le "$keep" ] && return 0

    # shellcheck disable=SC2012
    ls -1t "${real_target}".macupd-backup-* 2>/dev/null \
        | tail -n +"$((keep + 1))" \
        | while IFS= read -r stale; do
            [ -n "$stale" ] && rm -f "$stale" 2>/dev/null || true
        done
}

ensure_line_in_file() {
    local raw_target="$1"
    local line="$2"
    local target
    target="$(resolve_target_file "$raw_target")"
    touch "$target" || return 1
    if ! grep -Fqx "$line" "$target" 2>/dev/null; then
        declare_profile_backup "$raw_target"
        printf '%s\n' "$line" >> "$target"
    fi
}

remove_line_from_file() {
    local raw_target="$1"
    local line="$2"
    local target
    target="$(resolve_target_file "$raw_target")"
    [ -f "$target" ] || return 0

    # Nothing to remove: no content change, so no backup and no rewrite.
    grep -Fqx -- "$line" "$target" 2>/dev/null || return 0

    declare_profile_backup "$raw_target"

    local tmpfile
    tmpfile="$(mktemp "${TMPDIR:-/tmp}/mac_update_profile.XXXXXX")" || return 1
    grep -Fvx "$line" "$target" > "$tmpfile" 2>/dev/null || true
    if ! cat "$tmpfile" > "$target"; then
        rm -f "$tmpfile"
        return 1
    fi
    rm -f "$tmpfile"
}

remove_npmrc_prefix() {
    local target
    target="$(resolve_target_file "$NPMRC_PATH")"
    [ -f "$target" ] || return 0

    # Only back up / rewrite when a prefix/globalconfig line actually exists.
    grep -Eq '^(prefix|globalconfig) *=' "$target" 2>/dev/null || return 0

    declare_profile_backup "$NPMRC_PATH"

    local tmpfile
    tmpfile="$(mktemp "${TMPDIR:-/tmp}/mac_update_npmrc.XXXXXX")" || return 1
    grep -Ev '^(prefix|globalconfig) *=' "$target" > "$tmpfile" 2>/dev/null || true
    if ! cat "$tmpfile" > "$target"; then
        rm -f "$tmpfile"
        return 1
    fi
    rm -f "$tmpfile"
    [ -s "$target" ] || rm -f "$target"
}

expand_node_manager_paths() {
    # Homebrew paths (/usr/local/bin, /opt/homebrew/bin) are appended at the end of PATH as
    # fallback lookup locations for system node managers, without overriding managed toolchain paths.
    local node_dir
    for node_dir in "$HOME/.n/bin" /usr/local/bin /opt/homebrew/bin; do
        if [ -d "$node_dir" ]; then
            case ":$PATH:" in
                *":$node_dir:"*) ;;
                *) export PATH="$PATH:$node_dir" ;;
            esac
        fi
    done
    if [ -d "$HOME/.nvm/versions/node" ]; then
        for node_dir in "$HOME/.nvm/versions/node"/v*/bin; do
            if [ -d "$node_dir" ]; then
                case ":$PATH:" in
                    *":$node_dir:"*) ;;
                    *) export PATH="$PATH:$node_dir" ;;
                esac
            fi
        done
    fi
}

ensure_toolchain_paths() {
    local profile

    mkdir -p "$TOOLCHAIN_HOME" "$N_PREFIX" "$NPM_GLOBAL_PREFIX" "$NPM_GLOBAL_BIN" "$BUN_HOME" "$LOCAL_BIN" || return 1
    remove_npmrc_prefix || return 1

    export N_PREFIX
    export BUN_INSTALL="$BUN_HOME"
    export PATH="$LOCAL_BIN:$NPM_GLOBAL_BIN:$N_PREFIX/bin:$BUN_BIN:$PATH"
    expand_node_manager_paths
    hash -r 2>/dev/null || true

    profile="$(find_shell_profile)"
    sync_profile_block "$profile"
}

# The managed block is normalised by removing every known variant and re-appending
# the canonical lines. Doing that in place rewrote (and backed up) the profile on
# every run even when nothing changed — 2026-10-25 log: a fresh ~/.zshrc backup per
# run. Apply the edits to a staging copy and touch the real profile only when the
# result differs.
sync_profile_block() {
    local raw_profile="$1" real_profile staging rc=0
    real_profile="$(resolve_target_file "$raw_profile")"
    staging="$(mktemp "${TMPDIR:-/tmp}/mac_update_profile_stage.XXXXXX")" || return 1
    if [ -f "$real_profile" ]; then
        cat "$real_profile" > "$staging" || { rm -f "$staging"; return 1; }
    fi
    _MACUPD_PROFILE_STAGING=1
    apply_profile_block "$staging" || rc=$?
    _MACUPD_PROFILE_STAGING=0
    if [ "$rc" -eq 0 ] && ! cmp -s "$staging" "$real_profile" 2>/dev/null; then
        declare_profile_backup "$raw_profile"
        cat "$staging" > "$real_profile" || rc=1
    fi
    rm -f "$staging"
    return "$rc"
}

apply_profile_block() {
    local profile="$1"
    remove_line_from_file "$profile" "# Managed by macOS Updates — native CLI toolchain" || return 1
    remove_line_from_file "$profile" "export N_PREFIX=\"$N_PREFIX\"" || return 1
    remove_line_from_file "$profile" "export PATH=\"$NPM_GLOBAL_BIN:$N_PREFIX/bin:$BUN_BIN:\$PATH\"" || return 1
    remove_line_from_file "$profile" "export PATH=\"$LOCAL_BIN:$NPM_GLOBAL_BIN:$N_PREFIX/bin:$BUN_BIN:\$PATH\"" || return 1
    remove_line_from_file "$profile" "# Managed by macOS Updates — Bun only (nvm owns Node/npm)" || return 1
    remove_line_from_file "$profile" "export BUN_INSTALL=\"$BUN_HOME\"" || return 1
    remove_line_from_file "$profile" "export PATH=\"$BUN_BIN:\$PATH\"" || return 1
    remove_line_from_file "$profile" "export PATH=\"$LOCAL_BIN:$BUN_BIN:\$PATH\"" || return 1
    remove_line_from_file "$profile" "[ -n \"\$NVM_BIN\" ] && export PATH=\"\$NVM_BIN:\$PATH\"" || return 1
    ensure_line_in_file "$profile" "" || return 1

    # Opt-in escape hatch. Historically this branch was taken automatically
    # whenever ~/.nvm/nvm.sh existed, which produced a split-brain toolchain:
    # the interactive shell resolved node/npm/claude/codex from the nvm prefix
    # while this script kept updating a parallel copy under
    # ~/.local/share/mac-update that nothing on PATH pointed at. On the
    # 2026-08-19 machine that meant node v24.13.0 in the terminal against
    # v26.7.0 "successfully updated", and the same gap for npm, pnpm, codex and
    # opencode. The managed prefix now wins by default; set
    # MAC_UPDATE_NVM_OWNS_NODE=1 to hand Node/npm back to nvm deliberately.
    if [ "${MAC_UPDATE_NVM_OWNS_NODE:-0}" = "1" ] && [ -s "$HOME/.nvm/nvm.sh" ]; then
        ensure_line_in_file "$profile" "# Managed by macOS Updates — Bun only (nvm owns Node/npm)" || return 1
        ensure_line_in_file "$profile" "export BUN_INSTALL=\"$BUN_HOME\"" || return 1
        ensure_line_in_file "$profile" "export PATH=\"$LOCAL_BIN:$BUN_BIN:\$PATH\"" || return 1
        if [ -n "$NVM_BIN" ]; then
            ensure_line_in_file "$profile" "[ -n \"\$NVM_BIN\" ] && export PATH=\"\$NVM_BIN:\$PATH\"" || return 1
        fi
        return 0
    fi
    ensure_line_in_file "$profile" "# Managed by macOS Updates — native CLI toolchain" || return 1
    ensure_line_in_file "$profile" "export N_PREFIX=\"$N_PREFIX\"" || return 1
    ensure_line_in_file "$profile" "export BUN_INSTALL=\"$BUN_HOME\"" || return 1
    ensure_line_in_file "$profile" "export PATH=\"$LOCAL_BIN:$NPM_GLOBAL_BIN:$N_PREFIX/bin:$BUN_BIN:\$PATH\"" || return 1
}

normalize_semver() {
    printf '%s' "$1" | sed 's/^v//; s/ .*//'
}

semver_is_newer() {
    awk -v lhs="$(normalize_semver "$1")" -v rhs="$(normalize_semver "$2")" '
        BEGIN {
            sub(/[-+].*$/, "", lhs)
            sub(/[-+].*$/, "", rhs)
            lhs_n = split(lhs, lhs_parts, ".")
            rhs_n = split(rhs, rhs_parts, ".")
            max_n = lhs_n > rhs_n ? lhs_n : rhs_n
            for (i = 1; i <= max_n; i++) {
                left = lhs_parts[i] + 0
                right = rhs_parts[i] + 0
                if (left > right) exit 0
                if (left < right) exit 1
            }
            exit 1
        }
    '
}

detect_command_version() {
    local display_name="$1"
    local command_path="$2"
    local version=""

    case "$display_name" in
        node)
            version="$("$command_path" -v </dev/null 2>/dev/null | head -1)"
            ;;
        npm|pnpm|opencode-cli|bun)
            version="$("$command_path" --version </dev/null 2>/dev/null | head -1)"
            ;;
        claude-code)
            version="$("$command_path" -v </dev/null 2>/dev/null | head -1)"
            version="$(printf '%s' "$version" | sed 's/ .*//')"
            ;;
        codex-cli)
            version="$("$command_path" --version </dev/null 2>/dev/null | head -1 | awk '{print $NF}')"
            ;;
        agy-cli)
            version="$("$command_path" --version </dev/null 2>/dev/null | head -1)"
            ;;
        cursor-agent)
            version="$("$command_path" --version </dev/null 2>/dev/null | head -1)"
            ;;
        *)
            version="$("$command_path" --version </dev/null 2>/dev/null | head -1 | awk '{print $NF}')"
            ;;
    esac

    # A tool may print its name before the version ("opencode v2.3.2"): keep the
    # version token only; when there is none the version is unknown, never a name.
    case "$version" in
        ""|"?") ;;
        v[0-9]*|[0-9]*) ;;
        *) version="$(printf '%s' "$version" | tr ' ' '\n' | sed -n 's/^v\{0,1\}\([0-9][0-9]*\.[0-9][0-9.A-Za-z+-]*\)$/\1/p' | head -n 1)" ;;
    esac
    normalize_semver "${version:-?}"
}

resolve_command_path() {
    local command_name="$1"

    case "$command_name" in
        node|npx)
            if [ -x "$N_PREFIX/bin/$command_name" ]; then
                echo "$N_PREFIX/bin/$command_name"
                return 0
            fi
            ;;
        claude)
            # Claude Code uses a standalone native installer
            # (curl -fsSL https://claude.ai/install.sh | sh) that places
            # the binary at ~/.local/bin/claude. No npm-global fallback.
            if [ -x "$LOCAL_BIN/claude" ]; then
                echo "$LOCAL_BIN/claude"
                return 0
            fi
            ;;
        opencode)
            if [ -x "$LOCAL_BIN/opencode" ]; then
                echo "$LOCAL_BIN/opencode"
                return 0
            fi
            if [ -x "$NPM_GLOBAL_BIN/opencode" ]; then
                echo "$NPM_GLOBAL_BIN/opencode"
                return 0
            fi
            if [ -x "$HOME/.opencode/bin/opencode" ]; then
                echo "$HOME/.opencode/bin/opencode"
                return 0
            fi
            ;;
        npm|pnpm)
            if [ -x "$NPM_GLOBAL_BIN/$command_name" ]; then
                echo "$NPM_GLOBAL_BIN/$command_name"
                return 0
            fi
            ;;
        bun)
            if [ -x "$BUN_BIN/bun" ]; then
                echo "$BUN_BIN/bun"
                return 0
            fi
            ;;
        codex|agy|agent)
            # Standalone native binaries installed by vendor scripts
            if [ -x "$LOCAL_BIN/$command_name" ]; then
                echo "$LOCAL_BIN/$command_name"
                return 0
            fi
            ;;
    esac

    if command -v "$command_name" >/dev/null 2>&1; then
        command -v "$command_name"
        return 0
    fi

    return 1
}

. "$SCRIPT_DIR/lib/proc.sh"
# Per-vendor bootstrap/update contracts (H4/H5/M1).
# shellcheck source=lib/native_installers.sh
. "$SCRIPT_DIR/lib/native_installers.sh"

write_cli_snapshot() {
    local outfile="$1"
    : > "$outfile" || return 1

    while IFS='|' read -r display_name package_name method _brew_formula command_name; do
        local command_path
        local version

        case "$display_name" in
            ""|\#*) continue ;;
        esac

        if command_path="$(resolve_command_path "$command_name")"; then
            version="$(detect_command_version "$display_name" "$command_path")"
            if ! printf '%s|%s|%s|%s|%s\n' \
                "$display_name" \
                "$package_name" \
                "${version:-?}" \
                "$command_name" \
                "$command_path" >> "$outfile"; then
                return 1
            fi
        fi
    done < "$MANIFEST_PATH"
    return 0
}

detect_latest_node_version() {
    local json_body ver
    json_body="$(curl -fsSL --proto '=https' --proto-redir '=https' --tlsv1.2 --max-time 60 --retry 3 --retry-delay 2 https://nodejs.org/dist/index.json 2>/dev/null)"
    if [ -n "$json_body" ]; then
        # Newest *stable* release: the index can lead with an alpha/rc build.
        ver="$(echo "$json_body" | PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c 'import json,sys
from node_releases import latest_stable_node
print(latest_stable_node(json.load(sys.stdin)) or "")' 2>/dev/null)"
        if [ -z "$ver" ]; then
            ver="$(echo "$json_body" | tr '{' '\n' | grep -oE '"version":"v[0-9]+\.[0-9]+\.[0-9]+"' | head -1 | cut -d'"' -f4)"
        fi
        if [ -n "$ver" ]; then
            echo "$ver"
            return 0
        fi
    fi
    SOFT_FAIL=1
    return 1
}

install_node_tarball() {
    local latest_node="$1"
    local archive_arch
    local archive_name
    local archive_url
    local shasums_url
    local tmpdir
    local extracted_dir
    local staging_dir
    local backup_dir

    if [ -z "$latest_node" ]; then
        print_error "$L_NPM_NODE_LATEST_VERSION_FAILED"
        return 1
    fi

    case "$(uname -m)" in
        arm64)  archive_arch="arm64" ;;
        x86_64) archive_arch="x64" ;;
        *)
            print_error "$(printf "$L_NPM_NODE_UNSUPPORTED_ARCH" "$(uname -m)")"
            return 1
            ;;
    esac

    archive_name="node-${latest_node}-darwin-${archive_arch}.tar.gz"
    archive_url="https://nodejs.org/dist/${latest_node}/${archive_name}"
    shasums_url="https://nodejs.org/dist/${latest_node}/SHASUMS256.txt"
    tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/mac_update_node.XXXXXX")" || return 1

    print_info "$L_NPM_NODE_BOOTSTRAPPING"
    if ! curl -fsSL --proto '=https' --proto-redir '=https' --tlsv1.2 --max-time 180 --retry 3 --retry-delay 2 -o "$tmpdir/$archive_name" "$archive_url"; then
        rm -rf "$tmpdir"
        return 1
    fi

    if ! curl -fsSL --proto '=https' --proto-redir '=https' --tlsv1.2 --max-time 60 --retry 3 --retry-delay 2 -o "$tmpdir/SHASUMS256.txt" "$shasums_url"; then
        rm -rf "$tmpdir"
        return 1
    fi
    if ! grep "  ${archive_name}\$" "$tmpdir/SHASUMS256.txt" > "$tmpdir/node.sha256"; then
        rm -rf "$tmpdir"
        return 1
    fi
    if ! (cd "$tmpdir" && shasum -a 256 -c node.sha256 >/dev/null 2>&1); then
        print_error "$(printf "$L_NPM_NODE_CHECKSUM_MISMATCH" "$archive_name")"
        rm -rf "$tmpdir"
        return 1
    fi

    if ! tar -xzf "$tmpdir/$archive_name" -C "$tmpdir"; then
        rm -rf "$tmpdir"
        return 1
    fi

    extracted_dir="$tmpdir/node-${latest_node}-darwin-${archive_arch}"
    mkdir -p "$N_PREFIX"
    staging_dir="$(mktemp -d "$TOOLCHAIN_HOME/node.staging.XXXXXX")" || {
        rm -rf "$tmpdir"
        return 1
    }
    if ! cp -R "$extracted_dir"/. "$staging_dir"/; then
        rm -rf "$tmpdir" "$staging_dir"
        return 1
    fi
    backup_dir="$TOOLCHAIN_HOME/node.backup.$(date +%Y%m%d%H%M%S).$$"
    if [ -d "$N_PREFIX" ]; then
        if ! mv "$N_PREFIX" "$backup_dir"; then
            rm -rf "$tmpdir" "$staging_dir"
            return 1
        fi
    fi
    if ! mv "$staging_dir" "$N_PREFIX"; then
        [ -d "$backup_dir" ] && mv "$backup_dir" "$N_PREFIX" 2>/dev/null || true
        rm -rf "$tmpdir" "$staging_dir"
        return 1
    fi
    rm -rf "$backup_dir" 2>/dev/null || true
    rm -rf "$tmpdir"
    export PATH="$NPM_GLOBAL_BIN:$N_PREFIX/bin:$BUN_BIN:$PATH"
    hash -r 2>/dev/null || true
}

bootstrap_npm() {
    if [ -x "$N_PREFIX/bin/npm" ]; then
        echo "$N_PREFIX/bin/npm"
    elif [ -x "$NPM_GLOBAL_BIN/npm" ]; then
        echo "$NPM_GLOBAL_BIN/npm"
    elif command -v npm >/dev/null 2>&1; then
        command -v npm
    else
        echo ""
    fi
}

ensure_n_helper() {
    local npm_bin
    npm_bin="$(bootstrap_npm)"
    if [ -z "$npm_bin" ]; then
        print_error "$L_NPM_NODE_NO_NPM_BOOTSTRAP"
        return 1
    fi

    run_quiet_with_error_log \
        "npm install n@latest" \
        "$npm_bin" install -g --prefix "$NPM_GLOBAL_PREFIX" n@latest
}

ensure_latest_node() {
    local latest_node
    local current_node=""
    local n_bin="$NPM_GLOBAL_BIN/n"

    if [ ! -x "$N_PREFIX/bin/node" ] && [ "${MAC_UPDATE_BOOTSTRAP_CLI:-0}" != "1" ]; then
        print_info "$L_NPM_TOOLCHAIN_NOT_INSTALLED"
        cli_skip_item node node "not installed" native
        return 2
    fi

    latest_node="$(detect_latest_node_version)"
    if [ -z "$latest_node" ]; then
        cli_skip_item node node "latest Node.js version could not be determined" native
        SOFT_FAIL=1
        return 0
    fi
    current_node=""
    if [ -x "$N_PREFIX/bin/node" ]; then
        current_node="$("$N_PREFIX/bin/node" -v 2>/dev/null || true)"
    elif [ -x "$HOME/n/bin/node" ]; then
        current_node="$("$HOME/n/bin/node" -v 2>/dev/null || true)"
    elif command -v node >/dev/null 2>&1; then
        current_node="$(node -v 2>/dev/null || true)"
    else
        print_warn "No node executable found in $N_PREFIX/bin, $HOME/n/bin, or PATH"
    fi

    if ! ensure_n_helper; then
        if ! install_node_tarball "$latest_node"; then
            print_error "$L_NPM_NODE_BOOTSTRAP_FAILED"
            return 1
        fi
        if ! ensure_n_helper; then
            return 1
        fi
    fi

    if [ ! -x "$N_PREFIX/bin/node" ] && [ ! -x "$HOME/n/bin/node" ] || [ "$(normalize_semver "$current_node")" != "$(normalize_semver "$latest_node")" ]; then
        # skip/manual keep the installed Node; npm packages still use it.
        cli_override_gate node node node "$(normalize_semver "$current_node")" node || return 0
        mu_item_start cli node node "$(normalize_semver "$current_node")" "$(normalize_semver "$latest_node")" native
        mu_item_progress cli node installing
        print_info "$(printf "$L_NPM_NODE_UPDATING_VIA_N" "${latest_node:-latest}")"
        # Install the exact stable version detected above; `n latest` follows the
        # index head and installed v27.0.0-alpha on 2026-10-29.
        if N_PREFIX="$N_PREFIX" "$n_bin" "${latest_node#v}"; then
            export PATH="$LOCAL_BIN:$NPM_GLOBAL_BIN:$N_PREFIX/bin:$HOME/n/bin:$BUN_BIN:$PATH"
            hash -r 2>/dev/null || true
            local active_node=""
            if [ -x "$N_PREFIX/bin/node" ]; then
                active_node="$("$N_PREFIX/bin/node" -v 2>/dev/null || true)"
            elif [ -x "$HOME/n/bin/node" ]; then
                active_node="$("$HOME/n/bin/node" -v 2>/dev/null || true)"
            else
                print_warn "Neither $N_PREFIX/bin/node nor $HOME/n/bin/node exists after n update"
            fi
            cli_item_result node "$(normalize_semver "$current_node")" "$(normalize_semver "${active_node:-?}")" 0
            print_ok "Node.js active: $active_node"
        else
            cli_item_result node "$(normalize_semver "$current_node")" "" 1
            print_error "$L_NPM_NODE_UPDATE_N_FAILED"
            return 1
        fi
    else
        cli_end node current "$(normalize_semver "$current_node")" "$(normalize_semver "$current_node")" "" "" node
        print_ok "$(printf "$L_NPM_NODE_ALREADY_CURRENT" "$(normalize_semver "$current_node")")"
    fi
}

read_bun_version() {
    local ver
    if [ -f "$BUN_VERSION_PATH" ]; then
        ver="$(grep -v '^[[:space:]]*#' "$BUN_VERSION_PATH" | grep -v '^[[:space:]]*$' | head -1 | tr -d ' \r\n')"
        if [ -n "$ver" ]; then
            echo "$ver"
            return 0
        fi
    fi
    return 1
}

detect_latest_bun_version() {
    local tag latest min_floor
    tag="$(github_latest_tag "oven-sh/bun")" # oven-sh/bun releases/latest
    if [ -n "$tag" ] && [ "$tag" != "?" ]; then
        latest="$(echo "$tag" | sed 's/^bun-v//; s/^v//')"
    fi
    min_floor="$(read_bun_version 2>/dev/null || echo "")"
    if [ -z "$latest" ]; then
        latest="$min_floor"
    elif [ -n "$min_floor" ] && semver_is_newer "$min_floor" "$latest"; then
        latest="$min_floor"
    fi
    echo "$latest"
}

install_bun_tarball() {
    local bun_version="$1"
    local archive_arch archive_name tag archive_url shasums_url tmpdir
    local bun_binary staging_bin backup_bin installed_version

    case "$(uname -m)" in
        arm64)  archive_arch="aarch64" ;;
        x86_64) archive_arch="x64" ;;
        *)
            print_error "$(printf "$L_NPM_BUN_UNSUPPORTED_ARCH" "$(uname -m)")"
            return 1
            ;;
    esac

    tag="bun-v${bun_version}"
    archive_name="bun-darwin-${archive_arch}.zip"
    archive_url="https://github.com/oven-sh/bun/releases/download/${tag}/${archive_name}"
    shasums_url="https://github.com/oven-sh/bun/releases/download/${tag}/SHASUMS256.txt"
    tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/mac_update_bun.XXXXXX")" || return 1

    print_info "$(printf "$L_NPM_BUN_INSTALLING" "${bun_version}")"
    if ! curl -fsSL --proto '=https' --proto-redir '=https' --tlsv1.2 --max-time 180 --retry 3 --retry-delay 2 -o "$tmpdir/$archive_name" "$archive_url"; then
        rm -rf "$tmpdir"
        SOFT_FAIL=1
        return 1
    fi
    if ! curl -fsSL --proto '=https' --proto-redir '=https' --tlsv1.2 --max-time 60 --retry 3 --retry-delay 2 -o "$tmpdir/SHASUMS256.txt" "$shasums_url"; then
        rm -rf "$tmpdir"
        SOFT_FAIL=1
        return 1
    fi
    if ! grep -E "[[:space:]]+(\./)?${archive_name}\$" "$tmpdir/SHASUMS256.txt" | awk '{print $1 "  " "'"$archive_name"'"}' > "$tmpdir/bun.sha256" || [ ! -s "$tmpdir/bun.sha256" ]; then
        print_warn "$(printf "$L_NPM_BUN_CHECKSUM_NOT_FOUND" "$archive_name")"
        rm -rf "$tmpdir"
        SOFT_FAIL=1
        return 1
    fi
    if ! (cd "$tmpdir" && shasum -a 256 -c bun.sha256 >/dev/null 2>&1); then
        print_error "$(printf "$L_NPM_BUN_CHECKSUM_MISMATCH" "$archive_name")"
        rm -rf "$tmpdir"
        HARD_FAIL=1
        return 1
    fi
    if ! unzip -q -o "$tmpdir/$archive_name" -d "$tmpdir"; then
        rm -rf "$tmpdir"
        HARD_FAIL=1
        return 1
    fi
    bun_binary="$tmpdir/bun-darwin-${archive_arch}/bun"
    if [ ! -f "$bun_binary" ]; then
        rm -rf "$tmpdir"
        HARD_FAIL=1
        return 1
    fi
    chmod +x "$bun_binary" 2>/dev/null || true

    mkdir -p "$BUN_BIN"
    staging_bin="$(mktemp "${TMPDIR:-/tmp}/mac_update_bun_bin.XXXXXX")" || {
        rm -rf "$tmpdir"
        HARD_FAIL=1
        return 1
    }
    if ! cp "$bun_binary" "$staging_bin"; then
        rm -rf "$tmpdir" "$staging_bin"
        HARD_FAIL=1
        return 1
    fi
    chmod +x "$staging_bin"
    backup_bin="$BUN_BIN/bun.backup.$(date +%Y%m%d%H%M%S).$$"
    if [ -f "$BUN_BIN/bun" ]; then
        if ! mv "$BUN_BIN/bun" "$backup_bin" 2>/dev/null; then
            rm -rf "$tmpdir"
            rm -f "$staging_bin" 2>/dev/null || true
            HARD_FAIL=1
            return 1
        fi
    fi
    if ! mv "$staging_bin" "$BUN_BIN/bun"; then
        [ -f "$backup_bin" ] && mv "$backup_bin" "$BUN_BIN/bun" 2>/dev/null || true
        rm -rf "$tmpdir"
        HARD_FAIL=1
        return 1
    fi
    installed_version="$(normalize_semver "$("$BUN_BIN/bun" --version 2>/dev/null || echo '?')")"
    if [ "$installed_version" != "$(normalize_semver "$bun_version")" ]; then
        print_error "$(printf "$L_NPM_BUN_VERIFY_FAILED" "$bun_version" "$installed_version")"
        rm -f "$BUN_BIN/bun" 2>/dev/null || true
        [ -f "$backup_bin" ] && mv "$backup_bin" "$BUN_BIN/bun" 2>/dev/null || true
        rm -rf "$tmpdir"
        HARD_FAIL=1
        return 1
    fi
    rm -f "$backup_bin" 2>/dev/null || true
    rm -rf "$tmpdir"
    return 0
}

ensure_latest_bun() {
    local target_ver
    local current=""
    local floor_ver

    if [ ! -x "$BUN_BIN/bun" ] && [ "${MAC_UPDATE_BOOTSTRAP_CLI:-0}" != "1" ]; then
        print_info "$(printf "$L_NPM_CLI_NOT_INSTALLED" "bun")"
        cli_skip_item bun bun "not installed" native
        return 0
    fi

    export BUN_INSTALL="$BUN_HOME"
    mkdir -p "$BUN_HOME" "$BUN_BIN" || return 1

    target_ver="$(detect_latest_bun_version)"
    if [ -z "$target_ver" ]; then
        print_warn "Could not resolve latest Bun version and no floor version available"
        cli_skip_item bun bun "latest Bun version could not be determined" native
        SOFT_FAIL=1
        return 0
    fi

    if [ -x "$BUN_BIN/bun" ]; then
        current="$(normalize_semver "$("$BUN_BIN/bun" --version 2>/dev/null || echo '?')")"
        cli_override_gate bun bun bun "$current" bun || return 0
        mu_item_start cli bun bun "$current" "$target_ver" native
        mu_item_progress cli bun installing
        print_info "$L_NPM_BUN_UPDATING_NATIVELY"
        if run_quiet_with_error_log "bun upgrade" "$BUN_BIN/bun" upgrade; then
            cli_item_result bun "$current" "$(normalize_semver "$("$BUN_BIN/bun" --version 2>/dev/null || echo '?')")" 0
            print_ok "$(printf "$L_NPM_BUN_ACTIVE" "$("$BUN_BIN/bun" --version 2>/dev/null)")"
        else
            print_warn "$L_NPM_BUN_UPGRADE_WARN"
            if semver_is_newer "$target_ver" "$current"; then
                if ! install_bun_tarball "$target_ver"; then
                    cli_item_result bun "$current" "" 1
                    return 1
                fi
                cli_item_result bun "$current" "$(normalize_semver "$("$BUN_BIN/bun" --version 2>/dev/null || echo '?')")" 0
                print_ok "$(printf "$L_NPM_BUN_ACTIVE" "$("$BUN_BIN/bun" --version 2>/dev/null)")"
            else
                cli_end bun current "$current" "$target_ver" "bun upgrade failed; installed version is not older" "" bun
                print_ok "$(printf "$L_NPM_BUN_NOT_OLDER_THAN_FALLBACK" "$current" "$target_ver")"
            fi
        fi
    else
        CLI_EVENT_ID=bun
        CLI_EVENT_NAME=bun
        mu_item_start cli bun bun "" "$target_ver" native
        mu_item_progress cli bun installing
        if install_bun_tarball "$target_ver"; then
            cli_item_result bun "" "$(normalize_semver "$("$BUN_BIN/bun" --version 2>/dev/null || echo '?')")" 0
            print_ok "$(printf "$L_NPM_BUN_ACTIVE" "$("$BUN_BIN/bun" --version 2>/dev/null)")"
        elif [ "${HARD_FAIL:-0}" -ne 0 ]; then
            cli_item_result bun "" "" 1
            print_error "$L_NPM_BUN_INSTALL_FAILED"
            return 1
        else
            cli_item_result bun "" "" 1
        fi
    fi

    export PATH="$LOCAL_BIN:$NPM_GLOBAL_BIN:$N_PREFIX/bin:$BUN_BIN:$PATH"
    hash -r 2>/dev/null || true
}

# Vendor contracts live in lib/native_installers.sh (CODEX_NON_INTERACTIVE=1,
# per-vendor bootstrap args, download-then-exec). Do not pipe curl into sh.
install_native_cli() {
    local display_name="$1"
    local command_name="$2"
    local install_url installer_env bootstrap_args existing_cmd installer_tmp command_path verified=""

    install_url="$(native_installer_url "$command_name")"
    if [ -z "$install_url" ]; then
        print_warn "${display_name}: native-installer method not implemented for ${command_name}"
        cli_skip_item "$command_name" "$display_name" "native-installer method not implemented" native
        return 1
    fi
    installer_env="$(native_installer_env "$command_name")"
    bootstrap_args="$(native_installer_bootstrap_args "$command_name")"
    existing_cmd="$(native_installer_existing_update_cmd "$command_name")"

    if [ ! -x "$LOCAL_BIN/$command_name" ] && [ "${MAC_UPDATE_BOOTSTRAP_CLI:-0}" != "1" ]; then
        print_info "$(printf "$L_NPM_CLI_NOT_INSTALLED" "${display_name}")"
        cli_skip_item "$command_name" "$display_name" "not installed" native
        return 0
    fi
    local _cli_before=""
    [ -x "$LOCAL_BIN/$command_name" ] && _cli_before="$(detect_command_version "$display_name" "$LOCAL_BIN/$command_name")"
    [ "$_cli_before" = "?" ] && _cli_before=""
    cli_override_gate "$display_name" "$display_name" "$command_name" "$_cli_before" "$command_name" || return 0
    mu_item_start cli "$command_name" "$display_name" "$_cli_before" "" native
    mu_item_progress cli "$command_name" installing

    if [ -n "$existing_cmd" ] && [ -x "$LOCAL_BIN/$command_name" ]; then
        print_info "$(printf "$L_NPM_UPDATING_VIA_SELF_UPDATE" "${display_name}" "native installer")"
        # shellcheck disable=SC2086
        if run_quiet_with_error_log \
            "${command_name} ${existing_cmd}" \
            run_with_timeout "$(native_installer_timeout)" \
            env $installer_env "$LOCAL_BIN/$command_name" $existing_cmd \
            && verified="$(report_cli_version_or_fail "$display_name" "$LOCAL_BIN/$command_name")"; then
            cli_item_result "$display_name" "$_cli_before" "$(detect_command_version "$display_name" "$LOCAL_BIN/$command_name")" 0
            print_ok "${display_name}: ${verified}"
            return 0
        fi
        print_warn "$(printf "$L_NPM_PACKAGE_UPDATE_FAILED" "${display_name}")"
    else
        print_info "$(printf "$L_NPM_UPDATING_VIA_SELF_UPDATE" "${display_name}" "native installer")"
    fi

    installer_tmp="$(mktemp "${TMPDIR:-/tmp}/mac-update-installer.XXXXXX")" || return 1
    if ! download_installer_script "$install_url" "$installer_tmp"; then
        rm -f "$installer_tmp"
        cli_item_result "$display_name" "$_cli_before" "" 1
        print_warn "$(printf "$L_NPM_PACKAGE_UPDATE_FAILED" "${display_name}")"
        return 1
    fi
    # shellcheck disable=SC2086
    if run_quiet_with_error_log \
        "${command_name} native installer" \
        run_with_timeout "$(native_installer_timeout)" \
        env $installer_env /bin/sh "$installer_tmp" $bootstrap_args
    then
        command_path="$LOCAL_BIN/$command_name"
        if [ ! -x "$command_path" ]; then
            command_path="$(resolve_command_path "$command_name" 2>/dev/null || true)"
        fi
        if [ -n "$command_path" ] && verified="$(report_cli_version_or_fail "$display_name" "$command_path")"; then
            cli_item_result "$display_name" "$_cli_before" "$(detect_command_version "$display_name" "$command_path")" 0
            print_ok "${display_name}: ${verified}"
            rm -f "$installer_tmp"
            return 0
        fi
    fi
    rm -f "$installer_tmp"
    cli_item_result "$display_name" "$_cli_before" "" 1
    print_warn "$(printf "$L_NPM_PACKAGE_UPDATE_FAILED" "${display_name}")"
    return 1
}

install_latest_npm_packages() {
    local active_npm="$N_PREFIX/bin/npm"
    local display_name
    local package_name
    local method
    local _brew_formula
    local command_name
    local command_path
    local package_spec
    local failures=0

    if [ ! -x "$active_npm" ]; then
        active_npm="$(bootstrap_npm)"
    fi

    if [ -z "$active_npm" ]; then
        print_error "$L_NPM_NO_NPM_AFTER_NODE"
        return 1
    fi

    while IFS='|' read -r display_name package_name method _brew_formula command_name; do
        case "$display_name" in
            ""|\#*) continue ;;
        esac

        if [ "$method" = "npm" ]; then
            if [ "$package_name" = "npm" ]; then
                if [ ! -x "$N_PREFIX/bin/node" ] && [ "${MAC_UPDATE_BOOTSTRAP_CLI:-0}" != "1" ]; then
                    print_info "$(printf "$L_NPM_CLI_NOT_INSTALLED" "${display_name}")"
                    cli_skip_item "$package_name" "$display_name" "not installed" npm
                    continue
                fi
            else
                if [ ! -d "$NPM_GLOBAL_PREFIX/lib/node_modules/$package_name" ] && [ ! -x "$NPM_GLOBAL_BIN/$command_name" ] && [ "${MAC_UPDATE_BOOTSTRAP_CLI:-0}" != "1" ]; then
                    print_info "$(printf "$L_NPM_CLI_NOT_INSTALLED" "${display_name}")"
                    cli_skip_item "$package_name" "$display_name" "not installed" npm
                    continue
                fi
            fi
            package_spec="${package_name}@latest"
            _cli_before="$(detect_command_version "$display_name" "$NPM_GLOBAL_BIN/$command_name")"
            [ "$_cli_before" = "?" ] && _cli_before=""
            npm_latest_version() { run_with_timeout 30 "$active_npm" view "$package_name" version </dev/null; }
            cli_override_gate "$display_name" "$package_name" "$command_name" "$_cli_before" "$package_name" npm_latest_version || continue
            mu_item_start cli "$package_name" "$display_name" "$_cli_before" "" npm
            mu_item_progress cli "$package_name" installing
            print_info "$(printf "$L_NPM_UPDATING_PACKAGE_VIA_NPM" "${display_name}" "${package_spec}")"
            _cli_rc=0
            run_quiet_with_error_log \
                "npm install ${package_spec}" \
                "$active_npm" install -g --prefix "$NPM_GLOBAL_PREFIX" "$package_spec" || _cli_rc=$?
            _cli_after="$(detect_command_version "$display_name" "$NPM_GLOBAL_BIN/$command_name")"
            # npm itself lives in the Node prefix, not in the global bin.
            if [ "$package_name" = "npm" ] && [ "$_cli_after" = "?" ]; then
                _cli_after="$(detect_command_version npm "$N_PREFIX/bin/npm")"
            fi
            cli_item_result "$display_name" "$_cli_before" "$_cli_after" "$_cli_rc"
            if [ "$_cli_rc" -eq 0 ]; then
                print_ok "${display_name}: ${_cli_after}"
            else
                print_warn "$(printf "$L_NPM_PACKAGE_UPDATE_FAILED" "${display_name}")"
                failures=$((failures + 1))
            fi
        elif [ "$method" = "self-update" ]; then
            # Native OpenCode was already checked before Node/npm. Keep the
            # existing npm distribution only as a fallback if that attempt failed.
            if [ "$command_name" = "opencode" ] && [ "${OPENCODE_NATIVE_OK:-0}" = "1" ]; then
                continue
            fi
            command_path=""
            if [ "$command_name" = "opencode" ]; then
                # The native attempt may have left an older or broken binary.
                # npm fallback must update an existing npm wrapper, never the
                # native command and never bootstrap another distribution.
                if [ -d "$NPM_GLOBAL_PREFIX/lib/node_modules/opencode-ai" ] && [ -x "$NPM_GLOBAL_BIN/opencode" ]; then
                    command_path="$NPM_GLOBAL_BIN/opencode"
                fi
            else
                command_path="$(resolve_command_path "$command_name" 2>/dev/null || true)"
            fi
            if [ -n "$command_path" ]; then
                _cli_before="$(detect_command_version "$display_name" "$command_path")"
                [ "$_cli_before" = "?" ] && _cli_before=""
                cli_override_gate "$display_name" "$package_name" "$command_name" "$_cli_before" "$command_name" || continue
                mu_item_start cli "$command_name" "$display_name" "$_cli_before" "" self-update
                mu_item_progress cli "$command_name" installing
                print_info "$(printf "$L_NPM_UPDATING_VIA_SELF_UPDATE" "${display_name}" "${command_name}")"
                # Some vendor self-updaters may shell out to
                # `npm install -g` internally. Pin the prefix and the
                # PATH for the child only (subshell), so the managed prefix is
                # the one that actually gets upgraded.
                #
                # opencode uses `upgrade --method npm` rather than `update`; the
                # --method flag keeps it inside the managed npm prefix instead of
                # falling back to curl/brew.
                local _self_update_cmd="update"
                local _self_update_args=""
                local _update_ok=0
                local _verified=""
                local _repair_rc=0
                if [ "$command_name" = "opencode" ]; then
                    _self_update_cmd="upgrade"
                    _self_update_args="--method npm"
                fi
                if ( export npm_config_prefix="$NPM_GLOBAL_PREFIX"
                     export NPM_CONFIG_PREFIX="$NPM_GLOBAL_PREFIX"
                     export PATH="$LOCAL_BIN:$NPM_GLOBAL_BIN:$N_PREFIX/bin:$PATH"
                     if [ "$command_name" = "opencode" ]; then
                         export NPM_CONFIG_ALLOW_SCRIPTS="opencode-ai"
                     fi
                     run_quiet_with_error_log \
                        "${command_name} ${_self_update_cmd}" \
                        run_with_timeout 300 "$command_path" "$_self_update_cmd" $_self_update_args ); then
                    _update_ok=1
                fi
                if [ "$command_name" != "opencode" ]; then
                    command_path="$(resolve_command_path "$command_name" 2>/dev/null || printf '%s' "$command_path")"
                fi
                if ! _verified="$(report_cli_version_or_fail "$display_name" "$command_path")"; then
                    _verified=""
                    if [ "$command_name" = "opencode" ]; then
                        _repair_rc=0
                        repair_broken_opencode "$NPM_GLOBAL_PREFIX" "$command_path" || _repair_rc=$?
                        if [ "$_repair_rc" -eq 2 ]; then
                            print_info "$(printf "$L_NPM_CLI_NOT_INSTALLED" "${display_name}")"
                            cli_skip_item "$command_name" "$display_name" "not installed" self-update
                            continue
                        fi
                        if [ "$_repair_rc" -eq 0 ] && _verified="$(report_cli_version_or_fail "$display_name" "$command_path")"; then
                            _update_ok=1
                        else
                            _verified=""
                        fi
                    fi
                fi
                if [ "$_update_ok" -eq 1 ] && [ -n "$_verified" ]; then
                    cli_item_result "$display_name" "$_cli_before" "$(detect_command_version "$display_name" "$command_path")" 0
                    print_ok "${display_name}: ${_verified}"
                else
                    cli_item_result "$display_name" "$_cli_before" "" 1
                    print_warn "$(printf "$L_NPM_PACKAGE_UPDATE_FAILED" "${display_name}")"
                    failures=$((failures + 1))
                fi
            else
                print_info "$(printf "$L_NPM_CLI_NOT_INSTALLED" "${display_name}")"
                cli_skip_item "$command_name" "$display_name" "not installed" self-update
            fi
        fi
    done < "$MANIFEST_PATH"

    export PATH="$LOCAL_BIN:$NPM_GLOBAL_BIN:$N_PREFIX/bin:$BUN_BIN:$PATH"
    hash -r 2>/dev/null || true

    if [ "$failures" -ne 0 ]; then
        print_warn "$(printf "$L_NPM_FAILURES_SUMMARY" "$failures")"
        if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -f "$MAC_UPDATE_SESSION_DIR/npm_cli_errors.log" ]; then
            print_info "$(printf "$L_NPM_DIAGNOSTICS_PATH_FMT" "$MAC_UPDATE_SESSION_DIR/npm_cli_errors.log")"
        fi
        SOFT_FAIL=1
        return 1
    fi
    return 0
}

# Prefer the vendor standalone distribution before invoking any npm updater.
# The live vendor installer uses ~/.opencode/bin (its README currently advertises
# an install-dir override that the script does not implement).
update_opencode_native_first() {
    local old_path old_version="" native_path native_version installer_tmp
    OPENCODE_NATIVE_OK=0
    grep -q '^opencode-cli|' "$MANIFEST_PATH" || return 0
    old_path="$(resolve_command_path opencode 2>/dev/null || true)"
    if [ -z "$old_path" ] && [ "${MAC_UPDATE_BOOTSTRAP_CLI:-0}" != "1" ]; then
        return 0
    fi
    if [ -n "$old_path" ]; then
        old_version="$(report_cli_version_or_fail opencode-cli "$old_path" 2>/dev/null || true)"
    fi
    OPENCODE_NATIVE_TRIED=1
    local _oc_before="$old_version"
    [ "$_oc_before" = "?" ] && _oc_before=""
    mu_item_start cli opencode opencode-cli "$_oc_before" "" native
    mu_item_progress cli opencode installing
    native_path="$HOME/.opencode/bin/opencode"
    if [ -x "$LOCAL_BIN/opencode" ]; then
        # A user-local symlink may still be npm's wrapper, not a native CLI.
        # Retain it for explicit review instead of rewriting arbitrary links.
        if ! PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" python3 - "$HOME" "$LOCAL_BIN/opencode" <<'PYEOF_OPENCODE_PATH'
import sys
from cli_duplicates import supported_native_path
sys.exit(0 if supported_native_path(sys.argv[1], 'opencode', sys.argv[2]) else 1)
PYEOF_OPENCODE_PATH
        then
            print_warn "OpenCode user-local command has an unverified installation origin; retaining its existing distribution"
            return 1
        fi
        # Never replace an arbitrary user-owned command with a new symlink.
        native_path="$LOCAL_BIN/opencode"
    fi
    if [ -x "$native_path" ]; then
        if ! run_quiet_with_error_log "opencode upgrade --method curl" \
            run_with_timeout 300 "$native_path" upgrade --method curl; then
            return 1
        fi
    else
        installer_tmp="$(mktemp "${TMPDIR:-/tmp}/mac-update-opencode.XXXXXX")" || return 1
        if ! download_installer_script "https://opencode.ai/install" "$installer_tmp"; then
            rm -f "$installer_tmp"
            return 1
        fi
        # Hide npm-installed opencode during migration: the vendor script exits
        # early if ANY opencode on PATH already has the requested release.
        if ! run_quiet_with_error_log "opencode native installer" \
            run_with_timeout "$(native_installer_timeout)" \
            env PATH="/usr/bin:/bin:/usr/sbin:/sbin" /bin/bash "$installer_tmp" --no-modify-path; then
            rm -f "$installer_tmp"
            return 1
        fi
        rm -f "$installer_tmp"
    fi
    native_version="$(report_cli_version_or_fail opencode-cli "$native_path")" || return 1
    if [ -n "$old_version" ] && [ "$old_version" != "?" ] && semver_is_newer "$old_version" "$native_version"; then
        print_warn "OpenCode native release is older than the installed fallback; retaining npm"
        return 1
    fi
    if [ "$native_path" != "$LOCAL_BIN/opencode" ]; then
        # ln without -f refuses a raced-in user file, including dangling links.
        if [ ! -e "$LOCAL_BIN/opencode" ] && [ ! -L "$LOCAL_BIN/opencode" ]; then
            ln -s "$native_path" "$LOCAL_BIN/opencode" || return 1
        else
            return 1
        fi
    fi
    export PATH="$LOCAL_BIN:$NPM_GLOBAL_BIN:$N_PREFIX/bin:$BUN_BIN:$PATH"
    hash -r 2>/dev/null || true
    [ "$(command -v opencode)" = "$LOCAL_BIN/opencode" ] || return 1
    OPENCODE_NATIVE_OK=1
    CLI_EVENT_ID=opencode
    CLI_EVENT_NAME=opencode-cli
    cli_item_result opencode-cli "$_oc_before" "$native_version" 0
    print_ok "opencode-cli: $native_version (native)"
    return 0
}

cleanup_native_npm_duplicates() {
    local command_name native_path native_version prefix package_name old_version
    local candidates brew_prefix="" failures=0 npm_bin
    npm_bin="$(bootstrap_npm)"
    [ -n "$npm_bin" ] || return 0
    if command -v brew >/dev/null 2>&1; then
        brew_prefix="$(brew --prefix 2>/dev/null || true)"
    fi
    for command_name in claude codex opencode; do
        native_path="$LOCAL_BIN/$command_name"
        [ -x "$native_path" ] || continue
        [ "$(command -v "$command_name" 2>/dev/null || true)" = "$native_path" ] || continue
        native_version="$(report_cli_version_or_fail "$command_name" "$native_path" 2>/dev/null)" || continue
        candidates="$(PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" python3 - "$HOME" "$TOOLCHAIN_HOME" "$brew_prefix" "$command_name" "$native_path" "$native_version" <<'PYEOF_CLI_DUPLICATES'
import os, subprocess, sys
from cli_duplicates import known_npm_prefixes, npm_duplicates, removal_allowed, supported_native_path, NATIVE_NPM_PACKAGES
home, toolchain, brew, command, native, version = sys.argv[1:]
if not supported_native_path(home, command, native):
    sys.exit(0)
try:
    probe = subprocess.run(['ps', '-axo', 'command='], capture_output=True, text=True, timeout=10)
    processes = probe.stdout if probe.returncode == 0 else None
except (OSError, subprocess.TimeoutExpired):
    processes = None
for prefix, previous in npm_duplicates(known_npm_prefixes(home, toolchain, brew), command):
    package_root = prefix / 'lib/node_modules' / NATIVE_NPM_PACKAGES[command]
    # A symlinked npm wrapper in ~/.local/bin is not a native install.
    if os.path.realpath(native).startswith(str(package_root.resolve()) + os.sep):
        continue
    if removal_allowed(version, previous, processes, command):
        print(f'{prefix}|{NATIVE_NPM_PACKAGES[command]}|{previous}')
    else:
        print(f'Retained npm duplicate {NATIVE_NPM_PACKAGES[command]} {previous}: active process, older native or uncertain state', file=sys.stderr)
PYEOF_CLI_DUPLICATES
)" || { failures=$((failures + 1)); continue; }
        while IFS='|' read -r prefix package_name old_version; do
            [ -n "$prefix" ] || continue
            [ "$(command -v "$command_name" 2>/dev/null || true)" = "$native_path" ] || continue
            native_version="$(report_cli_version_or_fail "$command_name" "$native_path" 2>/dev/null)" || continue
            # Recheck processes immediately before deletion, after discovery.
            if ! PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" python3 - "$command_name" "$native_version" "$old_version" <<'PYEOF_CLI_PROCESS'
import subprocess, sys
from cli_duplicates import removal_allowed
try:
    probe = subprocess.run(['ps', '-axo', 'command='], capture_output=True, text=True, timeout=10)
    processes = probe.stdout if probe.returncode == 0 else None
except (OSError, subprocess.TimeoutExpired):
    processes = None
sys.exit(0 if removal_allowed(sys.argv[2], sys.argv[3], processes, sys.argv[1]) else 1)
PYEOF_CLI_PROCESS
            then
                print_warn "Retained npm duplicate $package_name: process state changed or is uncertain"
                continue
            fi
            if run_quiet_with_error_log "remove duplicate $package_name ($old_version)" \
                run_with_timeout 120 "$npm_bin" uninstall -g --prefix "$prefix" --ignore-scripts "$package_name"; then
                if [ -d "$prefix/lib/node_modules/$package_name" ] \
                    || ! report_cli_version_or_fail "$command_name" "$native_path" >/dev/null; then
                    failures=$((failures + 1))
                else
                    print_info "Removed npm duplicate $package_name $old_version from $prefix"
                fi
            else
                failures=$((failures + 1))
            fi
        done <<EOF
$candidates
EOF
    done
    [ "$failures" -eq 0 ]
}

update_native_clis() {
    local display_name
    local package_name
    local method
    local _brew_formula
    local command_name
    local failures=0

    while IFS='|' read -r display_name package_name method _brew_formula command_name; do
        case "$display_name" in
            ""|\#*) continue ;;
        esac

        if [ "$method" = "native-installer" ]; then
            if ! install_native_cli "$display_name" "$command_name"; then
                failures=$((failures + 1))
            fi
        fi
    done < "$MANIFEST_PATH"

    export PATH="$LOCAL_BIN:$NPM_GLOBAL_BIN:$N_PREFIX/bin:$BUN_BIN:$PATH"
    hash -r 2>/dev/null || true

    if [ "$failures" -ne 0 ]; then
        print_warn "$(printf "$L_NPM_FAILURES_SUMMARY" "$failures")"
        if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -f "$MAC_UPDATE_SESSION_DIR/npm_cli_errors.log" ]; then
            print_info "$(printf "$L_NPM_DIAGNOSTICS_PATH_FMT" "$MAC_UPDATE_SESSION_DIR/npm_cli_errors.log")"
        fi
        SOFT_FAIL=1
        return 1
    fi
    return 0
}

remove_legacy_brew_formulas() {
    if ! command -v brew >/dev/null 2>&1; then
        return 0
    fi

    print_info "$L_NPM_REMOVING_LEGACY_BREW"

    local formula
    local command_name
    local command_path
    local brew_prefix
    local native_version brew_versions

    brew_prefix="$(brew --prefix 2>/dev/null || echo "/opt/homebrew")"
    for formula in opencode bun node; do
        if ! brew list --formula "$formula" >/dev/null 2>&1; then
            continue
        fi

        case "$formula" in
            opencode)   command_name="opencode" ;;
            bun)        command_name="bun" ;;
            node)       command_name="node" ;;
        esac

        command_path="$(command -v "$command_name" 2>/dev/null || true)"
        if [ -n "$command_path" ] && ! echo "$command_path" | grep -q "^${brew_prefix}/"; then
            if [ "$formula" = "opencode" ]; then
                native_version="$(report_cli_version_or_fail opencode-cli "$command_path" 2>/dev/null)" || native_version="?"
                brew_versions="$(brew_formula_versions | awk '$1 == "opencode" { for (i=2; i<=NF; i++) print $i }')"
                if ! PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" python3 - "$HOME" "$command_path" "$native_version" "$brew_versions" <<'PYEOF_BREW_OPENCODE'
import subprocess, sys
from cli_duplicates import supported_native_path, removal_allowed
home, executable, native_version, brew_versions = sys.argv[1:]
try:
    probe = subprocess.run(['ps', '-axo', 'command='], capture_output=True, text=True, timeout=10)
    processes = probe.stdout if probe.returncode == 0 else None
except (OSError, subprocess.TimeoutExpired):
    processes = None
versions = brew_versions.split()
allowed = supported_native_path(home, 'opencode', executable) and bool(versions) and all(
    removal_allowed(native_version, version, processes, 'opencode') for version in versions
)
sys.exit(0 if allowed else 1)
PYEOF_BREW_OPENCODE
                then
                    print_warn "Retained Homebrew OpenCode: native origin/version or inactive process could not be verified"
                    continue
                fi
            fi
            if brew uninstall --formula "$formula" >/dev/null 2>&1; then
                print_ok "$(printf "$L_NPM_REMOVED_FROM_BREW" "$formula")"
            else
                print_warn "$(printf "$L_NPM_FAILED_REMOVE_BREW" "$formula")"
            fi
        else
            print_warn "$(printf "$L_NPM_SKIP_UNINSTALL_STILL_BREW" "$formula")"
        fi
    done
}

print_header "$(app_label "Native CLI & npm" "Native CLI & npm")"

if [ ! -f "$MANIFEST_PATH" ]; then
    print_error "$(printf "$L_NPM_MANIFEST_MISSING" "$MANIFEST_PATH")"
    exit 1
fi

# cli_preview_end <id> <display> <before> <latest> <method> — the preview
# result of one tool: "available" when the published version is newer, else
# "current"; an unknown latest version is said, never silenced.
cli_preview_end() {
    local id="$1" display="$2" before="$3" latest="$4" method="$5"
    latest="$(normalize_semver "$latest")"
    mu_item_start cli "$id" "$display" "$before" "$latest" "$method"
    if [ -z "$latest" ] || [ "$latest" = "?" ]; then
        print_info "[DRY-RUN] ${display}: ${before:-?} (newest version could not be checked)"
        cli_end "$id" current "$before" "" "newest version could not be checked in the preview" preview_unchecked "$display"
    elif [ -z "$before" ] || semver_is_newer "$latest" "$before"; then
        print_info "[DRY-RUN] Would update: ${display} ${before:-?} -> ${latest}"
        cli_end "$id" available "$before" "$latest" "would update" "" "$display"
    else
        cli_end "$id" current "$before" "$latest" "" "" "$display"
    fi
}

# cli_preview — a dry run checks every manifest tool the way a real run finds
# it (same paths, overrides and version probes) without installing, writing
# shell profiles or running self-updaters.
cli_preview() {
    local display_name package_name method _brew_formula command_name id before latest cmd npm_bin
    npm_bin="$N_PREFIX/bin/npm"
    [ -x "$npm_bin" ] || npm_bin="$(command -v npm 2>/dev/null || true)"
    while IFS='|' read -r display_name package_name method _brew_formula command_name; do
        case "$display_name" in ""|\#*) continue ;; esac
        id="$(cli_manifest_id "$package_name" "$method" "$command_name")"
        before=""
        latest=""
        case "$method" in
            native-installer)
                if [ ! -x "$LOCAL_BIN/$command_name" ]; then
                    cli_skip_item "$id" "$display_name" "not installed" native
                    continue
                fi
                before="$(detect_command_version "$display_name" "$LOCAL_BIN/$command_name")"
                [ "$before" = "?" ] && before=""
                cli_override_gate "$display_name" "$display_name" "$command_name" "$before" "$command_name" || continue
                mu_item_start cli "$id" "$display_name" "$before" "" native
                cli_end "$id" current "$before" "" "not checked by the preview: its own updater checks it during a real run" preview_unchecked "$display_name"
                continue
                ;;
            self-update)
                cmd="$(resolve_command_path "$command_name" 2>/dev/null || true)"
                if [ -z "$cmd" ]; then
                    cli_skip_item "$id" "$display_name" "not installed" native
                    continue
                fi
                before="$(detect_command_version "$display_name" "$cmd")"
                ;;
            npm)
                if [ "$package_name" = npm ]; then
                    cmd="$N_PREFIX/bin/npm"
                else
                    cmd="$NPM_GLOBAL_BIN/$command_name"
                fi
                if [ ! -x "$cmd" ]; then
                    cli_skip_item "$id" "$display_name" "not installed" npm
                    continue
                fi
                before="$(detect_command_version "$display_name" "$cmd")"
                if [ "$package_name" = npm ] && [ -x "$NPM_GLOBAL_BIN/npm" ]; then
                    # A real run installs npm@latest into the managed global
                    # prefix, which comes first on PATH and reads its version
                    # from there; the copy bundled with Node is only a fallback.
                    _cli_global_before="$(detect_command_version "$display_name" "$NPM_GLOBAL_BIN/npm")"
                    [ "$_cli_global_before" = "?" ] || before="$_cli_global_before"
                fi
                ;;
            native-node)
                if [ ! -x "$N_PREFIX/bin/node" ]; then
                    cli_skip_item "$id" "$display_name" "not installed" native
                    continue
                fi
                before="$(detect_command_version node "$N_PREFIX/bin/node")"
                latest="$(detect_latest_node_version 2>/dev/null || true)"
                ;;
            native-bun)
                cmd="$BUN_BIN/bun"
                [ -x "$cmd" ] || cmd="$(command -v bun 2>/dev/null || true)"
                if [ -z "$cmd" ]; then
                    cli_skip_item "$id" "$display_name" "not installed" native
                    continue
                fi
                before="$(detect_command_version bun "$cmd")"
                latest="$(detect_latest_bun_version 2>/dev/null || true)"
                ;;
            *)
                cli_skip_item "$id" "$display_name" "not checked by the preview" "$method"
                continue
                ;;
        esac
        [ "$before" = "?" ] && before=""
        if [ "$method" = npm ] || [ "$method" = self-update ]; then
            npm_latest_version() { [ -n "$npm_bin" ] && run_with_timeout 30 "$npm_bin" view "$package_name" version </dev/null 2>/dev/null; }
            cli_override_gate "$display_name" "$package_name" "$command_name" "$before" "$id" npm_latest_version || continue
            latest="$(npm_latest_version | head -n 1 | tr -d '[:space:]')"
        else
            cli_override_gate "$display_name" "$package_name" "$command_name" "$before" "$id" || continue
        fi
        cli_preview_end "$id" "$display_name" "$before" "$latest" "$method"
    done < "$MANIFEST_PATH"
}

if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
    print_warn "DRY-RUN mode — tools are checked, nothing is installed and no shell profile is changed"
    mu_group_total cli "$(cli_manifest_total)"
    # Same lookup paths as a real run, for this process only (no profile writes).
    export PATH="$LOCAL_BIN:$NPM_GLOBAL_BIN:$N_PREFIX/bin:$BUN_BIN:$PATH"
    hash -r 2>/dev/null || true
    cli_preview
    cli_finalize_items
    print_header "✅ Native CLI & npm — preview complete"
    exit "$(mac_update_severity_exit_code)"
fi

mu_group_total cli "$(cli_manifest_total)"

trap cleanup_npm_cli EXIT
trap 'cleanup_npm_cli; exit 130' INT TERM
if ! ensure_toolchain_paths; then
    print_error "$L_NPM_PATH_CONFIG_FAILED"
    exit 1
fi

NPM_CLI_EXIT=0
if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ]; then
    if ! : > "$MAC_UPDATE_SESSION_DIR/npm_cli_errors.log"; then
        print_warn "$L_NPM_DIAGNOSTIC_LOG_FAILED"
        SOFT_FAIL=1
    fi
fi

if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
    print_info "$L_NPM_SAVING_PRE_SNAPSHOT"
    if ! write_cli_snapshot "$MAC_UPDATE_SESSION_DIR/npm_cli_before.txt"; then
        print_warn "$L_NPM_SAVE_PRE_SNAPSHOT_FAILED"
        SOFT_FAIL=1
    fi
fi

update_native_clis || SOFT_FAIL=1
update_opencode_native_first || SOFT_FAIL=1

NODE_READY=1
_ensure_node_rc=0
ensure_latest_node || _ensure_node_rc=$?
if [ "$_ensure_node_rc" -eq 2 ]; then
    NODE_READY=0
elif [ "$_ensure_node_rc" -ne 0 ]; then
    HARD_FAIL=1
    NODE_READY=0
    print_error "$L_NPM_SKIPPING_PACKAGES_NODE_FAILED"
fi
if [ "$NODE_READY" -eq 1 ]; then
    install_latest_npm_packages || SOFT_FAIL=1
fi
cleanup_native_npm_duplicates || SOFT_FAIL=1
ensure_latest_bun || HARD_FAIL=1
remove_legacy_brew_formulas
prune_vendor_cli_versions
cli_finalize_items

if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
    print_info "$L_NPM_SAVING_POST_SNAPSHOT"
    if ! write_cli_snapshot "$MAC_UPDATE_SESSION_DIR/npm_cli_after.txt"; then
        print_warn "$L_NPM_SAVE_POST_SNAPSHOT_FAILED"
        SOFT_FAIL=1
    fi
fi

NPM_CLI_EXIT="$(mac_update_severity_exit_code)"
if [ "$NPM_CLI_EXIT" -ne 0 ]; then
    if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -s "$MAC_UPDATE_SESSION_DIR/npm_cli_errors.log" ]; then
        print_warn "$L_NPM_LAST_DIAGNOSTICS"
        tail -n 20 "$MAC_UPDATE_SESSION_DIR/npm_cli_errors.log" | sed 's/^/    /'
    fi
    print_header "$L_NPM_HEADER_FINISHED_WITH_ERRORS"
    exit "$NPM_CLI_EXIT"
fi

print_header "$L_NPM_HEADER_COMPLETE"
print_ok "PATH: $LOCAL_BIN:$NPM_GLOBAL_BIN:$N_PREFIX/bin:$BUN_BIN"
