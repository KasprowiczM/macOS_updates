#!/usr/bin/env bash
# Readiness inspection and explicitly requested dependency setup.
set -o pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

. "$SCRIPT_DIR/lib/tui.sh" || exit 2
type mac_update_tui_route >/dev/null 2>&1 || exit 2
mac_update_tui_route wizard "$@"
tui_status=$?
[ "$MAC_UPDATE_TUI_STARTED" = 1 ] && exit "$tui_status"
set -- "${MAC_UPDATE_TUI_ARGS[@]}"
. "$SCRIPT_DIR/lib/platform.sh"
mac_update_require_supported_platform || exit 1
. "$SCRIPT_DIR/i18n/loader.sh"
# New application acquisition is a separate explicit preview and consent flow.
case "${1:-}" in
    --catalog|--install-plan)
        catalog_mode="$1"; shift
        catalog_plan=""
        if [ "$catalog_mode" = --install-plan ]; then
            [ "$#" -gt 0 ] || { echo "${L_INSTALL_PLAN_PATH_REQUIRED:-An install plan path is required.}" >&2; exit 1; }
            catalog_plan="$1"; shift
        fi
        for catalog_arg in "$@"; do
            case "$catalog_arg" in
                -y|--yes) export MAC_UPDATE_YES=1 ;;
                --non-interactive) export MAC_UPDATE_NONINTERACTIVE=1 ;;
                *) echo "Unknown option: $catalog_arg" >&2; exit 1 ;;
            esac
        done
        . "$SCRIPT_DIR/lib/setup_catalog.sh"
        if [ "$catalog_mode" = --catalog ]; then setup_catalog_menu
        else setup_catalog_install_plan "$catalog_plan"; fi
        exit $?
        ;;
esac

install_deps=0
configure_shell=0
for arg in "$@"; do
    case "$arg" in
        --inspect) ;;
        --install-dependencies) install_deps=1 ;;
        --configure-shell) configure_shell=1 ;;
        -h|--help) echo "Usage: bash setup.sh [--inspect] [--install-dependencies] [--configure-shell] [--catalog] [--install-plan PATH] [--tui] [--cli]"; exit 0 ;;
        *) echo "Unknown option: $arg" >&2; exit 1 ;;
    esac
done
python_ready() {
    mac_update_tool_usable python3 && python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1
}
mas_ready() {
    command -v mas >/dev/null 2>&1 || return 1
    mas_version="$(mas version 2>/dev/null)" || return 1
    mas_major="${mas_version%%.*}"
    mas_minor="${mas_version#*.}"; mas_minor="${mas_minor%%.*}"
    case "$mas_major:$mas_minor" in *[!0-9:]*|:*|*:) return 1 ;; esac
    [ "$mas_major" -gt 4 ] || { [ "$mas_major" -eq 4 ] && [ "$mas_minor" -ge 1 ]; }
}
status=0
for tool in brew mas python3 git; do
    ready=0
    case "$tool" in
        mas) mas_ready && ready=1 ;;
        python3) python_ready && ready=1 ;;
        *) mac_update_tool_usable "$tool" && ready=1 ;;
    esac
    if [ "$ready" -eq 1 ]; then
        printf "${L_SETUP_TOOL_AVAILABLE:-%s: available}\n" "$tool"
    else
        printf "${L_SETUP_TOOL_UNAVAILABLE:-%s: unavailable}\n" "$tool"
        status=10
    fi
done
if ! python_ready; then
    echo "${L_SETUP_PYTHON_UNAVAILABLE:-Python 3.9 or newer is unavailable. Inventory and coverage cannot run; install Python 3 and retry.}"
fi
if [ "$install_deps" -eq 0 ] && [ "$configure_shell" -eq 0 ]; then exit "$status"; fi
if [ ! -t 0 ] || [ ! -t 1 ] || [ "${MAC_UPDATE_NONINTERACTIVE:-0}" = 1 ]; then
    echo "${L_SETUP_TTY_REQUIRED:-A terminal is required for changes. No changes made.}" >&2
    exit 10
