#!/usr/bin/env bash
# lib/internet_app_updates.sh — per-app update handlers (sourced by update_internet_apps.sh)
# Requires: helpers from update_internet_apps.sh (print_*, app_version, silent_launch_app, etc.)

# Print "newer" only when the remote version is provably greater than the
# installed version. "current" includes equality and a local version ahead of
# the feed; "unknown" prevents replacement when either version is unparseable.
internet_version_relation() {
    python3 - "$1" "$2" <<'PYEOF'
import re
import sys


def version_key(value):
    match = re.search(r"\d+(?:\.\d+)*", value or "")
    if not match:
        return None
    numbers = [int(part) for part in match.group(0).split(".")]
    numbers = (numbers + [0] * 12)[:12]
    suffix = (value[match.end():] or "").lower().split("+", 1)[0]
    prerelease = suffix.lstrip("-._")
    prerelease_rank = 4
    for marker, rank in (("dev", 0), ("alpha", 1), ("a", 1), ("beta", 2), ("b", 2), ("rc", 3)):
        if prerelease.startswith(marker):
            prerelease_rank = rank
            break
    suffix_numbers = [int(part) for part in re.findall(r"\d+", suffix)]
    suffix_numbers = (suffix_numbers + [0] * 4)[:4]
    return tuple(numbers + [prerelease_rank] + suffix_numbers)


remote = version_key(sys.argv[1])
local = version_key(sys.argv[2])
if remote is None or local is None:
    print("unknown")
elif remote > local:
    print("newer")
else:
    print("current")
PYEOF
}

GOOGLE_KEYSTONE_RAN=0
GOOGLE_KEYSTONE_EXIT=1
MAU_TEAMS21_VERIFIED=0
google_keystone_check() {
    local agent="$1"
    local output=""
    if [ "$GOOGLE_KEYSTONE_RAN" -eq 1 ]; then
        return "$GOOGLE_KEYSTONE_EXIT"
    fi
    GOOGLE_KEYSTONE_RAN=1
    output=$(run_with_timeout 180 "$agent" --runMode ondemand 2>&1)
    GOOGLE_KEYSTONE_EXIT=$?
    if [ "$GOOGLE_KEYSTONE_EXIT" -ne 0 ]; then
        internet_diag_log "ERROR: Google Keystone check failed (exit=$GOOGLE_KEYSTONE_EXIT)"
        [ -n "$output" ] && printf '%s\n' "$output" | tail -n 20
    fi
    return "$GOOGLE_KEYSTONE_EXIT"
}

iu_google_chrome() {
    print_header "🟡 Google Chrome"
    if [ -d "/Applications/Google Chrome.app" ]; then
        VER=$(app_version "/Applications/Google Chrome.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        # Keystone (Omaha) — oficjalny updater Google dla macOS
        KEYSTONE_AGENT="/Library/Google/GoogleSoftwareUpdate/GoogleSoftwareUpdate.bundle/Contents/Resources/GoogleSoftwareUpdateAgent.app/Contents/MacOS/GoogleSoftwareUpdateAgent"
        if [ -f "$KEYSTONE_AGENT" ]; then
            print_step "$L_INTERNET_LAUNCHING_KEYSTONE"
            if google_keystone_check "$KEYSTONE_AGENT"; then
                print_ok "$(internet_msg "$L_INTERNET_KEYSTONE_STARTED" "Chrome")"
                STATUS_CHROME="$L_INTERNET_STATUS_CHECKED_CLI"
            else
                print_warn "Google Keystone failed to check for Chrome updates"
                STATUS_CHROME="$L_INTERNET_STATUS_LAUNCH_FAILED"
            fi
        else
            print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "Chrome")"
            if silent_launch_app "Google Chrome"; then
                print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "Chrome → Pomoc → O Google Chrome")"
                STATUS_CHROME="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
            else
                STATUS_CHROME="$L_INTERNET_STATUS_LAUNCH_FAILED"
            fi
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Google Chrome")"
    fi

    # ── 2. FIREFOX DEVELOPER EDITION ──────────────────────────────
}

iu_firefox_developer_edition() {
    print_header "🦊 Firefox Developer Edition"
    if [ -d "/Applications/Firefox Developer Edition.app" ]; then
        VER=$(firefox_dev_version)
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"

        LATEST_FF=$(curl -s --max-time 20 --retry 2 \
            "https://product-details.mozilla.org/1.0/firefox_versions.json" 2>/dev/null \
            | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('FIREFOX_DEVEDITION','?'))" \
            2>/dev/null || echo "?")

        # Normalizuj wersję API: usuń sufiks beta np. "150.0b5" → "150.0"
        # CFBundleShortVersionString i application.ini przechowują wersję bazową bez sufiksu,
        # a Mozilla API zwraca pełną wersję z sufiksem (np. "150.0b5").
        # Porównujemy wersje bazowe, żeby uniknąć ciągłego pobierania tej samej wersji.
        LATEST_FF_BASE=$(echo "$LATEST_FF" | sed 's/b[0-9]*$//')
        FF_RELATION="$(internet_version_relation "$LATEST_FF_BASE" "$VER")"

        if [ "$LATEST_FF" = "?" ]; then
            print_warn "$(internet_msg "$L_INTERNET_OFFLINE" "Mozilla API")"
            if silent_launch_app "Firefox Developer Edition"; then
                print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "Firefox → Pomoc → O Firefoksie")"
                STATUS_FIREFOX="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
            else
                STATUS_FIREFOX="$L_INTERNET_STATUS_LAUNCH_FAILED"
            fi
        elif [ "$FF_RELATION" = "unknown" ]; then
            print_warn "$(internet_msg "$L_INTERNET_UNKNOWN_DETECTED" "Firefox Developer Edition version")"
            STATUS_FIREFOX="$L_INTERNET_STATUS_UNKNOWN_VERSION"
        elif [ "$FF_RELATION" = "current" ]; then
            # Equal or local ahead (e.g. local=150.0.1, remote=150.0b5).
            print_ok "$(internet_msg "$L_INTERNET_APP_CURRENT" "Firefox Developer Edition" "$VER (remote: $LATEST_FF)")"
            STATUS_FIREFOX="$(internet_msg "$L_INTERNET_STATUS_CURRENT_FMT" "$LATEST_FF")"
        else
            print_warn "$(internet_msg "$L_INTERNET_NEW_VERSION_AVAILABLE" "$LATEST_FF" "$VER")"
            print_step "$(internet_msg "$L_INTERNET_DOWNLOADING_APPLE_SILICON" "Firefox Developer Edition" "$LATEST_FF")"
            FF_URL="https://download.mozilla.org/?product=firefox-devedition-latest&os=osx&lang=pl"
            TEMP_DMG="$(make_temp_dmg Firefox_DevEd)"
            if curl -L --max-time 180 --retry 3 --retry-delay 2 -o "$TEMP_DMG" "$FF_URL" 2>/dev/null; then
                FF_MOUNT="$(mount_verified_dmg "$TEMP_DMG")"
                if [ -n "$FF_MOUNT" ]; then
                    if [ -d "$FF_MOUNT/Firefox Developer Edition.app" ]; then
                        FF_SOURCE_VER=$(app_version "$FF_MOUNT/Firefox Developer Edition.app")
                        if [ "$(internet_version_relation "$FF_SOURCE_VER" "$VER")" != "newer" ]; then
                            print_warn "Refusing non-newer Firefox payload: $FF_SOURCE_VER (installed: $VER)"
                            STATUS_FIREFOX="$L_INTERNET_STATUS_INSTALL_ERROR"
                        elif copy_verified_app "$FF_MOUNT/Firefox Developer Edition.app" "Firefox Developer Edition.app"; then
                            NEW_VER=$(firefox_dev_version)
                            print_ok "$(internet_msg "$L_INTERNET_APP_UPDATED" "Firefox Developer Edition" "$NEW_VER")"
                            STATUS_FIREFOX="$(internet_msg "$L_INTERNET_STATUS_UPDATED_FMT" "$NEW_VER")"
                        else
                            print_warn "$(internet_msg "$L_INTERNET_COPY_VERIFIED_FAILED" "Firefox Developer Edition")"
                            STATUS_FIREFOX="$L_INTERNET_STATUS_INSTALL_ERROR"
                        fi
                    else
                        print_warn "$(internet_msg "$L_INTERNET_APP_NOT_FOUND_VOLUME" "Firefox Developer Edition")"
                        STATUS_FIREFOX="$L_INTERNET_STATUS_INSTALL_ERROR"
                    fi
                    detach_verified_dmg "$FF_MOUNT" || true
                else
                    print_warn "$L_INTERNET_MOUNT_DMG_MANUAL"
                    STATUS_FIREFOX="$L_INTERNET_STATUS_MOUNT_ERROR"
                fi
                rm -f "$TEMP_DMG"
            else
                print_warn "$L_INTERNET_DOWNLOAD_VERIFY_FAILED"
                print_info "$(internet_msg "$L_INTERNET_DOWNLOAD_MANUALLY" "https://www.mozilla.org/pl/firefox/developer/")"
                STATUS_FIREFOX="$L_INTERNET_STATUS_DOWNLOAD_ERROR"
                rm -f "$TEMP_DMG" 2>/dev/null || true
            fi
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Firefox Developer Edition")"
    fi

    # ── 3. (Opera removed — no longer installed) ─────────────────


    # ── 4. BRAVE BROWSER ──────────────────────────────────────────
}

iu_brave_browser() {
    print_header "🦁 Brave Browser"
    if [ -d "/Applications/Brave Browser.app" ]; then
        VER=$(app_version "/Applications/Brave Browser.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "Brave")"
        if silent_launch_app "Brave Browser"; then
            print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "Brave → Pomoc → O Brave Browser")"
            STATUS_BRAVE="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
        else
            STATUS_BRAVE="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Brave Browser")"
    fi

    # ── 4b. CHATGPT ATLAS (Sparkle appcast + DMG) ────────────────
}

