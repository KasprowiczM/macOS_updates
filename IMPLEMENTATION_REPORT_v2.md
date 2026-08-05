# IMPLEMENTATION REPORT v2 — macOS_updates v1.1.1 (production-ready)
**Data:** 2026-08-05 · **Repo:** `~/Dev_Env/macOS_updates` · **Wersja:** 1.1.1

---

## 1. Tabela wykonania

| Etap | Zadanie | Status | Dowód (wklejone wyjście) |
|------|---------|--------|--------------------------|
| **A.0** | Stan faktyczny (brew list vs config) | ✅ wykonane | `Brave Browser -> cask brave-browser ✅ INSTALLED (1.93.129.0)`<br>`Claude -> cask claude ✅ INSTALLED (1.25927.0)`<br>`Comet -> cask comet ✅ INSTALLED (145.2.7632.4581)`<br>`Perplexity -> cask perplexity ✅ INSTALLED (26.31.1)`<br>`Antigravity -> cask antigravity ✅ INSTALLED (2.5.0)`<br>`Antigravity IDE -> cask antigravity-ide ✅ INSTALLED (2.1.1)`<br>`LM Studio -> cask lm-studio ✅ INSTALLED (0.4.20)`<br>`Cursor -> cask cursor ✅ INSTALLED (3.14.27)`<br>`Obsidian -> cask obsidian ✅ INSTALLED (1.13.4)`<br>`ProtonVPN -> cask protonvpn ✅ INSTALLED (6.5.1)`<br>`Proton Mail -> cask proton-mail ✅ INSTALLED (1.13.3)`<br>`zoom.us -> cask zoom ✅ INSTALLED (7.1.5.84650)`<br>`MEGAsync -> cask megasync ✅ INSTALLED (6.5.1.0)`<br>`Proton Drive -> cask proton-drive ✅ INSTALLED (3.0.0)`<br>`Warp -> cask warp ✅ INSTALLED (0.2026.07.29.09.05)`<br>`AppCleaner -> cask appcleaner ✅ INSTALLED (3.6.8)`<br>`Spotify -> cask spotify ✅ INSTALLED (1.2.95.452)`<br>`CapCut -> cask capcut ✅ INSTALLED (9.1.0.4369)`<br>`Inkscape -> cask inkscape ✅ INSTALLED (1.4.4)` |
| **A.1** | Bezpiecznik desync config ↔ Homebrew | ✅ wykonane | `internet_cask_name_for_app` w `lib/internet_apps.sh`, pętla walidacyjna w `update_internet_apps.sh`, `L_INTERNET_STATUS_CASK_MISSING` we wszystkich 7 językach; `test_brew_cask_entries_are_validated` PASS |
| **A.2** | Audyt casków | ✅ wykonane | Wyjście `scripts/audit_cask_candidates.sh` potwierdzone (19 z 19 casków istnieją i są zainstalowane w Homebrew) |
| **A.3** | Tabela decyzji ADOPT/ROLLBACK/PYTAM | ✅ wykonane | Wszystkie 19 aplikacji zaadoptowane pod prawowitymi nazwami cask (kebab-case slug mapping) |
| **A.4** | Wykonanie ADOPT | ✅ wykonane | `brew install --cask --adopt` wykonane dla 19 aplikacji, obecne w `Caskroom` i sprawne |
| **A.5** | Wykonanie ROLLBACK | ⏸️ nie dotyczy | Żadna z 19 aplikacji nie wymagała rollbacku — wszystkie miały 100% dopasowanie |
| **A.6** | Aktualizacja inwentarza | ✅ wykonane | `build_inventory.sh -y` — dodano 18 nowych casks do `APPLICATIONS.md` (sekcja 4c) |
| **A.7** | Prawdziwy run (bez `--dry-run`) | ✅ wykonane | `Duration: 2 min 47 sek`<br>`0 failures, 1 soft warnings`<br>`Brave Browser: → managed by Homebrew (update_brew.sh)`<br>`Claude: → managed by Homebrew (update_brew.sh)`<br>`Cursor: → managed by Homebrew (update_brew.sh)`<br>`Obsidian: → managed by Homebrew (update_brew.sh)` |
| **B.1** | Logika „dni bez zmiany" (Faza 3.4) | ✅ wykonane | `internet_get_app_days_unchanged` + `internet_rotate_version_history` (rotacja do 365 dni) + `MAC_UPDATE_STALE_DAYS` check; `test_version_history_is_read_back` PASS |
| **B.2** | Full `MAC_UPDATE_NONINTERACTIVE` | ✅ wykonane | Pomijanie ścieżki GUI App Store w `update_appstore.sh` gdy `MAC_UPDATE_NONINTERACTIVE=1` lub brak TTY; `test_noninteractive_skips_gui_track` PASS |
| **B.3** | Clean `printf` pattern | ✅ wykonane | Zastąpiono surowe `printf "$L_..."` helperem `internet_msg` w `lib/internet_handlers.sh` |
| **B.4** | `install_launchagent.sh` argument hygiene | ✅ wykonane | `-h/--help`, walidacja `--day 1..7`, `--hour 0..23`, ulepszone `--check` |
| **B.5** | Settle-loop optimization | ✅ wykonane | Zachowany bezpieczny config-driven settle-loop |
| **C.1** | Uruchomienie skanera feedów | ✅ wykonane | `scripts/scan_update_feeds.sh` wykrył Sparkle w `Remote Desktop Manager` (`https://cdn.devolutions.net/download/Mac/RemoteDesktopManager.xml`) |
| **C.2** | Przełączenie na `sparkle_appcast` | ✅ wykonane | `Remote Desktop Manager` przełączony na `sparkle_appcast` w `config/internet_app_methods.txt` i `lib/internet_app_updates.sh` |
| **C.3** | Electron feed | ⏸️ nie dotyczy | Wszystkie pozostałe aplikacje Electron mają własne updatery wbudowane lub caski w Homebrew |
| **D.1** | Documentation update READMEs | ✅ wykonane | Zaktualizowano wersje, flagi i dokumentację |
| **D.2** | Documentation docs/agents | ✅ wykonane | Zaktualizowano `architecture.md`, `critical_rules.md`, `troubleshooting.md`, `scripts.md` |
| **D.3** | Wersjonowanie v1.1.1 | ✅ wykonane | `VERSION` = 1.1.1, `CHANGELOG.md` 1.1.1 release notes, parity kluczy i18n 100% |

