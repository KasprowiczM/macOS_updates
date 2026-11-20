#!/usr/bin/env bash
# shellcheck disable=SC2329  # cleanup_brew is invoked through trap.
# ============================================================
# SKRYPT 4: Aktualizacja pakietów Homebrew
# ============================================================
# Data:  2026-03-18 (zaktualizowano)
set -o pipefail
# Homebrew can remove /opt/homebrew/bin/python3 (or any other symlink) while
# this process is running. Without checkhash, bash keeps calling the stale
# hashed path ("No such file or directory") instead of re-searching PATH.
shopt -s checkhash

# Kompatybilność: bash 3.2+ (macOS domyślny shell)
# Opis:  Aktualizuje wszystkie pakiety (formulae) i aplikacje
#        (casks) zainstalowane przez Homebrew.
#        Jeśli MAC_UPDATE_SESSION_DIR jest ustawiony, zapisuje
#        snapshoty wersji przed i po aktualizacji.
# ============================================================

# Kolory
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Katalog z skryptami
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

. "$SCRIPT_DIR/lib/platform.sh"
mac_update_require_supported_platform || exit 1

# ── i18n: load language strings ──────────────────────────────
. "$SCRIPT_DIR/lib/cli.sh"
. "$SCRIPT_DIR/lib/ui.sh"
. "$SCRIPT_DIR/i18n/loader.sh"
. "$SCRIPT_DIR/lib/severity.sh"
. "$SCRIPT_DIR/lib/internet_apps.sh"
. "$SCRIPT_DIR/lib/brew.sh"
. "$SCRIPT_DIR/lib/vendor_direct.sh"
. "$SCRIPT_DIR/lib/version.sh"
. "$SCRIPT_DIR/lib/internet_i18n.sh"
. "$SCRIPT_DIR/lib/events.sh"
. "$SCRIPT_DIR/lib/sudo_session.sh"
. "$SCRIPT_DIR/lib/overrides.sh"
mac_update_severity_init

cleanup_brew() {
    [ -f "${BREW_UPGRADE_LOG:-}" ] && rm -f "$BREW_UPGRADE_LOG" 2>/dev/null || true
}
trap cleanup_brew EXIT
trap 'cleanup_brew; exit 130' INT TERM

strip_ansi() {
    sed $'s/\033\\[[0-9;]*[a-zA-Z]//g'
}

print_header() { ui_print_header "$1"; }

# brew_cask_running_app <targets "A.app;B.app">
#   Prints the name of the first installed target app that is open or whose
#   running state cannot be proven closed; prints nothing when every installed
#   target is verifiably not running. Tri-state via internet_app_running_state:
#   only an explicit "false" lets the cask upgrade proceed.
brew_cask_running_app() {
    local targets="$1" t_name dir path bid state
    while IFS= read -r t_name; do
        [ -n "$t_name" ] || continue
        for dir in "/Applications" "$HOME/Applications"; do
            path="$dir/$t_name"
            [ -d "$path" ] || continue
            bid="$(internet_app_bundle_id "$path" 2>/dev/null || true)"
            state="$(internet_app_running_state "$bid")"
            if [ "$state" != "false" ]; then
                printf '%s\n' "$t_name"
                return 0
            fi
        done
    done <<EOF_RUNNING_TARGETS
$(printf '%s' "$targets" | tr ';' '\n')
EOF_RUNNING_TARGETS
    return 0
}



# brew_cask_running_quit_id <ids "a.b.c;d.e.f"|UNREADABLE>
#   For casks without an app target: prints the first declared quit/signal bundle
#   ID that is running or of unknown state (or UNREADABLE when the cask JSON could
#   not be read, which defers); nothing when none is declared or all are closed.
brew_cask_running_quit_id() {
    local ids="$1" bid state
    if [ "$ids" = "UNREADABLE" ]; then
        printf '%s\n' "UNREADABLE"
        return 0
    fi
    while IFS= read -r bid; do
        [ -n "$bid" ] || continue
        state="$(internet_app_running_state "$bid")"
        if [ "$state" != "false" ]; then
            printf '%s\n' "$bid"
            return 0
        fi
    done <<EOF_QUIT_IDS
$(printf '%s' "$ids" | tr ';' '\n')
EOF_QUIT_IDS
    return 0
}

# brew_app_is_background <app path>
#   True when the app declares itself a background / menu-bar app
#   (Info.plist LSUIElement or LSBackgroundOnly). Such an app holds no documents.
brew_app_is_background() {
    local path="$1" key v
    for key in LSUIElement LSBackgroundOnly; do
        v="$(defaults read "$path/Contents/Info" "$key" 2>/dev/null || true)"
        case "$(printf '%s' "$v" | tr '[:upper:]' '[:lower:]')" in
            1|true|yes) return 0 ;;
        esac
    done
    return 1
}

# brew_app_already_at_cask_version <app path> <cask version>
#   Returns 0 when the installed bundle already is the cask's target version or
#   newer, e.g. an app whose own updater (Sparkle) ran after Homebrew's receipt
#   was written. Equal short version, or equal CFBundleVersion when the cask
#   version carries a build ("3.7.8,1234"), or a newer short version only when
#   both use the same numbering scheme (app_vs_package_version_relation).
brew_app_already_at_cask_version() {
    local path="$1" cask_ver="$2" core build short bundle_build rel
    [ -n "$path" ] && [ -d "$path" ] && [ -n "$cask_ver" ] || return 1
    core="${cask_ver%%,*}"
    build=""
    case "$cask_ver" in *,*) build="${cask_ver#*,}"; build="${build%%,*}" ;; esac
    short="$(app_version "$path")"
    [ -n "$short" ] || return 1
    rel="$(version_cmp "$short" "$core")"
    [ "$rel" = "equal" ] && return 0
    if [ -n "$build" ]; then
        bundle_build="$(app_build_version "$path")"
        [ -n "$bundle_build" ] && [ "$bundle_build" = "$build" ] && return 0
    fi
    if [ "$rel" = "newer" ] && [ "$(app_vs_package_version_relation "$short" "$core" 2>/dev/null)" = "newer" ]; then
        return 0
    fi
    return 1
}

# brew_cask_open_decision <targets "A.app;B.app">
#   Prints nothing when every installed target is verifiably closed;
#   "defer|<app>" when an app is open (or its state is unknown) and may not be
#   quit for the user; "quit|<bundle ids>|<app name>" when every open app is a
#   background / menu-bar app that is provably running and can be quit politely.
brew_cask_open_decision() {
    local targets="$1" t_name dir path bid state first_defer="" quit_ids="" quit_name=""
    while IFS= read -r t_name; do
        [ -n "$t_name" ] || continue
        for dir in "/Applications" "$HOME/Applications"; do
            path="$dir/$t_name"
            [ -d "$path" ] || continue
            bid="$(internet_app_bundle_id "$path" 2>/dev/null || true)"
            state="$(internet_app_running_state "$bid")"
            [ "$state" = "false" ] && continue
            if [ "$state" = "true" ] && [ -n "$bid" ] && brew_app_is_background "$path"; then
                quit_ids="$quit_ids $bid"
                quit_name="${quit_name:-$t_name}"
            else
                first_defer="${first_defer:-$t_name}"
            fi
        done
    done <<EOF_OPEN_TARGETS
$(printf '%s' "$targets" | tr ';' '\n')
EOF_OPEN_TARGETS
    if [ -n "$first_defer" ]; then
        printf 'defer|%s\n' "$first_defer"
    elif [ -n "$quit_ids" ]; then
        printf 'quit|%s|%s\n' "${quit_ids# }" "$quit_name"
    fi
    return 0
}

