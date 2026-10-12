# Prompt poprawkowy v2 — Gemini 3.8 Flash — macOS Updates v1.5.0 (`feat/vendor-truth-v1.5`)

Jesteś inżynierem wdrażającym poprawki po **weryfikacji linia po linii** Twojej implementacji T0–T15
(`docs/reviews/archive/gemini_3.8_flash_opus55_impl_prompt_v1.md`). Testy (419/419), ShellCheck i gitleaks były
zielone, ale weryfikacja wykazała regresje, których testy nie wykryły. Ten prompt naprawia **wyłącznie**
poniższe punkty. Nie refaktoryzuj niczego poza zakresem.

**Wszystkie ograniczenia z §0–§2 promptu v1 nadal obowiązują** (D1: harmonogram poza zakresem; Bash 3.2;
`set -o pipefail`, nigdy `set -e`; status przez `INTERNET_LAST_STATUS`; brak nowych standalone entrypointów
Pythona; 7 języków i18n; `softwareupdate -i <label> -R`; `sudo mas`; nie pushuj, nie merguj).

---

## 0. Wynik weryfikacji (kontekst — nie wykonuj tej sekcji)

| # | Prio | Obszar | Dowód (odtworzony na żywo lub w teście) |
|---|------|--------|------------------------------------------|
| 1 | **P0** | `update_brew.sh` ~l.357: parser guardu cask | `print(f"{v}\|{installed}\|{\";\".join(targets)}")` w `python3 -c '…'` → **SyntaxError na Pythonie 3.9 i 3.14**; `2>/dev/null \|\| true` ukrywa błąd. Brak `PYTHONPATH` przy `from brew_casks import`. **Skutek: ochrona przed downgrade casków i rozpoznawanie ścieżki .app nie działają (na `main` działały — regresja).** |
| 2 | **P0** | `update_brew.sh` ~l.215: `expected_app` dla sierot | `from brew_casks import` bez `PYTHONPATH` → zawsze fallback `<token>.app`. |
| 3 | **P0** | `lib/python/cli_retention.py::prune_cursor_agent` | Chroni `realpath` **pliku** (`…/versions/X/cursor-agent`), a kandydaci są **katalogami** → aktywna wersja nigdy nie jest chroniona; gdy aktywna nie jest najnowsza po mtime, zostaje **usunięta** (odtworzone w teście). Retencja o 1 za mała. |
| 4 | **P0** | `lib/python/inventory_sync.py::gather_facts` | `mas list --json` (mas 7.0.0, NDJSON) ma klucz **`adamID`**, kod czyta `id` → `facts["mas"] == {}` → strażnik pomija GRUPĘ 2. Na żywo: `GarageBand` dalej odłączony, `Notion Web Clipper` (niezainstalowany) został, w legendzie **zniknął wiersz App Store**. T11 w raporcie oznaczone DONE mimo że diff nie spełnił oczekiwań z T11.6. |
| 5 | P1 | iPad: nazwa z `iTunesMetadata.itemName` zamiast nazwy `.app` | Na żywo: `IPMIView` został w GRUPIE 3, `TrackMan.Go.Ios` w 🆕, w sekcji iPad „Supermicro IPMIView”, „TrackMan Golf Pro” → podwójne liczenie. To samo w T12 (`appstore_ios_*.txt` vs `installed_apps_*.txt`). |
| 6 | P1 | `lib/vendor_direct.sh` | `[ -n "${internet_diag_log:-}" ] && internet_diag_log …` testuje **zmienną**, a to funkcja → diagnostyka martwa (9 miejsc). DMG kopiowany `cp -R` (niszczy podpis/xattr; reguła §6: `ditto`). Brak sprawdzenia wersji pobranego bundla przed `copy_verified_app` (ryzyko downgrade przy błędnym URL). `fetch_to_file` przepuszcza przekierowania na `http://`. |
| 7 | P1 | `update_appstore.sh` ~l.608 | `still_pending="$(ios_apps_pending … \|\| true)"` — porażka lookupu (rc 2) = pusty wynik = **„zweryfikowano”**. |
| 8 | P1 | `update_npm_cli.sh` ~l.1060 | Brak zarządzanego Node (`ensure_latest_node` rc 2) pomija `install_latest_npm_packages`, który obsługuje też **natywne** CLI (`claude`, `codex`, `agy`, `cursor-agent`) → nie są aktualizowane. |
| 9 | P1 | `update_internet_apps.sh` ~l.606 (Stale Days) | Nie pominięto kodów zweryfikowanych (T4.3) → „Aktualne (producent)” nadpisywane ostrzeżeniem o „starej” wersji. |
| 10 | P1 | Docker (`lib/internet_app_updates.sh` ~l.2086) | `docker desktop stop` natychmiast po `update -q`, **przed** pollingiem wersji → może przerwać instalację. |
| 11 | P1 | `lib/python/run_summary.py` (T12) | iPad zaktualizowany przez Track 2 raportowany jako `background`; duplikaty iPad (nazwa `.app` vs `itemName`) i casków o innej nazwie `.app` (np. `zoom` → `zoom.us`). |
| 12 | P2 | Omaha Google | Pętla kończy na **pierwszym** `"updatecheck"` dowolnej aplikacji (wyścig Chrome/Drive/Gemini); `--wake-all` odpalany 3× w jednym przebiegu. |
| 13 | P2 | Inwentarz — kosmetyka | Linia `> **System:** macOS 26.5F71)` (uszkodzona dawno) nigdy nie jest naprawiana (regex wymaga `(Build …)`); znika separator `---` przed `## Podsumowanie`; legenda nie filtruje niezainstalowanych, brak wiersza iPad; `skipped_groups` nigdy nie jest wypisywane. |
| 14 | P2 | UI / i18n / dokumentacja | `L_INTERNET_LAUNCH_CYCLE_FMT` dostaje `$WAIT` zamiast wersji `R`; nowe napisy po angielsku na sztywno; `scripts.md` ma `STAGE_WAIT=4` (kod 90) i `APPSTORE_VERIFY_TIMEOUT=90` (kod 300); `scripts.md`/7×README wciąż opisują `softwareupdate -ia -R` i `--greedy`; raport pokrycia pokazuje „uruchomiony updater (bez weryfikacji)” dla aplikacji zweryfikowanych feedem. |
| 15 | P3 | `lib/vendor_feeds.sh::vendor_feed_row` | Dopasowanie ERE z niepełnym escapowaniem (`( ) + ? { \|`). |
| 16 | Proces | `run_tests.sh` | `PYTHONPATH=dev_sync:lib/python` eksportowany globalnie → dziedziczą go podprocesy `bash` w testach i **maskują** brak `PYTHONPATH` w kodzie produkcyjnym. Krok kompilacji obejmuje heredoki, ale **nie** bloki `python3 -c '…'` (stąd #1). |

Zweryfikowane jako **poprawne** (nie ruszaj): T1 (moduł feedów, `version_cmp`), T2, T3 (cask jako drugi głos),
T4.2 algorytm poza #6/#9/#14, T5 poza #12, T7 bramka iPad poza #7, T8 kody i sumaryczne liczniki, T9 helpery
`lib/brew.sh` (w tym heurystyka sudo: Homebrew przy upgrade faktycznie wywołuje `sudo launchctl` — **zostaw**),
T13, `scripts/check_vendor_feeds.sh` (działa na żywo), `config/vendor_feeds.txt` identyczny z Dodatkiem A.

---

## 1. Metoda pracy (obowiązkowa dla każdego F)

1. **Najpierw test, który pada.** Napisz test z sekcji F, uruchom go na obecnym HEAD i **wklej linię porażki do
   raportu** (`FAIL: …` / `AssertionError: …`). Test, który od razu przechodzi, nie dowodzi niczego — popraw test.
2. Potem poprawka, potem `bash run_tests.sh` (całość) + ShellCheck jak w T15.
3. Jeden commit na F: `fix(v1.5.0): <opis> (F<n>)`. Nie łącz F w jeden commit.
4. Wersja zostaje `1.5.0`. W `CHANGELOG.md` pod `1.5.0` dodaj podsekcję `### Fixed (post-review)` z listą F.
5. Na żywo wolno uruchomić tylko komendy tylko-do-odczytu oraz `bash build_inventory.sh` w F3 (z kopią).
   Żadnych `brew upgrade`, `mas upgrade`, `softwareupdate -i`, `sudo`, `docker desktop update`, uruchamiania
   ani zamykania aplikacji.

---

## F0 — Testy przestają maskować błędy (zrób PIERWSZE)

**Pliki:** `run_tests.sh`, `tests/_env.py` (nowy helper, nie test), testy uruchamiające `bash`,
`tests/test_safety_static.py`.

1. `run_tests.sh` krok 3/4: nie eksportuj `PYTHONPATH` do środowiska. Ustaw ścieżki **w procesie** testów:
   ```bash
   if python3 -c 'import sys, unittest
   sys.path[:0] = ["dev_sync", "lib/python"]
   prog = unittest.main(module=None, argv=["unittest", "discover", "-s", "tests"], exit=False)
   sys.exit(0 if prog.result.wasSuccessful() else 1)' 2>&1; then
   ```
   (Zachowaj teksty `ok`/`err`. Sprawdź, że liczba testów jest taka sama jak przed zmianą.)
2. `tests/_env.py`: `def shell_env(**extra) -> dict` — kopia `os.environ` **bez** `PYTHONPATH`, plus `extra`.
   Każdy test, który uruchamia `bash` (skrypt `*.sh` lub funkcję z `lib/*.sh`), używa `env=shell_env(...)`.
   Usuń wszystkie `env["PYTHONPATH"] = …` przekazywane do podprocesów `bash` (np.
   `tests/test_vendor_truth_handlers.py:31`). Kod produkcyjny ma sam ustawiać ścieżkę — test ma to sprawdzać.
   Wyjątek: test, który **bezpośrednio** uruchamia `python3 -c "import <moduł>"` jako symulację wywołującego,
   może ustawić `PYTHONPATH` — dodaj wtedy komentarz `# explicit: simulates caller`.
3. `run_tests.sh` krok 2/4: oprócz heredoków kompiluj też bloki `python3 [-flagi] -c '<kod>'` w apostrofach:
   regex `python3\s+(?:-\S+\s+)*-c\s+'([^']*)'` (DOTALL) na tych samych plikach `*.sh`; każdy wynik przez
   `compile(code, path, "exec")`; błąd → `❌ inline python -c syntax error in <plik>:<linia>` i porażka kroku.
   **Na obecnym HEAD musi to zgłosić dokładnie `update_brew.sh:357`.**
4. Nowy test statyczny `test_shell_python_project_imports_set_path` (`tests/test_safety_static.py`):
   - moduły projektu = nazwy plików `lib/python/*.py` i `dev_sync/*.py`;
   - dla każdej linii `*.sh` (bez `.git/`, `graphify-out/`) pasującej do `^\s*(from|import)\s+(<moduły>)\b`
     znajdź **otwarcie** bloku Pythona: najbliższą wcześniejszą linię zawierającą `python3` albo heredoc
     `<<-?\s*['"]?[A-Z_]+['"]?`;
   - test przechodzi dla tego importu, jeśli linia otwarcia zawiera `PYTHONPATH=` **albo** między otwarciem a
     importem jest `sys.path.insert`, `sys.path[:0]` lub `sys.path.append`;
   - komunikat porażki wymienia `plik:linia`.
   **Na obecnym HEAD musi zgłosić dokładnie `update_brew.sh:219` i `update_brew.sh:364`.** Jeśli zgłosi coś
   jeszcze — sprawdź ręcznie: prawdziwy błąd napraw w F1, fałszywy alarm → popraw skaner (nigdy allowlista).

---

## F1 — (P0) `update_brew.sh`: guard przed downgrade i cele `.app`

**Pliki:** `lib/python/brew_casks.py`, `lib/brew.sh`, `update_brew.sh`, `tests/test_brew_casks.py`.

1. `brew_casks.py` — dwie czyste funkcje:
   ```python
   def cask_guard_facts(text: str) -> str:
       """'version|installed|A.app;B.app' from `brew info --json=v2 --cask <t>`; '' on any parse error."""
       try:
           cask = json.loads(text)["casks"][0]
       except (ValueError, KeyError, IndexError, TypeError):
           return ""
       version = str(cask.get("version") or "")
       installed = str(cask.get("installed") or "")
       return "|".join((version, installed, ";".join(app_targets(cask))))

   def cask_primary_app(text: str) -> str:
       """First app target name ('X.app') or ''."""
       try:
           targets = app_targets(json.loads(text)["casks"][0])
       except (ValueError, KeyError, IndexError, TypeError):
           return ""
       return targets[0] if targets else ""
   ```
2. `lib/brew.sh` — wrappery (ten sam wzorzec co `brew_orphan_casks`):
   ```bash
   # brew_cask_guard_facts — stdin: `brew info --json=v2 --cask <token>`; stdout: version|installed|targets
   brew_cask_guard_facts() {
       PYTHONPATH="$_BREW_SH_DIR/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
   import sys
   from brew_casks import cask_guard_facts
   print(cask_guard_facts(sys.stdin.read()))
   ' 2>/dev/null
   }
   brew_cask_primary_app() {   # same stdin; stdout: X.app or empty
       PYTHONPATH="$_BREW_SH_DIR/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
   import sys
   from brew_casks import cask_primary_app
   print(cask_primary_app(sys.stdin.read()))
   ' 2>/dev/null
   }
   ```
3. `update_brew.sh`: zastąp oba bloki `python3 -c '…'` wywołaniami:
   `expected_app="$(brew info --json=v2 --cask "$orph" 2>/dev/null | brew_cask_primary_app || true)"` oraz
   `parsed="$(printf '%s' "$cask_json" | brew_cask_guard_facts || true)"`. Reszta logiki bez zmian.
4. W pętli guardu, dla każdego casku przekazanego do `brew upgrade --cask`, dopisz do
   `$MAC_UPDATE_SESSION_DIR/brew_cask_targets.txt` wiersze `token|Nazwa.app` (z `targets_str`; potrzebne w F10).
5. **Testy:** `test_cask_guard_facts_parses_and_joins_targets`, `test_cask_guard_facts_bad_json_is_empty`,
   `test_cask_primary_app` (czysty Python) oraz `test_update_brew_downgrade_guard_blocks_upgrade` — stub `brew`
   w PATH (loguje argumenty; `info --json=v2 --cask foo` zwraca `version "1.0"`, `installed "2.0"`), środowisko
   z `shell_env()` (bez `PYTHONPATH`!): w wyjściu komunikat `L_BREW_CASK_WOULD_DOWNGRADE_FMT`, w logu stuba
   **brak** `upgrade --cask foo`. Drugi przypadek (`installed` < `version`) → `upgrade --cask foo` jest w logu.

---

## F2 — (P0) Retencja wersji CLI chroni **katalog** aktywnej wersji

**Plik:** `lib/python/cli_retention.py`, `tests/test_cli_installers.py`.

Dlaczego obecne testy przechodzą: `test_prune_never_deletes_symlink_target` linkuje do **katalogu** wersji
(`agent -> versions/X`), a na prawdziwym Macu link wskazuje **plik** w środku
(`~/.local/bin/agent -> ~/.local/share/cursor-agent/versions/X/cursor-agent`). Fikstura nie odpowiada
rzeczywistości. Zostaw obecne testy (ścieżka katalogowa też musi działać) i dodaj realistyczne.

1. Dodaj helper i użyj go w `prune_codex` (`current`) oraz `prune_cursor_agent` (`~/.local/bin/cursor-agent`,
   `~/.local/bin/agent`):
   ```python
   def _protected_version_dirs(root_real: str, link_paths: List[str]) -> Optional[Set[str]]:
       """Top-level version dirs under root that any link resolves into.
       Returns None when a link exists but resolves outside root (caller must then prune nothing)."""
       protected: Set[str] = set()
       for p in link_paths:
           if not (os.path.exists(p) or os.path.islink(p)):
               continue
           target = os.path.realpath(p)
           if not target.startswith(root_real + os.sep):
               return None
           first = os.path.relpath(target, root_real).split(os.sep, 1)[0]
           protected.add(os.path.join(root_real, first))
       return protected
   ```
   `None` → `return 0, 0` (fail-safe: nie wiemy, co jest aktywne). Kandydaci porównywani po `realpath` katalogu.
   Retencja bez zmian semantycznie: chronione + 1 najnowszy niechroniony (po mtime).
2. **Testy** (tmp HOME, linki do **plików** jak na prawdziwym Macu): (a) wersje A (najstarsza, aktywna: `agent -> versions/A/cursor-agent` i `cursor-agent -> versions/A/cursor-agent`), B, C (najnowsza)
   ⇒ zostają A i C, B usunięta; (b) aktywna = C ⇒ zostają C i B, A usunięta; (c) link poza root ⇒ nic nie
   usunięte; (d) codex: `current -> releases/X` oraz `current -> releases/X/bin/codex` — X zawsze zostaje.
   Test (a) **musi paść** na obecnym HEAD.

---

## F3 — (P0) Inwentarz: GRUPA 2, iPad, nagłówek, legenda, separator

**Pliki:** `lib/python/inventory_sync.py`, `update_all.sh` (prescan + postupdate), `tests/test_inventory_sync.py`,
`tests/fixtures/inventory/` (nowa fikstura `mas7_list.ndjson`), i18n ×7.

1. **mas 7:** w `gather_facts` czytaj `aid = str(obj.get("adamID") or obj.get("id") or "")` (NDJSON i tablica).
   Jeśli `returncode == 0`, stdout niepusty, a nie sparsowano **żadnego** wiersza → wykonaj fallback tekstowy
   `mas list`. Jeśli oba źródła zawiodą → `facts["mas"] = None` (nie `{}`). `{}` tylko gdy komenda się udała i
   naprawdę nie ma aplikacji. Fikstura `mas7_list.ndjson`: 3 linie z kluczami `adamID`, `name`, `version`,
   `bundleID`, `path` (dane syntetyczne, bez danych osobowych). Test `test_gather_facts_parses_mas7_ndjson`
   (wstrzyknięty `run`), `test_gather_facts_mas_unparseable_falls_back_to_text`.
2. **Tożsamość iPad = nazwa `.app`.** `facts["ipad"]` to lista `(app_name, item_id, version, item_name)`, gdzie
   `app_name` = nazwa katalogu bez `.app`, `item_name` = `itemName` (może być pusty). `sync_ipad_section` pokazuje
   `app_name` (akceptuje krotki 3- i 4-elementowe). W `sync_all` do usunięcia z GRUPY 3 i 🆕 dodaj **oba**:
   `app_name` i `item_name`. W prescan `SKIP_DISCOVERY_APPS` dostaje `app_name`. Zaktualizuj istniejące testy
   i dodaj `test_ipad_rows_use_bundle_name_and_remove_both_names` (GRUPA 3 ma `IPMIView`, 🆕 ma
   `TrackMan.Go.Ios`, facts mają `("TrackMan.Go.Ios", "1192720039", "4.6.1", "TrackMan Golf Pro")` itd.).
3. **Nagłówek:** nowa funkcja `refresh_system_line(md, os_label, build) -> str` zastępuje **całą** linię
   `^> \*\*System:\*\* .*$` (pierwsze wystąpienie) tekstem `> **System:** {os_label} (Build {build})`.
   W postupdate (`update_all.sh` ok. l.1692) zastąp obecny `re.sub` z `(Build [A-Z0-9]+\)` wywołaniem tej
   funkcji. Test: wejście `> **System:** macOS 26.5F71)` → `> **System:** macOS 27.0 Golden Gate (Build 27A5000)`.
4. **Separator:** po `sync_all` linia `---` bezpośrednio przed `## Podsumowanie` ma zostać (jeśli była).
   Popraw `rebuild_cli_section` / `recompute_summary`. Test `test_separator_before_summary_preserved` + istniejący
   test idempotencji ma dalej przechodzić.
5. **Legenda** (`legend_rows`): wiersze Auto i MAU tylko dla aplikacji zainstalowanych — dopasowanie
   `norm_name` nazwy z rejestru **lub** dowolnego aliasu z `APP_ALIASES` do `norm_name(installed_names)`;
   pusty `installed_names` = nie filtruj. Kolejność: Auto, MAU, `🛍️ App Store / \`sudo mas upgrade\``
   (nazwy mas, posortowane), **nowy** `📱 App Store — iPad (Track 2 GUI / ręcznie)` (nazwy `.app`, posortowane),
   CLI, Homebrew. Test `test_legend_filters_uninstalled_and_has_ipad_row`.
6. **Pominięte grupy są widoczne:** prescan i postupdate wypisują ostrzeżenie dla każdej pozycji
   `report["skipped_groups"]`: nowy klucz `L_PRESCAN_GROUP_SYNC_SKIPPED_FMT`
   (EN `Inventory group %s was not synchronized: its data source returned nothing (kept unchanged)`,
   PL `Grupa inwentarza %s nie została zsynchronizowana: źródło danych nic nie zwróciło (bez zmian)`),
   pozostałe 5 języków przetłumacz.
7. **Weryfikacja na żywo (obowiązkowa, z kopią):**
   ```bash
   mkdir -p scratch/backup_F3 && cp -p APPLICATIONS.md scratch/backup_F3/
   bash build_inventory.sh
   diff -u scratch/backup_F3/APPLICATIONS.md APPLICATIONS.md > scratch/F3_inventory.diff
   ```
   Oczekiwane na tym Macu: `GarageBand` **w** tabeli GRUPY 2 (brak odłączonego wiersza), `Notion Web Clipper`
   usunięty (sprawdź wcześniej `mas list`, że go nie ma); sekcja iPad z `IPMIView`, `Picsart`, `S2M`,
   `TrackMan.Go.Ios`, `UniFi`, `WiFiman`; `IPMIView` zniknął z GRUPY 3, `TrackMan.Go.Ios` z 🆕; linia
   `System:` poprawna; w legendzie są wiersze App Store i iPad; `---` przed `## Podsumowanie`; brak ostrzeżeń
   `skipped`. **Jeśli diff zawiera cokolwiek innego lub brakuje któregoś punktu — przywróć kopię
   (`cp -p scratch/backup_F3/APPLICATIONS.md .`), napraw, powtórz.** Do raportu wklej diff (nazwy aplikacji
   są OK; usuń nazwę użytkownika i ścieżkę domową, jeśli się pojawią).

---

## F4 — (P1) `vendor_direct`: diagnostyka, `ditto`, wersja przed kopią, HTTPS przy przekierowaniach

**Pliki:** `lib/vendor_direct.sh`, `lib/fetch.sh`, `lib/internet_handlers.sh`, `tests/test_vendor_truth_handlers.py`.

1. Dodaj `_vd_diag() { command -v internet_diag_log >/dev/null 2>&1 && internet_diag_log "$@"; return 0; }`
   i zastąp **wszystkie** `[ -n "${internet_diag_log:-}" ] && internet_diag_log … 2>/dev/null || true`
   wywołaniem `_vd_diag "…"`. Test statyczny: w `lib/*.sh` nie występuje `${internet_diag_log`.
2. DMG: zamiast `find … -exec cp -R {} …` iteruj po wynikach `find "$mnt" -maxdepth 3 -type d -name '*.app' -prune`
   i kopiuj `ditto "$app" "$extract_dir/$(basename "$app")"`; porażka `ditto` → `_vd_diag`, detach, return 1.
3. Nowy 7. argument `vendor_direct_install … "<expected_version>"`. Po wyborze jedynego bundla (krok 8):
   `cand_ver="$(app_version "$found")"`; wymagane `version_cmp "$expected_version" "$cand_ver"` ∈ {`equal`,
   `older`} **oraz** `version_cmp "$cand_ver" "$(app_version "$installed_app_path")"` = `newer`; inaczej
   `_vd_diag "ERROR: downloaded bundle version …"`, sprzątanie, return 1 (przed kopią ⇒ DOWNLOAD_ERROR, soft).
   Handler przekazuje `"$R"`.
4. `lib/fetch.sh::fetch_to_file`: dodaj `--proto =https --proto-redir =https --max-filesize "$max_bytes"` do
   `curl` (reszta kontraktu bez zmian; pozostałe sprawdzenia rozmiaru zostają).
5. `internet_handler_vendor_truth`: `printf "$L_INTERNET_LAUNCH_CYCLE_FMT\n" "$app" "$R"` (było `$WAIT`).
6. **Testy:** `test_vendor_direct_rejects_older_bundle_version` (zip z bundlem 1.0, installed 1.5, R 2.0 ⇒ rc 1,
   `copy_verified_app` stub nie wywołany), `test_vendor_direct_diag_is_logged` (stub `internet_diag_log`
   zapisuje do pliku; host odrzucony ⇒ wpis jest), `test_fetch_refuses_http_redirect` (stub `curl` loguje argumenty:
   są `--proto-redir =https`), `test_launch_cycle_message_shows_remote_version`.

---

## F5 — (P1) App Store: porażka lookupu ≠ weryfikacja

**Plik:** `update_appstore.sh` (pętla ok. l.605), i18n ×7, test w `tests/test_appstore_ios.py`.

```bash
        _verify_rc=0
        while [ "$elapsed" -lt "$verify_timeout" ]; do
            sleep 15
            elapsed=$((elapsed + 15))
            _verify_rc=0
            still_pending="$(ios_apps_pending 2>/dev/null)" || _verify_rc=$?
            if [ "$_verify_rc" -eq 0 ] && [ -z "$still_pending" ]; then
                all_verified=1
                break
            fi
        done
```
Po pętli: `all_verified=0` i `_verify_rc -eq 2` ⇒ `print_warn "$L_APPSTORE_IOS_VERIFY_LOOKUP_FAILED"`
(EN `Could not confirm iPad app updates: the App Store lookup failed`, PL `Nie można potwierdzić aktualizacji
aplikacji iPad: zapytanie do App Store się nie powiodło`), `SOFT_FAIL=1`, bez nadpisywania
`appstore_ios_pending.txt` pustą treścią. Test: stub `curl` zwraca rc 22 ⇒ brak `L_APPSTORE_IOS_VERIFIED`,
jest nowy komunikat, exit 10 (użyj `MAC_UPDATE_APPSTORE_VERIFY_TIMEOUT=15` i stubu `sleep`).

---

## F6 — (P1) Natywne CLI aktualizują się także bez zarządzanego Node

**Plik:** `update_npm_cli.sh`, test w `tests/test_cli_installers.py`.

Podziel `install_latest_npm_packages` na dwie funkcje o tej samej pętli po manifeście:
`install_latest_npm_packages` (tylko `method=npm` i `self-update` — wymagają npm) oraz
`update_native_clis` (tylko `native-installer`). Wywołanie:
```bash
if [ "$NODE_READY" -eq 1 ]; then
    install_latest_npm_packages || SOFT_FAIL=1
fi
update_native_clis || SOFT_FAIL=1
```
Reguła „tylko zainstalowane” (D2, `--bootstrap-cli`) bez zmian. Test: brak `$N_PREFIX/bin/node`, stub `claude`
w `~/.local/bin` ⇒ natywna ścieżka aktualizacji `claude` została wywołana (log stuba), `npm` nie.

---

## F7 — (P1) „Stale Days” nie nadpisuje statusów zweryfikowanych

**Plik:** `update_internet_apps.sh` (blok `STALE_LIMIT`), test.

W pętli, przed nadpisaniem: odczytaj obecną wartość zmiennej (`eval "_s_cur=\"\${$_s_var}\""`), policz
`_s_code="$(internet_status_code "$_s_cur")"` i **pomiń** aplikację, gdy kod ∈ `current_verified`,
`current_vendor`, `updated`, `behind`, `needs_restart`, `feed_stale`, `update_available`, `rollout_hold`.
Ostrzeżenie o „starej” wersji zostaje tylko dla statusów niezweryfikowanych. Test: `STATUS_CURSOR` =
`VENDOR_CURRENT_FMT`, `internet_get_app_days_unchanged` zwraca 99 ⇒ status bez zmian.

---

## F8 — (P1) Docker: najpierw czekaj na nową wersję, dopiero potem zatrzymuj

**Plik:** `lib/internet_app_updates.sh` (`iu_docker*`), i18n ×7, `tests/test_docker_update.py`.

Kolejność: `docker desktop update -q` → pętla pollingu wersji (jak teraz, do 300 s) → **po** pętli, jeśli
`was_running -eq 0`, `docker desktop stop`. Napisy `Starting Docker Desktop...`, `Updating Docker Desktop...`,
`Could not start Docker Desktop to apply update` → klucze `L_INTERNET_DOCKER_STARTING`,
`L_INTERNET_DOCKER_UPDATING`, `L_INTERNET_DOCKER_START_FAILED` (EN jak obecne teksty; PL: „Uruchamiam Docker
Desktop…”, „Aktualizuję Docker Desktop…”, „Nie udało się uruchomić Docker Desktop, aby zastosować
aktualizację”). Test: log stuba `docker` ma `desktop stop` **po** ostatnim odczycie wersji (stub `defaults`/
`app_version` zmienia wersję przy 2. odczycie).

---

## F9 — (P2) Omaha: status konkretnej aplikacji i jedno wybudzenie na przebieg

**Pliki:** `lib/internet_app_updates.sh` (`google_keystone_check`, `iu_google_chrome`, `iu_gemini`,
`iu_google_drive`), test w `tests/test_chromium_updaters.py`.

1. `google_keystone_check "<agent>" "<appid>"`: pętla kończy się, gdy `omaha_last_status` (moduł
   `vendor_feeds`, z `PYTHONPATH` jak w `evaluate_omaha_status`) zwraca niepusty status **dla tego appid** w
   dotychczasowym przyroście logów — nie na pierwszym dowolnym `"updatecheck"`.
2. Jedno wybudzenie na przebieg: pierwsze wywołanie zapisuje początkowe rozmiary logów w
   `$MAC_UPDATE_SESSION_DIR/google_omaha_init.txt` i wykonuje `--runMode ondemand`/`--wake-all`; kolejne
   wywołania w tym samym przebiegu (plik istnieje) **nie** wybudzają ponownie, tylko czytają przyrost od tych
   samych offsetów i czekają na swój appid. Bez `MAC_UPDATE_SESSION_DIR` zachowanie jak dotąd.
3. Napisy `Google Keystone failed to check for … updates` → `L_INTERNET_KEYSTONE_CHECK_FAILED_FMT`
   (EN `Google updater could not check %s for updates`, PL `Updater Google nie sprawdził aktualizacji %s`).
4. Testy: log zawiera najpierw `updatecheck` dla `com.google.drivefs`, potem dla `com.google.chrome` ⇒ Chrome
   dostaje swój status; trzy aplikacje w jednym przebiegu ⇒ stub updatera wywołany **raz**.

---

## F10 — (P1) Podsumowanie przebiegu: poprawna kategoria i brak duplikatów

**Pliki:** `update_appstore.sh` (zapisy `appstore_ios_before/after.txt`), `lib/python/run_summary.py`,
`tests/test_run_summary.py`.

1. Snapshoty iPad zapisuj jako `<nazwa .app>|<wersja>` — nazwa z czwartego pola `path`:
   `n="$(basename "$path" .app)"`. (`ios_apps_scan` bez zmian — pole 1 `itemName` zostaje dla komunikatów GUI.)
2. `run_summary.collect_run_items`: zmiany z `appstore_ios_before/after.txt` to kategoria **`appstore`**,
   `details: "App Store (iPad) — Track 2"` (te pliki obejmują tylko krok 1). Przetwarzaj je **przed** sekcją
   6b. Sekcja 6b (`installed_apps_scan` vs `installed_apps_after`, `background`) pomija klucze już widziane.
3. Jeśli istnieje `brew_cask_targets.txt` (F1.4), po dodaniu itemu cask oznacz jako widziane także nazwy
   `.app` z tego pliku (bez `.app`), np. `zoom` → `zoom.us`.
4. Testy: `test_ipad_update_during_track2_is_appstore_not_background` (bez duplikatu z 6b),
   `test_cask_with_different_app_name_not_duplicated_as_background` (`zoom|5.0→5.1` w caskach,
   `zoom.us|5.0→5.1` w installed_apps ⇒ jeden item `brew_cask`). Istniejący
   `test_between_step_changes_are_attributed` ma dalej przechodzić (dostosuj tylko część iPad do nowej reguły).

---

## F11 — (P2) Tekst, i18n, dokumentacja

1. `update_system.sh`: `Installing (restart required): …` i `Failed to install batch: …` → klucze
   `L_SYSTEM_INSTALLING_RESTART_BATCH_FMT`, `L_SYSTEM_RESTART_BATCH_FAILED_FMT`; `update_appstore.sh`
   `No iPad apps installed — skipping Track 2` → `L_APPSTORE_IOS_NONE_INSTALLED`. EN = obecny tekst,
   PL przetłumacz, pozostałe 5 języków też. Test parzystości kluczy ma przejść.
2. `scripts/report_update_coverage.sh`: gdy `classify` zwraca `managed_by == "vendor_feed"`, etykieta ma pochodzić
   z `METHOD_LABELS[lang]["vendor_feed"]`, a nie z metody rejestru (`silent_launch`). Test na wyjściu `--json`
   lub funkcji etykiety: `Claude` ⇒ „vendor feed verified”. Aplikacje z `config/inventory_exclusions.txt`
   raportuj jako wykluczone (nowa kategoria `excluded`, nie „Nieznane”) — z liczbą w podsumowaniu.
3. `docs/agents/scripts.md`: `MAC_UPDATE_STAGE_WAIT` domyślnie `90` (0–600, cykl uruchomienia updatera
   producenta), `MAC_UPDATE_APPSTORE_VERIFY_TIMEOUT` domyślnie `300` (0–1800); wiersz `update_system.sh` →
   „per-label `softwareupdate -i <label> -R`, restart-required labels in one final batch”; krok 3 →
   „formulae + casks (greedy only for `brew_cask`-designated tokens) + orphan skip + cleanup + doctor”.
4. 7×README: wiersz kroku 6 (`softwareupdate -ia -R`) → opis per-label + wsadowy restart (w każdym języku).
   `docs/agents/critical_rules.md` §5 tabela: wiersz „Homebrew cask --greedy-auto-updates” → greedy tylko dla
   tokenów oznaczonych `brew_cask`. **Nie** edytuj `docs/agents/audit_2026-04-26.md` (dokument historyczny).
5. Test statyczny: `docs/agents/scripts.md` zawiera domyślne wartości zgodne z kodem — parsuj
   `${MAC_UPDATE_STAGE_WAIT:-N}` i `${MAC_UPDATE_APPSTORE_VERIFY_TIMEOUT:-N}` z kodu i porównaj z tabelą.

---

## F12 — (P3) `vendor_feed_row`: dokładne dopasowanie pola

**Plik:** `lib/vendor_feeds.sh`. Zastąp `sed`+`grep -E` porównaniem pola w `awk`:
```bash
row=$(awk -F'|' -v a="$app" '
    /^[[:space:]]*#/ { next }
    { n = $1; gsub(/^[[:space:]]+|[[:space:]]+$/, "", n); if (n == a) { print; exit } }
' "$cfg" 2>/dev/null)
```
Test: nazwa z `+` i `(`, np. `Foo+ (Beta)` w tymczasowej konfiguracji (ustaw ścieżkę przez nadpisanie
`vendor_feed_config_path` w teście) ⇒ znaleziona; `Foo` ⇒ nieznaleziona.

---

## F13 — Weryfikacja końcowa i raport

```bash
bash run_tests.sh                                   # ALL CHECKS PASSED + liczba testów
find . -type f -name '*.sh' ! -path './.git/*' ! -path './graphify-out/*' ! -path './dev_sync_logs/*' -print0 | xargs -0 shellcheck --severity=warning
env -u PYTHONPATH bash -c 'source lib/brew.sh; brew info --json=v2 --cask "$(brew list --cask | head -1)" | brew_cask_guard_facts'   # niepusty wynik
bash scripts/check_vendor_feeds.sh
bash scripts/report_update_coverage.sh | head -40
git log --oneline main..HEAD
git diff --stat main..HEAD | tail -5
```

Raport: **`docs/reviews/archive/FIX_REPORT_opus55_v2.md`** — tabela `F | Status (DONE/PARTIAL) | Commit | Test, który
najpierw padł (nazwa + linia porażki) | Testy po`, potem wyniki powyższych komend (skrócone), diff F3,
odchylenia od promptu z uzasadnieniem, rzeczy niezweryfikowane na żywo. **F3 nie może być DONE, jeśli diff
z F3.7 nie spełnia wszystkich oczekiwań.** Nie deklaruj sukcesu bez wyników.

Na koniec w czacie trzy linie: gałąź, liczba nowych commitów, liczba testów przed i po. Dopisz:
„Raport: docs/reviews/archive/FIX_REPORT_opus55_v2.md”. Nie pushuj i nie merguj.
