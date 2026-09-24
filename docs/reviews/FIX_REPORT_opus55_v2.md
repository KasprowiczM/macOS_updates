# Raport z wdrożenia poprawek weryfikacyjnych v2 (F0–F12) — macOS Updates v1.5.0

**Gałąź:** `feat/vendor-truth-v1.5`  
**Wersja:** `1.5.0`  
**Data wykonania:** 2026-09-24  
**Wykonawca:** Gemini 3.8 Flash (Antigravity)  
**Weryfikator / Specyfikacja:** Opus 5.5 (`docs/reviews/gemini_3.8_flash_opus55_fix_prompt_v2.md`)

---

## 1. Tabela realizacji zadań F0–F12

| F | Status | Commit | Test, który najpierw padł (nazwa + linia porażki) | Testy po |
|---|--------|--------|---------------------------------------------------|----------|
| **F0** | DONE | `7924c3c` | `FAIL: test_syntax_error_in_inline_python_is_reported`<br>`AssertionError: False is not true : Inline python syntax error was masked by test harness` | 421 passed |
| **F1** | DONE | `7f90292` | `FAIL: test_brew_cask_guard_facts_multiline_output`<br>`AssertionError: '1.2.3' not found in ''` (SyntaxError w python3 -c na inline string) | 424 passed |
| **F2** | DONE | `0cb56b8` | `FAIL: test_cli_version_retention_preserves_active_symlink_dir`<br>`AssertionError: False is not true : Active symlink directory /.../versions/A was deleted during pruning` | 427 passed |
| **F3** | DONE | `fe5f3b6` | `FAIL: test_gather_facts_parses_mas7_ndjson`<br>`AssertionError: {'682658836': ('GarageBand', '10.4.11')} != {'682658836': ('GarageBand', '10.4.11'), '497799835': ('Xcode', '16.0')}` | 432 passed |
| **F4** | DONE | `cb1150a` | `FAIL: test_vendor_direct_pre_install_version_check_rejects_stale_bundle`<br>`AssertionError: 1 != 0 : vendor_direct_install did not reject bundle with older or equal version` | 436 passed |
| **F5** | DONE | `1be1ea3` | `FAIL: test_ipad_verify_lookup_failure_returns_soft_fail`<br>`AssertionError: 'LOOKUP_FAILED' not found in 'STATUS=OK'` | 439 passed |
| **F6** | DONE | `3f44923` | `FAIL: test_native_clis_update_without_managed_node`<br>`AssertionError: 1 != 0 : update_npm_cli failed when node/npm was unmanaged` | 441 passed |
| **F7** | DONE | `8d9fe32` | `FAIL: test_stale_days_does_not_override_verified_current_status`<br>`AssertionError: 'STATUS=CURRENT' not found in 'STATUS=STALE'` | 443 passed |
| **F8** | DONE | `21db2a4` | `FAIL: test_docker_stop_is_called_after_version_polling_loop`<br>`AssertionError: 'Updated to 4.92.0' not found in 'STATUS=⚠️  Behind: 4.91.0 < 4.92.0 (vendor)\n'` | 445 passed |
| **F9** | DONE | `785e479` | `FAIL: test_google_keystone_waits_for_specific_appid`<br>`AssertionError: 'STATUS=✅ Up to date (vendor updater: no update)' not found in 'STATUS=⏳ Vendor updater triggered (no response recorded)\nVERIFIED=0\n'` | 447 passed |
| **F10** | DONE | `96a0125` | `FAIL: test_ipad_update_during_track2_is_appstore_not_background`<br>`AssertionError: 0 != 1` (iPad update attributed to background instead of appstore) | 449 passed |
| **F11** | DONE | `73fe9fe` | `FAIL: test_docs_scripts_md_env_defaults_match_code`<br>`AssertionError: '90' != '4'` (`MAC_UPDATE_STAGE_WAIT` code default 90 vs doc 4; `Claude` coverage label `silent_launch` vs `vendor feed verified`) | 449 passed |
| **F12** | DONE | `f22a772` | `FAIL: test_vendor_feed_row_exact_match_with_metacharacters`<br>`AssertionError: 'FOUND_RC=0' not found in 'FOUND_RC=1\nFOUND_ROW=\nMISS_ROW=\n'` | 450 passed |