# brew_quit_background_apps <cask> <bundle ids>
#   Politely quits each app (AppleScript quit, never a signal) and waits up to
#   MAC_UPDATE_BREW_QUIT_WAIT seconds (default 20) until every one is closed.
#   Returns 1 when one is still running or its state is unknown.
brew_quit_background_apps() {
    local cask="$1" ids="$2" bid waited=0 limit="${MAC_UPDATE_BREW_QUIT_WAIT:-20}" all_closed
    case "$limit" in ''|*[!0-9]*) limit=20 ;; esac
    for bid in $ids; do
        print_info "$cask: quitting the background app $bid so it can be updated"
        run_with_timeout 10 osascript -e "tell application id \"$bid\" to quit" >/dev/null 2>&1 || true
    done
    while :; do
        all_closed=1
        for bid in $ids; do
            [ "$(internet_app_running_state "$bid")" = "false" ] || all_closed=0
        done
        if [ "$all_closed" -eq 1 ]; then
            print_info "$cask: the app quit after ${waited}s"
            return 0
        fi
        [ "$waited" -ge "$limit" ] && break
        sleep 1
        waited=$((waited + 1))
    done
    print_warn "$cask: the app did not quit within ${limit}s"
    return 1
}

# brew_relaunch_background_apps <cask> <bundle ids>
#   Reopens the apps in the background (no focus steal); runs after the upgrade
#   whether or not it worked, so an app we quit is never left closed.
brew_relaunch_background_apps() {
    local cask="$1" ids="$2" bid
    for bid in $ids; do
        print_info "$cask: reopening $bid"
        run_with_timeout 15 open -g -b "$bid" >/dev/null 2>&1 \
            || print_warn "$cask: could not reopen $bid; open it from Applications"
    done
    return 0
}

# ============================================================
print_header "$L_BREW_TITLE"
if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
    print_warn "$L_BREW_DRYRUN_MODE"
fi

# ============================================================
# Check if Homebrew is installed
# ============================================================
. "$SCRIPT_DIR/lib/requirements.sh"
BREW_REQ_STATUS="$(req_status homebrew)"
if [ "$BREW_REQ_STATUS" != "present" ] || ! command -v brew &> /dev/null; then
    # Missing, or only an Intel Homebrew under /usr/local: not a failure of the
    # run, but something the user has to prepare. The Intel one is left alone.
    [ "$BREW_REQ_STATUS" = "present" ] && BREW_REQ_STATUS="missing"
    print_warn "$(printf "$(_req_t L_BREW_REQUIREMENT_MISSING 'Homebrew is not ready on this Mac (%s).')" "$BREW_REQ_STATUS")"
    print_info "$(_req_t L_BREW_REQUIREMENT_RUN 'Run: mac-update prepare')"
    mu_item_start brew "requirement:homebrew" "Homebrew" "" "" homebrew
    mu_item_end brew "requirement:homebrew" needs_you "" "" "Homebrew: $BREW_REQ_STATUS. run: mac-update prepare" requirement_missing "Homebrew"
    exit 10
fi

BREW_VERSION=$(brew --version | head -1)
print_ok "$BREW_VERSION"
print_info "$L_BREW_LOCATION $(command -v brew)"

# CLT status check (one-line info if stale or orphan)
CLT_STATUS="$(mac_update_clt_status)"
if [ "$CLT_STATUS" = "stale" ] || [ "$CLT_STATUS" = "orphan" ]; then
    print_info "Command Line Tools ($CLT_STATUS) — Homebrew recommendation: sudo rm -rf /Library/Developer/CommandLineTools && sudo xcode-select --install"
fi

# ============================================================
# Check Xcode license agreement (preflight)
# ============================================================
if ! brew_xcode_license_ok; then
    XCODE_INFO=""
    if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -f "$MAC_UPDATE_SESSION_DIR/xcode_changed.txt" ]; then
        raw_xc="$(cat "$MAC_UPDATE_SESSION_DIR/xcode_changed.txt" 2>/dev/null)"
        xc_change="${raw_xc#xcode_changed=}"
        [ -n "$xc_change" ] && XCODE_INFO=" (Xcode $xc_change)"
    fi
    print_warn "$(printf "$L_BREW_XCODE_LICENSE_NOTICE" "$XCODE_INFO")"

    LICENSE_ACCEPTED=0
    if [ -t 0 ] && [ "${MAC_UPDATE_NONINTERACTIVE:-0}" != "1" ] && [ "${MAC_UPDATE_DRY_RUN:-0}" != "1" ]; then
        if mac_update_prompt_yn "$L_BREW_XCODE_LICENSE_PROMPT" n y; then
            print_info "Running: sudo xcodebuild -license accept..."
            # The run's single authorization (mu_sudo_ensure never asks twice).
            if mu_sudo_ensure "${L_BREW_XCODE_SUDO_PURPOSE:-accepting the Xcode license}" \
               && sudo -n xcodebuild -license accept 2>/dev/null && brew_xcode_license_ok; then
                LICENSE_ACCEPTED=1
                print_ok "Xcode license accepted successfully."
            fi
        fi
    fi

    if [ "$LICENSE_ACCEPTED" -ne 1 ]; then
        print_warn "$L_BREW_XCODE_LICENSE_MANUAL"
        if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ]; then
            echo "unknown" > "$MAC_UPDATE_SESSION_DIR/pending_brew_formulae"
            echo "unknown" > "$MAC_UPDATE_SESSION_DIR/pending_brew_casks"
            echo "xcode_license" > "$MAC_UPDATE_SESSION_DIR/pending_brew_reason"
        fi
        exit 10
    fi
fi

# ── Snapshot of installed packages before update ──
if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
    print_info "$L_BREW_SAVING_BEFORE"
    if ! brew list --formula --versions 2>/dev/null | strip_ansi > "$MAC_UPDATE_SESSION_DIR/brew_formulae_before.txt"; then
        print_warn "Could not save the pre-update formula snapshot."
        SOFT_FAIL=1
    fi
    if ! brew_cask_versions | strip_ansi > "$MAC_UPDATE_SESSION_DIR/brew_casks_before.txt"; then
        print_warn "Could not save the pre-update cask snapshot."
        SOFT_FAIL=1
    fi
fi

# Determine greedy tokens from config/internet_app_methods.txt
# (apps using brew_cask method, filtered to installed casks)
brew_greedy_tokens() {
    local app meth rest tok installed greedy
    installed="$(brew list --cask 2>/dev/null || true)"
    [ -n "$installed" ] || return 0

    greedy=""
    if [ -f "$SCRIPT_DIR/config/internet_app_methods.txt" ]; then
        while IFS='|' read -r app meth rest; do
            case "$app" in '#'*|'') continue ;; esac
            if [ "$meth" = "brew_cask" ]; then
                tok="$(internet_cask_name_for_app "$app" 2>/dev/null || true)"
                [ -n "$tok" ] || tok="$(echo "$app" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-')"
                if echo "$installed" | grep -qw "$tok"; then
                    greedy="$greedy $tok"
                fi
            fi
        done < "$SCRIPT_DIR/config/internet_app_methods.txt"
    fi
    echo "$greedy" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

# A preview (dry run) refreshes Homebrew's metadata like a real run so the list
# is accurate, then stops before the first upgrade ("PREVIEW STOP" below).
if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
    print_info "${L_BREW_DRYRUN_REFRESH:-Preview: refreshing Homebrew package information (brew update) so the list is accurate; no package is upgraded.}"
fi