iu_chatgpt_atlas() {
    print_header "🔵 ChatGPT Atlas"
    # Atlas może być zainstalowany jako "ChatGPT Atlas.app" lub "Atlas.app"
    ATLAS_APP=""
    for apath in "/Applications/ChatGPT Atlas.app" "/Applications/Atlas.app"; do
        [ -d "$apath" ] && ATLAS_APP="$apath" && break
    done
    if [ -n "$ATLAS_APP" ]; then
        VER=$(app_version "$ATLAS_APP")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"

        # Pobierz najnowszą wersję z Sparkle appcast OpenAI
        ATLAS_XML=$(curl -s --compressed --max-time 20 --retry 3 --retry-delay 2 \
            "https://persistent.oaistatic.com/atlas/public/sparkle_public_appcast.xml" 2>/dev/null)
        # Parse the highest shortVersionString (appcast may have multiple items)
        ATLAS_LATEST=$(echo "$ATLAS_XML" | grep 'sparkle:shortVersionString' | \
            sed 's|.*<sparkle:shortVersionString>\(.*\)</sparkle:shortVersionString>.*|\1|' | \
            sort -V | tail -1)
        ATLAS_DMG_URL=$(echo "$ATLAS_XML" | grep -m1 'enclosure url=".*\.dmg"' | \
            sed 's|.*enclosure url="\([^"]*\.dmg\)".*|\1|')
        ATLAS_RELATION="$(internet_version_relation "$ATLAS_LATEST" "$VER")"

        if [ -z "$ATLAS_LATEST" ]; then
            print_warn "$(internet_msg "$L_INTERNET_OFFLINE" "OpenAI server")"
            STATUS_ATLAS="$L_INTERNET_STATUS_OFFLINE"
        elif [ "$ATLAS_RELATION" = "unknown" ]; then
            print_warn "$(internet_msg "$L_INTERNET_UNKNOWN_DETECTED" "ChatGPT Atlas version")"
            STATUS_ATLAS="$L_INTERNET_STATUS_UNKNOWN_VERSION"
        elif [ "$ATLAS_RELATION" = "current" ]; then
            print_ok "$(internet_msg "$L_INTERNET_APP_CURRENT" "ChatGPT Atlas" "$VER (remote: $ATLAS_LATEST)")"
            STATUS_ATLAS="$L_INTERNET_STATUS_CURRENT"
        else
            print_warn "$(internet_msg "$L_INTERNET_NEW_VERSION_AVAILABLE" "$ATLAS_LATEST" "$VER")"
            if [ -n "$ATLAS_DMG_URL" ]; then
                print_step "$(internet_msg "$L_INTERNET_DOWNLOADING_SIZE" "ChatGPT Atlas" "$ATLAS_LATEST" "~250 MB")"
                TEMP_DMG="$(make_temp_dmg ChatGPT_Atlas)"
                if curl -L --max-time 300 --retry 3 --retry-delay 2 -o "$TEMP_DMG" "$ATLAS_DMG_URL" 2>/dev/null; then
                    ATLAS_MOUNT="$(mount_verified_dmg "$TEMP_DMG")"
                    if [ -n "$ATLAS_MOUNT" ]; then
                        ATLAS_SRC=""
                        for ATLAS_CANDIDATE in "$ATLAS_MOUNT/ChatGPT Atlas.app" "$ATLAS_MOUNT/Atlas.app"; do
                            [ -d "$ATLAS_CANDIDATE" ] && ATLAS_SRC="$ATLAS_CANDIDATE" && break
                        done
                        if [ -n "$ATLAS_SRC" ]; then
                            ATLAS_DEST="$(basename "$ATLAS_APP")"
                            ATLAS_SOURCE_VER=$(app_version "$ATLAS_SRC")
                            if [ "$(internet_version_relation "$ATLAS_SOURCE_VER" "$VER")" != "newer" ]; then
                                print_warn "Refusing non-newer Atlas payload: $ATLAS_SOURCE_VER (installed: $VER)"
                                STATUS_ATLAS="$L_INTERNET_STATUS_INSTALL_ERROR"
                            elif copy_verified_app "$ATLAS_SRC" "$ATLAS_DEST"; then
                                print_ok "$(internet_msg "$L_INTERNET_APP_COPIED" "$ATLAS_DEST")"
                                NEW_VER=$(app_version "$ATLAS_APP")
                                print_ok "$(internet_msg "$L_INTERNET_APP_UPDATED" "ChatGPT Atlas" "$NEW_VER")"
                                STATUS_ATLAS="$(internet_msg "$L_INTERNET_STATUS_UPDATED_FMT" "$NEW_VER")"
                            else
                                print_warn "$(internet_msg "$L_INTERNET_COPY_ERROR" "$ATLAS_DEST")"
                                STATUS_ATLAS="$L_INTERNET_STATUS_INSTALL_ERROR"
                            fi
                        else
                            print_warn "$L_INTERNET_APP_NOT_ON_VOLUME"
                            STATUS_ATLAS="$L_INTERNET_STATUS_INSTALL_ERROR"
                        fi
                        detach_verified_dmg "$ATLAS_MOUNT" || true
                    else
                        print_warn "$L_INTERNET_MOUNT_DMG_FAILED"
                        STATUS_ATLAS="$L_INTERNET_STATUS_MOUNT_ERROR"
                    fi
                    rm -f "$TEMP_DMG"
                else
                    print_warn "$L_INTERNET_DOWNLOAD_VERIFY_FAILED"
                    print_info "$(internet_msg "$L_INTERNET_DOWNLOAD_MANUALLY" "https://chatgpt.com/atlas/")"
                    STATUS_ATLAS="$L_INTERNET_STATUS_DOWNLOAD_ERROR"
                    rm -f "$TEMP_DMG" 2>/dev/null || true
                fi
            else
                print_warn "$L_INTERNET_NO_DOWNLOAD_URL"
                print_info "$(internet_msg "$L_INTERNET_DOWNLOAD_MANUALLY" "https://chatgpt.com/atlas/")"
                STATUS_ATLAS="$L_INTERNET_STATUS_NO_URL"
            fi
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "ChatGPT Atlas")"
        print_info "$(internet_msg "$L_INTERNET_DOWNLOAD_FROM" "https://chatgpt.com/atlas/")"
    fi

    # ============================================================
    # ██ SEKCJA 2: APLIKACJE AI
    # ============================================================

    # ── 5. CHATGPT ────────────────────────────────────────────────
}

iu_chatgpt() {
    print_header "🤖 ChatGPT / Codex (OpenAI)"
    OPENAI_APP="$(internet_app_path "ChatGPT / Codex" 2>/dev/null || true)"
    if [ -n "$OPENAI_APP" ] && [ -d "$OPENAI_APP" ]; then
        VER=$(app_version "$OPENAI_APP")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION_EXTRA" "$VER" "bundle: com.openai.codex")"
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "ChatGPT / Codex")"
        if silent_launch_app "$OPENAI_APP"; then
            print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "ChatGPT / Codex → Check for updates")"
            STATUS_CHATGPT="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
        else
            STATUS_CHATGPT="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "ChatGPT / Codex (com.openai.codex)")"
    fi

    # ── 6. CLAUDE (aplikacja desktopowa) ──────────────────────────
}

iu_claude() {
    print_header "🟣 Claude"
    if [ -d "/Applications/Claude.app" ]; then
        VER=$(app_version "/Applications/Claude.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "Claude")"
        if silent_launch_app "Claude"; then
            print_info "$(internet_msg "$L_INTERNET_AUTO_UPDATES_SPARKLE" "Claude")"
            STATUS_CLAUDE_APP="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
        else
            STATUS_CLAUDE_APP="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Claude Desktop")"
    fi

    # ── 7. COMET (Perplexity AI) ──────────────────────────────────
}

iu_comet() {
    print_header "☄️  Comet (Perplexity AI)"
    if [ -d "/Applications/Comet.app" ]; then
        VER=$(app_version "/Applications/Comet.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "Comet")"
        if silent_launch_app "Comet"; then
            print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "Comet → Pomoc → O Comet")"
            STATUS_COMET="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
        else
            STATUS_COMET="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Comet")"
    fi

    # ── 8. ANTIGRAVITY ────────────────────────────────────────────
}

iu_antigravity() {
    print_header "🪐 Antigravity"
    if [ -d "/Applications/Antigravity.app" ]; then
        VER=$(app_version "/Applications/Antigravity.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "Antigravity")"
        if silent_launch_app "Antigravity"; then
            print_info "$(internet_msg "$L_INTERNET_AUTO_UPDATES" "Antigravity")"
            STATUS_ANTIGRAVITY="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
        else
            STATUS_ANTIGRAVITY="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Antigravity")"
    fi

    # ── 8a. ANTIGRAVITY IDE ───────────────────────────────────────
}

iu_antigravity_ide() {
    print_header "🪐 Antigravity IDE"
    if [ -d "/Applications/Antigravity IDE.app" ]; then
        VER=$(app_version "/Applications/Antigravity IDE.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "Antigravity IDE")"
        if silent_launch_app "Antigravity IDE"; then
            print_info "$(internet_msg "$L_INTERNET_AUTO_UPDATES" "Antigravity IDE")"
            STATUS_ANTIGRAVITY_IDE="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
        else
            STATUS_ANTIGRAVITY_IDE="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Antigravity IDE")"
        STATUS_ANTIGRAVITY_IDE="$L_INTERNET_STATUS_SKIPPED"
    fi

    # ── 8b. GEMINI DESKTOP ───────────────────────────────────────
}

iu_gemini() {
    print_header "✨ Gemini"
    if [ -d "/Applications/Gemini.app" ]; then
        VER=$(app_version "/Applications/Gemini.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "Gemini")"
        if silent_launch_app "Gemini"; then
            print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "Gemini → app menu → Check for updates")"
            STATUS_GEMINI="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
        else
            STATUS_GEMINI="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Gemini")"
        STATUS_GEMINI="$L_INTERNET_STATUS_SKIPPED"
    fi

    # ── 9. LM STUDIO ──────────────────────────────────────────────
}

iu_lm_studio() {
    print_header "🧠 LM Studio"
    if [ -d "/Applications/LM Studio.app" ]; then
        VER=$(app_version "/Applications/LM Studio.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "LM Studio")"
        if silent_launch_app "LM Studio"; then
            print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "LM Studio → menu → Check for updates")"
            STATUS_LMSTUDIO="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
        else
            STATUS_LMSTUDIO="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "LM Studio")"
    fi

    # ── 10. PERPLEXITY DESKTOP ────────────────────────────────────
}

iu_perplexity_desktop() {
    print_header "🔍 Perplexity Desktop"
    # Perplexity Desktop — bezpośrednie pobranie z perplexity.ai (bundle: ai.perplexity.mac)
    # Uwaga: wersja z App Store (mas) jest obsługiwana przez update_appstore.sh
    if [ -d "/Applications/Perplexity.app" ]; then
        VER=$(app_version "/Applications/Perplexity.app")
        BUNDLE_ID=$(defaults read "/Applications/Perplexity.app/Contents/Info" CFBundleIdentifier 2>/dev/null || echo "?")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION_EXTRA" "$VER" "bundle: $BUNDLE_ID")"
        if echo "$BUNDLE_ID" | grep -q "perplexity"; then
            print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "Perplexity")"
            if silent_launch_app "Perplexity"; then
                print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "Perplexity → Perplexity → Check for updates")"
                print_info "Strona pobierania: https://www.perplexity.ai/platforms"
                STATUS_PERPLEXITY="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
            else
                STATUS_PERPLEXITY="$L_INTERNET_STATUS_LAUNCH_FAILED"
            fi
        else
            print_info "$(internet_msg "$L_INTERNET_UNKNOWN_DETECTED" "Perplexity")"
            STATUS_PERPLEXITY="$L_INTERNET_STATUS_UNKNOWN_VERSION"
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Perplexity Desktop")"
        print_info "$(internet_msg "$L_INTERNET_DOWNLOAD_FROM" "https://www.perplexity.ai/platforms (lub przez App Store)")"
    fi

    # ── 11b. OPENCODE DESKTOP (SST/opencode) ──────────────────────
}

iu_opencode_desktop() {
    print_header "🤖 OpenCode Desktop"
    # OpenCode — agent kodowania AI (SST), dostępny jako CLI (npm) i Desktop app
    # Strona: https://opencode.ai | GitHub: sst/opencode
    # Uwaga: npm package `opencode-ai` dostarcza CLI `opencode` (brak .app)
    #        Desktop App: pobierz z https://opencode.ai/download
    OPENCODE_APP_PATH=""
    for _oc_path in "/Applications/opencode.app" "/Applications/OpenCode.app" \
                    "/Applications/Opencode.app" "/Applications/opencode Desktop.app"; do
        if [ -d "$_oc_path" ]; then
            OPENCODE_APP_PATH="$_oc_path"
            break
        fi
    done
    if [ -n "$OPENCODE_APP_PATH" ]; then
        VER=$(app_version "$OPENCODE_APP_PATH")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION_EXTRA" "$VER" "$OPENCODE_APP_PATH")"
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "OpenCode Desktop")"
        if silent_launch_app "$OPENCODE_APP_PATH"; then
            print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "https://opencode.ai")"
            print_info "Uwaga: CLI 'opencode' aktualizowane osobno przez update_npm_cli.sh"
            STATUS_OPENCODE="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
        else
            STATUS_OPENCODE="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED_AS_APP" "OpenCode Desktop")"
        print_info "$(internet_msg "$L_INTERNET_CLI_MANAGED_SEPARATE" "opencode")"
        print_info "Desktop App: pobierz z https://opencode.ai"
        STATUS_OPENCODE="$L_INTERNET_STATUS_NO_DESKTOP_APP"
    fi

    # ============================================================
    # ██ SEKCJA 3: VPN I BEZPIECZEŃSTWO
    # ============================================================

    # ── 12. PROTONVPN ─────────────────────────────────────────────
}

iu_protonvpn() {
    print_header "🛡️  ProtonVPN"
    if [ -d "/Applications/ProtonVPN.app" ]; then
        VER=$(app_version "/Applications/ProtonVPN.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "ProtonVPN")"
        if silent_launch_app "ProtonVPN"; then
            print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "ProtonVPN → Check for updates")"
            STATUS_PROTONVPN="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
        else
            STATUS_PROTONVPN="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "ProtonVPN")"
    fi

    # ── 13. KEEPASSXC (GitHub API + DMG arm64) ────────────────────
}

