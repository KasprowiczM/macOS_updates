# Ultra Review — macOS Updates v1.4.5 po upgrade do macOS 27 Golden Gate (Fable 5.1, v1)

**Data:** 2026-09-16 (12:58–13:40 lokalnie)
**Zakres:** repozytorium (`main` = `ea61efd` + 11 niezacommitowanych plików), żywy system po upgrade 26.6.2 → 27.0, ostatni przebieg `logs/update_all_20260916_110633.log` (wykonany jeszcze na 26.6.2, tuż przed upgrade), dokumentacja Apple/Homebrew/mas dot. macOS 27.
**Maszyna:** Apple Silicon, **macOS 27.0 (26A428)**, Bash 3.2.57 (arm64-apple-darwin26), zsh 5.9, Python 3.14.7 (Homebrew), Homebrew **7.0.2**, Xcode **27.0 (27A266a)**, mas **7.0.0**, Node 26.8.2 / npm 12.0.2 (managed prefix).
**Metoda:** procedura `ultra-review` (6 faz, evidence-first). Każda liczba pochodzi z komendy wykonanej w tej sesji. **Bez zmian w kodzie** — ten plik i `gemini_3.8_flash_macos27_prompt_v1.md` to jedyne artefakty.

---

## 0. Wniosek w jednym zdaniu

v1.4.5 zamknęło regresje z poprzedniego review (Codex 0.154.0, agy 1.2.4, OpenCode 1.18.31 — wszystkie zaktualizowane i mierzalne), ale **upgrade do macOS 27 ujawnił trzy luki, które toolkit sam wywołał lub przemilczał w tym samym przebiegu**: (1) krok 1 zaktualizował Xcode do 27.0 przez `mas`, po czym krok 3 (Homebrew) padł w całości na `You have not agreed to the Xcode license` — toolkit nie zna tej zależności; (2) `softwareupdate -l` pokazał macOS 26.7 **i** macOS 27 jednocześnie, użytkownik odmówił, a krok 6 zaraportował `OK completed` z `system_upgraded: 0` i bez żadnego `pending` — trzy dostępne aktualizacje zniknęły z JSON-a; (3) macOS 27 **usunął Rosettę** przy upgrade, a jedyna aplikacja Intel-only na tej maszynie (DJI Assistant 2) jest w inwentarzu jako „ręczna aktualizacja” bez informacji, że od dziś nie wystartuje, a od macOS 28 nie wystartuje nigdy.

---

## 1. Faza 1 — pomiar stanu zastanego (ground truth)

| Sonda | Wynik |
|---|---|
| `sw_vers` | `27.0` / `26A428` — Golden Gate, wydany 2026-09-14 |
| `/bin/bash --version` | **3.2.57** — ograniczenie Bash 3.2 pozostaje w mocy na macOS 27 |
| `git status --short` | `main` = `origin/main` (0 niewypchniętych), **11 plików zmodyfikowanych (+1317/−190), 3 nieśledzone**; zmiany leżą w working tree od 2026-09-10 |
| nieśledzone | `ULTRA_REVIEW_REPORT.md` **w katalogu głównym** (łamie konwencję `docs/reviews/`), `docs/reviews/archive/fable5.1_ultra_review_v1.md`, `tests/test_run_log_regressions_20260910.py` |
| tagi | nadal **tylko `v1.0.21`** — macOS CI (tag/dispatch) nie uruchomiło się dla v1.1–v1.4.5 |
| `bash run_tests.sh` | `Ran 291 tests in 34.8s — OK`, gitleaks 112 commitów czysto, `ALL CHECKS PASSED` (z niezacommitowanymi zmianami) |
| `agentic lint` | 0 błędów (10 ostrzeżeń / 21 info dotyczą skarbca) |
| `launchctl list` | LaunchAgent projektu nieinstalowany; działają tylko `com.agentic.*` |
| `brew config` | `macOS: 27.0-arm64`, `CLT: 27.0`, `Xcode: 27.0`, `Rosetta 2: false` |
| `brew doctor` | **„Your Command Line Tools (CLT) does not support macOS 27” → Tier 2**; `/Library/Developer/CommandLineTools` istnieje, ale `pkgutil --pkg-info=com.apple.pkg.CLTools_Executables` → **brak receiptu** (katalog-sierota); `xcode-select -p` → Xcode.app, więc brew realnie używa toolchainu Xcode |
| `xcodebuild -license check` | rc 0 — licencja zaakceptowana **po** przebiegu 11:06 (w logu jeszcze błąd) |
| `brew outdated` | `unbound 1.26.0 < 1.26.1` — zaległość z przebiegu, w którym krok brew nie wykonał się |
| `mas outdated` / `softwareupdate -l` | puste / `No new software available` |
| `mas account` | **`Error: Unexpected argument 'account'`** — podkomenda usunięta w mas 5.0.0 (2025-12-28), nie „problem macOS 26.x” jak mówi komunikat toolkitu |
| Rosetta | `oahd` nie działa, `/Library/Apple/usr/share/rosetta` nie istnieje — **usunięta przez upgrade** |
| Intel-only w `/Applications` (`lipo -archs` na każdym `CFBundleExecutable`) | **1 aplikacja: `DJI Assistant 2(Consumer Drones Series).app` [x86_64]** |
| CLI (`--version`, rc 0) | claude 2.1.273 · codex-cli 0.154.0 · opencode 1.18.31 · agy 1.2.4 · cursor-agent 2026.09.10 — wszystkie sprawne |
| TCC | `sqlite3 ~/Library/Application Support/com.apple.TCC/TCC.db` → **unable to open** (macOS 27 zamyka bezpośredni dostęp; toolkit go nie używa — OK) |
| Homebrew tap trust | `~/.homebrew/trust.json` obejmuje 5 tapów + 2 formuły — `brew outdated` bez ostrzeżeń |

