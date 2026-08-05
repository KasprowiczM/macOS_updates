# IMPLEMENTATION PROMPT — macOS_updates v1.0.21 → v1.1.0
> **Przeznaczenie:** wklej całość jako pojedynczy prompt do Claude Opus 4.6 (thinking) w sesji uruchomionej w katalogu `~/Dev_Env/macOS_updates`.
> **Wersja promptu:** 2026-08-05 · **Bazuje na:** `ULTRA_REVIEW_2026-08-05.md`

---

Jesteś doświadczonym inżynierem shell/macOS pracującym w repozytorium `~/Dev_Env/macOS_updates` (Bash 3.2+, Python 3, Apple Silicon only, macOS 13–26, 7 języków).

Przeczytaj **najpierw** te pliki, zanim cokolwiek zmienisz:
- `CLAUDE.md` — zasady nienaruszalne projektu
- `ULTRA_REVIEW_2026-08-05.md` — pełna analiza, z której pochodzi ten plan
- `docs/agents/architecture.md`, `docs/agents/critical_rules.md`, `docs/agents/exit_codes.md`
- `lib/internet_handlers.sh`, `lib/severity.sh`, `lib/ui.sh`, `lib/github_release.sh`
- `update_all.sh` (linie 120–330), `update_internet_apps.sh` (linie 440–670), `update_brew.sh` (linie 120–270)

## ZASADY NIENARUSZALNE (naruszenie = zadanie niewykonane)

1. **Bash 3.2** — zero `declare -A`, `mapfile`, `readarray`, `${var^^}`, `&>>`. Testuj mentalnie pod `/bin/bash` 3.2.57.
2. **`softwareupdate` ZAWSZE z `-R`.**
3. **`mas upgrade` ZAWSZE z `sudo`.**
4. **Zero hardcoded paths** — `SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"`; temp przez `mktemp -d "${TMPDIR:-/tmp}/mac_update_*.XXXXXX"`.
5. **Brak nowych samodzielnych entrypointów Pythona w pipeline** — Python zostaje w heredocach lub w czystych modułach pod `lib/python/`.
6. **Wszystkie `update_*.sh` mają `set -o pipefail`, żaden nie ma `set -e`.**
7. **Każdy nowy string użytkownika musi trafić do WSZYSTKICH 7 plików `i18n/lang_*.sh`** (`en, pl, de, es, fr, it, pt`) — nazwa zmiennej identyczna, tłumaczenie właściwe dla języka. Brak klucza w choćby jednym języku = zadanie niewykonane.
8. **Nie zmieniasz semantyki severity contract** (0 / 10 / 1) opisanego w `update_all.sh` ~linia 280–320. Statusy „launched unverified" nadal **nie** ustawiają hard failu i **nie** blokują kroku 6.
9. **Nie dotykasz `/etc/sudoers`** i nie wprowadzasz sudo bez hasła nigdzie w projekcie.
10. **Po każdej fazie uruchamiasz `bash run_tests.sh` i musi przejść na zielono.** Jeśli nie przechodzi — naprawiasz, zanim ruszysz dalej.

## PROTOKÓŁ PRACY

- Pracuj **fazami w podanej kolejności**. Nie zaczynaj fazy N+1 przed zielonym `run_tests.sh` w fazie N.
- Po każdej fazie zrób **osobny commit** z prefiksem `[FAZA N]` i opisem w treści.
- Prowadź plik `IMPLEMENTATION_LOG_2026-08-05.md` — po każdej fazie dopisz sekcję: co zrobiono, jakie pliki zmieniono (z numerami linii), wynik `run_tests.sh`, co zostało odłożone i dlaczego.
- Jeżeli którakolwiek instrukcja poniżej okaże się niewykonalna lub błędna po zderzeniu z kodem — **NIE improwizuj cicho**. Zatrzymaj się, opisz rozbieżność w logu i zapytaj.
- Nie refaktoryzuj rzeczy spoza zakresu. Zakres jest zamknięty listą poniżej.