iu_keepassxc() {
    print_header "🔑 KeePassXC"
    if [ -d "/Applications/KeePassXC.app" ]; then
        VER=$(app_version "/Applications/KeePassXC.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"

        LATEST_KPX_TAG=$(github_latest_tag "keepassxreboot/keepassxc")
        LATEST_KPX=$(echo "$LATEST_KPX_TAG" | sed 's/^v//')
        KPX_RELATION="$(internet_version_relation "$LATEST_KPX" "$VER")"
        # Arch detection for DMG URL
        KPX_ARCH=$([ "$(uname -m)" = "arm64" ] && echo "arm64" || echo "x86_64")

        if [ "$LATEST_KPX" = "?" ]; then
            print_warn "$(internet_msg "$L_INTERNET_OFFLINE" "GitHub")"
            if silent_launch_app "KeePassXC"; then
                print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "KeePassXC → Check for updates")"
                STATUS_KEEPASSXC="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
            else
                STATUS_KEEPASSXC="$L_INTERNET_STATUS_LAUNCH_FAILED"
            fi
        elif [ "$KPX_RELATION" = "unknown" ]; then
            print_warn "$(internet_msg "$L_INTERNET_UNKNOWN_DETECTED" "KeePassXC version")"
            STATUS_KEEPASSXC="$L_INTERNET_STATUS_UNKNOWN_VERSION"
        elif [ "$KPX_RELATION" = "current" ]; then
            print_ok "$(internet_msg "$L_INTERNET_APP_CURRENT" "KeePassXC" "$VER (remote: $LATEST_KPX)")"
            STATUS_KEEPASSXC="$L_INTERNET_STATUS_CURRENT"
        else
            print_warn "$(internet_msg "$L_INTERNET_NEW_VERSION_AVAILABLE" "$LATEST_KPX" "$VER")"
            print_step "$(internet_msg "$L_INTERNET_DOWNLOADING" "KeePassXC" "$LATEST_KPX ($KPX_ARCH)")"
            KPX_URL="https://github.com/keepassxreboot/keepassxc/releases/download/${LATEST_KPX_TAG}/KeePassXC-${LATEST_KPX}-${KPX_ARCH}.dmg"
            TEMP_DMG="$(make_temp_dmg KeePassXC)"
            if curl -L --max-time 180 --retry 3 --retry-delay 2 -o "$TEMP_DMG" "$KPX_URL" 2>/dev/null; then
                KPX_MOUNT="$(mount_verified_dmg "$TEMP_DMG")"
                if [ -n "$KPX_MOUNT" ]; then
                    if [ -d "$KPX_MOUNT/KeePassXC.app" ]; then
                        KPX_SOURCE_VER=$(app_version "$KPX_MOUNT/KeePassXC.app")
                        if [ "$(internet_version_relation "$KPX_SOURCE_VER" "$VER")" != "newer" ]; then
                            print_warn "Refusing non-newer KeePassXC payload: $KPX_SOURCE_VER (installed: $VER)"
                            STATUS_KEEPASSXC="$L_INTERNET_STATUS_INSTALL_ERROR"
                        elif copy_verified_app "$KPX_MOUNT/KeePassXC.app" "KeePassXC.app"; then
                            print_ok "$(internet_msg "$L_INTERNET_APP_COPIED" "KeePassXC")"
                            NEW_VER=$(app_version "/Applications/KeePassXC.app")
                            print_ok "$(internet_msg "$L_INTERNET_APP_UPDATED" "KeePassXC" "$NEW_VER")"
                            STATUS_KEEPASSXC="$(internet_msg "$L_INTERNET_STATUS_UPDATED_FMT" "$NEW_VER")"
                        else
                            print_warn "$(internet_msg "$L_INTERNET_COPY_ERROR" "KeePassXC")"
                            STATUS_KEEPASSXC="$L_INTERNET_STATUS_INSTALL_ERROR"
                        fi
                    else
                        print_warn "$(internet_msg "$L_INTERNET_APP_NOT_FOUND_VOLUME" "KeePassXC")"
                        STATUS_KEEPASSXC="$L_INTERNET_STATUS_INSTALL_ERROR"
                    fi
                    detach_verified_dmg "$KPX_MOUNT" || true
                else
                    print_warn "$L_INTERNET_MOUNT_DMG_FAILED"
                    STATUS_KEEPASSXC="$L_INTERNET_STATUS_MOUNT_ERROR"
                fi
                rm -f "$TEMP_DMG"
            else
                print_warn "$L_INTERNET_DOWNLOAD_VERIFY_FAILED"
                print_info "$(internet_msg "$L_INTERNET_DOWNLOAD_MANUALLY" "https://keepassxc.org/download/")"
                STATUS_KEEPASSXC="$L_INTERNET_STATUS_DOWNLOAD_ERROR"
                rm -f "$TEMP_DMG" 2>/dev/null || true
            fi
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "KeePassXC")"
    fi

    # ============================================================
    # ██ SEKCJA 4: POCZTA I KOMUNIKACJA
    # ============================================================

    # ── 14. PROTON MAIL ───────────────────────────────────────────
}

iu_proton_mail() {
    print_header "📧 Proton Mail"
    if [ -d "/Applications/Proton Mail.app" ]; then
        VER=$(app_version "/Applications/Proton Mail.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"

        # Proton does not publish a stable public desktop-release endpoint.
        # Trigger its built-in updater and report the result honestly instead
        # of turning the chronic GitHub 404 into a false offline failure.
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "Proton Mail")"
        if silent_launch_app "/Applications/Proton Mail.app"; then
            print_info "$(internet_msg "$L_INTERNET_AUTO_UPDATES_SPARKLE" "Proton Mail")"
            STATUS_PROTONMAIL="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
        else
            STATUS_PROTONMAIL="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Proton Mail")"
    fi

    # ── 15. ZOOM ──────────────────────────────────────────────────
}

iu_zoom() {
    print_header "📹 Zoom"
    ZOOM_PATH=""
    for p in "/Applications/zoom.us.app" "${HOME}/Applications/zoom.us.app"; do
        if [ -d "$p" ]; then ZOOM_PATH="$p"; break; fi
    done
    if [ -n "$ZOOM_PATH" ]; then
        VER=$(app_version "$ZOOM_PATH")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION_EXTRA" "$VER" "$ZOOM_PATH")"
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "Zoom")"
        if silent_launch_app "zoom.us" || silent_launch_app "$ZOOM_PATH"; then
            print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "zoom.us → Check for updates")"
            STATUS_ZOOM="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
        else
            STATUS_ZOOM="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Zoom")"
    fi

    # ── 15b. (Signal removed — no longer installed) ──────────────


    # ============================================================
    # ██ SEKCJA 5: PRZECHOWYWANIE W CHMURZE
    # ============================================================

    # ── 16. GOOGLE DRIVE ──────────────────────────────────────────
}

iu_google_drive() {
    print_header "🟢 Google Drive"
    if [ -d "/Applications/Google Drive.app" ]; then
        VER=$(app_version "/Applications/Google Drive.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        KEYSTONE_AGENT="/Library/Google/GoogleSoftwareUpdate/GoogleSoftwareUpdate.bundle/Contents/Resources/GoogleSoftwareUpdateAgent.app/Contents/MacOS/GoogleSoftwareUpdateAgent"
        if [ -f "$KEYSTONE_AGENT" ]; then
            print_step "$L_INTERNET_LAUNCHING_KEYSTONE_DRIVE"
            if google_keystone_check "$KEYSTONE_AGENT"; then
                print_ok "$(internet_msg "$L_INTERNET_KEYSTONE_STARTED" "Google Drive")"
                STATUS_GOOGLEDRIVE="$L_INTERNET_STATUS_CHECKED_CLI"
            else
                print_warn "Google Keystone failed to check for Google Drive updates"
                STATUS_GOOGLEDRIVE="$L_INTERNET_STATUS_LAUNCH_FAILED"
            fi
        else
            print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "Google Drive")"
            if silent_launch_app "Google Drive"; then
                print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "Google Drive → O Google Drive")"
                STATUS_GOOGLEDRIVE="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
            else
                STATUS_GOOGLEDRIVE="$L_INTERNET_STATUS_LAUNCH_FAILED"
            fi
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Google Drive")"
    fi

    # ── 17. MEGASYNC ──────────────────────────────────────────────
}

iu_megasync() {
    print_header "☁️  MEGAsync"
    if [ -d "/Applications/MEGAsync.app" ]; then
        VER=$(app_version "/Applications/MEGAsync.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "MEGAsync")"
        if silent_launch_app "MEGAsync"; then
            print_info "$(internet_msg "$L_INTERNET_AUTO_UPDATES_SPARKLE" "MEGAsync")"
            STATUS_MEGASYNC="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
        else
            STATUS_MEGASYNC="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "MEGAsync")"
    fi

    # ── 18. PROTON DRIVE ──────────────────────────────────────────
}

iu_proton_drive() {
    print_header "🔵 Proton Drive"
    if [ -d "/Applications/Proton Drive.app" ]; then
        VER=$(app_version "/Applications/Proton Drive.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "Proton Drive")"
        if silent_launch_app "Proton Drive"; then
            print_info "$(internet_msg "$L_INTERNET_AUTO_UPDATES_SPARKLE" "Proton Drive")"
            STATUS_PROTONDRIVE="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
        else
            STATUS_PROTONDRIVE="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Proton Drive")"
    fi

    # ============================================================
    # ██ SEKCJA 6: MICROSOFT 365
    # ============================================================

}

# ── Microsoft AutoUpdate (msupdate) helpers ───────────────────
# msupdate draws a carriage-return progress spinner with ANSI erase-line
# codes, so its raw output is NOT line-oriented. Captured verbatim on this
# Mac (cat -v) — three physical lines, the last one without a newline:
#   ^M
#   ^M^[[2K^MChecking for updates...^M^[[2K^MUpdate Assistant: Idle^M...^M^[[2K^MNo updates available^M
#   ^M^[[2K^MUpdate Assistant: Idle
# The old parser only dropped blank lines and lines containing "No updates",
# so that trailing "Update Assistant: Idle" fragment was counted as one
# pending update. That triggered a pointless msupdate --install which hung
# until the timeout and failed the whole internet-apps step.

# Microsoft product IDs documented for msupdate --apps. Used as a fast path so
# that IDs without a digit (WDAVSHIM) are still recognised; every other ID
# falls through to the generic shape check in mau_classify_output.
MAU_KNOWN_PRODUCT_IDS="MSau04 MSWD2019 XCEL2019 PPT32019 OPIM2019 ONMC2019 TEAMS21 WDAVSHIM OLIC02"
# The five Office DeferralDays entries left behind by the 2026-07-14 Office
# Preview package-regression quarantine.
MAU_OFFICE_DEFERRAL_IDS="MSWD2019 XCEL2019 PPT32019 OPIM2019 ONMC2019"
# DeferralVersions pins the MAXIMUM version MAU will ever offer, so a pin at
# the installed build blocks all future updates for that product.
MAU_STALE_DEFERRAL_VERSION_IDS="TEAMS21"

# Turn raw msupdate output into clean logical lines: drop ANSI escape
# sequences, translate carriage returns into newlines so the spinner's
# overwritten segments become separate lines, trim each line, drop empties.
mau_sanitize_output() {
    local esc
    esc="$(printf '\033')"
    printf '%s\n' "$1" \
        | tr '\r' '\n' \
        | sed "s/${esc}\\[[0-9;?]*[0-9A-Za-z]//g" \
        | tr -d '\001-\010\013\014\016-\037\177' \
        | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e '/^$/d'
}

# Classify every sanitized line as "NOISE", "ID<tab><product-id>" or
# "UNKNOWN<tab><line>". Requiring a positively identified product ID is the
# whole point: the previous "anything that is not blank" filter is what caused
# the false positive. A line we cannot identify is reported for diagnostics,
# never counted as a pending update.
mau_classify_output() {
    mau_sanitize_output "$1" | awk -v known=" $MAU_KNOWN_PRODUCT_IDS " '
        function is_product_id(tok) {
            if (tok == "") return 0
            if (index(known, " " tok " ") > 0) return 1
            if (length(tok) < 5 || length(tok) > 8) return 0
            if (tok !~ /^[A-Z]/) return 0
            if (tok !~ /[0-9]/) return 0
            if (tok ~ /^[A-Z][A-Z0-9]*$/) return 1
            if (tok ~ /^[A-Z][A-Za-z]+[0-9]+$/) return 1
            return 0
        }
        {
            if ($0 ~ /^[Uu]pdate [Aa]ssistant:/ \
                || $0 ~ /^Checking for updates/ \
                || $0 ~ /^Detecting and downloading/ \
                || $0 ~ /^Found the following/ \
                || $0 ~ /[Nn]o updates available/) {
                print "NOISE\t" $0
                next
            }
            # Real entries carry the ID in parentheses, e.g. "Word (MSWD2019)".
            rest = $0
            while (match(rest, /\([A-Za-z0-9]+\)/)) {
                tok = substr(rest, RSTART + 1, RLENGTH - 2)
                if (is_product_id(tok)) { print "ID\t" tok; next }
                rest = substr(rest, RSTART + RLENGTH)
            }
            n = split($0, parts, /[^A-Za-z0-9]+/)
            for (i = 1; i <= n; i++) {
                if (is_product_id(parts[i])) { print "ID\t" parts[i]; next }
            }
            print "UNKNOWN\t" $0
        }
    '
}

# "No updates available" is authoritative: when MAU prints it there are zero
# pending updates no matter what spinner fragments trail behind it.
mau_has_no_updates_sentinel() {
    mau_sanitize_output "$1" | grep -qi '^no updates available$'
}

# Genuine pending product IDs only, de-duplicated, one per line.
mau_parse_pending() {
    if mau_has_no_updates_sentinel "$1"; then
        return 0
    fi
    mau_classify_output "$1" | awk -F'\t' '$1 == "ID" && !seen[$2]++ { print $2 }'
}

# Lines that survived the noise filter but carry no product ID — diagnostics
# only, so an unexpected MAU message can be investigated without ever being
# mistaken for a pending update.
mau_parse_unrecognized() {
    mau_classify_output "$1" | awk -F'\t' '$1 == "UNKNOWN" { print $2 }'
}

# Space-separated product IDs that may be passed to msupdate --install --apps.
# TEAMS21 is excluded on purpose: Microsoft documents that Teams updates cannot
# be managed through msupdate, so a TEAMS21 offer is informational only and
# Teams keeps its own updater path (see iu_microsoft_teams).
mau_installable_ids() {
    printf '%s\n' "$1" \
        | grep -v '^TEAMS21$' \
        | grep -v '^[[:space:]]*$' \
        | tr '\n' ' ' \
        | sed 's/[[:space:]]*$//' || true
}

# One scoped msupdate --install pass over a space-separated ID list. Sets
# MAU_INSTALL_CLEAN for the caller and returns msupdate's exit status.
mau_run_scoped_install() {
    local ids="$1" out="" install_exit=0
    print_step "$(internet_msg "$L_INTERNET_MS_INSTALLING_SCOPED_FMT" "$ids")"
    # shellcheck disable=SC2086  # deliberate word splitting: one argv per product ID
    out=$(run_with_timeout "$MAU_INSTALL_TIMEOUT" "$MAU_CLI" \
        --install --wait "$MAU_INSTALL_WAIT" --apps $ids 2>&1) || install_exit=$?
    MAU_INSTALL_CLEAN="$(mau_sanitize_output "$out")"
    [ -n "$MAU_INSTALL_CLEAN" ] && printf '%s\n' "$MAU_INSTALL_CLEAN" | tail -n 20
    internet_diag_log "msupdate --install --apps $ids (exit=$install_exit, sanitized):"
    [ -n "$MAU_INSTALL_CLEAN" ] && internet_diag_log "$MAU_INSTALL_CLEAN"
    return "$install_exit"
}

# Strictly numeric count of non-blank lines, so the caller's -gt comparison
# can never see whitespace or a multiline value.
mau_count_lines() {
    local value="$1" count=""
    if [ -z "$value" ]; then
        echo 0
        return 0
    fi
    count="$(printf '%s\n' "$value" | grep -c '[^[:space:]]' 2>/dev/null || true)"
    count="$(printf '%s' "$count" | tr -cd '0-9')"
    [ -n "$count" ] || count=0
    echo "$count"
}

# Positive-integer timeout or the documented default (same contract as
# MAC_UPDATE_MAS_CHECK_TIMEOUT / MAC_UPDATE_MAS_UPGRADE_TIMEOUT).
mau_timeout_value() {
    local raw="$1" fallback="$2"
    case "$raw" in
        ''|*[!0-9]*) echo "$fallback"; return 0 ;;
    esac
    if [ "$raw" -gt 0 ]; then
        echo "$raw"
    else
        echo "$fallback"
    fi
}

