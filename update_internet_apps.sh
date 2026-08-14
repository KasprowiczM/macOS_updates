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
#   PRZEGLĄDARKI:     Google Chrome, Firefox Dev Edition, Brave, ChatGPT Atlas
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
. "$SCRIPT_DIR/lib/internet_registry.sh"
. "$SCRIPT_DIR/lib/internet_handlers.sh"
. "$SCRIPT_DIR/lib/github_release.sh"
. "$SCRIPT_DIR/lib/internet_i18n.sh"
. "$SCRIPT_DIR/lib/version.sh"
. "$SCRIPT_DIR/lib/platform.sh"

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
    if [ -z "$target" ]; then
        return 1
    fi
    # Path vs name detection: a leading "/" means full path
    case "$target" in
        /*)
            open -gjF "$target" 2>/dev/null \
                || open -gj "$target" 2>/dev/null \
                || open "$target" 2>/dev/null \
                || return 1
            ;;
        *)
            open -gjF -a "$target" 2>/dev/null \
                || open -gj -a "$target" 2>/dev/null \
                || open -a "$target" 2>/dev/null \
                || return 1
            ;;
    esac
    return 0
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
STATUS_BRAVE="→ managed by Homebrew (update_brew.sh)"
STATUS_ATLAS="$L_INTERNET_STATUS_SKIPPED"
STATUS_CHATGPT="$L_INTERNET_STATUS_SKIPPED"
STATUS_CLAUDE_APP="$L_INTERNET_STATUS_SKIPPED"
STATUS_GEMINI="$L_INTERNET_STATUS_SKIPPED"
STATUS_COMET="$L_INTERNET_STATUS_SKIPPED"
STATUS_PERPLEXITY="→ managed by Homebrew (update_brew.sh)"
STATUS_ANTIGRAVITY="$L_INTERNET_STATUS_SKIPPED"
STATUS_ANTIGRAVITY_IDE="$L_INTERNET_STATUS_SKIPPED"
STATUS_LMSTUDIO="→ managed by Homebrew (update_brew.sh)"
STATUS_PROTONVPN="→ managed by Homebrew (update_brew.sh)"
STATUS_KEEPASSXC="$L_INTERNET_STATUS_SKIPPED"
STATUS_PROTONMAIL="$L_INTERNET_STATUS_SKIPPED"
STATUS_PROTONDRIVE="$L_INTERNET_STATUS_SKIPPED"
STATUS_ZOOM="→ managed by Homebrew (update_brew.sh)"
STATUS_GOOGLEDRIVE="$L_INTERNET_STATUS_SKIPPED"
STATUS_MEGASYNC="→ managed by Homebrew (update_brew.sh)"
STATUS_MICROSOFT="$L_INTERNET_STATUS_SKIPPED"
STATUS_TEAMS="$L_INTERNET_STATUS_SKIPPED"
STATUS_VSCODE="$L_INTERNET_STATUS_SKIPPED"
STATUS_CODEEDIT="$L_INTERNET_STATUS_SKIPPED"
STATUS_DOCKER="$L_INTERNET_STATUS_SKIPPED"
STATUS_WARP="$L_INTERNET_STATUS_SKIPPED"
STATUS_CURSOR="$L_INTERNET_STATUS_SKIPPED"
STATUS_APPCLEANER="→ managed by Homebrew (update_brew.sh)"
STATUS_OBSIDIAN="→ managed by Homebrew (update_brew.sh)"
STATUS_SPOTIFY="→ managed by Homebrew (update_brew.sh)"
STATUS_CAPCUT="→ managed by Homebrew (update_brew.sh)"
STATUS_LEDGER="$L_INTERNET_STATUS_SKIPPED"
STATUS_TREZOR="$L_INTERNET_STATUS_SKIPPED"
STATUS_IPMIVIEW="$L_INTERNET_STATUS_SKIPPED"
STATUS_RDMANAGER="$L_INTERNET_STATUS_SKIPPED"
STATUS_OPENCODE="$L_INTERNET_STATUS_SKIPPED"
STATUS_INKSCAPE="→ managed by Homebrew (update_brew.sh)"
STATUS_DJI="$L_INTERNET_STATUS_SKIPPED"
STATUS_UNIFI="→ managed by App Store (update_appstore.sh)"
STATUS_WIFIMAN="→ managed by App Store (update_appstore.sh)"
STATUS_PICSART="→ managed by App Store (update_appstore.sh)"

# ============================================================
# App handlers — config/internet_dispatch_order.txt
# ============================================================
. "$SCRIPT_DIR/lib/internet_app_updates.sh"
internet_dispatch_run_all

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
        _s_app_name="$(echo "$_s_app" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        _s_days="$(internet_get_app_days_unchanged "$_s_app_name")"
        if [ "$_s_days" -gt "$STALE_LIMIT" ]; then
            eval "${_s_var}=\"\$(internet_msg \"\$L_INTERNET_STALE_WARNING_FMT\" \"$_s_days\" \"$STALE_LIMIT\")\""
        fi
    fi
done < "$SCRIPT_DIR/config/internet_app_methods.txt"

# ── Validate brew_cask entries exist in Homebrew ──
_installed_casks="$(brew list --cask --versions 2>/dev/null || true)"
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

# ============================================================
# PODSUMOWANIE
# ============================================================
print_header "$L_INTERNET_SUMMARY_TITLE"

echo -e "  ${BOLD}$L_INTERNET_SECTION_BROWSERS${NC}"
printf "  %-32s %s\n" "Google Chrome:"            "$STATUS_CHROME"
printf "  %-32s %s\n" "Firefox Dev Edition:"      "$STATUS_FIREFOX"
printf "  %-32s %s\n" "Brave Browser:"            "$STATUS_BRAVE"
printf "  %-32s %s\n" "ChatGPT Atlas:"            "$STATUS_ATLAS"
echo ""

echo -e "  ${BOLD}$L_INTERNET_SECTION_AI${NC}"
printf "  %-32s %s\n" "ChatGPT / Codex:"          "$STATUS_CHATGPT"
printf "  %-32s %s\n" "Claude Desktop:"           "$STATUS_CLAUDE_APP"
printf "  %-32s %s\n" "Gemini Desktop:"           "$STATUS_GEMINI"
printf "  %-32s %s\n" "Comet (Perplexity Browser):" "$STATUS_COMET"
printf "  %-32s %s\n" "Perplexity Desktop:"       "$STATUS_PERPLEXITY"
printf "  %-32s %s\n" "Antigravity:"              "$STATUS_ANTIGRAVITY"
printf "  %-32s %s\n" "Antigravity IDE:"          "$STATUS_ANTIGRAVITY_IDE"
printf "  %-32s %s\n" "LM Studio:"                "$STATUS_LMSTUDIO"
printf "  %-32s %s\n" "OpenCode Desktop:"         "$STATUS_OPENCODE"
echo ""

echo -e "  ${BOLD}$L_INTERNET_SECTION_VPN${NC}"
printf "  %-32s %s\n" "ProtonVPN:"                "$STATUS_PROTONVPN"
printf "  %-32s %s\n" "KeePassXC:"                "$STATUS_KEEPASSXC"
echo ""

echo -e "  ${BOLD}$L_INTERNET_SECTION_MAIL${NC}"
printf "  %-32s %s\n" "Proton Mail:"              "$STATUS_PROTONMAIL"
printf "  %-32s %s\n" "Zoom:"                     "$STATUS_ZOOM"
echo ""

echo -e "  ${BOLD}$L_INTERNET_SECTION_CLOUD${NC}"
printf "  %-32s %s\n" "Google Drive:"             "$STATUS_GOOGLEDRIVE"
printf "  %-32s %s\n" "MEGAsync:"                 "$STATUS_MEGASYNC"
printf "  %-32s %s\n" "Proton Drive:"             "$STATUS_PROTONDRIVE"
echo ""

echo -e "  ${BOLD}$L_INTERNET_SECTION_MICROSOFT${NC}"
printf "  %-32s %s\n" "Microsoft AutoUpdate:" "$STATUS_MICROSOFT"
printf "  %-32s %s\n" "Microsoft Teams (hybrid):" "$STATUS_TEAMS"
echo ""

echo -e "  ${BOLD}$L_INTERNET_SECTION_DEV${NC}"
printf "  %-32s %s\n" "Visual Studio Code:"       "$STATUS_VSCODE"
printf "  %-32s %s\n" "CodeEdit:"                 "$STATUS_CODEEDIT"
printf "  %-32s %s\n" "Docker Desktop:"           "$STATUS_DOCKER"
printf "  %-32s %s\n" "Warp:"                     "$STATUS_WARP"
printf "  %-32s %s\n" "Cursor:"                   "$STATUS_CURSOR"
echo ""

echo -e "  ${BOLD}$L_INTERNET_SECTION_PRODUCTIVITY${NC}"
printf "  %-32s %s\n" "AppCleaner:"               "$STATUS_APPCLEANER"
printf "  %-32s %s\n" "Obsidian:"                 "$STATUS_OBSIDIAN"
echo ""

echo -e "  ${BOLD}$L_INTERNET_SECTION_MULTIMEDIA${NC}"
printf "  %-32s %s\n" "Spotify:"                  "$STATUS_SPOTIFY"
printf "  %-32s %s\n" "CapCut:"                   "$STATUS_CAPCUT"
printf "  %-32s %s\n" "Inkscape:"                 "$STATUS_INKSCAPE"
printf "  %-32s %s\n" "Picsart:"                  "$STATUS_PICSART"
echo ""

echo -e "  ${BOLD}$L_INTERNET_SECTION_CRYPTO${NC}"
printf "  %-32s %s\n" "Ledger Live/Wallet:"       "$STATUS_LEDGER"
printf "  %-32s %s\n" "Trezor Suite:"             "$STATUS_TREZOR"
echo ""

echo -e "  ${BOLD}$L_INTERNET_SECTION_NETWORK${NC}"
printf "  %-32s %s\n" "Remote Desktop Manager:"   "$STATUS_RDMANAGER"
printf "  %-32s %s\n" "IPMIView:"                 "$STATUS_IPMIVIEW"
printf "  %-32s %s\n" "DJI Assistant 2:"          "$STATUS_DJI"
echo ""

echo -e "  ${BOLD}IoT / iPad on Apple Silicon${NC}"
printf "  %-32s %s\n" "UniFi:"                    "$STATUS_UNIFI"
printf "  %-32s %s\n" "WiFiman:"                  "$STATUS_WIFIMAN"

echo ""
echo -e "  ${YELLOW}──────────────────────────────────────────────────────${NC}"
print_info "$L_INTERNET_CHECKED_NOTE"
print_info "$L_INTERNET_INSTRUCTIONS"

for status in \
    "$STATUS_CHROME" "$STATUS_FIREFOX" "$STATUS_BRAVE" "$STATUS_ATLAS" \
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
