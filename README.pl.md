# Aktualizacje macOS

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

> **v1.2.0** — Gotowy do użycia na produkcji jedno-komendowy orkiestrator aktualizacji dla **Maców z Apple Silicon i macOS 13+**. Koordynuje zweryfikowane aktualizacje pakietów oraz uczciwe wywoływanie updaterów dla **oprogramowania już zainstalowanego na tym Macu**. **Wielojęzyczny** (7 języków). Opcjonalna prywatna nakładka przez [`dev_sync/`](dev_sync/README.md).

**Repozytorium publiczne:** [github.com/KasprowiczM/macOS_updates](https://github.com/KasprowiczM/macOS_updates) · Publikacja: [docs/PUBLIC_RELEASE.md](docs/PUBLIC_RELEASE.md) · Zmiany: [CHANGELOG.md](CHANGELOG.md)

---

## Instalacja jedną komendą (nowi użytkownicy)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

Instalator klonuje repozytorium, pyta o **język** (angielskie menu, 7 wersji językowych), instaluje zależności, buduje **Twój** plik `APPLICATIONS.md` na podstawie aplikacji obecnych na tym Macu i wyświetla podsumowanie wspieranych programów.

Zobacz [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md)

---

## Dodatkowe funkcje i narzędzia

- **Touch ID dla sudo:** `bash scripts/setup_touchid_sudo.sh` konfiguruje uwierzytelnianie Touch ID dla sudo (`/etc/pam.d/sudo_local`). Konfiguracja per-maszyna.
- **Harmonogram LaunchAgent:** `bash scripts/install_launchagent.sh --day 1 --hour 9` instaluje cotygodniowy harmonogram aktualizacji w tle. *Uruchomienia w tle używają trybu nieinteraktywnego (`--non-interactive` / `MAC_UPDATE_NONINTERACTIVE=1`), wykonując Homebrew, npm CLI i aplikacje internetowe oraz bezpiecznie pomijając interaktywne kroki App Store i restart macOS.*
- **Flagi i zmienne:** `MAC_UPDATE_NONINTERACTIVE=1` (pomijanie promptów), `MAC_UPDATE_STALE_DAYS=45` (próg dawności niezweryfikowanych aplikacji), `MAC_UPDATE_NO_SUDO_KEEPALIVE=0` (kontrola sudo keep-alive).
- **Nowe metody:** `brew_cask` (adopcja casków Homebrew z weryfikacją na żywo), `sparkle_appcast` (zdalna weryfikacja wersji z feedów XML Sparkle).

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
