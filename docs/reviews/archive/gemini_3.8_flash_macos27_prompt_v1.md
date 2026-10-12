# Prompt wykonawczy dla Gemini 3.8 Flash — macOS Updates v1.4.6: adaptacja do macOS 27 Golden Gate

> Źródło ustaleń: `docs/reviews/archive/fable5.1_ultra_review_macos27_v1.md` (2026-09-16). Wklej całość poniższego bloku jako pierwszą wiadomość. Prompt jest samowystarczalny; review czytaj tylko, gdy potrzebujesz dowodu z logu.

---

Jesteś inżynierem shell/macOS pracującym w repozytorium `~/Dev_Env/macOS_updates` (Bash **3.2**, Python 3, Apple Silicon only, macOS 13–**27**, 7 języków i18n). Zanim cokolwiek zmienisz, przeczytaj `AGENTS.md`, `docs/agents/critical_rules.md`, `docs/agents/exit_codes.md` i `docs/reviews/archive/fable5.1_ultra_review_macos27_v1.md`. Pracujesz na maszynie z **macOS 27.0 (26A428)**, Homebrew 7.0.2, Xcode 27.0, mas 7.0.0.

## Nienegocjowalne ograniczenia

1. **Bash 3.2**: żadnych `declare -A`, `mapfile`, `readarray`, `${var,,}`, `[[ =~ ]]` z grupami nazwanymi. Sprawdzaj `bash -n` po każdym pliku.
2. Każdy `update_*.sh` ma `set -o pipefail` i **nie ma** `set -e`.
3. `softwareupdate` do instalacji **zawsze z `-R`**. `mas upgrade` **zawsze `sudo` + jawne ID**. Interaktywne `sudo` tylko przy TTY.
4. Każde zapytanie Homebrew przez `lib/brew.sh`; nigdy `brew outdated … 2>&1`; nigdy `brew list --cask --versions`.
5. **Measured, not claimed**: sukces raportujesz wyłącznie po odczycie żywego systemu (`--version` rc 0 + semver, ponowny listing, zmiana wersji bundla). Brak pomiaru = `unknown`/`unconfirmed`, nigdy `0` ani `OK`.
6. Żadnych nowych samodzielnych entrypointów Python — czyste funkcje w `lib/python/*.py`, wywoływane z heredoców.
7. Żadnych ścieżek na sztywno, `mktemp -d "${TMPDIR:-/tmp}/mac_update_*.XXXXXX"`, brak PII w plikach śledzonych.
8. **Nie uruchamiaj** `update_all.sh` bez `--dry-run`, `brew upgrade`, `softwareupdate -i`, `xcodebuild -license accept`, `softwareupdate --install-rosetta`, `rm -rf /Library/...`. Wszystkie testy na atrapach w `PATH` i w katalogach tymczasowych.
9. Zmiana widoczna dla użytkownika = aktualizacja **wszystkich 7** plików `i18n/lang_*.sh` (parytet kluczy jest testowany) oraz 7 README, gdy dotyczy dokumentacji.
10. Nie dodawaj workflowów GitHub Actions, harmonogramów ani runnerów macOS. Nie taguj. Nie pushuj bez polecenia.
11. Każdą poprawkę zaczynaj testem, który **pada na obecnym kodzie**, a przechodzi po zmianie. Preferuj testy behawioralne (atrapy `softwareupdate`, `xcodebuild`, `mas`, `lipo`, `launchctl` w `PATH`) nad `assertIn` na źródle.
12. `bash run_tests.sh` musi być zielony po każdym zadaniu; na końcu ShellCheck `-S warning` bez znalezisk.

## Zadania w dokładnej kolejności

### T0 — Higiena repo (bez zmian logiki)

- `git switch -c fix/macos27-adaptation` z bieżącego working tree (zawiera niezacommitowane zmiany MAU v3 / run_summary v3 — **zachowaj je**, są przetestowane: 291 testów).
- Przenieś nieśledzony `ULTRA_REVIEW_REPORT.md` do `docs/reviews/ULTRA_REVIEW_2026-09-06_v144.md` (zwykłe `mv`). Nie dodawaj plików z `docs/reviews/` do commita, jeśli `docs/reviews/README.md` mówi, że są nieśledzone.
- Pierwszy commit: „feat: run summary v3 with per-item results and MAU interruption handling” z 11 zmienionymi plikami + `tests/test_run_log_regressions_20260910.py`.