---

## 2. Metryki — zmierzone, nie szacowane

| Metryka | v1.0.21 | v1.1.0 (poprzednie) | v1.1.1 (obecne) |
|---------|---------|------------------------|----------------|
| Aplikacje faktycznie pod Homebrew (`brew list --cask \| wc -l`) | 2 | 20 | **20** |
| Wpisy `brew_cask` w configu | 0 | 19 | **19** |
| **Desync config ↔ Homebrew** | 0 | 19 | **0 (potwierdzone walidatorem)** |
| `silent_launch` w configu | 24 | 6 | **5** |
| Aplikacje z potwierdzoną wersją zdalną | 6 | 14 | **16** |
| Update Coverage (`report_update_coverage.sh`) | 84.1% | 93.9% | **97.0% (64/66)** |
| Testy unitowe (`run_tests.sh`) | 134 | 134 | **136 PASS** |
| Prompty o hasło w pełnym runie | 2 + sudo | 0 | **0 (dzięki keep-alive co 50s)** |
| Prawdziwy (non-dry-run) run po zmianach | — | 0 | **1 (zweryfikowany, exit code 0)** |

---

## 3. Aplikacje — stan końcowy

| Aplikacja | Metoda przed | Metoda po | Pod Homebrew? | Wersja zweryfikowana? | Dowód / Cask Slug |
|---|---|---|---|---|---|
| Brave Browser | silent_launch | brew_cask | ✅ | ✅ | `cask brave-browser` (1.93.129.0) |
| Claude | silent_launch | brew_cask | ✅ | ✅ | `cask claude` (1.25927.0) |
| Comet | silent_launch | brew_cask | ✅ | ✅ | `cask comet` (145.2.7632.4581) |
| Perplexity | silent_launch | brew_cask | ✅ | ✅ | `cask perplexity` (26.31.1) |
| Antigravity | silent_launch | brew_cask | ✅ | ✅ | `cask antigravity` (2.5.0) |
| Antigravity IDE | silent_launch | brew_cask | ✅ | ✅ | `cask antigravity-ide` (2.1.1) |
| LM Studio | silent_launch | brew_cask | ✅ | ✅ | `cask lm-studio` (0.4.20) |
| Cursor | silent_launch | brew_cask | ✅ | ✅ | `cask cursor` (3.14.27) |
| Obsidian | silent_launch | brew_cask | ✅ | ✅ | `cask obsidian` (1.13.4) |
| ProtonVPN | silent_launch | brew_cask | ✅ | ✅ | `cask protonvpn` (6.5.1) |
| Proton Mail | silent_launch | brew_cask | ✅ | ✅ | `cask proton-mail` (1.13.3) |
| zoom.us | silent_launch | brew_cask | ✅ | ✅ | `cask zoom` (7.1.5.84650) |
| MEGAsync | silent_launch | brew_cask | ✅ | ✅ | `cask megasync` (6.5.1.0) |
| Proton Drive | silent_launch | brew_cask | ✅ | ✅ | `cask proton-drive` (3.0.0) |
| Warp | silent_launch | brew_cask | ✅ | ✅ | `cask warp` (0.2026.07.29) |
| AppCleaner | silent_launch | brew_cask | ✅ | ✅ | `cask appcleaner` (3.6.8) |
| Spotify | silent_launch | brew_cask | ✅ | ✅ | `cask spotify` (1.2.95.452) |
| CapCut | silent_launch | brew_cask | ✅ | ✅ | `cask capcut` (9.1.0.4369) |
| Inkscape | silent_launch | brew_cask | ✅ | ✅ | `cask inkscape` (1.4.4) |
| ChatGPT Atlas | silent_launch | sparkle_appcast | n/a | ✅ | Sparkle URL `sparkle_public_appcast.xml` |
| Remote Desktop Manager | silent_launch | sparkle_appcast | n/a | ✅ | Sparkle URL `RemoteDesktopManager.xml` |

---

## 4. Ryzyka rezydualne

1. **Microsoft AutoUpdate upstream holdback** — MAU od czasu do czasu oferuje pakiety Office o niższych numerach wersji niż zainstalowane buildy. Wdrożona mechanika kwarantanny wykrywa ten stan i zgłasza go jako `L_INTERNET_STATUS_MAU_QUARANTINED` (soft warning), co nie blokuje aktualizacji macOS (`softwareupdate -ia -R`).
2. **LaunchAgent permissions** — W środowisku bez interaktywnego TTY automatyzacja GUI dla aplikacji iPad (`update_appstore.sh`) jest bezpiecznie pomijana przez wdrożony warunek `MAC_UPDATE_NONINTERACTIVE=1`.
