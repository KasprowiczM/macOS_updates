# Aktualizacje macOS

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

**Strona:** [macosupdates.dev](https://macosupdates.dev) · **Repozytorium:** [github.com/KasprowiczM/macOS_updates](https://github.com/KasprowiczM/macOS_updates) · **Licencja:** [MIT](LICENSE) · **Zmiany:** [CHANGELOG.md](CHANGELOG.md)

> **v1.5.5** — Gotowy do użycia na produkcji jedno-komendowy orkiestrator aktualizacji dla **Maców z Apple Silicon i macOS 13–27**. Koordynuje zweryfikowane aktualizacje pakietów oraz uczciwe wywoływanie updaterów dla **oprogramowania już zainstalowanego na tym Macu**. **Wielojęzyczny** (7 języków). Opcjonalna prywatna nakładka przez [`dev_sync/`](dev_sync/README.md).

| W skrócie | |
|-----------|--|
| Platforma | wyłącznie Apple Silicon (arm64) · macOS 13 Ventura do macOS 27 · Bash 3.2 + Python 3 |
| Potok | 7 kroków (0–6), aktualizacja systemu macOS zawsze na końcu |
| Rejestr | 43 aplikacje internetowe · 11 metod aktualizacji (zob. [Metody aktualizacji](#metody-aktualizacji)) |
| Języki | EN, PL, ES, FR, DE, IT, PT (CLI i dokumentacja) |
| Testy | 561 testów automatycznych (`bash run_tests.sh`) |

**Nowość w v1.5.5:** Aktualizacja Homebrew usuwająca `python3` w trakcie przebiegu nie psuje już kroku inwentarza/raportu (powłoka ponownie przeszukuje `PATH`), a nieudany krok raportujący nie odkłada już aktualizacji macOS. Komunikaty końcowe są uczciwe: brak twierdzenia o zaktualizowanych plikach po błędzie, a ostrzeżenia o starym feedzie lub niezamkniętej aplikacji nie są już opisywane jako niezweryfikowane aktualizacje. Aplikacje uruchomione przez narzędzie dostają wielokrotną prośbę o zamknięcie (bez wymuszania). Wcześniejsze wydania 1.5.x (stary feed producenta jako ostrzeżenie, pobieranie ChatGPT/Proton od producenta, natywne CLI przed npm, ochrona podmiany pakietów) opisuje [CHANGELOG.md](CHANGELOG.md).

**Prawda od producenta (od v1.5.0):** wersja każdej aplikacji jest porównywana z feedem jej producenta, zanim cokolwiek zostanie uruchomione. Aktualne aplikacje zostają nietknięte; nieaktualne aktualizuje ich własny updater albo instalacja od producenta z weryfikacją podpisu i Team ID. Aktualizowane jest wyłącznie to, co jest zainstalowane (`--bootstrap-cli` celowo instaluje brakujące CLI). Aplikacje usunięte ręcznie są rozpoznawane i nigdy nie wracają. **Aplikacje, które masz otwarte, nigdy nie są zamykane. Skrypt zamyka tylko to, co sam uruchomił.** Stan producentów sprawdzisz bez zmian w systemie: `bash scripts/check_vendor_feeds.sh`.

---

## Instalacja jedną komendą (nowi użytkownicy)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

Instalator klonuje repozytorium, pyta o **język** (angielskie menu, 7 wersji językowych), instaluje zależności, buduje **Twój** plik `APPLICATIONS.md` na podstawie aplikacji obecnych na tym Macu i wyświetla, które programy można aktualizować. Nigdy nie importuje cudzego inwentarza i nie instaluje aplikacji za Ciebie.

Zobacz [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md)

---

## Co robi ten system

`update_all.sh` wykonuje siedem kroków:

| Krok | Działanie |
|------|-----------|
| 0 | **Prescan** — wykryj zainstalowane aplikacje → zaktualizuj `APPLICATIONS.md` |
| 1 | **App Store** — Tor 1: `sudo mas upgrade <app-id>`; Tor 2: AppleScript GUI dla aplikacji iPad |
| 2 | **Natywne CLI + npm** — najpierw istniejące natywne CLI, potem Node, Bun i globalne pakiety npm CLI |
| 3 | **Homebrew** — formulae i caski (`brew_cask` + ochrona przed downgrade'em) + cleanup i doctor |
| 4 | **Aplikacje z Internetu** — zweryfikowane handlery, `sparkle_appcast`, CLI producentów i uczciwe wywołania updaterów |
| 5 | **Postupdate/historia** — odśwież `APPLICATIONS.md`, dopisz atomowo do `UPDATES.md` |
| 6 | **macOS (końcowy)** — per-etykieta `softwareupdate -i <label> -R` (etykiety wymagające restartu w końcowym pakiecie); odraczany po blokującym błędzie twardym w krokach 1–4 lub przy braku autoryzacji |

**Ważne:** Aktualizacje dotyczą wyłącznie oprogramowania już zainstalowanego na Twoim Macu. Zgłaszane są braki obsługiwanych aplikacji, ale nie są one instalowane. Końcowy krok macOS może uruchomić komputer ponownie, dlatego działa ostatni i zawsze zachowuje wymagane `-R`. Krok 5 służy tylko do raportowania: jego awaria jest błędem, ale nigdy nie odkłada kroku macOS. Nieznane zainstalowane aplikacje są wypisywane, aby Ty (lub agent AI) mógł dodać handlery.

Raport pokrycia rozróżnia: **verified direct** — skrypt potwierdził ścieżkę pakietu/wersji; **triggered-unverified** — uruchomił aplikację, lecz nie może potwierdzić zakończenia aktualizacji producenta; **externally managed** — cyklem zarządza producent lub App Store; **manual** — potrzebna jest akcja użytkownika; **unknown** — brak zarejestrowanej metody.

```bash
bash scripts/report_update_coverage.sh   # raport pokrycia aplikacji
bash build_inventory.sh                  # przebudowa APPLICATIONS.md z tego Maca
```

### Metody aktualizacji

Rejestr ([`config/internet_apps.txt`](config/internet_apps.txt), [`config/internet_app_methods.txt`](config/internet_app_methods.txt)) przypisuje 43 aplikacje do 11 metod:

| Metoda | Aplikacje | Pokrycie | Jak aktualizuje |
|--------|----------:|----------|-----------------|
| `brew_cask` | 11 | externally managed | Cask Homebrew (greedy tylko dla tych tokenów) z ochroną przed cofnięciem wersji, np. Brave, Obsidian, Spotify, Inkscape |
| `silent_launch` | 9 | triggered-unverified | Własny updater aplikacji; oportunistyczne sprawdzenie feedu Sparkle / electron-updater, w przeciwnym razie „uruchomiono (niezweryfikowane)”. Nigdy nie podmienia samej aplikacji |
| `github_dmg` | 6 | verified direct | DMG od producenta/z GitHuba z weryfikacją podpisu i Team ID, podmiana etapowa z rollbackiem (Firefox Developer Edition, KeePassXC, VS Code, CodeEdit, Ledger Live, Trezor Suite) |
| `msupdate` | 5 | verified direct | Microsoft AutoUpdate (`msupdate`): Word, Excel, PowerPoint, Outlook, OneNote |
| `keystone` | 3 | verified direct | Updater Google (Omaha) weryfikowany historią aktualizacji: Chrome, Gemini, Google Drive |
| `appstore_gui` | 3 | externally managed | App Store Tor 2 (AppleScript): UniFi, WiFiman, Picsart |
| `sparkle_appcast` | 1 | verified direct | Appcast Sparkle (Proton Drive) |
| `chromium_updater` | 1 | verified direct | Dowód z updatera opartego na Chromium (Comet) |
| `docker_cli` | 1 | verified direct | Docker Desktop: zweryfikowany DMG z appcastu, gdy aplikacja nie pracuje; zapasowo `docker desktop update` |
| `mau_fallback_self_update` | 1 | triggered-unverified | Własny updater Teams plus obserwowany, weryfikowany fallback MAU `TEAMS21`, gdy Microsoft go oferuje |
| `manual` | 2 | manual | IPMIView i DJI Assistant 2 — tylko powiadomienie |

---

## Flagi wiersza poleceń

Autorytatywną listę definiuje `lib/cli.sh`; `bash update_all.sh --help` ją wyświetla.

| Flaga | Działanie |
|-------|-----------|
| `-y`, `--yes` | Pomija pytanie o potwierdzenie |
| `-h`, `--help` | Wyświetla pomoc i wychodzi z kodem `0` |
| `--dry-run` | Podgląd każdego kroku, bez wprowadzania zmian, bez pytań o poświadczenia |
| `--verify-only` | Weryfikuje wersje zainstalowanych aplikacji względem historii bez modyfikacji |
| `--json-summary` | Wypisuje obiekt JSON z podsumowaniem na stdout po zakończeniu |
| `--bootstrap-cli` | Celowo instaluje brakujące narzędzia CLI (domyślnie aktualizowane są tylko zainstalowane) |
| `--non-interactive` | Tryb nieinteraktywny dla launchd / cron (wymusza również `-y`) |
| `--notify` | Wysyła powiadomienie systemowe macOS po zakończeniu |
| `--treat-appstore-ax-as-warning` | Traktuje wyjście App Store `2` (brak uprawnień Dostępności) jako ostrzeżenie |
| `--skip-prescan` | Pomija krok 0 (prescan `APPLICATIONS.md`) |
| `--skip-appstore` | Pomija krok 1 (App Store) |
| `--skip-npm` | Pomija krok 2 (natywne CLI + npm) |
| `--skip-brew` | Pomija krok 3 (Homebrew) |
| `--skip-internet` | Pomija krok 4 (aplikacje internetowe) |
| `--skip-postupdate` | Pomija krok 5 (historia `APPLICATIONS.md` / `UPDATES.md`) |
| `--skip-system` | Pomija krok 6 (aktualizacja systemu macOS) |
| `--skip-doctor` | Pomija `brew doctor` w `update_brew.sh` |

Nieznana opcja `-…` kończy działanie kodem `2` po wypisaniu pomocy.

## Zmienne środowiskowe

Każda flaga ma odpowiednik w postaci zmiennej (`MAC_UPDATE_DRY_RUN=1`, `MAC_UPDATE_SKIP_SYSTEM=1`, …); poniżej najczęściej używane zmienne bez osobnej flagi. Pełna lista z wartościami domyślnymi: [docs/agents/scripts.md](docs/agents/scripts.md#environment-variables).

| Zmienna | Wartość domyślna | Znaczenie |
|---------|------------------|-----------|
| `MAC_UPDATE_NONINTERACTIVE` | `0` | Brak zapytań; pomija automatyzację GUI App Store Tor 2 |
| `MAC_UPDATE_NOTIFY` | `0` | Powiadomienie na biurku po zakończeniu (włączane też w trybie nieinteraktywnym) |
| `MAC_UPDATE_NO_SUDO` | *ustawiane automatycznie* | Eksportowane przez `update_all.sh` przy braku TTY; skrypty podrzędne pomijają kroki roota zamiast kończyć się błędem |
| `MAC_UPDATE_NO_SUDO_KEEPALIVE` | `0` | Ustawienie na `1` wyłącza odświeżanie znacznika czasu `sudo` w tle |
| `MAC_UPDATE_STALE_DAYS` | `45` | Liczba dni, po których niezweryfikowana aplikacja jest oznaczana jako przestarzała |
| `MAC_UPDATE_MAX_LOGS` | `30` | Liczba zachowywanych logów w `logs/` |
| `MAC_UPDATE_INTERNET_SETTLE_SECONDS` | `15` | Pauza pozwalająca uruchomionemu updaterowi przepisać `Info.plist` (`0` wyłącza, limit 120; pomijana, gdy nie uruchomiono żadnej aplikacji) |
| `MAC_UPDATE_QUIT_WAIT` | `60` | Sekundy (0–300), jakie aplikacja uruchomiona przez narzędzie ma na zamknięcie po łagodnym `quit`; nigdy nie jest zabijana siłą (v1.5.5) |
| `MAC_UPDATE_QUIT_RESEND` | `10` | Sekundy (1–60) między kolejnymi łagodnymi prośbami `quit` w oknie oczekiwania (v1.5.5) |
| `MAC_UPDATE_MAS_CHECK_TIMEOUT` | `120` | Limit czasu dla `mas outdated` |
| `MAC_UPDATE_MAS_UPGRADE_TIMEOUT` | `1800` | Limit czasu dla `sudo mas upgrade` |
| `MAC_UPDATE_MAU_DEFERRAL_DAYS` | `7` | Okno kwarantanny Microsoft AutoUpdate (ograniczone do zakresu Microsoftu 1–28) |
| `MAC_UPDATE_MAU_CLEAR_DEFERRALS` | `0` | Ustawienie na `1` usuwa blokujące klucze odroczeń MAU przez `defaults delete` |
| `MAC_UPDATE_MAU_KEEP_DEFERRALS` | `0` | Ustawienie na `1` sprawia, że zestaw narzędzi nigdy nie modyfikuje preferencji MAU |
| `MAC_UPDATE_LANG` / `MAC_LANG` | z `.mac_update_prefs` | Język interfejsu (`en pl es it pt de fr`) |

## sudo i Touch ID — kontrakt

Przepisany w v1.3.1 / v1.4.0. `update_all.sh` ma **dokładnie jedno** miejsce wywołania
interaktywnego `sudo`, obwarowane trzema warunkami:

1. **Najwyżej raz na uruchomienie.** Pojedyncze `sudo -v` przed przekierowaniem
   logu, potem proces w tle odświeża znacznik co 50 s, więc długi run nigdy nie
   pyta drugi raz. Keep-alive startuje najwyżej raz i jest ubijany przez pułapkę
   sprzątającą na każdej ścieżce wyjścia, łącznie z `INT`/`TERM` — nie może już
   zostać osierocony.
2. **Nigdy bez terminala sterującego.** Jeśli `stdin` nie jest terminalem — task
   runner IDE, powłoka agenta, launchd, cron — skrypt **nie** wywołuje `sudo -v`.
   Gołe `sudo -v` bez TTY eskaluje do graficznego okna askpass / Touch ID; to był
   powód, dla którego każda komenda uruchamiana z IDE wyglądała na wymagającą
   podniesienia uprawnień. Zamiast tego eksportowana jest zmienna
   `MAC_UPDATE_NO_SUDO=1`, a kroki wymagające roota są pomijane i raportowane
   miękko.
3. **Nigdy przy `--dry-run`.** Podgląd nie prosi o poświadczenia.

`sudo` nie jest w ogóle wywoływane, gdy nie uruchamia się ani krok 1 (App Store), ani
krok 6 (macOS), np. `bash update_all.sh --skip-appstore --skip-system`.

Jeżeli `sudo` nadal pyta o hasło zamiast o palec, sprawdź
[docs/agents/troubleshooting.md](docs/agents/troubleshooting.md) — sekcja Touch ID.

---

## Konfiguracja per-maszyna (**nie** przychodzi z `git pull`)

Dwie rzeczy żyją poza repozytorium i dlatego trzeba je ustawić raz **na każdym
Macu**. Sklonowanie albo pobranie repo na drugiej maszynie ich nie przeniesie —
to najczęstsze źródło nieporozumień w tym projekcie.

| Krok | Komenda | Dlaczego nie może być w gicie |
|------|---------|-------------------------------|
| Touch ID dla `sudo` | `bash scripts/setup_touchid_sudo.sh` | Zapisuje `/etc/pam.d/sudo_local` — plik należący do roota, lokalny dla maszyny, poza repozytorium |
| Cotygodniowy run w tle | `bash scripts/install_launchagent.sh --day 1 --hour 9` | Zapisuje `~/Library/LaunchAgents/com.<user>.macos-updates.plist` — per-użytkownik, per-maszyna |

```bash
bash scripts/setup_touchid_sudo.sh --check      # tylko raport, nic nie zapisuje
bash scripts/setup_touchid_sudo.sh              # instalacja / naprawa
bash scripts/setup_touchid_sudo.sh --uninstall

bash scripts/install_launchagent.sh --check
bash scripts/install_launchagent.sh --uninstall
```

`setup_touchid_sudo.sh` nigdy nie dotyka `/etc/sudoers` i nigdy nie nadaje `sudo`
bez hasła. Na macOS 14+ używa `/etc/pam.d/sudo_local`, który przeżywa
aktualizacje systemu; na macOS 13 patchuje `/etc/pam.d/sudo`, który aktualizacje
macOS nadpisują — uruchom skrypt ponownie po dużej aktualizacji.

### Co run w tle robi, a czego nie robi

LaunchAgent uruchamia `update_all.sh -y --skip-system` ze zmiennymi
`MAC_UPDATE_NONINTERACTIVE=1` i `MAC_UPDATE_NOTIFY=1`.

- **Wykonuje:** Homebrew, natywne CLI + npm, aplikacje internetowe, inwentarz i historię.
- **Nie aktualizuje systemu macOS** — `--skip-system` jest celowe. Na Apple Silicon
  `softwareupdate` wymaga **poświadczeń właściciela woluminu**, których nie da się
  podać z zadania launchd, a krok może zrestartować Maca.
- **Nie aktualizuje App Store** — `sudo mas upgrade` wymaga hasła, a ścieżka Tor 2
  steruje interfejsem App Store przez AppleScript. Oba są pomijane w sesji bez TTY
  i raportowane jako ostrzeżenie miękkie (kod `10`), nigdy jako błąd.

Oba pozostają więc interaktywne — celowo. Uruchom `bash update_all.sh` ręcznie,
gdy chcesz zainstalować aktualizacje App Store i macOS.

---

## Wymagania

| Narzędzie | Instalowane automatycznie? |
|------|----------------|
| Mac z Apple Silicon (arm64) | — |
| macOS 13 Ventura lub nowszy (testowane do macOS 27) | — |
| Xcode Command Line Tools | ✅ `setup.sh` / `install.sh` |
| Homebrew | ✅ |
| `mas` (App Store CLI) | ✅ |
| Python 3 | ✅ (przez Homebrew, jeśli brakuje) |
| `rclone` (opcjonalnie) | ✅ jeśli wybrany jako dostawca chmury |

Maki z Intelem i macOS 12 lub starszy nie są obsługiwane; skrypty kończą działanie przed jakąkolwiek zmianą.

---

## Szybki start

### Nowy użytkownik (bez chmury)

```bash
# Opcja A — jedna komenda (zalecane)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"

# Opcja B — ręcznie
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh
bash build_inventory.sh
bash update_all.sh
```

### Właściciel (GitHub + nakładka w chmurze)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

---

## Struktura projektu

```
macOS_updates/
├── VERSION                     # Wersja pakietu (jedno źródło prawdy)
├── install.sh                  # Jednolinijkowy instalator
├── uninstall.sh                # Usuwa sklonowane pliki (zachowuje Homebrew/aplikacje)
├── setup.sh                    # Konfiguracja pierwszego uruchomienia (bez chmury)
├── migration_setup.sh          # Pełna konfiguracja + kreator chmury
├── build_inventory.sh          # Buduje APPLICATIONS.md dla tego Maca
├── update_all.sh               # Główny orkiestrator
├── update_*.sh                 # Poszczególne kroki aktualizacji
├── run_tests.sh                # Składnia + Python + unittest + skan sekretów
│
├── dev_sync/                   # Prywatna synchronizacja z chmurą
│   ├── provider_setup.sh
│   ├── dev-sync-export.sh      # (+ import, verify, prune, …)
│   └── dev_sync_*.py           # Backend Pythona
├── dev-sync-*.sh               # Skrypty w głównym katalogu (kompatybilność)
│
├── config/                     # Rejestr aplikacji internetowych (publiczny)
│   ├── internet_apps.txt
│   ├── internet_app_methods.txt
│   └── internet_dispatch_order.txt
│
├── lib/                        # Współdzielone biblioteki Bash (+ lib/python/)
├── i18n/                       # Tłumaczenia UI w 7 językach
├── scripts/                    # Narzędzia (raport pokrycia, feedy producentów, generator, …)
├── templates/                  # APPLICATIONS.md.template (wzór)
├── tests/                      # unittest + statyczne sprawdzanie bezpieczeństwa
├── docs/
│   ├── INSTALL.md · UNINSTALL.md · PUBLIC_RELEASE.md
│   ├── user/                   # Poradniki dla użytkowników końcowych (7 języków)
│   ├── agents/                 # Referencje dla deweloperów / agentów AI
│   ├── reviews/                # Indeks + bieżące zapisy deweloperskie (archive/ = historia)
│   └── archive/                # Zastąpione plany implementacji
│
├── CHANGELOG.md · CONTRIBUTING.md · SECURITY.md · LICENSE
└── AGENTS.md · CLAUDE.md · GEMINI.md · CODEX.md
```

**Prywatne pliki (zignorowane przez git, tylko lokalne lub w chmurze):** `APPLICATIONS.md`, `UPDATES.md`, `.dev_sync_config.json`, `.mac_update_prefs`, `.env`, `logs/`

### Poszczególne skrypty

| Skrypt | Cel |
|--------|---------|
| `install.sh` | Klonuje + konfiguruje + tworzy inwentarz u nowych użytkowników |
| `setup.sh` | Instaluje zależności (bez chmury) |
| `migration_setup.sh` | Pełna migracja + skan aplikacji + chmura |
| `build_inventory.sh` | Skan tylko do odczytu → atomowe odświeżenie `APPLICATIONS.md` bez historii aktualizacji |
| `update_all.sh` | Wszystkie kroki aktualizacji + logi |
| `update_system.sh` … `update_brew.sh` | Aktualizacje jednowarstwowe |
| `uninstall.sh` | Usuwa katalog macOS_updates |
| `run_tests.sh` | Składnia + Python + unittest + skan sekretów |

Pełna lista skryptów: [docs/agents/scripts.md](docs/agents/scripts.md).

---

## Dodawanie obsługi nowej aplikacji

1. Zainstaluj aplikację samodzielnie (ten skrypt nigdy nie instaluje nowych aplikacji).
2. Uruchom `bash build_inventory.sh`, aby dodać ją do `APPLICATIONS.md`.
3. Aby aplikacja aktualizowała się automatycznie, postępuj zgodnie z [docs/user/pl/GUIDE.md](docs/user/pl/GUIDE.md) (lub poproś Agenta AI):

```bash
bash scripts/scaffold_internet_app.sh "Nazwa Aplikacji" silent_launch
bash run_tests.sh
```

Metody z rejestru są mapowane na powyższe stany pokrycia. Przykładowo `github_dmg` i potwierdzone CLI producenta są **verified direct**, a `silent_launch` jest **triggered-unverified** — samo uruchomienie nie oznacza potwierdzonej aktualizacji; przepływy zarządzane przez App Store lub producenta mogą być **externally managed**, a `manual` i brakujące wpisy w rejestrze pozostają jawne.

---

## Synchronizacja w chmurze (`dev_sync`)

| GitHub (publiczny) | Chmura (prywatna) |
|-----------------|-----------------|
| Skrypty, `config/`, `docs/`, testy | `APPLICATIONS.md`, `UPDATES.md`, `.env`, `.dev_sync_config.json` |

```bash
bash dev_sync/provider_setup.sh
bash dev_sync/dev-sync-export.sh
bash dev_sync/dev-sync-import.sh
bash dev_sync/dev-sync-verify-full.sh
```

Skrypty `dev-sync-*.sh` w głównym katalogu wywołują te same skrypty z `dev_sync/`.

---

## Testowanie

Zestaw testów obejmuje składnię basha, kompilację Pythona, statyczne kontrakty bezpieczeństwa, strażników dokumentacji oraz testy jednostkowe (561 testów automatycznych).
Pull requesty uruchamiają na Ubuntu ShellCheck, przenośne testy Pythona i skan sekretów.
Pełna suite `run_tests.sh` na runnerze macOS działa tylko przy `workflow_dispatch` albo tagu `v*` — nie przy każdym pushu.

```bash
bash run_tests.sh
bash update_all.sh --dry-run -y
```

---

## Ważne notatki techniczne

- **`softwareupdate` musi używać `-R`** — inaczej aktualizacje pobierają się, ale nigdy nie są stosowane.
- **`mas upgrade` musi używać `sudo` i jawnych identyfikatorów aplikacji** w systemach macOS 14.8.2+/15.7.2+/26.1+ (zmiana uprawnień, zob. https://github.com/orgs/Homebrew/discussions/6550).
- **Całość oparta o Bash 3.2+** — żadnych `declare -A`, `mapfile`, `readarray`.
- Pobrane aplikacje przechodzą weryfikację tożsamości/podpisu i rollback-safe staged swap; każdy DMG dostaje unikalny mountpoint sesji.
- Prywatny inwentarz, historia oraz import chmurowy używają zapisu atomowego i stagingu zaakceptowanych plików.

---

## Dokumentacja

| Odbiorca | Rozpocznij tutaj |
|----------|------------|
| Użytkownicy | [docs/user/INDEX.md](docs/user/INDEX.md) (szybki start, przewodnik i runbook w 7 językach) · [szybki start po polsku](docs/user/pl/QUICK_START.md) |
| Instalacja/deinstalacja | [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md) |
| Publiczny GitHub a prywatna nakładka | [docs/PUBLIC_RELEASE.md](docs/PUBLIC_RELEASE.md) · [dev_sync/README.md](dev_sync/README.md) |
| Deweloperzy/agenci | [docs/agents/scripts.md](docs/agents/scripts.md) · [zasady krytyczne](docs/agents/critical_rules.md) · [kody wyjścia](docs/agents/exit_codes.md) · [rozwiązywanie problemów](docs/agents/troubleshooting.md) · [lista akceptacyjna](docs/agents/acceptance_checklist.md) |
| Kontekst agentów AI | [AGENTS.md](AGENTS.md) (wspólny kontrakt) · [CLAUDE.md](CLAUDE.md) · [GEMINI.md](GEMINI.md) · [CODEX.md](CODEX.md) |
| Historia wydań | [CHANGELOG.md](CHANGELOG.md) · [indeks zapisów deweloperskich](docs/reviews/README.md) |
| Współtworzenie / bezpieczeństwo | [CONTRIBUTING.md](CONTRIBUTING.md) · [SECURITY.md](SECURITY.md) |

---

## Rozwiązywanie problemów

| Problem | Rozwiązanie |
|---------|-------------|
| Nowy Mac | `install.sh` albo `setup.sh` + `build_inventory.sh` |
| Zła lista aplikacji | `build_inventory.sh` — nigdy nie kopiuj cudzego `APPLICATIONS.md` |
| Aplikacja nie aktualizuje się automatycznie | `scripts/report_update_coverage.sh` → dodaj handler według przewodnika |
| Brak `APPLICATIONS.md` | `build_inventory.sh` albo `dev_sync/dev-sync-import.sh` (właściciel) |
| `mas upgrade` kończy się błędem | `sudo mas upgrade <app-id>` |
| Chmura nie jest skonfigurowana | `bash dev_sync/provider_setup.sh` |

Pełna lista: [docs/agents/troubleshooting.md](docs/agents/troubleshooting.md)

---

## Licencja

[MIT](LICENSE) © macOS Updates contributors