# ============================================================
# STEP 1: Update Homebrew itself
# ============================================================
print_header "$L_BREW_UPDATE"

if brew update; then
    print_ok "$L_BREW_UPDATED"
else
    print_warn "brew update failed; refusing to use potentially stale metadata."
    SOFT_FAIL=1
    exit "$(mac_update_severity_exit_code)"
fi

# ============================================================
# STEP 2: Check outdated packages
# ============================================================
print_header "$L_BREW_OUTDATED"

echo -e "${CYAN}$L_BREW_OUTDATED_LIST${NC}"
if ! OUTDATED_FORMULAE=$(brew_outdated_formulae); then
    print_warn "brew outdated --formula failed; update state is unknown."
    [ -n "$OUTDATED_FORMULAE" ] && printf '%s\n' "$OUTDATED_FORMULAE"
    SOFT_FAIL=1
    exit "$(mac_update_severity_exit_code)"
fi
if [ -z "$OUTDATED_FORMULAE" ]; then
    print_ok "All formulae are up to date!"
else
    echo "$OUTDATED_FORMULAE"
fi

echo ""
echo -e "${CYAN}$L_BREW_CASKS_OUTDATED${NC}"
GREEDY_TOKENS="$(brew_greedy_tokens)"
# shellcheck disable=SC2086
if ! OUTDATED_CASKS=$(brew_outdated_casks $GREEDY_TOKENS); then
    print_warn "brew outdated --cask failed; update state is unknown."
    [ -n "$OUTDATED_CASKS" ] && printf '%s\n' "$OUTDATED_CASKS"
    SOFT_FAIL=1
    exit "$(mac_update_severity_exit_code)"
fi

# Check for orphan casks (installed cask whose app target is missing)
ORPHAN_CASKS="$(brew_orphan_casks 2>/dev/null || true)"
if [ -n "$ORPHAN_CASKS" ]; then
    for orph in $ORPHAN_CASKS; do
        [ -n "$orph" ] || continue
        expected_app="$(brew info --json=v2 --cask "$orph" 2>/dev/null | brew_cask_primary_app || true)"
        [ -n "$expected_app" ] || expected_app="${orph}.app"

        print_info "$(printf "$L_BREW_ORPHAN_CASK_FMT" "$orph" "$expected_app" "$orph")"

        if [ -n "$OUTDATED_CASKS" ]; then
            OUTDATED_CASKS="$(echo "$OUTDATED_CASKS" | awk -v o="$orph" '$1 != o')"
        fi

        if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -d "$MAC_UPDATE_SESSION_DIR" ]; then
            echo "$orph" >> "$MAC_UPDATE_SESSION_DIR/brew_orphan_casks.txt"
        fi

        if [ -t 0 ] && [ "${MAC_UPDATE_YES:-0}" != "1" ] && [ "${MAC_UPDATE_NONINTERACTIVE:-0}" != "1" ] \
           && [ "${MAC_UPDATE_DRY_RUN:-0}" != "1" ]; then
            # shellcheck disable=SC2059
            if mac_update_prompt_yn "$(printf "$L_BREW_ORPHAN_CASK_PROMPT_FMT" "$orph")" n n; then
                brew uninstall --cask --force "$orph" || true
            fi
        fi
    done
fi

if [ -z "$OUTDATED_CASKS" ]; then
    print_ok "All casks are up to date!"
else
    echo "$OUTDATED_CASKS"
fi

# ── User overrides (lib/overrides.sh): manual → report only, skip → ignore ──
# brew_apply_overrides <group> <list> — prints the list without overridden
# entries and emits their item_end events. Sets BREW_OVERRIDE_FILTERED=1 when
# anything was removed.
BREW_OVERRIDE_FILTERED=0
brew_apply_overrides() {
    local group="$1" list="$2" line token mode event_id
    while IFS= read -r line; do
        token="${line%% *}"
        [ -n "$token" ] || continue
        mode="$(mu_override_mode "$group" "$token")"
        event_id="$token"
        [ "$group" = cask ] && event_id="cask:$token"
        case "$mode" in
            skip)
                mu_item_start brew "$event_id" "${token##*/}" "" "" homebrew
                mu_item_end brew "$event_id" skipped "" "" "user override: skip" "" "${token##*/}"
                printf 'filtered\n' >> "$BREW_FILTER_MARK"
                ;;
            manual)
                print_info "$token: update available (manual by user override)" >&2
                mu_item_start brew "$event_id" "${token##*/}" "" "" homebrew
                mu_item_end brew "$event_id" needs_you "" "" "update available (manual)" manual_mode "${token##*/}"
                printf 'filtered\n' >> "$BREW_FILTER_MARK"
                ;;
            *) printf '%s\n' "$line" ;;
        esac
    done <<EOF_BREW_OVERRIDES
$list
EOF_BREW_OVERRIDES
}
BREW_FILTER_MARK="$(mktemp "${TMPDIR:-/tmp}/mac_update_brew_filter.XXXXXX")" || BREW_FILTER_MARK=/dev/null
OUTDATED_FORMULAE_PREFILTER="$OUTDATED_FORMULAE"
OUTDATED_CASKS_PREFILTER="$OUTDATED_CASKS"
OUTDATED_FORMULAE="$(brew_apply_overrides brew "$OUTDATED_FORMULAE")"
OUTDATED_CASKS="$(brew_apply_overrides cask "$OUTDATED_CASKS")"
[ -s "$BREW_FILTER_MARK" ] && BREW_OVERRIDE_FILTERED=1
[ "$BREW_FILTER_MARK" = /dev/null ] || rm -f "$BREW_FILTER_MARK"
OUTDATED_FORMULA_TOKENS="$(printf '%s\n' "$OUTDATED_FORMULAE" | awk 'NF { print $1 }')"

# ── Item rows ───────────────────────────────────────────────
# Casks: every installed cask is itemised (up-to-date ones end right here as
# current; outdated ones start in the guard loop below). Formulae: only the
# outdated ones are itemised — hundreds of up-to-date rows would bury them —
# and the number checked travels on group_end ("checked").
# Overridden items were already started and ended by brew_apply_overrides.
brew_report_inventory() {
    local line token ver seen="|" outdated="|" total=0 formula_count=0
    local installed formulae
    installed="$(brew_cask_versions 2>/dev/null || true)"
    while IFS= read -r line; do
        token="${line%% *}"
        [ -n "$token" ] && outdated="$outdated$token|"
    done <<EOF_BREW_OUTDATED_CASK_TOKENS
$OUTDATED_CASKS_PREFILTER
EOF_BREW_OUTDATED_CASK_TOKENS
    # Total = installed casks (plus any outdated one the listing missed) + outdated formulae.
    total="$(printf '%s\n' "$installed" | awk 'NF { print $1 }' | grep -c . || true)"
    for token in $(printf '%s\n' "$outdated" | tr '|' ' '); do
        printf '%s\n' "$installed" | awk -v t="$token" '$1 == t { f = 1 } END { exit !f }' || total=$((total + 1))
    done
    formula_count="$(printf '%s\n' "$OUTDATED_FORMULAE_PREFILTER" | grep -c '[^[:space:]]' || true)"
    mu_group_total brew "$((total + formula_count))"
    formulae="$(brew_formula_versions 2>/dev/null | grep -c . || true)"
    mu_group_checked brew "${formulae:-0}"
    while IFS= read -r line; do
        token="${line%% *}"
        [ -n "$token" ] || continue
        case "$seen" in *"|$token|"*) continue ;; esac
        seen="$seen$token|"
        case "$outdated" in *"|$token|"*) continue ;; esac
        ver="${line##* }"
        [ "$ver" = "$token" ] && ver=""
        mu_item_start brew "cask:$token" "$token" "$ver" "" homebrew
        case " $(printf '%s' "$ORPHAN_CASKS" | tr '\n' ' ') " in
            *" $token "*) mu_item_end brew "cask:$token" skipped "$ver" "" "installed cask whose app is missing" "" "$token" ;;
            *) mu_item_end brew "cask:$token" current "$ver" "$ver" "" "" "$token" ;;
        esac
    done <<EOF_BREW_INSTALLED_CASKS
