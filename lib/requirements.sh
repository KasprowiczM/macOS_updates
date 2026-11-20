#!/usr/bin/env bash
# lib/requirements.sh — one requirements list for doctor, prepare and the UI (Bash 3.2+)
#
# The manifest is config/requirements.tsv. Functions:
#   req_status <id>        present | missing | wrong_arch | too_old | shim | manual
#   req_list_tsv           id<TAB>status<TAB>level<TAB>groups<TAB>name<TAB>hint, no header, no network
#   req_report             human list with "needed by" for doctor
#   req_prepare [--yes]    install what is missing, in dependency order (exit 0 / 10 / 1)
# Reading is side-effect free. Only req_prepare changes the Mac, and only after
# one confirmation (or --yes). An existing Intel Homebrew is never touched.
# Needs lib/platform.sh and the i18n strings loaded by the caller.

_REQ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_REQ_ROOT="$(cd "$_REQ_DIR/.." && pwd)"
REQ_MANIFEST="${MAC_UPDATE_REQUIREMENTS_FILE:-$_REQ_ROOT/config/requirements.tsv}"

# Localised text with a plain fallback: _req_t L_NAME fallback
_req_t() {
    local v
    eval "v=\"\${$1:-}\""
    printf '%s' "${v:-$2}"
}

req_native_prefix() { printf '%s' "${MAC_UPDATE_HOMEBREW_PREFIX:-/opt/homebrew}"; }
req_intel_prefix() { printf '%s' "${MAC_UPDATE_INTEL_BREW_PREFIX:-/usr/local}"; }

# "4.1.2" >= "4.1" ? (numeric, dotted)
_req_version_ge() {
    local have="$1" want="$2" a b
    while [ -n "$have$want" ]; do
        a="${have%%.*}"; b="${want%%.*}"
        case "$have" in *.*) have="${have#*.}" ;; *) have="" ;; esac
        case "$want" in *.*) want="${want#*.}" ;; *) want="" ;; esac
        a="${a//[!0-9]/}"; b="${b//[!0-9]/}"
        a="${a:-0}"; b="${b:-0}"
        [ "$a" -gt "$b" ] && return 0
        [ "$a" -lt "$b" ] && return 1
    done
    return 0
}

_req_python_status() {
    local p
    p="$(command -v python3 2>/dev/null)" || { echo missing; return; }
    if ! mac_update_tool_usable python3; then echo shim; return; fi
    if "$p" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
        echo present
    else
        echo too_old
    fi
}