# ── MAU deferral preferences ──────────────────────────────────
# Every read and every mutation happens on an exported copy, so a partial
# failure can never corrupt the live com.microsoft.autoupdate2 domain.
mau_prefs_export() {
    defaults export com.microsoft.autoupdate2 "$1" >/dev/null 2>&1
}

mau_plist_keys() {
    plutil -extract "$2" xml1 -o - "$1" 2>/dev/null \
        | sed -n 's|.*<key>\(.*\)</key>.*|\1|p'
}

mau_deferral_value() {
    plutil -extract "OptionalUpdatesDeferrals.$2.$3" raw -o - "$1" 2>/dev/null
}

# "ID=value" for every entry of one deferral container.
mau_deferral_entries() {
    local plist="$1" container="$2" id value
    for id in $(mau_plist_keys "$plist" "OptionalUpdatesDeferrals.$container"); do
        value="$(mau_deferral_value "$plist" "$container" "$id")"
        printf '%s=%s\n' "$id" "$value"
    done
}

# "Container.ID=value" for the whole OptionalUpdatesDeferrals subtree.
mau_deferral_state() {
    local plist="$1" container entry
    for container in DeferralDays DeferralVersions; do
        mau_deferral_entries "$plist" "$container" | while IFS= read -r entry; do
            [ -n "$entry" ] && printf '%s.%s\n' "$container" "$entry"
        done
    done
}

# Permanent health check, not a one-off cleanup. Microsoft documents
# DeferralDays as an integer in 1-28 and DeferralVersions as Major.Minor only;
# anything else has undefined behaviour and silently blocks updates.
mau_deferral_health_warnings() {
    local plist="$1" entry id value
    mau_deferral_entries "$plist" DeferralDays | while IFS= read -r entry; do
        [ -n "$entry" ] || continue
        id="${entry%%=*}"
        value="${entry#*=}"
        case "$value" in
            ''|*[!0-9]*)
                echo "DeferralDays.$id=$value is not an integer"
                continue
                ;;
        esac
        if [ "$value" -lt 1 ] || [ "$value" -gt 28 ]; then
            echo "DeferralDays.$id=$value is outside Microsoft's documented 1-28 range"
        fi
    done
    mau_deferral_entries "$plist" DeferralVersions | while IFS= read -r entry; do
        [ -n "$entry" ] || continue
        id="${entry%%=*}"
        value="${entry#*=}"
        if ! printf '%s' "$value" | grep -q '^[0-9][0-9]*\.[0-9][0-9]*$'; then
            echo "DeferralVersions.$id=$value is not the documented Major.Minor form"
        fi
    done
}

# Remove only the targeted stale entries from an exported copy and echo what
# was removed. Every untargeted key is preserved; containers emptied by the
# removals are dropped instead of being left behind as {}.
# $2 is the explicit DeferralDays ID list to release — the caller decides which
# products have earned their release, because a deferral is only stale once the
# feed stops offering a downgrade for that product.
mau_clean_stale_deferrals() {
    local plist="$1" day_ids="$2" id container removed=""
    for id in $day_ids; do
        if [ -n "$(mau_deferral_value "$plist" DeferralDays "$id")" ] \
            && plutil -remove "OptionalUpdatesDeferrals.DeferralDays.$id" "$plist" >/dev/null 2>&1; then
            removed="$removed DeferralDays.$id"
        fi
    done
    for id in $MAU_STALE_DEFERRAL_VERSION_IDS; do
        if [ -n "$(mau_deferral_value "$plist" DeferralVersions "$id")" ] \
            && plutil -remove "OptionalUpdatesDeferrals.DeferralVersions.$id" "$plist" >/dev/null 2>&1; then
            removed="$removed DeferralVersions.$id"
        fi
    done
    for container in DeferralDays DeferralVersions; do
        if [ -z "$(mau_plist_keys "$plist" "OptionalUpdatesDeferrals.$container")" ]; then
            plutil -remove "OptionalUpdatesDeferrals.$container" "$plist" >/dev/null 2>&1 || true
        fi
    done
    if [ -z "$(mau_plist_keys "$plist" OptionalUpdatesDeferrals)" ]; then
        plutil -remove OptionalUpdatesDeferrals "$plist" >/dev/null 2>&1 || true
    fi
    printf '%s\n' "${removed# }"
}

# Create the OptionalUpdatesDeferrals.DeferralDays container when it is absent.
# plutil -extract with xml1 succeeds for dictionaries, unlike raw, so it is the
# existence probe here as well as in mau_plist_keys.
mau_plist_ensure_deferral_days() {
    local plist="$1"
    plutil -extract OptionalUpdatesDeferrals xml1 -o - "$plist" >/dev/null 2>&1 \
        || plutil -insert OptionalUpdatesDeferrals -json '{}' "$plist" >/dev/null 2>&1 \
        || return 1
    plutil -extract OptionalUpdatesDeferrals.DeferralDays xml1 -o - "$plist" >/dev/null 2>&1 \
        || plutil -insert OptionalUpdatesDeferrals.DeferralDays -json '{}' "$plist" >/dev/null 2>&1 \
        || return 1
    return 0
}

# Arm (or refresh) the documented per-app quarantine on an exported copy and
# echo the IDs it set. Microsoft documents DeferralDays as an integer of 1-28
# and states that critical updates bypass deferrals, so this never withholds a
# security release — it only stops MAU's daemon from re-downloading a package
# that provably cannot install.
mau_arm_deferrals() {
    local plist="$1" ids="$2" days="$3" id key armed=""
    for id in $ids; do
        [ -n "$id" ] || continue
        [ "$(mau_deferral_value "$plist" DeferralDays "$id")" = "$days" ] && continue
        mau_plist_ensure_deferral_days "$plist" || continue
        key="OptionalUpdatesDeferrals.DeferralDays.$id"
        if plutil -extract "$key" raw -o - "$plist" >/dev/null 2>&1; then
            plutil -replace "$key" -integer "$days" "$plist" >/dev/null 2>&1 \
                && armed="$armed $id"
        else
            plutil -insert "$key" -integer "$days" "$plist" >/dev/null 2>&1 \
                && armed="$armed $id"
        fi
    done
    printf '%s\n' "${armed# }"
}

# ── Office package-regression guard ───────────────────────────
# Microsoft product ID → the installed bundle that product updates.
# Bash 3.2 has no associative arrays, so this stays a case lookup.
mau_app_path_for_id() {
    case "$1" in
        MSWD2019) echo "/Applications/Microsoft Word.app" ;;
        XCEL2019) echo "/Applications/Microsoft Excel.app" ;;
        PPT32019) echo "/Applications/Microsoft PowerPoint.app" ;;
        OPIM2019) echo "/Applications/Microsoft Outlook.app" ;;
        ONMC2019) echo "/Applications/Microsoft OneNote.app" ;;
    esac
}

# Short version the feed offers for one product ID, e.g. "16.111.1" out of
# "MSWD2019  Microsoft Word Update 16.111.1 (26071913)". The parenthesised
# trailing token is the build number on a different numbering scale, so only
# dotted numeric tokens qualify and the scan runs right to left.
mau_offered_version() {
    mau_sanitize_output "$1" | awk -v id="$2" '
        index($0, id) == 0 { next }
        {
            for (i = NF; i >= 1; i--) {
                tok = $i
                gsub(/[()]/, "", tok)
                if (tok ~ /^[0-9]+(\.[0-9]+)+$/) { print tok; exit }
            }
        }'
}

# Installed short version read the way PackageKit reads it. app_version()
# deliberately falls back to CFBundleVersion and mdls, which for Office are a
# different numbering scale (16.111.26071215 vs 16.111.5), so mixing them here
# would invert the comparison.
mau_installed_short_version() {
    defaults read "$1/Contents/Info" CFBundleShortVersionString 2>/dev/null
}

# "ID offered installed" for every pending product whose offered package
# declares a short version that is NOT newer than the installed app.
# PackageKit refuses such a component ("Skipping component ... because the
# version ... is already installed") and the delta package then fails its
# postinstall with PKInstallErrorDomain Code=112. Those installs cannot
# succeed, so they are quarantined rather than re-downloaded every run.
# See docs/agents/critical_rules.md section 9.
mau_regressed_entries() {
    local list="$1" ids="$2" id app offered installed
    for id in $ids; do
        [ -n "$id" ] || continue
        app="$(mau_app_path_for_id "$id")"
        [ -n "$app" ] && [ -d "$app" ] || continue
        offered="$(mau_offered_version "$list" "$id")"
        [ -n "$offered" ] || continue
        installed="$(mau_installed_short_version "$app")"
        [ -n "$installed" ] || continue
        # Strictly older only. Arguments are reversed on purpose:
        # internet_version_relation folds "equal" into "current", and an equal
        # short version with a newer build is a legitimate build-only update
        # that PackageKit accepts. Quarantining that would block real updates.
        if [ "$(internet_version_relation "$installed" "$offered")" = "newer" ]; then
            printf '%s %s %s\n' "$id" "$offered" "$installed"
        fi
    done
}

