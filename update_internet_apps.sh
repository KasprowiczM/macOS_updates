#!/usr/bin/env bash
# shellcheck disable=SC2329  # Helpers are invoked by the sourced dispatch module and traps.
# ============================================================
# SCRIPT 5: Update internet-downloaded applications
# ============================================================
# Autor: mk | Data: 2026-03-18 (zaktualizowano)
set -o pipefail

# Kompatybilność: bash 3.2+ (macOS domyślny shell, Apple Silicon arm64)
#
# Aplikacje objęte skryptem:
#   PRZEGLĄDARKI:     Google Chrome, Firefox Dev Edition, Brave
#   AI:               ChatGPT, Claude, Gemini, Comet, Perplexity Desktop,
#                     Antigravity, Antigravity IDE, LM Studio, Codex, OpenCode Desktop
#   VPN/BEZP.:        ProtonVPN, KeePassXC
#   POCZTA/KOMUN.:    Proton Mail, Zoom
#   CHMURA:           Google Drive, MEGAsync, Proton Drive
#   MICROSOFT 365:    Word, Excel, PowerPoint, Outlook, OneNote (via msupdate)
#   TEAMS:            built-in updater + observed MAU fallback (TEAMS21)
#   DEV TOOLS:        VS Code, CodeEdit, Docker Desktop, Warp, Cursor
#   PRODUKTYWNOŚĆ:    AppCleaner, Obsidian
#   MULTIMEDIA:       Spotify
#   KRYPTO:           Ledger Live/Wallet, Trezor Suite
#   SIEĆ/IT:          Remote Desktop Manager
#
#   * = tylko powiadomienie/informacja, wymagana ręczna aktualizacja
#
# Metody aktualizacji:
#   - GitHub API + pobieranie DMG: Firefox Dev Edition, KeePassXC,
#     CodeEdit, Trezor Suite (arm64)
#   - Google Keystone agent: Google Chrome, Google Drive
#   - Microsoft AutoUpdate (msupdate CLI): cały pakiet Microsoft 365
#   - Docker Desktop CLI: docker desktop update (v4.37+)
#   - Wbudowany auto-updater (silent_launch_app → open -gjF): większość pozostałych
#     Apps są uruchamiane w tle ukryte; Sparkle/Squirrel/Omaha/Electron i tak
#     wykonują sprawdzenie aktualizacji przy starcie, bez aktywacji okna.
# ============================================================

# Kolory
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m'

# Katalog z skryptami
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Shared libraries ─────────────────────────────────────────
. "$SCRIPT_DIR/lib/internet_apps.sh"
. "$SCRIPT_DIR/lib/brew.sh"
. "$SCRIPT_DIR/lib/internet_registry.sh"
. "$SCRIPT_DIR/lib/internet_handlers.sh"
. "$SCRIPT_DIR/lib/github_release.sh"
. "$SCRIPT_DIR/lib/internet_i18n.sh"
. "$SCRIPT_DIR/lib/version.sh"
. "$SCRIPT_DIR/lib/platform.sh"
. "$SCRIPT_DIR/lib/internet_status.sh"

mac_update_require_supported_platform || exit 1
. "$SCRIPT_DIR/lib/ui.sh"

# ── i18n: load language strings ──────────────────────────────
. "$SCRIPT_DIR/i18n/loader.sh"

print_header() { ui_print_header "$1"; }



# ── Severity contract with update_all.sh (see its comment block) ──
#   0  = clean
#   10 = soft/degraded — nothing is known to be broken, something could not be
#        verified (offline, vendor updater unreachable, launch refused). MUST
#        NOT defer the final macOS system update.
#   1  = hard failure — a download/install actually broke and may have left an
#        application bundle mid-replacement.
INTERNET_SOFT_EXIT=10
INTERNET_EXIT=0
INTERNET_HARD_FAIL=0
INTERNET_SOFT_FAIL=0
INTERNET_TEMP_ROOT="${MAC_UPDATE_SESSION_DIR:-}"
INTERNET_TEMP_OWNED=0
if [ -z "$INTERNET_TEMP_ROOT" ]; then
    INTERNET_TEMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/mac_update_internet.XXXXXX")"
    INTERNET_TEMP_OWNED=1
fi
chmod 700 "$INTERNET_TEMP_ROOT" 2>/dev/null || true
INTERNET_MOUNT_TRACK_FILE="$(mktemp "$INTERNET_TEMP_ROOT/mounted_dmgs.XXXXXX")" || {
    print_error "Cannot create DMG mount tracking file in $INTERNET_TEMP_ROOT"
    if [ "$INTERNET_TEMP_OWNED" -eq 1 ]; then
        rm -rf "$INTERNET_TEMP_ROOT" 2>/dev/null || true
    fi
    exit 1
}

# Startup sweep for orphaned staging/backup directories in /Applications (REPORT ONLY)
for orphaned in /Applications/.macupd_staging.* /Applications/.macupd_backup.*; do
    if [ -d "$orphaned" ]; then
        print_warn "Orphaned staging or backup directory detected from previous run: $orphaned"
    fi
done

cleanup_internet_temp() {
    local mount_cleanup_failed=0
    if [ -f "${INTERNET_MOUNT_TRACK_FILE:-}" ]; then
        while IFS= read -r mount_point; do
            [ -n "$mount_point" ] || continue
            case "$mount_point" in
                "$INTERNET_TEMP_ROOT"/dmg_mount.*)
                    if hdiutil detach "$mount_point" -quiet >/dev/null 2>&1 \
                        || ! mount | grep -Fq " on $mount_point ("; then
                        rm -rf "$mount_point" 2>/dev/null || true
                    else
                        mount_cleanup_failed=1
                        internet_diag_log "WARN: mount still active after cleanup: $mount_point"
                    fi
                    ;;
            esac
        done < "$INTERNET_MOUNT_TRACK_FILE"
        if [ "$mount_cleanup_failed" -eq 0 ]; then
            rm -f "$INTERNET_MOUNT_TRACK_FILE" 2>/dev/null || true
        fi
    fi
    if [ "$INTERNET_TEMP_OWNED" -eq 1 ] && [ "$mount_cleanup_failed" -eq 0 ]; then
        case "$INTERNET_TEMP_ROOT" in
            "${TMPDIR:-/tmp}"/mac_update_internet.*|/tmp/mac_update_internet.*)
                rm -rf "$INTERNET_TEMP_ROOT" 2>/dev/null || true
                ;;
        esac
    fi
}
trap cleanup_internet_temp EXIT