---

# FAZA 1 — Bugfixy krytyczne (blokujące bezobsługowość)

## 1.1 — BUG-1: stdout pollution w `internet_handler_silent_launch`

**Problem:** `lib/internet_handlers.sh:10` — funkcja zwraca status przez `echo`, ale równocześnie drukuje UI przez `print_info`/`print_step`/`print_warn` na stdout. Wołana jest przez podstawienie komendy w `lib/internet_handlers.sh:106`, więc **cały UI trafia do zmiennej statusu**. Dotyczy 19 aplikacji (wszystkie wywołania `internet_dispatch_silent_launch` w `lib/internet_app_updates.sh`).

**Wymagana implementacja — wariant „zmienna globalna", NIE `>&2`:**

Przerób `internet_handler_silent_launch()` tak, aby:
- ustawiała globalną `INTERNET_LAST_STATUS` zamiast `echo`
- drukowała UI normalnie na stdout (bez przekierowań)
- nie zwracała nic na stdout

Analogicznie przerób **wszystkie** funkcje w `lib/internet_handlers.sh`, które dziś zwracają status przez `echo`:
- `internet_handler_silent_launch`
- `internet_handler_manual`
- `internet_handler_keystone`

Zaktualizuj `internet_dispatch_silent_launch()` (`lib/internet_handlers.sh:92`) tak, aby po wywołaniu handlera czytała `INTERNET_LAST_STATUS` i przekazywała ją do `internet_handler_set_status`.

Następnie **przeskanuj `lib/internet_app_updates.sh` (87 KB) w poszukiwaniu WSZYSTKICH miejsc**, które używają wzorca `VAR="$(jakas_funkcja ...)"` gdzie `jakas_funkcja` drukuje UI. Napraw każde znalezione. Wypisz w logu implementacji pełną listę znalezionych i naprawionych miejsc.

**Kryterium akceptacji:** żaden status w `config/internet_app_methods.txt` nie może po runie zawierać znaku nowej linii ani sekwencji ANSI.

## 1.2 — BUG-2: odblokowanie martwego settle-loopa

**Problem:** `update_internet_apps.sh:467–472` buduje listę `unverified_apps` porównując `$st` ze stałą `$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED`. Z powodu BUG-1 porównanie nigdy nie było prawdziwe, więc adaptacyjna pętla polling-until-stable nigdy się nie wykonała — kod zawsze wpadał w `else` z płaskim `sleep 15`.

**Po naprawie 1.1 ta pętla zacznie działać.** Twoje zadania:
1. **POTWIERDZONY DRUGI BUG — literówka w nazwie zmiennej.** Lista w linii 468 zawiera `STATUS_PROTON_MAIL` (z podkreśleniem), podczas gdy reszta projektu konsekwentnie używa `STATUS_PROTONMAIL`:
   - `lib/internet_app_updates.sh:416` ustawia `STATUS_PROTONMAIL`
   - `config/internet_app_methods.txt` deklaruje `STATUS_PROTONMAIL`
   - `printf` w podsumowaniu (`update_internet_apps.sh:555`) czyta `$STATUS_PROTONMAIL`
   - ale settle-list (468) i `case` (~483) używają `STATUS_PROTON_MAIL`

   Skutek: Proton Mail **nigdy** nie trafi do settle-loopa, nawet po naprawie 1.1. Napraw nazwę i **przeszukaj cały projekt pod kątem analogicznych literówek** w nazwach `STATUS_*` — porównaj zbiór nazw z `config/internet_app_methods.txt` ze zbiorem nazw faktycznie używanych w `update_internet_apps.sh` i `lib/internet_app_updates.sh`. Rozbieżności wypisz w logu.
2. Zamiast utrzymywać listę ręcznie, wygeneruj ją z `config/internet_app_methods.txt` (kolumna 3 dla wierszy z `silent_launch`). Lista w kodzie ma przestać istnieć.
3. Dodaj do pętli twardy limit czasu i log diagnostyczny: ile sekund faktycznie czekano i które aplikacje zmieniły wersję.