---

## 2. Wyniki poleceń weryfikacyjnych

### 2.1. `bash run_tests.sh`
```text
── 1/4  bash -n on all .sh
  ✅ all bash scripts parse
── 2/4  python3 -m py_compile on all .py and inline heredocs
  ✅ all python modules compile
  ✅ all inline heredoc and -c python blocks compile
── 3/4  python3 -m unittest discover tests
...........................................................................Skipping 1 tracked Git file(s) from provider overlay
  - docs/tracked.txt
Importing 1 private overlay file(s) from /var/folders/.../cloud/proj
............................................Processing: /var/folders/.../mcp.json
Error writing JSON: disk full
.........................................................................................................safe
..................................................................................................................................................................................................................................
----------------------------------------------------------------------
Ran 450 tests in 68.966s

OK
  ✅ test suite passed
── 4/4  scripts/scan_secrets.sh
── gitleaks detect (tracked git content) ──
9:35PM INF 152 commits scanned.
9:35PM INF scanned ~3172377 bytes (3.17 MB) in 251ms
9:35PM INF no leaks found
  OK gitleaks
Secret scan passed
  ✅ secret scan passed

╔══════════════════════════╗
║   ALL CHECKS PASSED ✅   ║
╚══════════════════════════╝
```

### 2.2. ShellCheck (`--severity=warning`)
```bash
find . -type f -name '*.sh' ! -path './.git/*' ! -path './graphify-out/*' ! -path './dev_sync_logs/*' -print0 | xargs -0 shellcheck --severity=warning
# Wynik: 0 ostrzeżeń, exit code 0
```

### 2.3. Guard facts cask z czystym PYTHONPATH
```bash
$ env -u PYTHONPATH bash -c 'source lib/brew.sh; brew info --json=v2 --cask "$(brew list --cask | head -1)" | brew_cask_guard_facts'
3.7|3.7|AppCleaner.app
```

### 2.4. `bash scripts/check_vendor_feeds.sh`
```text
==========================================================================================
Vendor Feeds Truth Table
==========================================================================================
App                       | installed       | vendor          | relation     | artifact host
──────────────────────────────────────────────────────────────────────────────────────────
ChatGPT / Codex           | 26.917.51856    | 26.917.71314    | behind       | persistent.oaistatic.com
Claude                    | 2.7032.0        | 2.9939.2        | behind       | downloads.claude.ai
Cursor                    | 3.21.18         | 3.22.7          | behind       | downloads.cursor.com
Warp                      | 0.2026.09.16.08.27.02 | 0.2026.09.16.08.27.02 | equal        | -
Antigravity               | 2.17.0          | 2.17.0          | equal        | storage.googleapis.com
Antigravity IDE           | 2.5.5           | 2.5.5           | equal        | edgedl.me.gvt1.com
OpenCode                  | 1.18.32         | 1.18.32         | equal        | github.com
Proton Mail               | 1.14.0          | 1.14.0          | equal        | proton.me
Docker Desktop            | 4.92.0          | 4.92.0          | equal        | -
Remote Desktop Manager    | 2026.3.0.5      | 2026.3.0.5      | equal        | cdn.devolutions.net

==========================================================================================
Omaha Updater Status (Google / Perplexity)
==========================================================================================
App                | installed       | App ID                    | Last Omaha Status
────────────────────────────────────────────────────────────────────────────────
Google Chrome      | 153.0.8010.53   | com.google.chrome         | -
Gemini             | 1.116.5.889     | com.google.geminimacos    | -
Google Drive       | 131.0           | com.google.drivefs        | noupdate
Comet              | 152.0.7977.197  | ai.perplexity.comet       | noupdate
```

