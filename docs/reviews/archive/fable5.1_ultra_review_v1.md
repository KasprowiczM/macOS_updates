# Ultra Review — macOS Updates v1.4.4 (Fable 5.1, v1)

**Data:** 2026-09-05 (17:23–17:45 lokalnie)
**Zakres:** całe repozytorium + żywy system docelowy + 26 logów przebiegów (2026-08-19 → 2026-09-05), w tym przebieg `update_all_20260905_172339.log` obserwowany na żywo w trakcie review
**Maszyna referencyjna:** Apple Silicon, macOS 26.6.2 (25G83), Homebrew 6.0.22, mas 7.0.0, Node 26.8.1, npm 12.0.2 (managed prefix)
**Metoda:** procedura `ultra-review` (6 faz, evidence-first). Każda liczba poniżej pochodzi z pomiaru — komendy i wyjścia są cytowane. Repozytorium jest źródłem hipotez, system docelowy jest źródłem prawdy.
**Bez zmian w kodzie.** Ten dokument i `gemini_3.8_flash_high_v1.md` to jedyne artefakty tej sesji.

---

## 0. Wniosek w jednym zdaniu

v1.4.4 naprawiło zawieszenie z 2026-09-03 i dodało obserwowalność, ale **wprowadziło dwie regresje, które od dwóch przebiegów psują krok „Native CLI + npm" na każdym uruchomieniu**: (1) argument `latest` przekazywany do *wszystkich* instalatorów natywnych, choć akceptuje go tylko instalator Claude — Codex i Agy padają z `Unknown argument: latest` (Codex stoi na 0.153.2 przy dostępnym 0.153.4); (2) przełączenie OpenCode na `opencode upgrade --method npm` pod npm 12 z blokadą skryptów `postinstall` zostawiło **niedziałający plik binarny `opencode`**, a toolkit 2026-09-04 zaraportował to jako `✅ opencode-cli: ?`. To trzecie review z rzędu, w którym główny defekt należy do tej samej klasy: *system twierdzi coś, czego nie zmierzył*.

---

## 1. Faza 1 — pomiar stanu zastanego (ground truth)

| Sonda | Wynik |
|---|---|
| `git status --short` | czysto; `main` = `616ac3f` = `origin/main`; 0 niewypchniętych commitów; 0 stash |
| gałęzie | 5 (4 gałęzie `fix/*` wszystkie zmergowane do `main`, jedna w worktree `…-v144-wt`) |
| tagi | **tylko `v1.0.21`** — v1.1 … v1.4.4 nie mają tagów |
| `bash run_tests.sh` | `Ran 229 tests in 37.5s — OK`, gitleaks czysto, `ALL CHECKS PASSED` |
| `shellcheck -S warning update_*.sh lib/*.sh scripts/*.sh` | 0 znalezisk |
| `agentic lint` | 0 błędów (178 ostrzeżeń dotyczą skarbca, nie tego projektu) |
| `launchctl list \| grep macos-updates` | brak — LaunchAgent projektu **nie jest zainstalowany** |
| `logs/` | 26 logów `update_all_*`, 22 `run_summary_*.json`, `version_history.tsv` (99 KB) |
| ostatnie 2 przebiegi | 09-04: `exit 0, degraded` (npmcli ⚠️); 09-05: `exit 0, degraded` (appstore ⚠️ + npmcli ⚠️) |
| przebieg 09-03 | zawieszony na Claude TUI, brak `run_summary` (naprawione w v1.4.4) |
| `VERSION` | `1.4.4` |
| wersje w dokumentach | `CLAUDE.md` **1.4.1**, `GEMINI.md` **1.4.1**, `AGENTS.md` **1.4.3**, `README*.md` (7 plików) **1.4.0**, `CONTRIBUTING.md` **1.0.2** |
| i18n | 7 plików `lang_*.sh`, każdy **604 klucze** — parytet zachowany |
| prywatność (tracked) | 2 adresy e-mail + nazwy montowań chmur w `docs/reviews/archive/ULTRA_REVIEW_2026-08-19.md:205`; hostname w `ULTRA_REVIEW_2026-09-02.md`; `/Users/<login>` w 4 tracked plikach `docs/` |

### 1.1 Przebieg na żywo 2026-09-05 17:23 → 17:30 (7 m 05 s)

