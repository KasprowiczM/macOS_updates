#!/usr/bin/env python3
"""One-shot migrator: Polish literals in update_internet_apps.sh → L_INTERNET_* (EN i18n)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "update_internet_apps.sh"

# Status literal replacements (assignment RHS)
STATUS_REPLACEMENTS = [
    (r'STATUS_\w+="✅ Aktualny \(\$LATEST_FF\)"', 'STATUS_FIREFOX="$(internet_msg "$L_INTERNET_STATUS_CURRENT_FMT" "$LATEST_FF")"'),
    (r'STATUS_\w+="✅ Aktualny"', 'STATUS_VAR="$L_INTERNET_STATUS_CURRENT"'),
    (r'STATUS_\w+="✅ Zaktualizowany do \$NEW_VER"', 'STATUS_VAR="$(internet_msg "$L_INTERNET_STATUS_UPDATED_FMT" "$NEW_VER")"'),
    (r'"⚠️  Błąd instalacji"', '"$L_INTERNET_STATUS_INSTALL_ERROR"'),
    (r'"⚠️  Błąd montowania"', '"$L_INTERNET_STATUS_MOUNT_ERROR"'),
    (r'"⚠️  Błąd pobierania"', '"$L_INTERNET_STATUS_DOWNLOAD_ERROR"'),
    (r'"⚠️  Błąd rozpakowywania"', '"$L_INTERNET_STATUS_EXTRACT_ERROR"'),
    (r'"⚠️  Brak URL"', '"$L_INTERNET_STATUS_NO_URL"'),
    (r'"⏭️  Nieznana wersja"', '"$L_INTERNET_STATUS_UNKNOWN_VERSION"'),
    (r'"⏭️  Brak Desktop \.app"', '"$L_INTERNET_STATUS_NO_DESKTOP_APP"'),
]

# print_* phrase replacements (order matters — longer first)
PHRASE_REPLACEMENTS = [
    ('print_info "Zainstalowana wersja: $VER"', 'print_info "$(internet_msg "$L_INTERNET_INSTALLED_VERSION" "$VER")"'),
    ('print_step "Uruchamiam Google Keystone Updater (Omaha)..."', 'print_step "$L_INTERNET_LAUNCHING_KEYSTONE"'),
    ('print_ok "Keystone uruchomiony — Chrome zaktualizuje się automatycznie w tle"', 'print_ok "$(internet_msg "$L_INTERNET_KEYSTONE_STARTED" "Chrome")"'),
    ('print_warn "Brak połączenia z API Mozilla"', 'print_warn "$(internet_msg "$L_INTERNET_OFFLINE" "Mozilla API")"'),
    ('print_warn "Brak połączenia z serwerem OpenAI — pomijam aktualizację Atlas"', 'print_warn "$(internet_msg "$L_INTERNET_OFFLINE" "OpenAI server")"'),
    ('print_warn "Pobieranie lub weryfikacja DMG nie powiodła się."', 'print_warn "$L_INTERNET_DOWNLOAD_VERIFY_FAILED"'),
    ('print_warn "Nie można zamontować DMG. Zaktualizuj ręcznie."', 'print_warn "$L_INTERNET_MOUNT_DMG_MANUAL"'),
    ('print_warn "Nie można zamontować DMG."', 'print_warn "$L_INTERNET_MOUNT_DMG_FAILED"'),
    ('print_warn "Nie można skopiować zweryfikowanej aplikacji Firefox Developer Edition."', 'print_warn "$(internet_msg "$L_INTERNET_COPY_VERIFIED_FAILED" "Firefox Developer Edition")"'),
    ('print_warn "Nie znaleziono .app na woluminie."', 'print_warn "$L_INTERNET_APP_NOT_ON_VOLUME"'),
    ('print_warn "Nie znaleziono woluminu Atlas po montowaniu DMG."', 'print_warn "$L_INTERNET_VOLUME_NOT_FOUND"'),
    ('print_warn "Brak URL pobierania w appcast."', 'print_warn "$L_INTERNET_NO_DOWNLOAD_URL"'),
    ('print_warn "Dostępna nowa wersja:', 'print_warn "$(internet_msg "$L_INTERNET_NEW_VERSION_AVAILABLE"'),
    ('print_ok "Firefox Developer Edition jest aktualny (wersja $VER, kanał: $LATEST_FF)"', 'print_ok "$(internet_msg "$L_INTERNET_APP_CURRENT" "Firefox Developer Edition" "$VER")"'),
    ('print_ok "ChatGPT Atlas jest aktualny (wersja $VER)"', 'print_ok "$(internet_msg "$L_INTERNET_APP_CURRENT" "ChatGPT Atlas" "$VER")"'),
    ('print_ok "$APP_BASE skopiowany pomyślnie"', 'print_ok "$(internet_msg "$L_INTERNET_APP_COPIED" "$APP_BASE")"'),
    ('print_warn "Błąd kopiowania $APP_BASE"', 'print_warn "$(internet_msg "$L_INTERNET_COPY_ERROR" "$APP_BASE")"'),
]

# Regex: print_info "APP nie jest zainstalowany"
NOT_INSTALLED_RE = re.compile(
    r'print_info "([^"]+) nie jest zainstalowany(?: jako \.app)?"'
)


def migrate_not_installed(text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        app = m.group(1)
        if "jako .app" in m.group(0):
            return f'print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED_AS_APP" "{app}")"'
        return f'print_info "$(internet_msg "$L_INTERNET_NOT_INSTALLED" "{app}")"'

    return NOT_INSTALLED_RE.sub(repl, text)


def migrate_launch_hidden(text: str) -> str:
    # print_step "Uruchamiam X w tle (ukryty) — ..."
    pat = re.compile(
        r'print_step "Uruchamiam ([^"]+) w tle \(ukryty\)[^"]*"'
    )

    def repl(m: re.Match[str]) -> str:
        app = m.group(1)
        return f'print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "{app}")"'

    return pat.sub(repl, text)


def migrate_manual_verify(text: str) -> str:
    pat = re.compile(r'print_info "Ręczna weryfikacja: ([^"]+)"')

    def repl(m: re.Match[str]) -> str:
        return f'print_info "$(internet_msg "$L_INTERNET_MANUAL_VERIFY" "{m.group(1)}")"'

    return pat.sub(repl, text)


def migrate_download_manual(text: str) -> str:
    for prefix in ("Pobierz ręcznie:", "Pobierz z:", "Pobierz najnowszą wersję:"):
        pat = re.compile(rf'print_info "{re.escape(prefix)} ([^"]+)"')
        key = {
            "Pobierz ręcznie:": "L_INTERNET_DOWNLOAD_MANUALLY",
            "Pobierz z:": "L_INTERNET_DOWNLOAD_FROM",
            "Pobierz najnowszą wersję:": "L_INTERNET_DOWNLOAD_LATEST",
        }[prefix]

        def repl(m: re.Match[str], k=key) -> str:
            return f'print_info "$(internet_msg "${k}" "{m.group(1)}")"'

        text = pat.sub(repl, text)
    return text


def migrate_auto_updates(text: str) -> str:
    pat = re.compile(r'print_info "([^"]+) aktualizuje się automatycznie\.?"')

    def repl(m: re.Match[str]) -> str:
        return f'print_info "$(internet_msg "$L_INTERNET_AUTO_UPDATES" "{m.group(1)}")"'

    return pat.sub(repl, text)


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")
    for old, new in PHRASE_REPLACEMENTS:
        text = text.replace(old, new)
    for pat, repl in STATUS_REPLACEMENTS:
        if "STATUS_VAR" in repl or "STATUS_FIREFOX" in repl:
            continue  # skip broken generic patterns
        text = re.sub(pat, repl, text)
    # Explicit status fixes
    text = text.replace('STATUS_FIREFOX="✅ Aktualny ($LATEST_FF)"',
                        'STATUS_FIREFOX="$(internet_msg "$L_INTERNET_STATUS_CURRENT_FMT" "$LATEST_FF")"')
    text = re.sub(
        r'STATUS_(\w+)="✅ Zaktualizowany do \$NEW_VER"',
        r'STATUS_\1="$(internet_msg "$L_INTERNET_STATUS_UPDATED_FMT" "$NEW_VER")"',
        text,
    )
    text = text.replace('STATUS_ATLAS="✅ Aktualny"', 'STATUS_ATLAS="$L_INTERNET_STATUS_CURRENT"')
    text = migrate_not_installed(text)
    text = migrate_launch_hidden(text)
    text = migrate_manual_verify(text)
    text = migrate_download_manual(text)
    text = migrate_auto_updates(text)
    # Section comment EN
    text = text.replace("# ██ SEKCJA 1: PRZEGLĄDARKI", "# SECTION 1: BROWSERS")
    TARGET.write_text(text, encoding="utf-8")
    print(f"Migrated {TARGET}")


if __name__ == "__main__":
    main()