### T1 — Strażnik licencji Xcode (P0-1)

Kontekst: przebieg 2026-09-16 11:06 zaktualizował Xcode 27.0 w kroku App Store, po czym krok Homebrew padł na `You have not agreed to the Xcode license`; cały krok został pominięty.

1. `lib/brew.sh`: funkcja `brew_xcode_license_ok()` — zwraca 0, gdy `xcode-select -p` nie wskazuje `*.app/Contents/Developer` **lub** `xcodebuild -license check >/dev/null 2>&1` zwraca 0. Bez wywołania `brew`.
2. `update_brew.sh` preflight, przed snapshotem `before`: jeśli `! brew_xcode_license_ok`:
   - TTY i `MAC_UPDATE_NONINTERACTIVE` ≠ 1: wypisz komunikat i18n `L_BREW_XCODE_LICENSE_PROMPT`, zapytaj `[T/n]`, przy zgodzie wykonaj `sudo xcodebuild -license accept`, ponów sprawdzenie; przy odmowie lub porażce → zapisz `unknown` do `pending_brew_formulae` i `pending_brew_casks` z powodem `xcode_license` (nowy plik `pending_brew_reason`) i zakończ krok kodem 10.
   - bez TTY: to samo bez pytania, komunikat zawiera dokładną komendę do wykonania ręcznie.
3. `update_appstore.sh`: po `mas_after.txt` porównaj wersję `Xcode` z `mas_before.txt`; przy zmianie zapisz `xcode_changed=<old>-><new>` w `$MAC_UPDATE_SESSION_DIR/xcode_changed.txt`. `update_brew.sh` dołącza tę informację do komunikatu o licencji.
4. `lib/python/run_summary.py::collect_run_items`: gdy `pending_brew_reason` = `xcode_license`, item `Step: Homebrew` dostaje `details: "Xcode license not accepted (Xcode <old>-><new>)"`.
5. Testy (`tests/test_xcode_license_gate.py`): atrapa `xcodebuild` zwracająca 69 → krok brew nie woła `brew update`, zapisuje `unknown` + powód, rc 10; atrapa zwracająca 0 → normalny przebieg; tryb nieinteraktywny nie woła `sudo`.
6. i18n: 3 nowe klucze × 7 języków.

### T2 — Krok macOS: uczciwy stan i polityka majora (P0-3)

Kontekst: `softwareupdate -l` zwrócił trzy etykiety (`Safari27.0TahoeAuto-27.0`, `macOS Tahoe 26.7-25G229`, `macOS 27-26A428`); użytkownik odmówił; krok zgłosił `OK completed`, `system_upgraded: 0`, bez `pending`.

1. `lib/python/system_updates.py` (nowy, czyste funkcje): `parse_softwareupdate_list(text) -> list[dict(label, title, version, size_kib, recommended, restart)]` oraz `classify_updates(items, current_version) -> dict(same_major=[...], major=[...], other=[...])`. Wersja `27` (bez kropki) ma major 27.
2. `update_system.sh`:
   - po `softwareupdate -l` zapisz surowy listing do `$MAC_UPDATE_SESSION_DIR/system_available.txt`, a liczbę etykiet do `pending_system` (`0` tylko przy `No new software available`; przy błędzie `softwareupdate -l` → `unknown`).
   - Domyślnie instaluj **tylko** `same_major` + `other` (Safari, XProtect itp.) przez `sudo softwareupdate -i "<label>" -R` dla każdej etykiety (pętla, jeden `sudo -v` na początku). Etykiety `major` pomijaj i raportuj `L_SYSTEM_MAJOR_AVAILABLE` z nazwą i wersją.
   - `MAC_UPDATE_ALLOW_MAJOR_UPGRADE=1` **i** TTY **i** osobne potwierdzenie `[T/n]` → wolno zainstalować etykietę majora (nadal `-R`). W trybie `MAC_UPDATE_NONINTERACTIVE=1` major nigdy.
   - Odmowa użytkownika: zamiast `exit 0` → zapisz `system_skipped_by_user` w sesji i zakończ kodem 10 tak, aby `update_all.sh` ustawił `RESULT_SYSTEM="$L_ALL_RESULT_SKIPPED_BY_USER"` (nowy klucz i18n), a nie `OK completed`.
   - Po udanej instalacji bez restartu ponów `softwareupdate -l` i zapisz `pending_system` ponownie (pomiar, nie założenie).