### 1.1 Ostatni przebieg 2026-09-16 11:06 → 11:17 (11 m 10 s, wykonany na 26.6.2)

```
0. Scan:      OK
1. App Store: OK completed   ← Whisper Transcription 15.0 → 15.0.2 (sudo mas upgrade z ID); Xcode 27.0 już na liście
2. npm/CLI:   OK completed   ← pnpm 12.4.1→12.4.2, claude 2.1.270→2.1.273, opencode 1.18.30→1.18.31, agy 1.2.2→1.2.4
3. Homebrew:  ⚠️ (niezweryfikowane) ← "You have not agreed to the Xcode license"; snapshot formuł nie zapisany; brew update odmówił
4. Internet:  OK completed   ← VS Code 1.137.0 → 1.138.0; 12 × "⏳ Uruchomiony (niezweryfikowany)"
5. Inventory: OK             ← 10 pól wersji
6. System:    OK completed   ← softwareupdate: Safari 27.0 + macOS Tahoe 26.7 + macOS 27; "Kontynuować? [T/n]" → anulowano
```

JSON (`run_summary_20260916_110633.json`, `format_version: 3`): `exit_code 0`, `degraded true`, `pending_after_run_brew_formulae: null / "missing"` (uczciwie), `pending_after_run_appstore: 0 / verified`, `pending_after_run_mau: 0 / verified`, `system_upgraded: 0`, **brak** jakiegokolwiek klucza `pending_after_run_system`. `items` zawiera 6 `updated` + 1 `unconfirmed` (Step: Homebrew) — nowa sekcja per-item działa i zgadza się z logiem.

Po przebiegu użytkownik wykonał upgrade do 27.0 przez GUI i zaakceptował licencję Xcode ręcznie.

---

## 2. Faza 2 — co działa (zweryfikowane)