$installed
EOF_BREW_INSTALLED_CASKS
}
brew_report_inventory

# brew_close_unprocessed <result> <reason> <detail> — the update was not run:
# every outdated item still open gets its item_end.
brew_close_unprocessed() {
    local token line
    for token in $OUTDATED_FORMULA_TOKENS; do
        mu_item_start brew "$token" "${token##*/}" "" "" homebrew
        mu_item_end brew "$token" "$1" "" "" "$3" "$2" "${token##*/}"
    done
    while IFS= read -r line; do
        token="${line%% *}"
        [ -n "$token" ] || continue
        mu_item_start brew "cask:$token" "$token" "" "" homebrew
        mu_item_end brew "cask:$token" "$1" "" "" "$3" "$2" "$token"
    done <<EOF_BREW_UNPROCESSED
$OUTDATED_CASKS
EOF_BREW_UNPROCESSED
}

BREW_HAS_OUTDATED=1
if [ -z "$OUTDATED_FORMULAE" ] && [ -z "$OUTDATED_CASKS" ]; then
    BREW_HAS_OUTDATED=0
    echo ""
    print_ok "$L_BREW_SUMMARY"
fi

# PREVIEW STOP: a dry run reports every outdated formula and cask from the same
# lists a real run upgrades (result "available" with installed -> new version)
# and ends before any upgrade, cleanup or uninstall.
if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
    BREW_PREVIEW_VERSIONS="$(HOMEBREW_NO_AUTO_UPDATE=1 brew outdated --json=v2 --greedy 2>/dev/null | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
for kind in ("formulae", "casks"):
    for row in data.get(kind) or []:
        name = str(row.get("name") or "")
        old = row.get("installed_versions") or [""]
        new = str(row.get("current_version") or "")
        if name:
            print("%s|%s|%s" % (name, str(old[-1] if isinstance(old, list) and old else old), new))
' 2>/dev/null || true)"
    brew_preview_versions() {
        printf '%s\n' "$BREW_PREVIEW_VERSIONS" | awk -F'|' -v t="$1" '$1 == t { print $2 "|" $3; exit }'
    }
    for _bp_token in $OUTDATED_FORMULA_TOKENS; do
        _bp_v="$(brew_preview_versions "${_bp_token##*/}")"
        print_info "[DRY-RUN] Would upgrade: $_bp_token ${_bp_v:+(${_bp_v%%|*} -> ${_bp_v#*|})}"
        mu_item_start brew "$_bp_token" "${_bp_token##*/}" "${_bp_v%%|*}" "${_bp_v#*|}" homebrew
        mu_item_end brew "$_bp_token" available "${_bp_v%%|*}" "${_bp_v#*|}" "would upgrade (brew upgrade)" "" "${_bp_token##*/}"
    done
    while IFS= read -r _bp_line; do
        _bp_token="${_bp_line%% *}"
        [ -n "$_bp_token" ] || continue
        _bp_v="$(brew_preview_versions "$_bp_token")"
        print_info "[DRY-RUN] Would upgrade: $_bp_token ${_bp_v:+(${_bp_v%%|*} -> ${_bp_v#*|})}"
        mu_item_start brew "cask:$_bp_token" "$_bp_token" "${_bp_v%%|*}" "${_bp_v#*|}" homebrew
        # The same open-app decision the real run makes: a background app is
        # quit and reopened (still available); a windowed open app is left to you.
        _bp_json="$(brew info --json=v2 --cask "$_bp_token" 2>/dev/null || true)"
        _bp_targets=""
        [ -n "$_bp_json" ] && _bp_targets="$(printf '%s' "$_bp_json" | brew_cask_guard_facts 2>/dev/null | cut -d'|' -f3)"
        _bp_decision=""
        if [ -n "$_bp_targets" ]; then
            _bp_decision="$(brew_cask_open_decision "$_bp_targets")"
        elif [ -n "$_bp_json" ]; then
            _bp_ids="$(printf '%s' "$_bp_json" | brew_cask_quit_ids 2>/dev/null || true)"
            _bp_open="$(brew_cask_running_quit_id "$_bp_ids")"
            # An unreadable cask record cannot tell: the preview stays "available".
            [ -n "$_bp_open" ] && [ "$_bp_open" != "UNREADABLE" ] && _bp_decision="defer|$_bp_open"
        fi
        case "$_bp_decision" in
            defer\|*)
                # Open but already at the cask's version (the app updated itself): current.
                _bp_path=""
                for _bp_dir in "/Applications" "$HOME/Applications"; do
                    [ -d "$_bp_dir/${_bp_decision#defer|}" ] && { _bp_path="$_bp_dir/${_bp_decision#defer|}"; break; }
                done
                if brew_app_already_at_cask_version "$_bp_path" "${_bp_v#*|}"; then
                    print_info "$(internet_msg "$L_BREW_CASK_SELF_UPDATED_FMT" "$_bp_token" "$(app_version "$_bp_path")")"
                    mu_item_end brew "cask:$_bp_token" current "${_bp_v%%|*}" "$(app_version "$_bp_path")" "already updated by the app itself" "" "$_bp_token"
                    continue
                fi
                print_warn "$(internet_msg "$L_BREW_CASK_RUNNING_FMT" "$_bp_token" "${_bp_v%%|*}" "${_bp_v#*|}" "${_bp_decision#defer|}")"
                mu_item_end brew "cask:$_bp_token" needs_you "${_bp_v%%|*}" "${_bp_v#*|}" "app is open: ${_bp_decision#defer|} (quit it and rerun)" app_running "$_bp_token"
                continue
                ;;
        esac
        mu_item_end brew "cask:$_bp_token" available "${_bp_v%%|*}" "${_bp_v#*|}" "would upgrade (brew upgrade --cask)" "" "$_bp_token"
    done <<EOF_BREW_PREVIEW_CASKS
$OUTDATED_CASKS
EOF_BREW_PREVIEW_CASKS
    [ "$BREW_HAS_OUTDATED" -eq 1 ] && print_info "$L_BREW_DRYRUN_WOULD_RUN_UPGRADE"
    exit "$(mac_update_severity_exit_code)"
fi

# ============================================================
# POTWIERDZENIE
# ============================================================
if [ "$BREW_HAS_OUTDATED" -eq 1 ]; then
echo ""
print_warn "$L_BREW_PACKAGES_FOUND"
# update_all.sh exports MAC_UPDATE_PARENT_CONFIRMED=1 after its own
# confirmation: asking again only stalls the run (2026-11-04: ~51 minutes).
if [ "${MAC_UPDATE_YES:-0}" != "1" ] && [ "${MAC_UPDATE_PARENT_CONFIRMED:-0}" != "1" ]; then
    if ! mac_update_prompt_yn "$L_BREW_CONFIRM_UPDATE " n y; then
        if [ "${MAC_UPDATE_PROMPT_TIMED_OUT:-0}" = "1" ]; then
            # Nobody answered: skip the upgrades, softly, and say why.
            print_warn "$L_BREW_UPDATE_TIMEOUT_SKIPPED"
            brew_close_unprocessed needs_you timeout "no answer; update not started"
            if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -d "$MAC_UPDATE_SESSION_DIR" ]; then
                printf '%s\n' "$(printf '%s\n' "$OUTDATED_FORMULAE" | grep -c . || true)" > "$MAC_UPDATE_SESSION_DIR/pending_brew_formulae"
                printf '%s\n' "$(printf '%s\n' "$OUTDATED_CASKS" | grep -c . || true)" > "$MAC_UPDATE_SESSION_DIR/pending_brew_casks"
            fi
            exit 10
        fi
        print_info "$L_BREW_UPDATE_CANCELED"
        brew_close_unprocessed skipped "" "update not confirmed"
        exit 0
    fi