fi
# Track action failures separately from the initial readiness report.
status=0
confirm() {
    printf '%s [y/N] ' "$1"
    IFS= read -r answer || return 1
    case "$answer" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
}
if [ "$install_deps" -eq 1 ]; then
    echo "${L_SETUP_DEPENDENCIES_PREVIEW:-Dependency plan: missing mas and Python can be installed with Homebrew. Homebrew itself must be installed separately from https://brew.sh.}"
    for dep in mas python3; do
        if { [ "$dep" = mas ] && ! command -v mas >/dev/null 2>&1; } || { [ "$dep" = python3 ] && ! python_ready; }; then
            package="$dep"; [ "$dep" = python3 ] && package=python
            if command -v brew >/dev/null 2>&1; then
                if confirm "$(printf "${L_SETUP_CONFIRM_INSTALL:-Install %s using Homebrew?}" "$package")"; then
                    brew install "$package" || status=10
                fi
            else
                printf "${L_SETUP_BREW_UNAVAILABLE:-Homebrew unavailable; install %s separately.}\n" "$package"
            fi
        fi
    done
    if command -v mas >/dev/null 2>&1 && command -v brew >/dev/null 2>&1; then
        mas_version="$(mas version 2>/dev/null || echo 0.0)"
        mas_major="${mas_version%%.*}"
        mas_minor="${mas_version#*.}"
        mas_minor="${mas_minor%%.*}"
        case "$mas_major:$mas_minor" in *[!0-9:]*|:*|*:) mas_major=0; mas_minor=0 ;; esac
        if [ "$mas_major" -lt 4 ] || { [ "$mas_major" -eq 4 ] && [ "$mas_minor" -lt 1 ]; }; then
            printf "${L_SETUP_MAS_OLD:-mas %s is older than 4.1.}\n" "$mas_version"
            if confirm "${L_SETUP_CONFIRM_UPGRADE_MAS:-Upgrade mas using Homebrew?}"; then brew upgrade mas || status=10; fi
        fi
    fi
fi
if [ "$configure_shell" -eq 1 ]; then
    prefix="${MAC_UPDATE_HOMEBREW_PREFIX:-/opt/homebrew}"
    case "${SHELL:-/bin/zsh}" in
        */zsh) profile="$HOME/.zprofile" ;;
        */bash) profile="$HOME/.bash_profile" ;;
        *) echo "$L_SETUP_SHELL_UNSUPPORTED"; exit 10 ;;
    esac
    echo "${L_SETUP_SHELL_PREVIEW:-Shell plan: add Homebrew shellenv to} $profile ($prefix/bin/brew)."
    case "$prefix" in
        /*) ;;
        *) echo "${L_SETUP_UNSAFE_PREFIX:-Unsafe Homebrew prefix; shell configuration skipped.}"; exit 10 ;;
    esac
    case "$prefix" in
        *[!a-zA-Z0-9_./-]*) echo "${L_SETUP_UNSAFE_PREFIX:-Unsafe Homebrew prefix; shell configuration skipped.}"; exit 10 ;;
    esac
    if ! python_ready; then
        echo "$L_SETUP_PYTHON_UNAVAILABLE"
        exit 10
    fi
    profile_token="$(PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import sys
from setup_safety import fingerprint
print(fingerprint(sys.argv[1]))
' "$profile" 2>/dev/null)" || { echo "$L_SETUP_PROFILE_SYMLINK"; exit 10; }

    if [ ! -x "$prefix/bin/brew" ]; then
        printf "${L_SETUP_SHELL_BREW_UNAVAILABLE:-Homebrew unavailable at %s; shell configuration skipped.}\n" "$prefix"
        status=10
    elif confirm "$(printf "${L_SETUP_CONFIRM_SHELL:-Update %s?}" "$profile")"; then
        line="eval \"\$(\"$prefix/bin/brew\" shellenv)\""
        if ! PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import sys
from setup_safety import append_profile
try:
    append_profile(sys.argv[1], sys.argv[2], sys.argv[3])
except (OSError, ValueError):
    sys.exit(1)
' "$profile" "$line" "$profile_token"; then
            echo "$L_SETUP_PROFILE_CHANGED"
            status=10
        fi
    fi
fi
# Recheck after approved actions: a successful install can resolve a missing
# prerequisite, while a declined or failed action remains a soft unavailable.
for tool in brew git; do
    mac_update_tool_usable "$tool" || status=10
done
mas_ready || status=10
python_ready || status=10
exit "$status"
