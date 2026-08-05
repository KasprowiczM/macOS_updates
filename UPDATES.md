# 📖 INSTRUKCJA AKTUALIZACJI MACBOOKA — Kompletny Przewodnik

> **System:** macOS 26.6 Tahoe | **Architektura:** Apple Silicon (arm64)
> **Użytkownik:** mk | **Home:** `/Users/mk`
> **Folder skryptów:** `~/Dev_Env/macOS_updates`
> **Dla:** Użytkowników macOS
> **Data:** 2026-08-05 (zaktualizowano)

---

## 🗺️ Spis treści

0. [Przeniesienie na nowy Mac — migracja](#0-migracja-na-nowy-mac)
1. [Przed rozpoczęciem — ważne informacje](#1-przed-rozpoczęciem)
2. [Metoda błyskawiczna — jeden skrypt](#2-metoda-błyskawiczna)
3. [Aktualizacja 1: System macOS](#3-aktualizacja-systemu-macos)
4. [Aktualizacja 2: App Store](#4-aktualizacja-app-store)
5. [Aktualizacja 3: Aplikacje z Internetu](#5-aktualizacja-aplikacji-z-internetu)
6. [Aktualizacja 4: Homebrew](#6-aktualizacja-homebrew)
7. [Harmonogram](#7-harmonogram)
8. [Rozwiązywanie problemów](#8-rozwiązywanie-problemów)

---

## 0. Przeniesienie na nowy Mac — migracja {#0-migracja-na-nowy-mac}

Po skopiowaniu całego folderu projektu na nowego MacBooka **uruchom najpierw**:

```bash
cd ~/Dev_Env/macOS_updates && bash migration_setup.sh
```

Skrypt `migration_setup.sh` przeprowadza **16 faz** jednorazowej konfiguracji:

| # | Faza | Co robi |
|---|------|---------|
| 1 | Wykrywanie systemu | Użytkownik, macOS, architektura (arm64/Intel), terminal |
| 2 | Stary username | Wyciąga poprzednią nazwę z CLAUDE.md (`/Users/<stary>/`) |
| 3 | Naprawa ścieżek | Aktualizuje `/Users/<stary>/` → `/Users/<nowy>/` we wszystkich `.md` |
| 4 | Wersja macOS | Aktualizuje wersję macOS i arch w CLAUDE.md, AGENTS.md, GEMINI.md |
| 5 | Xcode CLT | Sprawdza/instaluje Xcode Command Line Tools |
| 6 | Homebrew | Instaluje jeśli brak; dodaje `shellenv` do profilu powłoki |
| 7 | mas | Instaluje/aktualizuje do ≥4.0 (wymóg CVE-2025-43411 na macOS 26.x) |
| 8 | Python 3 | Wykrywa lub instaluje przez Homebrew |
| 9 | curl, git | Weryfikacja dostępności |
| 10 | Narzędzia opcjonalne | msupdate (MS365), Docker ≥4.37, Google Keystone |
| 11 | Uprawnienia | `chmod +x` dla wszystkich `*.sh` |
| 12 | App Store | Weryfikacja zalogowania przez `mas list` |
| 13 | Accessibility | Test `osascript`; otwiera Ustawienia systemowe jeśli brak |
| 14 | Skan aplikacji | Python skanuje `/Applications` + brew + mas → aktualizuje APPLICATIONS.md |
| 15 | Naprawa MCP | Aktualizuje ścieżki i PATH w konfiguracjach Gemini/Windsurf |
| 16 | Log migracji | Dopisuje wpis do UPDATES.md; wyświetla checklistę ✅/⚠️/❌ |

**Po zakończeniu migration_setup.sh** — uruchom normalnie:

```bash
bash update_all.sh
```

> ⚠️ Skrypt jest idempotentny — bezpieczne wielokrotne uruchomienie.
> Jeśli coś nie wyszło (np. brak internetu dla Homebrew), uruchom ponownie po naprawieniu problemu.

---

## 1. Przed rozpoczęciem {#1-przed-rozpoczęciem}

Przed każdą aktualizacją upewnij się, że:

- ✅ **Masz kopię zapasową** — podłącz dysk i użyj Time Machine *(Jabłko → Ustawienia → Time Machine)*
- ✅ **Bateria ≥ 50%** lub podłączony zasilacz
- ✅ **Stabilne WiFi** — aktualizacje mogą ważyć kilka GB
- ✅ **≥ 10 GB wolnego miejsca** *(Jabłko → O tym Macu → Pamięć masowa)*
- ✅ **Masz czas** — pełna aktualizacja: 30–60 minut

---

## 2. Metoda błyskawiczna {#2-metoda-błyskawiczna}

Jeden skrypt robi **wszystko** automatycznie.

**Jak uruchomić?**

1. Naciśnij **⌘ + Spacja**, wpisz `Terminal`, naciśnij **Enter**
2. Wpisz poniższą komendę i naciśnij **Enter**:

```bash
cd ~/Dev_Env/macOS_updates && bash update_all.sh
```

Skrypt uruchomi po kolei wszystkie kroki i wyświetli podsumowanie.

> 💡 **Nowy Mac?** Uruchom najpierw `bash migration_setup.sh` (tylko raz, przed pierwszym `update_all.sh`).

---

## 3. Aktualizacja systemu macOS {#3-aktualizacja-systemu-macos}

**Skrypt:** `bash update_system.sh`

### 🔧 Aktualizacja Ledger Wallet, bezpieczne montowanie i usprawnienia dev-sync: 2026-05-22

**Bezpieczna aktualizacja aplikacji z Internetu oraz integracja z cloud storage (12/12 testów ✅)**

**Nowe funkcje i poprawki:**
- **🔐 Ledger Live / Ledger Wallet:** Zaimplementowano bezpośredni instalator DMG pobierający najnowszą wersję bezpośrednio ze strony producenta, weryfikujący podpis Gatekeeper i bezpiecznie nadpisujący starą aplikację. Całkowicie omija uszkodzony auto-updater wewnątrz aplikacji.
- **📁 Trezor Suite, KeePassXC, CodeEdit:** Naprawiono montowanie woluminów zawierających spacje w nazwie oraz problem z nadpisywaniem pakietów `.app` (zapobieganie uszkodzeniom podpisów cyfrowych).
- **⚙️ Pętle plików Markdown:** Zabezpieczono skrypty `setup.sh` oraz `migration_setup.sh` przed nieprawidłowym dzieleniem nazw ścieżek zawierających spacje podczas pętli po plikach `.md`.
- **🧼 Czyszczenie w tle:** Dodano handlery `trap` na sygnały `EXIT`, `INT`, `TERM` w `update_brew.sh` oraz `update_npm_cli.sh` w celu automatycznego sprzątania katalogów tymczasowych przy przerwaniu skryptu.
- **🔄 Dev-Sync Cloud Sync:** Dodano obsługę zmiennej środowiskowej `DEV_SYNC_FORCE_PYTHON_TRANSFER=1` umożliwiającej dynamiczne przełączenie na czysty transfer Pythonowy. Rozwiązuje to problem blokowania `mmap` przez FileProvider w systemie macOS (np. przy synchronizacji z Proton Drive).

### Ręcznie (graficznie):

1. Kliknij **🍎** (lewy górny róg) → **Ustawienia systemowe**
2. Kliknij **Ogólne** → **Aktualizacja oprogramowania**
3. Poczekaj na sprawdzenie aktualizacji
4. Kliknij **Zaktualizuj teraz** (jeśli dostępne)
5. Wprowadź hasło → poczekaj na instalację (10–30 min)
6. Zrestartuj komputer gdy zostaniesz poproszony

> 💡 Włącz **Aktualizacje automatyczne** w tym samym miejscu.

---

## 4. Aktualizacja App Store {#4-aktualizacja-app-store}

**Skrypt:** `bash update_appstore.sh`

Skrypt działa **dwutorowo** — obsługuje wszystkie typy aplikacji App Store:

**TOR 1 — `sudo mas upgrade`** (natywne aplikacje macOS):
Amphetamine, Canva, iMovie, KeePassium, Keynote, NordVPN, Notion Web Clipper, Numbers, OneDrive, Pages, Perplexity, Prime Video, Telegram, WhatsApp, Xcode, myCANAL (CANAL+)

**TOR 2 — Automatyzacja GUI App Store** (aplikacje iPad na Apple Silicon):
UniFi, WiFiman, Picsart i inne iPad apps — `mas` ich oficjalnie nie obsługuje (udokumentowane ograniczenie). Skrypt automatyzuje kliknięcie „Update All" w App Store UI przez AppleScript.

> 💡 Skrypt ustawia `MAS_NO_AUTO_INDEX=1` automatycznie — eliminuje ostrzeżenia o braku indeksu Spotlight.

> ⚠️ **TOR 2 wymaga jednorazowego uprawnienia Accessibility** dla terminala (Terminal.app / Warp / iTerm):
> Ustawienia systemowe → Prywatność i bezpieczeństwo → Dostępność → `+` → dodaj terminal.
> Skrypt wykryje brak uprawnienia i otworzy odpowiedni panel automatycznie.

### Ręcznie (graficznie):

1. Kliknij ikonę **App Store** w Docku (niebieski kwadrat z „A")
2. W lewym panelu wybierz **Uaktualnienia**
3. Kliknij **Zaktualizuj wszystko** (prawy górny róg)
4. Zaloguj się na **Apple ID** jeśli wymagane

> ⚠️ Musisz być zalogowany tym samym Apple ID, którym kupowałeś aplikacje.

---

## 5. Aktualizacja aplikacji z Internetu {#5-aktualizacja-aplikacji-z-internetu}

**Skrypt:** `bash update_internet_apps.sh`

Skrypt sprawdza i uruchamia każdą aplikację aby wywołać jej wbudowany mechanizm aktualizacji. Poniżej szczegółowe instrukcje ręczne dla każdej aplikacji.

---

### 🌐 Przeglądarki internetowe

#### Google Chrome
Chrome aktualizuje się **automatycznie w tle**. Aby sprawdzić lub wymusić:
1. Otwórz Chrome
2. Kliknij **⋮** (trzy kropki) → **Pomoc** → **O Google Chrome**
3. Aktualizacja pobierze się automatycznie → kliknij **Uruchom ponownie**

#### Firefox Developer Edition
1. Otwórz **Firefox Developer Edition**
2. Kliknij **☰** → **Pomoc** → **O Firefoksie**
3. Firefox automatycznie sprawdzi i pobierze aktualizację
4. Kliknij **Uruchom ponownie, aby zaktualizować Firefoksa**

**Lub pobierz ręcznie:** https://www.mozilla.org/pl/firefox/developer/

#### Brave Browser
1. Otwórz **Brave**
2. Kliknij menu **☰** → **Pomoc** → **O Brave**
3. Brave sprawdzi i pobierze aktualizację automatycznie

**Lub pobierz ręcznie:** https://brave.com/download/

---

### 🤖 Aplikacje AI

#### ChatGPT (OpenAI)
ChatGPT aktualizuje się automatycznie. Aby sprawdzić:
1. Otwórz **ChatGPT**
2. Kliknij **ChatGPT** w menu górnym → **Sprawdź aktualizacje**

**Lub pobierz ręcznie:** https://openai.com/download

#### ChatGPT Atlas (OpenAI)
1. Otwórz **ChatGPT Atlas**
2. Aplikacja sprawdzi aktualizacje automatycznie przy starcie

#### Claude (Anthropic)
1. Otwórz **Claude**
2. Kliknij **Claude** w menu górnym → **Sprawdź aktualizacje**

**Lub pobierz ręcznie:** https://claude.ai/download

#### Codex (OpenAI)
1. Otwórz **Codex**
2. Aplikacja sprawdzi aktualizacje automatycznie

**Lub pobierz ręcznie:** https://github.com/openai/codex

#### Comet — Perplexity AI
Comet bazuje na Chromium i aktualizuje się automatycznie.
1. Otwórz **Comet** → kliknij **Comet** w menu → **Sprawdź aktualizacje**

**Lub pobierz ręcznie:** https://www.perplexity.ai/settings

#### Antigravity — Google AI
1. Otwórz **Antigravity**
2. Aplikacja automatycznie sprawdzi dostępność nowej wersji przy starcie

#### LM Studio
1. Otwórz **LM Studio**
2. Sprawdź powiadomienie o aktualizacji w aplikacji

**Lub pobierz ręcznie:** https://lmstudio.ai

#### Perplexity
1. Otwórz **Perplexity**
2. Aplikacja sprawdza aktualizacje automatycznie

---

### 🔒 Bezpieczeństwo i VPN

#### NordVPN
1. Otwórz **NordVPN**
2. Kliknij ikonę **koła zębatego** (⚙️) → **Ogólne** → **Sprawdź aktualizacje**

**Lub pobierz ręcznie:** https://nordvpn.com/download/mac/

#### ProtonVPN
1. Otwórz **ProtonVPN**
2. Kliknij **ProtonVPN** w menu górnym → **Sprawdź aktualizacje**

**Lub pobierz ręcznie:** https://protonvpn.com/download

#### KeePassXC
1. Otwórz **KeePassXC**
2. Kliknij **KeePassXC** → **Sprawdź aktualizacje**
3. Jeśli jest dostępna — pobierz wersję **ARM64 (Apple Silicon) .dmg**
4. Otwórz plik → przeciągnij do folderu Aplikacje

**Lub pobierz ręcznie:** https://keepassxc.org/download/#mac

---

### 📧 Poczta i komunikacja

#### Proton Mail
Proton Mail sprawdza aktualizacje automatycznie przy starcie.
1. Otwórz **Proton Mail**
2. Kliknij **Proton Mail** w menu górnym → **Sprawdź aktualizacje**

**Lub pobierz ręcznie:** https://proton.me/mail/download

#### Zoom
1. Otwórz **Zoom**
2. Kliknij **zoom.us** w górnym menu → **Sprawdź aktualizacje** (Check for Updates)
3. Kliknij **Aktualizuj** i poczekaj

**Lub pobierz ręcznie:** https://zoom.us/download

---

### ☁️ Przechowywanie w chmurze

#### Google Drive
Google Drive aktualizuje się automatycznie w tle.
**Lub pobierz ręcznie:** https://www.google.com/drive/download/

#### OneDrive
OneDrive aktualizuje się automatycznie przez Microsoft AutoUpdate.
**Lub pobierz ręcznie:** https://www.microsoft.com/en-us/microsoft-365/onedrive/download

#### MEGAsync
1. Otwórz **MEGAsync** (ikona w menu bar)
2. Kliknij ikonę → **Ustawienia** → **Sprawdź aktualizacje**

**Lub pobierz ręcznie:** https://mega.nz/desktop

#### Proton Drive
Proton Drive sprawdza aktualizacje automatycznie.
**Lub pobierz ręcznie:** https://proton.me/drive/download

---

### 💼 Microsoft 365

Microsoft 365 (Word, Excel, PowerPoint, Outlook, OneNote, Teams) aktualizuje się przez **Microsoft AutoUpdate**:
1. Otwórz dowolną aplikację Microsoft (np. Word)
2. Kliknij **Pomoc** w menu górnym → **Sprawdź aktualizacje**
3. Microsoft AutoUpdate sprawdzi i zaktualizuje wszystkie aplikacje M365

**Lub pobierz pakiet ręcznie:** https://www.microsoft.com/microsoft-365

---

### 💻 Narzędzia deweloperskie

#### Visual Studio Code
1. Otwórz **Visual Studio Code**
2. Kliknij **Pomoc** → **Sprawdź aktualizacje** (Check for Updates)
3. Kliknij **Pobierz aktualizację** → **Uruchom ponownie**

**Lub pobierz ręcznie (Apple Silicon):** https://code.visualstudio.com/download

#### Warp
1. Otwórz **Warp**
2. Kliknij **Warp** w menu → **Sprawdź aktualizacje**

**Lub pobierz ręcznie:** https://www.warp.dev

#### Docker
Docker Desktop aktualizuje się przez wbudowany mechanizm:
1. Kliknij ikonę **Docker** w menu bar (wieloryb) → **Check for Updates**

**Lub pobierz ręcznie:** https://www.docker.com/products/docker-desktop/

#### CodeEdit
1. Otwórz **CodeEdit**
2. Kliknij **CodeEdit** w menu → **Sprawdź aktualizacje**

**Lub pobierz ręcznie:** https://codeedit.app

#### VirtualBox
VirtualBox nie ma auto-updater. Sprawdzaj ręcznie:
**Pobierz ręcznie:** https://www.virtualbox.org/wiki/Downloads

---

### 📋 Produktywność

#### Notion / Notion Calendar
1. Otwórz **Notion**
2. Kliknij **Notion** w menu → **Sprawdź aktualizacje**

**Lub pobierz ręcznie:** https://www.notion.so/desktop

#### Canva
Canva aktualizuje się automatycznie przy starcie.
**Lub pobierz ręcznie:** https://www.canva.com/download/

---

### 🎨 Multimedia i grafika

#### DaVinci Resolve
DaVinci Resolve nie ma auto-updater. Sprawdzaj ręcznie:
**Pobierz ręcznie:** https://www.blackmagicdesign.com/products/davinciresolve

#### Blackmagic RAW / Proxy Generator Lite
Aktualizowane razem z DaVinci Resolve lub osobno:
**Pobierz ręcznie:** https://www.blackmagicdesign.com/support/

#### Spotify
Spotify aktualizuje się automatycznie w tle.
**Lub pobierz ręcznie:** https://www.spotify.com/download/

---

### 🔐 Krypto i finanse

#### Ledger Live
1. Otwórz **Ledger Live**
2. Kliknij **Ustawienia** → **O Ledger Live** → sprawdź wersję
3. Aplikacja informuje o dostępnych aktualizacjach

**Lub pobierz ręcznie:** https://www.ledger.com/ledger-live

#### Trezor Suite
1. Otwórz **Trezor Suite**
2. Aplikacja automatycznie sprawdza aktualizacje przy starcie

**Lub pobierz ręcznie:** https://trezor.io/trezor-suite

---

### 🖥️ Sieć i infrastruktura IT

#### UniFi Network Application
1. Otwórz **UniFi**
2. Sprawdź aktualizacje w panelu aplikacji

**Lub pobierz ręcznie:** https://www.ui.com/download/unifi

#### Remote Desktop Manager
1. Otwórz **Remote Desktop Manager**
2. Kliknij **Pomoc** → **Sprawdź aktualizacje**

**Lub pobierz ręcznie:** https://devolutions.net/remote-desktop-manager/

---

## 6. Aktualizacja Homebrew {#6-aktualizacja-homebrew}

**Skrypt:** `bash update_brew.sh`

### Ręcznie przez Terminal:

**Krok 1:** Otwórz Terminal (⌘ + Spacja → „Terminal" → Enter)

**Krok 2:** Wpisz kolejno (każda komenda + Enter):

```bash
# Zaktualizuj bazę pakietów
brew update

# Sprawdź co jest nieaktualne
brew outdated

# Zaktualizuj wszystko
brew upgrade

# Wyczyść stare pliki
brew cleanup

# Sprawdź stan instalacji
brew doctor
```

Jeśli `brew doctor` wyświetli **„Your system is ready to brew."** — wszystko jest w porządku! ✅

### Kluczowe pakiety Homebrew (narzędzia użytkownika)

| Pakiet | Wersja | Do czego służy |
|--------|--------|----------------|
| `bun` | 1.3.10 | JavaScript/TypeScript runtime |
| `coreutils` | 9.10 | Narzędzia GNU |
| `ffmpeg` | 8.0.1 | Konwersja wideo/audio |
| `gemini-cli` | 0.31.0 | Google Gemini AI (CLI) |
| `ghostscript` | 10.06.0 | PostScript i PDF |
| `gogcli` | 0.11.0 | Klient GOG.com |
| `imagemagick` | 7.1.2 | Edycja obrazów (CLI) |
| `midnight-commander` | 4.8.33 | Menedżer plików CLI |
| `node` | 25.6.1 | JavaScript/Node.js |
| `openai-whisper` | 20250625 | Rozpoznawanie mowy (lokalnie) |
| `opencode` | 1.2.15 | Agent kodowania AI |
| `postgresql@16` | 16.13 | Baza danych PostgreSQL |
| `python@3.11` | 3.11.14 | Python 3.11 |
| `python@3.14` | 3.14.3 | Python 3.14 |
| `pytorch` | 2.10.0 | Uczenie maszynowe |
| `qwen-code` | 0.11.0 | Asystent kodowania Qwen AI |
| `ripgrep` | 15.1.0 | Szybkie wyszukiwanie |
| `supabase` | 2.75.0 | Backend-as-a-Service CLI |
| `tesseract` | 5.5.2 | OCR — rozpoznawanie tekstu |
| `uv` | 0.10.7 | Menedżer pakietów Python |
| `blackhole-2ch` *(cask)* | 0.6.1 | Wirtualna karta audio |
| `inkscape` *(cask)* | 1.4.3 | Edytor grafiki wektorowej |

> ⚠️ **Uwaga:** `mas` (CLI dla App Store) nie jest zainstalowany jako brew formula — zostanie doinstalowany automatycznie przez `update_appstore.sh`.

---

## 7. Harmonogram {#7-harmonogram}

| Częstotliwość | Czynność | Skrypt |
|---------------|----------|--------|
| **Co tydzień** | App Store | `bash update_appstore.sh` |
| **Co tydzień** | Homebrew | `bash update_brew.sh` |
| **Co miesiąc** | System macOS | `bash update_system.sh` |
| **Co miesiąc** | Aplikacje z internetu | `bash update_internet_apps.sh` |
| **Co kwartał** | Pełna aktualizacja | `bash update_all.sh` |

---

## 8. Rozwiązywanie problemów {#8-rozwiązywanie-problemów}

| Problem | Rozwiązanie |
|---------|------------|
| **Folder skopiowany na nowy Mac** | Uruchom `bash migration_setup.sh` — naprawia ścieżki, instaluje zależności |
| Skrypt nie uruchamia się | `chmod +x *.sh` (lub uruchom ponownie `migration_setup.sh`) |
| `brew: command not found` | `eval "$(/opt/homebrew/bin/brew shellenv)"` (arm64) / `eval "$(/opt/homebrew/bin/brew shellenv)"` (Intel) |
| Homebrew nie zainstalowany | `migration_setup.sh` instaluje automatycznie; lub: `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"` |
| Brak miejsca podczas aktualizacji | `brew cleanup --prune=all` |
| `mas` błąd zalogowania | Zaloguj się ręcznie w App Store, potem spróbuj ponownie |
| `mas` nie zainstalowany | `brew install mas` (lub uruchom `migration_setup.sh`) |
| `mas upgrade` nie działa | Użyj `sudo mas upgrade` (wymagane od macOS 26.x — CVE-2025-43411) |
| Accessibility: "not allowed" | Ustawienia systemowe → Prywatność → Dostępność → dodaj terminal |
| Aktualizacja systemu się zawiesza | Poczekaj 30 min — nie wyłączaj komputera |
| macOS zaktualizował się ale nie zastosował | Użyj `sudo softwareupdate -ia -R` — nigdy `sudo reboot` |
| Chrome nie aktualizuje się | Chrome → **⋮** → Pomoc → O Google Chrome |
| KeePassXC pobierz ręcznie | https://keepassxc.org/download/ (wersja ARM64) |
| VirtualBox nie aktualizuje się | Pobierz ręcznie: https://www.virtualbox.org/wiki/Downloads |
| Microsoft apps nie aktualizują się | Otwórz Word/Excel → Pomoc → Sprawdź aktualizacje (Microsoft AutoUpdate) |
| Docker nie aktualizuje się przez skrypt | Wymagany Docker Desktop ≥4.37; starszy: aktualizuj ręcznie przez ikonę w menu bar |
| APPLICATIONS.md ma przestarzałe wersje | Uruchom `update_all.sh` (krok 6) lub `migration_setup.sh` (po migracji) |

---

## Przydatne linki

| Aplikacja | Strona |
|-----------|--------|
| macOS | https://support.apple.com |
| Homebrew | https://brew.sh |
| VS Code | https://code.visualstudio.com |
| Firefox Dev Edition | https://www.mozilla.org/pl/firefox/developer/ |
| Chrome | https://www.google.com/chrome |
| Brave | https://brave.com/download/ |
| Zoom | https://zoom.us/download |
| KeePassXC | https://keepassxc.org/download |
| NordVPN | https://nordvpn.com/download/mac |
| ProtonVPN | https://protonvpn.com/download |
| Proton Mail | https://proton.me/mail/download |
| Claude | https://claude.ai/download |
| Docker | https://www.docker.com/products/docker-desktop/ |
| Warp | https://www.warp.dev |

---
*Zaktualizowano: 2026-08-05 | macOS 26.6 Tahoe arm64 | Użytkownik: mk*

---

## 📅 Historia sesji aktualizacji

### 🔄 Sesja aktualizacji: 2026-08-05 17:34

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | pominięty |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | Ostrzeżenie zakończono z ostrzeżeniami (niezweryfikowane) |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Docker Desktop | 4.84.0 | 4.85.0 |


### 🔄 Sesja aktualizacji: 2026-08-05 17:31

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | pominięty |
| 🛍️ App Store | Błąd |
| 🌐 Aplikacje z Internetu | Ostrzeżenie zakończono z ostrzeżeniami (niezweryfikowane) |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

*Brak zaktualizowanych pakietów w tej sesji.*


### 🔄 Sesja aktualizacji: 2026-08-05 11:39

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | Ostrzeżenie zakończono z ostrzeżeniami (niezweryfikowane) |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `cffi` | 2.1.0 | 2.1.1 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Gemini | 1.88.5.636 | 1.92.1.684 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.221 | 2.1.222 |


### 🔄 Sesja aktualizacji: 2026-08-04 23:28

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | Ostrzeżenie zakończono z ostrzeżeniami (niezweryfikowane) |
| 🌐 Aplikacje z Internetu | Ostrzeżenie zakończono z ostrzeżeniami (niezweryfikowane) |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `stripe` | 1.45.0 | 1.45.1 |
| `unbound` | 1.25.2 | 1.26.0 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Trezor Suite | 26.7.3 | 26.7.4 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `opencode-cli` | 1.18.12 | 1.18.13 |


### 🔄 Sesja aktualizacji: 2026-08-04 09:06

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | Ostrzeżenie zakończono z ostrzeżeniami (niezweryfikowane) |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `sdl3` | 3.4.12 | 3.4.14 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.220 | 2.1.221 |
| `opencode-cli` | 1.18.11 | 1.18.12 |


### 🔄 Sesja aktualizacji: 2026-08-03 20:36

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | Ostrzeżenie zakończono z ostrzeżeniami (niezweryfikowane) |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `glib` | 2.88.2 | 2.88.3 |
| `gogcli` | 0.34.1 | 0.34.2 |
| `harfbuzz` | 14.2.1 | 14.3.0 |
| `libnghttp2` | 1.69.0 | 1.70.0 |
| `mpg123` | 1.33.6 | 1.33.7 |
| `openimageio` | 3.1.15.0_1 | 3.1.16.0 |
| `poppler` | 26.07.0 | 26.08.0 |
| `uv` | 0.12.0 | 0.12.1 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| ChatGPT / Codex | 26.727.40816 | 26.727.51351 |
| OpenCode | 1.18.10 | 1.18.11 |
| Proton Mail | 1.13.3 | 1.13.4 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `agy-cli` | 1.1.9 | 1.1.10 |
| `node` | 26.5.1 | 26.6.0 |
| `opencode-cli` | 1.18.10 | 1.18.11 |
| `pnpm` | 11.18.0 | 11.20.0 |


### 🔄 Sesja aktualizacji: 2026-07-31 12:22

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | Ostrzeżenie zakończono z ostrzeżeniami (niezweryfikowane) |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gh` | 2.96.0 | 2.97.0 |
| `stripe` | 1.44.1 | 1.45.0 |
| `supabase` | 2.110.0 | 2.111.0 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `agy-cli` | 1.1.8 | 1.1.9 |


### 🔄 Sesja aktualizacji: 2026-07-30 22:09

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | Ostrzeżenie zakończono z ostrzeżeniami (niezweryfikowane) |
| 🌐 Aplikacje z Internetu | Ostrzeżenie zakończono z ostrzeżeniami (niezweryfikowane) |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| ChatGPT / Codex | 26.721.81911 | 26.727.40816 |
| Trezor Suite | 26.7.2 | 26.7.3 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `opencode-cli` | 1.18.9 | 1.18.10 |


### 🔄 Sesja aktualizacji: 2026-07-30 14:26

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | Ostrzeżenie zakończono z ostrzeżeniami (niezweryfikowane) |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `stripe` | 1.44.0 | 1.44.1 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `node` | 26.5.0 | 26.5.1 |
| `npm` | 12.0.1 | 12.0.2 |


### 🔄 Sesja aktualizacji: 2026-07-29 15:54

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | Ostrzeżenie zakończono z ostrzeżeniami (niezweryfikowane) |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `libarchive` | 3.8.8 | 3.8.9 |
| `uv` | 0.11.32 | 0.12.0 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| ChatGPT / Codex | 26.721.41059 | 26.721.81911 |
| Ledger Live | 4.13.0 | 4.13.1 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `codex-cli` | 0.145.0 | 0.146.0 |
| `opencode-cli` | 1.18.8 | 1.18.9 |
| `pnpm` | 11.17.0 | 11.18.0 |


### 🔄 Sesja aktualizacji: 2026-07-28 16:52

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | Ostrzeżenie zakończono z ostrzeżeniami (niezweryfikowane) |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

*Brak zaktualizowanych pakietów w tej sesji.*


### 🔄 Sesja aktualizacji: 2026-07-28 14:50

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | Ostrzeżenie zakończono z ostrzeżeniami (niezweryfikowane) |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `imagemagick` | 7.1.2-28 | 7.1.2-29 |
| `libssh2` | 1.11.1_3 | 1.11.1_4 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| ChatGPT Atlas | 1.2026.189.0 | 1.2026.189.1 |
| Ledger Live | 4.11.0 | 4.13.0 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `agy-cli` | 1.1.7 | 1.1.8 |
| `opencode-cli` | 1.18.7 | 1.18.8 |


### 🔄 Sesja aktualizacji: 2026-07-27 19:59

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | ⏭️ pominięto, ponieważ blokujący krok aktualizacji zakończył się błędem |
| 🛍️ App Store | Błąd |
| 🌐 Aplikacje z Internetu | Ostrzeżenie zakończono z ostrzeżeniami (niezweryfikowane) |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `imagemagick` | 7.1.2-27 | 7.1.2-28 |
| `openexr` | 3.4.13_1 | 3.4.13_2 |
| `openjph` | 0.30.1 | 0.31.0 |
| `supabase` | 2.109.1 | 2.110.0 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| OpenCode | 1.18.5 | 1.18.7 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `opencode-cli` | 1.18.5 | 1.18.7 |


### 🔄 Sesja aktualizacji: 2026-07-26 14:09

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | ⏭️ skipped because an earlier update step failed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | Błąd |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `certifi` | 2026.6.17 | 2026.7.22 |
| `sqlite` | 3.53.3 | 3.53.4 |
| `tesseract` | 5.5.2 | 5.5.3 |
| `uv` | 0.11.31 | 0.11.32 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Brave Browser | 150.1.92.143 | 150.1.92.144 |
| ChatGPT / Codex | 26.715.72359 | 26.721.41059 |
| Claude | 1.24012.1 | 1.24012.9 |
| OpenCode | 1.18.4 | 1.18.5 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `agy-cli` | 1.1.5 | 1.1.7 |
| `claude-code` | 2.1.218 | 2.1.220 |
| `opencode-cli` | 1.18.4 | 1.18.5 |
| `pnpm` | 11.16.0 | 11.17.0 |


### 🔄 Sesja aktualizacji: 2026-07-22 23:04

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | ⏭️ skipped because an earlier update step failed |
| 🛍️ App Store | Błąd |
| 🌐 Aplikacje z Internetu | Błąd |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `bats-core` | 1.13.0 | 1.14.0 |
| `stripe` | 1.43.8 | 1.44.0 |
| `unbound` | 1.25.1 | 1.25.2 |
| `uv` | 0.11.29 | 0.11.31 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Brave Browser | 150.1.92.141 | 150.1.92.143 |
| ChatGPT Atlas | 1.2026.126.0 | 1.2026.189.0 |
| Claude | 1.22209.0 | 1.24012.1 |
| Comet | 149.0.7827.1093 | 150.0.7871.228 |
| Gemini | 1.84.4.574 | 1.86.7.600 |
| Ledger Live | 4.10.0 | 4.11.0 |
| OpenCode | 1.18.3 | 1.18.4 |
| Perplexity | 26.27.0 | 26.28.1 |
| Trezor Suite | 26.6.1 | 26.7.2 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `agy-cli` | 1.1.4 | 1.1.5 |
| `claude-code` | 2.1.214 | 2.1.218 |
| `codex-cli` | 0.144.5 | 0.145.0 |
| `opencode-cli` | 1.18.3 | 1.18.4 |
| `pnpm` | 11.14.0 | 11.16.0 |


### 🔄 Sesja aktualizacji: 2026-07-18 08:37

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | ⏭️ skipped because an earlier update step failed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | Błąd |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `ca-certificates` | 2026-05-14 | 2026-07-16 |
| `dav1d` | 1.5.3 | 1.5.4 |
| `gogcli` | 0.34.0 | 0.34.1 |
| `hwloc` | 2.13.0 | 2.14.0 |
| `libraw` | 0.22.1 | 0.22.2 |
| `libtool` | 2.5.4 | 2.6.2 |
| `nss` | 3.125 | 3.126 |
| `openblas` | 0.3.33 | 0.3.34 |
| `python@3.11` | 3.11.15_3 | 3.11.15_4 |
| `svt-av1` | 4.1.0 | 4.2.0 |
| `uv` | 0.11.28 | 0.11.29 |
| `xsimd` | 14.2.0 | 14.3.0 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Antigravity | 2.2.1 | 2.3.1 |
| OpenCode | 1.17.20 | 1.18.3 |
| Visual Studio Code | 1.128.0 | 1.129.1 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `agy-cli` | 1.1.2 | 1.1.4 |
| `claude-code` | 2.1.209 | 2.1.214 |
| `codex-cli` | 0.144.4 | 0.144.5 |
| `opencode-cli` | 1.17.20 | 1.18.3 |
| `pnpm` | 11.13.0 | 11.14.0 |


### 🔄 Sesja aktualizacji: 2026-07-14 14:23

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | ⏭️ skipped because an earlier update step failed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | Błąd |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| ChatGPT / Codex | 26.707.62119 | 26.707.72221 |
| Claude | 1.20186.1 | 1.20186.9 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `agy-cli` | 1.1.1 | 1.1.2 |
| `claude-code` | 2.1.207 | 2.1.209 |
| `codex-cli` | 0.144.3 | 0.144.4 |


### 🔄 Sesja aktualizacji: 2026-07-14 00:26

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Microsoft Teams | 26072.608.4595.8484 | 26163.407.4839.8659 |

**🔍 Nowe aplikacje wykryte i dodane do APPLICATIONS.md:**
- Picsart
- WiFiman


### 🔄 Sesja aktualizacji: 2026-07-14 00:14

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | ⏭️ skipped because an earlier update step failed |
| 🛍️ App Store | Błąd |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | Błąd |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `stripe` | 1.43.7 | 1.43.8 |
| `tbb` | 2023.0.0 | 2023.1.0 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| OpenCode | 1.17.18 | 1.17.20 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `npm` | 12.0.0 | 12.0.1 |
| `opencode-cli` | 1.17.18 | 1.17.20 |
| `pnpm` | 11.12.0 | 11.13.0 |

**🔍 Nowe aplikacje wykryte i dodane do APPLICATIONS.md:**
- Picsart
- WiFiman


### 🔄 Sesja aktualizacji: 2026-07-13 10:13

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `fontconfig` | 2.18.1 | 2.18.2 |
| `gogcli` | 0.33.0 | 0.34.0 |
| `lame` | 3.100 | 4.0 |
| `libssh2` | 1.11.1_1 | 1.11.1_3 |
| `p11-kit` | 0.26.2 | 0.26.4 |
| `pytorch` | 2.12.1 | 2.13.0 |
| `stripe` | 1.43.6 | 1.43.7 |

**🆕 Nowe pakiety Homebrew w tej sesji:**
- `json-c` 0.19
- `mpg123` 1.33.6
- `pybind11` 3.0.4

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `agy-cli` | 1.1.0 | 1.1.1 |
| `claude-code` | 2.1.205 | 2.1.207 |
| `codex-cli` | 0.143.0 | 0.144.3 |
| `opencode-cli` | 1.17.16 | 1.17.18 |
| `pnpm` | 11.10.0 | 11.12.0 |


### 🔄 Sesja aktualizacji: 2026-07-09 10:48

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Google Chrome | 150.0.7871.101 | 150.0.7871.115 |
| OpenCode | 1.17.15 | 1.17.16 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.204 | 2.1.205 |
| `npm` | 11.18.0 | 12.0.0 |
| `opencode-cli` | 1.17.15 | 1.17.16 |


### 🔄 Sesja aktualizacji: 2026-07-08 16:24

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `cffi` | 2.0.0_1 | 2.1.0 |
| `gogcli` | 0.32.0 | 0.33.0 |
| `imagemagick` | 7.1.2-26 | 7.1.2-27 |
| `numpy` | 2.4.6 | 2.5.1 |
| `supabase` | 2.109.0 | 2.109.1 |
| `uv` | 0.11.26 | 0.11.28 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Docker Desktop | 4.79.0 | 4.80.0 |
| Ledger Live | 4.8.0 | 4.10.0 |
| Ledger Wallet | 4.8.0 | 4.10.0 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `agy-cli` | 1.0.16 | 1.1.0 |
| `claude-code` | 2.1.201 | 2.1.204 |
| `codex-cli` | 0.142.5 | 0.143.0 |
| `node` | 26.4.0 | 26.5.0 |
| `opencode-cli` | 1.17.13 | 1.17.15 |


### 🔄 Sesja aktualizacji: 2026-07-06 13:26

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | Błąd |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `ffmpeg` | 8.1.2 | 8.1.2_1 |
| `isl` | 0.27 | 0.28 |
| `jpeg-xl` | 0.11.2 | 0.12.0 |
| `openimageio` | 3.1.15.0 | 3.1.15.0_1 |


### 🔄 Sesja aktualizacji: 2026-07-05 14:21

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | Błąd |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `blackhole-2ch` *(cask)* | 0.7.0 | 0.7.1 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Spotify | 1.2.92.148 | 1.2.93.667 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `pnpm` | 11.9.0 | 11.10.0 |


### 🔄 Sesja aktualizacji: 2026-07-04 14:22

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | Błąd |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gogcli` | 0.31.1 | 0.32.0 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.200 | 2.1.201 |


### 🔄 Sesja aktualizacji: 2026-07-03 22:04

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | Błąd |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `create-dmg` | 1.2.3 | 1.3.0 |
| `gh` | 2.95.0 | 2.96.0 |
| `gnupg` | 2.5.20 | 2.5.21 |
| `libtiff` | 4.7.1_1 | 4.7.2 |
| `poppler` | 26.06.0 | 26.07.0 |
| `stripe` | 1.43.5 | 1.43.6 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `agy-cli` | 1.0.15 | 1.0.16 |
| `claude-code` | 2.1.198 | 2.1.200 |


### 🔄 Sesja aktualizacji: 2026-07-02 11:47

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | Błąd |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `jpeg-turbo` | 3.1.4.1 | 3.2.0 |
| `libevent` | 2.1.12_1 | 2.1.13 |
| `openimageio` | 3.1.14.1 | 3.1.15.0 |
| `pinentry` | 1.3.2 | 1.3.3 |
| `sdl3` | 3.4.10 | 3.4.12 |
| `stripe` | 1.43.2 | 1.43.5 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Claude | 1.17377.1 | 1.17377.2 |
| Gemini | 1.80.15.516 | 1.80.18.522 |
| OpenCode | 1.17.12 | 1.17.13 |
| Visual Studio Code | 1.126.0 | 1.127.0 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `agy-cli` | 1.0.14 | 1.0.15 |
| `claude-code` | 2.1.197 | 2.1.198 |
| `codex-cli` | 0.142.4 | 0.142.5 |
| `opencode-cli` | 1.17.12 | 1.17.13 |


### 🔄 Sesja aktualizacji: 2026-06-30 23:22

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gpgme` | 2.1.1 | 2.1.2 |
| `minizip-ng` | 4.2.1 | 4.2.2 |
| `openssl@3` | 3.6.2 | 3.6.3 |
| `supabase` | 2.108.0 | 2.109.0 |
| `uv` | 0.11.25 | 0.11.26 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| OpenCode | 1.17.11 | 1.17.12 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `agy-cli` | 1.0.13 | 1.0.14 |
| `claude-code` | 2.1.195 | 2.1.197 |
| `npm` | 11.17.0 | 11.18.0 |
| `opencode-cli` | 1.17.11 | 1.17.12 |


### 🔄 Sesja aktualizacji: 2026-06-29 10:39

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Codex | 26.623.42026 | 26.623.61825 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `codex-cli` | 0.142.3 | 0.142.4 |


### 🔄 Sesja aktualizacji: 2026-06-28 20:35

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `sqlite` | 3.53.2 | 3.53.3 |


### 🔄 Sesja aktualizacji: 2026-06-27 11:23

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `glib` | 2.88.1 | 2.88.2 |
| `gogcli` | 0.31.0 | 0.31.1 |
| `gpgme` | 2.1.0 | 2.1.1 |
| `libheif` | 1.23.0 | 1.23.1 |
| `pango` | 1.57.1 | 1.58.0 |
| `uv` | 0.11.24 | 0.11.25 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Codex | 26.623.31921 | 26.623.42026 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `agy-cli` | 1.0.12 | 1.0.13 |
| `claude-code` | 2.1.191 | 2.1.195 |
| `codex-cli` | 0.142.2 | 0.142.3 |


### 🔄 Sesja aktualizacji: 2026-06-25 21:22

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gogcli` | 0.30.0 | 0.31.0 |
| `supabase` | 2.107.0 | 2.108.0 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Codex | 26.616.81150 | 26.623.30605 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.187 | 2.1.191 |
| `codex-cli` | 0.142.0 | 0.142.2 |
| `node` | 26.3.1 | 26.4.0 |
| `opencode-cli` | 1.17.9 | 1.17.11 |


### 🔄 Sesja aktualizacji: 2026-06-22 11:51

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gogcli` | 0.29.0 | 0.30.0 |


### 🔄 Sesja aktualizacji: 2026-06-21 13:42

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `fmt` | 12.1.0 | 12.2.0 |
| `jq` | 1.8.1 | 1.8.2 |
| `libvmaf` | 3.1.0 | 3.2.0 |
| `onnx` | 1.21.0_2 | 1.22.0 |
| `pytorch` | 2.12.0_2 | 2.12.1 |
| `scipy` | 1.17.1 | 1.18.0 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Codex | 26.616.41845 | 26.616.51431 |
| OpenCode | 1.17.8 | 1.17.9 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.183 | 2.1.185 |
| `opencode-cli` | 1.17.8 | 1.17.9 |


### 🔄 Sesja aktualizacji: 2026-06-20 12:02

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

*Brak zaktualizowanych pakietów w tej sesji.*


### 🔄 Sesja aktualizacji: 2026-06-20 09:56

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gogcli` | 0.28.0 | 0.29.0 |
| `onnx` | 1.21.0_1 | 1.21.0_2 |
| `openexr` | 3.4.12_2 | 3.4.13 |
| `protobuf` | 35.0 | 35.1 |
| `pytorch` | 2.12.0_1 | 2.12.0_2 |
| `uv` | 0.11.22 | 0.11.23 |

**🔍 Nowe aplikacje wykryte i dodane do APPLICATIONS.md:**
- CapCut


### 🔄 Sesja aktualizacji: 2026-06-19 09:46

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `certifi` | 2026.5.20 | 2026.6.17 |
| `uv` | 0.11.21 | 0.11.22 |
| `blackhole-2ch` *(cask)* | 0.6.1 | 0.7.0 |

**🆕 Nowe pakiety Homebrew w tej sesji:**
- `sdl2-compat` 2.32.70
- `sdl3` 3.4.10

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.181 | 2.1.183 |
| `pnpm` | 11.7.0 | 11.8.0 |


### 🔄 Sesja aktualizacji: 2026-06-18 12:46

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `ffmpeg` | 8.1.1 | 8.1.2 |
| `gcc` | 15.3.0 | 16.1.0 |
| `gh` | 2.94.0 | 2.95.0 |
| `libidn` | 1.43 | 1.44 |
| `libomp` | 22.1.7 | 22.1.8 |
| `openexr` | 3.4.12_1 | 3.4.12_2 |
| `openjph` | 0.28.1 | 0.29.0 |
| `supabase` | 2.106.0 | 2.107.0 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Firefox Developer Edition | 152.0 | 153.0 |
| OpenCode | 1.17.7 | 1.17.8 |
| Trezor Suite | 26.5.2 | 26.6.1 |
| Visual Studio Code | 1.124.2 | 1.125.0 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.179 | 2.1.181 |
| `codex-cli` | 0.140.0 | 0.141.0 |
| `node` | 26.3.0 | 26.3.1 |
| `opencode-cli` | 1.17.7 | 1.17.8 |


### 🔄 Sesja aktualizacji: 2026-06-17 15:18

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gcc` | 15.2.0_1 | 15.3.0 |


### 🔄 Sesja aktualizacji: 2026-06-17 08:04

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gogcli` | 0.27.0 | 0.28.0 |
| `pugixml` | 1.15 | 1.16 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `agy-cli` | 1.0.8 | 1.0.9 |
| `claude-code` | 2.1.177 | 2.1.179 |
| `codex-cli` | 0.139.0 | 0.140.0 |


### 🔄 Sesja aktualizacji: 2026-06-15 13:22

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gogcli` | 0.25.0 | 0.27.0 |
| `openimageio` | 3.1.14.0 | 3.1.14.1 |
| `pystring` | 1.1.5 | 1.2.0 |
| `python@3.14` | 3.14.5 | 3.14.6 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `opencode-cli` | 1.17.4 | 1.17.7 |
| `pnpm` | 11.6.0 | 11.7.0 |


### 🔄 Sesja aktualizacji: 2026-06-13 11:06

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gogcli` | 0.24.0 | 0.25.0 |
| `nss` | 3.124 | 3.125 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Codex | 26.609.30741 | 26.609.41114 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `agy-cli` | 1.0.7 | 1.0.8 |
| `claude-code` | 2.1.175 | 2.1.177 |


### 🔄 Sesja aktualizacji: 2026-06-12 10:04

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gogcli` | 0.23.0 | 0.24.0 |
| `openexr` | 3.4.12 | 3.4.12_1 |
| `openjph` | 0.27.4 | 0.28.1 |
| `python@3.11` | 3.11.15_1 | 3.11.15_3 |
| `supabase` | 2.105.0 | 2.106.0 |
| `uv` | 0.11.20 | 0.11.21 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Antigravity | 2.0.11 | 2.1.4 |
| Ledger Live | 4.6.1 | 4.8.0 |
| Ledger Wallet | 4.6.1 | 4.8.0 |
| Visual Studio Code | 1.124.0 | 1.124.2 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.173 | 2.1.175 |
| `npm` | 11.16.0 | 11.17.0 |
| `opencode-cli` | 1.17.3 | 1.17.4 |
| `pnpm` | 11.5.3 | 11.6.0 |


### 🔄 Sesja aktualizacji: 2026-06-11 12:02

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | Błąd |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gh` | 2.93.0 | 2.94.0 |
| `uv` | 0.11.19 | 0.11.20 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.170 | 2.1.173 |
| `opencode-cli` | 1.17.2 | 1.17.3 |


### 🔄 Sesja aktualizacji: 2026-06-10 19:30

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `poppler` | 26.04.0 | 26.06.0 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Visual Studio Code | 1.123.0 | 1.124.0 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `opencode-cli` | 1.17.0 | 1.17.2 |
| `pnpm` | 11.5.2 | 11.5.3 |


### 🔄 Sesja aktualizacji: 2026-06-10 11:30

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `agy-cli` | 1.0.6 | 1.0.7 |
| `claude-code` | 2.1.169 | 2.1.170 |
| `codex-cli` | 0.138.0 | 0.139.0 |
| `gemini-cli` | 0.45.2 | 0.46.0 |
| `opencode-cli` | 1.16.2 | 1.17.0 |


### 🔄 Sesja aktualizacji: 2026-06-09 14:44

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

*Brak zaktualizowanych pakietów w tej sesji.*


### 🔄 Sesja aktualizacji: 2026-06-09 11:40

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gogcli` | 0.22.0 | 0.23.0 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.168 | 2.1.169 |
| `codex-cli` | 0.137.0 | 0.138.0 |


### 🔄 Sesja aktualizacji: 2026-06-08 21:24

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

*Brak zaktualizowanych pakietów w tej sesji.*


### 🔄 Sesja aktualizacji: 2026-06-08 21:19

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🔍 Nowe aplikacje wykryte i dodane do APPLICATIONS.md:**
- Arc
- Bruno
- Figma
- TablePlus

*Brak zaktualizowanych pakietów w tej sesji.*


### 🔄 Sesja aktualizacji: 2026-06-08 21:07

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| LM Studio | 0.4.16+1 | 0.4.16+2 |
| Microsoft Excel | 16.109.3 | 16.110 |
| Microsoft OneNote | 16.109.3 | 16.110 |
| Microsoft Outlook | 16.109.3 | 16.110 |
| Microsoft PowerPoint | 16.109.3 | 16.110 |
| Microsoft Word | 16.109.3 | 16.110 |


### 🔄 Sesja aktualizacji: 2026-06-08 08:42

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gogcli` | 0.21.0 | 0.22.0 |


### 🔄 Sesja aktualizacji: 2026-06-07 10:50

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.167 | 2.1.168 |


### 🔄 Sesja aktualizacji: 2026-06-07 00:53

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Codex | 26.602.30954 | 26.602.40724 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `agy-cli` | 1.0.5 | 1.0.6 |
| `claude-code` | 2.1.165 | 2.1.167 |
| `gemini-cli` | 0.45.1 | 0.45.2 |

**🔍 Nowe aplikacje wykryte i dodane do APPLICATIONS.md:**
- DJI Assistant 2(Consumer Drones Series)


### 🔄 Sesja aktualizacji: 2026-06-04 10:30

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `fontconfig` | 2.18.0 | 2.18.1 |
| `libde265` | 1.1.0 | 1.1.1 |
| `uv` | 0.11.18 | 0.11.19 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `agy-cli` | 1.0.4 | 1.0.5 |
| `claude-code` | 2.1.161 | 2.1.162 |
| `codex-cli` | 0.136.0 | 0.137.0 |


### 🔄 Sesja aktualizacji: 2026-06-03 11:06

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `harfbuzz` | 14.2.0 | 14.2.1 |
| `libomp` | 22.1.6 | 22.1.7 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.160 | 2.1.161 |
| `gemini-cli` | 0.44.1 | 0.45.0 |


### 🔄 Sesja aktualizacji: 2026-06-02 23:05

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Antigravity IDE | 2.0.3 | 2.0.4 |
| Codex | 26.527.60818 | 26.601.20914 |
| Microsoft Excel | 16.109.2 | 16.109.3 |
| Microsoft OneNote | 16.109.2 | 16.109.3 |
| Microsoft Outlook | 16.109.2 | 16.109.3 |
| Microsoft PowerPoint | 16.109.2 | 16.109.3 |
| Microsoft Word | 16.109.2 | 16.109.3 |
| Perplexity | 26.20.0 | 26.22.0 |


### 🔄 Sesja aktualizacji: 2026-06-02 10:56

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gogcli` | 0.20.0 | 0.21.0 |
| `graphite2` | 1.3.14 | 1.3.15 |
| `supabase` | 2.103.0 | 2.104.0 |
| `uv` | 0.11.17 | 0.11.18 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `agy-cli` | 1.0.3 | 1.0.4 |
| `claude-code` | 2.1.159 | 2.1.160 |
| `codex-cli` | 0.135.0 | 0.136.0 |
| `pnpm` | 11.5.0 | 11.5.1 |


### 🔄 Sesja aktualizacji: 2026-05-31 19:48

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

*Brak zaktualizowanych pakietów w tej sesji.*


### 🔄 Sesja aktualizacji: 2026-05-30 11:00

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `libheif` | 1.22.2 | 1.23.0 |
| `supabase` | 2.101.0 | 2.102.0 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Codex | 26.527.30818 | 26.527.31326 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.156 | 2.1.158 |


### 🔄 Sesja aktualizacji: 2026-05-29 10:06

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `uv` | 0.11.16 | 0.11.17 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.153 | 2.1.156 |
| `codex-cli` | 0.134.0 | 0.135.0 |
| `gemini-cli` | 0.44.0 | 0.44.1 |
| `opencode-cli` | 1.15.11 | 1.15.12 |


### 🔄 Sesja aktualizacji: 2026-05-28 08:29

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gh` | 2.92.0 | 2.93.0 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Trezor Suite | 26.5.1 | 26.5.2 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `agy-cli` | 1.0.2 | 1.0.3 |
| `claude-code` | 2.1.152 | 2.1.153 |
| `gemini-cli` | 0.43.0 | 0.44.0 |
| `npm` | 11.15.0 | 11.16.0 |
| `pnpm` | 11.3.0 | 11.4.0 |


### 🔄 Sesja aktualizacji: 2026-05-27 13:56

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `imagemagick` | 7.1.2-23 | 7.1.2-24 |
| `libde265` | 1.0.19 | 1.1.0 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Codex | 26.519.41501 | 26.519.81530 |
| OpenCode | 1.15.10 | 1.15.11 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.150 | 2.1.152 |
| `codex-cli` | 0.133.0 | 0.134.0 |
| `opencode-cli` | 1.15.10 | 1.15.11 |
| `qwen-code` | 0.16.1 | 0.16.2 |


### 🔄 Sesja aktualizacji: 2026-05-26 13:02

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

*Brak zaktualizowanych pakietów w tej sesji.*


### 🔄 Sesja aktualizacji: 2026-05-26 12:40

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `libheif` | 1.22.0 | 1.22.2 |


### 🔄 Sesja aktualizacji: 2026-05-25 17:46

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `fontconfig` | 2.17.1 | 2.18.0 |
| `openexr` | 3.4.11 | 3.4.12 |

**🔍 Nowe aplikacje wykryte i dodane do APPLICATIONS.md:**
- Copilot
- Whisper Transcription


### 🔄 Sesja aktualizacji: 2026-05-24 20:23

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🔍 Nowe aplikacje wykryte i dodane do APPLICATIONS.md:**
- Copilot

*Brak zaktualizowanych pakietów w tej sesji.*


### 🔄 Sesja aktualizacji: 2026-05-23 12:07

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

*Brak zaktualizowanych pakietów w tej sesji.*


### 🔄 Sesja aktualizacji: 2026-05-23 11:37

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | Błąd |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `certifi` | 2026.4.22 | 2026.5.20 |
| `ghostscript` | 10.07.0 | 10.07.1 |
| `libomp` | 22.1.5 | 22.1.6 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Codex | 26.519.31651 | 26.519.41501 |
| OpenCode | 1.15.7 | 1.15.10 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.148 | 2.1.150 |


### 🔄 Sesja aktualizacji: 2026-05-22 21:11

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | Błąd |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gogcli` | 0.18.0 | 0.19.0 |


### 🔄 Sesja aktualizacji: 2026-05-22 10:36

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | Błąd |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gogcli` | 0.17.0 | 0.18.0 |
| `onnx` | 1.21.0 | 1.21.0_1 |
| `protobuf` | 34.1 | 35.0 |
| `pytorch` | 2.12.0 | 2.12.0_1 |
| `supabase` | 2.100.1 | 2.101.0 |
| `uv` | 0.11.15 | 0.11.16 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Codex | 26.513.31313 | 26.519.31651 |
| OpenCode | 1.15.6 | 1.15.7 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.146 | 2.1.148 |
| `codex-cli` | 0.132.0 | 0.133.0 |
| `gemini-cli` | 0.42.0 | 0.43.0 |
| `pnpm` | 11.1.3 | 11.2.2 |


### 🔄 Sesja aktualizacji: 2026-05-21 09:03

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gnutls` | 3.8.13_1 | 3.8.13_2 |
| `libheif` | 1.21.2_2 | 1.22.0 |
| `unbound` | 1.25.0 | 1.25.1 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| OpenCode | 1.15.5 | 1.15.6 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.145 | 2.1.146 |
| `node` | 26.1.0 | 26.2.0 |
| `npm` | 11.14.1 | 11.15.0 |


### 🔄 Sesja aktualizacji: 2026-05-20 11:30

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🔍 Nowe aplikacje wykryte i dodane do APPLICATIONS.md:**
- IPMIView
- Inkscape

*Brak zaktualizowanych pakietów w tej sesji.*


### 🔄 Sesja aktualizacji: 2026-05-20 09:22

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `libde265` | 1.0.18 | 1.0.19 |
| `numpy` | 2.4.5 | 2.4.6 |
| `supabase` | 2.100.0 | 2.100.1 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.144 | 2.1.145 |
| `codex-cli` | 0.131.0 | 0.132.0 |

**🔍 Nowe aplikacje wykryte i dodane do APPLICATIONS.md:**
- Inkscape

**🗑️ Aplikacje do usunięcia z listy (odinstalowane):**
- MacWhisper *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Notion *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Notion Calendar *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*


### 🔄 Sesja aktualizacji: 2026-05-19 09:05

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | Błąd |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gpgme` | 2.0.1 | 2.1.0 |
| `gpgmepp` | 2.0.0 | 2.1.0 |
| `numpy` | 2.4.4 | 2.4.5 |
| `supabase` | 2.98.2 | 2.100.0 |
| `uv` | 0.11.14 | 0.11.15 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| OpenCode | 1.15.4 | 1.15.5 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.143 | 2.1.144 |
| `codex-cli` | 0.130.0 | 0.131.0 |
| `pnpm` | 11.1.2 | 11.1.3 |

**🔍 Nowe aplikacje wykryte i dodane do APPLICATIONS.md:**
- Cursor
- Inkscape

**🗑️ Aplikacje do usunięcia z listy (odinstalowane):**
- MacWhisper *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Notion *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Notion Calendar *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*


### 🔄 Sesja aktualizacji: 2026-05-14 12:33

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `ca-certificates` | 2026-03-19 | 2026-05-14 |
| `gnupg` | 2.5.19 | 2.5.20 |
| `libksba` | 1.7.0 | 1.8.0 |
| `opencolorio` | 2.5.1_1 | 2.5.2 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Google Drive | 124.0 | 125.0 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.140 | 2.1.141 |

**🔍 Nowe aplikacje wykryte i dodane do APPLICATIONS.md:**
- Inkscape

**🗑️ Aplikacje do usunięcia z listy (odinstalowane):**
- MacWhisper *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Notion *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Notion Calendar *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*


### 🔄 Sesja aktualizacji: 2026-05-13 19:15

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🔍 Nowe aplikacje wykryte i dodane do APPLICATIONS.md:**
- Inkscape

**🗑️ Aplikacje do usunięcia z listy (odinstalowane):**
- MacWhisper *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Notion *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Notion Calendar *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*

*Brak zaktualizowanych pakietów w tej sesji.*


### 🔄 Sesja aktualizacji: 2026-05-13 18:52

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | Błąd |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `expat` | 2.8.0 | 2.8.1 |
| `imagemagick` | 7.1.2-21 | 7.1.2-22 |
| `python@3.14` | 3.14.4_1 | 3.14.5 |
| `sqlite` | 3.53.0 | 3.53.1 |
| `uv` | 0.11.13 | 0.11.14 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.139 | 2.1.140 |
| `gemini-cli` | 0.41.2 | 0.42.0 |
| `node` | 24.15.0 | 26.1.0 |
| `pnpm` | 11.1.0 | 11.1.1 |

**🔍 Nowe aplikacje wykryte i dodane do APPLICATIONS.md:**
- Inkscape

**🗑️ Aplikacje do usunięcia z listy (odinstalowane):**
- MacWhisper *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*


### 🔄 Sesja aktualizacji: 2026-05-07 09:27

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | Błąd |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `supabase` | 2.98.1 | 2.98.2 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `node` | 24.15.0 | 26.0.0 |


### 🔄 Sesja aktualizacji: 2026-05-06 10:07

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `node` | 24.15.0 | 26.0.0 |

**🔍 Nowe aplikacje wykryte i dodane do APPLICATIONS.md:**
- Ascendo


### 🔄 Sesja aktualizacji: 2026-05-04 11:04

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

*Brak zaktualizowanych pakietów w tej sesji.*


### 🔄 Sesja aktualizacji: 2026-05-03 12:59

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| OpenCode | 1.14.31 | 1.14.33 |


### 🔄 Sesja aktualizacji: 2026-05-01 14:01

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

*Brak zaktualizowanych pakietów w tej sesji.*


### 🔄 Sesja aktualizacji: 2026-05-01 12:19

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `openexr` | 3.4.10 | 3.4.11 |
| `tbb` | 2022.3.0 | 2023.0.0 |
| `xsimd` | 14.1.0 | 14.2.0 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.123 | 2.1.126 |
| `codex-cli` | 0.125.0 | 0.128.0 |
| `gemini-cli` | 0.40.0 | 0.40.1 |


### 🔄 Sesja aktualizacji: 2026-04-29 17:25

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🔍 Nowe aplikacje wykryte i dodane do APPLICATIONS.md:**
- Obsidian

*Brak zaktualizowanych pakietów w tej sesji.*


### 🔄 Sesja aktualizacji: 2026-04-29 17:12

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | Błąd |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gh` | 2.91.0 | 2.92.0 |
| `python@3.11` | 3.11.15 | 3.11.15_1 |
| `python@3.14` | 3.14.4 | 3.14.4_1 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Claude | 1.4758.0 | 1.5354.0 |
| Codex | 26.422.62136 | 26.422.71525 |
| Microsoft Excel | 16.108.1 | 16.108.2 |
| Microsoft OneNote | 16.108.1 | 16.108.2 |
| Microsoft Outlook | 16.108.1 | 16.108.2 |
| Microsoft PowerPoint | 16.108.1 | 16.108.2 |
| Microsoft Word | 16.108.1 | 16.108.2 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.121 | 2.1.123 |
| `gemini-cli` | 0.39.1 | 0.40.0 |


### 🔄 Sesja aktualizacji: 2026-04-28 14:20

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gogcli` | 0.13.0 | 0.14.0 |
| `minizip-ng` | 4.2.0 | 4.2.1 |
| `uv` | 0.11.7 | 0.11.8 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.119 | 2.1.121 |


### 🔄 Sesja aktualizacji: 2026-04-27 16:38

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `awk` | 20251225 | 20260426 |
| `minizip-ng` | 4.1.2 | 4.2.0 |
| `supabase` | 2.90.0 | 2.95.4 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| OpenCode | 1.14.25 | 1.14.28 |


### 🔄 Sesja aktualizacji: 2026-04-26 19:24

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `minizip-ng` | 4.1.1 | 4.1.2 |


### 🔄 Sesja aktualizacji: 2026-04-26 10:38

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

*Brak zaktualizowanych pakietów w tej sesji.*


### 🔄 Sesja aktualizacji: 2026-04-25 09:03

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `expat` | 2.7.5 | 2.8.0 |
| `openblas` | 0.3.32 | 0.3.33 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Trezor Suite | 26.3.3 | 26.4.2 |
| Warp | 0.2026.04.15.08.45.02 | 0.2026.04.22.08.46.02 |


### 🔄 Sesja aktualizacji: 2026-04-24 09:32

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `certifi` | 2026.2.25 | 2026.4.22 |
| `highway` | 1.3.0 | 1.4.0 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Codex | 26.422.20832 | 26.422.21637 |
| OpenCode | 1.14.21 | 1.14.22 |
| Proton Mail | 1.12.1 | 1.13.0 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.118 | 2.1.119 |
| `gemini-cli` | 0.39.0 | 0.39.1 |


### 🔄 Sesja aktualizacji: 2026-04-23 09:03

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `libomp` | 22.1.3 | 22.1.4 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Firefox Developer Edition | 150.0 | 151.0 |
| MacWhisper | 13.19.2 | 13.20 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.117 | 2.1.118 |
| `codex-cli` | 0.122.0 | 0.123.0 |
| `gemini-cli` | 0.38.2 | 0.39.0 |
| `npm` | 11.12.1 | 11.13.0 |
| `pnpm` | 10.33.0 | 10.33.1 |


### 🔄 Sesja aktualizacji: 2026-04-22 10:30

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `imagemagick` | 7.1.2-19 | 7.1.2-21 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Google Chrome | 147.0.7727.57 | 147.0.7727.102 |
| Microsoft PowerPoint | 16.108 | 16.108.1 |
| Microsoft Word | 16.108 | 16.108.1 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.116 | 2.1.117 |
| `opencode-cli` | 1.14.19 | 1.14.20 |


### 🔄 Sesja aktualizacji: 2026-04-21 12:00

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `coreutils` | 9.10 | 9.11 |
| `gogcli` | 0.12.0 | 0.13.0 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| MacWhisper | 13.19.1 | 13.19.2 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `claude-code` | 2.1.114 | 2.1.116 |


### 🔄 Sesja aktualizacji: 2026-04-20 13:33

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `ffmpeg` | 8.1 | 8.1_1 |
| `libheif` | 1.21.2_1 | 1.21.2_2 |
| `x265` | 4.1 | 4.2 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `bun` | 1.3.12 | 1.3.13 |
| `opencode-cli` | 1.14.17 | 1.14.19 |


### 🔄 Sesja aktualizacji: 2026-04-19 09:46

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `libmpc` | 1.4.0 | 1.4.1 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Spotify | 1.2.63.394 | 1.2.87.415 |

**🧰 Native CLI + npm — wykryte zmiany wersji:**

| Narzędzie | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| `opencode-cli` | 1.4.11 | 1.14.17 |


### 🔄 Sesja aktualizacji: 2026-04-18 14:50

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🧰 Native CLI + npm | OK completed |
| 🍺 Homebrew | OK completed |


### 🔄 Sesja aktualizacji: 2026-04-18 13:52

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `simdjson` | 4.6.1 | 4.6.2 |

**🗑️ Aplikacje do usunięcia z listy (odinstalowane):**
- Opera *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Codex Desktop (OpenAI) *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Comet (Perplexity Browser) *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- opencode Desktop *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Perplexity Desktop *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Microsoft Defender *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Inkscape *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- VirtualBox *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Blackmagic Proxy Generator Lite *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Blackmagic RAW Player *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- DaVinci Resolve *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Ledger Live (lub Ledger Wallet) *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*


### 🔄 Sesja aktualizacji: 2026-04-17 12:53

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🍺 Homebrew | OK completed |

**🗑️ Aplikacje do usunięcia z listy (odinstalowane):**
- Opera *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Codex Desktop (OpenAI) *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Comet (Perplexity Browser) *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- opencode Desktop *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Perplexity Desktop *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Microsoft Defender *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Blackmagic RAW Player *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- DaVinci Resolve *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Ledger Live (lub Ledger Wallet) *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*


### 🔄 Sesja aktualizacji: 2026-04-17 09:07

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gemini-cli` | 0.38.0 | 0.38.1 |
| `opencode` | 1.4.6 | 1.4.7 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| ChatGPT | 1.2026.051 | 1.2026.097 |
| Claude | 1.2773.0 | 1.3109.0 |
| Codex | 26.415.20818 | 26.415.21839 |
| opencode | 1.4.6 | 1.4.7 |

**🗑️ Aplikacje do usunięcia z listy (odinstalowane):**
- Opera *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Codex Desktop (OpenAI) *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Comet (Perplexity Browser) *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- opencode Desktop *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Perplexity Desktop *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Microsoft Defender *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Blackmagic RAW Player *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- DaVinci Resolve *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Ledger Live (lub Ledger Wallet) *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*


### 🔄 Sesja aktualizacji: 2026-04-16 09:34

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gemini-cli` | 0.37.2 | 0.38.0 |
| `uv` | 0.11.6 | 0.11.7 |

**🗑️ Aplikacje do usunięcia z listy (odinstalowane):**
- Opera *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Codex Desktop (OpenAI) *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Comet (Perplexity Browser) *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- opencode Desktop *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Perplexity Desktop *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Microsoft Defender *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Blackmagic RAW Player *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- DaVinci Resolve *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Ledger Live (lub Ledger Wallet) *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*


### 🔄 Sesja aktualizacji: 2026-04-15 10:48

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gemini-cli` | 0.37.1 | 0.37.2 |
| `libarchive` | 3.8.6 | 3.8.7 |
| `opencode` | 1.4.3 | 1.4.6 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| MacWhisper | 13.19 | 13.19.1 |

**🗑️ Aplikacje do usunięcia z listy (odinstalowane):**
- Opera *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Codex Desktop (OpenAI) *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Comet (Perplexity Browser) *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- opencode Desktop *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Perplexity Desktop *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Microsoft Defender *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Blackmagic RAW Player *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- DaVinci Resolve *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*
- Ledger Live (lub Ledger Wallet) *(oznaczone w APPLICATIONS.md — usuń wiersz ręcznie)*


### 🚀 Migracja na nowy MacBook: 2026-04-14 17:23

| Parametr | Wartość |
|----------|---------|
| 🖥️ Nowy komputer | MacBook-MK |
| 👤 Użytkownik | mk |
| 🍎 macOS | 26.4.1 |
| 💻 Architektura | Apple Silicon arm64 |
| 📂 Ścieżka projektu | /Users/mk/Dev_Env/macOS_updates |
| 📅 Data migracji | 2026-04-14 |

*Migracja wykonana przez migration_setup.sh — ścieżki, wersje i zależności zaktualizowane.*


### 🔄 Sesja aktualizacji: 2026-04-14 11:58

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `giflib` | 6.1.2 | 6.1.3 |
| `node` | 25.9.0_1 | 25.9.0_2 |
| `supabase` | 2.84.2 | 2.90.0 |

**🆕 Nowe pakiety Homebrew w tej sesji:**
- `merve` 1.2.2
- `nbytes` 0.1.4
- `simdutf` 8.2.0

### 🔄 Sesja aktualizacji: 2026-04-13 11:55

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `imagemagick` | 7.1.2-18 | 7.1.2-19 |

### 🔄 Sesja aktualizacji: 2026-04-12 12:55

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `pystring` | 1.1.4 | 1.1.5 |
| `qwen-code` | 0.14.2 | 0.14.3 |
| `sqlite` | 3.52.0 | 3.53.0 |

### 🔄 Sesja aktualizacji: 2026-04-11 11:13

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `libheif` | 1.21.2 | 1.21.2_1 |
| `libpng` | 1.6.56 | 1.6.57 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Codex | 26.406.31014 | 26.409.20454 |

**🔍 Nowe aplikacje wykryte i dodane do APPLICATIONS.md:**


### 🔄 Sesja aktualizacji: 2026-04-10 11:19

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `bun` | 1.3.11 | 1.3.12 |
| `gemini-cli` | 0.37.0 | 0.37.1 |
| `opencode` | 1.4.1 | 1.4.3 |
| `python@3.14` | 3.14.3_1 | 3.14.4 |
| `uv` | 0.11.5 | 0.11.6 |

### 🔄 Sesja aktualizacji: 2026-04-09 10:46

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gemini-cli` | 0.36.0 | 0.37.0 |
| `opencode` | 1.4.0 | 1.4.1 |
| `openssl@3` | 3.6.1 | 3.6.2 |
| `qwen-code` | 0.14.1 | 0.14.2 |
| `uv` | 0.11.4 | 0.11.5 |

### 🔄 Sesja aktualizacji: 2026-04-07 22:59

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `opencode` | 1.3.15 | 1.3.17 |
| `qwen-code` | 0.14.0 | 0.14.1 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Claude | 1.569.0 | 1.1062.0 |
| Microsoft Excel | 16.107.3 | 16.107.4 |
| Microsoft OneNote | 16.107.3 | 16.107.4 |
| Microsoft Outlook | 16.107.3 | 16.107.4 |
| Microsoft PowerPoint | 16.107.3 | 16.107.4 |
| Microsoft Word | 16.107.3 | 16.107.4 |
| opencode | 1.3.15 | 1.3.17 |


### 🔄 Sesja aktualizacji: 2026-04-07 07:56

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `libraw` | 0.22.0_1 | 0.22.1 |
| `openimageio` | 3.1.12.0 | 3.1.12.0_1 |

### 🔄 Sesja aktualizacji: 2026-04-05 22:21

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `harfbuzz` | 14.0.0 | 14.1.0 |
| `opencode` | 1.3.14 | 1.3.15 |
| `simdjson` | 4.6.0 | 4.6.1 |


### 🔄 Sesja aktualizacji: 2026-04-04 22:11

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `aom` | 3.13.2 | 3.13.3 |
| `libvmaf` | 3.0.0 | 3.1.0 |
| `node` | 25.9.0 | 25.9.0_1 |
| `opencode` | 1.3.13 | 1.3.14 |
| `openexr` | 3.4.8 | 3.4.9 |
| `qwen-code` | 0.13.2 | 0.14.0 |
| `simdjson` | 4.4.2 | 4.6.0 |
| `supabase` | 2.75.0 | 2.84.2 |


### 🔄 Sesja aktualizacji: 2026-04-02 14:08

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gemini-cli` | 0.35.3 | 0.36.0 |
| `harfbuzz` | 13.2.1 | 14.0.0 |
| `node` | 25.8.2 | 25.9.0 |
| `uv` | 0.11.2 | 0.11.3 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Google Drive | 122.0 | 123.0 |


### 🔄 Sesja aktualizacji: 2026-04-01 14:03

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | OK completed |
| 🛍️ App Store | OK completed |
| 🌐 Aplikacje z Internetu | OK completed |
| 🍺 Homebrew | OK completed |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `opencode` | 1.3.10 | 1.3.13 |
| `openimageio` | 3.1.11.0 | 3.1.12.0 |
| `xz` | 5.8.2 | 5.8.3 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Antigravity | 1.21.6 | 1.21.9 |
| Microsoft Excel | 16.107.2 | 16.107.3 |
| Microsoft OneNote | 16.107.2 | 16.107.3 |
| Microsoft Outlook | 16.107.2 | 16.107.3 |
| Microsoft PowerPoint | 16.107.2 | 16.107.3 |
| Microsoft Word | 16.107.2 | 16.107.3 |
| opencode | 1.3.10 | 1.3.13 |


### 🚀 Migracja na nowy MacBook: 2026-03-31 16:53

| Parametr | Wartość |
|----------|---------|
| 🖥️ Nowy komputer | MacBook-MK |
| 👤 Użytkownik | mk |
| 🍎 macOS | 26.4 |
| 💻 Architektura | Apple Silicon arm64 |
| 📂 Ścieżka projektu | /Users/mk/Dev_Env/macOS_updates |
| 📅 Data migracji | 2026-03-31 |

*Migracja wykonana przez migration_setup.sh — ścieżki, wersje i zależności zaktualizowane.*


### 🔄 Sesja aktualizacji: 2026-03-31 11:48

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | ✅ zakończony |
| 🛍️ App Store | ✅ zakończony |
| 🌐 Aplikacje z Internetu | ✅ zakończony |
| 🍺 Homebrew | ✅ zakończony |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `opencode` | 1.3.7 | 1.3.9 |
| `perl` | 5.42.1_1 | 5.42.2 |
| `qwen-code` | 0.13.1 | 0.13.2 |

**🔍 Nowe aplikacje wykryte i dodane do APPLICATIONS.md:**
- Inkscape


### 🔄 Sesja aktualizacji: 2026-03-30 14:08

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | ✅ zakończony |
| 🛍️ App Store | ✅ zakończony |
| 🌐 Aplikacje z Internetu | ✅ zakończony |
| 🍺 Homebrew | ✅ zakończony |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `jpeg-turbo` | 3.1.4 | 3.1.4.1 |
| `libngtcp2` | 1.21.0 | 1.22.0 |
| `numpy` | 2.4.3 | 2.4.4 |
| `opencode` | 1.3.5 | 1.3.7 |

**🔍 Nowe aplikacje wykryte i dodane do APPLICATIONS.md:**
- Inkscape


### 🔄 Sesja aktualizacji: 2026-03-29 17:26

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | ✅ zakończony |
| 🛍️ App Store | ✅ zakończony |
| 🌐 Aplikacje z Internetu | ✅ zakończony |
| 🍺 Homebrew | ✅ zakończony |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `opencode` | 1.3.3 | 1.3.5 |


### 🔄 Sesja aktualizacji: 2026-03-28 20:11

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | ✅ zakończony |
| 🛍️ App Store | ✅ zakończony |
| 🌐 Aplikacje z Internetu | ✅ zakończony |
| 🍺 Homebrew | ✅ zakończony |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gemini-cli` | 0.35.2 | 0.35.3 |
| `libpng` | 1.6.55 | 1.6.56 |
| `onnx` | 1.20.1_5 | 1.21.0 |
| `openai-whisper` | 20250625_3 | 20250625_4 |


### 🔄 Sesja aktualizacji: 2026-03-28 10:25

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | ✅ zakończony |
| 🛍️ App Store | ✅ zakończony |
| 🌐 Aplikacje z Internetu | ✅ zakończony |
| 🍺 Homebrew | ✅ zakończony |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `jpeg-turbo` | 3.1.3 | 3.1.4 |
| `openexr` | 3.4.7 | 3.4.8 |
| `qwen-code` | 0.13.0 | 0.13.1 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Trezor Suite | 26.3.2 | 26.3.3 |


### 🔄 Sesja aktualizacji: 2026-03-27 12:41

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | ✅ zakończony |
| 🛍️ App Store | ✅ zakończony |
| 🌐 Aplikacje z Internetu | ✅ zakończony |
| 🍺 Homebrew | ✅ zakończony |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gemini-cli` | 0.35.1 | 0.35.2 |
| `opencode` | 1.3.2 | 1.3.3 |
| `uv` | 0.11.1 | 0.11.2 |

**🔍 Nowe aplikacje wykryte i dodane do APPLICATIONS.md:**


### 🔄 Sesja aktualizacji: 2026-03-26 10:52

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | ✅ zakończony |
| 🛍️ App Store | ✅ zakończony |
| 🌐 Aplikacje z Internetu | ✅ zakończony |
| 🍺 Homebrew | ✅ zakończony |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `gemini-cli` | 0.35.0 | 0.35.1 |
| `libomp` | 22.1.1 | 22.1.2 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Firefox Developer Edition | 149.0 | 150.0 |


### 🔄 Sesja aktualizacji: 2026-03-25 15:05

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | ✅ zakończony |
| 🛍️ App Store | ✅ zakończony |
| 🌐 Aplikacje z Internetu | ✅ zakończony |
| 🍺 Homebrew | ✅ zakończony |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `node` | 25.8.1_1 | 25.8.2 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Google Chrome | 146.0.7680.154 | 146.0.7680.165 |


### 🔄 Sesja aktualizacji: 2026-03-25 11:40

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | ✅ zakończony |
| 🛍️ App Store | ✅ zakończony |
| 🌐 Aplikacje z Internetu | ✅ zakończony |
| 🍺 Homebrew | ✅ zakończony |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `ada-url` | 3.4.3 | 3.4.4 |
| `freetype` | 2.14.2 | 2.14.3 |
| `gemini-cli` | 0.34.0 | 0.35.0 |
| `openblas` | 0.3.31_1 | 0.3.32 |
| `opencode` | 1.3.0 | 1.3.2 |
| `uv` | 0.11.0 | 0.11.1 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Codex | 26.318.11754 | 26.323.20928 |


### 🔄 Sesja aktualizacji: 2026-03-24 12:33

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | ✅ zakończony |
| 🛍️ App Store | ✅ zakończony |
| 🌐 Aplikacje z Internetu | ✅ zakończony |
| 🍺 Homebrew | ✅ zakończony |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `pango` | 1.57.0_2 | 1.57.1 |
| `pytorch` | 2.10.0_2 | 2.11.0 |
| `qwen-code` | 0.12.6 | 0.13.0 |
| `svt-av1` | 4.0.1 | 4.1.0 |
| `uv` | 0.10.12 | 0.11.0 |


### 🔄 Sesja aktualizacji: 2026-03-23 11:32

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | ✅ zakończony |
| 🛍️ App Store | ✅ zakończony |
| 🌐 Aplikacje z Internetu | ✅ zakończony |
| 🍺 Homebrew | ✅ zakończony |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `imagemagick` | 7.1.2-17 | 7.1.2-18 |
| `opencode` | 1.2.27 | 1.3.0 |


### 🔄 Sesja aktualizacji: 2026-03-21 10:14

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | ✅ zakończony |
| 🛍️ App Store | ✅ zakończony |
| 🌐 Aplikacje z Internetu | ✅ zakończony |
| 🍺 Homebrew | ✅ zakończony |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `aom` | 3.13.1 | 3.13.2 |
| `libde265` | 1.0.17 | 1.0.18 |
| `libmpc` | 1.3.1 | 1.4.0 |
| `simdjson` | 4.4.1 | 4.4.2 |
| `xsimd` | 14.0.0 | 14.1.0 |


### 🔄 Sesja aktualizacji: 2026-03-20 08:51

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | ✅ zakończony |
| 🛍️ App Store | ✅ zakończony |
| 🌐 Aplikacje z Internetu | ✅ zakończony |
| 🍺 Homebrew | ✅ zakończony |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `ca-certificates` | 2025-12-02 | 2026-03-19 |
| `harfbuzz` | 13.2.0 | 13.2.1 |
| `libnghttp2` | 1.68.0 | 1.68.1 |
| `simdjson` | 4.4.0 | 4.4.1 |
| `uv` | 0.10.11 | 0.10.12 |


### 🔄 Sesja aktualizacji: 2026-03-19 08:17

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | ✅ zakończony |
| 🛍️ App Store | ✅ zakończony |
| 🌐 Aplikacje z Internetu | ✅ zakończony |
| 🍺 Homebrew | ✅ zakończony |

**🍺 Homebrew — zaktualizowane pakiety:**

| Pakiet | Poprzednia wersja | Nowa wersja |
|--------|-------------------|-------------|
| `expat` | 2.7.4 | 2.7.5 |
| `harfbuzz` | 13.1.1 | 13.2.0 |
| `icu4c@78` | 78.2 | 78.3 |
| `protobuf@33` | 33.5 | 33.6 |

**🌐 Aplikacje internetowe — wykryte zmiany wersji:**

| Aplikacja | Poprzednia wersja | Nowa wersja |
|-----------|-------------------|-------------|
| Codex | 26.313.41514 | 26.317.21539 |
| Trezor Suite | 26.2.3 | 26.3.2 |


### 🔄 Sesja aktualizacji: 2026-03-02 22:00

| Krok | Wynik |
|------|-------|
| 🍎 System macOS | ✅ zakończony |
| 🛍️ App Store | ✅ zakończony |
| 🌐 Aplikacje z Internetu | ✅ zakończony |
| 🍺 Homebrew | ✅ zakończony |

**🔍 Nowe aplikacje wykryte i dodane do APPLICATIONS.md:**
- Ledger Wallet
- Microsoft Defender Shim

*Brak zaktualizowanych pakietów w tej sesji.*


### 🔧 Konserwacja skryptów: 2026-03-31

**Naprawiony problem: ściany ostrzeżeń `mas` o braku indeksu Spotlight**

Podczas ostatniej sesji aktualizacji (`sudo mas upgrade` + `mas outdated`) `mas` generował
wielokrotnie ostrzeżenia dla każdej aplikacji App Store, np.:

```
Warning: Found a likely App Store app that is not indexed in Spotlight in /Applications/WhatsApp.app
         Indexing now, which will not complete until sometime after mas exits
         Disable auto-indexing via: export MAS_NO_AUTO_INDEX=1
```

Ostrzeżenia pojawiały się **dwukrotnie** — raz przy `sudo mas upgrade` (TOR 1),
drugi raz przy `mas outdated` (weryfikacja końcowa). Dotknęło to 17 aplikacji:
Amphetamine, Canva, iMovie, KeePassium, Keynote, myCANAL, NordVPN, Notion Web Clipper,
Numbers, OneDrive, Pages Creator Studio, Perplexity, Prime Video, Telegram,
WhatsApp, Xcode, Numbers Creator Studio.

**Przyczyna:** `mas` przy skanowaniu `/Applications` próbuje automatycznie windeksować
w Spotlight aplikacje, które nie mają jeszcze wpisu w indeksie. To zachowanie jest
nieszkodliwe funkcjonalnie, ale generuje bardzo dużo szumu w logach.

**Naprawa:** Dodano `export MAS_NO_AUTO_INDEX=1` na początku `update_appstore.sh`
(przed pierwszym wywołaniem `mas`), co wyłącza to zachowanie zgodnie z zaleceniem `mas`.

**Zmienione pliki:**
- `update_appstore.sh` — dodano `export MAS_NO_AUTO_INDEX=1`, zaktualizowano datę nagłówka i komentarz
- `CLAUDE.md` — dodano wpis w sekcji Troubleshooting



### 🔧 Konserwacja skryptów: 2026-04-05

**Naprawiony problem: Firefox Developer Edition zawsze ponownie pobierany i instalowany**

Przy każdym uruchomieniu `update_internet_apps.sh` skrypt pobierał i instalował Firefox Dev Edition
nawet jeśli był już aktualny. Przyczyna: porównanie wersji zawsze kończyło się niezgodnością.

**Przyczyna techniczna:**
- `CFBundleShortVersionString` w Info.plist zwraca tylko wersję bazową: `"150.0"`
- Mozilla Product Details API zwraca pełną wersję z sufiksem beta: `"150.0b5"`
- `"150.0" != "150.0b5"` → porównanie zawsze fałszywe → skrypt zawsze próbuje aktualizować
- Po instalacji `app_version()` nadal zwracało `"150.0"` → APPLICATIONS.md nigdy nie otrzymywało
  prawidłowej wersji z sufiksem beta

**Naprawa:**
Firefox Dev Edition przechowuje pełną wersję (z sufiksem beta) w `application.ini`:
```
/Applications/Firefox Developer Edition.app/Contents/Resources/application.ini
[App]
Version=150.0b5
```

Dodano funkcję pomocniczą `firefox_dev_version()` która:
1. Czyta `Version=` z `application.ini` (pierwszeństwo)
2. Fallback na `CFBundleShortVersionString` gdy plik nie istnieje

Naprawiono trzy miejsca w `update_internet_apps.sh`:
- `VER=` przed porównaniem (odczyt zainstalowanej wersji)
- `NEW_VER=` po instalacji (odczyt nowej wersji do logu)
- `capture_internet_app_versions()` (snapshoty przed/po → aktualizacja APPLICATIONS.md)

APPLICATIONS.md zaktualizowano: `150.0` → `150.0b5`

**Nowa funkcja: automatyczna aktualizacja VirtualBox**

Wcześniej VirtualBox był oznaczony jako "tylko ręczna aktualizacja". Po zbadaniu dostępnych
metod: Oracle udostępnia prosty endpoint API:
- `https://download.virtualbox.org/virtualbox/LATEST.TXT` → zwraca aktualną wersję
- `https://download.virtualbox.org/virtualbox/{ver}/` → listing z nazwą pliku DMG

VirtualBox 7.1+ to universal binary (`VirtualBox-{ver}-{build}-macOS.dmg`), obsługujący
zarówno Apple Silicon (ARM64) jak i Intel (x86_64).

Sekcja VirtualBox w skrypcie przebudowana: sprawdza LATEST.TXT, porównuje z zainstalowaną
wersją, parsuje listing katalogu dla nazwy DMG, pobiera i instaluje przez `sudo installer -pkg`.

**Zbadane i zachowane jako "tylko ręczna aktualizacja":**
- **DaVinci Resolve**: Blackmagic Design nie udostępnia publicznego API. Blackmagic Software
  Update app (jeśli zainstalowana) jest nadal otwierana automatycznie przez skrypt.
- **IPMIView**: Supermicro nie udostępnia API. Narzędzie jest deprecated dla platform X14/H14+.

**Zmienione pliki:**
- `update_internet_apps.sh` — `firefox_dev_version()`, fix Firefox VER/NEW_VER/capture, VirtualBox auto-update
- `APPLICATIONS.md` — Firefox Dev Edition: `150.0` → `150.0b5`
- `CLAUDE.md` — zaktualizowana tabela metod aktualizacji, sekcja version detection, troubleshooting



### 🔧 Konserwacja skryptów: 2026-05-03

**Audyt + utwardzenie toolkitu (12/12 testów ✅, +206/−684 linii)**

Pełen przegląd projektu, naprawa ostrzeżeń, dodanie infrastruktury logów oraz CI.

**Naprawione błędy:**
- Nieużywane importy Pythona w `dev_sync/dev_sync_export.py` (`Path`) i `dev_sync_verify_git.py` (`sys`).
- 4× hardkodowane `/tmp/mac_update_*` w `update_npm_cli.sh` → `${TMPDIR:-/tmp}/mac_update_*`
  (zgodne z resztą kodu i konwencją macOS per-user temp pod `/var/folders/`).

**Nowa funkcjonalność: persystencja logów**
- Każde wywołanie `update_all.sh` zapisuje `logs/update_all_<YYYYMMDD_HHMMSS>.log`
  (gitignored). Rotacja zachowuje ostatnie `MAC_UPDATE_MAX_LOGS` plików (domyślnie 30).
- Przy `OVERALL_EXIT != 0` trap `EXIT` dopisuje do logu wszystkie snapshoty `*.txt`
  z katalogu sesyjnego **przed** jego usunięciem (limit 200 linii na snapshot).
  Wcześniej post-mortem awarii był niemożliwy — katalog sesyjny był wycierany.

**Nowa funkcjonalność: diagnostyka App Store**
- `update_appstore.sh` zapisuje `$MAC_UPDATE_SESSION_DIR/appstore_diag.txt` przy:
  awarii TRACK 1 (`sudo mas upgrade`), nieudanej gałęzi TRACK 2 (AppleScript) lub
  niepustym końcowym `mas outdated`. Plik trafia do persystowanego logu.
- Adresuje powracające awarie typu „App Store | Błąd" w UPDATES.md
  (np. 2026-04-29 17:12) — wcześniej bez kontekstu diagnostycznego.

**Utwardzenie:**
- `set -o pipefail` we wszystkich orchestratorach `update_*.sh` (6 plików). Bez tego
  awaria upstreamu w `cmd1 | cmd2` była po cichu połykana. Świadomie **bez** `set -e` —
  orchestrator musi wykonać każdy krok mimo częściowych awarii.
- Ujednolicone shebangi `#!/usr/bin/env bash` we wszystkich 16 plikach `.sh`.

**Czyszczenie i18n:**
- Usunięto 92 nieużywane klucze `L_*` z 7 plików językowych = **−644 linie**.
  Backupy zachowane jako `i18n/*.bak` (gitignored) — usunąć po potwierdzeniu poprawności.

**Test suite + CI:**
- Rozszerzony z 8 do 12 testów. Nowe asserty pilnują: braku hardkodu `/tmp` w npm-cli,
  obecności `pipefail`, persystencji logów, diagnostyki App Store.
- Nowy `run_tests.sh` — jedna komenda: `bash -n` + `py_compile` + `unittest`.
- Nowy `.github/workflows/ci.yml` — uruchamia `run_tests.sh` na `macos-latest`
  (Bash 3.2 default) plus `shellcheck` na `ubuntu-latest`.

**Zaktualizowane reguły CLAUDE.md:**
- Reguła #5: temp dla mktemp używa `${TMPDIR:-/tmp}/mac_update_*.XXXXXX`.
- Reguła #6 (nowa): wszystkie orchestratory `update_*.sh` muszą mieć `set -o pipefail`.

**Zmienione pliki (24):**
- `update_all.sh` (+55) — LOGS_DIR, rotacja, tee, snapshoty na fail
- `update_appstore.sh` (+42) — TRACK 1/2 diag, appstore_diag.txt
- `update_npm_cli.sh` — TMPDIR + shebang + pipefail
- `update_brew.sh`, `update_internet_apps.sh`, `update_system.sh` — shebang + pipefail
- `setup.sh`, `migration_setup.sh`, `fix_mcp_all.sh`, `i18n/loader.sh`, `dev_sync/provider_setup.sh` — shebang
- `i18n/lang_*.sh` (7×) — −92 nieużywanych kluczy
- `dev_sync/dev_sync_export.py`, `dev_sync/dev_sync_verify_git.py` — usunięte nieużywane importy
- `tests/test_safety_static.py` (+51) — 4 nowe asserty
- `run_tests.sh` (nowy) — jednokomendowy test runner
- `.github/workflows/ci.yml` (nowy) — CI workflow
- `CLAUDE.md` — sekcja „Run logs & diagnostics", reguły #5/#6, link do `run_tests.sh`
- `.gitignore` — `/logs/`, `*.bak`