fi

# ============================================================
# KROK 3: AKTUALIZACJA FORMULAE
# ============================================================
print_header "$L_BREW_UPGRADE_FORMULAE"
FORMULA_UPGRADE_FAILED=0

# Capture output so we can detect recoverable link conflicts
BREW_UPGRADE_LOG=$(mktemp "${TMPDIR:-/tmp}/brew_upgrade.XXXXXX") || {
    print_error "Could not create the Homebrew upgrade diagnostic log."
    exit 1
}
for _f in $OUTDATED_FORMULA_TOKENS; do
    mu_item_start brew "$_f" "${_f##*/}" "" "" homebrew
    mu_item_progress brew "$_f" installing
done
if [ -z "$OUTDATED_FORMULA_TOKENS" ]; then
    print_ok "$L_BREW_FORMULAE_OK"
elif if [ "$BREW_OVERRIDE_FILTERED" -eq 1 ]; then
        # Explicit names: user-overridden formulae stay untouched.
        # shellcheck disable=SC2086
        brew upgrade --formula $OUTDATED_FORMULA_TOKENS 2>&1 | tee "$BREW_UPGRADE_LOG"
    else
        brew upgrade --formula 2>&1 | tee "$BREW_UPGRADE_LOG"
    fi; then
    print_ok "$L_BREW_FORMULAE_OK"
else
    print_warn "$L_BREW_FORMULAE_WARN"
    HARD_FAIL=1
    FORMULA_UPGRADE_FAILED=1
fi

# ============================================================
# KROK 3.5: OPT-IN RECOVERY DLA "BREW LINK DID NOT COMPLETE"
# ============================================================
LINK_FAILED_KEGS=$(awk '
    /^==> Upgrading / {
        if ($0 !~ /outdated package/) { kegname = $3 }
        next
    }
    /Error: The .brew link. step did not complete successfully/ {
        if (kegname != "") { print kegname; kegname = "" }
    }
' "$BREW_UPGRADE_LOG" 2>/dev/null | sort -u)
rm -f "$BREW_UPGRADE_LOG" 2>/dev/null || true

if [ -n "$LINK_FAILED_KEGS" ] && [ "${MAC_UPDATE_BREW_LINK_OVERWRITE:-0}" != "1" ]; then
    print_warn "Homebrew reported unlinked kegs. Automatic 'brew link --overwrite' is disabled."
    print_info "Inspect the conflicting files first; set MAC_UPDATE_BREW_LINK_OVERWRITE=1 only for an explicit recovery run."
elif [ -n "$LINK_FAILED_KEGS" ]; then
    print_warn "$L_BREW_LINK_RECOVERY_DETECTED"
    RELINKED=0
    RELINK_FAILED=0
    while IFS= read -r keg; do
        keg=$(echo "$keg" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        [ -z "$keg" ] && continue
        case "$keg" in
            ""|*[!a-zA-Z0-9@+_./-]*) continue ;;
        esac
        echo -e "  ${CYAN}→ brew link --overwrite $keg${NC}"
        if brew link --overwrite "$keg" >/dev/null 2>&1; then
            print_ok "$L_BREW_LINK_RECOVERED $keg"
            RELINKED=$((RELINKED + 1))
        else
            print_warn "$L_BREW_LINK_FAILED $keg"
            RELINK_FAILED=$((RELINK_FAILED + 1))
        fi
    done <<EOF
$LINK_FAILED_KEGS
EOF
    if [ "$RELINKED" -gt 0 ] && [ "$RELINK_FAILED" -eq 0 ]; then
        if [ "$FORMULA_UPGRADE_FAILED" -eq 1 ]; then
            HARD_FAIL=0
        fi
        print_ok "$L_BREW_LINK_RECOVERY_OK"
    elif [ "$RELINK_FAILED" -gt 0 ]; then
        SOFT_FAIL=1
    fi
fi

# Guard against cask downgrades (when cask formula version < installed app version)
UPGRADEABLE_CASKS=""
DEFERRED_RUNNING_CASKS=""
SELF_UPDATED_CASKS=""
BG_QUIT_CASKS=""
if [ -n "$OUTDATED_CASKS" ]; then
    for cask in $(echo "$OUTDATED_CASKS" | awk '{print $1}'); do
        mu_item_start brew "cask:$cask" "$cask" "" "" homebrew
        cask_json=$(brew info --json=v2 --cask "$cask" 2>/dev/null || true)
        cask_ver=""
        cask_app_name=""
        cask_recorded_ver=""
        targets_str=""
        if [ -n "$cask_json" ]; then
            parsed="$(printf '%s' "$cask_json" | brew_cask_guard_facts || true)"
            cask_ver=$(echo "$parsed" | cut -d'|' -f1)
            cask_recorded_ver=$(echo "$parsed" | cut -d'|' -f2)
            targets_str=$(echo "$parsed" | cut -d'|' -f3)
        fi

        # Homebrew's own record of what it installed is the only like-for-like
        # operand for the cask version. Prefer it; the bundle version is a
        # fallback and may use a different scheme entirely.
        if [ -n "$cask_recorded_ver" ] && [ -n "$cask_ver" ]; then
            if [ "$(internet_version_relation "$cask_recorded_ver" "$cask_ver")" = "newer" ]; then
                print_warn "$(internet_msg "$L_BREW_CASK_WOULD_DOWNGRADE_FMT" "$cask" "$cask_ver" "$cask_recorded_ver")"
                mu_item_end brew "cask:$cask" current "$cask_recorded_ver" "$cask_ver" "installed version is newer than the cask" "" "$cask"
                SOFT_FAIL=1
                continue
            fi
        fi

        cask_app_path=""
        if [ -n "$targets_str" ]; then
            while IFS= read -r t_name; do
                [ -n "$t_name" ] || continue
                for dir in "/Applications" "$HOME/Applications"; do
                    if [ -d "$dir/$t_name" ]; then
                        cask_app_path="$dir/$t_name"
                        break 2
                    fi
                done
            done <<EOF_TARGETS
$(echo "$targets_str" | tr ';' '\n')
EOF_TARGETS
            if [ -z "$cask_app_path" ]; then
                # Cask declares app targets, but none exist on disk -> skip
                mu_item_end brew "cask:$cask" skipped "" "" "app not found on disk" "" "$cask"
                continue
            fi
        else
            # Only casks without app targets use Caskroom fallback
            prefix="$(brew --prefix 2>/dev/null || echo "/opt/homebrew")"
            cask_app_path=$(find "$prefix/Caskroom/$cask" -maxdepth 3 -name "*.app" 2>/dev/null | head -1)
        fi

        if [ -n "$cask_app_path" ] && [ -d "$cask_app_path" ]; then
            installed_ver=$(app_version "$cask_app_path")
            if [ -n "$installed_ver" ] && [ -n "$cask_ver" ]; then
                # Scheme-aware: a bundle version such as Brave's
                # "151.1.93.138" carries the Chromium major in front of the
                # cask's own "1.93.138.0". Comparing them digit by digit read
                # the app as newer and skipped the upgrade on every run.
                rel=$(app_vs_package_version_relation "$installed_ver" "$cask_ver" 2>/dev/null || echo "unknown")
                if [ "$rel" = "newer" ]; then
                    print_warn "$(internet_msg "$L_BREW_CASK_WOULD_DOWNGRADE_FMT" "$cask" "$cask_ver" "$installed_ver")"
                    mu_item_end brew "cask:$cask" current "$installed_ver" "$cask_ver" "installed version is newer than the cask" "" "$cask"
                    SOFT_FAIL=1
                    continue
                fi
                if [ "$rel" = "unknown" ]; then
                    print_info "$(internet_msg "$L_BREW_CASK_VERSION_SCHEME_INFO_FMT" "$cask" "$installed_ver" "$cask_ver")"
                fi
            fi
        fi
        # An app that is open is never replaced (critical_rules 15). Unknown
        # running state defers too, exactly like the app-copy transaction.
        deferred_app=""
        quit_spec=""
        if [ -n "$targets_str" ]; then
            decision="$(brew_cask_open_decision "$targets_str")"
            case "$decision" in
                defer\|*) deferred_app="${decision#defer|}" ;;
                quit\|*) quit_spec="${decision#quit|}" ;;
            esac
        elif [ -z "$cask_json" ]; then
            deferred_app="UNREADABLE"
        else
            # No app target (pkg casks): honour the quit/signal bundle IDs the
            # cask itself declares; none declared (fonts, drivers, CLIs) -> upgrade.
            deferred_app="$(printf '%s' "$cask_json" | brew_cask_quit_ids)"
            deferred_app="$(brew_cask_running_quit_id "$deferred_app")"
        fi
        # The app is open and already at the cask's version: its own updater got
        # there first. Nothing to upgrade, nothing to quit, nothing to warn about
        # (Homebrew's receipt stays as it is; brew upgrade is never run for it).
        if [ -n "$deferred_app" ] && [ "$deferred_app" != "UNREADABLE" ] && brew_app_already_at_cask_version "$cask_app_path" "$cask_ver"; then
            print_info "$(internet_msg "$L_BREW_CASK_SELF_UPDATED_FMT" "$cask" "$(app_version "$cask_app_path")")"
            mu_item_end brew "cask:$cask" current "${cask_recorded_ver:-}" "$(app_version "$cask_app_path")" "already updated by the app itself" "" "$cask"
            SELF_UPDATED_CASKS="$SELF_UPDATED_CASKS $cask"
            continue
        fi
        if [ -n "$deferred_app" ]; then
            print_warn "$(internet_msg "$L_BREW_CASK_RUNNING_FMT" "$cask" "${cask_recorded_ver:-?}" "${cask_ver:-?}" "$deferred_app")"
            if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -d "$MAC_UPDATE_SESSION_DIR" ]; then
                echo "$cask|$deferred_app" >> "$MAC_UPDATE_SESSION_DIR/brew_deferred_running.txt"
            fi
            DEFERRED_RUNNING_CASKS="$DEFERRED_RUNNING_CASKS $cask"
            mu_item_end brew "cask:$cask" needs_you "${cask_recorded_ver:-}" "${cask_ver:-}" "app is open: $deferred_app (quit it and rerun)" app_running "$cask"
            SOFT_FAIL=1
            continue
        fi
        if [ -n "$quit_spec" ]; then
            # A background / menu-bar app is open: it is quit politely right
            # before its upgrade and reopened right after (see below).
            BG_QUIT_CASKS="$BG_QUIT_CASKS