- **Regresje P0-1/P0-2/P0-3 z review 2026-09-05 są zamknięte i zmierzone**: per-vendor kontrakt instalatorów — Codex i agy aktualizują się (log 11:06), OpenCode 1.18.31 z działającą binarką, `?` nie pojawia się przy `✅`.
- **`sudo mas upgrade` z jawnymi ID** (reguła 2): Whisper Transcription poszedł z ID `1668083311`, kolejka po przebiegu zmierzona (`mas outdated` puste → `verified`).
- **Uczciwe `null`/`missing` dla brew** przy nieudanym kroku — dokładnie kontrakt M2/R7; toolkit nie zamienił awarii na zero.
- **Schemat v3 z `items`** (niezacommitowany): App Store, npm, internet, brew, MAU w jednej liście z `old/new/status`; deduplikacja, odrzucanie `?`/`unknown`, brak fałszywych „nowo zainstalowanych” przy braku snapshotu `before` — testy `test_run_log_regressions_20260910.py` (17 przypadków) i `test_run_summary.py` (11) pokrywają uwagi z handoffu 2026-09-10 (intersekcja ID, aktywne procesy MAU, przerwanie XPC przy exit 0 → soft 10).
- **Bash 3.2 / `pipefail` / brak `set -e`** — bez zmian, a macOS 27 nadal dostarcza Bash 3.2.57, więc ograniczenie nie jest historyczne.
- **Bezpieczeństwo bez regresji**: 291 testów, gitleaks czysto, brak bezpośrednich odczytów TCC/Containers (macOS 27 by je zablokował).
- **MAU**: 5 aplikacji Office 16.112.4, `pending_after_run_mau: 0` zweryfikowane sentinelem, kwarantanna z TTL zachowana.
- **Homebrew 7.0.2**: tapy zewnętrzne już zaufane w `trust.json`, więc domyślne `HOMEBREW_REQUIRE_TAP_TRUST` w 7.x nie wycina formuł z `steipete/openclaw/anomalyco/oven-sh/supabase`.

---

## 3. Faza 3 — zweryfikowane luki

### P0-1 — Krok 1 aktualizuje Xcode, krok 3 pada na licencji Xcode; toolkit nie zna tej zależności

**Dowód:** log 11:06, linie 64 (`497799835 Xcode (27.0)` w `mas list`), 167 (`Could not save the pre-update formula snapshot`), 173–176 (`Error: You have not agreed to the Xcode license … brew update failed; refusing to use potentially stale metadata`). Skutek: cały krok Homebrew pominięty, `unbound` do dziś zaległy, `pending_after_run_brew_*: missing`.

**Mechanizm:** każda duża aktualizacja Xcode (a macOS 27 = Xcode 27) unieważnia zgodę na licencję; Homebrew (`brew update`, `brew list --versions`, `brew outdated`) odmawia pracy do `sudo xcodebuild -license accept`. `rg xcodebuild` w repo → **0 trafień** poza i18n. Kolejność kroków (App Store → … → Homebrew) gwarantuje, że toolkit sam sobie zepsuje krok 3 przy każdym majorze Xcode.

**Wytyczna:** preflight w `update_brew.sh` (i w `lib/brew.sh` jako strażnik): jeśli `xcode-select -p` wskazuje `Xcode.app` **i** `xcodebuild -license check` ≠ 0 → przy TTY zapytać i wykonać `sudo xcodebuild -license accept` (jawnie, jedna komenda, po `sudo -v`), bez TTY → `pending_brew_* = unknown` z powodem `xcode_license` i komunikatem z dokładną komendą. Dodatkowo `update_appstore.sh`: jeśli w `mas_before/after` zmieniła się wersja Xcode → zapisać `xcode_changed` w sesji, żeby krok 3 mógł to nazwać po imieniu.

### P0-2 — macOS 27 usunął Rosettę; toolkit nie ma świadomości architektury aplikacji

**Dowód:** Apple release notes macOS 27: *„If Rosetta was previously installed, it is not automatically restored after upgrading to macOS 27.0 (163213094)”*; *„All Intel-based software will no longer be compatible with macOS 28.0, excluding legacy games”*. Pomiar: `oahd` nie działa, katalog Rosetty nie istnieje, `lipo -archs` → **DJI Assistant 2 = x86_64 only**. Inwentarz i krok internetowy opisują tę aplikację jako `ℹ️ Ręczna aktualizacja` (log l. 397–399), bez słowa o tym, że **nie uruchomi się** bez `softwareupdate --install-rosetta --agree-to-license` i że za rok zniknie jej kanał w ogóle. `rg rosetta|arch -x86_64` w skryptach → 0 trafień.

