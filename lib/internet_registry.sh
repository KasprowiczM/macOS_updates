#!/usr/bin/env bash
# lib/internet_registry.sh — load config/internet_app_methods.txt (Bash 3.2+)

_internet_methods_config_path() {
    echo "${SCRIPT_DIR}/config/internet_app_methods.txt"
}

_INTERNET_REGISTRY_LOADED=0

# Populates INTERNET_METHOD_APPS[], INTERNET_METHOD_TYPES[], INTERNET_METHOD_STATUS[]
internet_registry_load() {
    [ "${_INTERNET_REGISTRY_LOADED:-0}" -eq 1 ] && return 0
    local cfg line app method status
    INTERNET_METHOD_APPS=()
    INTERNET_METHOD_TYPES=()
    INTERNET_METHOD_STATUS=()
    INTERNET_METHOD_FEEDS=()
    cfg="$(_internet_methods_config_path)"
    [ -f "$cfg" ] || return 1
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line%%#*}"
        line="${line#"${line%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"
        [ -n "$line" ] || continue
        # Validate: 3 or 4 pipe-delimited fields (AppName|method|STATUS_VAR[|feed_url])
        case "$line" in
            *\|*\|*\|*\|*)
                echo "internet_registry_load: malformed row (more than 4 fields): $line" >&2
                continue
                ;;
            *\|*\|*\|*) ;;
            *\|*\|*) ;;
            *)
                echo "internet_registry_load: malformed row (need 3 or 4 fields): $line" >&2
                continue
                ;;
        esac
        app="${line%%|*}"
        line="${line#*|}"
        method="${line%%|*}"
        line="${line#*|}"
        case "$line" in
            *\|*)
                status="${line%%|*}"
                feed_url="${line#*|}"
                ;;
            *)
                status="$line"
                feed_url=""
                ;;
        esac
        INTERNET_METHOD_APPS+=("$app")
        INTERNET_METHOD_TYPES+=("$method")
        INTERNET_METHOD_STATUS+=("$status")
        INTERNET_METHOD_FEEDS+=("$feed_url")
    done < "$cfg"
    _INTERNET_REGISTRY_LOADED=1
    return 0
}

internet_registry_method_for() {
    local name="$1"
    local i
    internet_registry_load || return 1
    i=0
    while [ "$i" -lt "${#INTERNET_METHOD_APPS[@]}" ]; do
        if [ "${INTERNET_METHOD_APPS[$i]}" = "$name" ]; then
            echo "${INTERNET_METHOD_TYPES[$i]}"
            return 0
        fi
        i=$((i + 1))
    done
    return 1
}

# internet_effective_method <app> <config_method>
# The method that actually decides an app's update, for reporting
# (logs/version_history.tsv). A row in config/vendor_feeds.txt makes the vendor
# feed the source of truth for silent_launch / docker_cli / sparkle_appcast apps:
# internet_handler_vendor_truth (or Docker's verified DMG path) compares versions
# and installs directly; the configured method is only the fallback when the
# feed is unusable. Same rule as scripts/report_update_coverage.sh (vendor_feed).
# Other methods are returned unchanged. Every returned name is either a config
# method (with a handler, rule 6a) or "vendor_feed" (internet_handler_vendor_truth).
internet_effective_method() {
    local app="$1" method="$2"
    case "$method" in
        silent_launch|docker_cli|sparkle_appcast)
            if command -v vendor_feed_row >/dev/null 2>&1 && vendor_feed_row "$app" >/dev/null 2>&1; then
                printf 'vendor_feed\n'
                return 0
            fi
            ;;
    esac
    printf '%s\n' "$method"
}

_internet_dispatch_config_path() {
    echo "${SCRIPT_DIR}/config/internet_dispatch_order.txt"
}

# Presence is evaluated before headers or handler side effects. Catalog entries
# describe capability, never ownership. MAU can live outside application roots.
internet_app_present() {
    local path
    if [ "$1" = "Microsoft AutoUpdate" ]; then
        path="${MAC_UPDATE_MAU_APP:-/Library/Application Support/Microsoft/MAU2.0/Microsoft AutoUpdate.app}"
    else
        path="$(internet_app_path "$1" 2>/dev/null)"
    fi
    [ -n "$path" ] && [ -d "$path" ]
}