## 1.3 — BUG-3: sudo keep-alive

**Problem:** `update_all.sh:194` robi jednorazowe `sudo -v`. Domyślny `timestamp_timeout` to 5 minut. Zarejestrowane czasy runów: 52 min, 19 min, 14 min, 12 min. Krok 6 (`sudo softwareupdate -ia -R`) startuje na końcu → ponowny prompt w środku runu.

**Implementacja:**
- Tuż po istniejącym bloku `sudo -v` (`update_all.sh` ~194) uruchom proces potomny odświeżający timestamp co 50 s (`sudo -n true`), który sam się kończy, gdy odświeżenie się nie powiedzie.
- PID zapisz w `SUDO_KEEPALIVE_PID`.
- W `cleanup_session_dir()` (`update_all.sh` ~206) **bezwarunkowo** ubij ten proces — także na ścieżkach `INT`/`TERM`.
- Keep-alive uruchamiaj **tylko** gdy `[ -t 0 ]` i `MAC_UPDATE_SKIP_SYSTEM != 1`, i tylko gdy pierwsze `sudo -n true` się powiodło (czyli użytkownik faktycznie się uwierzytelnił).
- Dodaj zmienną `MAC_UPDATE_NO_SUDO_KEEPALIVE=1` wyłączającą mechanizm.

**Kryterium akceptacji:** po zakończeniu `update_all.sh` (także po Ctrl-C) `pgrep -f "sudo -n true"` nie zwraca osieroconych procesów.

## 1.4 — BUG-4: `sudo -v` z wyciszonym stderr

`update_all.sh:194` — usuń `2>/dev/null`. Stderr wycisz wyłącznie gdy `MAC_UPDATE_JSON_SUMMARY=1`. Komunikat błędu PAM musi być widoczny.

## 1.5 — Testy regresyjne

Dodaj do `tests/test_safety_static.py` w klasie `StaticShellSafetyTests`:

1. `test_internet_handlers_do_not_echo_status_in_command_substitution` — statyczna asercja, że `lib/internet_handlers.sh` nie zawiera wzorca `="$(internet_handler_`.
2. `test_internet_handlers_set_last_status_global` — każda funkcja `internet_handler_*` kończąca się ustawieniem statusu używa `INTERNET_LAST_STATUS`.
3. `test_update_all_has_sudo_keepalive` — `update_all.sh` zawiera keep-alive **i** jego kill w cleanupie.
4. `test_settle_list_generated_from_config` — `update_internet_apps.sh` nie zawiera już hardkodowanej listy 19 zmiennych `STATUS_*` w jednej linii.
5. `test_all_languages_have_same_keys` — **kluczowy test**: zbierz nazwy zmiennych `L_*` ze wszystkich 7 `i18n/lang_*.sh` i asertuj, że zbiory są identyczne. Ten test ma chronić przed regresją i18n we wszystkich kolejnych fazach.

**Bramka wyjścia z Fazy 1:**
```bash
bash run_tests.sh                                  # zielone
bash update_all.sh --dry-run -y                    # bez błędów
bash update_all.sh -y --skip-system                # ANI JEDNEGO promptu o hasło
```
W logu z ostatniego polecenia sprawdź, że sekcje aplikacji (Brave, Cursor, Obsidian, Spotify, ProtonVPN…) mają treść **pod swoim nagłówkiem**, a tabela podsumowania ma **dokładnie jedną linię na aplikację**.

---

# FAZA 2 — Migracja do Homebrew Cask (największy zysk w pokryciu)

**Kontekst:** dziś 24 z 45 aplikacji ma metodę `silent_launch` = zero weryfikacji wersji. `update_brew.sh` **już** używa `brew upgrade --cask --greedy` (linia 240) oraz `brew outdated --cask --greedy` (linie 130 i 260). **Nie musisz zmieniać kodu `update_brew.sh`** — migracja polega na przeniesieniu aplikacji pod zarząd Homebrew i aktualizacji configu.