make_temp_dmg() {
    mktemp "$INTERNET_TEMP_ROOT/$1.XXXXXX.dmg"
}

verify_dmg() {
    local dmg_path="$1"
    hdiutil verify "$dmg_path" -quiet >/dev/null 2>&1
}

# Mount a verified DMG read-only at a unique path controlled by this session.
# Handlers can capture the printed path and pass it to detach_verified_dmg.
mount_verified_dmg() {
    local dmg_path="$1"
    local mount_point

    if ! verify_dmg "$dmg_path"; then
        internet_diag_log "ERROR: hdiutil verify failed for $dmg_path"
        return 1
    fi
    mount_point="$(mktemp -d "$INTERNET_TEMP_ROOT/dmg_mount.XXXXXX")" || return 1
    if ! hdiutil attach "$dmg_path" -nobrowse -readonly -mountpoint "$mount_point" -quiet >/dev/null 2>&1; then
        internet_diag_log "ERROR: hdiutil attach failed for $dmg_path at $mount_point"
        rm -rf "$mount_point" 2>/dev/null || true
        return 1
    fi
    if ! printf '%s\n' "$mount_point" >> "$INTERNET_MOUNT_TRACK_FILE"; then
        hdiutil detach "$mount_point" -quiet >/dev/null 2>&1 || true
        rm -rf "$mount_point" 2>/dev/null || true
        return 1
    fi
    printf '%s\n' "$mount_point"
}

detach_verified_dmg() {
    local mount_point="$1"
    [ -n "$mount_point" ] || return 1
    case "$mount_point" in
        "$INTERNET_TEMP_ROOT"/dmg_mount.*) ;;
        *)
            internet_diag_log "ERROR: refused to detach unmanaged mount point: $mount_point"
            return 1
            ;;
    esac
    if ! hdiutil detach "$mount_point" -quiet >/dev/null 2>&1; then
        internet_diag_log "WARN: hdiutil detach failed for $mount_point"
        return 1
    fi
    rm -rf "$mount_point" 2>/dev/null || true
    return 0
}

verify_app_signature() {
    local app_path="$1"
    spctl --assess --type execute "$app_path" >/dev/null 2>&1
}

app_bundle_identifier() {
    local app_path="$1"
    local identifier
    identifier="$(codesign -dv --verbose=4 "$app_path" 2>&1 \
        | sed -n 's/^Identifier=//p' | head -1)"
    if [ -z "$identifier" ]; then
        identifier="$(defaults read "$app_path/Contents/Info" CFBundleIdentifier 2>/dev/null || true)"
    fi
    printf '%s\n' "$identifier"
}

app_team_identifier() {
    local app_path="$1"
    codesign -dv --verbose=4 "$app_path" 2>&1 \
        | sed -n 's/^TeamIdentifier=//p' | head -1
}

verify_replacement_identity() {
    local new_app="$1"
    local installed_app="$2"
    local app_label="$3"
    local new_bundle old_bundle new_team old_team

    new_bundle="$(app_bundle_identifier "$new_app")"
    old_bundle="$(app_bundle_identifier "$installed_app")"
    new_team="$(app_team_identifier "$new_app")"
    old_team="$(app_team_identifier "$installed_app")"

    if [ -z "$new_bundle" ] || [ -z "$old_bundle" ] \
        || [ -z "$new_team" ] || [ -z "$old_team" ]; then
        print_warn "Cannot verify bundle/team identity for $app_label; refusing replacement"
        internet_diag_log "ERROR: missing signing identity for $app_label (old bundle=$old_bundle team=$old_team; new bundle=$new_bundle team=$new_team)"
        return 1
    fi
    if [ "$new_bundle" != "$old_bundle" ] || [ "$new_team" != "$old_team" ]; then
        print_warn "Signing identity mismatch for $app_label; refusing replacement"
        internet_diag_log "ERROR: identity mismatch for $app_label (old bundle=$old_bundle team=$old_team; new bundle=$new_bundle team=$new_team)"
        return 1
    fi
    return 0
}

copy_verified_app() {
    if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
        print_warn "[DRY-RUN] skip copy: $2"
        return 0
    fi
    local app_path="$1"
    local app_label="$2"
    local dest="/Applications/$app_label"
    local app_name
    local staging_root staging backup_root backup rejected
    local had_existing=0

    if ! verify_app_signature "$app_path"; then
        print_warn "$(internet_msg "$L_INTERNET_GATEKEEPER_REJECTED" "$app_label")"
        return 1
    fi

    # mktemp prevents collisions with concurrent/stale runs. The staging and
    # backup roots live beside the destination so every mv stays on one volume.
    staging_root="$(mktemp -d "/Applications/.macupd_staging.XXXXXX")" || return 1
    backup_root="$(mktemp -d "/Applications/.macupd_backup.XXXXXX")" || {
        rm -rf "$staging_root" 2>/dev/null || true
        return 1
    }
    staging="$staging_root/$app_label"
    backup="$backup_root/$app_label"
    if ! ditto "$app_path" "$staging" 2>/dev/null; then
        rm -rf "$staging_root" "$backup_root" 2>/dev/null || true
        return 1
    fi
    if ! verify_app_signature "$staging"; then
        print_warn "Staged signature check failed for $app_label"
        internet_diag_log "ERROR: staged spctl failed for $staging"
        rm -rf "$staging_root" "$backup_root" 2>/dev/null || true
        return 1
    fi
    if [ -e "$dest" ] || [ -L "$dest" ]; then
        if ! verify_replacement_identity "$staging" "$dest" "$app_label"; then
            rm -rf "$staging_root" "$backup_root" 2>/dev/null || true
            return 1
        fi
        had_existing=1
    fi

    # Quit the running app before replacing its bundle (ignore errors if not running).
    app_name="${app_label%.app}"
    osascript -e 'on run argv' -e 'tell application (item 1 of argv) to quit' -e 'end run' -- "$app_name" 2>/dev/null || true
    sleep 1

    if [ "$had_existing" -eq 1 ] && ! mv "$dest" "$backup" 2>/dev/null; then
        internet_diag_log "ERROR: could not move existing $dest to rollback backup $backup"
        rm -rf "$staging_root" "$backup_root" 2>/dev/null || true
        return 1
    fi
    if ! mv "$staging" "$dest" 2>/dev/null; then
        if [ "$had_existing" -eq 1 ] && ! mv "$backup" "$dest" 2>/dev/null; then
            internet_diag_log "CRITICAL: install failed and rollback is at $backup"
            print_error "CRITICAL: Install failed for $app_label and automatic rollback failed! Retained backup is at $backup. Restore with: mv \"$backup\" \"$dest\""
            rm -rf "$staging_root" 2>/dev/null || true
            return 1
        fi
        rm -rf "$staging_root" "$backup_root" 2>/dev/null || true
        return 1
    fi

    # A post-swap Gatekeeper failure restores the known previous bundle.
    if ! verify_app_signature "$dest"; then
        print_warn "Post-install signature check failed for $app_label"
        internet_diag_log "ERROR: post-install spctl failed for $dest; rolling back"
        rejected="$staging_root/$app_label.rejected"
        if ! mv "$dest" "$rejected" 2>/dev/null; then
            internet_diag_log "WARN: could not preserve rejected app; removing it before rollback"
            if ! rm -rf "$dest" 2>/dev/null; then
                internet_diag_log "CRITICAL: could not remove rejected app; rollback remains at $backup"
                print_error "CRITICAL: Could not remove rejected app $dest; retained backup is at $backup. Restore with: mv \"$backup\" \"$dest\""
                return 1
            fi
        fi
        if [ "$had_existing" -eq 1 ] && ! mv "$backup" "$dest" 2>/dev/null; then
            internet_diag_log "CRITICAL: rejected app is at $rejected; rollback remains at $backup"
            print_error "CRITICAL: Rejected app is at $rejected; automatic rollback failed! Retained backup is at $backup. Restore with: mv \"$backup\" \"$dest\""
            return 1
        fi
        rm -rf "$staging_root" "$backup_root" 2>/dev/null || true
        return 1
    fi

    rm -rf "$staging_root" "$backup_root" 2>/dev/null || true
    return 0
}