internet_dispatch_status_var() {
    case "$1" in
        iu_google_chrome) echo STATUS_CHROME ;;
        iu_firefox_developer_edition) echo STATUS_FIREFOX ;;
        iu_chatgpt) echo STATUS_CHATGPT ;;
        iu_claude) echo STATUS_CLAUDE_APP ;;
        iu_comet) echo STATUS_COMET ;;
        iu_antigravity) echo STATUS_ANTIGRAVITY ;;
        iu_antigravity_ide) echo STATUS_ANTIGRAVITY_IDE ;;
        iu_gemini) echo STATUS_GEMINI ;;
        iu_opencode_desktop) echo STATUS_OPENCODE ;;
        iu_keepassxc) echo STATUS_KEEPASSXC ;;
        iu_proton_mail) echo STATUS_PROTONMAIL ;;
        iu_google_drive) echo STATUS_GOOGLEDRIVE ;;
        iu_proton_drive) echo STATUS_PROTONDRIVE ;;
        iu_microsoft_365) echo STATUS_MICROSOFT ;;
        iu_microsoft_teams) echo STATUS_TEAMS ;;
        iu_visual_studio_code) echo STATUS_VSCODE ;;
        iu_codeedit) echo STATUS_CODEEDIT ;;
        iu_docker_desktop) echo STATUS_DOCKER ;;
        iu_warp) echo STATUS_WARP ;;
        iu_cursor) echo STATUS_CURSOR ;;
        iu_opendesign) echo STATUS_OPENDESIGN ;;
        iu_hyperframes) echo STATUS_HYPERFRAMES ;;
        iu_superset) echo STATUS_SUPERSET ;;
        iu_deepseek_harness) echo STATUS_DEEPSEEK ;;
        iu_grok_bot) echo STATUS_GROKBOT ;;
        iu_ledger) echo STATUS_LEDGER ;;
        iu_trezor_suite) echo STATUS_TREZOR ;;
        iu_remote_desktop_manager) echo STATUS_RDMANAGER ;;
        iu_ipmiview) echo STATUS_IPMIVIEW ;;
        *) return 1 ;;
    esac
}

internet_handler_has_local_target() {
    local wanted app method status rest
    wanted="$(internet_dispatch_status_var "$1")" || return 1
    if [ "$wanted" = "STATUS_MICROSOFT" ] && internet_app_present "Microsoft AutoUpdate"; then
        return 0
    fi
    while IFS='|' read -r app method status rest; do
        [ "$status" = "$wanted" ] || continue
        internet_app_present "$app" && return 0
    done < "$(_internet_methods_config_path)"
    return 1
}

# internet_handler_apps <handler> — installed app names this handler serves.
internet_handler_apps() {
    local wanted app method status rest
    wanted="$(internet_dispatch_status_var "$1")" || return 1
    while IFS='|' read -r app method status rest; do
        case "$app" in '#'*|'') continue ;; esac
        [ "$status" = "$wanted" ] || continue
        internet_app_present "$app" && printf '%s\n' "$app"
    done < "$(_internet_methods_config_path)"
    return 0
}

# internet_event_id <app> — the id the terminal interface uses for an internet
# app: its bundle id when the installed bundle is readable, else the registry name.
internet_event_id() {
    local path bid=""
    path="$(internet_app_path "$1" 2>/dev/null || true)"
    if [ -n "$path" ] && [ -d "$path" ] && type internet_app_bundle_id >/dev/null 2>&1; then
        bid="$(internet_app_bundle_id "$path" 2>/dev/null || true)"
    fi
    printf '%s\n' "${bid:-$1}"
}

# internet_override_mode <app> / internet_override_source <app>
# Overrides are keyed by bundle id (terminal interface) or registry name.
internet_override_mode() {
    type mu_override_mode >/dev/null 2>&1 || { echo auto; return 0; }
    mu_override_mode internet "$(internet_event_id "$1")" "$1"
}
internet_override_source() {
    type mu_override_source >/dev/null 2>&1 || return 0
    local src
    src="$(mu_override_source internet "$(internet_event_id "$1")")"
    [ -n "$src" ] || src="$(mu_override_source internet "$1")"
    printf '%s\n' "$src"
}

# internet_manual_check <app> <event-id>
#   manual mode still reports "update available" where a cheap existing check
#   exists (a configured vendor feed); nothing is downloaded or launched.
internet_manual_check() {
    local app="$1" ident="$2" path installed="" res latest="" rel=""
    path="$(internet_app_path "$app" 2>/dev/null || true)"
    [ -n "$path" ] && type app_version >/dev/null 2>&1 && installed="$(app_version "$path" 2>/dev/null || true)"
    if type vendor_feed_lookup >/dev/null 2>&1 && res="$(vendor_feed_lookup "$app" 2>/dev/null)"; then
        latest="${res%%|*}"
    fi
    if [ -n "$latest" ] && [ -n "$installed" ] && type internet_version_relation >/dev/null 2>&1; then
        rel="$(internet_version_relation "$latest" "$installed" 2>/dev/null || true)"
    fi
    if [ "$rel" = newer ]; then
        print_info "$app: update available ${installed} → ${latest} (manual by user override)"
        mu_item_end internet "$ident" needs_you "$installed" "$latest" "update available (manual)" manual_mode "$app"
    elif [ -n "$rel" ]; then
        mu_item_end internet "$ident" current "$installed" "$latest" "manual by user override" "" "$app"
    else
        print_info "$app: automatic update off (manual by user override)"
        mu_item_end internet "$ident" needs_you "$installed" "" "manual by user override" manual_mode "$app"
    fi
}

