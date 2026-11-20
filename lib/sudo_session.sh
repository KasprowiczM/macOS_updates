#!/usr/bin/env bash
# lib/sudo_session.sh — one administrator authorization per update run.
#
#   mu_sudo_ensure <purpose> [--allow-password]
#
# Returns 0 when a sudo timestamp is (or becomes) valid, 1 otherwise. It is the
# only place in the toolkit that may run an interactive `sudo -v`.
#
# Contract (2026-11-19, "too many password prompts"):
#   * A warm timestamp returns 0 at once: no prompt, no event.
#   * Never in a dry run, never without a terminal on stdin, never for a
#     scheduled/silent run, never when MAC_UPDATE_NO_SUDO=1.
#   * At most ONE attempt per run. update_all.sh makes it at the start of a real
#     run; the attempt leaves "sudo_attempted" in the session directory, so a
#     child script whose timestamp is cold later gets 1 and reports its
#     root-only items as needing the user instead of asking again.
#   * The attempt is a single plain `sudo -v`: with pam_tid configured macOS
#     shows the Touch ID sheet first and sudo falls back to its own password
#     prompt on the terminal. SUDO_ASKPASS is removed for that call only.
#   * --allow-password is used by the macOS system step alone, when system
#     updates are pending and the timestamp is cold: it may ask once more
#     (its own marker "sudo_attempted_system").
#   * A prompt event (kind=sudo) is emitted right before sudo runs and a
#     prompt_end event right after it returns, on every path.
#
# Children and Homebrew get SUDO_ASKPASS pointing at sudo_askpass_refuse.sh
# (exported by update_all.sh), so a cold timestamp can never turn into a typed
# password prompt in the middle of a run. Bash 3.2 compatible.

_MU_SUDO_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_MU_SUDO_ATTEMPTED=""
_MU_SUDO_ATTEMPTED_SYSTEM=""

mu_sudo_refuse_askpass() {
    printf '%s\n' "$_MU_SUDO_LIB_DIR/sudo_askpass_refuse.sh"
}

# 0 when the sudo timestamp is valid right now. Never prompts.
mu_sudo_warm() {
    command -v sudo >/dev/null 2>&1 || return 1
    sudo -n true 2>/dev/null
}

_mu_sudo_marker() {
    # $1: attempted | attempted_system | unavailable
    if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -d "$MAC_UPDATE_SESSION_DIR" ]; then
        printf '%s\n' "$MAC_UPDATE_SESSION_DIR/sudo_$1"
    fi
}

_mu_sudo_already_tried() {
    local which="$1" marker
    if [ "$which" = system ]; then
        [ -n "$_MU_SUDO_ATTEMPTED_SYSTEM" ] && return 0
        marker="$(_mu_sudo_marker attempted_system)"
    else
        [ -n "$_MU_SUDO_ATTEMPTED" ] && return 0
        marker="$(_mu_sudo_marker attempted)"
    fi
    [ -n "$marker" ] && [ -e "$marker" ]
}

_mu_sudo_mark_tried() {
    local which="$1" marker
    if [ "$which" = system ]; then
        _MU_SUDO_ATTEMPTED_SYSTEM=1
        marker="$(_mu_sudo_marker attempted_system)"
    else
        _MU_SUDO_ATTEMPTED=1
        marker="$(_mu_sudo_marker attempted)"
    fi
    [ -z "$marker" ] || : > "$marker" 2>/dev/null || true
}

# 0 when this process may show an authentication prompt at all.
mu_sudo_can_prompt() {
    [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ] && return 1
    [ "${MAC_UPDATE_NO_SUDO:-0}" = "1" ] && return 1
    [ "${MAC_UPDATE_NONINTERACTIVE:-0}" = "1" ] && return 1
    [ -t 0 ] || return 1
    command -v sudo >/dev/null 2>&1
}

# 0 when mu_sudo_ensure with the same arguments would really show a prompt
# (cold timestamp, prompting allowed, no earlier attempt in this run).
mu_sudo_will_prompt() {
    local which=run
    [ "${1:-}" = "--allow-password" ] && which=system
    mu_sudo_can_prompt || return 1
    _mu_sudo_already_tried "$which" && return 1
    ! mu_sudo_warm
}

# 0 when the start-of-run authorization was attempted and not given.
mu_sudo_declined() {
    local marker
    marker="$(_mu_sudo_marker unavailable)"
    [ -n "$marker" ] && [ -e "$marker" ]
}

mu_sudo_ensure() {
    local purpose="${1:-administrator rights}" which=run prompt_id=sudo rc
    [ "${2:-}" = "--allow-password" ] && { which=system; prompt_id=system_sudo; }
    [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ] && return 1
    mu_sudo_warm && return 0
    mu_sudo_can_prompt || return 1
    _mu_sudo_already_tried "$which" && return 1
    _mu_sudo_mark_tried "$which"
    if type print_info >/dev/null 2>&1; then
        print_info "$(printf "${L_SUDO_CONFIRM_FMT:-Confirm with Touch ID (or type your Mac password once) for: %s}" "$purpose")"
    fi
    if type mu_prompt >/dev/null 2>&1; then
        mu_prompt "$prompt_id" sudo "$purpose" "" "" ""
    fi
    env -u SUDO_ASKPASS sudo -v
    rc=$?
    if type mu_prompt_end >/dev/null 2>&1; then
        mu_prompt_end "$prompt_id" sudo "$purpose" "" "" ""
    fi
    if [ "$rc" -ne 0 ]; then
        local marker
        marker="$(_mu_sudo_marker unavailable)"
        [ -z "$marker" ] || : > "$marker" 2>/dev/null || true
        return 1
    fi
    return 0
}