```
0. Scan:      OK
1. App Store: Ostrzeżenie (niezweryfikowane)   ← TOR 2 kliknął „Update All", mas nie widział nic
2. npm/CLI:   Ostrzeżenie (niezweryfikowane)   ← codex, opencode, agy: 3 błędy
3. Homebrew:  OK  (6 formulae + 2 caski: brave-browser, perplexity)
4. Internet:  OK  (13 aplikacji „⏳ Uruchomiony (niezweryfikowany)")
5. Inventory: OK  (18 zmian wersji)
6. System:    OK  (No new software available)
```

Diagnostyka z kroku 2 (sanityzowana, z logu):

```
=== codex native installer (exit=1) ===
Unknown argument: latest
=== opencode upgrade (exit=1) ===
Error: opencode-ai's postinstall script was not run.
=== agy native installer (exit=1) ===
[ERROR] Unknown parameter: latest
```

Ten sam wzorzec dla codex/agy jest w przebiegu 09-04 (linie 156–160 logu). Seria `npmcli` = 2 przebiegi; detektor chroniczny (próg 3) zapali się przy następnym.

---

## 2. Faza 2 — co działa i jest architektoniczną siłą (zweryfikowane)

- **Naprawa zawieszenia (Z0) działa.** `lib/proc.sh` ma `--kill-after=5`, test `test_term_ignoring_child_still_returns_124` przechodzi w <10 s; Claude poszedł ścieżką `claude update` i zakończył się `✅ 2.1.261` w obu przebiegach po v1.4.4. Krok 2 nie blokuje już kroków 3–6.
- **Inwarianty v1.4.3 są nienaruszone**: `pending_after_run_*` w `counts` (wszystkie 0 po 09-05), `run_counts.json` → `counts`, TOR 1 z jawnymi ID + jeden retry, IPMIView/DJI jako `ℹ️`. MAU: „Microsoft AutoUpdate: ✅ Aktualny", `pending_after_run_mau: 0`.
- **Trójdzielna diagnostyka App Store jest zapisywana zawsze** (`appstore_diag.txt`: before TRACK 1 / TRACK 2 / after both) — 09-05 pokazuje dokładnie rozbieżność, o którą chodziło w R4: `mas outdated` puste, GUI `UPDATE_ALL_DEEP`.
- **`lib/brew.sh` jako jedyna brama do Homebrew** działa: żadne `2>&1` na `brew outdated`, guard downgrade'u casków przepuścił Brave 1.94.119.0 → 1.94.121.0 poprawnie (regresja z 08-26 nie wróciła).
- **Bezpieczeństwo bez zastrzeżeń w kodzie**: atomowe zapisy, `chmod 600` na kopiach profili z rotacją (`MAC_UPDATE_MAX_PROFILE_BACKUPS`), sanityzacja stderr npm (`sanitize_npm_stderr`), gitleaks w pakiecie testów, zero hardcode'ów `/Users/` w skryptach.
- **Bash 3.2 i `set -o pipefail`** respektowane we wszystkich 6 orkiestratorach; brak `set -e`, brak `declare -A`/`mapfile`.
- **Dokumentacja procesu** jest wzorowa: CHANGELOG w formie objaw → przyczyna → naprawa → pomiar, plan v1.4.4 z checkboxami, audyt strażników, 14 handoffów w skarbcu, decyzje w `decisions/`.
- **`version_history.tsv`** (99 KB) jest cichym skarbem: per-przebieg, per-app, wersja i metoda — gotowe źródło do weryfikacji TOR 2 i trendów (patrz R5).
- **Budżet GitHub Actions** jest respektowany: Ubuntu-only na push, macOS tylko tag/dispatch, `concurrency` + `timeout-minutes`.

---

## 3. Faza 3 — zweryfikowane luki (P0 / P1 / P2)

### P0-1 — Regresja v1.4.4: `sh -s latest` łamie instalatory Codex i Agy na każdym przebiegu

**Objaw:** 09-04 i 09-05: `⚠️ Aktualizacja codex-cli nie powiodła się`, `⚠️ Aktualizacja agy-cli nie powiodła się`.

**Kod:** `update_npm_cli.sh:887`

```bash
env $installer_env sh -c "curl -fsSL '$install_url' | sh -s latest" </dev/null
```

**Dowód z instalatorów dostawców (pobrane 2026-09-05, tylko odczyt):**

