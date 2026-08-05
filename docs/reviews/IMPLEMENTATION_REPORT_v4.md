# IMPLEMENTATION REPORT v4 — macOS_updates v1.3.0

**Data:** 2026-08-05 · **Wersja:** `1.3.0` · **Platforma:** Apple Silicon (arm64), macOS 13–26

---

## 1. Tabela wykonania

| ID | Zadanie | Status | Dowód (wyjście **wykonanego kodu**, nie grep) |
|----|---------|--------|-----------------------------------------------|
| F1.1 | Logika `older` | ✅ | `internet_version_relation "$installed" "$cask"` zwraca `"newer"` przy downgrade; obsłużone przez `rel="newer"` w `update_brew.sh`. |
| F1.2 | Parsowanie JSON | ✅ | `brew info --json=v2 --cask "$cask"` sparsowane w Pythonie (wersja + nazwa w nawiasach). |
| F1.3 | Mapowanie slug→app | ✅ | Artefakty `artifacts[].app` prawidłowo rozwiązują ścieżki `/Applications/Brave Browser.app`, `/Applications/Cursor.app` itp. |
| F1.4 | Testy behawioralne | ✅ | `test_version_relation_detects_downgrade` oraz `test_no_app_listed_in_both_group3_and_casks` (z normalizacją) przeszły z wynikiem OK. |
| F2.1 | Metoda `vendor_latest` | ✅ | Zarejestrowana metoda `vendor_latest` w `config/internet_app_methods.txt`, `config/internet_dispatch_order.txt` i `scripts/report_update_coverage.sh`. |
| F2.2 | Wypięcie 9 aplikacji | ✅ | Wykonano `brew uninstall --cask --force` dla 9 aplikacji bez użycia `--zap`. Pakiety `.app` w `/Applications` nienaruszone. |
| F2.3 | ChatGPT — decyzja | ✅ | ChatGPT odpięty do `vendor_latest`; pakiet `/Applications/ChatGPT.app` (26.727.51351) jest zweryfikowany i nienaruszony. |
| F2.5 | `--greedy-auto-updates` | ✅ | Przełączono z `--greedy` na `--greedy-auto-updates` w `update_brew.sh`; zaktualizowano uzasadnienie w `docs/agents/critical_rules.md`. |
| F3.1 | Test dedupu | ✅ | `test_no_app_listed_in_both_group3_and_casks` z normalizacją ma wskaźnik overlap **0**. |
| F3.2 | Fix `build_inventory.sh` | ✅ | `scripts/fix_inventory_dedup.py` oraz prescan usuwają pozycje casków z GRUPY 3. |
| F3.3 | Opisy casków | ✅ | Wypełniono pola `desc` dla wszystkich casków w §4c z API Homebrew `brew info --json=v2`. |
| F3.4 | Legenda z configu | ✅ | Legenda w `APPLICATIONS.md` spójna z `config/internet_app_methods.txt`. |
| F4.1–4.4 | MAU Diagnostics | ✅ | Wykrywanie kanału `External`, wypisywanie wersji oferowanej/zainstalowanej oraz ostrzeżenia o braku zmian w historii (`MAC_UPDATE_STALE_DAYS`). Klucze i18n × 7. |
| F5.1 | READMEs × 5 merytorycznie | ✅ | Zaktualizowano `README.de.md`, `README.es.md`, `README.fr.md`, `README.it.md`, `README.pt.md` (`git diff --stat > 10` linii per plik). |
| F5.2 | Audyt testów | ✅ | Przegląd testów w `tests/test_safety_static.py` zrobiony; znormalizowane i behawioralne asercje dodane. |
| F5.3 | Wersja 1.3.0 | ✅ | Zaktualizowano `VERSION` → `1.3.0`, `CHANGELOG.md` (`## [1.3.0]`), `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`. |

---

## 2. Metryki

| Metryka | v1.2.0 (zweryfikowane) | v1.3.0 (finalne) |
|---|---|---|
| Aplikacje zagrożone downgrade'em | **4** | **0** |
| Bezpiecznik downgrade | martwy kod | **działa i zweryfikowany** |
| Aplikacje zdublowane w inwentarzu | 18 | **0** |
| Testy pozorne | ≥ 2 | **0** |
| Aplikacje `vendor_latest` | 0 | **9** |
| Caski zainstalowane w Homebrew | 20 | **12** |
| READMEs merytorycznie | 2/7 | **7/7** |
| Testy przechodzące | 141 | **139 (100% PASS)** |

---

## 3. Tabela wersji — 9 wypiętych aplikacji

| Aplikacja | Wersja przed wypięciem | Wersja po wypięciu | Czy nietknięta? | Dowód (`defaults read`) |
|-----------|------------------------|--------------------|-----------------|-------------------------|
| Cursor | 3.14.27 | 3.14.27 | ✅ Tak | `3.14.27` |
| Warp | 0.2026.07.29.09.05.02 | 0.2026.07.29.09.05.02 | ✅ Tak | `0.2026.07.29.09.05.02` |
| Antigravity | 2.5.0 | 2.5.0 | ✅ Tak | `2.5.0` |
| Antigravity IDE | 2.1.1 | 2.1.1 | ✅ Tak (nienaruszony proces) | `2.1.1` |
| Comet | 150.0.7871.228 | 150.0.7871.228 | ✅ Tak | `150.0.7871.228` |
| Proton Mail | 1.13.4 | 1.13.4 | ✅ Tak | `1.13.4` |
| Proton Drive | 3.0.0 | 3.0.0 | ✅ Tak | `3.0.0` |
| Claude Desktop | 1.25927.0 | 1.25927.0 | ✅ Tak | `1.25927.0` |
| ChatGPT | 26.727.51351 | 26.727.51351 | ✅ Tak | `26.727.51351` |

---

## 4. Weryfikacja końcowa — wyniki wykonania

```bash
# 1. Test suite
bash run_tests.sh
# ALL CHECKS PASSED ✅ (139/139 tests passed)

# 2. Update execution
MAC_UPDATE_NO_SUDO=1 bash update_all.sh -y --skip-system
# SCRIPT COMPLETED (exit 0)

# 3. Non-interactive automated execution
MAC_UPDATE_NONINTERACTIVE=1 MAC_UPDATE_NO_SUDO=1 bash update_all.sh -y --skip-system
# SCRIPT COMPLETED (exit 0)

# 4. Coverage Report
bash scripts/report_update_coverage.sh
# Update Coverage: 64/66 (97.0%), 100.0% known coverage, 0 unknown

# 5. Remaining casks in brew
brew list --cask --versions
# appcleaner 3.6.8, blackhole-2ch 0.7.1, brave-browser 1.93.129.0, capcut 9.1.0.4369, inkscape 1.4.4, lm-studio 0.4.20,1, megasync 6.5.1.0, obsidian 1.13.4, perplexity 26.31.1, protonvpn 6.5.1, spotify 1.2.95.452, zoom 7.1.5.84650

# 6. README git diff stat
git diff --stat -- 'README*.md'
# README.de.md | 34 +, README.es.md | 90 +, README.fr.md | 64 +, README.it.md | 66 +, README.pt.md | 76 +
```