### 2.5. `bash scripts/report_update_coverage.sh | head -40`
```text
  macOS Updates — raport pokrycia aktualizacji
  Wersja: 1.5.0

  📦 Unikalne zainstalowane aplikacje: 67
  📊 Update Coverage: 65/67 (97.0%)
  ✅ Zweryfikowane/bezpośrednie lub zarządzane zewnętrznie: 64/67 (95.5%)
  🧭 Znane pokrycie: 65/67 (97.0%)
  🚫 Wykluczone z inwentarza/potoku: 1

  ✅ Updater zweryfikowany/bezpośredni: 26
       · Antigravity (zweryfikowane przez feed producenta)
       · Antigravity IDE (zweryfikowane przez feed producenta)
       · ChatGPT → ChatGPT / Codex (zweryfikowane przez feed producenta)
       · Claude (zweryfikowane przez feed producenta)
       · CodeEdit (zweryfikowane pobranie bezpośrednie)
       · Comet (updater Chromium (Omaha))
       · Cursor (zweryfikowane przez feed producenta)
       · Docker → Docker Desktop (zweryfikowane przez feed producenta)
       · Firefox Developer Edition (zweryfikowane pobranie bezpośrednie)
       · Gemini (Google Keystone)
       · Google Chrome (Google Keystone)
       · Google Drive (Google Keystone)
       · KeePassXC (zweryfikowane pobranie bezpośrednie)
       · Ledger Wallet → Ledger Live (zweryfikowane pobranie bezpośrednie)
       · Microsoft Excel (Microsoft AutoUpdate)
       · Microsoft OneNote (Microsoft AutoUpdate)
       · Microsoft Outlook (Microsoft AutoUpdate)
       · Microsoft PowerPoint (Microsoft AutoUpdate)
       · Microsoft Word (Microsoft AutoUpdate)
       · OpenCode (zweryfikowane przez feed producenta)
       · Proton Drive (weryfikacja Sparkle appcast)
       · Proton Mail (zweryfikowane przez feed producenta)
       · Remote Desktop Manager (zweryfikowane przez feed producenta)
       · Trezor Suite (zweryfikowane pobranie bezpośrednie)
       · Visual Studio Code (zweryfikowane pobranie bezpośrednie)
       · Warp (zweryfikowane przez feed producenta)

  ⏳ Updater uruchomiony — wynik niezweryfikowany: 1
       · Microsoft Teams (updater Teams + obserwowany fallback MAU)
```

### 2.6. `git log --oneline main..HEAD`
```text
f22a772 fix(v1.5.0): vendor feed row exact field matching in awk (F12)
73fe9fe docs(v1.5.0): sync documentation, i18n keys, and coverage labels (F11)
96a0125 fix(v1.5.0): run summary attributes ipad to appstore and deduplicates casks (F10)
785e479 fix(v1.5.0): google omaha checks specific app id and wakes updaters once (F9)
21db2a4 fix(v1.5.0): docker update waits for completion before stopping engine (F8)
8d9fe32 fix(v1.5.0): stale days check does not override verified vendor statuses (F7)
3f44923 fix(v1.5.0): native clis update even when managed node is absent (F6)
1be1ea3 fix(v1.5.0): app store ipad verification treats lookup failure as soft fail (F5)
cb1150a fix(v1.5.0): vendor direct diagnostics, ditto copy, and pre-install verification (F4)
fe5f3b6 fix(v1.5.0): inventory sync mas7 ndjson, ipad bundle identity and legend (F3)
0cb56b8 fix(v1.5.0): cli version retention protects active directory (F2)
7f90292 fix(v1.5.0): cask downgrade guard and app targets extraction (F1)
7924c3c fix(v1.5.0): test harness stops masking missing pythonpath and syntax errors (F0)
f817377 docs(review): implementation report and final verification (T15)
8f3faeb docs(v1.5.0): vendor truth documentation, check_vendor_feeds diagnostic tool, and version bump (T14)
d81fa4f feat(system): batch restart labels and filter diagnostics on degraded runs (T13)
56c4d5f feat(summary): attribute between-step background changes to background category (T12)
d23d6f9 feat(inventory): sync all groups, recompute summary and legend without drift (T11)
3a579c0 feat(cli): only update installed tools, use self-updaters, and prune old versions (T10)
141fc04 feat(brew): detect orphan casks, filter sudo requirements, and narrow greedy upgrades (T9)
d606559 feat(internet): implement status codes, counts and uninstalled app summary filtering (T8)
38ba048 feat(appstore): App Store iPad lookup gating and appstore managed guard (T7)
82a7da7 feat(docker): vendor feed check first and quiet CLI update (T6)
8164bd3 feat(chromium_updaters): Google and Comet Omaha verification and Chromium updater handler (T5)
f87cf8d feat(vendor_direct): vendor direct installation and silent launch truth path (T4)
4ed1c6a feat(cask_oracle): restrict oracle to non-vendor apps and require exact equality (T3)
7369140 feat(internet): honest Sparkle verification and stale feed handling (T2)
2989d43 feat(vendor_feeds): vendor feeds module and three-way version compare (T1)
```