## 2.1 — Audyt dostępności casków

Napisz `scripts/audit_cask_candidates.sh`, który:
- czyta `config/internet_app_methods.txt`, bierze wiersze z `silent_launch`
- dla każdej aplikacji sprawdza `brew info --cask <kandydat>` po liście kandydatów nazw (slug z nazwy aplikacji + ręczne aliasy)
- wypisuje tabelę: `Aplikacja | zainstalowana wersja | kandydat cask | istnieje? | wersja w cask | auto_updates? | version :latest?`
- ma tryb `--json`
- **niczego nie instaluje ani nie zmienia**

Aliasy do wpisania na start (zweryfikuj każdy przez `brew info --cask`, nie zakładaj):
`Brave Browser→brave-browser`, `Cursor→cursor`, `Obsidian→obsidian`, `LM Studio→lm-studio`, `ProtonVPN→protonvpn`, `Proton Mail→proton-mail`, `Proton Drive→proton-drive`, `MEGAsync→megasync`, `Warp→warp`, `AppCleaner→appcleaner`, `Spotify→spotify`, `CapCut→capcut`, `Claude→claude`, `zoom.us→zoom`, `Remote Desktop Manager→devolutions-remote-desktop-manager`, `Comet→comet`, `ChatGPT / Codex→chatgpt`.

Uruchom skrypt i **wklej pełny wynik do logu implementacji**. To on decyduje, co migrujesz — nie zgaduj.

## 2.2 — Migracja

Dla każdej aplikacji z potwierdzonym caskiem, **partiami po 5**:
```bash
brew install --cask --adopt <cask>
```
Po każdej partii: uruchom aplikację ręcznie i potwierdź, że działa (nie stracone ustawienia/licencje). Dopiero potem następna partia.

**Aplikacje do POMINIĘCIA w migracji** (uzasadnij w logu, jeśli decydujesz inaczej):
- `ChatGPT Atlas`, `Gemini`, `Antigravity`, `Antigravity IDE`, `Ascendo`, `OpenCode`, `Perplexity` — sprawdź, ale spodziewaj się braku casków lub niestabilnych
- Wszystko, co ma płatną licencję powiązaną ze ścieżką instalacji

## 2.3 — Aktualizacja configu

Dla każdej zmigrowanej aplikacji:
- `config/internet_app_methods.txt`: zmień `silent_launch` → `brew_cask`
- `config/internet_dispatch_order.txt`: **usuń** odpowiedni wpis `iu_*`
- `lib/internet_app_updates.sh`: usuń martwą funkcję `iu_*` (albo zostaw z komentarzem `# migrated to Homebrew cask YYYY-MM-DD` — wybierz jedno podejście i zastosuj konsekwentnie)
- `update_internet_apps.sh`: status ma pokazywać `→ managed by Homebrew (update_brew.sh)` — użyj istniejącego wzorca `STATUS_INKSCAPE`
- `APPLICATIONS.md`: przenieś aplikację z GRUPY 3 do sekcji 4c (Casks)

## 2.4 — Kontrola kosztu `--greedy`

Po migracji zmierz:
```bash
time brew outdated --cask --greedy
time brew outdated --cask --greedy-auto-updates
```
Jeśli `--greedy` jest wyraźnie wolniejszy **lub** powoduje reinstalację casków `version :latest` przy każdym runie:
- przełącz `update_brew.sh` linie 130, 240, 260 na `--greedy-auto-updates`
- dodaj osobną, **tygodniową** ścieżkę dla `version :latest` sterowaną zmienną `MAC_UPDATE_GREEDY_LATEST=1`
- udokumentuj decyzję w `docs/agents/critical_rules.md`

Jeśli różnica jest pomijalna — zostaw `--greedy` i **zapisz w logu, że sprawdziłeś, z liczbami**.