**Wytyczna:** (a) w `build_inventory.sh` / `lib/python/inventory.py` dodać kolumnę/marker architektury (`arm64` / `universal` / **`x86_64-only`**) z `lipo -archs` głównego wykonywalnego; (b) `update_internet_apps.sh` — dla `x86_64-only` sprawdzać obecność Rosetty (`/usr/bin/pgrep -q oahd || [ -d /Library/Apple/usr/share/rosetta ]`) i raportować `⚠️ wymaga Rosetty (niezainstalowana po macOS 27); koniec wsparcia: macOS 28`; (c) opcjonalna, **opt-in** flaga `MAC_UPDATE_INSTALL_ROSETTA=1` wykonująca `softwareupdate --install-rosetta --agree-to-license` (bez `-R`, to nie jest aktualizacja systemu); domyślnie tylko informacja; (d) `report_update_coverage.sh` — nowa kategoria „Intel-only / EOL macOS 28”.

### P0-3 — Krok macOS raportuje `OK completed` po odmowie użytkownika; brak `pending_after_run_system`; brak polityki majora

**Dowód:** `update_system.sh:99` → `exit 0` po `Aktualizacja anulowana`; `update_all.sh:1959` mapuje rc 0 na `"$L_STATUS_OK completed"`. JSON: `system_upgraded: 0`, żadnego `pending_*_system`, żadnego `verification`. A `softwareupdate -l` zwrócił **trzy** pozycje (Safari 27.0, Tahoe 26.7, macOS 27). Detektor chroniczny nigdy tego nie zobaczy.

Drugi problem tej samej ścieżki: gdyby użytkownik odpowiedział „T”, poszłoby `sudo softwareupdate -ia -R` — **instaluje wszystko rekomendowane**, czyli przy równoczesnej dostępności 26.7 i 27.0 toolkit sam decyduje o skoku majora (i restarcie do nowego systemu) bez osobnej zgody. Etykiety macOS 27 nie mają nazwy kodowej (`macOS 27-26A428`, `Safari27.0TahoeAuto-27.0`) — obecny `grep -qi restart` działa, ale nie rozróżnia „minor” od „major”.

**Wytyczna:** (1) stan kroku `skipped_by_user` (nowy klucz i18n, nie `OK`), `pending_after_run_system = <liczba etykiet>` + `verification: verified` + lista etykiet w `items` jako `pending`; (2) parsować bloki `* Label: … Title: …, Version: X` i klasyfikować: `major` gdy `major(X) > major(sw_vers)`; domyślnie instalować **tylko** same-major przez `softwareupdate -i "<label>" -R` (po jednej etykiecie), a upgrade majora wyłącznie z `MAC_UPDATE_ALLOW_MAJOR_UPGRADE=1` **i** jawnym TTY-potwierdzeniem; (3) w trybie `MAC_UPDATE_NONINTERACTIVE=1` major nigdy; (4) test behawioralny z atrapą `softwareupdate` zwracającą powyższy trzypozycyjny listing z 11:06.

### P1-4 — `mas account` nie istnieje od mas 5.0; komunikat obwinia macOS

**Dowód:** `update_appstore.sh:161` `if mas account …`; `mas account` → `Unexpected argument`; i18n `L_APPSTORE_LOGIN_UNSTABLE="…(known issue on macOS 26.x)"`, `L_MSG_APPSTORE_MAS_LIMIT`, `L_MAS_VERSION_OLD`, `L_MSG_MAS_OLD/FIX` — cztery komunikaty przypisują usunięcie podkomendy systemowi. Fallback przez `mas list` działa, więc to defekt prawdomówności, nie funkcji.

**Wytyczna:** przy `mas version` ≥ 5 nie wołać `account` wcale; komunikat: „mas ≥ 5 nie udostępnia `account`; weryfikuję dostęp przez `mas list`”. Uaktualnić 7 × i18n. Test statyczny: brak `mas account` bez bramki wersji.

### P1-5 — Katalog CLT bez receiptu → Homebrew Tier 2 na macOS 27

**Dowód:** `brew doctor` (dwa ostrzeżenia CLT, „Tier 2 configuration”), `pkgutil` bez receiptu, `softwareupdate -l` nie oferuje CLT. Homebrew 7.0.0 (2026-09-13) deklaruje macOS 27 jako **Tier 1**, ale pod warunkiem aktualnego CLT (`CLT.minimum_version` dla 27 = `27.0.0`). Casks od 7.0 nie wymagają CLT, formuły ze źródeł — tak. `setup.sh`/`migration_setup.sh` nie sprawdzają zgodności CLT z majorem systemu (tylko i18n `xcode-select --install`).