# internet_event_installed_version <app> — the version installed now (the same
# reader the preview and the run snapshots use); empty when unknown.
internet_event_installed_version() {
    local app="$1" path ver
    path="$(internet_app_path "$app" 2>/dev/null || true)"
    [ -n "$path" ] && [ -d "$path" ] || return 0
    ver="$(internet_app_snapshot_version "$path" 2>/dev/null || true)"
    [ "$ver" = "?" ] && ver=""
    printf '%s' "$ver"
}

# The version each app had before its handler ran, so item_end can say
# from -> to for every real-run result (a direct install included).
INTERNET_BEFORE_VERS=""
internet_event_remember_version() {
    INTERNET_BEFORE_VERS="${INTERNET_BEFORE_VERS}
$1	$2"
}
internet_event_recalled_version() {
    printf '%s\n' "$INTERNET_BEFORE_VERS" | awk -F'\t' -v id="$1" '$1 == id && v == "" { v = $2 } END { print v }'
}

# internet_dispatch_override_gate <handler>
#   Applies lib/overrides.sh (group "internet", id = bundle id or app name)
#   before a handler runs. Returns 1 when the handler must not run: every
#   served app is skip or manual, or the user chose another source that is
#   really available (brew: an installed cask; appstore: an App Store copy).
#   An unavailable source is ignored with a logged note. One handler serving
#   several apps (Microsoft AutoUpdate) runs when any of them stays automatic.
internet_dispatch_override_gate() {
    local fn="$1" var apps app mode source auto=0 manual=0 cask path any=0 ident
    type mu_override_mode >/dev/null 2>&1 || return 0
    var="$(internet_dispatch_status_var "$fn")" || return 0
    apps="$(internet_handler_apps "$fn")"
    [ -n "$apps" ] || return 0
    while IFS= read -r app; do
        [ -n "$app" ] || continue
        any=1
        ident="$(internet_event_id "$app")"
        mode="$(internet_override_mode "$app")"
        source="$(internet_override_source "$app")"
        case "$mode" in
            skip) mu_item_end internet "$ident" skipped "" "" "user override: skip" "" "$app"; continue ;;
            manual) manual=1; internet_manual_check "$app" "$ident"; continue ;;
        esac
        case "$source" in
            brew)
                cask="$(internet_cask_name_for_app "$app" 2>/dev/null || true)"
                if [ -n "$cask" ] && command -v brew >/dev/null 2>&1 \
                   && HOMEBREW_NO_AUTO_UPDATE=1 brew list --cask "$cask" >/dev/null 2>&1; then
                    print_info "$app: updated through Homebrew (user override source=brew)"
                    mu_item_end internet "$ident" skipped "" "" "source=brew: handled by the Homebrew step" "" "$app"
                    continue
                fi
                print_info "$app: source=brew ignored (no installed Homebrew cask); using the vendor method"
                ;;
            appstore)
                path="$(internet_app_path "$app" 2>/dev/null || true)"
                if [ -n "$path" ] && type app_store_managed >/dev/null 2>&1 && app_store_managed "$path"; then
                    print_info "$app: updated through the App Store (user override source=appstore)"
                    mu_item_end internet "$ident" skipped "" "" "source=appstore: handled by the App Store step" "" "$app"
                    continue
                fi
                print_info "$app: source=appstore ignored (not an App Store copy); using the vendor method"
                ;;
        esac
        auto=1
        _inet_before="$(internet_event_installed_version "$app")"
        internet_event_remember_version "$ident" "$_inet_before"
        mu_item_start internet "$ident" "$app" "$_inet_before" "" "${source:-vendor}"
        INTERNET_STARTED_IDS="${INTERNET_STARTED_IDS:-}|$ident|"
    done <<EOF_INTERNET_OVERRIDE_APPS
$apps
EOF_INTERNET_OVERRIDE_APPS
    [ "$any" -eq 1 ] || return 0
    [ "$auto" -eq 1 ] && return 0
    if [ "$manual" -eq 1 ]; then
        eval "$var=\"\${L_INTERNET_STATUS_MANUAL_UPDATE:-manual}\""
    else
        eval "$var=\"\${L_INTERNET_STATUS_SKIPPED:-skipped}\""
    fi
    INTERNET_OVERRIDDEN_VARS="${INTERNET_OVERRIDDEN_VARS:-} $var"
    return 1
}

# Run ordered handler functions from config/internet_dispatch_order.txt
internet_dispatch_run_all() {
    local cfg line fn
    cfg="$(_internet_dispatch_config_path)"
    [ -f "$cfg" ] || return 1
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line%%#*}"
        line="${line#"${line%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"
        [ -n "$line" ] || continue
        fn="$line"
        if type "$fn" >/dev/null 2>&1; then
            internet_handler_has_local_target "$fn" || continue
            internet_dispatch_override_gate "$fn" || continue
            "$fn"
        else
            print_warn "Missing internet handler: $fn"
            INTERNET_HARD_FAIL=1
            INTERNET_EXIT=1
        fi
    done < "$cfg"
    return 0
}