**Bramka wyjścia z Fazy 2:**
- `bash scripts/report_update_coverage.sh` pokazuje liczbę `silent_launch` **spadłą co najmniej o 10**
- `bash run_tests.sh` zielone
- pełny run `bash update_all.sh -y` bez regresji
- każda zmigrowana aplikacja uruchomiona ręcznie i potwierdzona jako sprawna

---

# FAZA 3 — Prawdziwa weryfikacja wersji (Sparkle + Electron)

## 3.1 — Skaner feedów

Napisz `scripts/scan_update_feeds.sh` (read-only), który dla każdej `.app` w `/Applications` i `~/Applications` wypisuje:
- `SUFeedURL` z `Contents/Info.plist` (Sparkle)
- obecność i zawartość `Contents/Resources/app-update.yml` (electron-updater)
- `KSUpdateURL` (Google Keystone)
- wykryty framework: `sparkle` / `electron` / `keystone` / `none`

Tryb `--json`. Uruchom i wklej wynik do logu — to wejście dla 3.2.

## 3.2 — Metoda `sparkle_appcast`

Dodaj do `lib/internet_handlers.sh` funkcję `internet_handler_sparkle_check()`:
- czyta `SUFeedURL` z `Info.plist`
- `curl -fsSL --max-time 15 --retry 2` po appcast
- parsuje **najwyższą** wersję z `sparkle:shortVersionString`, a gdy jej brak — z `<title>`; fallback na `sparkle:version`
- porównuje z `app_version` używając **istniejącej** logiki porównywania wersji z projektu (znajdź ją; jeśli nie ma — napisz `internet_version_compare()` w `lib/version.sh` obsługującą schematy `1.2.3`, `1.2.3.4`, `2026.7.4`, `0.2026.07.29.09.05.02`)
- ustawia `INTERNET_LAST_STATUS` na jeden z: `L_INTERNET_STATUS_CURRENT_FMT` (równe), nowy `L_INTERNET_STATUS_UPDATE_AVAILABLE_FMT` (dostępna nowsza), `L_INTERNET_STATUS_OFFLINE` (brak sieci), `L_INTERNET_STATUS_UNKNOWN_VERSION` (nie da się sparsować)
- **nigdy nie instaluje** — sam raportuje. Instalacja pozostaje w gestii updatera aplikacji.

Nowe klucze i18n do dodania **we wszystkich 7 językach**:
- `L_INTERNET_STATUS_UPDATE_AVAILABLE_FMT` — np. EN `"⚠️  Update available: %s → %s"`, PL `"⚠️  Dostępna aktualizacja: %s → %s"`
- `L_INTERNET_SPARKLE_FEED_FOUND` / `L_INTERNET_SPARKLE_FEED_MISSING`

Zarejestruj metodę `sparkle_appcast` w `config/internet_app_methods.txt` i w `METHOD_LABELS` w `scripts/report_update_coverage.sh` (**wszystkie 7 sekcji językowych** w tym pliku).

## 3.3 — Wdrożenie na aplikacjach

Na podstawie wyniku 3.1 przełącz na `sparkle_appcast` każdą pozostałą aplikację `silent_launch`, która ma `SUFeedURL`. Zachowaj `silent_launch` jako **akcję** (nadal odpalasz updater), ale **dodaj weryfikację** — status ma pochodzić z appcastu, nie z faktu uruchomienia.

## 3.4 — Historia wersji

Zaimplementuj trwałą historię, żeby „⏳ uruchomiony" zamienić w sygnał:
- po kroku 4 dopisz do `logs/version_history.tsv` (TSV: `timestamp`, `app`, `version`, `method`) zawartość `internet_after.txt`
- plik chroniony `chmod 600`, rotacja jak logi (`MAC_UPDATE_MAX_LOGS`), gitignore
- w podsumowaniu kroku 4 dla aplikacji bez bezpośredniej weryfikacji dopisz `· bez zmiany od N dni`
- gdy `N > MAC_UPDATE_STALE_DAYS` (domyślnie 45) → `SOFT_FAIL=1` (**nigdy** hard fail — nie wolno zablokować kroku 6)