**Wytyczna:** w `setup.sh`/`migration_setup.sh` i jako `ℹ️` w `update_brew.sh`: jeśli `/Library/Developer/CommandLineTools` istnieje bez receiptu lub `pkgutil` wersja < major OS → wypisać jednorazowo instrukcję Homebrew (`sudo rm -rf /Library/Developer/CommandLineTools && sudo xcode-select --install`), **nie wykonywać automatycznie** (rm -rf w /Library to nie jest zadanie toolkitu bez zgody). Zwinąć ostrzeżenie `brew doctor` do jednej linii w logu zamiast 25.

### P1-6 — Sześć dni niezacommitowanej pracy (+1317 linii) na `main`, review w katalogu głównym, brak tagów

**Dowód:** `git diff --stat` (11 plików), `git log` bez commitów od 2026-09-07, `ULTRA_REVIEW_REPORT.md` w root (konwencja: `docs/reviews/`), `git tag` → `v1.0.21`. Zmiana jest testowana (291 OK) i spójna z handoffem 2026-09-10 — powinna trafić na gałąź `fix/mau-v3-summary-items` i do PR, a v1.4.5 dostać tag (jeden run macOS CI ≈ 5 min budżetu, w granicach guardraila z `AGENTS.md`).

### P1-7 — 12 z 32 pozycji internetowych nadal „⏳ niezweryfikowany”, choć wyrocznia casków jest darmowa

Bez zmian od review 2026-09-05 (R6). Log 11:06 l. 414–446. Jedno `brew info --json=v2 --cask …` + istniejące `app_vs_package_version_relation()` zamieniłoby większość ⏳ w `aktualna` / `w tyle`. Po macOS 27 rośnie waga tej weryfikacji: Apple wymusza TLS 1.2+/ATS dla procesów instalacji — vendorowe updatery, które padną po cichu, będą wyglądały identycznie jak te, które działają.

### P1-8 — Zlokalizowane napisy jako stany w JSON

`steps.brew = "Ostrzeżenie zakończono z ostrzeżeniami (niezweryfikowane)"`; `classify_step_status()` w `run_summary.py` musi zgadywać stan z tokenów w 7 językach (`"ostrzeż"`, `"avertissement"`…). Stabilne kody (`ok|warn|error|skipped|unconfirmed`) powinny być zapisywane obok tekstu przez `update_all.sh`, a nie rekonstruowane po fakcie. Częściowo R7 z poprzedniego review.

### P1-9 — `install_launchagent.sh` używa `launchctl load -w`; macOS 27 odrzuca plisty z kwarantanną

**Dowód:** `scripts/install_launchagent.sh:126`; release notes 27: *„launchd no longer supports loading launchd property list files with the quarantine extended attribute (166415497)”*. Plist jest generowany heredokiem (bez xattr), więc dziś działa — ale instalacja z pobranego archiwum lub kopii z chmury (`dev_sync`) może nieść `com.apple.quarantine`. Wytyczna: `xattr -d com.apple.quarantine "$PLIST" 2>/dev/null || true` przed załadowaniem, przejście na `launchctl bootstrap gui/$(id -u)` + `enable`, i uczciwy komunikat, że tryb nienadzorowany nie robi App Store (P2-14 z poprzedniego review, nadal nieopisane).

### P2-10 — Dokumentacja i i18n: „macOS 13–26”, „macOS 26.x”, brak nazwy „Golden Gate”

`13–26` w 11 plikach (7 × README, CLAUDE/AGENTS/GEMINI/CODEX.md); `migration_setup.sh:346` dla `-ge 27` daje etykietę bez nazwy kodowej (powinno być „Golden Gate”); i18n 5 kluczy z „26.x” (P1-4). `docs/agents/critical_rules.md` nie ma sekcji o licencji Xcode ani Rosetcie.

### P2-11 — Stały deferral MAU dla wersji już zainstalowanej

Log l. 307: `DeferralVersions.TEAMS21=26225.1706.5101.3140`; l. 315: zainstalowany Teams `26225.1706.5101.3140`. Deferral wskazuje wersję, która już jest — martwy wpis. Zgodnie z regułą 10 kwarantanna ma TTL; warto, by `mau_quarantine_expired_ids` traktowała „deferral == installed” jako natychmiast wygasły (bez czekania na TTL), bo nie ukrywa już żadnej diagnostyki.

