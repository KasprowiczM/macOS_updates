#!/usr/bin/env bash
# lib/native_installers.sh — Per-vendor native CLI bootstrap/update helpers.
# Sourced by update_npm_cli.sh. Not a pipeline entrypoint.

_NATIVE_INSTALLERS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/fetch.sh
. "$_NATIVE_INSTALLERS_DIR/fetch.sh"

native_installer_url() {
    case "$1" in
        claude) printf '%s' "https://claude.ai/install.sh" ;;
        codex)  printf '%s' "https://chatgpt.com/codex/install.sh" ;;
        agy)    printf '%s' "https://antigravity.google/cli/install.sh" ;;
        agent)  printf '%s' "https://cursor.com/install" ;;
        *)      printf '%s' "" ;;
    esac
}

native_installer_env() {
    case "$1" in
        codex) printf '%s' "CODEX_NON_INTERACTIVE=1" ;;
        *)     printf '%s' "" ;;
    esac
}

native_installer_timeout() {
    local raw="${MAC_UPDATE_NATIVE_INSTALLER_TIMEOUT:-360}"
    case "$raw" in
        ''|*[!0-9]*) echo 360; return 0 ;;
    esac
    if [ "$raw" -lt 60 ]; then
        echo 360
    else
        echo "$raw"
    fi
}

# Arguments passed to the vendor bootstrap script (not a shared `latest`).
native_installer_bootstrap_args() {
    case "$1" in
        claude) printf '%s' "latest" ;;
        codex)  printf '%s' "--release latest" ;;
        agy)    printf '%s' "" ;;
        agent)  printf '%s' "" ;;
        *)      printf '%s' "" ;;
    esac
}

# Vendor self-update subcommand once a binary already exists.
native_installer_existing_update_cmd() {
    case "$1" in
        claude|agy|codex|agent) printf '%s' "update" ;;
        *)                      printf '%s' "" ;;
    esac
}

download_installer_script() {
    local url="$1"
    local dest="$2"
    fetch_to_file "$url" "$dest" 60 10485760
}

# Print a usable version or fail. Exit 0 is not enough: the binary must run.
report_cli_version_or_fail() {
    local display_name="$1"
    local command_path="$2"
    local version=""
    local first=""
    local last=""

    if [ ! -x "$command_path" ]; then
        printf '%s\n' "?"
        return 1
    fi
    if ! "$command_path" --version </dev/null >/dev/null 2>&1 \
        && ! "$command_path" -v </dev/null >/dev/null 2>&1; then
        printf '%s\n' "?"
        return 1
    fi
    version="$("$command_path" --version </dev/null 2>/dev/null | head -1)"
    if [ -z "$version" ]; then
        version="$("$command_path" -v </dev/null 2>/dev/null | head -1)"
    fi
    # Codex prints "codex-cli 0.153.4". Taking the first word reports the
    # product name as a successful version. Prefer the last token that
    # contains a digit; require a digit afterwards.
    first="$(printf '%s' "$version" | awk '{print $1}')"
    last="$(printf '%s' "$version" | awk '{print $NF}')"
    case "$first" in
        *[0-9]*) version="$first" ;;
        *) version="$last" ;;
    esac
    version="$(printf '%s' "$version" | sed 's/^v//')"
    case "$version" in
        *[0-9]*)
            printf '%s\n' "$version"
            return 0
            ;;
    esac
    printf '%s\n' "?"
    return 1
}

# Repair an already-installed OpenCode stub in the managed prefix only.
# Returns 2 when there is no existing install (do not bootstrap here).
repair_broken_opencode() {
    local prefix="$1"
    local binary="$2"
    local npm_bin=""
    local _repair_rc=1
    local _pkg=""
    local _node=""

    if [ ! -x "$binary" ]; then
        return 2
    fi
    if [ -z "$prefix" ] || [ ! -d "$prefix" ]; then
        return 1
    fi
    npm_bin="$prefix/bin/npm"
    if [ ! -x "$npm_bin" ]; then
        npm_bin="$(command -v npm 2>/dev/null || true)"
    fi
    if [ -z "$npm_bin" ]; then
        return 1
    fi
    # npm 12 allow-scripts allowlist blocks postinstall even when
    # ignore-scripts is false. Scope the exception to this child; do not
    # write ~/.npmrc.
    NPM_CONFIG_IGNORE_SCRIPTS=false \
        "$npm_bin" install -g --prefix "$prefix" \
        --allow-scripts=opencode-ai opencode-ai@latest </dev/null
    _repair_rc=$?
    if [ "$_repair_rc" -eq 0 ] && "$binary" --version </dev/null >/dev/null 2>&1; then
        return 0
    fi
    _pkg="$prefix/lib/node_modules/opencode-ai"
    _node=""
    if [ -x "$prefix/bin/node" ]; then
        _node="$prefix/bin/node"
    else
        _node="$(command -v node 2>/dev/null || true)"
    fi
    if [ -n "$_node" ] && [ -f "$_pkg/postinstall.mjs" ]; then
        (cd "$_pkg" && "$_node" postinstall.mjs </dev/null) || return 1
        return 0
    fi
    return "$_repair_rc"
}

# Prune old vendor CLI versions (Codex releases, cursor-agent versions, agy backups).
# Skips when MAC_UPDATE_DRY_RUN=1 or MAC_UPDATE_KEEP_CLI_VERSIONS=1.
prune_vendor_cli_versions() {
    if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ] || [ "${MAC_UPDATE_KEEP_CLI_VERSIONS:-0}" = "1" ]; then
        return 0
    fi

    local py_bin
    py_bin="$(command -v python3 2>/dev/null || true)"
    [ -n "$py_bin" ] || return 0

    local agy_ok=0
    if [ -x "$HOME/.local/bin/agy" ] && "$HOME/.local/bin/agy" --version </dev/null >/dev/null 2>&1; then
        agy_ok=1
    fi

    local prune_output
    prune_output="$(PYTHONPATH="$_NATIVE_INSTALLERS_DIR/python${PYTHONPATH:+:$PYTHONPATH}" "$py_bin" - "$HOME" "$agy_ok" <<'PYEOF_PRUNE'
import os
import sys
from cli_retention import prune_all

home = sys.argv[1]
agy_ok = sys.argv[2] == "1"

for name, count, mb in prune_all(home, is_agy_working=agy_ok):
    if count > 0:
        print(f"{count}|{name}|{mb}")
PYEOF_PRUNE
)"

    [ -n "$prune_output" ] || return 0

    local count name mb
    while IFS='|' read -r count name mb; do
        [ -n "$count" ] || continue
        if [ -z "${L_NPM_PRUNED_FMT:-}" ]; then
            L_NPM_PRUNED_FMT="Removed %s old %s versions (freed %s MB)"
        fi
        if type print_info >/dev/null 2>&1; then
            # shellcheck disable=SC2059
            print_info "$(printf "$L_NPM_PRUNED_FMT" "$count" "$name" "$mb")"
        else
            # shellcheck disable=SC2059
            printf '%s\n' "$(printf "$L_NPM_PRUNED_FMT" "$count" "$name" "$mb")"
        fi
    done <<EOF
$prune_output
EOF
    return 0
}