Nowe klucze i18n (7 języków): `L_INTERNET_UNCHANGED_DAYS_FMT`, `L_INTERNET_STALE_WARNING_FMT`.

**Bramka wyjścia z Fazy 3:**
- `report_update_coverage.sh` pokazuje `silent_launch` **≤ 8**
- co najmniej 5 aplikacji raportuje realną, sprawdzoną wersję zdalną
- `logs/version_history.tsv` powstaje i rośnie między runami
- `bash run_tests.sh` zielone, w tym test równości kluczy i18n

---

# FAZA 4 — Automatyzacja i harmonogram

## 4.1 — Touch ID w onboardingu

`scripts/setup_touchid_sudo.sh` **już istnieje** (napisany w ramach review). Twoje zadania:
- przeczytaj go, zweryfikuj poprawność i zgodność z zasadami projektu
- podepnij do `install.sh` jako krok opcjonalny z pytaniem (respektuj `MAC_UPDATE_YES`)
- dodaj wywołanie `--check` na starcie `update_all.sh`: jeśli Touch ID nie jest skonfigurowany, a terminal jest interaktywny → **jednorazowa** podpowiedź `print_info` (nie warn, nie blokada)
- opisz w `README.md` i `README.pl.md` w sekcji instalacji
- dodaj `docs/agents/troubleshooting.md` → sekcja „Touch ID pyta o hasło" z tabelą objaw/przyczyna/fix z §2 review

## 4.2 — LaunchAgent

Dodaj `scripts/install_launchagent.sh`:
- generuje `~/Library/LaunchAgents/com.<user>.macos-updates.plist` (label z `id -un`, **nie** hardkoduj `mk`)
- `ProgramArguments`: `/bin/bash <SCRIPT_DIR>/update_all.sh -y --skip-system`
- `StartCalendarInterval`: konfigurowalny, domyślnie poniedziałek 09:00
- `StandardOutPath`/`StandardErrorPath` → `logs/launchd.out` / `logs/launchd.err`
- flagi: `--uninstall`, `--check`, `--day N`, `--hour N`

**`--skip-system` jest obowiązkowe i musi być udokumentowane:** krok 6 wymaga na Apple Silicon poświadczeń volume owner, więc w tle tylko by zawisł. macOS zostaje na ręcznym runie z Touch ID.

Dodaj `MAC_UPDATE_NONINTERACTIVE=1`, które: wymusza `MAC_UPDATE_YES=1`, pomija keep-alive sudo, pomija wszystko, co potrzebuje TTY lub Accessibility (Tor 2 App Store GUI).

## 4.3 — Powiadomienie o wyniku

Po runie z launchd wyślij natywne powiadomienie macOS z podsumowaniem (liczba aktualizacji, status, ostrzeżenia). Użyj `osascript -e 'display notification ...'`. Sterowane `MAC_UPDATE_NOTIFY=1` (domyślnie ON dla launchd, OFF dla runu interaktywnego).

**Bramka wyjścia z Fazy 4:**
- `bash scripts/install_launchagent.sh --check` raportuje poprawny stan
- `launchctl list | grep macos-updates` pokazuje zarejestrowany agent
- ręczny `launchctl start` wykonuje pełny run bez interakcji, `logs/launchd.out` zawiera sensowne podsumowanie
- `scripts/setup_touchid_sudo.sh --check` przechodzi na tym Macu

---

# FAZA 5 — Redukcja długu (config-driven, wzorzec Installomatora)

**Cel:** `lib/internet_app_updates.sh` ma dziś **87 KB** i ~45 niemal identycznych funkcji `iu_*`. To główny dług projektu.

## 5.1 — Rozszerz format configu