$cask|$quit_spec"
        fi
        UPGRADEABLE_CASKS="$UPGRADEABLE_CASKS $cask"
        if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -d "$MAC_UPDATE_SESSION_DIR" ]; then
            if [ -n "$targets_str" ]; then
                while IFS= read -r t_target; do
                    [ -n "$t_target" ] || continue
                    echo "$cask|$t_target" >> "$MAC_UPDATE_SESSION_DIR/brew_cask_targets.txt"
                done <<EOF_SESSION_TARGETS
$(echo "$targets_str" | tr ';' '\n')
EOF_SESSION_TARGETS
            fi
        fi
    done
fi

if [ -n "$UPGRADEABLE_CASKS" ]; then
    # shellcheck disable=SC2086
    SUDO_CASKS="$(brew_casks_requiring_sudo $UPGRADEABLE_CASKS 2>/dev/null || true)"
    # Casks whose installer needs root run only with a valid sudo timestamp
    # (the run's single authorization). Homebrew's own sudo never asks for a
    # typed password mid-run (SUDO_ASKPASS refuses), so without the timestamp
    # these casks are left for the user instead of failing or prompting.
    if [ -n "$SUDO_CASKS" ] && [ "${MAC_UPDATE_NO_SUDO:-0}" != "1" ] \
       && mu_sudo_ensure "${L_BREW_SUDO_PURPOSE:-Homebrew apps that need administrator rights}"; then
        SUDO_CASKS=""
    fi
    if [ -n "$SUDO_CASKS" ]; then
        for scask in $SUDO_CASKS; do
            [ -n "$scask" ] || continue
            print_warn "$(printf "$L_BREW_CASK_NEEDS_INTERACTIVE_FMT" "$scask")"
            mu_item_end brew "cask:$scask" needs_you "" "" "needs an administrator password" needs_password "$scask"
            if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -d "$MAC_UPDATE_SESSION_DIR" ]; then
                echo "$scask" >> "$MAC_UPDATE_SESSION_DIR/brew_needs_interactive.txt"
            fi
            SOFT_FAIL=1
            UPGRADEABLE_CASKS="$(echo "$UPGRADEABLE_CASKS" | tr ' ' '\n' | awk -v s="$scask" '$1 != s' | tr '\n' ' ' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        done
    fi
fi

if [ -n "$UPGRADEABLE_CASKS" ]; then
    # One cask per command: a failing cask never stops the others.
    _cask_failures=0
    for _cask in $UPGRADEABLE_CASKS; do
        mu_item_progress brew "cask:$_cask" installing
        _bg_ids=""
        _bg_name=""
        _bg_line="$(printf '%s\n' "$BG_QUIT_CASKS" | awk -F'|' -v c="$_cask" '$1 == c { print; exit }')"
        if [ -n "$_bg_line" ]; then
            _bg_ids="$(printf '%s' "$_bg_line" | cut -d'|' -f2)"
            _bg_name="$(printf '%s' "$_bg_line" | cut -d'|' -f3-)"
            if ! brew_quit_background_apps "$_cask" "$_bg_ids"; then
                # Not closed in time: today's result, and nothing was replaced.
                brew_relaunch_background_apps "$_cask" "$_bg_ids"
                print_warn "$(internet_msg "$L_BREW_CASK_RUNNING_FMT" "$_cask" "?" "?" "$_bg_name")"
                DEFERRED_RUNNING_CASKS="$DEFERRED_RUNNING_CASKS $_cask"
                mu_item_end brew "cask:$_cask" needs_you "" "" "app is open: $_bg_name (quit it and rerun)" app_running "$_cask"
                SOFT_FAIL=1
                continue
            fi
        fi
        if brew upgrade --cask "$_cask"; then
            _cask_rc=0
        else
            _cask_rc=1
        fi
        [ -n "$_bg_ids" ] && brew_relaunch_background_apps "$_cask" "$_bg_ids"
        if [ "$_cask_rc" -eq 0 ]; then
            mu_item_end brew "cask:$_cask" updated "" "" "" "" "$_cask"
        else
            _cask_failures=$((_cask_failures + 1))
            mu_item_end brew "cask:$_cask" failed "" "" "brew upgrade --cask failed" unknown "$_cask"
        fi
    done
    if [ "$_cask_failures" -eq 0 ]; then
        print_ok "$L_BREW_CASKS_OK"
    else
        print_warn "$L_BREW_CASKS_WARN"
        HARD_FAIL=1
    fi