| Instalator | Parsowanie `$1` | Skutek `latest` |
|---|---|---|
| `https://claude.ai/install.sh` | `TARGET="$1"`, akceptuje `^(stable\|latest\|X.Y.Z)$` | OK |
| `https://chatgpt.com/codex/install.sh` | `Usage: install.sh [--release VERSION]`; `*) echo "Unknown argument: $1"` | **exit 1** |
| `https://antigravity.google/cli/install.sh` | `Usage: install.sh [options]`; `*) echo "[ERROR] Unknown parameter: $1"` | **exit 1** |
| `https://cursor.com/install` | nie parsuje argumentów | ignoruje (przypadkiem działa) |

**Pomiar skutku:** `~/.local/bin/codex --version` → `codex-cli 0.153.2`; `gh api repos/openai/codex/releases/latest` → `rust-v0.153.4`. Codex jest w tyle **z winy toolkitu**, choć krok raportuje tylko miękkie ostrzeżenie.

**Jak to przeszło przez testy:** commit `7eea126` („update stale stdin-detach assertion after T2 sh -s latest change") **rozszerzył test**, żeby akceptował nową formę, zamiast pozwolić testowi złapać regresję. Test sprawdza treść pliku (`assertIn`), nie zachowanie — nie mógł wiedzieć, że dwa z czterech dostawców odrzucą argument. To dokładnie ryzyko „regex-on-file", o którym ostrzega plan v1.4.4 w swojej pierwszej linii.

### P0-2 — OpenCode CLI jest niedziałający na maszynie, a toolkit zgłosił sukces

**Pomiar (2026-09-05):**

```
$ ~/.local/share/mac-update/npm-global/bin/opencode --version
Error: opencode-ai's postinstall script was not run.
$ ls …/node_modules/opencode-ai/node_modules/      → puste (brak opencode-darwin-arm64)
$ cat …/node_modules/opencode-ai/bin/opencode.exe  → 479-bajtowy stub wypisujący powyższy błąd
$ …/npm-global/bin/npm --version                   → 12.0.2
$ npm config list -l | grep allow-scripts          → allow-scripts = ["@higgsfield/cli"]   (z ~/.npmrc)
$ npm view opencode-ai version                     → 1.18.29   (zainstalowane: 1.18.27)
```

**Łańcuch przyczynowy (trzy ogniwa, każde zmierzone):**

1. Toolkit sam podniósł `npm` do **12.0.2** w managed prefix (`✅ npm: 12.0.2`). npm 12 domyślnie **nie uruchamia skryptów cyklu życia zależności**, chyba że pakiet jest na liście `allow-scripts`. W `~/.npmrc` tej maszyny lista zawiera wyłącznie `@higgsfield/cli` (wpis zostawiony przez inny instalator).
2. v1.4.4 zmieniło metodę `opencode-cli` z `npm` na `self-update` → `opencode upgrade --method npm`. Vendorowy updater wywołuje `npm i -g opencode-ai@latest` **npm-em z PATH**, czyli 12.0.2 → `postinstall.mjs` (pobiera binarkę platformy) nie wykonał się → drzewo bez binarki, stub zamiast programu. mtime katalogu: **2026-09-04 13:28** — dokładnie krok 2 przebiegu 09-04.
3. Log 09-04, linia 144: **`✅ opencode-cli: ?`**. `detect_command_version` zwróciło `?` (bo `--version` padło), a `print_ok` to przyjął. 09-05 `opencode upgrade` już nie może wystartować (binarka jest stubem) → błąd → będzie tak na każdym przebiegu, bez ścieżki samonaprawy. Drzewo bez `postinstall` **ukrywa własne wejście diagnostyczne** (reguła 10 z `AGENTS.md`), a strażnik nie ma TTL ani drogi powrotu.

**Waga:** to nie jest „niezweryfikowane" — to zepsute narzędzie użytkownika, zgłoszone jako sukces. Klasa defektu identyczna z 1.4.2 (MAU „released" bez odczytu domeny) i 1.4.3 (TOR 1 „completed" przy pominiętym WhatsAppie).

### P0-3 — Zielony status przy nieznanej wersji jest dozwolony w całym kroku 2

`print_ok "${display_name}: $(detect_command_version …)"` jest wywoływane w czterech gałęziach (`npm`, `native-installer` ×2, `self-update`) bez sprawdzenia, czy wynik jest semverem ani czy `--version` wyszło z kodem 0. `normalize_semver "${version:-?}"` celowo produkuje `?`. Brak jednego miejsca, które powiedziałoby: **`?` po aktualizacji = porażka**. P0-2 jest tylko pierwszym pakietem, który w to wpadł.

### P1-4 — App Store TOR 2: trwale niesprawdzalny stan, choć dane do weryfikacji już są

09-05: `mas outdated --accurate` → puste; AppleScript → `UPDATE_ALL_DEEP` (kliknięto); krok kończy się `⚠️ Track 2 is still installing in the background; its completion is not verified`. 09-04: `NO_UPDATES_FOUND` → `OK`. Operator nie wie, czy 09-05 przycisk dotyczył UniFi/WiFiman/Picsart (jedyne `appstore_gui`), czy był fałszywym trafieniem.

A jednak `version_history.tsv` zapisuje `UniFi 10.37.1 / WiFiman 1.37.1 / Picsart 30.7.1` (`appstore_gui`) w każdym przebiegu — `app_version()` już czyta `mdls kMDItemVersion` dla aplikacji iPad. Pomiar wersji bundli **przed** i **po** TOR 2 (z krótkim settle) zamieniłby „niezweryfikowane" na jeden z trzech mierzalnych stanów: `zainstalowano X→Y`, `nic się nie zmieniło (przycisk bez kandydatów)`, `w toku`. Trzecia sekcja `appstore_diag.txt` mówi tylko o `mas`, które z definicji nie widzi iPad apps.

### P1-5 — Krok internetowy: 13 z 32 pozycji to „⏳ Uruchomiony (niezweryfikowany)", a krok jest `OK completed`

Z podsumowania 09-05: ChatGPT, Claude, Gemini, Comet, Antigravity, Antigravity IDE, OpenCode Desktop, Proton Mail, Teams, Docker, Warp, Cursor — `silent_launch`. `counts` nie rozróżnia zweryfikowanych od uruchomionych; `report_update_coverage.sh` liczy je jako pokryte.

**Pomiar wyroczni (tylko odczyt, `brew info --json=v2 --cask`, 2026-09-05):**

| Aplikacja | Zainstalowane (`CFBundleShortVersionString`) | Cask Homebrew | Relacja |
|---|---|---|---|
| ChatGPT | 26.901.41600 | 26.901.41600 | **aktualna** |
| Claude | 1.46388.4 | 1.46388.4 | **aktualna** |
| Cursor | 3.19.7 | 3.19.7 | **aktualna** |
| Warp | 0.2026.09.02.08.27.01 | 0.2026.09.02.08.27.stable_01 | aktualna (po normalizacji) |
| Docker Desktop | 4.89.0 | 4.89.0 | **aktualna** |
| Microsoft Teams | 26213.1006.5011.1671 | 26213.1006.5011.1671 | **aktualna** |
| **Antigravity** | 2.11.0 | 2.12.2 | **w tyle** — updater uruchamiany co dzień nie dowiózł |
| **OpenCode Desktop** | 1.18.27 | 1.18.29 | **w tyle** |
| Proton Mail | 1.14.0 | 1.13.4 | zainstalowana nowsza (cask się spóźnia) |
| Comet | 151.0.7922.247 | 145.2.7632.4581 | inny schemat (prefiks Chromium) → `unknown` |
| Gemini | 1.107.3.828 | 2.10.1 | mapowanie casku do sprawdzenia |

Wszystkie 11 aplikacji `silent_launch` **mają cask**. Jedno wywołanie `brew info --json=v2 --cask a b c …` (bez instalowania czegokolwiek) + istniejące `app_vs_package_version_relation()` z `lib/version.sh` zamienia 6 „niezweryfikowanych" w „aktualna", a 2 w konkretne „w tyle o N dni" — bez zmiany kanału aktualizacji (doktryna „najszybszy zaufany kanał wygrywa" z `Opus5_Max_Ultra_Review_v6.md` zostaje nienaruszona: cask jest wyrocznią, nie instalatorem).

