# Aktualizacje macOS

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

> **v1.3.1** — Gotowy do użycia na produkcji jedno-komendowy orkiestrator aktualizacji dla **Maców z Apple Silicon i macOS 13–26**. Koordynuje zweryfikowane aktualizacje pakietów oraz uczciwe wywoływanie updaterów dla **oprogramowania już zainstalowanego na tym Macu**. **Wielojęzyczny** (7 języków). Opcjonalna prywatna nakładka przez [`dev_sync/`](dev_sync/README.md).

**Repozytorium publiczne:** [github.com/KasprowiczM/macOS_updates](https://github.com/KasprowiczM/macOS_updates) · Publikacja: [docs/PUBLIC_RELEASE.md](docs/PUBLIC_RELEASE.md) · Zmiany: [CHANGELOG.md](CHANGELOG.md)

---

## Instalacja jedną komendą (nowi użytkownicy)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

Instalator klonuje repozytorium, pyta o **język** (angielskie menu, 7 wersji językowych), instaluje zależności, buduje **Twój** plik `APPLICATIONS.md` na podstawie aplikacji obecnych na tym Macu i wyświetla podsumowanie wspieranych programów.

Zobacz [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md)

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
- **Nie aktualizuje App Store** — `sudo mas upgrade` wymaga hasła, a ścieżka TOR 2
  steruje interfejsem App Store przez AppleScript. Oba są pomijane w sesji bez TTY
  i raportowane jako ostrzeżenie miękkie (kod `10`), nigdy jako błąd.

Oba pozostają więc interaktywne — celowo. Uruchom `bash update_all.sh` ręcznie,
gdy chcesz zainstalować aktualizacje App Store i macOS.

---

## sudo i Touch ID — kontrakt

Przepisany w v1.3.1. `update_all.sh` ma **dokładnie jedno** miejsce wywołania
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

Jeżeli `sudo` nadal pyta o hasło zamiast o palec, sprawdź
[docs/agents/troubleshooting.md](docs/agents/troubleshooting.md) — sekcja Touch ID.

---

## Metody aktualizacji

| Metoda | Weryfikacja wersji zdalnej | Zastosowanie |
|--------|---------------------------|--------------|
| `github_dmg` | ✅ pełna, z weryfikacją podpisu i Team ID | Firefox Dev, KeePassXC, VS Code, CodeEdit, Ledger, Trezor |
| `sparkle_appcast` | ✅ z appcastu Sparkle | ChatGPT Atlas, Proton Drive, Remote Desktop Manager |
| `brew_cask` | ✅ przez Homebrew, z zabezpieczeniem przed cofnięciem wersji | Brave, Obsidian, Spotify, ProtonVPN, zoom i inne |
| `msupdate` | ✅ przez Microsoft AutoUpdate | Word, Excel, PowerPoint, Outlook, OneNote |
| `docker_cli` | ✅ przez `docker desktop update` | Docker Desktop |
| `keystone` | ⚠️ wyzwalacz Google Omaha | wyłącznie Google Chrome i Google Drive |
| `silent_launch` | ⚠️ oportunistyczna — patrz niżej | aplikacje z własnym updaterem |
| `appstore_gui` | ⚠️ AppleScript | aplikacje iPadOS na Apple Silicon |
| `manual` | ❌ brak | IPMIView, DJI Assistant 2 |

**Oportunistyczna weryfikacja (`silent_launch`):** aplikacja, której jedyną
udokumentowaną drogą aktualizacji jest własny updater, może mimo to publikować
maszynowo czytelny feed wersji. Skrypt najpierw szuka `SUFeedURL` w `Info.plist`
(Sparkle), potem `Contents/Resources/app-update.yml` (electron-updater). Gdy feed
odpowie — raportuje prawdziwe porównanie (`✅ Aktualny (x)` /
`⚠️ Dostępna aktualizacja: x → y`). Gdy feedu nie ma albo nie da się go sparsować
— schodzi do uczciwego `⏳ Uruchomiony (niezweryfikowany)` zamiast twierdzić, że
sprawdził coś, czego nie sprawdził. **Weryfikacja nigdy nie podmienia aplikacji** —
instalacją nadal zajmuje się updater producenta.

---

## Co robi ten system

`update_all.sh` wykonuje siedem kroków:

| Krok | Działanie |
|------|-----------|
| 0 | **Prescan** — wykryj zainstalowane aplikacje → zaktualizuj `APPLICATIONS.md` |
| 1 | **App Store** — Tor 1: `sudo mas upgrade`; Tor 2: AppleScript GUI dla aplikacji iPad |
| 2 | **Natywne CLI + npm** — Node, Bun, globalne pakiety npm CLI |
| 3 | **Homebrew** — formulae i caski (`brew_cask` + ochrona przed downgrade'em) + cleanup i doctor |
| 4 | **Aplikacje z Internetu** — zweryfikowane handlery, `sparkle_appcast`, CLI i uczciwe wywołania updaterów |
| 5 | **Postupdate/historia** — odśwież `APPLICATIONS.md`, dopisz do `UPDATES.md` |
| 6 | **macOS (końcowy)** — `softwareupdate -ia -R`; pomijany gdy wcześniejszy krok zawiódł |

**Ważne:** Aktualizacje dotyczą wyłącznie oprogramowania już zainstalowanego na Twoim Macu. Końcowy krok macOS może uruchomić komputer ponownie, dlatego działa ostatni i zawsze zachowuje wymagane `-R`. Zgłaszane są braki obsługiwanych aplikacji, ale nie są one instalowane.

Raport pokrycia rozróżnia: **verified direct** — skrypt potwierdził ścieżkę pakietu/wersji; **triggered-unverified** — uruchomił aplikację, lecz nie może potwierdzić zakończenia aktualizacji producenta; **externally managed** — cyklem zarządza producent lub App Store; **manual** — potrzebna jest akcja użytkownika; **unknown** — brak zarejestrowanej metody. Inkscape jest obsługiwany jako cask Homebrew, UniFi/WiFiman/Picsart przez App Store Track 2, Office przez `msupdate`, a Teams przez własny updater z obserwowowanym, weryfikowanym fallbackiem MAU `TEAMS21`, gdy Microsoft go oferuje. Ręczne pozostają tylko IPMIView i DJI Assistant 2.

```bash
bash scripts/report_update_coverage.sh   # raport pokrycia aplikacji
bash build_inventory.sh                  # przebudowa APPLICATIONS.md z tego Maca
```

---

## Wymagania

| Narzędzie | Instalowane automatycznie? |
|------|----------------|
| Mac z Apple Silicon (arm64) | — |
| macOS 13 Ventura lub nowszy | — |
| Xcode Command Line Tools | ✅ `setup.sh` / `install.sh` |
| Homebrew | ✅ |
| `mas` (App Store CLI) | ✅ |
| Python 3 | ✅ (przez Homebrew, jeśli brakuje) |
| `rclone` (opcjonalnie) | ✅ jeśli wybrany jako dostawca chmury |

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
├── VERSION                     # Wersja pakietu (1.0.21)
├── install.sh                  # Jednolinijkowy instalator
├── uninstall.sh                # Usuwa sklonowane pliki (zachowuje Homebrew/aplikacje)
├── setup.sh                    # Konfiguracja pierwszego uruchomienia (bez chmury)
├── migration_setup.sh          # Pełna konfiguracja + kreator chmury
├── build_inventory.sh          # Buduje APPLICATIONS.md dla tego Maca
├── update_all.sh               # Główny orkiestrator
├── update_*.sh                 # Poszczególne kroki aktualizacji
│
├── dev_sync/                   # Prywatna synchronizacja z chmurą
│   ├── provider_setup.sh
│   ├── dev-sync-export.sh      # (+ import, verify, prune, …)
│   └── dev_sync_*.py           # Backend Pythona
├── dev-sync-*.sh               # Skrypty narzędziowe w głównym katalogu (kompatybilność)
│
├── config/                     # Rejestr aplikacji internetowych (publiczny)
│   ├── internet_apps.txt
│   ├── internet_app_methods.txt
│   └── internet_dispatch_order.txt
│
├── lib/                        # Współdzielone biblioteki Bash
├── i18n/                       # Tłumaczenia UI w 7 językach
├── scripts/                    # Narzędzia (raporty, generatory, …)
├── templates/                  # APPLICATIONS.md.template (wzór)
├── tests/                      # unittest + statyczne sprawdzanie bezpieczeństwa
├── docs/
│   ├── INSTALL.md · UNINSTALL.md
│   ├── user/                   # Poradniki dla użytkowników końcowych (7 języków)
│   └── agents/                 # Referencje dla deweloperów / agentów AI
│
├── AGENTS.md
└── run_tests.sh
```

**Prywatne pliki (zignorowane przez git, tylko lokalne lub w chmurze):** `APPLICATIONS.md`, `UPDATES.md`, `.dev_sync_config.json`, `.mac_update_prefs`, `.env`

---

## Poszczególne skrypty

| Skrypt | Cel |
|--------|---------|
| `install.sh` | Klonuje + konfiguruje + tworzy inventarz u nowych użytkowników |
| `setup.sh` | Instaluje zależności (bez chmury) |
| `migration_setup.sh` | Pełna migracja + skan aplikacji + chmura |
| `build_inventory.sh` | Skan aplikacji → `APPLICATIONS.md` |
| `update_all.sh` | Wszystkie kroki aktualizacji + logi |
| `update_system.sh` … | Aktualizacje jednowarstwowe |
| `uninstall.sh` | Usuwa katalog macOS_updates |
| `run_tests.sh` | Sprawdzenie składni + Python + unittest + skan sekretów |

---

## Dodawanie obsługi nowej aplikacji

1. Zainstaluj aplikację samodzielnie (ten skrypt nigdy nie instaluje nowych aplikacji).
2. Uruchom `bash build_inventory.sh`, aby dodać ją do `APPLICATIONS.md`.
3. Aby aplikacja aktualizowała się automatycznie, postępuj zgodnie z [docs/user/pl/GUIDE.md](docs/user/pl/GUIDE.md) (lub poproś Agenta AI):

```bash
bash scripts/scaffold_internet_app.sh "Nazwa Aplikacji" silent_launch
bash run_tests.sh
```

Metody z rejestru są mapowane na powyższe stany pokrycia. Przykładowo `github_dmg` i potwierdzone CLI producenta są **verified direct**, a `silent_launch` jest **triggered-unverified** — samo uruchomienie nie oznacza potwierdzonej aktualizacji.

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

---

## Testowanie

```bash
bash run_tests.sh
bash update_all.sh --dry-run -y
```

---

## Ważne notatki techniczne

- **`softwareupdate` musi używać `-R`** — inaczej aktualizacje pobierają się, ale nigdy nie są stosowane.
- **`mas upgrade` musi używać `sudo`** w systemie macOS 26.x (CVE-2025-43411).
- **Całość oparta o Bash 3.2+** — żadnych `declare -A`, `mapfile`, `readarray`.
- Pobrane aplikacje przechodzą weryfikację tożsamości/podpisu i rollback-safe staged swap; każdy DMG dostaje unikalny mountpoint sesji.
- Prywatny inwentarz, historia oraz import chmurowy używają zapisu atomowego i stagingu zaakceptowanych plików.

---

## Dokumentacja

| Odbiorca | Rozpocznij tutaj |
|----------|------------|
| Użytkownicy | [docs/user/pl/QUICK_START.md](docs/user/pl/QUICK_START.md) |
| Instalacja/deinstalacja | [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md) |
| Deweloperzy/agenci | [docs/agents/scripts.md](docs/agents/scripts.md) |
| Synchronizacja (dev sync) | [dev_sync/README.md](dev_sync/README.md) |
| Agenci AI (kontekst) | `AGENTS.md` |

---

## Rozwiązywanie problemów

Pełna lista: [docs/agents/troubleshooting.md](docs/agents/troubleshooting.md)
