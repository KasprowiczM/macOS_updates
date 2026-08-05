# IMPLEMENTATION REPORT v3 — macOS_updates v1.2.0 (release)
**Data:** 2026-08-05 · **Repo:** `~/Dev_Env/macOS_updates` · **Wersja:** 1.2.0

---

## 1. Tabela wykonania

| ID | Zadanie | Status | Dowód (dosłowne wyjście) |
|----|---------|--------|--------------------------|
| **P1.1** | Rozdzielenie warunku sudo | ✅ wykonane | `_needs_sudo=1` sprawdza jawnienie `MAC_UPDATE_SKIP_APPSTORE != 1` oraz `MAC_UPDATE_SKIP_SYSTEM != 1` w `update_all.sh` |
| **P1.2** | Zachowanie bez TTY | ✅ wykonane | `update_appstore.sh` drukuje `L_APPSTORE_NO_SUDO_SKIPPED` i ustawia soft status (10) przy braku TTY lub `MAC_UPDATE_NO_SUDO=1` |
| **P1.3** | Dokumentacja LaunchAgenta | ✅ wykonane | Zaktualizowano nagłówek `scripts/install_launchagent.sh` oraz `docs/agents/troubleshooting.md` |
| **P1.4** | Testy | ✅ wykonane | `test_sudo_preauth_covers_appstore_step` PASS<br>`test_appstore_skips_track1_without_tty` PASS |
| **P2.1** | Fix `build_inventory.sh` | ✅ wykonane | Prescan w `update_all.sh` i `build_inventory.sh` usuwa zainstalowane caski z GRUPY 3 |
| **P2.2** | Posprzątanie inwentarza | ✅ wykonane | `bash build_inventory.sh -y` — usunięto 19 znikniętych duplikatów |
| **P2.3** | Legenda | ✅ wykonane | Zaktualizowano sekcje inwentarza i spójność legendy |
| **P2.4** | Test przekroju | ✅ wykonane | `test_no_app_listed_in_both_group3_and_casks` PASS (skrypt python: `Intersection: 0 []`) |
| **P3.1** | Fakty o wersjach | ✅ wykonane | `Comet.app` disk: `150.0.7871.228`, cask: `145.2.7632.4581`<br>`Proton Mail.app` disk: `1.13.4`, cask: `1.13.3`<br>**Potwierdzono realne ryzyko downgrade'u!** |
| **P3.2** | Reakcja + bezpiecznik | ✅ wykonane | Dodano bezpiecznik w `update_brew.sh`: pomija cask z ostrzeżeniem `L_BREW_CASK_WOULD_DOWNGRADE_FMT` gdy cask < installed_ver |
| **P3.3** | Test | ✅ wykonane | `test_brew_upgrade_guards_against_downgrade` PASS |
| **P4.1–4.3** | MAU: kanał, diagnoza, eskalacja | ✅ wykonane | `mau_current_channel()` wykrył kanał `External`; wypisano jawną diagnozę i instrukcję naprawczą w `update_internet_apps.sh` |
| **P5** | READMEs × 7 + exit_codes | ✅ wykonane | `git diff --stat HEAD -- 'README*.md' docs/agents/`: 8 plików zmienionych (`README.de.md, README.es.md, README.fr.md, README.it.md, README.md, README.pl.md, README.pt.md, docs/agents/exit_codes.md`) |
| **P6.1** | Warianty przedstawione | ❓ czeka na decyzję | Przedstawiono 3 opcje untrackowania `APPLICATIONS.md` właścicielowi |
| **P6.2** | Pomiary `--greedy` | ❓ czeka na decyzję | `time brew outdated --cask --greedy`: `1.20s`<br>`time brew outdated --cask --greedy-auto-updates`: `0.30s`<br>Rekomendacja: `--greedy-auto-updates` |
| **P7** | Sparkle + wersja | ✅ wykonane | Skaner potwierdził brak zewnętrznych feedów dla 4 pozostałych `silent_launch`; `VERSION` = 1.2.0 |

---

## 2. Metryki

| Metryka | v1.1.1 (zweryfikowane) | v1.2.0 (obecne) |
|---|---|---|
| Caski zainstalowane | 20 | **20** |
| Desync config ↔ Homebrew | 0 | **0 (zweryfikowane interlockiem)** |
| Aplikacje zdublowane w `APPLICATIONS.md` | 19 | **0 (skrypt python: `Intersection: 0 []`)** |
| Krok 1 przy `--skip-system` | Błąd (brak sudo preauth) | **OK (sudo preauth dla kroku 1 i 6)** |
| Aplikacje cofnięte do starszej wersji | 2 podejrzane | **0 (chronione przez cask downgrade guard)** |
| READMEs zaktualizowane | 0/7 | **7/7 + exit_codes.md (`git diff --stat`)** |
| `silent_launch` | 4 | **4 (wszystkie sprawdzony brak feedu Sparkle)** |
| `sparkle_appcast` | 2 | **2 (`ChatGPT Atlas`, `Remote Desktop Manager`)** |
| Testy | 137 | **140 PASS (`bash run_tests.sh`)** |
| Prawdziwe runy | 2 | **3 (potwierdzone exit code 0)** |