# Drop the given space-separated IDs from a newline-separated ID list on stdin.
mau_filter_out_ids() {
    awk -v drop=" $1 " 'NF && index(drop, " " $0 " ") == 0'
}

# Office product IDs that currently carry a DeferralDays quarantine. Used to
# explain an empty update list honestly instead of reporting "up to date".
mau_active_office_deferrals() {
    local plist ids="" id
    plist="$(mktemp "${TMPDIR:-/tmp}/mau-prefs.XXXXXX")" || return 0
    if mau_prefs_export "$plist"; then
        for id in $MAU_OFFICE_DEFERRAL_IDS; do
            [ -n "$(mau_deferral_value "$plist" DeferralDays "$id")" ] && ids="$ids $id"
        done
    fi
    rm -f "$plist" 2>/dev/null || true
    printf '%s\n' "${ids# }"
}

# Preflight run before msupdate --list: report the deferral state, warn about
# malformed entries, and clear stale DeferralVersions pins, which cap the
# maximum version MAU will ever offer and therefore block a product forever.
#
# It deliberately does NOT touch the Office DeferralDays quarantine. Whether a
# deferral is stale or still protective depends on what the feed is currently
# offering, which is only known after msupdate --list, so that decision belongs
# to mau_reconcile_deferrals. Clearing it here unconditionally is what made
# every run re-download a package that provably could not install.
mau_deferral_preflight() {
    local plist before warnings
    plist="$(mktemp "${TMPDIR:-/tmp}/mau-prefs.XXXXXX")" || return 1
    # defaults import replaces the whole domain, so stop MAU first — otherwise
    # its daemon can race the rewrite and win.
    killall "Microsoft AutoUpdate" "Microsoft Update Assistant" 2>/dev/null || true
    if ! mau_prefs_export "$plist"; then
        rm -f "$plist" 2>/dev/null || true
        internet_diag_log "WARN: could not export com.microsoft.autoupdate2 preferences"
        return 1
    fi

    before="$(mau_deferral_state "$plist")"
    if [ -z "$before" ]; then
        internet_diag_log "MAU: no OptionalUpdatesDeferrals entries"
        rm -f "$plist" 2>/dev/null || true
        return 0
    fi

    print_warn "$(internet_msg "$L_INTERNET_MS_DEFERRALS_FOUND_FMT" "$(printf '%s\n' "$before" | tr '\n' ' ')")"
    internet_diag_log "MAU deferrals before cleanup: $(printf '%s\n' "$before" | tr '\n' ' ')"
    warnings="$(mau_deferral_health_warnings "$plist")"
    if [ -n "$warnings" ]; then
        printf '%s\n' "$warnings" | while IFS= read -r line; do
            [ -n "$line" ] && print_warn "$line"
        done
        internet_diag_log "MAU deferral health: $(printf '%s\n' "$warnings" | tr '\n' ';')"
    fi

    # Read-only by design. Every deferral mutation happens exactly once per run,
    # in mau_reconcile_deferrals after msupdate --list. Two export/import cycles
    # in a single run raced each other: `killall cfprefsd` invalidates the
    # preference daemon's cache, so the next `defaults export` could return
    # pre-mutation (or empty) state, and re-importing that resurrected an entry
    # the first pass had just removed while reporting it as gone.
    rm -f "$plist" 2>/dev/null || true
    return 0
}

# Quarantine window in days, clamped to Microsoft's documented 1-28 range.
# 7 rather than the 28 maximum: an active deferral hides the product from
# msupdate --list, so the window is also how long the toolkit stays blind to a
# corrected package. A week keeps MAU's daemon quiet while still re-evaluating
# the feed regularly; 28 would delay a genuine fix by up to a month.
mau_deferral_days_value() {
    local raw="${MAC_UPDATE_MAU_DEFERRAL_DAYS:-7}"
    case "$raw" in
        ''|*[!0-9]*) echo 7; return 0 ;;
    esac
    if [ "$raw" -lt 1 ] || [ "$raw" -gt 28 ]; then
        echo 7
    else
        echo "$raw"
    fi
}

# Reconcile the Office quarantine with what the feed is actually offering:
# arm the documented per-app deferral for every product stuck in a downgrade
# loop, and release it for every product whose offer has since been corrected.
# Runs after msupdate --list, because only the offer tells the two apart.
mau_reconcile_deferrals() {
    local regressed="$1" plist backup release id armed removed days verify unverified=""
    release=""
    for id in $MAU_OFFICE_DEFERRAL_IDS; do
        case " $regressed " in
            *" $id "*) ;;
            *) release="$release $id" ;;
        esac
    done
    release="${release# }"

    if [ "${MAC_UPDATE_MAU_KEEP_DEFERRALS:-0}" = "1" ]; then
        print_info "$L_INTERNET_MS_DEFERRALS_KEPT"
        return 0
    fi
    if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
        [ -n "$regressed" ] && print_info "$(internet_msg "$L_INTERNET_MS_DEFERRALS_DRYRUN_FMT" "$regressed")"
        return 0
    fi

    plist="$(mktemp "${TMPDIR:-/tmp}/mau-prefs.XXXXXX")" || return 1
    # defaults import replaces the whole domain, so stop MAU first — otherwise
    # its daemon can race the rewrite and win.
    killall "Microsoft AutoUpdate" "Microsoft Update Assistant" 2>/dev/null || true
    if ! mau_prefs_export "$plist"; then
        rm -f "$plist" 2>/dev/null || true
        internet_diag_log "WARN: could not export com.microsoft.autoupdate2 for reconcile"
        return 1
    fi

    # Back up the untouched export before mutating anything.
    if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ]; then
        backup="$MAC_UPDATE_SESSION_DIR/mau_prefs_reconcile_backup.plist"
    else
        backup="$(mktemp "${TMPDIR:-/tmp}/mau-prefs-backup.XXXXXX")" || backup=""
    fi
    if [ -z "$backup" ] || ! cp "$plist" "$backup" 2>/dev/null; then
        print_warn "Could not back up Microsoft AutoUpdate preferences — leaving deferrals untouched"
        internet_diag_log "ERROR: MAU preference backup failed; skipped deferral reconcile"
        rm -f "$plist" 2>/dev/null || true
        return 1
    fi

    days="$(mau_deferral_days_value)"
    armed="$(mau_arm_deferrals "$plist" "$regressed" "$days")"
    removed="$(mau_clean_stale_deferrals "$plist" "$release")"
    if [ -z "$armed" ] && [ -z "$removed" ]; then
        rm -f "$plist" 2>/dev/null || true
        internet_diag_log "MAU deferrals already reconciled (armed: none, released: none)"
        return 0
    fi

    # Validate the mutated copy before it is allowed to replace live prefs.
    if ! plutil -lint "$plist" >/dev/null 2>&1; then
        print_warn "Rewritten Microsoft AutoUpdate preferences failed plutil -lint — not imported"
        internet_diag_log "ERROR: MAU reconcile rewrite failed lint; backup at $backup"
        rm -f "$plist" 2>/dev/null || true
        return 1
    fi
    if ! defaults import com.microsoft.autoupdate2 "$plist" >/dev/null 2>&1; then
        print_warn "Could not import reconciled Microsoft AutoUpdate preferences"
        print_info "Restore with: defaults import com.microsoft.autoupdate2 $backup"
        internet_diag_log "ERROR: defaults import failed during reconcile; backup at $backup"
        rm -f "$plist" 2>/dev/null || true
        return 1
    fi
    rm -f "$plist" 2>/dev/null || true
    # Deliberately no `killall cfprefsd` here. defaults import hands the write
    # to the preference daemon, which flushes it lazily; killing the daemon
    # straight afterwards discards the write. That silently reverted every
    # reconcile while still reporting success. Only MAU is restarted, so it
    # re-reads the domain on its next launch.
    killall "Microsoft AutoUpdate" "Microsoft Update Assistant" 2>/dev/null || true

    # Never claim a change that did not land: re-read the live domain and
    # report what it actually contains.
    verify="$(mktemp "${TMPDIR:-/tmp}/mau-prefs.XXXXXX")" || return 0
    if mau_prefs_export "$verify"; then
        for id in $armed; do
            if [ "$(mau_deferral_value "$verify" DeferralDays "$id")" != "$days" ]; then
                unverified="$unverified $id"
            fi
        done
        if [ -n "$unverified" ]; then
            print_warn "$(internet_msg "$L_INTERNET_MS_DEFERRALS_UNVERIFIED_FMT" "${unverified# }")"
            internet_diag_log "ERROR: MAU deferral write did not persist for:${unverified}"
            rm -f "$verify" 2>/dev/null || true
            return 1
        fi
    fi
    rm -f "$verify" 2>/dev/null || true

    [ -n "$armed" ] && print_info "$(internet_msg "$L_INTERNET_MS_DEFERRALS_ARMED_FMT" "$armed" "$days")"
    [ -n "$removed" ] && print_ok "$(internet_msg "$L_INTERNET_MS_DEFERRALS_CLEARED_FMT" "$removed")"
    internet_diag_log "MAU deferrals reconciled (armed: ${armed:-none}, released: ${removed:-none}, days=$days)"
    return 0
}

