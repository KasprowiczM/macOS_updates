#!/usr/bin/env bash
# lib/internet_app_updates.sh — per-app update handlers (sourced by update_internet_apps.sh)
# Requires: helpers from update_internet_apps.sh (print_*, app_version, silent_launch_app, etc.)

iu_google_chrome() {
    print_header "🟡 Google Chrome"
    if [ -d "/Applications/Google Chrome.app" ]; then
        VER=$(app_version "/Applications/Google Chrome.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        # Keystone (Omaha) — oficjalny updater Google dla macOS
        KEYSTONE_AGENT="/Library/Google/GoogleSoftwareUpdate/GoogleSoftwareUpdate.bundle/Contents/Resources/GoogleSoftwareUpdateAgent.app/Contents/MacOS/GoogleSoftwareUpdateAgent"
        if [ -f "$KEYSTONE_AGENT" ]; then
            print_step "$L_INTERNET_LAUNCHING_KEYSTONE"
            "$KEYSTONE_AGENT" --runMode ondemand 2>/dev/null &
            sleep 3
            print_ok "$(internet_msg "$L_INTERNET_KEYSTONE_STARTED" "Chrome")"
            STATUS_CHROME="$L_INTERNET_STATUS_CHECKED_CLI"
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

        if [ "$LATEST_FF" = "?" ]; then
            print_warn "$(internet_msg "$L_INTERNET_OFFLINE" "Mozilla API")"
            if silent_launch_app "Firefox Developer Edition"; then
                print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "Firefox → Pomoc → O Firefoksie")"
                STATUS_FIREFOX="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
            else
                STATUS_FIREFOX="$L_INTERNET_STATUS_LAUNCH_FAILED"
            fi
        elif [ "$LATEST_FF" = "$VER" ] || [ "$LATEST_FF_BASE" = "$VER" ]; then
            # Exact match — already current
            print_ok "$(internet_msg "$L_INTERNET_APP_CURRENT" "Firefox Developer Edition" "$VER")"
            STATUS_FIREFOX="$(internet_msg "$L_INTERNET_STATUS_CURRENT_FMT" "$LATEST_FF")"
        elif [ "$(printf '%s\n%s\n' "$LATEST_FF_BASE" "$VER" | sort -V | tail -1)" = "$VER" ]; then
            # Local version is newer or equal to remote base (e.g. local=150.0.1, remote=150.0b5)
            # DevEdition = beta channel — local may legitimately be ahead
            print_ok "$(internet_msg "$L_INTERNET_APP_CURRENT" "Firefox Developer Edition" "$VER (remote: $LATEST_FF)")"
            STATUS_FIREFOX="$(internet_msg "$L_INTERNET_STATUS_CURRENT_FMT" "$LATEST_FF")"
        else
            print_warn "$(internet_msg "$L_INTERNET_NEW_VERSION_AVAILABLE" "$LATEST_FF" "$VER")"
            print_step "$(internet_msg "$L_INTERNET_DOWNLOADING_APPLE_SILICON" "Firefox Developer Edition" "$LATEST_FF")"
            FF_URL="https://download.mozilla.org/?product=firefox-devedition-latest&os=osx&lang=pl"
            TEMP_DMG="$(make_temp_dmg Firefox_DevEd)"
            if curl -L --max-time 180 --retry 3 --retry-delay 2 -o "$TEMP_DMG" "$FF_URL" 2>/dev/null \
                && verify_dmg "$TEMP_DMG"; then
                if hdiutil attach "$TEMP_DMG" -quiet -nobrowse 2>/dev/null; then
                    sleep 1
                    if copy_verified_app "/Volumes/Firefox Developer Edition/Firefox Developer Edition.app" "Firefox Developer Edition.app"; then
                        NEW_VER=$(firefox_dev_version)
                        print_ok "$(internet_msg "$L_INTERNET_APP_UPDATED" "Firefox Developer Edition" "$NEW_VER")"
                        STATUS_FIREFOX="$(internet_msg "$L_INTERNET_STATUS_UPDATED_FMT" "$NEW_VER")"
                    else
                        print_warn "$(internet_msg "$L_INTERNET_COPY_VERIFIED_FAILED" "Firefox Developer Edition")"
                        STATUS_FIREFOX="$L_INTERNET_STATUS_INSTALL_ERROR"
                    fi
                    hdiutil detach "/Volumes/Firefox Developer Edition" -quiet 2>/dev/null || true
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

        if [ -z "$ATLAS_LATEST" ]; then
            print_warn "$(internet_msg "$L_INTERNET_OFFLINE" "OpenAI server")"
            STATUS_ATLAS="$L_INTERNET_STATUS_OFFLINE"
        elif [ "$ATLAS_LATEST" = "$VER" ]; then
            print_ok "$(internet_msg "$L_INTERNET_APP_CURRENT" "ChatGPT Atlas" "$VER")"
            STATUS_ATLAS="$L_INTERNET_STATUS_CURRENT"
        else
            print_warn "$(internet_msg "$L_INTERNET_NEW_VERSION_AVAILABLE" "$ATLAS_LATEST" "$VER")"
            if [ -n "$ATLAS_DMG_URL" ]; then
                print_step "$(internet_msg "$L_INTERNET_DOWNLOADING_SIZE" "ChatGPT Atlas" "$ATLAS_LATEST" "~250 MB")"
                TEMP_DMG="$(make_temp_dmg ChatGPT_Atlas)"
                if curl -L --max-time 300 --retry 3 --retry-delay 2 -o "$TEMP_DMG" "$ATLAS_DMG_URL" 2>/dev/null \
                    && verify_dmg "$TEMP_DMG"; then
                    if hdiutil attach "$TEMP_DMG" -quiet -nobrowse 2>/dev/null; then
                        sleep 1
                        ATLAS_VOL=$(find /Volumes -maxdepth 1 -type d \
                            \( -iname "*atlas*" -o -iname "*chatgpt*" \) 2>/dev/null | head -1)
                        if [ -n "$ATLAS_VOL" ]; then
                            SRC_APP=$(find "$ATLAS_VOL" -maxdepth 1 -name "*.app" 2>/dev/null | head -1)
                            if [ -n "$SRC_APP" ]; then
                                APP_BASE=$(basename "$SRC_APP")
                                if copy_verified_app "$SRC_APP" "$APP_BASE"; then
                                    print_ok "$(internet_msg "$L_INTERNET_APP_COPIED" "$APP_BASE")"
                                    NEW_VER=$(app_version "$ATLAS_APP")
                                    print_ok "$(internet_msg "$L_INTERNET_APP_UPDATED" "ChatGPT Atlas" "$NEW_VER")"
                                    STATUS_ATLAS="$(internet_msg "$L_INTERNET_STATUS_UPDATED_FMT" "$NEW_VER")"
                                else
                                    print_warn "$(internet_msg "$L_INTERNET_COPY_ERROR" "$APP_BASE")"
                                    STATUS_ATLAS="$L_INTERNET_STATUS_INSTALL_ERROR"
                                fi
                                hdiutil detach "$ATLAS_VOL" -quiet 2>/dev/null || true
                            else
                                hdiutil detach "$ATLAS_VOL" -quiet 2>/dev/null || true
                                print_warn "$L_INTERNET_APP_NOT_ON_VOLUME"
                                STATUS_ATLAS="$L_INTERNET_STATUS_INSTALL_ERROR"
                            fi
                        else
                            print_warn "$L_INTERNET_VOLUME_NOT_FOUND"
                            STATUS_ATLAS="$L_INTERNET_STATUS_MOUNT_ERROR"
                        fi
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
    print_header "🤖 ChatGPT"
    if [ -d "/Applications/ChatGPT.app" ]; then
        VER=$(app_version "/Applications/ChatGPT.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "ChatGPT")"
        if silent_launch_app "ChatGPT"; then
            print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "ChatGPT → Check for updates")"
            STATUS_CHATGPT="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
        else
            STATUS_CHATGPT="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "ChatGPT")"
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

    # ── 11. CODEX DESKTOP (OpenAI) ────────────────────────────────
}