elif [ -z "$DEFERRED_RUNNING_CASKS" ]; then
    print_ok "$L_BREW_CASKS_OK"
fi
fi

# A successful upgrade is not enough: query Homebrew again and fail if any
# formula or greedy cask remains outdated, or if verification itself fails.
print_header "$L_BREW_OUTDATED"
if ! REMAINING_FORMULAE=$(brew_outdated_formulae | strip_ansi); then
    print_warn "Final brew outdated --formula verification failed."
    [ -n "$REMAINING_FORMULAE" ] && printf '%s\n' "$REMAINING_FORMULAE"
    SOFT_FAIL=1
elif [ -n "$REMAINING_FORMULAE" ]; then
    print_error "Formulae still outdated after upgrade:"
    printf '%s\n' "$REMAINING_FORMULAE"
    HARD_FAIL=1
fi
for _f in $OUTDATED_FORMULA_TOKENS; do
    if printf '%s\n' "$REMAINING_FORMULAE" | awk -v f="$_f" '$1 == f { found = 1 } END { exit !found }'; then
        mu_item_end brew "$_f" failed "" "" "still outdated after brew upgrade" unknown "${_f##*/}"
    else
        mu_item_end brew "$_f" updated "" "" "" "" "${_f##*/}"
    fi
done
# shellcheck disable=SC2086
if ! REMAINING_CASKS=$(brew_outdated_casks $GREEDY_TOKENS | strip_ansi); then
    print_warn "Final brew outdated --cask --greedy-auto-updates verification failed."
    [ -n "$REMAINING_CASKS" ] && printf '%s\n' "$REMAINING_CASKS"
    SOFT_FAIL=1
else
    # Casks deferred because their app is open were already reported (and
    # recorded in brew_deferred_running.txt); do not report them a second time.
    # A cask whose open app already updated itself is current, not pending.
    for dcask in $DEFERRED_RUNNING_CASKS $SELF_UPDATED_CASKS; do
        REMAINING_CASKS="$(printf '%s\n' "$REMAINING_CASKS" | awk -v c="$dcask" '$1 != c')"
    done
    REMAINING_CASKS="$(printf '%s\n' "$REMAINING_CASKS" | grep -v '^[[:space:]]*$' || true)"
fi
if [ -n "$REMAINING_CASKS" ]; then
    print_info "Casks listed in greedy outdated check (informational only):"
    printf '%s\n' "$REMAINING_CASKS"
fi
if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ]; then
    PENDING_BREW_FORMULAE="$(printf '%s\n' "$REMAINING_FORMULAE" | wc -l | tr -d ' ')"
    PENDING_BREW_CASKS="$(printf '%s\n' "$REMAINING_CASKS" | wc -l | tr -d ' ')"
    [ -n "$REMAINING_FORMULAE" ] || PENDING_BREW_FORMULAE=0
    [ -n "$REMAINING_CASKS" ] || PENDING_BREW_CASKS=0
    # Deferred (app open) casks are still pending: count them, the run summary
    # lists each one from brew_deferred_running.txt.
    DEFERRED_COUNT=0
    for dcask in $DEFERRED_RUNNING_CASKS; do DEFERRED_COUNT=$((DEFERRED_COUNT + 1)); done
    PENDING_BREW_CASKS=$((PENDING_BREW_CASKS + DEFERRED_COUNT))
    printf '%s\n' "$PENDING_BREW_FORMULAE" > "$MAC_UPDATE_SESSION_DIR/pending_brew_formulae"
    printf '%s\n' "$PENDING_BREW_CASKS" > "$MAC_UPDATE_SESSION_DIR/pending_brew_casks"
fi
if [ "$HARD_FAIL" -eq 0 ] && [ "$SOFT_FAIL" -eq 0 ]; then
    print_ok "$L_BREW_SUMMARY"
fi

# ============================================================
# KROK 5: SPRAWDZENIE PROBLEMÓW
# ============================================================
if [ "${MAC_UPDATE_SKIP_DOCTOR:-0}" = "1" ]; then
    print_info "$L_BREW_DOCTOR_SKIPPED"
else
print_header "$L_BREW_HEALTH_CHECKING"

DOCTOR_OUT=$(brew doctor 2>&1 | strip_ansi)
DOCTOR_EXIT=$?
if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
    printf '%s\n' "$DOCTOR_OUT" > "$MAC_UPDATE_SESSION_DIR/brew_doctor.txt"
fi

UNLINKED_KEGS=$(echo "$DOCTOR_OUT" | awk '
    /You have unlinked kegs in your Cellar/ { in_block = 1; next }
    in_block && /^$/ { in_block = 0; next }
    in_block && /^Leaving kegs unlinked/ { next }
    in_block && /^Run .brew link./ { next }
    in_block && /^  [a-zA-Z]/ { gsub(/^[[:space:]]+|[[:space:]]+$/, ""); print }
')
if [ -n "$UNLINKED_KEGS" ] && [ "${MAC_UPDATE_BREW_LINK_OVERWRITE:-0}" != "1" ]; then
    print_warn "brew doctor found unlinked kegs; automatic overwrite recovery is disabled."
    print_info "Set MAC_UPDATE_BREW_LINK_OVERWRITE=1 only after reviewing the conflicts."
elif [ -n "$UNLINKED_KEGS" ]; then
    print_info "$L_BREW_DOCTOR_UNLINKED_FOUND"
    RELINKED2=0
    while IFS= read -r keg; do
        [ -z "$keg" ] && continue
        case "$keg" in
            ""|*[!a-zA-Z0-9@+_./-]*) continue ;;
        esac
        if brew link --overwrite "$keg" >/dev/null 2>&1; then
            print_ok "$L_BREW_LINK_RECOVERED $keg"
            RELINKED2=$((RELINKED2 + 1))
        fi
    done <<EOF
$UNLINKED_KEGS
EOF
    if [ "$RELINKED2" -gt 0 ]; then
        DOCTOR_OUT=$(brew doctor 2>&1 | strip_ansi)
        DOCTOR_EXIT=$?
        if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
            printf '%s\n' "$DOCTOR_OUT" > "$MAC_UPDATE_SESSION_DIR/brew_doctor.txt"
        fi
    fi
fi