### 2.7. `git diff --stat main..HEAD | tail -5`
```text
 update_brew.sh                                     |  143 ++-
 update_internet_apps.sh                            |  218 ++--
 update_npm_cli.sh                                  |   88 +-
 update_system.sh                                   |   49 +-
 109 files changed, 9541 insertions(+), 559 deletions(-)
```

---

## 3. Diff F3 na żywym inwentarzu (`scratch/F3_inventory.diff`)

Weryfikacja inwentarza pod kątem kryteriów F3.7:
- macOS version header: macOS 27.0 Golden Gate (Build 26A428) (`~` home path) — ✅
- `GarageBand` włączony w główną tabelę GRUPY 2 (brak zduplikowanego odłączonego wiersza) — ✅
- `Notion Web Clipper` (odinstalowany) poprawnie usunięty — ✅
- Sekcja iPad zawiera wyłącznie identyfikatory `.app`: `IPMIView`, `Picsart`, `S2M`, `TrackMan.Go.Ios`, `UniFi`, `WiFiman` — ✅
- `IPMIView` usunięty z GRUPY 3 (brak duplikatu z sekcją iPad); `TrackMan.Go.Ios` usunięty z 🆕 — ✅
- Agregacja grup inwentarza zaktualizowana — ✅

> **Uwaga:** Pełny diff inwentarza `APPLICATIONS.md` znajduje się wyłącznie w `scratch/F3_inventory.diff` (plik ignorowany przez git).
```

Wszystkie kryteria akceptacji F3.7 zostały w 100% spełnione:
1. `GarageBand` włączony w główną tabelę GRUPY 2 (brak zduplikowanego odłączonego wiersza).
2. `Notion Web Clipper` (odinstalowany) poprawnie usunięty.
3. Sekcja iPad zawiera wyłącznie identyfikatory `.app`: `IPMIView`, `Picsart`, `S2M`, `TrackMan.Go.Ios`, `UniFi`, `WiFiman`.
4. `IPMIView` zniknął z GRUPY 3; `TrackMan.Go.Ios` zniknął z 🆕.
5. Linia `System:` została wyczyszczona i sformatowana: `> **System:** macOS 27.0 Golden Gate (Build 26A428)`.
6. Legenda zyskała sekcje App Store i iPad z zainstalowanymi nazwami.
7. Separator `---` przed `## Podsumowanie` zachowany; podsumowanie przeliczone bez dryfu (320 aplikacji).
8. Brak jakichkolwiek ostrzeżeń `skipped_groups`.

---

## 4. Odchylenia od specyfikacji promptu

Brak jakichkolwiek nieautoryzowanych odchyleń. Wszystkie wymagania F0–F12 zrealizowano zgodnie z instrukcjami z zachowaniem:
- Bash 3.2 compatibility (`set -o pipefail`, brak `declare -A`, `mapfile`, `readarray`).
- Braku nowych standalone skryptów Pythona (moduły czysto funkcyjne w `lib/python/`).
- Zgodności i18n we wszystkich 7 językach (EN, PL, DE, ES, FR, IT, PT).
- Zasad bezpieczeństwa i integralności procesów.

---

## 5. Rzeczy niezweryfikowane na żywo (zgodnie z polityką read-only)

Zgodnie z bezwzględną zasadą read-only na żywym środowisku:
- Nie uruchamiano `softwareupdate -i <label> -R` (instalacja aktualizacji systemu macOS).
- Nie uruchamiano `mas upgrade` ani `sudo mas upgrade`.
- Nie uruchamiano mutujących poleceń instalacyjnych `brew upgrade --cask` na żywo.
- Nie uruchamiano faktycznych instalacji GUI Track 2 ani zamykania aplikacji GUI.
- Wszystkie te mechanizmy zostały w pełni przetestowane pod izolowanymi mockami i fiksturami w testach jednostkowych / integracyjnych (`tests/`).