iu_codex_desktop() {
    print_header "⚡ Codex Desktop (OpenAI)"
    # OpenAI Codex — agent kodowania AI, pobierany z chatgpt.com/codex
    # Obsługuje auto-aktualizacje przez wbudowany updater (Electron Squirrel)
    if [ -d "/Applications/Codex.app" ]; then
        VER=$(app_version "/Applications/Codex.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "Codex")"
        if silent_launch_app "Codex"; then
            print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "Codex → About Codex → Check for updates")"
            print_info "Strona pobierania: https://chatgpt.com/codex"
            STATUS_CODEX="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
        else
            STATUS_CODEX="$L_INTERNET_STATUS_LAUNCH_FAILED"
        fi
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Codex Desktop")"
        print_info "$(internet_msg "$L_INTERNET_DOWNLOAD_FROM" "https://chatgpt.com/codex (tylko Apple Silicon)")"
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
        elif [ "$LATEST_KPX" = "$VER" ]; then
            print_ok "$(internet_msg "$L_INTERNET_APP_CURRENT" "KeePassXC" "$VER")"
            STATUS_KEEPASSXC="$L_INTERNET_STATUS_CURRENT"
        else
            print_warn "$(internet_msg "$L_INTERNET_NEW_VERSION_AVAILABLE" "$LATEST_KPX" "$VER")"
            print_step "$(internet_msg "$L_INTERNET_DOWNLOADING" "KeePassXC" "$LATEST_KPX ($KPX_ARCH)")"
            KPX_URL="https://github.com/keepassxreboot/keepassxc/releases/download/${LATEST_KPX_TAG}/KeePassXC-${LATEST_KPX}-${KPX_ARCH}.dmg"
            TEMP_DMG="$(make_temp_dmg KeePassXC)"
            if curl -L --max-time 180 --retry 3 --retry-delay 2 -o "$TEMP_DMG" "$KPX_URL" 2>/dev/null \
                && verify_dmg "$TEMP_DMG"; then
                if hdiutil attach "$TEMP_DMG" -quiet -nobrowse 2>/dev/null; then
                    sleep 1
                    VOLUME_PATH=$(find /Volumes -maxdepth 1 -type d -iname "*keepass*" 2>/dev/null | head -1)
                    if [ -n "$VOLUME_PATH" ] && [ -d "$VOLUME_PATH/KeePassXC.app" ]; then
                        if copy_verified_app "$VOLUME_PATH/KeePassXC.app" "KeePassXC.app"; then
                            print_ok "$(internet_msg "$L_INTERNET_APP_COPIED" "KeePassXC")"
                            NEW_VER=$(app_version "/Applications/KeePassXC.app")
                            print_ok "$(internet_msg "$L_INTERNET_APP_UPDATED" "KeePassXC" "$NEW_VER")"
                            STATUS_KEEPASSXC="$(internet_msg "$L_INTERNET_STATUS_UPDATED_FMT" "$NEW_VER")"
                        else
                            print_warn "$(internet_msg "$L_INTERNET_COPY_ERROR" "KeePassXC")"
                            STATUS_KEEPASSXC="$L_INTERNET_STATUS_INSTALL_ERROR"
                        fi
                        hdiutil detach "$VOLUME_PATH" -quiet 2>/dev/null || true
                    else
                        [ -n "$VOLUME_PATH" ] && hdiutil detach "$VOLUME_PATH" -quiet 2>/dev/null || true
                        print_warn "$(internet_msg "$L_INTERNET_APP_NOT_FOUND_VOLUME" "KeePassXC")"
                        STATUS_KEEPASSXC="$L_INTERNET_STATUS_INSTALL_ERROR"
                    fi
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

        LATEST_PROTON_TAG=$(github_latest_tag "ProtonMail/proton-mail-desktop")
        LATEST_PROTON=$(echo "$LATEST_PROTON_TAG" | sed 's/^v//')

        if [ "$LATEST_PROTON" = "?" ]; then
            print_warn "$(internet_msg "$L_INTERNET_OFFLINE" "GitHub")"
        elif [ "$LATEST_PROTON" = "$VER" ]; then
            print_ok "$(internet_msg "$L_INTERNET_APP_CURRENT" "Proton Mail" "$VER")"
            STATUS_PROTONMAIL="$L_INTERNET_STATUS_CURRENT"
        else
            print_warn "$(internet_msg "$L_INTERNET_NEW_VERSION_MAYBE" "$LATEST_PROTON" "$VER")"
        fi
        # If not already marked current, launch for self-update
        if [ "${STATUS_PROTONMAIL:-}" != "$L_INTERNET_STATUS_CURRENT" ]; then
            print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "Proton Mail")"
            if silent_launch_app "Proton Mail"; then
                print_info "$(internet_msg "$L_INTERNET_AUTO_UPDATES_SPARKLE" "Proton Mail")"
                STATUS_PROTONMAIL="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
            else
                STATUS_PROTONMAIL="$L_INTERNET_STATUS_LAUNCH_FAILED"
            fi
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
            "$KEYSTONE_AGENT" --runMode ondemand 2>/dev/null &
            sleep 2
            print_ok "$(internet_msg "$L_INTERNET_KEYSTONE_STARTED" "Google Drive")"
            STATUS_GOOGLEDRIVE="$L_INTERNET_STATUS_CHECKED_CLI"
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