iu_microsoft_365() {
    print_header "💼 Microsoft 365 (via Microsoft AutoUpdate)"

    MAU_CLI="/Library/Application Support/Microsoft/MAU2.0/Microsoft AutoUpdate.app/Contents/MacOS/msupdate"
    MAU_APP="/Library/Application Support/Microsoft/MAU2.0/Microsoft AutoUpdate.app"
    MAU_TEAMS21_OFFERED=0
    MAU_CHECK_TIMEOUT="$(mau_timeout_value "${MAC_UPDATE_MSUPDATE_CHECK_TIMEOUT:-120}" 120)"
    # msupdate's own --wait returns the current install state instead of
    # hanging, so it is the primary bound. run_with_timeout stays strictly
    # above it as a hard backstop — a killed msupdate (124) tells us nothing,
    # a --wait return is readable. Office full installers are multi-GB, hence
    # the 1800s default rather than the old 300s.
    MAU_INSTALL_WAIT="$(mau_timeout_value "${MAC_UPDATE_MSUPDATE_INSTALL_TIMEOUT:-1800}" 1800)"
    MAU_INSTALL_TIMEOUT=$((MAU_INSTALL_WAIT + 60))

    # Sprawdź czy zainstalowana jest jakakolwiek aplikacja Microsoft
    MS_INSTALLED=0
    for ms_app in "Microsoft Word" "Microsoft Excel" "Microsoft PowerPoint" \
                   "Microsoft Outlook" "Microsoft OneNote"; do
        if [ -d "/Applications/${ms_app}.app" ]; then
            VER=$(app_version "/Applications/${ms_app}.app")
            print_info "${ms_app}: $VER"
            MS_INSTALLED=1
        fi
    done

    if [ "$MS_INSTALLED" = "1" ]; then
        if [ -f "$MAU_CLI" ]; then
            # Report the deferral state and clear version pins. The DeferralDays
            # quarantine is reconciled after the list, once the offer is known.
            mau_deferral_preflight || true
            # Krok 1: sprawdź dostępne aktualizacje z limitem czasu MAU_CHECK_TIMEOUT
            print_step "$L_INTERNET_MS_CHECKING"
            MAU_LIST_EXIT=0
            MAU_LIST=$(run_with_timeout "$MAU_CHECK_TIMEOUT" "$MAU_CLI" --list 2>&1) || MAU_LIST_EXIT=$?

            if [ "$MAU_LIST_EXIT" -ne 0 ]; then
                print_warn "$(internet_msg "$L_INTERNET_MS_CHECK_FAILED_FMT" "$MAU_LIST_EXIT")"
                MAU_LIST_CLEAN="$(mau_sanitize_output "$MAU_LIST")"
                [ -n "$MAU_LIST_CLEAN" ] && printf '%s\n' "$MAU_LIST_CLEAN" | tail -n 20
                internet_diag_log "ERROR: msupdate --list failed (exit=$MAU_LIST_EXIT)"
                STATUS_MICROSOFT="$L_INTERNET_STATUS_CHECK_MAU"
            else
                # Only positively identified product IDs count as pending. The
                # old "every non-blank line" filter counted spinner fragments.
                MAU_PENDING="$(mau_parse_pending "$MAU_LIST")"
                MAU_UNRECOGNIZED="$(mau_parse_unrecognized "$MAU_LIST")"
                [ -n "$MAU_UNRECOGNIZED" ] && internet_diag_log \
                    "msupdate --list unrecognized lines: $(printf '%s\n' "$MAU_UNRECOGNIZED" | tr '\n' ';')"
                if printf '%s\n' "$MAU_PENDING" | grep -q '^TEAMS21$'; then
                    MAU_TEAMS21_OFFERED=1
                fi
                MAU_COUNT="$(mau_count_lines "$MAU_PENDING")"

                if [ "$MAU_COUNT" -gt 0 ]; then
                    print_info "$(internet_msg "$L_INTERNET_MS_UPDATES_AVAILABLE" "$MAU_COUNT")"
                    printf '%s\n' "$MAU_PENDING" | while IFS= read -r line; do
                        [ -n "$line" ] && print_info "  → $line"
                    done

                    # A package whose short version is not newer than the
                    # installed app can never install: PackageKit skips the
                    # component and the delta postinstall fails with 112.
                    # Quarantine those instead of downloading them again.
                    MAU_PENDING_IDS="$(printf '%s\n' "$MAU_PENDING" | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
                    MAU_REGRESSED="$(mau_regressed_entries "$MAU_LIST" "$MAU_PENDING_IDS")"
                    MAU_REGRESSED_IDS="$(printf '%s\n' "$MAU_REGRESSED" \
                        | awk 'NF { print $1 }' | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
                    if [ -n "$MAU_REGRESSED_IDS" ]; then
                        printf '%s\n' "$MAU_REGRESSED" | while read -r r_id r_offered r_installed; do
                            [ -n "$r_id" ] && print_warn "$(internet_msg \
                                "$L_INTERNET_MS_REGRESSION_FMT" "$r_id" "$r_offered" "$r_installed")"
                        done
                        print_info "$L_INTERNET_MS_REGRESSION_NOTE"
                        internet_diag_log "MAU upstream package regression (offered <= installed): $(printf '%s\n' "$MAU_REGRESSED" | tr '\n' ';')"
                    fi
                    mau_reconcile_deferrals "$MAU_REGRESSED_IDS" || true

                    # TEAMS21 is dropped by mau_installable_ids: Microsoft
                    # documents Teams as unmanageable through msupdate.
                    MAU_INSTALL_IDS="$(printf '%s\n' "$MAU_PENDING" \
                        | mau_filter_out_ids "$MAU_REGRESSED_IDS")"
                    MAU_INSTALL_IDS="$(mau_installable_ids "$MAU_INSTALL_IDS")"

                    if [ -z "$MAU_INSTALL_IDS" ]; then
                        # Everything pending is quarantined or Teams-owned:
                        # there is nothing msupdate can usefully install.
                        if [ -n "$MAU_REGRESSED_IDS" ]; then
                            STATUS_MICROSOFT="$L_INTERNET_STATUS_MAU_QUARANTINED"
                        else
                            print_ok "$L_INTERNET_MS_CURRENT"
                            STATUS_MICROSOFT="$L_INTERNET_STATUS_CURRENT"
                        fi
                    else
                        MAU_INSTALL_EXIT=0
                        mau_run_scoped_install "$MAU_INSTALL_IDS" || MAU_INSTALL_EXIT=$?
                        if [ "$MAU_INSTALL_EXIT" -eq 0 ]; then
                            MAU_VERIFY_EXIT=0
                            MAU_VERIFY=$(run_with_timeout "$MAU_CHECK_TIMEOUT" "$MAU_CLI" --list 2>&1) || MAU_VERIFY_EXIT=$?
                            # Quarantined products are still offered by the
                            # feed, so they are expected to remain listed.
                            MAU_REMAINING="$(mau_parse_pending "$MAU_VERIFY" \
                                | mau_filter_out_ids "$MAU_REGRESSED_IDS")"
                            if [ "$MAU_VERIFY_EXIT" -ne 0 ]; then
                                print_warn "$(internet_msg "$L_INTERNET_MS_CHECK_FAILED_FMT" "$MAU_VERIFY_EXIT")"
                                internet_diag_log "ERROR: msupdate --list re-verification failed (exit=$MAU_VERIFY_EXIT)"
                                STATUS_MICROSOFT="$L_INTERNET_STATUS_CHECK_MAU"
                            elif [ -n "$MAU_REMAINING" ]; then
                                print_warn "$L_INTERNET_MS_STILL_PENDING"
                                printf '%s\n' "$MAU_REMAINING" | while IFS= read -r line; do
                                    [ -n "$line" ] && print_info "  → $line"
                                done
                                internet_diag_log "WARN: Microsoft updates still pending after install: $(printf '%s\n' "$MAU_REMAINING" | tr '\n' ' ')"
                                STATUS_MICROSOFT="$L_INTERNET_STATUS_CHECK_MAU"
                            elif [ -n "$MAU_REGRESSED_IDS" ]; then
                                # Installable set succeeded, quarantine stands.
                                STATUS_MICROSOFT="$L_INTERNET_STATUS_MAU_QUARANTINED"
                            else
                                print_ok "$L_INTERNET_MS_UPDATED"
                                STATUS_MICROSOFT="$(internet_msg "$L_INTERNET_STATUS_UPDATED_FMT" "Microsoft apps")"
                                if [ "$MAU_TEAMS21_OFFERED" -eq 1 ]; then
                                    MAU_TEAMS21_VERIFIED=1
                                fi
                            fi
                        else
                            if [ "$MAU_INSTALL_EXIT" = "124" ] || [ "$MAU_INSTALL_EXIT" = "137" ] || [ "$MAU_INSTALL_EXIT" = "143" ]; then
                                print_warn "$L_INTERNET_MS_TIMEOUT"
                            else
                                print_warn "$(internet_msg "$L_INTERNET_MS_INSTALL_ERROR" "$MAU_INSTALL_EXIT")"
                            fi
                            if [ -d "$MAU_APP" ]; then
                                if open -a "$MAU_APP" 2>/dev/null; then
                                    print_info "$L_INTERNET_MS_ACCEPT_IN_WINDOW"
                                else
                                    print_warn "Could not launch Microsoft AutoUpdate after the CLI failure."
                                fi
                            fi
                            STATUS_MICROSOFT="$L_INTERNET_STATUS_CHECK_MAU"
                        fi
                    fi
                else
                    # Nothing offered. A live quarantine could be the reason, so
                    # say so instead of claiming everything is up to date.
                    # An active DeferralDays entry suppresses the product from
                    # msupdate --list entirely, so an empty list is NOT evidence
                    # that the feed was corrected. Releasing here would arm and
                    # release on alternating runs forever. The quarantine is
                    # only ever released on positive evidence: an offer whose
                    # short version is newer than what is installed. Until then
                    # it lapses on its own after MAC_UPDATE_MAU_DEFERRAL_DAYS,
                    # which is what makes the next re-evaluation possible.
                    MAU_HELD="$(mau_active_office_deferrals)"
                    if [ -n "$MAU_HELD" ]; then
                        print_warn "$(internet_msg "$L_INTERNET_MS_DEFERRALS_HOLDING_FMT" "$MAU_HELD")"
                        STATUS_MICROSOFT="$L_INTERNET_STATUS_MAU_QUARANTINED"
                    else
                        print_ok "$L_INTERNET_MS_CURRENT"
                        STATUS_MICROSOFT="$L_INTERNET_STATUS_CURRENT"
                    fi
                fi
            fi
        elif [ -d "$MAU_APP" ]; then
            print_step "$L_INTERNET_MS_OPENING_GUI"
            if open -a "$MAU_APP" 2>/dev/null; then
                print_info "$L_INTERNET_MS_ACCEPT_GUI"
                STATUS_MICROSOFT="$L_INTERNET_STATUS_MAU_OPENED"
            else
                print_warn "Could not launch Microsoft AutoUpdate"
                STATUS_MICROSOFT="$L_INTERNET_STATUS_CHECK_MAU"
            fi
        else
            print_warn "Microsoft AutoUpdate is not installed"
            print_info "$(internet_msg "$L_INTERNET_DOWNLOAD_FROM" "https://learn.microsoft.com/en-us/microsoft-365-apps/mac/update-office-for-mac-using-msupdate")"
            STATUS_MICROSOFT="$L_INTERNET_STATUS_MAU_MISSING"
        fi
    else
        print_info "$L_INTERNET_MS_NONE_INSTALLED"
    fi

    # ============================================================
    # ██ SEKCJA 7: NARZĘDZIA DEWELOPERSKIE
    # ============================================================

    # ── 18b. MICROSOFT TEAMS ─────────────────────────────────────
    # Teams owns its normal update cadence. Microsoft documents TEAMS21 as an
    # MAU fallback that may be offered when the Teams updater fails; the shared
    # MAU handler above can therefore verify a fallback update in this run.
}

iu_microsoft_teams() {
    print_header "💬 Microsoft Teams"
    if [ -d "/Applications/Microsoft Teams.app" ]; then
        VER=$(app_version "/Applications/Microsoft Teams.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        if [ "$MAU_TEAMS21_VERIFIED" -eq 1 ]; then
            print_ok "Microsoft Teams fallback update verified by MAU (TEAMS21): $VER"
            STATUS_TEAMS="✅ MAU fallback verified ($VER)"
        else
            print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "Microsoft Teams")"
            if silent_launch_app "/Applications/Microsoft Teams.app"; then
                print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "Microsoft Teams → Check for updates")"
                STATUS_TEAMS="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
            else
                STATUS_TEAMS="$L_INTERNET_STATUS_LAUNCH_FAILED"
            fi
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Microsoft Teams")"
    fi

    # ── 19. VISUAL STUDIO CODE ────────────────────────────────────
}

iu_visual_studio_code() {
    print_header "💻 Visual Studio Code"
    if [ -d "/Applications/Visual Studio Code.app" ]; then
        VER=$(app_version "/Applications/Visual Studio Code.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"

        LATEST_VSCODE=$(github_latest_tag "microsoft/vscode" | sed 's/^v//')
        VSCODE_RELATION="$(internet_version_relation "$LATEST_VSCODE" "$VER")"

        if [ "$LATEST_VSCODE" = "?" ]; then
            # Offline or GitHub unreachable — launch app for built-in updater
            print_warn "$L_INTERNET_STATUS_OFFLINE"
            print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "Visual Studio Code")"
            if silent_launch_app "Visual Studio Code"; then
                print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "VS Code → Help → Check for Updates")"
                STATUS_VSCODE="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
            else
                STATUS_VSCODE="$L_INTERNET_STATUS_LAUNCH_FAILED"
            fi
        elif [ "$VSCODE_RELATION" = "unknown" ]; then
            print_warn "$(internet_msg "$L_INTERNET_UNKNOWN_DETECTED" "Visual Studio Code version")"
            STATUS_VSCODE="$L_INTERNET_STATUS_UNKNOWN_VERSION"
        elif [ "$VSCODE_RELATION" = "current" ]; then
            print_ok "$(internet_msg "$L_INTERNET_APP_CURRENT" "VS Code" "$VER (remote: $LATEST_VSCODE)")"
            STATUS_VSCODE="$L_INTERNET_STATUS_CURRENT"
        else
            print_warn "$(internet_msg "$L_INTERNET_NEW_VERSION_AVAILABLE" "$LATEST_VSCODE" "$VER")"
            print_step "$(internet_msg "$L_INTERNET_DOWNLOADING" "Visual Studio Code" "$LATEST_VSCODE")"
            VSCODE_URL="https://update.code.visualstudio.com/latest/darwin-arm64/stable"
            TEMP_ZIP="$(mktemp "$INTERNET_TEMP_ROOT/vscode.XXXXXX.zip")"
            TEMP_DIR="$INTERNET_TEMP_ROOT/vscode_extracted"
            rm -rf "$TEMP_DIR" 2>/dev/null || true
            mkdir -p "$TEMP_DIR"

            if curl -L --max-time 300 --retry 3 --retry-delay 2 -o "$TEMP_ZIP" "$VSCODE_URL" 2>/dev/null; then
                print_step "$(internet_msg "$L_INTERNET_EXTRACTING" "Visual Studio Code")"
                if unzip -q "$TEMP_ZIP" -d "$TEMP_DIR" 2>/dev/null; then
                    if [ -d "$TEMP_DIR/Visual Studio Code.app" ]; then
                        VSCODE_SOURCE_VER=$(app_version "$TEMP_DIR/Visual Studio Code.app")
                        if [ "$(internet_version_relation "$VSCODE_SOURCE_VER" "$VER")" != "newer" ]; then
                            print_warn "Refusing non-newer VS Code payload: $VSCODE_SOURCE_VER (installed: $VER)"
                            STATUS_VSCODE="$L_INTERNET_STATUS_INSTALL_ERROR"
                        elif copy_verified_app "$TEMP_DIR/Visual Studio Code.app" "Visual Studio Code.app"; then
                            NEW_VER=$(app_version "/Applications/Visual Studio Code.app")
                            print_ok "$(internet_msg "$L_INTERNET_APP_UPDATED" "Visual Studio Code" "$NEW_VER")"
                            STATUS_VSCODE="$(internet_msg "$L_INTERNET_STATUS_UPDATED_FMT" "$NEW_VER")"
                        else
                            print_warn "$(internet_msg "$L_INTERNET_COPY_ERROR" "Visual Studio Code")"
                            STATUS_VSCODE="$L_INTERNET_STATUS_INSTALL_ERROR"
                        fi
                    else
                        print_warn "$(internet_msg "$L_INTERNET_APP_NOT_IN_ARCHIVE" "Visual Studio Code")"
                        STATUS_VSCODE="$L_INTERNET_STATUS_INSTALL_ERROR"
                    fi
                else
                    print_warn "$L_INTERNET_STATUS_EXTRACT_ERROR"
                    STATUS_VSCODE="$L_INTERNET_STATUS_EXTRACT_ERROR"
                fi
            else
                print_warn "$L_INTERNET_STATUS_DOWNLOAD_ERROR"
                STATUS_VSCODE="$L_INTERNET_STATUS_DOWNLOAD_ERROR"
            fi
            rm -f "$TEMP_ZIP" 2>/dev/null || true
            rm -rf "$TEMP_DIR" 2>/dev/null || true
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Visual Studio Code")"
    fi

    # ── 20. CODEEDIT (GitHub API + DMG) ───────────────────────────
}