3. `update_all.sh`: nowy klucz w `counts`: `pending_after_run_system` (+ `verification`), obsługa kodu 10 z kroku systemowego jako `skipped_by_user`/`warn` bez degradacji reszty. `PENDING_FILES` w `run_summary.py` rozszerz o `("pending_after_run_system", "pending_system")`. Etykiety z `system_available.txt` trafiają do `items` jako `status: pending`, `category: system`, `name: <Title>`, `new_version: <Version>`.
4. Testy (`tests/test_system_step.py`): atrapa `softwareupdate` zwracająca dokładnie listing z 11:06 + atrapa `sw_vers` = `26.6.2`: (a) bez flagi — wywołane `-i` tylko dla Safari i 26.7, nigdy dla `macOS 27-26A428`; (b) z flagą i `MAC_UPDATE_YES=1` — major dozwolony; (c) odmowa → rc 10, `pending_system=3`, brak `OK`; (d) `-ia` nie występuje w żadnym wywołaniu instalacji; (e) każdy `-i` ma `-R` (test statyczny z `test_safety_static.py` musi nadal przechodzić — zaktualizuj go, jeśli sprawdza literalnie `-ia -R`).
5. `docs/agents/critical_rules.md`: sekcja „Major upgrades” + „softwareupdate labels bez nazwy kodowej od macOS 27”.

### T3 — Świadomość architektury i Rosetta (P0-2)

Kontekst: macOS 27 usuwa Rosettę przy upgrade i nie przywraca jej; Intel-only apps przestają działać w macOS 28. Na maszynie: `DJI Assistant 2(Consumer Drones Series).app` = `x86_64`.

1. `lib/python/inventory.py`: funkcja `app_architecture(app_path) -> "arm64"|"universal"|"x86_64-only"|"unknown"` na podstawie `lipo -archs` głównego wykonywalnego (`CFBundleExecutable`); bez wyjątków przy brakującym binarium. `build_inventory.sh` zapisuje wynik do nowej kolumny/markera w `APPLICATIONS.md` (zachowaj `norm_name()` — jedno źródło, nie kopiuj).
2. `lib/platform.sh`: `mac_update_rosetta_installed()` → 0 gdy `/usr/bin/pgrep -q oahd` **lub** `[ -d /Library/Apple/usr/share/rosetta ]`.
3. `update_internet_apps.sh` / `lib/internet_app_updates.sh`: dla aplikacji `x86_64-only` status w tabeli końcowej `⚠️ Intel-only: wymaga Rosetty` z dopiskiem `(niezainstalowana)` gdy brak, oraz `koniec wsparcia: macOS 28`. Nie zmieniaj metody aktualizacji aplikacji.
4. Opcjonalnie, **opt-in**: `MAC_UPDATE_INSTALL_ROSETTA=1` → jeśli istnieje ≥1 aplikacja `x86_64-only` i Rosetta nieobecna, wykonaj `softwareupdate --install-rosetta --agree-to-license` (bez `sudo`, bez `-R`), a potem **zmierz** ponownie `mac_update_rosetta_installed`. Domyślnie tylko informacja.
5. `scripts/report_update_coverage.sh`: kategoria „Intel-only (Rosetta, EOL macOS 28)” z liczbą aplikacji.
6. `run_summary.py`: item `status: pending`, `category: internet`, `details: "Intel-only; Rosetta missing; EOL macOS 28"` dla każdej takiej aplikacji.
7. Testy: atrapa `lipo` (`x86_64` / `arm64 x86_64` / `arm64`), atrapa `pgrep`; bez flagi `softwareupdate` nie jest wołane; z flagą wołane raz i wynik mierzony ponownie.
8. i18n: 3 klucze × 7.

### T4 — `mas account` i komunikaty „macOS 26.x” (P1-4)