iu_microsoft_365() {
    print_header "💼 Microsoft 365 (via Microsoft AutoUpdate)"

    MAU_CLI="/Library/Application Support/Microsoft/MAU2.0/Microsoft AutoUpdate.app/Contents/MacOS/msupdate"
    MAU_APP="/Library/Application Support/Microsoft/MAU2.0/Microsoft AutoUpdate.app"

    # Sprawdź czy zainstalowana jest jakakolwiek aplikacja Microsoft
    MS_INSTALLED=0
    for ms_app in "Microsoft Word" "Microsoft Excel" "Microsoft PowerPoint" \
                   "Microsoft Outlook" "Microsoft OneNote" "Microsoft Teams"; do
        if [ -d "/Applications/${ms_app}.app" ]; then
            VER=$(app_version "/Applications/${ms_app}.app")
            print_info "${ms_app}: $VER"
            MS_INSTALLED=1
        fi
    done

    if [ "$MS_INSTALLED" = "1" ]; then
        if [ -f "$MAU_CLI" ]; then
            # Krok 1: sprawdź dostępne aktualizacje z limitem czasu 30s
            print_step "$L_INTERNET_MS_CHECKING"
            MAU_LIST=$(run_with_timeout 60 "$MAU_CLI" --list 2>/dev/null || true)

            # Filtruj linie zawierające rzeczywiste wpisy aktualizacji
            # msupdate --list wypisuje nazwy pakietów lub pusty wynik gdy brak aktualizacji
            MAU_UPDATES=$(echo "$MAU_LIST" | grep -v "^[[:space:]]*$" | grep -v "No updates" || true)
            MAU_COUNT=$(echo "$MAU_UPDATES" | grep -c "." 2>/dev/null || echo "0")

            if [ -n "$MAU_UPDATES" ] && [ "$MAU_COUNT" -gt 0 ]; then
                print_info "$(internet_msg "$L_INTERNET_MS_UPDATES_AVAILABLE" "$MAU_COUNT")"
                echo "$MAU_UPDATES" | while read -r line; do
                    [ -n "$line" ] && print_info "  → $line"
                done
                # Krok 2: instaluj tylko jeśli są aktualizacje; limit 300s (5 min)
                print_step "$L_INTERNET_MS_INSTALLING"
                if run_with_timeout 300 "$MAU_CLI" --install 2>/dev/null; then
                    print_ok "$L_INTERNET_MS_UPDATED"
                    STATUS_MICROSOFT="$(internet_msg "$L_INTERNET_STATUS_UPDATED_FMT" "Microsoft 365")"
                else
                    EXIT_CODE=$?
                    if [ "$EXIT_CODE" = "124" ]; then
                        print_warn "$L_INTERNET_MS_TIMEOUT"
                    else
                        print_warn "$(internet_msg "$L_INTERNET_MS_INSTALL_ERROR" "$EXIT_CODE")"
                    fi
                    if [ -d "$MAU_APP" ]; then
                        open -a "$MAU_APP" 2>/dev/null || true
                        print_info "$L_INTERNET_MS_ACCEPT_IN_WINDOW"
                    fi
                    STATUS_MICROSOFT="$L_INTERNET_STATUS_CHECK_MAU"
                fi
            else
                print_ok "$L_INTERNET_MS_CURRENT"
                STATUS_MICROSOFT="$L_INTERNET_STATUS_CURRENT"
            fi
        elif [ -d "$MAU_APP" ]; then
        print_step "$L_INTERNET_MS_OPENING_GUI"
        open -a "$MAU_APP" 2>/dev/null || true
        print_info "$L_INTERNET_MS_ACCEPT_GUI"
        STATUS_MICROSOFT="$L_INTERNET_STATUS_MAU_OPENED"
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

    # ── 19. VISUAL STUDIO CODE ────────────────────────────────────
}