. "$SCRIPT_DIR/lib/proc.sh"
. "$SCRIPT_DIR/lib/vendor_feeds.sh"
. "$SCRIPT_DIR/lib/vendor_direct.sh"
. "$SCRIPT_DIR/lib/appstore_ios.sh"

# silent_launch_app — trigger a Mac app's built-in auto-updater without
# bringing windows to the foreground.
#   -g : background launch (does not activate; no Dock bounce)
#   -j : launches with the Hidden flag set (no visible windows)
#   -F : opens "fresh" — no window/state restoration from previous session
# Sparkle / Squirrel / Omaha / Electron updaters all run on launch
# regardless of foreground state, so apps still self-update silently.
# Accepts either an app name (-a) or a path; falls back if -F is rejected.
silent_launch_app() {
    local target="$1"
    local explicit_bid="${2:-}"
    if [ -z "$target" ]; then
        return 1
    fi

    local bid="$explicit_bid"
    if [ -z "$bid" ]; then
        local app_path=""
        case "$target" in
            /*)
                app_path="$target"
                ;;
            *)
                if command -v internet_app_path >/dev/null 2>&1; then
                    app_path="$(internet_app_path "$target" 2>/dev/null || true)"
                fi
                ;;
        esac
        if [ -n "$app_path" ] && command -v internet_app_bundle_id >/dev/null 2>&1; then
            bid="$(internet_app_bundle_id "$app_path" 2>/dev/null || true)"
        fi
    fi

    local was_running=0
    if [ -n "$bid" ] && command -v internet_app_is_running >/dev/null 2>&1; then
        if internet_app_is_running "$bid"; then
            was_running=1
        fi
    fi

    local open_rc=0
    # Path vs name detection: a leading "/" means full path
    case "$target" in
        /*)
            open -gjF "$target" 2>/dev/null \
                || open -gj "$target" 2>/dev/null \
                || open "$target" 2>/dev/null \
                || open_rc=1
            ;;
        *)
            open -gjF -a "$target" 2>/dev/null \
                || open -gj -a "$target" 2>/dev/null \
                || open -a "$target" 2>/dev/null \
                || open_rc=1
            ;;
    esac

    if [ "$open_rc" -ne 0 ]; then
        return 1
    fi

    if [ "$was_running" -eq 0 ] && [ -n "$bid" ] && [ -n "${MAC_UPDATE_SESSION_DIR:-}" ]; then
        local track_file="$MAC_UPDATE_SESSION_DIR/toolkit_launched.txt"
        mkdir -p "$MAC_UPDATE_SESSION_DIR" 2>/dev/null || true
        if [ ! -f "$track_file" ] || ! grep -Fqx "$bid" "$track_file" 2>/dev/null; then
            printf '%s\n' "$bid" >> "$track_file"
        fi
    fi

    return 0
}

quit_toolkit_launched_apps() {
    if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -f "$MAC_UPDATE_SESSION_DIR/toolkit_launched.txt" ]; then
        local _t_bid
        while IFS= read -r _t_bid || [ -n "$_t_bid" ]; do
            case "$_t_bid" in '#'*|'') continue ;; esac
            _t_bid="$(echo "$_t_bid" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
            [ -n "$_t_bid" ] || continue
            if ! internet_app_quit_gracefully "$_t_bid"; then
                print_warn "$(printf "$L_INTERNET_APP_STILL_RUNNING_FMT" "$_t_bid")"
                INTERNET_SOFT_FAIL="1"
            fi
        done < "$MAC_UPDATE_SESSION_DIR/toolkit_launched.txt"
    fi
}

capture_app_path() {
    internet_app_path "$1"
}

firefox_dev_version() {
    internet_firefox_snapshot_version
}

capture_internet_app_versions() {
    internet_capture_versions "$1"
}

# ── Snapshot PRZED aktualizacją ───────────────────────────────
if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
    : > "$MAC_UPDATE_SESSION_DIR/internet_diag.txt"
    internet_diag_section "Internet apps update start"
    print_info "$L_INTERNET_SNAPSHOT_BEFORE"
    capture_internet_app_versions "$MAC_UPDATE_SESSION_DIR/internet_before.txt"
fi

# ============================================================
print_header "$L_SCRIPT_TITLE_INTERNET"
if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
    print_warn "$L_INTERNET_DRY_RUN"
fi
print_info "$L_INTERNET_CHECKING_APPS"
if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
    print_info "[DRY-RUN] Would check all apps in config/internet_apps.txt (no downloads, mounts, or copies)"
    internet_diag_section "DRY-RUN"
    internet_diag_log "Dry-run: skipped all internet app mutations"
    print_header "$L_INTERNET_SCRIPT_DONE"
    exit 0
fi
echo ""

# ── Inicjalizacja statusów (bash 3.2 — bez tablic asocjacyjnych) ──
STATUS_CHROME="$L_INTERNET_STATUS_SKIPPED"
STATUS_FIREFOX="$L_INTERNET_STATUS_SKIPPED"
STATUS_BRAVE="$L_INTERNET_STATUS_MANAGED_BREW"
STATUS_CHATGPT="$L_INTERNET_STATUS_SKIPPED"
STATUS_CLAUDE_APP="$L_INTERNET_STATUS_SKIPPED"
STATUS_GEMINI="$L_INTERNET_STATUS_SKIPPED"
STATUS_COMET="$L_INTERNET_STATUS_SKIPPED"
STATUS_PERPLEXITY="$L_INTERNET_STATUS_MANAGED_BREW"
STATUS_ANTIGRAVITY="$L_INTERNET_STATUS_SKIPPED"
STATUS_ANTIGRAVITY_IDE="$L_INTERNET_STATUS_SKIPPED"
STATUS_LMSTUDIO="$L_INTERNET_STATUS_MANAGED_BREW"
STATUS_PROTONVPN="$L_INTERNET_STATUS_MANAGED_BREW"
STATUS_KEEPASSXC="$L_INTERNET_STATUS_SKIPPED"
STATUS_PROTONMAIL="$L_INTERNET_STATUS_SKIPPED"
STATUS_PROTONDRIVE="$L_INTERNET_STATUS_SKIPPED"
STATUS_ZOOM="$L_INTERNET_STATUS_MANAGED_BREW"
STATUS_GOOGLEDRIVE="$L_INTERNET_STATUS_SKIPPED"
STATUS_MEGASYNC="$L_INTERNET_STATUS_MANAGED_BREW"
STATUS_MICROSOFT="$L_INTERNET_STATUS_SKIPPED"
STATUS_TEAMS="$L_INTERNET_STATUS_SKIPPED"
STATUS_VSCODE="$L_INTERNET_STATUS_SKIPPED"
STATUS_CODEEDIT="$L_INTERNET_STATUS_SKIPPED"
STATUS_DOCKER="$L_INTERNET_STATUS_SKIPPED"
STATUS_WARP="$L_INTERNET_STATUS_SKIPPED"
STATUS_CURSOR="$L_INTERNET_STATUS_SKIPPED"
STATUS_APPCLEANER="$L_INTERNET_STATUS_MANAGED_BREW"
STATUS_OBSIDIAN="$L_INTERNET_STATUS_MANAGED_BREW"
STATUS_SPOTIFY="$L_INTERNET_STATUS_MANAGED_BREW"
STATUS_CAPCUT="$L_INTERNET_STATUS_MANAGED_BREW"
STATUS_LEDGER="$L_INTERNET_STATUS_SKIPPED"
STATUS_TREZOR="$L_INTERNET_STATUS_SKIPPED"
STATUS_IPMIVIEW="$L_INTERNET_STATUS_SKIPPED"
STATUS_RDMANAGER="$L_INTERNET_STATUS_SKIPPED"
STATUS_OPENCODE="$L_INTERNET_STATUS_SKIPPED"
STATUS_INKSCAPE="$L_INTERNET_STATUS_MANAGED_BREW"
STATUS_DJI="$L_INTERNET_STATUS_SKIPPED"
STATUS_UNIFI="$L_INTERNET_STATUS_MANAGED_APPSTORE"
STATUS_WIFIMAN="$L_INTERNET_STATUS_MANAGED_APPSTORE"
STATUS_PICSART="$L_INTERNET_STATUS_MANAGED_APPSTORE"

# ============================================================
# App handlers — config/internet_dispatch_order.txt
# ============================================================
. "$SCRIPT_DIR/lib/internet_app_updates.sh"

# Check for Intel-only (x86_64-only) applications and Rosetta availability
if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
    rm -f "$MAC_UPDATE_SESSION_DIR/rosetta_missing_apps.txt" 2>/dev/null || true
fi

HAS_X86_64=0
while IFS='|' read -r _app_name _method _status_var _rest; do
    case "$_app_name" in '#'*|'') continue ;; esac
    _app_path="$(internet_app_path "$_app_name")"
    if [ -d "$_app_path" ]; then
        _arch="$(mac_update_app_architecture "$_app_path")"
        if [ "$_arch" = "x86_64-only" ]; then
            HAS_X86_64=1
            break
        fi
    fi
done < "$SCRIPT_DIR/config/internet_app_methods.txt"

if [ "$HAS_X86_64" -eq 1 ]; then
    if ! mac_update_rosetta_installed; then
        if [ "${MAC_UPDATE_INSTALL_ROSETTA:-0}" = "1" ]; then
            print_step "Installing Rosetta via softwareupdate..."
            softwareupdate --install-rosetta --agree-to-license
            if mac_update_rosetta_installed; then
                print_ok "Rosetta installed successfully"
            else
                print_warn "Rosetta installation could not be verified"
            fi
        fi
    fi
fi

internet_dispatch_run_all

# Ensure all x86_64-only apps reflect Rosetta requirement in their final status
while IFS='|' read -r _app_name _method _status_var _rest; do
    case "$_app_name" in '#'*|'') continue ;; esac
    _status_var="$(echo "$_status_var" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    _app_path="$(internet_app_path "$_app_name")"
    if [ -d "$_app_path" ]; then
        _arch="$(mac_update_app_architecture "$_app_path")"
        if [ "$_arch" = "x86_64-only" ]; then
            if mac_update_rosetta_installed; then
                eval "$_status_var=\"\$L_INTERNET_ROSETTA_REQUIRED; \$L_INTERNET_ROSETTA_EOL\""
            else
                eval "$_status_var=\"\$L_INTERNET_ROSETTA_REQUIRED \$L_INTERNET_ROSETTA_NOT_INSTALLED; \$L_INTERNET_ROSETTA_EOL\""
                if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
                    echo "$_app_name" >> "$MAC_UPDATE_SESSION_DIR/rosetta_missing_apps.txt"
                fi
            fi
        fi
    fi
done < "$SCRIPT_DIR/config/internet_app_methods.txt"

if [ -n "$MAC_UPDATE_SESSION_DIR" ] && [ -f "$MAC_UPDATE_SESSION_DIR/rosetta_missing_apps.txt" ]; then
    sort -u "$MAC_UPDATE_SESSION_DIR/rosetta_missing_apps.txt" -o "$MAC_UPDATE_SESSION_DIR/rosetta_missing_apps.txt" 2>/dev/null || true
fi

# ── Snapshot PO aktualizacji ──────────────────────────────────
if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
    print_info "$L_INTERNET_SNAPSHOT_AFTER"
    # Vendor updaters launched above rewrite Info.plist asynchronously, so the
    # "after" snapshot has to let them land. There is no completion signal to
    # poll, hence a fixed settle. It is ~18% of this step's wall clock, so it is
    # configurable: lower it on a fast machine, raise it on a slow link.
    INTERNET_SETTLE="${MAC_UPDATE_INTERNET_SETTLE_SECONDS:-15}"
    case "$INTERNET_SETTLE" in
        ''|*[!0-9]*) INTERNET_SETTLE=15 ;;
    esac
    [ "$INTERNET_SETTLE" -gt 120 ] && INTERNET_SETTLE=120

    # Build unverified_apps list from config — no hardcoded STATUS_* names.
    # This replaced a hand-maintained 19-variable list that contained two
    # typos (STATUS_PROTON_MAIL, STATUS_PROTON_DRIVE vs the canonical
    # STATUS_PROTONMAIL, STATUS_PROTONDRIVE). See BUG-1b fix (2026-08-05).
    unverified_apps=""
    st=""
    while IFS='|' read -r _cfg_app_name _cfg_method _cfg_status_var; do
        case "$_cfg_app_name" in '#'*|'') continue ;; esac
        _cfg_method="$(echo "$_cfg_method" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        _cfg_status_var="$(echo "$_cfg_status_var" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        if [ "$_cfg_method" = "silent_launch" ]; then
            eval "st=\$$_cfg_status_var"
            if [ "$st" = "$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED" ]; then
                unverified_apps="$unverified_apps $_cfg_status_var"
            fi
        fi
    done < "$SCRIPT_DIR/config/internet_app_methods.txt"

    if [ -n "$unverified_apps" ] && [ "$INTERNET_SETTLE" -gt 0 ]; then
        # Adaptive polling: wait until versions stabilize (3 consecutive
        # identical readings) or until the hard time limit is reached.
        stable_count=0
        last_versions=""
        elapsed=0
        settle_start=$(date +%s)
        while [ "$elapsed" -lt "$INTERNET_SETTLE" ]; do
            current_versions=""
            for var in $unverified_apps; do
                # Resolve STATUS_VAR → app name → app path from config
                _settle_app_name=""
                while IFS='|' read -r _sa_name _sa_method _sa_var; do
                    case "$_sa_name" in '#'*|'') continue ;; esac
                    _sa_var="$(echo "$_sa_var" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
                    if [ "$_sa_var" = "$var" ]; then
                        _settle_app_name="$(echo "$_sa_name" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
                        break
                    fi
                done < "$SCRIPT_DIR/config/internet_app_methods.txt"
                if [ -n "$_settle_app_name" ]; then
                    _settle_app_path="$(capture_app_path "$_settle_app_name")"
                    ver="$(app_version "$_settle_app_path" 2>/dev/null)"
                else
                    ver=""
                fi
                current_versions="$current_versions $ver"
            done
            if [ -n "$last_versions" ] && [ "$current_versions" = "$last_versions" ]; then
                stable_count=$((stable_count + 1))
                if [ "$stable_count" -ge 3 ]; then
                    break
                fi
            else
                stable_count=0
                last_versions="$current_versions"
            fi
            sleep 1
            elapsed=$((elapsed + 1))
        done
        settle_end=$(date +%s)
        settle_actual=$((settle_end - settle_start))
        print_info "Settle wait: ${settle_actual}s (limit ${INTERNET_SETTLE}s, ${stable_count} stable readings)"
    elif [ "$INTERNET_SETTLE" -gt 0 ]; then
        sleep "$INTERNET_SETTLE"
    fi
    quit_toolkit_launched_apps
    capture_internet_app_versions "$MAC_UPDATE_SESSION_DIR/internet_after.txt"
    print_ok "$(internet_msg "$L_INTERNET_SNAPSHOTS_SAVED" "$MAC_UPDATE_SESSION_DIR")"

    # ── Version History Persistence (TSV) ──────────────────────
    HISTORY_FILE="$SCRIPT_DIR/logs/version_history.tsv"
    if [ -f "$MAC_UPDATE_SESSION_DIR/internet_after.txt" ]; then
        mkdir -p "$SCRIPT_DIR/logs"
        [ -f "$HISTORY_FILE" ] || touch "$HISTORY_FILE"
        chmod 600 "$HISTORY_FILE" 2>/dev/null || true

        TS="$(date -u +"%Y-%m-%d %H:%M:%S")"
        while IFS='|' read -r _h_app _h_ver; do
            [ -n "$_h_app" ] || continue
            _h_method="unknown"
            while IFS='|' read -r _m_app _m_meth _; do
                case "$_m_app" in '#'*|'') continue ;; esac
                _m_app="$(echo "$_m_app" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
                if [ "$_m_app" = "$_h_app" ]; then
                    _h_method="$(echo "$_m_meth" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
                    break
                fi
            done < "$SCRIPT_DIR/config/internet_app_methods.txt"
            printf "%s\t%s\t%s\t%s\n" "$TS" "$_h_app" "$_h_ver" "$_h_method" >> "$HISTORY_FILE"
        done < "$MAC_UPDATE_SESSION_DIR/internet_after.txt"
        internet_rotate_version_history
    fi
fi

# ── Stale Days Warning for Unverified Apps ──
STALE_LIMIT="${MAC_UPDATE_STALE_DAYS:-45}"
while IFS='|' read -r _s_app _s_meth _s_var; do
    case "$_s_app" in '#'*|'') continue ;; esac
    _s_meth="$(echo "$_s_meth" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    _s_var="$(echo "$_s_var" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    if [ "$_s_meth" = "silent_launch" ]; then
        _s_cur=""
        eval "_s_cur=\"\${$_s_var}\""
        _s_code="$(internet_status_code "$_s_cur")"
        case "$_s_code" in
            current_verified|current_vendor|updated|behind|needs_restart|feed_stale|update_available|rollout_hold)
                continue
                ;;
        esac
        _s_app_name="$(echo "$_s_app" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        _s_days="$(internet_get_app_days_unchanged "$_s_app_name")"
        if [ "$_s_days" -gt "$STALE_LIMIT" ]; then
            eval "${_s_var}=\"\$(internet_msg \"\$L_INTERNET_STALE_WARNING_FMT\" \"$_s_days\" \"$STALE_LIMIT\")\""
        fi
    fi
done < "$SCRIPT_DIR/config/internet_app_methods.txt"

# ── Validate brew_cask entries exist in Homebrew ──
_installed_casks="$(brew_cask_versions 2>/dev/null || true)"
while IFS='|' read -r _v_app _v_meth _v_var; do
    case "$_v_app" in '#'*|'') continue ;; esac
    _v_meth="$(echo "$_v_meth" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    _v_var="$(echo "$_v_var" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    if [ "$_v_meth" = "brew_cask" ]; then
        _v_app_name="$(echo "$_v_app" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        _v_cask="$(internet_cask_name_for_app "$_v_app_name")"
        if ! echo "$_installed_casks" | grep -qi "^${_v_cask}[[:space:]]"; then
            eval "${_v_var}=\"\$L_INTERNET_STATUS_CASK_MISSING\""
        fi
    fi
done < "$SCRIPT_DIR/config/internet_app_methods.txt"

# ── Cask Oracle for Unverified / Silent Launch Apps ──
# Homebrew casks are a free, read-only oracle used to verify installed
# bundle versions. Never mutates system; only transforms ⏳ into ✅ or ⚠️.
if [ -f "$SCRIPT_DIR/config/cask_oracles.txt" ] && command -v brew >/dev/null 2>&1; then
    _oracle_tokens=""
    while IFS='|' read -r _o_app _o_token; do
        case "$_o_app" in '#'*|'') continue ;; esac
        _o_app="$(echo "$_o_app" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        _o_token="$(echo "$_o_token" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        [ -n "$_o_token" ] || continue

        # v1.5.0 (T3): Skip apps that have a vendor feed in config/vendor_feeds.txt
        if vendor_feed_row "$_o_app" >/dev/null 2>&1; then
            continue
        fi

        _o_var=""
        while IFS='|' read -r _m_app _m_meth _m_var; do
            case "$_m_app" in '#'*|'') continue ;; esac
            _m_app="$(echo "$_m_app" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
            if [ "$_m_app" = "$_o_app" ]; then
                _o_var="$(echo "$_m_var" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
                break
            fi
        done < "$SCRIPT_DIR/config/internet_app_methods.txt"

        _cur_st=""
        if [ -n "$_o_var" ]; then
            eval "_cur_st=\$$_o_var"
            case "$_cur_st" in
                *"⏳"*)
                    _oracle_tokens="$_oracle_tokens $_o_token"
                    ;;
            esac
        fi
    done < "$SCRIPT_DIR/config/cask_oracles.txt"

    _oracle_data=""
    if [ -n "$_oracle_tokens" ]; then
        # shellcheck disable=SC2086
        _oracle_data="$(brew_cask_latest_versions $_oracle_tokens 2>/dev/null || true)"
    fi

    if [ -n "$_oracle_data" ]; then
        while IFS='|' read -r _o_app _o_token; do
            case "$_o_app" in '#'*|'') continue ;; esac
            _o_app="$(echo "$_o_app" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
            _o_token="$(echo "$_o_token" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
            [ -n "$_o_token" ] || continue

            # v1.5.0 (T3): Skip apps that have a vendor feed in config/vendor_feeds.txt
            if vendor_feed_row "$_o_app" >/dev/null 2>&1; then
                continue
            fi

            _o_var=""
            while IFS='|' read -r _m_app _m_meth _m_var; do
                case "$_m_app" in '#'*|'') continue ;; esac
                _m_app="$(echo "$_m_app" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
                if [ "$_m_app" = "$_o_app" ]; then
                    _o_var="$(echo "$_m_var" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
                    break
                fi
            done < "$SCRIPT_DIR/config/internet_app_methods.txt"

            [ -n "$_o_var" ] || continue
            _cur_st=""
            eval "_cur_st=\$$_o_var"
            case "$_cur_st" in
                *"⏳"*) ;;
                *) continue ;;
            esac

            _cask_ver="$(echo "$_oracle_data" | awk -F'\t' -v tok="$_o_token" '$1 == tok {print $2; exit}')"
            [ -n "$_cask_ver" ] || continue

            _bundle_ver=""
            if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -f "$MAC_UPDATE_SESSION_DIR/internet_after.txt" ]; then
                _bundle_ver="$(awk -F'|' -v app="$_o_app" '$1 == app {print $2; exit}' "$MAC_UPDATE_SESSION_DIR/internet_after.txt")"
            fi
            if [ -z "$_bundle_ver" ]; then
                _app_path="$(capture_app_path "$_o_app")"
                [ -n "$_app_path" ] && _bundle_ver="$(app_version "$_app_path" 2>/dev/null)"
            fi

            case "$_bundle_ver" in
                ''|'unknown'|'nieznana'|'null'|"${L_INTERNET_VERSION_UNKNOWN:-unknown}") continue ;;
            esac

            _cask_rel="$(version_cmp "$_cask_ver" "$_bundle_ver")"

            if [ "$_cask_rel" = "newer" ]; then
                eval "${_o_var}=\"\$(internet_msg \"\$L_INTERNET_STATUS_CASK_BEHIND_FMT\" \"\$_bundle_ver\" \"\$_cask_ver\")\""
                if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -d "$MAC_UPDATE_SESSION_DIR" ]; then
                    printf "%s|%s|%s\n" "$_o_app" "$_bundle_ver" "$_cask_ver" >> "$MAC_UPDATE_SESSION_DIR/internet_behind_apps.txt"
                fi
            elif [ "$_cask_rel" = "equal" ]; then
                eval "${_o_var}=\"\$L_INTERNET_STATUS_CASK_CURRENT\""
                if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -d "$MAC_UPDATE_SESSION_DIR" ]; then
                    printf "%s|%s\n" "$_o_app" "$_bundle_ver" >> "$MAC_UPDATE_SESSION_DIR/internet_verified_apps.txt"
                fi
            fi
            # older / unknown -> no change of status (remains ⏳)
        done < "$SCRIPT_DIR/config/cask_oracles.txt"
    fi
fi

# ── Compute and Persist Internet Counts ──
_cnt_verified=0
_cnt_behind=0
_cnt_unverified=0
_soft_fail_from_codes=0

if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -d "$MAC_UPDATE_SESSION_DIR" ]; then
    rm -f "$MAC_UPDATE_SESSION_DIR/internet_status_codes.txt" 2>/dev/null || true
fi

while IFS='|' read -r _c_app _c_meth _c_var; do
    case "$_c_app" in '#'*|'') continue ;; esac
    _c_var="$(echo "$_c_var" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    [ -n "$_c_var" ] || continue
    _v_st=""
    eval "_v_st=\$$_c_var"
    _code="$(internet_status_code "$_v_st")"
    if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -d "$MAC_UPDATE_SESSION_DIR" ]; then
        printf "%s|%s|%s\n" "$_c_app" "$_code" "$_v_st" >> "$MAC_UPDATE_SESSION_DIR/internet_status_codes.txt"
    fi
    case "$_code" in
        current_verified|current_vendor|updated)
            _cnt_verified=$((_cnt_verified + 1))
            ;;
        behind|needs_restart)
            _cnt_behind=$((_cnt_behind + 1))
            ;;
        unverified)
            _cnt_unverified=$((_cnt_unverified + 1))
            ;;
    esac
    case "$_code" in
        behind|needs_restart|feed_stale)
            _soft_fail_from_codes=1
            ;;
    esac
done < "$SCRIPT_DIR/config/internet_app_methods.txt"

if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -d "$MAC_UPDATE_SESSION_DIR" ]; then
    printf "%d\n" "$_cnt_verified" > "$MAC_UPDATE_SESSION_DIR/internet_verified"
    printf "%d\n" "$_cnt_behind" > "$MAC_UPDATE_SESSION_DIR/internet_behind"
    printf "%d\n" "$_cnt_unverified" > "$MAC_UPDATE_SESSION_DIR/internet_unverified"

    python3 - "$MAC_UPDATE_SESSION_DIR" "$_cnt_verified" "$_cnt_behind" "$_cnt_unverified" <<'PYEOF'
import json, os, sys

sdir = sys.argv[1]
try:
    v, b, u = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    cpath = os.path.join(sdir, "run_counts.json")
    data = {}
    if os.path.isfile(cpath):
        try:
            with open(cpath, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                data = loaded
        except Exception:
            data = {}
    data["internet_verified"] = v
    data["internet_behind"] = b
    data["internet_unverified"] = u
    with open(cpath, "w", encoding="utf-8") as f:
        json.dump(data, f)
except Exception:
    pass
PYEOF
fi

# ============================================================
# PODSUMOWANIE
# ============================================================
print_header "$L_INTERNET_SUMMARY_TITLE"

internet_summary_section "$L_INTERNET_SECTION_BROWSERS"
internet_summary_row "Google Chrome:"            "$STATUS_CHROME"        "Google Chrome"
internet_summary_row "Firefox Dev Edition:"      "$STATUS_FIREFOX"       "Firefox Developer Edition"
internet_summary_row "Brave Browser:"            "$STATUS_BRAVE"         "Brave Browser"

internet_summary_section "$L_INTERNET_SECTION_AI"
internet_summary_row "ChatGPT / Codex:"          "$STATUS_CHATGPT"       "ChatGPT / Codex"
internet_summary_row "Claude Desktop:"           "$STATUS_CLAUDE_APP"    "Claude"
internet_summary_row "Gemini Desktop:"           "$STATUS_GEMINI"        "Gemini"
internet_summary_row "Comet (Perplexity Browser):" "$STATUS_COMET"       "Comet"
internet_summary_row "Perplexity Desktop:"       "$STATUS_PERPLEXITY"    "Perplexity"
internet_summary_row "Antigravity:"              "$STATUS_ANTIGRAVITY"   "Antigravity"
internet_summary_row "Antigravity IDE:"          "$STATUS_ANTIGRAVITY_IDE" "Antigravity IDE"
internet_summary_row "LM Studio:"                "$STATUS_LMSTUDIO"      "LM Studio"
internet_summary_row "OpenCode Desktop:"         "$STATUS_OPENCODE"      "OpenCode"

internet_summary_section "$L_INTERNET_SECTION_VPN"
internet_summary_row "ProtonVPN:"                "$STATUS_PROTONVPN"     "ProtonVPN"
internet_summary_row "KeePassXC:"                "$STATUS_KEEPASSXC"     "KeePassXC"

internet_summary_section "$L_INTERNET_SECTION_MAIL"
internet_summary_row "Proton Mail:"              "$STATUS_PROTONMAIL"    "Proton Mail"
internet_summary_row "Zoom:"                     "$STATUS_ZOOM"          "zoom.us"

internet_summary_section "$L_INTERNET_SECTION_CLOUD"
internet_summary_row "Google Drive:"             "$STATUS_GOOGLEDRIVE"   "Google Drive"
internet_summary_row "MEGAsync:"                 "$STATUS_MEGASYNC"      "MEGAsync"
internet_summary_row "Proton Drive:"             "$STATUS_PROTONDRIVE"   "Proton Drive"

internet_summary_section "$L_INTERNET_SECTION_MICROSOFT"
internet_summary_row "Microsoft AutoUpdate:"     "$STATUS_MICROSOFT"     "Microsoft AutoUpdate"
internet_summary_row "Microsoft Teams (hybrid):" "$STATUS_TEAMS"         "Microsoft Teams"

internet_summary_section "$L_INTERNET_SECTION_DEV"
internet_summary_row "Visual Studio Code:"       "$STATUS_VSCODE"        "Visual Studio Code"
internet_summary_row "CodeEdit:"                 "$STATUS_CODEEDIT"      "CodeEdit"
internet_summary_row "Docker Desktop:"           "$STATUS_DOCKER"        "Docker Desktop"
internet_summary_row "Warp:"                     "$STATUS_WARP"          "Warp"
internet_summary_row "Cursor:"                   "$STATUS_CURSOR"        "Cursor"

internet_summary_section "$L_INTERNET_SECTION_PRODUCTIVITY"
internet_summary_row "AppCleaner:"               "$STATUS_APPCLEANER"    "AppCleaner"
internet_summary_row "Obsidian:"                 "$STATUS_OBSIDIAN"      "Obsidian"

internet_summary_section "$L_INTERNET_SECTION_MULTIMEDIA"
internet_summary_row "Spotify:"                  "$STATUS_SPOTIFY"       "Spotify"
internet_summary_row "CapCut:"                   "$STATUS_CAPCUT"        "CapCut"
internet_summary_row "Inkscape:"                 "$STATUS_INKSCAPE"      "Inkscape"
internet_summary_row "Picsart:"                  "$STATUS_PICSART"       "Picsart"

internet_summary_section "$L_INTERNET_SECTION_CRYPTO"
internet_summary_row "Ledger Live/Wallet:"       "$STATUS_LEDGER"        "Ledger Live"
internet_summary_row "Trezor Suite:"             "$STATUS_TREZOR"        "Trezor Suite"

internet_summary_section "$L_INTERNET_SECTION_NETWORK"
internet_summary_row "Remote Desktop Manager:"   "$STATUS_RDMANAGER"     "Remote Desktop Manager"
internet_summary_row "IPMIView:"                 "$STATUS_IPMIVIEW"      "IPMIView"
internet_summary_row "DJI Assistant 2:"          "$STATUS_DJI"           "DJI Assistant 2"

internet_summary_section "IoT / iPad on Apple Silicon"
internet_summary_row "UniFi:"                    "$STATUS_UNIFI"         "UniFi"
internet_summary_row "WiFiman:"                  "$STATUS_WIFIMAN"       "WiFiman"
internet_summary_end

echo ""
echo -e "  ${YELLOW}──────────────────────────────────────────────────────${NC}"
print_info "$L_INTERNET_CHECKED_NOTE"
print_info "$L_INTERNET_INSTRUCTIONS"

for status in \
    "$STATUS_CHROME" "$STATUS_FIREFOX" "$STATUS_BRAVE" \
    "$STATUS_CHATGPT" "$STATUS_CLAUDE_APP" "$STATUS_GEMINI" "$STATUS_COMET" "$STATUS_PERPLEXITY" \
    "$STATUS_ANTIGRAVITY" "$STATUS_ANTIGRAVITY_IDE" "$STATUS_LMSTUDIO" "$STATUS_OPENCODE" \
    "$STATUS_PROTONVPN" "$STATUS_KEEPASSXC" "$STATUS_PROTONMAIL" "$STATUS_ZOOM" \
    "$STATUS_GOOGLEDRIVE" "$STATUS_MEGASYNC" "$STATUS_PROTONDRIVE" "$STATUS_MICROSOFT" "$STATUS_TEAMS" \
    "$STATUS_VSCODE" "$STATUS_CODEEDIT" "$STATUS_DOCKER" "$STATUS_WARP" "$STATUS_CURSOR" \
    "$STATUS_APPCLEANER" "$STATUS_OBSIDIAN" "$STATUS_SPOTIFY" "$STATUS_CAPCUT" \
    "$STATUS_LEDGER" "$STATUS_TREZOR" \
    "$STATUS_RDMANAGER" "$STATUS_IPMIVIEW" "$STATUS_INKSCAPE" \
    "$STATUS_DJI" "$STATUS_UNIFI" "$STATUS_WIFIMAN" "$STATUS_PICSART"
do
    # Flag a failure only when the status equals an explicit error-status
    # constant — do not scan for the ⚠️ glyph, which would silently break if a
    # translation used a different warning symbol. Every failure status below is
    # a static string (no %s substitution), so an exact match is safe and
    # locale-independent. Keep them static: adding a %s to any of these keys
    # would break the exact match and silently reclassify the status.
    #
    # HARD (exit 1): a download or install actually broke. The bundle swap in
    # copy_verified_app can leave staging/rollback state behind, so the machine
    # may be mid-mutation and a reboot could make it worse.
    case "$status" in
        "$L_INTERNET_STATUS_INSTALL_ERROR"|\
        "$L_INTERNET_STATUS_MOUNT_ERROR"|\
        "$L_INTERNET_STATUS_EXTRACT_ERROR")
            INTERNET_HARD_FAIL=1
            ;;
    esac
    # SOFT (exit 10): could not verify, or environmental. Nothing was mutated,
    # so these must stay visible without deferring the macOS system update.
    case "$status" in
        "$L_INTERNET_STATUS_OFFLINE"|\
        "$L_INTERNET_STATUS_NO_URL"|\
        "$L_INTERNET_STATUS_DOWNLOAD_ERROR"|\
        "$L_INTERNET_STATUS_CHECK_MAU"|\
        "$L_INTERNET_STATUS_MAU_MISSING"|\
        "$L_INTERNET_STATUS_MAU_QUARANTINED"|\
        "$L_INTERNET_STATUS_MAU_OPENED"|\
        "$L_INTERNET_STATUS_UNKNOWN_VERSION"|\
        "$L_INTERNET_STATUS_CASK_MISSING"|\
        "$L_INTERNET_STATUS_LAUNCH_FAILED")
            INTERNET_SOFT_FAIL=1
            ;;
    esac
done
[ "$_soft_fail_from_codes" -ne 0 ] && INTERNET_SOFT_FAIL=1

if [ "$INTERNET_HARD_FAIL" -ne 0 ]; then
    INTERNET_EXIT=1
    print_error "$L_INTERNET_HARD_FAILURE"
    [ "$INTERNET_SOFT_FAIL" -ne 0 ] && print_warn "$L_INTERNET_PARTIAL_FAILURE"
elif [ "$INTERNET_SOFT_FAIL" -ne 0 ]; then
    INTERNET_EXIT="$INTERNET_SOFT_EXIT"
    print_warn "$L_INTERNET_PARTIAL_FAILURE"
    print_info "$L_INTERNET_SOFT_NOTE"
fi
print_header "$L_INTERNET_SCRIPT_DONE"
exit "$INTERNET_EXIT"