1. `update_appstore.sh:161`: przed `mas account` sprawdź `mas version`; dla major ≥ 5 pomiń wywołanie i użyj bezpośrednio ścieżki `mas list`. Komunikat: „mas ≥ 5 nie udostępnia `account`; weryfikuję dostęp przez `mas list`”.
2. Zmień treść kluczy `L_APPSTORE_LOGIN_UNSTABLE`, `L_MSG_APPSTORE_MAS_LIMIT`, `L_MAS_VERSION_OLD`, `L_MSG_MAS_OLD`, `L_MSG_MAS_FIX` w 7 językach: przyczyna to wersja mas / zmiana installd na macOS 26.1+/15.7.2+/14.8.2+, nie „problem macOS 26.x”.
3. Test statyczny w `test_safety_static.py`: `mas account` występuje tylko wewnątrz bramki wersji; test behawioralny z atrapą `mas` zwracającą `Unexpected argument 'account'` → brak ostrzeżenia o macOS, krok kontynuuje.

### T5 — Diagnoza Command Line Tools (P1-5)

1. `lib/platform.sh`: `mac_update_clt_status()` → wypisuje `ok|missing|stale|orphan` na podstawie `pkgutil --pkg-info=com.apple.pkg.CLTools_Executables` (wersja vs major `sw_vers`) i istnienia `/Library/Developer/CommandLineTools`.
2. `setup.sh`, `migration_setup.sh` (faza zależności) i `update_brew.sh` (jedna linia `ℹ️` na przebieg): dla `stale|orphan` wypisz instrukcję Homebrew (`sudo rm -rf /Library/Developer/CommandLineTools && sudo xcode-select --install`) — **nie wykonuj**. Dla `missing` przy braku Xcode.app: `xcode-select --install` jak dotychczas.
3. `update_brew.sh`: jeśli logujesz `brew doctor`, zredukuj powtarzalne ostrzeżenie CLT do jednej linii (pełny tekst do `$MAC_UPDATE_SESSION_DIR/brew_doctor.txt`).
4. Testy z atrapą `pkgutil` i tymczasowym katalogiem.

### T6 — Wyrocznia casków dla `silent_launch` (P1-7)

1. `lib/brew.sh`: `brew_cask_latest_versions <token…>` — jedno `brew info --json=v2 --cask` (stdout tylko), zwraca `token<TAB>version`. Read-only; nie instaluje.
2. Mapowanie app → cask w `config/` (nie w kodzie): dla obecnych 12 pozycji ⏳ (ChatGPT, Claude, Gemini, Comet, Antigravity, Antigravity IDE, OpenCode Desktop, Proton Mail, Teams, Docker, Warp, Cursor). Brak casku = pozostaje ⏳.
3. Po settle w kroku internetowym: `app_vs_package_version_relation()` (już w `lib/version.sh`) porównuje wersję bundla z caskiem → status `✅ aktualna (cask)` / `⚠️ w tyle: X < Y` / `⏳`. Cask jest **wyrocznią**, nie kanałem instalacji — nie zmieniaj handlerów.
4. `counts.internet_verified`, `counts.internet_behind`, `counts.internet_unverified`; itemy `behind` jako `status: pending`.
5. Test z atrapą `brew` zwracającą JSON dla 3 tokenów (aktualna / w tyle / brak).

### T7 — Stabilne kody stanów kroków (P1-8)

1. `update_all.sh`: obok `RESULT_*` zapisuj `STATUS_CODE_*` ∈ `ok|warn|error|skipped|skipped_by_user|unconfirmed` do `$SESSION_DIR/step_status_codes.txt` (`step=code` per linia). Przekaż do heredoca podsumowania.
2. `run_summary.py`: `steps` w JSON staje się `{"brew": {"code": "warn", "text": "<i18n>"}}`; `format_version` → 4; `migrate_run_summary` mapuje v3 przez istniejące `classify_step_status` (zostaje jako fallback). Uaktualnij `find_chronic_streaks`/detektor, jeśli czyta `steps`.
3. Testy: JSON v3 → v4 migracja; nowy przebieg używa kodu z pliku, nie tokenów tekstowych.

### T8 — LaunchAgent zgodny z macOS 27 (P1-9)

1. `scripts/install_launchagent.sh`: przed załadowaniem `xattr -d com.apple.quarantine "$PLIST_PATH" 2>/dev/null || true`; zamiast `launchctl load -w` użyj `launchctl bootstrap gui/$(id -u) "$PLIST_PATH"` + `launchctl enable gui/$(id -u)/<label>`; odinstalowanie przez `bootout`. Zachowaj fallback na `load -w`, gdy `bootstrap` zwróci błąd „already loaded”.
2. README (7 języków, sekcja o trybie tygodniowym): jedno zdanie, że tryb nienadzorowany nie aktualizuje App Store (brak TTY → brak `sudo mas` i brak TOR 2).
3. Test z atrapami `launchctl` i `xattr` rejestrującymi argumenty.