iu_visual_studio_code() {
    print_header "💻 Visual Studio Code"
    if [ -d "/Applications/Visual Studio Code.app" ]; then
        VER=$(app_version "/Applications/Visual Studio Code.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"

        LATEST_VSCODE=$(github_latest_tag "microsoft/vscode" | sed 's/^v//')

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
        elif [ "$VER" = "$LATEST_VSCODE" ]; then
            print_ok "$(internet_msg "$L_INTERNET_APP_CURRENT" "VS Code" "$VER")"
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
                        if copy_verified_app "$TEMP_DIR/Visual Studio Code.app" "Visual Studio Code.app"; then
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

        if [ "$LATEST_CE" = "?" ]; then
            print_warn "$(internet_msg "$L_INTERNET_OFFLINE" "GitHub")"
            if silent_launch_app "CodeEdit"; then
                STATUS_CODEEDIT="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
            else
                STATUS_CODEEDIT="$L_INTERNET_STATUS_LAUNCH_FAILED"
            fi
        elif [ "$LATEST_CE" = "$VER" ]; then
            print_ok "$(internet_msg "$L_INTERNET_APP_CURRENT" "CodeEdit" "$VER")"
            STATUS_CODEEDIT="$L_INTERNET_STATUS_CURRENT"
        else
            print_warn "$(internet_msg "$L_INTERNET_NEW_VERSION_AVAILABLE" "$LATEST_CE" "$VER")"
            print_step "$(internet_msg "$L_INTERNET_DOWNLOADING" "CodeEdit" "$LATEST_CE")"
            CE_URL="https://github.com/CodeEditApp/CodeEdit/releases/download/${LATEST_CE_TAG}/CodeEdit.dmg"
            TEMP_DMG="$(make_temp_dmg CodeEdit)"
            if curl -L --max-time 180 --retry 3 --retry-delay 2 -o "$TEMP_DMG" "$CE_URL" 2>/dev/null \
                && verify_dmg "$TEMP_DMG"; then
                if hdiutil attach "$TEMP_DMG" -quiet -nobrowse 2>/dev/null; then
                    sleep 1
                    VOLUME_PATH=$(find /Volumes -maxdepth 1 -type d -iname "*codeedit*" 2>/dev/null | head -1)
                    if [ -n "$VOLUME_PATH" ] && [ -d "$VOLUME_PATH/CodeEdit.app" ]; then
                        if copy_verified_app "$VOLUME_PATH/CodeEdit.app" "CodeEdit.app"; then
                            NEW_VER=$(app_version "/Applications/CodeEdit.app")
                            print_ok "$(internet_msg "$L_INTERNET_APP_UPDATED" "CodeEdit" "$NEW_VER")"
                            STATUS_CODEEDIT="$(internet_msg "$L_INTERNET_STATUS_UPDATED_FMT" "$NEW_VER")"
                        else
                            print_warn "$(internet_msg "$L_INTERNET_COPY_ERROR" "CodeEdit")"
                            STATUS_CODEEDIT="$L_INTERNET_STATUS_INSTALL_ERROR"
                        fi
                        hdiutil detach "$VOLUME_PATH" -quiet 2>/dev/null || true
                    else
                        [ -n "$VOLUME_PATH" ] && hdiutil detach "$VOLUME_PATH" -quiet 2>/dev/null || true
                        print_warn "$(internet_msg "$L_INTERNET_APP_NOT_FOUND_VOLUME" "CodeEdit")"
                        STATUS_CODEEDIT="$L_INTERNET_STATUS_INSTALL_ERROR"
                    fi
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
        if command -v docker >/dev/null 2>&1; then
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
            # No CLI — visible launch for menu-bar notification
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

        if [ -z "$LATEST_LEDGER" ]; then
            print_warn "$(internet_msg "$L_INTERNET_OFFLINE" "GitHub")"
            STATUS_LEDGER="$L_INTERNET_STATUS_OFFLINE"
        elif [ "$LATEST_LEDGER" = "$VER" ]; then
            print_ok "$(internet_msg "$L_INTERNET_APP_CURRENT" "$LEDGER_NAME" "$VER")"
            STATUS_LEDGER="$L_INTERNET_STATUS_CURRENT"
        else
            print_warn "$(internet_msg "$L_INTERNET_NEW_VERSION_AVAILABLE" "$LATEST_LEDGER" "$VER")"
            print_step "$(internet_msg "$L_INTERNET_DOWNLOADING" "$LEDGER_NAME" "$LATEST_LEDGER")"
            # Parse the actual DMG filename from the YAML 'path:' field
            LEDGER_DMG_FILE=$(echo "$LEDGER_YML" | grep "^  *- url:" | head -1 | sed 's|.*url: *||' | tr -d '[:space:]')
            if [ -z "$LEDGER_DMG_FILE" ]; then
                LEDGER_DMG_FILE="ledger-live-desktop-${LATEST_LEDGER}-mac.dmg"
            fi
            LEDGER_URL="https://download.live.ledger.com/${LEDGER_DMG_FILE}"
            TEMP_DMG="$(make_temp_dmg LedgerWallet)"
            if curl -L --max-time 300 --retry 3 --retry-delay 2 -o "$TEMP_DMG" "$LEDGER_URL" 2>/dev/null \
                && verify_dmg "$TEMP_DMG"; then
                if hdiutil attach "$TEMP_DMG" -quiet -nobrowse 2>/dev/null; then
                    sleep 1
                    VOLUME_PATH=$(find /Volumes -maxdepth 1 -type d -iname "*ledger*" 2>/dev/null | head -1)
                    if [ -n "$VOLUME_PATH" ] && { [ -d "$VOLUME_PATH/Ledger Live.app" ] || [ -d "$VOLUME_PATH/Ledger Wallet.app" ]; }; then
                        SRC_APP=""
                        if [ -d "$VOLUME_PATH/Ledger Wallet.app" ]; then
                            SRC_APP="Ledger Wallet.app"
                        else
                            SRC_APP="Ledger Live.app"
                        fi

                        if copy_verified_app "$VOLUME_PATH/$SRC_APP" "$LEDGER_NAME.app"; then
                            NEW_VER=$(app_version "/Applications/$LEDGER_NAME.app")
                            print_ok "$(internet_msg "$L_INTERNET_APP_UPDATED" "$LEDGER_NAME" "$NEW_VER")"
                            STATUS_LEDGER="$(internet_msg "$L_INTERNET_STATUS_UPDATED_FMT" "$NEW_VER")"
                        else
                            print_warn "$(internet_msg "$L_INTERNET_COPY_ERROR" "$SRC_APP")"
                            STATUS_LEDGER="$L_INTERNET_STATUS_INSTALL_ERROR"
                        fi
                        hdiutil detach "$VOLUME_PATH" -quiet 2>/dev/null || true
                    else
                        [ -n "$VOLUME_PATH" ] && hdiutil detach "$VOLUME_PATH" -quiet 2>/dev/null || true
                        print_warn "$L_INTERNET_APP_NOT_ON_VOLUME"
                        STATUS_LEDGER="$L_INTERNET_STATUS_INSTALL_ERROR"
                    fi
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

        if [ "$LATEST_TS" = "?" ]; then
            print_warn "$(internet_msg "$L_INTERNET_OFFLINE" "GitHub")"
            STATUS_TREZOR="$L_INTERNET_STATUS_OFFLINE"
        elif [ "$LATEST_TS" = "$VER" ]; then
            print_ok "$(internet_msg "$L_INTERNET_APP_CURRENT" "Trezor Suite" "$VER")"
            STATUS_TREZOR="$L_INTERNET_STATUS_CURRENT"
        else
            print_warn "$(internet_msg "$L_INTERNET_NEW_VERSION_AVAILABLE" "$LATEST_TS" "$VER")"
            print_step "$(internet_msg "$L_INTERNET_DOWNLOADING_ARM" "Trezor Suite" "$LATEST_TS")"
            TS_URL="https://github.com/trezor/trezor-suite/releases/download/${LATEST_TS_TAG}/Trezor-Suite-${LATEST_TS}-mac-arm64.dmg"
            TEMP_DMG="$(make_temp_dmg TrezorSuite)"
            if curl -L --max-time 300 --retry 3 --retry-delay 2 -o "$TEMP_DMG" "$TS_URL" 2>/dev/null \
                && verify_dmg "$TEMP_DMG"; then
                if hdiutil attach "$TEMP_DMG" -quiet -nobrowse 2>/dev/null; then
                    sleep 1
                    VOLUME_PATH=$(find /Volumes -maxdepth 1 -type d -iname "*trezor*" 2>/dev/null | head -1)
                    if [ -n "$VOLUME_PATH" ] && [ -d "$VOLUME_PATH/Trezor Suite.app" ]; then
                        if copy_verified_app "$VOLUME_PATH/Trezor Suite.app" "Trezor Suite.app"; then
                            NEW_VER=$(app_version "/Applications/Trezor Suite.app")
                            print_ok "$(internet_msg "$L_INTERNET_APP_UPDATED" "Trezor Suite" "$NEW_VER")"
                            STATUS_TREZOR="$(internet_msg "$L_INTERNET_STATUS_UPDATED_FMT" "$NEW_VER")"
                        else
                            print_warn "$(internet_msg "$L_INTERNET_COPY_ERROR" "Trezor Suite.app")"
                            STATUS_TREZOR="$L_INTERNET_STATUS_INSTALL_ERROR"
                        fi
                        hdiutil detach "$VOLUME_PATH" -quiet 2>/dev/null || true
                    else
                        [ -n "$VOLUME_PATH" ] && hdiutil detach "$VOLUME_PATH" -quiet 2>/dev/null || true
                        print_warn "$(internet_msg "$L_INTERNET_APP_NOT_FOUND_VOLUME" "Trezor Suite")"
                        print_info "$(internet_msg "$L_INTERNET_DOWNLOAD_MANUALLY" "https://trezor.io/trezor-suite")"
                        STATUS_TREZOR="$L_INTERNET_STATUS_INSTALL_ERROR"
                    fi
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

    # ── 35. INKSCAPE (Vector Graphics) ───────────────────────────
}

iu_inkscape() {
    print_header "🎨 Inkscape"
    if [ -d "/Applications/Inkscape.app" ]; then
        VER=$(app_version "/Applications/Inkscape.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_warn "$(internet_msg "$L_INTERNET_NO_AUTO_UPDATER" "Inkscape")"
        print_info "$(internet_msg "$L_INTERNET_DOWNLOAD_LATEST" "https://inkscape.org/release/")"
        STATUS_INKSCAPE="$L_INTERNET_STATUS_MANUAL_UPDATE"
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Inkscape")"
    fi

}

iu_dji_assistant() {
    print_header "🚁 DJI Assistant 2"
    # Note: The app name has parentheses in the bundle name
    DJI_PATH=""
    for dpath in "/Applications/DJI Assistant 2(Consumer Drones Series).app" \
                 "/Applications/DJI Assistant 2.app"; do
        [ -d "$dpath" ] && DJI_PATH="$dpath" && break
    done
    if [ -n "$DJI_PATH" ]; then
        VER=$(app_version "$DJI_PATH")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_warn "$(internet_msg "$L_INTERNET_NO_AUTO_UPDATER" "DJI Assistant 2")"
        print_info "$(internet_msg "$L_INTERNET_DOWNLOAD_LATEST" "https://www.dji.com/downloads/djiapp/dji-assistant-2-consumer-drones-series")"
        STATUS_DJI="$L_INTERNET_STATUS_MANUAL_UPDATE"
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "DJI Assistant 2")"
    fi
}

iu_unifi() {
    print_header "📡 UniFi"
    if [ -d "/Applications/UniFi.app" ]; then
        VER=$(app_version "/Applications/UniFi.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_warn "$(internet_msg "$L_INTERNET_NO_AUTO_UPDATER" "UniFi (iPad/iOS app)")"
        print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "App Store → Account → Updates")"
        STATUS_UNIFI="$L_INTERNET_STATUS_MANUAL_UPDATE"
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "UniFi")"
    fi
}

iu_wifiman() {
    print_header "📶 WiFiman"
    if [ -d "/Applications/WiFiman.app" ]; then
        VER=$(app_version "/Applications/WiFiman.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_warn "$(internet_msg "$L_INTERNET_NO_AUTO_UPDATER" "WiFiman (iPad/iOS app)")"
        print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "App Store → Account → Updates")"
        STATUS_WIFIMAN="$L_INTERNET_STATUS_MANUAL_UPDATE"
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "WiFiman")"
    fi
}

iu_picsart() {
    print_header "🎨 Picsart"
    if [ -d "/Applications/Picsart.app" ]; then
        VER=$(app_version "/Applications/Picsart.app")
        print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"
        print_warn "$(internet_msg "$L_INTERNET_NO_AUTO_UPDATER" "Picsart")"
        print_info "$(internet_msg "$L_INTERNET_DOWNLOAD_LATEST" "https://picsart.com/apps")"
        STATUS_PICSART="$L_INTERNET_STATUS_MANUAL_UPDATE"
    else
        print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "Picsart")"
    fi
}