iu_codeedit() {
    print_header "✏️  CodeEdit"
    if [ -d "/Applications/CodeEdit.app" ]; then
        VER=$(app_version "/Applications/CodeEdit.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"

        LATEST_CE_TAG=$(github_latest_tag "CodeEditApp/CodeEdit")
        LATEST_CE=$(echo "$LATEST_CE_TAG" | sed 's/^v//')
        CE_RELATION="$(internet_version_relation "$LATEST_CE" "$VER")"

        if [ "$LATEST_CE" = "?" ]; then
            print_warn "$(internet_msg "$L_INTERNET_OFFLINE" "GitHub")"
            if silent_launch_app "CodeEdit"; then
                STATUS_CODEEDIT="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
            else
                STATUS_CODEEDIT="$L_INTERNET_STATUS_LAUNCH_FAILED"
            fi
        elif [ "$CE_RELATION" = "unknown" ]; then
            print_warn "$(internet_msg "$L_INTERNET_UNKNOWN_DETECTED" "CodeEdit version")"
            STATUS_CODEEDIT="$L_INTERNET_STATUS_UNKNOWN_VERSION"
        elif [ "$CE_RELATION" = "current" ]; then
            print_ok "$(internet_msg "$L_INTERNET_APP_CURRENT" "CodeEdit" "$VER (remote: $LATEST_CE)")"
            STATUS_CODEEDIT="$L_INTERNET_STATUS_CURRENT"
        else
            print_warn "$(internet_msg "$L_INTERNET_NEW_VERSION_AVAILABLE" "$LATEST_CE" "$VER")"
            print_step "$(internet_msg "$L_INTERNET_DOWNLOADING" "CodeEdit" "$LATEST_CE")"
            CE_URL="https://github.com/CodeEditApp/CodeEdit/releases/download/${LATEST_CE_TAG}/CodeEdit.dmg"
            TEMP_DMG="$(make_temp_dmg CodeEdit)"
            if curl -L --max-time 180 --retry 3 --retry-delay 2 -o "$TEMP_DMG" "$CE_URL" 2>/dev/null; then
                CE_MOUNT="$(mount_verified_dmg "$TEMP_DMG")"
                if [ -n "$CE_MOUNT" ]; then
                    if [ -d "$CE_MOUNT/CodeEdit.app" ]; then
                        CE_SOURCE_VER=$(app_version "$CE_MOUNT/CodeEdit.app")
                        if [ "$(internet_version_relation "$CE_SOURCE_VER" "$VER")" != "newer" ]; then
                            print_warn "Refusing non-newer CodeEdit payload: $CE_SOURCE_VER (installed: $VER)"
                            STATUS_CODEEDIT="$L_INTERNET_STATUS_INSTALL_ERROR"
                        elif copy_verified_app "$CE_MOUNT/CodeEdit.app" "CodeEdit.app"; then
                            NEW_VER=$(app_version "/Applications/CodeEdit.app")
                            print_ok "$(internet_msg "$L_INTERNET_APP_UPDATED" "CodeEdit" "$NEW_VER")"
                            STATUS_CODEEDIT="$(internet_msg "$L_INTERNET_STATUS_UPDATED_FMT" "$NEW_VER")"
                        else
                            print_warn "$(internet_msg "$L_INTERNET_COPY_ERROR" "CodeEdit")"
                            STATUS_CODEEDIT="$L_INTERNET_STATUS_INSTALL_ERROR"
                        fi
                    else
                        print_warn "$(internet_msg "$L_INTERNET_APP_NOT_FOUND_VOLUME" "CodeEdit")"
                        STATUS_CODEEDIT="$L_INTERNET_STATUS_INSTALL_ERROR"
                    fi
                    detach_verified_dmg "$CE_MOUNT" || true
                else
                    print_warn "$L_INTERNET_MOUNT_DMG_FAILED"
                    STATUS_CODEEDIT="$L_INTERNET_STATUS_MOUNT_ERROR"
                fi
                rm -f "$TEMP_DMG"
            else
                print_warn "$L_INTERNET_DOWNLOAD_VERIFY_FAILED"
                print_info "$(internet_msg "$L_INTERNET_DOWNLOAD_MANUALLY" "https://github.com/CodeEditApp/CodeEdit/releases")"
                STATUS_CODEEDIT="$L_INTERNET_STATUS_DOWNLOAD_ERROR"
                rm -f "$TEMP_DMG" 2>/dev/null || true
            fi
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "CodeEdit")"
    fi

    # ── 21. DOCKER DESKTOP ────────────────────────────────────────
}

iu_docker_desktop() {
    print_header "🐳 Docker Desktop"
    if [ -d "/Applications/Docker.app" ]; then
        VER=$(app_version "/Applications/Docker.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"

        # Docker Desktop CLI (available from v4.37+)
        if command -v docker >/dev/null 2>&1 && run_with_timeout 15 docker desktop status >/dev/null 2>&1; then
            print_step "$L_INTERNET_DOCKER_CHECKING"
            # Check if an update is available first (non-destructive)
            if run_with_timeout 60 docker desktop update --check-only --quiet 2>/dev/null; then
                print_info "Update available — applying..."
                if run_with_timeout 600 docker desktop update --quiet 2>/dev/null; then
                    print_ok "$L_INTERNET_DOCKER_CLI_OK"
                    STATUS_DOCKER="$L_INTERNET_STATUS_CHECKED_CLI"
                else
                    print_warn "Docker desktop update command failed"
                    STATUS_DOCKER="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
                fi
            else
                print_ok "$(internet_msg "$L_INTERNET_APP_CURRENT" "Docker Desktop" "$VER")"
                STATUS_DOCKER="$L_INTERNET_STATUS_CURRENT"
            fi
        else
            # No CLI, or the CLI plugin is present but the Docker Desktop app
            # isn't running -- "docker desktop status" fails in that case too,
            # and --check-only's exit code must not be misread as "no update
            # available" when it really means "couldn't check at all".
            print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "Docker Desktop")"
            if open -a Docker 2>/dev/null; then
                print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "Docker icon w menu bar → Software updates")"
                STATUS_DOCKER="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
            else
                STATUS_DOCKER="$L_INTERNET_STATUS_LAUNCH_FAILED"
            fi
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Docker Desktop")"
    fi

    # ── 22. WARP ──────────────────────────────────────────────────
}

iu_warp() {
    print_header "⚡ Warp"
    if [ -d "/Applications/Warp.app" ]; then
        VER=$(app_version "/Applications/Warp.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "Warp")"
        if silent_launch_app "Warp"; then
            print_info "$(internet_msg "$L_INTERNET_WEEKLY_AUTO_UPDATES" "Warp")"
            print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "Warp → Warp → O Warp / Check for Updates")"
            STATUS_WARP="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
        else
            STATUS_WARP="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Warp")"
    fi

    # ── 23. CURSOR ────────────────────────────────────────────────
}

iu_cursor() {
    print_header "⚡ Cursor"
    if [ -d "/Applications/Cursor.app" ]; then
        VER=$(app_version "/Applications/Cursor.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "Cursor")"
        if silent_launch_app "Cursor"; then
            print_info "$(internet_msg "$L_INTERNET_WEEKLY_AUTO_UPDATES" "Cursor")"
            print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "Cursor → Cursor → Check for updates")"
            STATUS_CURSOR="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
        else
            STATUS_CURSOR="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Cursor")"
    fi
}

iu_ascendo() {
    print_header "📊 Ascendo"
    if [ -d "/Applications/Ascendo.app" ]; then
        VER=$(app_version "/Applications/Ascendo.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "Ascendo")"
        if silent_launch_app "Ascendo"; then
            print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "Ascendo → Check for updates")"
            STATUS_ASCENDO="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
        else
            STATUS_ASCENDO="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Ascendo")"
    fi
}

iu_appcleaner() {
    print_header "🧹 AppCleaner"
    if [ -d "/Applications/AppCleaner.app" ]; then
        VER=$(app_version "/Applications/AppCleaner.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "AppCleaner")"
        if silent_launch_app "AppCleaner"; then
            print_info "$(internet_msg "$L_INTERNET_AUTO_UPDATES_SPARKLE" "AppCleaner")"
            STATUS_APPCLEANER="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
        else
            STATUS_APPCLEANER="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "AppCleaner")"
    fi

    # ── 25. OBSIDIAN ──────────────────────────────────────────────
}

iu_obsidian() {
    print_header "📝 Obsidian"
    if [ -d "/Applications/Obsidian.app" ]; then
        VER=$(app_version "/Applications/Obsidian.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "Obsidian")"
        if silent_launch_app "Obsidian"; then
            print_info "$(internet_msg "$L_INTERNET_AUTO_UPDATES" "Obsidian")"
            STATUS_OBSIDIAN="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
        else
            STATUS_OBSIDIAN="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Obsidian")"
    fi

    # ============================================================
    # ██ SEKCJA 9: MULTIMEDIA I GRAFIKA
    # ============================================================

    # ── 27. SPOTIFY ───────────────────────────────────────────────
}

iu_spotify() {
    print_header "🎵 Spotify"
    if [ -d "/Applications/Spotify.app" ]; then
        VER=$(app_version "/Applications/Spotify.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "Spotify")"
        if silent_launch_app "Spotify"; then
            print_info "$L_INTERNET_SPOTIFY_PROFILE_DOT"
            print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "Spotify → Spotify → O Spotify")"
            STATUS_SPOTIFY="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
        else
            STATUS_SPOTIFY="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Spotify")"
    fi

    # ============================================================
    # ██ SEKCJA 10: KRYPTO I FINANSE
    # ============================================================

    # ── 30. LEDGER LIVE / LEDGER WALLET ───────────────────────────
}

iu_capcut() {
    print_header "🎬 CapCut"
    if [ -d "/Applications/CapCut.app" ]; then
        VER=$(app_version "/Applications/CapCut.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "CapCut")"
        if silent_launch_app "CapCut"; then
            print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "CapCut → CapCut → Check for Updates")"
            STATUS_CAPCUT="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
        else
            STATUS_CAPCUT="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "CapCut")"
    fi
}