Rozszerz `config/internet_app_methods.txt` (albo wprowadź `config/internet_apps.tsv`, jeśli uznasz to za czystsze — **udokumentuj wybór**) o kolumny:
```
AppName | method | STATUS_VAR | app_path | feed_url | version_regex | team_id | verify_hint | download_url
```
Zachowaj wsteczną zgodność: wiersze 3-kolumnowe muszą nadal działać (walidacja w `lib/internet_registry.sh:20–40` już odrzuca >3 pól — rozszerz ją, nie łam).

## 5.2 — Handlery generyczne

Zredukuj `lib/internet_app_updates.sh` do zestawu **generycznych** handlerów sterowanych configiem:
`keystone`, `github_dmg`, `sparkle_appcast`, `electron_feed`, `silent_launch`, `msupdate`, `docker_cli`, `brew_cask`, `appstore_gui`, `manual`.

Funkcje `iu_*` per aplikacja mają zniknąć wszędzie tam, gdzie nie robią nic ponad to, co daje generyk. Zostawiasz **wyłącznie** te z prawdziwą, nieredukowalną logiką (np. Microsoft 365 z obsługą deferrali, Teams z fallbackiem MAU, Firefox Dev z kanałem beta) — i uzasadniasz każdą w logu.

**Cel liczbowy: `lib/internet_app_updates.sh` poniżej 25 KB.**

## 5.3 — Aktualizacja scaffoldu

`scripts/scaffold_internet_app.sh` ma po tej zmianie generować **wpis w configu**, a nie funkcję shellową. Zaktualizuj też `docs/agents/scripts.md` → sekcja „adding internet apps".

## 5.4 — Auto-mapowanie (à la Patchomator)