DOCTOR_FILTERED=$(printf '%s\n' "$DOCTOR_OUT" | awk '
    function emit_dylib_block() {
        if (!(dylib_paths == 1 && asaf_paths == 1)) {
            printf "%s", dylib_block
        }
        in_dylib_block = 0
        dylib_block = ""
        dylib_paths = 0
        asaf_paths = 0
    }
    function emit_clt_block() {
        if (!clt_emitted) {
            printf "Warning: Command Line Tools (CLT) requires update/reinstall (details in brew_doctor.txt)\n"
            clt_emitted = 1
        }
        in_clt_block = 0
    }
    in_clt_block && /^(Warning:|Error:)/ {
        emit_clt_block()
        if ($0 ~ /^Warning: .*Command Line Tools/) {
            in_clt_block = 1
            next
        }
    }
    in_clt_block {
        next
    }
    /^Warning: .*Command Line Tools/ {
        if (in_dylib_block) emit_dylib_block()
        in_clt_block = 1
        next
    }
    /^Warning: Unbrewed dylibs were found in \/usr\/local\/lib/ {
        in_dylib_block = 1
        dylib_block = $0 ORS
        next
    }
    in_dylib_block && /^(Warning:|Error:)/ {
        emit_dylib_block()
        print
        next
    }
    in_dylib_block {
        dylib_block = dylib_block $0 ORS
        if ($0 ~ /^[[:space:]]+\/usr\/local\/lib\//) {
            dylib_path = $0
            sub(/^[[:space:]]+/, "", dylib_path)
            dylib_paths++
            if (dylib_path == "/usr/local/lib/libASAF.dylib") asaf_paths++
        }
        next
    }
    { print }
    END {
        if (in_dylib_block) emit_dylib_block()
        if (in_clt_block) emit_clt_block()
    }
')

# Keep libASAF dylib filter in place for now.
# TODO(C2): libASAF dylib filter can be removed once severity is corrected across scripts.
ASAF_ONLY_FILTERED=0
if [ "$DOCTOR_FILTERED" != "$DOCTOR_OUT" ]; then
    ASAF_ONLY_FILTERED=1
fi
REAL_WARNINGS=$(printf '%s\n' "$DOCTOR_FILTERED" | grep '^Warning:' 2>/dev/null || true)
DOCTOR_ERRORS=$(printf '%s\n' "$DOCTOR_FILTERED" | grep '^Error:' 2>/dev/null || true)

if [ -n "$DOCTOR_ERRORS" ]; then
    [ -n "$DOCTOR_FILTERED" ] && printf '%s\n' "$DOCTOR_FILTERED"
    print_warn "$L_BREW_HEALTH_WARN"
    SOFT_FAIL=1
elif [ -n "$REAL_WARNINGS" ]; then
    [ -n "$DOCTOR_FILTERED" ] && printf '%s\n' "$DOCTOR_FILTERED"
    # Advisories are recorded for the run summary (source|severity|text) and
    # shown instead of the unconditional "good condition" line. They stay
    # non-blocking: surfacing, not soft-failing every run.
    DOCTOR_ADVISORIES="$(printf '%s\n' "$DOCTOR_FILTERED" | brew_doctor_advisories)"
    if [ -n "$DOCTOR_ADVISORIES" ]; then
        if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -d "$MAC_UPDATE_SESSION_DIR" ]; then
            printf '%s\n' "$DOCTOR_ADVISORIES" >> "$MAC_UPDATE_SESSION_DIR/advisories.txt"
        fi
        ADVISORY_COUNT="$(printf '%s\n' "$DOCTOR_ADVISORIES" | grep -c . || true)"
    else
        ADVISORY_COUNT="$(printf '%s\n' "$REAL_WARNINGS" | grep -c . || true)"
    fi
    # shellcheck disable=SC2059
    print_info "$(printf "$L_BREW_DOCTOR_ADVISORIES_FMT" "$ADVISORY_COUNT")"
    printf '%s\n' "$DOCTOR_ADVISORIES" | while IFS='|' read -r _src sev text; do
        [ "$sev" = "security" ] || continue
        print_warn "$(internet_msg "$L_BREW_DOCTOR_SECURITY_FMT" "$text")"
    done
else
    print_ok "$L_BREW_HEALTH_OK"
    if [ "$ASAF_ONLY_FILTERED" -eq 1 ]; then
        print_info "$L_BREW_DYLIB_FILTERED_INFO"
        print_info "$L_BREW_DYLIB_INFO"
    fi
fi
fi

# ============================================================
# KROK 6: CZYSZCZENIE
# ============================================================
print_header "$L_BREW_CACHE_CLEANING"

CACHE_DIR=$(brew --cache 2>/dev/null || echo "")
CLEANUP_OUT=$(brew cleanup --prune=all 2>&1 | strip_ansi)
CLEANUP_EXIT=$?
if [ -n "$MAC_UPDATE_SESSION_DIR" ] && [ -n "$CLEANUP_OUT" ]; then
    echo "$CLEANUP_OUT" >> "$MAC_UPDATE_SESSION_DIR/brew_cleanup.log"
fi
if [ "$CLEANUP_EXIT" -eq 0 ]; then
    if echo "$CLEANUP_OUT" | grep -qi "warning"; then
        print_warn "Homebrew cleanup completed with warnings."
    elif [ -z "$CLEANUP_OUT" ] || echo "$CLEANUP_OUT" | grep -qi "Nothing to remove"; then
        print_info "Homebrew cleanup: no obsolete cache to clean."
    else
        if [ -n "$CACHE_DIR" ] && [ -d "$CACHE_DIR" ]; then
            CACHE_SIZE=$(du -sh "$CACHE_DIR" 2>/dev/null | awk '{print $1}' || echo "?")
            print_ok "$L_BREW_CACHE_CLEANED (~$CACHE_SIZE)"
        else
            print_ok "$L_BREW_CACHE_CLEANED"
        fi
    fi
else
    print_warn "Homebrew cleanup failed."
    SOFT_FAIL=1
fi

# ============================================================
# PODSUMOWANIE
# ============================================================
print_header "$L_BREW_INSTALLED_TITLE"

echo -e "${CYAN}Formulae:${NC}"
brew list --formula --versions 2>/dev/null | column -t || brew list --formula --versions

echo ""
echo -e "${CYAN}Casks:${NC}"
brew_cask_versions | column -t || brew_cask_versions

# ── Snapshot wersji zainstalowanych pakietów PO aktualizacji ──
if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
    print_info "$L_BREW_SAVING_SNAPSHOT"
    BREW_SNAPSHOT_OK=1
    if ! brew list --formula --versions 2>/dev/null | strip_ansi > "$MAC_UPDATE_SESSION_DIR/brew_formulae_after.txt"; then
        print_warn "Could not save the post-update formula snapshot."
        BREW_SNAPSHOT_OK=0
        SOFT_FAIL=1
    fi
    if ! brew_cask_versions | strip_ansi > "$MAC_UPDATE_SESSION_DIR/brew_casks_after.txt"; then
        print_warn "Could not save the post-update cask snapshot."
        BREW_SNAPSHOT_OK=0
        SOFT_FAIL=1
    fi
    if [ "$BREW_SNAPSHOT_OK" -eq 1 ]; then
        print_ok "$L_BREW_SNAPSHOTS_SAVED_TO $MAC_UPDATE_SESSION_DIR"
    fi
fi

BREW_FINAL_EXIT="$(mac_update_severity_exit_code)"
if [ "$BREW_FINAL_EXIT" -eq 0 ]; then
    print_header "$L_BREW_SCRIPT_DONE"
    echo -e "  ${GREEN}$L_BREW_ALL_DONE${NC}"
else
    # Never print the "COMPLETED SUCCESSFULLY" banner above a non-zero exit —
    # the 2026-08-19 run log showed "SKRYPT 4 ZAKOŃCZONY POMYŚLNIE" directly
    # above "Homebrew finished with errors", which sends the reader hunting in
    # the wrong place.
    print_header "$(app_label Homebrew Homebrew)"
    if [ "$BREW_FINAL_EXIT" -eq "$MAC_UPDATE_SOFT_EXIT" ]; then
        print_warn "Homebrew finished with soft warnings (non-blocking). Review output above."
    else
        print_error "Homebrew finished with errors. Review output above."
    fi
fi
echo ""
exit "$BREW_FINAL_EXIT"