### P2-12 — Pakiety `.pkg` domyślnie `arm64` na macOS 27

Release notes: *„Installer packages which specify no hostArchitecture will now default to arm64”*. `rg "installer -pkg"` w skryptach → 0 trafień (toolkit nie instaluje pkg bezpośrednio), więc dziś bez wpływu; odnotować w `critical_rules.md` na wypadek dodania handlera pkg.

### P2-13 — Inne ustalenia macOS 27 bez wpływu na kod (zweryfikowane negatywnie)

- Bezpośredni odczyt TCC.db zablokowany — toolkit używa sondy `osascript` (`update_appstore.sh:365`), więc TOR 2 działa (log: „Uprawnienie Accessibility potwierdzone”).
- SIP: dostęp do kontenerów innych zespołów deweloperskich domyślnie odmawiany — `rg "Library/Containers|Group Containers"` → 0 trafień; MAU czyta `~/Library/Preferences/com.microsoft.autoupdate2.plist` (poza kontenerem).
- Homebrew 7.0: Intel → Tier 3, macOS 27 AS → Tier 1, casks bez CLT, tap trust domyślnie włączony — `trust.json` już ma wpisy.
- mas 7.0.0 wrapper: `/usr/bin/jq` istnieje na 15+ (macOS 27 też), `sudo` w wrapperze; `sudo mas upgrade <id>` z logu działa.

---

## 4. Faza 4 — kontekst ekosystemu (wrzesień 2026)

| Źródło | Fakt istotny dla projektu |
|---|---|
| Apple, macOS 27 release notes | Rosetta nieprzywracana po upgrade; Intel-only apps przestają działać w macOS 28; Ustawienia › Ogólne listuje niekompatybilne aplikacje Intel; launchd odrzuca quarantined plist; TCC.db niedostępne; SIP zamyka cross-team containers; pkg → arm64 domyślnie; procesy software update / app installation wymagają TLS 1.2+/ATS |
| Apple Support 102527 | Rosetta „through macOS 27”; od 28 tylko podzbiór dla starych gier |
| Homebrew 7.0.0 (2026-09-13) | macOS 27 AS Tier 1 z bottles; Intel Tier 3, koniec 2027-09-01; casks bez CLT; CLT `minimum_version` dla 27 = 27.0.0; `brew doctor` → Tier 2 przy przestarzałym CLT |
| mas 5.0.0 (2025-12-28) / 7.0.0 | `account`/`region`/`signin` usunięte; wymóg macOS 13+; root przez `sudo` dla `upgrade` (workaround installd 26.1+/15.7.2+/14.8.2+) |
| Xcode 27 | Aktualizacja z App Store unieważnia zgodę na licencję → Homebrew odmawia do `sudo xcodebuild -license accept` (zaobserwowane w logu) |
| Praktyka SRE „measured, not claimed” | P0-3: odmowa użytkownika to stan mierzalny (`skipped_by_user`, N pending), nie `OK` |

---

## 5. Faza 5 — macierz punktowa (0–10)

| Wymiar | Ocena | Uzasadnienie |
|---|:--:|---|
| **Prawdomówność raportowania** | **6** | Duży postęp (items, null/missing, brak `✅ ?`), ale `OK completed` przy 3 odrzuconych aktualizacjach systemu i „macOS 26.x” zamiast „mas ≥ 5” |
| Zgodność z macOS 27 | 5 | Działa (Bash 3.2, osascript, mas 7, brew 7), ale brak obsługi licencji Xcode, Rosetty, polityki majora, CLT |
| Architektura i ograniczenia | 8 | Bez zmian: `lib/brew.sh`, `pipefail`, 0 ShellCheck; monolity 2 k linii nadal |
| Bezpieczeństwo i sekrety | 8 | gitleaks czysto, brak odczytów TCC/Containers, PII z poprzedniego review do sprawdzenia po commicie |
| Odporność strażników | 7 | MAU: intersekcja ID, XPC, aktywne procesy — dobrze; brak strażnika Xcode-license i Rosetta |
| Testowalność | 7 | 291 zielonych, nowe testy behawioralne z atrapami `msupdate`; brak testu `softwareupdate` z listingiem 26.7 + 27 |
| Obserwowalność | 7 | `items`, `verification`, `run_status`; brak `pending_system`, stany zlokalizowane w JSON |
| Pokrycie aktualizacji (zweryfikowane) | 6 | 12/32 internet ⏳; 1 aplikacja Intel-only bez ostrzeżenia EOL |
| Dokumentacja — aktualność | 5 | „13–26” w 11 plikach, brak Golden Gate, brak rozdziału o Xcode/Rosetta/CLT |
| Higiena repo / skarbca | 5 | 6 dni bez commita, review w root, brak tagów, karta projektu ze stanem 2026-09-07 |
| Gotowość DR | 8 | bez zmian |
| **Systemowa uczciwość** | **7** | Projekt nauczył się nie zgadywać zer; teraz musi nauczyć się nie nazywać odmowy sukcesem |
| **Łącznie** | **6,6** | 6,3 (2026-09-05) → 6,6: CLI naprawione, macOS 27 otworzył nowe pozycje |