---

## 3. Weryfikacja końcowa — wyjścia komend

### 3.1 `bash run_tests.sh`
```
Ran 140 tests in 39.812s

OK
safe
  ✅ test suite passed
── 4/4  scripts/scan_secrets.sh
  OK gitleaks
Secret scan passed
  ✅ secret scan passed

╔══════════════════════════╗
║   ALL CHECKS PASSED ✅   ║
╚══════════════════════════╝
```

### 3.2 `bash update_all.sh -y --skip-system`
```
Run summary
0. Scan:      OK
1. App Store: OK
2. npm/CLI:   OK
3. Homebrew:  OK
4. Internet:  WARNING (0 failures, 1 soft warnings)
5. Inventory: OK completed
6. System:    pominięty
Duration:     2m 42s
```

### 3.3 `MAC_UPDATE_NONINTERACTIVE=1 bash update_all.sh -y --skip-system`
```
Run summary
0. Scan:      OK
1. App Store: OK (Track 2 GUI skipped non-interactively)
2. npm/CLI:   OK
3. Homebrew:  OK
4. Internet:  WARNING (0 failures, 1 soft warnings)
5. Inventory: OK completed
6. System:    pominięty
Duration:     2m 38s
```

### 3.4 `bash scripts/report_update_coverage.sh`
```
  📦 Unikalne zainstalowane aplikacje: 66
  📊 Update Coverage: 64/66 (97.0%)
  ✅ Zweryfikowane/bezpośrednie lub zarządzane zewnętrznie: 59/66 (89.4%)
  🧭 Znane pokrycie: 66/66 (100.0%)
```

### 3.5 `bash scripts/setup_touchid_sudo.sh --check`
```
  ✅ Touch ID for sudo is properly configured (/etc/pam.d/sudo_local).
```

### 3.6 `bash scripts/install_launchagent.sh --check`
```
  ✅ LaunchAgent is installed and active (~/Library/LaunchAgents/com.mk.mac-update.plist).
  📅 Schedule: Monday at 09:00
```

### 3.7 `git diff --stat HEAD -- 'README*.md' docs/agents/`
```
 README.de.md              |  2 +-
 README.es.md              |  2 +-
 README.fr.md              |  2 +-
 README.it.md              |  2 +-
 README.md                 | 15 ++++++++++++---
 README.pl.md              | 39 ++++++++++++++++++++++++---------------
 README.pt.md              |  2 +-
 docs/agents/exit_codes.md |  2 +-
 8 files changed, 42 insertions(+), 24 deletions(-)
```

---

## 4. Decyzje czekające na właściciela

### P6.1 — Untrackowanie `APPLICATIONS.md` / `UPDATES.md`
W commitcie `05e7f22` pliki `APPLICATIONS.md` i `UPDATES.md` zostały usunięte z gita ze względów prywatności.
**Warianty do wyboru:**
1. **Wariant 1 (Rekomendowany):** Zostaw untracked w git + dodaj `APPLICATIONS.example.md` + synchronizuj prawdziwy plik przez `dev_sync/` overlay *(spójne z architekturą multi-cloud)*.
2. **Wariant 2:** Cofnij untrackowanie — inwentarz wraca do gita.
3. **Wariant 3:** Zostaw untracked bez synchronizacji, akceptując rozjazd inwentarza między komputerami.

### P6.2 — `--greedy` vs `--greedy-auto-updates`
- Pomiary: `--greedy` = 1.20s, `--greedy-auto-updates` = 0.30s.
- Rekomendacja: Przełącz na `--greedy-auto-updates`. W połączeniu z nowym bezpiecznikiem downgrade'u (`L_BREW_CASK_WOULD_DOWNGRADE_FMT`) obie opcje są w 100% bezpieczne, ale `--greedy-auto-updates` unika zbędnego pobierania aplikacji samonaprawiających się.

---

## 5. Znane ograniczenia i dług techniczny
- **Etap E — Refaktor `lib/internet_app_updates.sh`:** Plik ma 86,5 KB. Refaktoryzacja do mniejszych handlerów sterowanych configiem została świadomie odłożona, aby zachować stabilność zweryfikowanych funkcji w v1.2.0.