_req_homebrew_status() {
    local native intel
    native="$(req_native_prefix)"
    intel="$(req_intel_prefix)"
    if [ -x "$native/bin/brew" ]; then echo present; return; fi
    if [ -x "$intel/bin/brew" ]; then echo wrong_arch; return; fi
    if command -v brew >/dev/null 2>&1; then
        case "$(command -v brew)" in "$intel"/*) echo wrong_arch ;; *) echo present ;; esac
        return
    fi
    echo missing
}

_req_mas_status() {
    local v
    command -v mas >/dev/null 2>&1 || { echo missing; return; }
    v="$(mas version 2>/dev/null)" || { echo too_old; return; }
    case "$v" in [0-9]*) ;; *) echo too_old; return ;; esac
    if _req_version_ge "$v" 4.1; then echo present; else echo too_old; fi
}

_req_clt_status() {
    local s dev
    s="$(mac_update_clt_status)"
    case "$s" in
        ok) echo present ;;
        stale) echo too_old ;;
        missing) echo missing ;;
        *)  # orphan: a developer directory (for example Xcode.app) may still serve
            dev="$(xcode-select -p 2>/dev/null)"
            if [ -n "$dev" ] && [ -x "$dev/usr/bin/git" ]; then echo present; else echo missing; fi
            ;;
    esac
}

req_status() {
    case "$1" in
        clt) _req_clt_status ;;
        python3) _req_python_status ;;
        curl) command -v curl >/dev/null 2>&1 && echo present || echo missing ;;
        homebrew) _req_homebrew_status ;;
        mas) _req_mas_status ;;
        git) mac_update_tool_usable git && echo present || echo missing ;;
        node)
            if [ -x "${N_PREFIX:-$HOME/.local/share/mac-update/node}/bin/node" ] || command -v node >/dev/null 2>&1; then
                echo present
            else
                echo missing
            fi
            ;;
        rosetta) mac_update_rosetta_installed && echo present || echo missing ;;
        touchid)
            if grep -qs 'pam_tid' "${MAC_UPDATE_PAM_SUDO_LOCAL:-/etc/pam.d/sudo_local}" "${MAC_UPDATE_PAM_SUDO:-/etc/pam.d/sudo}"; then
                echo present
            else
                echo missing
            fi
            ;;
        accessibility|appstore_signin) echo manual ;;
        *) echo missing ;;
    esac
}

# Rows of the manifest as "id level groups install"
_req_rows() {
    local id level groups install
    [ -f "$REQ_MANIFEST" ] || return 0
    while IFS="$(printf '\t')" read -r id level groups install; do
        case "$id" in ''|'#'*) continue ;; esac
        printf '%s\t%s\t%s\t%s\n' "$id" "$level" "$groups" "$install"
    done < "$REQ_MANIFEST"
}

req_list_tsv() {
    local id level groups install st name hint
    while IFS="$(printf '\t')" read -r id level groups install; do
        st="$(req_status "$id")"
        name="$(_req_t "L_REQ_NAME_$id" "$id")"
        hint="$(_req_t "L_REQ_HINT_$id" "")"
        printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$id" "$st" "$level" "$groups" "$name" "$hint"
    done <<EOF_REQ
$(_req_rows)
EOF_REQ
}

# Installable by prepare: required, and the status says something can be done.
_req_installable() { # id status level
    [ "$3" = required ] || return 1
    case "$1:$2" in
        clt:missing) return 0 ;;
        homebrew:missing|homebrew:wrong_arch) return 0 ;;
        python3:missing|python3:shim|python3:too_old) return 0 ;;
        mas:missing|mas:too_old) return 0 ;;
    esac
    return 1
}

_req_icon() {
    case "$1" in
        present) printf '✅' ;;
        manual) printf 'ℹ️ ' ;;
        *) printf '⚠️ ' ;;
    esac
}

# Prints the list. Returns 0 nothing missing, 10 when a required row is not
# present, so callers can decide on the closing line.
req_report() {
    local id st level groups name hint rc=0 installable=0 lbl need
    echo ""
    echo "  $(_req_t L_REQ_TITLE 'Requirements')"
    echo ""
    while IFS="$(printf '\t')" read -r id st level groups name hint; do
        [ -n "$id" ] || continue
        lbl="$(_req_t "L_REQ_STATUS_$st" "$st")"
        need="$(_req_t L_REQ_NEEDED_BY 'needed by'): $groups"
        printf '  %s %s — %s (%s; %s)\n' "$(_req_icon "$st")" "$name" "$lbl" "$level" "$need"
        if [ "$st" != present ] && [ -n "$hint" ]; then
            printf '       %s\n' "$hint"
        fi
        if [ "$level" = required ] && [ "$st" != present ]; then
            rc=10
            if _req_installable "$id" "$st" "$level"; then installable=1; fi
        fi
    done <<EOF_REP
$(req_list_tsv)
EOF_REP
    echo ""
    if [ "$installable" -eq 1 ]; then
        echo "  $(_req_t L_REQ_RUN_PREPARE 'Something installable is missing. Run: mac-update prepare')"
    fi
    return "$rc"
}

_req_step() { # id state text
    local icon
    case "$2" in ok) icon='✅' ;; skipped) icon='⏭️ ' ;; *) icon='❌' ;; esac
    printf '  %s %s: %s\n' "$icon" "$1" "$3"
}

# Obtain sudo once for the Homebrew installer. The shared helper
# (lib/sudo_session.sh: mu_sudo_ensure, Touch ID first, one typed password as
# fallback) is used when present; otherwise a single plain `sudo -v` on a TTY.
req_acquire_sudo() {
    if [ -f "$_REQ_DIR/sudo_session.sh" ] && ! type mu_sudo_ensure >/dev/null 2>&1; then
        # shellcheck source=/dev/null
        . "$_REQ_DIR/sudo_session.sh"
    fi
    if type mu_sudo_ensure >/dev/null 2>&1; then
        mu_sudo_ensure prepare --allow-password
        return $?
    fi
    sudo -n true 2>/dev/null && return 0
    if [ ! -t 0 ] || [ "${MAC_UPDATE_NONINTERACTIVE:-0}" = 1 ]; then
        return 1
    fi
    sudo -v
}

_req_poll_clt() {
    local waited=0 limit="${MAC_UPDATE_CLT_WAIT:-1800}" every="${MAC_UPDATE_CLT_POLL:-5}"
    while [ "$waited" -lt "$limit" ]; do
        [ "$(_req_clt_status)" = present ] && return 0
        sleep "$every"
        waited=$((waited + every))
    done
    [ "$(_req_clt_status)" = present ]
}

_req_install_clt() {
    if [ -d /Applications/Xcode.app ] && [ "$(_req_clt_status)" = present ]; then return 0; fi
    xcode-select --install >/dev/null 2>&1 || true
    _req_step clt skipped "$(_req_t L_REQ_CLT_WAIT 'click Install in the macOS dialog; waiting for it to finish')"
    _req_poll_clt
}

_req_install_homebrew() {
    local prefix url
    prefix="$(req_native_prefix)"
    url="${MAC_UPDATE_HOMEBREW_INSTALL_URL:-https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh}"
    req_acquire_sudo || return 2
    NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL --proto '=https' --tlsv1.2 "$url")" || return 1
    [ -x "$prefix/bin/brew" ] || return 1
    eval "$("$prefix/bin/brew" shellenv)" 2>/dev/null || true
    mac_update_ensure_homebrew_path
    return 0
}

# The shellenv line goes through setup.sh --configure-shell (previewed, symlink
# safe, idempotent).
_req_configure_shell() {
    MAC_UPDATE_YES=1 bash "$_REQ_ROOT/setup.sh" --cli --configure-shell >/dev/null 2>&1
}

_req_brew() { # run the native brew only
    "$(req_native_prefix)/bin/brew" "$@"
}

# req_prepare [--yes]. The flag must be explicit: --non-interactive alone never installs. Exit 0 nothing required left, 10 user needed, 1 error.
req_prepare() {
    local yes=0 arg
    for arg in "$@"; do [ "$arg" = --yes ] || [ "$arg" = -y ] && yes=1; done
    local before todo="" id st level groups name hint n=0 rc=0 failed=0 needs_user=0
    before="$(req_list_tsv)"
    while IFS="$(printf '\t')" read -r id st level groups name hint; do
        [ -n "$id" ] || continue
        if _req_installable "$id" "$st" "$level"; then
            todo="$todo $id"
            n=$((n + 1))
        fi
    done <<EOF_TODO
$before
EOF_TODO
    if [ "$n" -eq 0 ]; then
        echo "  $(_req_t L_REQ_NOTHING 'Nothing to install: every required item is present.')"
        # Required rows that are not installable by us still need the user.
        while IFS="$(printf '\t')" read -r id st level groups name hint; do
            [ "$level" = required ] && [ "$st" != present ] && needs_user=1
        done <<EOF_NU
$before
EOF_NU
        [ "$needs_user" -eq 1 ] && { req_report; return 10; }
        return 0
    fi
    req_report
    if [ "$yes" != 1 ]; then
        if [ ! -t 0 ] || [ ! -t 1 ] || [ "${MAC_UPDATE_NONINTERACTIVE:-0}" = 1 ]; then
            echo "  $(_req_t L_REQ_NONINTERACTIVE 'Nothing was changed. Run "mac-update prepare" in a terminal, or add --yes.')"
            return 10
        fi
        printf '  %s [y/N] ' "$(printf "$(_req_t L_REQ_CONFIRM 'Install %s now? This may ask for your password and needs the internet.')" "$(echo $todo)")"
        local answer=""
        IFS= read -r answer || answer=""
        case "$answer" in y|Y|yes|YES) ;; *) echo "  $(_req_t L_REQ_DECLINED 'Nothing was changed.')"; return 10 ;; esac
    fi

    # 1. Command Line Tools
    case " $todo " in *" clt "*)
        if _req_install_clt; then _req_step clt ok "$(_req_t L_REQ_OK 'installed')"
        else _req_step clt failed "$(_req_t L_REQ_CLT_CANCELLED 'not finished; run mac-update prepare again after the installer completes')"; needs_user=1; fi
    esac
    # 2. Native Homebrew (needs the Command Line Tools)
    case " $todo " in *" homebrew "*)
        if [ "$(_req_clt_status)" != present ]; then
            _req_step homebrew skipped "$(_req_t L_REQ_NEEDS_CLT 'needs the Command Line Tools first')"; needs_user=1
        else
            _req_install_homebrew; rc=$?
            if [ "$rc" -eq 0 ]; then
                _req_step homebrew ok "$(_req_t L_REQ_OK 'installed')"
                if _req_configure_shell; then _req_step shell ok "$(_req_t L_REQ_SHELL_OK 'Homebrew added to your shell profile')"
                else _req_step shell skipped "$(_req_t L_REQ_SHELL_SKIP 'shell profile not changed; open a new terminal or run setup.sh --configure-shell')"; fi
            elif [ "$rc" -eq 2 ]; then
                _req_step homebrew failed "$(_req_t L_REQ_NEEDS_SUDO 'administrator password needed; run mac-update prepare in a terminal')"; needs_user=1
            else
                _req_step homebrew failed "$(_req_t L_REQ_FAILED 'the installer did not finish')"; failed=1
            fi
        fi
    esac
    # 3. Python: the Command Line Tools one counts; Homebrew Python only if still unusable
    case " $todo " in *" python3 "*)
        st="$(_req_python_status)"
        if [ "$st" = present ]; then
            _req_step python3 ok "$(_req_t L_REQ_PY_FROM_CLT 'available from the Command Line Tools')"
        elif [ -x "$(req_native_prefix)/bin/brew" ]; then
            if _req_brew install python >/dev/null 2>&1; then _req_step python3 ok "$(_req_t L_REQ_OK 'installed')"
            else _req_step python3 failed "$(_req_t L_REQ_FAILED 'the installer did not finish')"; failed=1; fi
        else
            _req_step python3 skipped "$(_req_t L_REQ_NEEDS_BREW 'needs Homebrew first')"; needs_user=1
        fi
    esac
    # 4. mas
    case " $todo " in *" mas "*)
        if [ -x "$(req_native_prefix)/bin/brew" ]; then
            if [ "$(_req_mas_status)" = missing ]; then _req_brew install mas >/dev/null 2>&1; rc=$?
            else _req_brew upgrade mas >/dev/null 2>&1; rc=$?; fi
            if [ "$rc" -eq 0 ]; then
                _req_step mas ok "$(_req_t L_REQ_OK 'installed')"
            else
                _req_step mas failed "$(_req_t L_REQ_FAILED 'the installer did not finish')"; failed=1
            fi
        else
            _req_step mas skipped "$(_req_t L_REQ_NEEDS_BREW 'needs Homebrew first')"; needs_user=1
        fi
    esac
    # Anything required and still not present?
    while IFS="$(printf '\t')" read -r id st level groups name hint; do
        [ "$level" = required ] && [ "$st" != present ] && needs_user=1
    done <<EOF_AFTER
$(req_list_tsv)
EOF_AFTER
    if [ "$failed" -eq 1 ]; then return 1; fi
    if [ "$needs_user" -eq 1 ]; then
        # re-check: success of every step clears the flag
        local left=0
        while IFS="$(printf '\t')" read -r id st level groups name hint; do
            [ "$level" = required ] && [ "$st" != present ] && left=1
        done <<EOF_LEFT
$(req_list_tsv)
EOF_LEFT
        [ "$left" -eq 1 ] && return 10
    fi
    return 0
}