---

## 6. Faza 6 — rekomendacje w kolejności wykonania

Pełny prompt wykonawczy: `docs/reviews/archive/gemini_3.8_flash_macos27_prompt_v1.md`.

| # | Priorytet | Rekomendacja | Zamyka |
|---|---|---|---|
| **R0** | P1 | Przenieść bieżące zmiany na gałąź `fix/mau-v3-summary-items`, przenieść `ULTRA_REVIEW_REPORT.md` do `docs/reviews/`, commit + PR; **nie tagować bez zgody** | P1-6 |
| **R1** | P0 | Strażnik licencji Xcode w `lib/brew.sh` + `update_brew.sh` (TTY: `sudo xcodebuild -license accept` po pytaniu; bez TTY: `unknown` z powodem); marker `xcode_changed` z kroku App Store | P0-1 |
| **R2** | P0 | Krok systemowy: `skipped_by_user`, `pending_after_run_system` + `verification`, etykiety w `items`; parser etykiet; **polityka majora** (`MAC_UPDATE_ALLOW_MAJOR_UPGRADE`, same-major przez `-i <label> -R`); test z listingiem 11:06 | P0-3 |
| **R3** | P0 | Architektura w inwentarzu (`lipo -archs`), status `x86_64-only` + „Rosetta nieobecna / EOL macOS 28”, opt-in `MAC_UPDATE_INSTALL_ROSETTA=1`, kategoria w coverage | P0-2 |
| **R4** | P1 | Bramka `mas version ≥ 5` → bez `mas account`; 7 × i18n bez „macOS 26.x” | P1-4 |
| **R5** | P1 | Diagnoza CLT vs major OS w setup/migration/brew (informacja, nie `rm -rf`), zwinięcie `brew doctor` do 1 linii | P1-5 |
| **R6** | P1 | Wyrocznia casków dla `silent_launch` (`brew info --json=v2 --cask`, read-only), `counts.internet_verified/behind` | P1-7 |
| **R7** | P1 | Stabilne kody stanów kroków zapisywane przez `update_all.sh` do sesji; `classify_step_status` tylko jako fallback dla starych JSON | P1-8 |
| **R8** | P1 | `install_launchagent.sh`: `xattr -d`, `launchctl bootstrap gui/$UID`, README o braku App Store w trybie nienadzorowanym | P1-9 |
| **R9** | P2 | „13–27” w 11 plikach, „Golden Gate” w `migration_setup.sh`, nowa sekcja `critical_rules.md` (Xcode license, Rosetta, CLT, pkg arm64, TLS) | P2-10, P2-12 |
| **R10** | P2 | `mau_quarantine_expired_ids`: deferral == installed → wygasły natychmiast | P2-11 |
| **R11** | P2 | Karta projektu + handoff + `agentic sync` po merge | higiena |

---

## 7. Co dla maszyny użytkownika (poza kodem, do wykonania ręcznie lub przez toolkit po R1–R3)

