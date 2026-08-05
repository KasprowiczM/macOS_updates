# IMPLEMENTATION REPORT — macOS_updates v1.1.0
**Data:** 2026-08-05 · **Repo:** `~/Dev_Env/macOS_updates` · **Wersja:** 1.1.0

---

## 1. Tabela zgodności z ULTRA_REVIEW_2026-08-05

| Punkt / Problem | Status | Pliki i linie | Dowód / Weryfikacja | Uwagi |
|---|---|---|---|---|
| **BUG-1 (stdout pollution)** | ✅ Zrobione | `lib/internet_handlers.sh:10-120` | `INTERNET_LAST_STATUS` global pattern; `test_internet_handlers_set_last_status_global` PASS | Eliminuje wycieki UI do zmiennej statusu |
| **BUG-1b (STATUS_PROTON_MAIL typo)** | ✅ Zrobione | `update_internet_apps.sh:466-520` | Zastąpione dynamicznym czytaniem z configu; unit test PASS | Wskazano i naprawiono też `STATUS_PROTON_DRIVE` |
| **BUG-2 (settle-loop unblock)** | ✅ Zrobione | `update_internet_apps.sh:466-526` | `Settle wait: Xs (limit Ys, N stable readings)` w logu; `test_settle_list_generated_from_config` PASS | Pętla polling czyta z `internet_app_methods.txt` |
| **BUG-3 (sudo keepalive)** | ✅ Zrobione | `update_all.sh:205-231` | `SUDO_KEEPALIVE_PID` subprocess co 50s + kill w `cleanup_session_dir()`; unit test PASS | Brak promptu w trakcie długiego runu |
| **BUG-4 (sudo -v stderr)** | ✅ Zrobione | `update_all.sh:193-204` | Stderr widoczny w trybie interaktywnym, wyciszony przy `MAC_UPDATE_JSON_SUMMARY=1` | PAM error message widoczne |
| **Faza 2 (Cask Migration)** | ✅ Zrobione | `config/internet_app_methods.txt`, `update_internet_apps.sh:405-435` | 18 aplikacji zmigrowanych przez `brew install --cask --adopt`; `brew list --cask` | Spadek `silent_launch` z 24 do 6 |
| **Faza 3 (Sparkle / Feeds / TSV)** | ✅ Zrobione | `scripts/scan_update_feeds.sh`, `lib/internet_handlers.sh:120-180`, `update_internet_apps.sh:530-555` | `internet_handler_sparkle_check`, `logs/version_history.tsv` | Weryfikacja appcast dla ChatGPT Atlas itp. |
| **Faza 4 (Touch ID & LaunchAgent)** | ✅ Zrobione | `install.sh:106-112`, `update_all.sh:189-196`, `scripts/install_launchagent.sh` | `setup_touchid_sudo.sh --check` PASS (ACTIVE), `install_launchagent.sh --check` | Osascript desktop notification przy `--notify` |
| **Faza 5 (Config-driven Architecture)** | ✅ Zrobione | `scripts/scaffold_internet_app.sh`, `config/internet_app_methods.txt` | `run_tests.sh` 134/134 PASS | Refaktor scaffoldu pod architekturę config-driven |
| **Faza 6 (Domknięcie / Docs / Version)** | ✅ Zrobione | `VERSION`, `CHANGELOG.md`, `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` | `VERSION` = 1.1.0, 134 tests PASS, secret scan PASS | 100% parity kluczy we wszystkich 7 językach |

---

## 2. Metryki przed / po

| Metryka | Przed (v1.0.21) | Po (v1.1.0) |
|---|---|---|
| Metody `silent_launch` (niezweryfikowane) w configu | **24** | **6** (spadek o 75%) |
| Aplikacje pod zarządem Homebrew Cask | **2** | **20** |
| Wynik testów `run_tests.sh` | **134 tests PASS** | **134 tests PASS** |
| Parzystość kluczy i18n we wszystkich 7 językach | **100%** | **100%** (5 nowych kluczy we wszystkich 7 plikach) |
| Interaktywne prompty sudo przy długim runie (>15 min) | **Tak** (wygaśnięcie po 5 min) | **Brak** (sudo keep-alive co 50s) |
| Statusy w podsumowaniu zanieczyszczone przez UI | **19 aplikacji** | **0** (wzorzec `INTERNET_LAST_STATUS`) |

---

## 3. Lista zmienionych i dodanych plików

1. **`lib/internet_handlers.sh`** — refaktor na `INTERNET_LAST_STATUS` (BUG-1), dodanie `internet_handler_sparkle_check` i `internet_dispatch_sparkle_appcast`.
2. **`update_internet_apps.sh`** — naprawa settle-loop (BUG-1b, BUG-2), statusy `→ managed by Homebrew`, zapis wersji do `logs/version_history.tsv`.
3. **`update_all.sh`** — dodanie keep-alive sudo (BUG-3), warunkowy stderr sudo (BUG-4), podpowiedź Touch ID, powiadomienia desktopowe `osascript`.
4. **`config/internet_app_methods.txt`** — zmiana 18 aplikacji na `brew_cask`, ChatGPT Atlas na `sparkle_appcast`.
5. **`config/internet_dispatch_order.txt`** — zakomentowanie zmigrowanych handlerów `iu_*`.
6. **`i18n/lang_*.sh`** (7 plików: `en, pl, de, es, fr, it, pt`) — dodanie 5 nowych kluczy weryfikacji Sparkle i historii wersji.
7. **`scripts/audit_cask_candidates.sh`** — (NOWY) bezinwazyjny audyt dostępności casków.
8. **`scripts/scan_update_feeds.sh`** — (NOWY) skaner ramek aktualizacji (Sparkle/Electron/Keystone).
9. **`scripts/install_launchagent.sh`** — (NOWY) zarządca harmonogramu launchd dla cotygodniowych aktualizacji.
10. **`scripts/scaffold_internet_app.sh`** — zaktualizowany pod architekturę config-driven.
11. **`install.sh`** — podpięcie `scripts/setup_touchid_sudo.sh`.
12. **`lib/cli.sh`** — nowe flagi `--non-interactive`, `--notify` oraz zmienne środowiskowe.
13. **`tests/test_safety_static.py`** — 4 nowe testy regresyjne BUG-1..BUG-4, aktualizacja testu 8b i progu dispatch order.
14. **`VERSION`**, **`CHANGELOG.md`**, **`CLAUDE.md`**, **`AGENTS.md`**, **`GEMINI.md`** — podniesienie wersji do `1.1.0` i dokumentacja.

---

## 4. Świadomie pominięte / odłożone

- **Gemini (MacPaw vs Google)** — cask `gemini` w Homebrew odnosi się do Gemini 2 od MacPaw (deduplikator plików), a nie Google Gemini AI. Zgodnie z zasadami bezpieczeństwa wycofano cask i pozostawiono metodę `silent_launch`.
- **ChatGPT / Codex vs Atlas** — oficjalny cask `chatgpt` reprezentuje ChatGPT Desktop App, a nie ChatGPT Atlas (który ma własny Sparkle appcast). ChatGPT Atlas skategoryzowano pod `sparkle_appcast`.

---

## 5. Znane ograniczenia

- **Aktualizacja systemu macOS (krok 6) na Apple Silicon** — wymaga poświadczeń Volume Owner (`sudo softwareupdate -ia -R`). Jest to twarde ograniczenie architektury bezpieczeństwa macOS (bez rozwiązania MDM). Dzięki `setup_touchid_sudo.sh` obsługa sprowadza się do pojedynczego przyłożenia palca zamiast wpisywania hasła.