### T9 — Dokumentacja i metadane (P2-10, P2-12)

- „macOS 13–26” → „macOS 13–27” w `README*.md` (7), `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `CODEX.md`; `migration_setup.sh:346` → `macOS ${MACOS_VERSION} Golden Gate` dla `-eq 27`, generyczne dla `-ge 28`.
- `docs/agents/critical_rules.md`: nowa sekcja „macOS 27” (licencja Xcode po aktualizacji z App Store, Rosetta nieprzywracana / EOL 28, CLT `minimum_version` 27.0.0 w Homebrew 7, `pkg` domyślnie arm64, launchd odrzuca quarantined plist, TCC.db niedostępne, TLS 1.2+/ATS dla procesów instalacji).
- `docs/agents/troubleshooting.md`: wpisy „brew: You have not agreed to the Xcode license”, „brew doctor: CLT does not support macOS 27 (Tier 2)”, „Intel app nie startuje po upgrade (Rosetta)”.
- `CHANGELOG.md`: wpis 1.4.6 w formie objaw → przyczyna → naprawa → pomiar. `VERSION` → `1.4.6`.

### T10 — Martwy deferral MAU (P2-11)

- `mau_quarantine_expired_ids` (lib/internet_app_updates.sh): jeśli `DeferralVersions.<ID>` == zainstalowana wersja produktu, ID jest wygasłe natychmiast (nie ukrywa już żadnej diagnostyki). Test z `MAC_UPDATE_MAU_PREFS_FILE` na tymczasowym pliście: Teams `26225.1706.5101.3140` deferred i zainstalowany → w zbiorze expired.

## Checklista odbioru (uruchom i wklej wyniki)

- [ ] `bash run_tests.sh` → `ALL CHECKS PASSED`, liczba testów > 291 (podaj), gitleaks czysto.
- [ ] `shellcheck -S warning update_*.sh lib/*.sh scripts/*.sh` → 0 znalezisk; `bash -n` na każdym zmienionym `.sh`.
- [ ] `for f in i18n/lang_*.sh; do grep -cE '^[A-Z_]+=' "$f"; done` → 7 identycznych liczb.
- [ ] `bash update_all.sh --dry-run` na tej maszynie kończy się bez błędu i pokazuje: brak ostrzeżenia „macOS 26.x” przy `mas`, linia `ℹ️` o CLT, status architektury DJI Assistant 2, brak `-ia` w wypisanych komendach `softwareupdate`.
- [ ] Test z listingiem `softwareupdate` z 2026-09-16 11:06: bez flagi → `macOS 27-26A428` **nie** jest instalowane; odmowa → `pending_after_run_system: 3`, `steps.system.code: skipped_by_user`.
- [ ] Atrapa `xcodebuild` rc 69 → krok brew: `pending_brew_formulae=unknown`, `pending_brew_reason=xcode_license`, rc 10, zero wywołań `brew update`.
- [ ] `python3 -c "import json;d=json.load(open('logs/run_summary_latest.json'));print(d['format_version'])"` po `--dry-run` → `4`; `migrate_run_summary` na `logs/run_summary_20260916_110633.json` zwraca `steps.brew.code == "warn"`.
- [ ] `git diff --stat main` nie zawiera `docs/reviews/*`, logów, `APPLICATIONS.md` z danymi maszyny ani żadnego `/Users/<login>`.
- [ ] `git log --oneline main..HEAD` — jeden commit na zadanie T0–T10, komunikaty w formie „fix|feat|docs: …”.
- [ ] Nie tagowano, nie pushowano, nie uruchamiano mutacji systemu. Na końcu wypisz, czego **nie** udało się zweryfikować bez uruchomienia prawdziwego przebiegu.

## Po zakończeniu

Napisz handoff (jedna wiadomość): co zrobiono per T, co pozostało, jakie decyzje wymagają użytkownika (CLT reinstall, Rosetta, LaunchAgent, tag v1.4.6). Nie zapisuj sekretów ani ścieżek prywatnych. Jeśli istnieje CLI `agentic`, wykonaj `agentic handoff "<treść>" -p macos-updates` i `agentic sync`.