### P1-6 — Zawieszenie jest niewidzialne dla detektora chronicznego

Przebieg 09-03 nie zapisał `run_summary` (proces zginął w kroku 2). `find_chronic_streaks` widzi tylko pliki, które istnieją; seria „nie dokończono" nie istnieje jako pojęcie. Dodatkowo w `update_all.sh:2019` generator podsumowania ma `2>/dev/null || true` — awaria zapisu JSON jest cicha, a detektor traci punkt danych bez śladu. Wynik detektora idzie tylko na stdout — nie do `run_summary_*.json`, nie do powiadomienia `MAC_UPDATE_NOTIFY`.

### P1-7 — Dwa `npm` w managed prefix: raportowany 12.0.2, instalujący 11.19.0

`install_latest_npm_packages` używa `active_npm="$N_PREFIX/bin/npm"` (11.19.0, dołączony do Node), a `✅ npm: 12.0.2` dotyczy `NPM_GLOBAL_BIN/npm`, który jest pierwszy w PATH użytkownika i w PATH podprocesów vendorowych updaterów. Dwie różne polityki `allow-scripts`, dwie wersje — trudne do zdiagnozowania, gdy jeden z nich zepsuje instalację (P0-2).

### P1-8 — Prywatność w publicznym repozytorium

`git grep` w tracked plikach:

- `docs/reviews/archive/ULTRA_REVIEW_2026-08-19.md:205` — **dwa prywatne adresy e-mail** i nazwy montowań chmur (Proton Drive / Google Drive).
- `docs/reviews/archive/ULTRA_REVIEW_2026-09-02.md:5,159` — nazwa hosta maszyny referencyjnej.
- `docs/archive/plans/2026-09-03-…md:624`, `docs/reviews/archive/GEMINI_TASK_2026-09-02.md`, `ULTRA_REVIEW_2026-06-20.md`, `ULTRA_REVIEW_2026-08-05.md` — ścieżki `/Users/<login>/…`.

`gitleaks` nie oznacza adresów e-mail ani hostname'ów. `docs/reviews/README.md` sam ostrzega: „prompt and report files can quote local paths and machine-specific detail" — ostrzeżenie nie zastąpiło kontroli. Kontrakt Agentic OS („Privacy boundary — CRITICAL") jest tu naruszony.

### P1-9 — Dryf dokumentacji: pięć różnych numerów wersji i trzy nieaktualne reguły

- Wersje: `1.4.4` (VERSION) vs `1.4.3` (AGENTS.md) vs `1.4.1` (CLAUDE.md, GEMINI.md) vs `1.4.0` (7× README) vs `1.0.2` (CONTRIBUTING). Konwencja z karty projektu — „zmiana widoczna dla użytkownika = aktualizacja wszystkich 7 README" — nie jest egzekwowana testem.
- `docs/agents/critical_rules.md §2` pokazuje **gołe** `sudo env MAS_NO_AUTO_INDEX=1 mas upgrade` — dokładnie to, czego reguła 2 w `AGENTS.md` od v1.4.3 zabrania.
- `critical_rules.md` ma zdublowane numery sekcji (`## 5` ×2, `## 6` ×2 obok `6a–6d`).
- `troubleshooting.md`: „Office reported Held back … Nothing to do — it clears itself" — obalone w v1.4.3 (nie zwalniało się przez 7 tygodni; dodano TTL).
- `README.md` tabela zmiennych nie zna `MAC_UPDATE_MAU_QUARANTINE_MAX_DAYS`, `MAC_UPDATE_CHRONIC_WINDOW/THRESHOLD`, `MAC_UPDATE_NATIVE_INSTALLER_TIMEOUT`, `MAC_UPDATE_MAX_PROFILE_BACKUPS` (0 trafień).
- README DE/ES/FR/IT/PT mają 116–119 linii wobec 334 (EN) / 350 (PL) — to skróty, nie tłumaczenia; „7 języków" jest prawdziwe dla UI (604 klucze), nie dla dokumentacji.
- `AGENTS.md` numeruje reguły 1–8, potem 10 (brak 9).

### P1-10 — Testy adaptowane do kodu zamiast kodu do testów

Poza `7eea126` (P0-1): 16 testów v1.4.4 to w większości `assertIn(<fragment kodu>, source)`. Test `test_opencode_self_update_calls_upgrade_not_update` przechodzi, gdy binarka jest stubem. Testy behawioralne istnieją (`run_proc` na `lib/proc.sh`) i to one złapały prawdziwy błąd — wzorzec do rozszerzenia: fałszywe `curl`/`sh`/`npm` na PATH przechwytujące argumenty.

### P2-11 — Brak tagów wydań → zadanie CI na macOS nigdy nie startuje

`ci.yml`: job `test` na `macos-latest` warunkowany `startsWith(github.ref, 'refs/tags/v')` lub dispatch. Ostatni tag to `v1.0.21`. Wydania 1.1–1.4.4 nigdy nie były testowane na prawdziwym Bash 3.2 w CI. Jeden tag na wydanie = ~5 min budżetu/miesiąc — mieści się w guardrailu.