Rozszerz krok 0 (`prescan`): nowo wykryta aplikacja w `/Applications` ma być automatycznie zmapowana na metodę na podstawie `scripts/scan_update_feeds.sh` (jest Sparkle → `sparkle_appcast`; jest cask → `brew_cask`; nic → `manual` + wpis do „do skategoryzowania" w `APPLICATIONS.md`). Propozycja ma być **wypisana użytkownikowi, nie zapisana automatycznie** do configu.

**Bramka wyjścia z Fazy 5:**
- `lib/internet_app_updates.sh` < 25 KB
- `bash run_tests.sh` zielone
- pełny run `update_all.sh -y` daje **identyczny zestaw statusów** jak przed refaktorem (porównaj z zapisanym logiem z Fazy 3 — to jest test regresji)

---

# FAZA 6 — Domknięcie

## 6.1 — Wersja i changelog
- `VERSION` → `1.1.0`
- `CHANGELOG.md` → nowa sekcja `## [1.1.0] — <data>` w stylu istniejących wpisów (Keep a Changelog), z podziałem `### Fixed` / `### Added` / `### Changed`, opisująca **każdą** fazę
- `CLAUDE.md` → zaktualizuj numer wersji w nagłówku

## 6.2 — Dokumentacja
- `README.md` **oraz wszystkie 6 tłumaczeń** (`de/es/fr/it/pl/pt`) — nowe skrypty, nowe zmienne środowiskowe, Touch ID, LaunchAgent
- `docs/agents/scripts.md` — nowe skrypty w `scripts/`
- `docs/agents/architecture.md` — nowy kontrakt `INTERNET_LAST_STATUS`, format configu
- `docs/agents/critical_rules.md` — reguła: „handlery NIGDY nie zwracają statusu przez stdout"; decyzja o `--greedy` z Fazy 2.4
- `docs/agents/troubleshooting.md` — Touch ID, keep-alive, launchd

## 6.3 — Pełna lista nowych zmiennych środowiskowych

Udokumentuj w `README.md` i `lib/cli.sh` (usage) **komplet** wprowadzonych zmiennych:
`MAC_UPDATE_NO_SUDO_KEEPALIVE`, `MAC_UPDATE_NONINTERACTIVE`, `MAC_UPDATE_NOTIFY`, `MAC_UPDATE_STALE_DAYS`, `MAC_UPDATE_GREEDY_LATEST`.
Dodaj odpowiadające im flagi CLI w `mac_update_parse_cli()` (`lib/cli.sh:30`) tam, gdzie ma to sens.

## 6.4 — Weryfikacja końcowa

Wykonaj i **wklej pełne wyniki do logu implementacji**:
```bash
bash run_tests.sh
bash -n update_all.sh && bash -n update_internet_apps.sh && bash -n update_brew.sh
shellcheck -S warning *.sh lib/*.sh scripts/*.sh    # jeśli dostępny
bash update_all.sh --dry-run -y
bash scripts/report_update_coverage.sh
bash scripts/setup_touchid_sudo.sh --check
bash scripts/install_launchagent.sh --check
bash update_all.sh -y --skip-system                 # pełny run
```

---

# RAPORT KOŃCOWY — wymagany format

Na koniec utwórz `IMPLEMENTATION_REPORT_2026-08-05.md` zawierający:

1. **Tabela zgodności z review** — wiersz na każdy punkt: `BUG-1 (stdout pollution), BUG-1b (STATUS_PROTON_MAIL), BUG-2 (settle-loop), BUG-3 (sudo keepalive), BUG-4 (sudo -v stderr), Faza 2, Faza 3, Faza 4, Faza 5, Faza 6`, kolumny: `Status (✅ zrobione / ⚠️ częściowo / ❌ nie) | Pliki i linie | Dowód (komenda + wynik) | Uwagi`.
2. **Metryki przed/po**, wypełnione **faktycznymi** liczbami:
   - liczba metod `silent_launch` w `config/internet_app_methods.txt`: przed **24** → po ?
   - rozmiar `lib/internet_app_updates.sh`: przed **87 371 B** → po ?
   - liczba interaktywnych promptów w pełnym runie: przed **2× `[T/n]` + sudo** → po ?
   - czas trwania kroku 4: przed **1 min 19 s** → po ?
   - liczba aplikacji z **potwierdzoną wersją zdalną** (linia `remote:` w logu): przed **6** (CodeEdit, Firefox Dev, KeePassXC, Ledger, Trezor, VS Code) → po ?
   - liczba aplikacji ze statusem `⏳ Launched (unverified)`: przed **24** → po ?
3. **Lista wszystkich zmienionych plików** z krótkim opisem zmiany.
4. **Lista nowych kluczy i18n** z potwierdzeniem obecności we wszystkich 7 językach.
5. **Świadomie pominięte / odłożone** — z uzasadnieniem. Puste „nie zdążyłem" jest niedopuszczalne; jeśli czegoś nie zrobiłeś, napisz dlaczego i co blokuje.
6. **Znane ograniczenia** — w szczególności potwierdzenie, że aktualizacja macOS na Apple Silicon nadal wymaga interakcji (volume owner) i że to jest oczekiwane, nie bug.

---

# CZEGO NIE ROBIĆ

- ❌ Nie dodawaj `set -e` do żadnego orkiestratora.
- ❌ Nie zmieniaj kolejności kroków w `update_all.sh`.
- ❌ Nie sprawiaj, żeby statusy „unverified" blokowały krok 6.
- ❌ Nie usuwaj weryfikacji podpisu / Team ID z `copy_verified_app()` ani `verify_replacement_identity()`.
- ❌ Nie wprowadzaj zależności od `jq`, `gh`, `yq` ani innych narzędzi spoza obecnego zestawu bez wyraźnego uzasadnienia i fallbacku.
- ❌ Nie commituj niczego z `logs/`, `dev_sync_logs/`, `.mac_update_prefs`.
- ❌ Nie zmieniaj `dev_sync/` — jest poza zakresem.
- ❌ Nie dodawaj kluczy i18n tylko do `en` i `pl`. **Wszystkie 7 albo żaden.**

Zacznij od przeczytania wskazanych plików i przedstawienia mi planu Fazy 1 do zatwierdzenia. Nie pisz kodu, zanim nie potwierdzę planu.