iu_ledger() {
    print_header "🔐 Ledger Wallet / Ledger Live"
    LEDGER_APP=""
    LEDGER_NAME=""
    for lapp in "Ledger Wallet" "Ledger Live"; do
        if [ -d "/Applications/${lapp}.app" ]; then
            LEDGER_APP="/Applications/${lapp}.app"
            LEDGER_NAME="$lapp"
            break
        fi
    done

    if [ -n "$LEDGER_APP" ]; then
        VER=$(app_version "$LEDGER_APP")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_APP" "$LEDGER_NAME" "$VER")"

        LEDGER_YML=$(curl -s --max-time 20 --retry 3 --retry-delay 2 "https://download.live.ledger.com/latest-mac.yml" 2>/dev/null)
        LATEST_LEDGER=$(echo "$LEDGER_YML" | grep "^version:" | cut -d' ' -f2 | tr -d '[:space:]')
        LEDGER_RELATION="$(internet_version_relation "$LATEST_LEDGER" "$VER")"

        if [ -z "$LATEST_LEDGER" ]; then
            print_warn "$(internet_msg "$L_INTERNET_OFFLINE" "GitHub")"
            STATUS_LEDGER="$L_INTERNET_STATUS_OFFLINE"
        elif [ "$LEDGER_RELATION" = "unknown" ]; then
            print_warn "$(internet_msg "$L_INTERNET_UNKNOWN_DETECTED" "Ledger version")"
            STATUS_LEDGER="$L_INTERNET_STATUS_UNKNOWN_VERSION"
        elif [ "$LEDGER_RELATION" = "current" ]; then
            print_ok "$(internet_msg "$L_INTERNET_APP_CURRENT" "$LEDGER_NAME" "$VER (remote: $LATEST_LEDGER)")"
            STATUS_LEDGER="$L_INTERNET_STATUS_CURRENT"
        else
            print_warn "$(internet_msg "$L_INTERNET_NEW_VERSION_AVAILABLE" "$LATEST_LEDGER" "$VER")"
            print_step "$(internet_msg "$L_INTERNET_DOWNLOADING" "$LEDGER_NAME" "$LATEST_LEDGER")"
            # Parse the actual DMG filename from the YAML 'files' list (skip ZIP, extract DMG only)
            LEDGER_DMG_FILE=$(echo "$LEDGER_YML" | grep "^  *- url:.*\.dmg" | head -1 | sed 's|.*url: *||' | tr -d '[:space:]')
            if [ -z "$LEDGER_DMG_FILE" ]; then
                LEDGER_DMG_FILE="ledger-live-desktop-${LATEST_LEDGER}-mac.dmg"
            fi
            LEDGER_URL="https://download.live.ledger.com/${LEDGER_DMG_FILE}"
            TEMP_DMG="$(make_temp_dmg LedgerWallet)"
            if curl -L --max-time 300 --retry 3 --retry-delay 2 -o "$TEMP_DMG" "$LEDGER_URL" 2>/dev/null; then
                LEDGER_MOUNT="$(mount_verified_dmg "$TEMP_DMG")"
                if [ -n "$LEDGER_MOUNT" ]; then
                    if [ -d "$LEDGER_MOUNT/Ledger Live.app" ] || [ -d "$LEDGER_MOUNT/Ledger Wallet.app" ]; then
                        SRC_APP=""
                        if [ -d "$LEDGER_MOUNT/Ledger Wallet.app" ]; then
                            SRC_APP="Ledger Wallet.app"
                        else
                            SRC_APP="Ledger Live.app"
                        fi

                        LEDGER_SOURCE_VER=$(app_version "$LEDGER_MOUNT/$SRC_APP")
                        if [ "$(internet_version_relation "$LEDGER_SOURCE_VER" "$VER")" != "newer" ]; then
                            print_warn "Refusing non-newer Ledger payload: $LEDGER_SOURCE_VER (installed: $VER)"
                            STATUS_LEDGER="$L_INTERNET_STATUS_INSTALL_ERROR"
                        elif copy_verified_app "$LEDGER_MOUNT/$SRC_APP" "$LEDGER_NAME.app"; then
                            NEW_VER=$(app_version "/Applications/$LEDGER_NAME.app")
                            print_ok "$(internet_msg "$L_INTERNET_APP_UPDATED" "$LEDGER_NAME" "$NEW_VER")"
                            STATUS_LEDGER="$(internet_msg "$L_INTERNET_STATUS_UPDATED_FMT" "$NEW_VER")"
                        else
                            print_warn "$(internet_msg "$L_INTERNET_COPY_ERROR" "$SRC_APP")"
                            STATUS_LEDGER="$L_INTERNET_STATUS_INSTALL_ERROR"
                        fi
                    else
                        print_warn "$L_INTERNET_APP_NOT_ON_VOLUME"
                        STATUS_LEDGER="$L_INTERNET_STATUS_INSTALL_ERROR"
                    fi
                    detach_verified_dmg "$LEDGER_MOUNT" || true
                else
                    print_warn "$L_INTERNET_MOUNT_DMG_FAILED"
                    STATUS_LEDGER="$L_INTERNET_STATUS_MOUNT_ERROR"
                fi
                rm -f "$TEMP_DMG"
            else
                print_warn "$L_INTERNET_DOWNLOAD_VERIFY_FAILED"
                STATUS_LEDGER="$L_INTERNET_STATUS_DOWNLOAD_ERROR"
                rm -f "$TEMP_DMG" 2>/dev/null || true
            fi
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Ledger Live / Ledger Wallet")"
    fi

    # ── 31. TREZOR SUITE (GitHub API + DMG arm64) ─────────────────
}

iu_trezor_suite() {
    print_header "🔒 Trezor Suite"
    if [ -d "/Applications/Trezor Suite.app" ]; then
        VER=$(app_version "/Applications/Trezor Suite.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"

        # Monorepo: trezor-suite publishes both suite (desktop) and connect (library)
        # releases. /releases/latest may return a connect release. Filter to desktop-only
        # tags matching v?NN.N.N (no slashes, no connect prefix).
        LATEST_TS_TAG=$(curl -s --max-time 20 --retry 3 --retry-delay 2 \
            -H "User-Agent: macos-updates-toolkit" \
            ${GITHUB_TOKEN:+-H "Authorization: Bearer $GITHUB_TOKEN"} \
            "https://api.github.com/repos/trezor/trezor-suite/releases?per_page=20" 2>/dev/null \
            | python3 -c 'import json,sys,re
try:
    releases=json.load(sys.stdin)
    for r in releases:
        tag=r.get("tag_name","")
        if not r.get("prerelease") and re.match(r"^v?\d{2}\.\d+\.\d+$", tag):
            print(tag); break
    else:
        print("?")
except Exception:
    print("?")' 2>/dev/null)
        LATEST_TS=$(echo "$LATEST_TS_TAG" | sed 's/^v//')
        TS_RELATION="$(internet_version_relation "$LATEST_TS" "$VER")"

        if [ "$LATEST_TS" = "?" ]; then
            print_warn "$(internet_msg "$L_INTERNET_OFFLINE" "GitHub")"
            STATUS_TREZOR="$L_INTERNET_STATUS_OFFLINE"
        elif [ "$TS_RELATION" = "unknown" ]; then
            print_warn "$(internet_msg "$L_INTERNET_UNKNOWN_DETECTED" "Trezor Suite version")"
            STATUS_TREZOR="$L_INTERNET_STATUS_UNKNOWN_VERSION"
        elif [ "$TS_RELATION" = "current" ]; then
            print_ok "$(internet_msg "$L_INTERNET_APP_CURRENT" "Trezor Suite" "$VER (remote: $LATEST_TS)")"
            STATUS_TREZOR="$L_INTERNET_STATUS_CURRENT"
        else
            print_warn "$(internet_msg "$L_INTERNET_NEW_VERSION_AVAILABLE" "$LATEST_TS" "$VER")"
            print_step "$(internet_msg "$L_INTERNET_DOWNLOADING_ARM" "Trezor Suite" "$LATEST_TS")"
            TS_URL="https://github.com/trezor/trezor-suite/releases/download/${LATEST_TS_TAG}/Trezor-Suite-${LATEST_TS}-mac-arm64.dmg"
            TEMP_DMG="$(make_temp_dmg TrezorSuite)"
            if curl -L --max-time 300 --retry 3 --retry-delay 2 -o "$TEMP_DMG" "$TS_URL" 2>/dev/null; then
                TS_MOUNT="$(mount_verified_dmg "$TEMP_DMG")"
                if [ -n "$TS_MOUNT" ]; then
                    if [ -d "$TS_MOUNT/Trezor Suite.app" ]; then
                        TS_SOURCE_VER=$(app_version "$TS_MOUNT/Trezor Suite.app")
                        if [ "$(internet_version_relation "$TS_SOURCE_VER" "$VER")" != "newer" ]; then
                            print_warn "Refusing non-newer Trezor Suite payload: $TS_SOURCE_VER (installed: $VER)"
                            STATUS_TREZOR="$L_INTERNET_STATUS_INSTALL_ERROR"
                        elif copy_verified_app "$TS_MOUNT/Trezor Suite.app" "Trezor Suite.app"; then
                            NEW_VER=$(app_version "/Applications/Trezor Suite.app")
                            print_ok "$(internet_msg "$L_INTERNET_APP_UPDATED" "Trezor Suite" "$NEW_VER")"
                            STATUS_TREZOR="$(internet_msg "$L_INTERNET_STATUS_UPDATED_FMT" "$NEW_VER")"
                        else
                            print_warn "$(internet_msg "$L_INTERNET_COPY_ERROR" "Trezor Suite.app")"
                            STATUS_TREZOR="$L_INTERNET_STATUS_INSTALL_ERROR"
                        fi
                    else
                        print_warn "$(internet_msg "$L_INTERNET_APP_NOT_FOUND_VOLUME" "Trezor Suite")"
                        print_info "$(internet_msg "$L_INTERNET_DOWNLOAD_MANUALLY" "https://trezor.io/trezor-suite")"
                        STATUS_TREZOR="$L_INTERNET_STATUS_INSTALL_ERROR"
                    fi
                    detach_verified_dmg "$TS_MOUNT" || true
                else
                    print_warn "$L_INTERNET_MOUNT_DMG_FAILED"
                    STATUS_TREZOR="$L_INTERNET_STATUS_MOUNT_ERROR"
                fi
                rm -f "$TEMP_DMG"
            else
                print_warn "$L_INTERNET_DOWNLOAD_VERIFY_FAILED"
                print_info "$(internet_msg "$L_INTERNET_DOWNLOAD_MANUALLY" "https://github.com/trezor/trezor-suite/releases")"
                STATUS_TREZOR="$L_INTERNET_STATUS_DOWNLOAD_ERROR"
                rm -f "$TEMP_DMG" 2>/dev/null || true
            fi
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Trezor Suite")"
    fi

    # ============================================================
    # ██ SEKCJA 11: SIEĆ I INFRASTRUKTURA IT
    # ============================================================

    # ── 32. REMOTE DESKTOP MANAGER (Devolutions) ──────────────────
}

iu_remote_desktop_manager() {
    print_header "🖥️  Remote Desktop Manager"
    if [ -d "/Applications/Remote Desktop Manager.app" ]; then
        VER=$(app_version "/Applications/Remote Desktop Manager.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "Remote Desktop Manager")"
        if silent_launch_app "Remote Desktop Manager"; then
            print_info "$(internet_msg "$L_INTERNET_UPDATE_NOTIFY_LAUNCH" "Remote Desktop Manager")"
            print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "https://devolutions.net/remote-desktop-manager/release-notes/mac/")"
            STATUS_RDMANAGER="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
        else
            STATUS_RDMANAGER="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Remote Desktop Manager")"
    fi

    # ── 34. IPMIVIEW (Supermicro) ────────────────────────────────
}

iu_ipmiview() {
    print_header "🔧 IPMIView (Supermicro)"
    IPMI_PATH=""
    for ipath in "/Applications/IPMIView.app" "/Applications/IPMI View.app"; do
        [ -d "$ipath" ] && IPMI_PATH="$ipath" && break
    done
    if [ -n "$IPMI_PATH" ]; then
        VER=$(app_version "$IPMI_PATH")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_warn "$(internet_msg "$L_INTERNET_NO_AUTO_UPDATER" "IPMIView")"
        print_info "$(internet_msg "$L_INTERNET_DOWNLOAD_LATEST" "https://www.supermicro.com/en/solutions/management-software/ipmi-utilities")"
        STATUS_IPMIVIEW="$L_INTERNET_STATUS_MANUAL_UPDATE"
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "IPMIView")"
    fi

    # ── 35. DJI ASSISTANT (manual) ───────────────────────────────
}

iu_dji_assistant() {
    print_header "🚁 DJI Assistant 2"
    DJI_PATH="$(internet_app_path "DJI Assistant 2")"
    if [ -d "$DJI_PATH" ]; then
        VER=$(app_version "$DJI_PATH")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_warn "$(internet_msg "$L_INTERNET_NO_AUTO_UPDATER" "DJI Assistant 2")"
        print_info "$(internet_msg "$L_INTERNET_DOWNLOAD_LATEST" "https://www.dji.com/downloads/djiapp/dji-assistant-2-consumer-drones-series")"
        STATUS_DJI="$L_INTERNET_STATUS_MANUAL_UPDATE"
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "DJI Assistant 2")"
    fi
}