### P2-12 — Szum z zewnętrznych tapów Homebrew

`brew update` wypisuje 6 bloków `Warning: Calling the 'verified' parameter … is deprecated` (steipete/tap ×4, openclaw/tap, anomalyco/tap) — ~25 linii szumu na przebieg, wymieszanych z prawdziwym wyjściem. Nie wina toolkitu, ale toolkit może to zwinąć do jednej linii `ℹ️ 3 zewnętrzne tapy zgłaszają deprecacje (szczegóły: brew_update.log)`.

### P2-13 — Komunikat „(opencode update)" przy komendzie `upgrade --method npm`

`L_NPM_UPDATING_VIA_SELF_UPDATE` dostaje `command_name`, więc log mówi „opencode update", a wykonuje się `opencode upgrade --method npm`. Kosmetyka, ale to znów raport ≠ pomiar.

### P2-14 — Tryb LaunchAgent nie aktualizuje App Store

`install_launchagent.sh` ustawia `MAC_UPDATE_NONINTERACTIVE=1` + `--skip-system`. W tym trybie `update_appstore.sh` pomija TOR 2 (brak TTY) i nie prosi o `sudo` (TOR 1). Zaplanowany przebieg tygodniowy nigdy nie zaktualizuje App Store — jest to logiczne (brak TTY), ale nieopisane wprost w README przy sekcji „Weekly background run". LaunchAgent i tak nie jest zainstalowany (karta: decyzja otwarta).

### P2-15 — Bałagan w katalogu głównym i trzy instalatory

7 wrapperów `dev-sync-*.sh` (kompatybilność wsteczna, po 6 linii), `fix_mcp_all.sh`, `setup.sh` (858 linii), `migration_setup.sh` (1474), `install.sh` (134). `update_all.sh` ma 2046 linii, `lib/internet_app_updates.sh` 1954 — monolity, w których każda poprawka wymaga czytania całości.

### P2-16 — Higiena skarbca Agentic OS

Karta `project.macos-updates.md`: sekcja „State" datowana 2026-08-26 (v1.4.2), choć wyszły v1.4.3 i v1.4.4; „Decide the MAU channel" nadal otwarte, choć zamknięte 2026-09-02; `uses_skills: []` mimo używania `ultra-review`, `agentic-memory`, `verification-before-completion`. Handoff z 09-03 mówi „awaiting confirmation to push/merge" — merge nastąpił, ale handoff zamykający nie został dopisany.

---

## 4. Faza 4 — kontekst ekosystemu (2026)

- **npm 12 (2026): skrypty cyklu życia zależności są opt-in** (`allow-scripts`, `dangerously-allow-all-scripts`, `allow-scripts-pin`). Każdy pakiet z `postinstall` pobierającym binarkę platformy (opencode-ai, wiele CLI w Rust/Go dystrybuowanych przez npm) wymaga jawnej zgody. Toolkit, który sam podnosi npm do `@latest`, musi tę politykę **znać i egzekwować per pakiet** — inaczej odtworzy P0-2 przy kolejnym pakiecie.
- **Instalatory `curl | sh` dostawców różnią się interfejsem** i zmieniają go bez wersjonowania (Codex: `--release`, Claude: pozycyjny `[stable|latest|X.Y.Z]`, Agy: tylko `-h`). Standard branżowy: per-vendor adapter z jawnie zapisanym kontraktem argumentów i testem behawioralnym, nigdy wspólny sufiks.
- **Homebrew 6.x jako wyrocznia wersji**: `brew info --json=v2 --cask` jest darmowym, offline-cache'owanym źródłem „najnowsza znana wersja" dla ~90 % desktopowych aplikacji macOS. Projekt już używa go w guardzie casków; rozszerzenie na `silent_launch` to reuse, nie nowa zależność.
- **macOS 26.x**: `mas account` nadal nie działa (znany problem), `mas 7.0.0` — dwutorowość App Store pozostaje konieczna; jedyną drogą weryfikacji iPad apps pozostaje `mdls`/bundle.
- **„Measured, not claimed"** jako reguła SRE: wynik mutacji potwierdza się sondą na żywym systemie (tu: `--version` z kodem 0 + semver), nigdy kodem wyjścia helpera. Projekt ma tę zasadę w karcie („A mutation is only reported as done once the live system says so") — P0-2 pokazuje, że nie ma jej w kodzie kroku 2.
- **Prywatność publicznych repo**: gitleaks nie jest narzędziem do PII. Standard: dodatkowy skan `git ls-files` na e-maile, hostname'y, `/Users/<login>` — tanio, deterministycznie, w `run_tests.sh`.