1. `brew upgrade unbound` (albo po prostu kolejny `bash update_all.sh` — licencja jest już zaakceptowana).
2. Decyzja o CLT: `sudo rm -rf /Library/Developer/CommandLineTools && sudo xcode-select --install` **lub** świadome pozostanie przy toolchainie Xcode 27 (wtedy `brew doctor` będzie marudził, ale bottles działają).
3. Decyzja o Rosetcie: jeśli DJI Assistant 2 jest potrzebny → `softwareupdate --install-rosetta --agree-to-license`; sprawdzić Ustawienia › Ogólne › lista aplikacji Intel (macOS 27 pokazuje ją systemowo) i zaplanować alternatywę przed macOS 28.
4. Sprawdzić `~/Library/Audio/Plug-Ins`, `~/Library/Printers`, `~/Library/ColorPickers` pod kątem wtyczek Intel (release notes 176042635) — toolkit tego nie skanuje.
5. LaunchAgent: decyzja nadal otwarta (karta projektu); nie instalować przed R8.

---

## 8. Czego celowo nie zrobiłem

- Nie uruchamiałem `update_all.sh`, `brew upgrade`, `softwareupdate` w trybie instalacji, `xcodebuild -license accept`, instalacji Rosetty ani niczego, co mutuje system. Wszystkie sondy były read-only (`brew outdated/doctor/config`, `mas outdated`, `softwareupdate -l`, `lipo`, `pkgutil`, `xcodebuild -license check`).
- Nie commitowałem, nie przenosiłem plików, nie edytowałem kodu ani i18n. Dwa nieśledzone pliki review pozostały bez zmian.
- Nie oceniałem `dev_sync/` (osobne review 2026-08-19; H1–H3 zamknięte w v1.4.5 wg karty).
- Nie używałem subagentów — zgodnie z poleceniem; skille: `ultra-review`, `agentic-memory`.

---

## 9. Ślad dowodowy

```bash
sw_vers; uname -m; /bin/bash --version; python3 --version; brew --version; brew config; mas version
git status --short; git diff --stat; git log --oneline -15; git tag --sort=-creatordate
bash run_tests.sh                                   # 291 OK, gitleaks clean
agentic context -p macos-updates --brief; agentic lint
launchctl list | grep -iE "mac-update|macos_updates|agentic"
sed 's/\x1b\[[0-9;]*m//g' logs/update_all_20260916_110633.log; cat logs/run_summary_20260916_110633.json
brew outdated --verbose; brew doctor; brew tap; cat ~/.homebrew/trust.json
mas outdated; mas account; softwareupdate -l
xcodebuild -license check; xcodebuild -version; xcode-select -p
ls -d /Library/Developer/CommandLineTools; pkgutil --pkg-info=com.apple.pkg.CLTools_Executables
pgrep -q oahd; ls /Library/Apple/usr/share/rosetta
for app in /Applications/*.app; do lipo -archs "$app/Contents/MacOS/<CFBundleExecutable>"; done
sqlite3 ~/Library/Application\ Support/com.apple.TCC/TCC.db "select …"   # unable to open (macOS 27)
rg -n "xcodebuild|rosetta|arch -x86_64|TCC.db|Group Containers|com.apple.quarantine|launchctl (bootstrap|load)|installer -pkg|mas account|13–26" …
git diff update_all.sh lib/python/run_summary.py lib/internet_app_updates.sh
for c in claude codex opencode agy cursor-agent; do $c --version; done
```

Źródła zewnętrzne (odczyt 2026-09-16): [Apple — macOS 27 release notes (kopia gist)](https://gist.github.com/applch/de455a43aacf42a8c13c4750b045d3a9), [Apple Support 102527 — Rosetta](https://support.apple.com/en-us/102527), [Apple Support 127257 — What's new in macOS 27](https://support.apple.com/en-us/127257), [Homebrew 7.0.0](https://brew.sh/2026/09/13/homebrew-7.0.0/), [Homebrew Support Tiers](https://docs.brew.sh/Support-Tiers), [Homebrew OS::Mac::CLT](https://docs.brew.sh/rubydoc/OS/Mac/CLT.html), [mas v5.0.0](https://github.com/mas-cli/mas/releases/tag/v5.0.0), [mas v4.0.0](https://github.com/mas-cli/mas/releases/tag/v4.0.0), [mas #1274](https://github.com/mas-cli/mas/issues/1274).

*Wszystkie liczby pochodzą z pomiaru maszyny docelowej 2026-09-16. Gdy ten plik nie zgadza się z kodem, kod wygrywa.*