---

## 5. Faza 5 — macierz punktowa (0–10)

| Wymiar | Ocena | Uzasadnienie |
|---|:--:|---|
| **Prawdomówność raportowania** | **4** | `✅ opencode-cli: ?` przy zepsutej binarce; 13 „⏳" w kroku `OK completed`; TOR 2 „niezweryfikowane" mimo dostępnych danych. Regres z 8 po v1.4.3. |
| Architektura i ograniczenia | 8 | Bash 3.2, `pipefail`, `lib/` czytelne, `lib/brew.sh` jako brama, 0 shellcheck. Minus za monolity 2 k linii. |
| Bezpieczeństwo i sekrety | 7 | Kod: bez zastrzeżeń. Repo: PII (e-maile, hostname, ścieżki) w tracked `docs/`. |
| Odporność strażników | 7 | Reguła 10 działa dla MAU; ale P0-2 to nowy strażnik bez TTL (stub bez `postinstall`), a P0-1 to instalator bez kontraktu. |
| Testowalność | 6 | 229 zielonych w 37 s, ale test rozszerzony pod regresję; dominują `assertIn` na źródle. |
| Obserwowalność | 7 | `counts` + `pending_*` + diag trójdzielny + detektor chroniczny — duży skok. Ślepy na zawieszenia, wynik poza JSON. |
| Pokrycie aktualizacji (zweryfikowane) | 6 | 95 % „obsługiwane", ale 13/32 pozycji internetowych bez dowodu; 2 aplikacje realnie w tyle (Antigravity, OpenCode Desktop). |
| Dokumentacja — aktualność | 5 | 5 różnych numerów wersji, 3 reguły sprzeczne z kodem, README non-EN/PL to skróty. Proces (CHANGELOG, handoffy, plany) — 9. |
| Automatyzacja / harmonogram | 6 | LaunchAgent nieinstalowany; tryb nienadzorowany nie robi App Store; CI macOS de facto wyłączone (brak tagów). |
| Gotowość DR | 8 | `dev_sync`, rotacja logów/backupów, `version_history.tsv`, snapshoty sesji. |
| Higiena danych (repo + skarbiec) | 6 | Czysty git, ale karta projektu 10 dni w tyle, `uses_skills` puste, 40 plików w `docs/reviews/` bez indeksu chronologicznego. |
| **Systemowa uczciwość** | **6** | Projekt *wie*, że to jego słaby punkt (dwa poprzednie review), ma regułę w karcie — i mimo to wysłał `✅ ?`. Brakuje mechanizmu, nie świadomości. |
| **Łącznie** | **6,3** | v1.4.3 oceniono na 8,2 „po". Dziś: naprawiono zawieszenie, cofnięto się w prawdomówności. |

---

## 6. Faza 6 — rekomendacje (w kolejności wykonania)

Pełny prompt wykonawczy z akceptacją: `docs/reviews/gemini_3.8_flash_high_v1.md`.

| # | Priorytet | Rekomendacja | Zamyka |
|---|---|---|---|
| **R1** | P0 | Per-vendor kontrakt argumentów instalatora (`native_installer_args()`): `latest` tylko dla Claude; test behawioralny z fałszywym `sh` na PATH; pomiar: codex 0.153.4, agy aktualne. | P0-1, P1-10 |
| **R2** | P0 | Jedna bramka „measured, not claimed" w kroku 2: po każdej mutacji `--version` musi wyjść 0 i dać semver; `?` = porażka. Reguła 9 w `AGENTS.md`. | P0-3 |
| **R3** | P0 | Naprawa OpenCode: wykrycie stubu → reinstalacja `npm i -g opencode-ai@latest --allow-scripts=opencode-ai` (lub równoważne w npm 12) i weryfikacja `--version`; `opencode upgrade --method npm` tylko przy zdrowej binarce i z `npm_config_allow_scripts` w env podprocesu; polityka `allow-scripts` per pakiet zapisana w manifeście. | P0-2 |
| **R4** | P1 | Jeden `npm` do instalowania i raportowania (ten z `NPM_GLOBAL_BIN`, jeśli istnieje), wersja obu w snapshotach. | P1-7 |
| **R5** | P1 | TOR 2 weryfikowany bundlami `appstore_gui` (przed/po + settle), trzy jawne stany zamiast „niezweryfikowane". | P1-4 |
| **R6** | P1 | Wyrocznia casków dla `silent_launch` (tylko odczyt, jedno `brew info --json=v2 --cask`), `counts.internet_verified/unverified/behind`, status „w tyle" widoczny w podsumowaniu. | P1-5 |
| **R7** | P1 | Provisional `run_summary` na starcie (`status: running`), detektor liczy przebiegi bez zakończenia; wynik detektora w JSON i w powiadomieniu; zapis JSON nie może być cicho połknięty. | P1-6 |
| **R8** | P1 | Skan PII tracked plików w `run_tests.sh` + oczyszczenie 6 plików `docs/`. | P1-8 |
| **R9** | P1 | `VERSION` jako jedyne źródło; test `test_docs_version_matches_VERSION`; poprawa `critical_rules §2`, numeracji, `troubleshooting`, tabeli env w README. | P1-9 |
| **R10** | P2 | Tag `v1.4.5` po merge (uruchomi macOS CI raz), zwijanie deprecacji tapów, komunikat `upgrade --method npm`, README o trybie LaunchAgent. | P2-11…14 |
| **R11** | P2 | Karta projektu + handoff + `agentic sync`; `uses_skills`. | P2-16 |
| **R12** | P2 (osobne wydanie) | Podział `update_all.sh` (kroki do `lib/steps/*.sh`) i `internet_app_updates.sh` (per-app pliki); usunięcie 7 wrapperów `dev-sync-*.sh` z katalogu głównego po jednym wydaniu deprecacji. | P2-15 |

---

## 7. Czego celowo nie zrobiłem

- **Nie naprawiałem OpenCode ręcznie** (`node postinstall.mjs`) ani nie uruchamiałem żadnego instalatora — review ma zostawić system w stanie, który Gemini zmierzy jako punkt wyjścia. Stan zastany: `opencode --version` → błąd, `codex 0.153.2`, `agy 1.1.26`.
- **Nie zmieniałem niczego w repozytorium** poza dodaniem tych dwóch plików w `docs/reviews/` (nietrackowane, zgodnie z konwencją katalogu). Nie dotykałem `.mac_update_prefs`, `~/.npmrc`, `~/.zshrc`.
- **Nie oceniałem `dev_sync/`** poza testami (`DevSyncPathSafetyTests` zielone) — to osobna domena z własnym review z 2026-08-19.
- **Nie rekomenduję migracji aplikacji `silent_launch` na caski.** Doktryna „najszybszy zaufany kanał" stoi; R6 używa casku jako wyroczni, nie instalatora.

---

## 8. Ślad dowodowy (komendy użyte w tym review)

```bash
git status --short; git branch -vv; git log --oneline -25; git tag --sort=-creatordate
bash run_tests.sh                                   # 229 OK, gitleaks clean
shellcheck -S warning update_*.sh lib/*.sh scripts/*.sh
agentic lint; agentic context -p macos-updates --brief; agentic recall "opencode" -p macos-updates
launchctl list | grep -iE "mac-update|macos"
sed 's/\x1b\[[0-9;]*m//g' logs/update_all_20260905_172339.log   # + 09-04, 09-03
cat logs/run_summary_20260905_172339.json
curl -fsSL https://chatgpt.com/codex/install.sh | grep -n "Unknown argument"     # + claude, agy, cursor
~/.local/share/mac-update/npm-global/bin/opencode --version
npm config list -l | grep allow-scripts; npm view opencode-ai version
gh api repos/openai/codex/releases/latest --jq .tag_name
brew info --json=v2 --cask chatgpt claude cursor warp docker-desktop antigravity comet proton-mail microsoft-teams gemini opencode-desktop
defaults read "/Applications/<App>.app/Contents/Info" CFBundleShortVersionString
git grep -nE "@gmail|@proton|/Users/|mac-r12" -- .
grep -rnoE "v\*?\*?1\.[0-9]\.[0-9]" CLAUDE.md AGENTS.md GEMINI.md README*.md CONTRIBUTING.md
for f in i18n/lang_*.sh; do grep -cE '^[A-Z_]+=' $f; done   # 604 ×7
```

*Wszystkie liczby pochodzą z pomiaru systemu docelowego 2026-09-05. Ten plik jest artefaktem deweloperskim (`docs/reviews/README.md`); gdy nie zgadza się z kodem, kod wygrywa.*
