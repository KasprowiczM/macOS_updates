# Prompt v8 — Gemini 3.8 Flash — zielone CI na GitHub (testy hermetyczne)

Stan: v1.5.1 jest na `main` (`16a3897`, tag `v1.5.1`). Lokalnie 480/480, ale **CI na GitHub jest czerwone**:

| Run | Job | Wynik |
|---|---|---|
| `main` push (ubuntu-latest) | `portable Python compile + unittest` | ❌ — czerwone już od `0a613d0` (v1.4.6) |
| tag `v1.5.1` (macos-latest) | `bash -n + py_compile + unittest` | ❌ 5 failures + 1 error (tag `v1.4.6` był zielony) |

Przyczyna: testy zależą od **Maca właściciela** (zawartość `/Applications`, zainstalowane narzędzia, prawdziwe
`osascript`/`date`), a nie od fikstur. Zasady v1–v7 obowiązują. Gałąź `fix/ci-hermetic-tests` od `main`.
**Nie zmieniaj logiki produkcyjnej**, chyba że test ujawni prawdziwy błąd (wtedy opisz go w raporcie).
Nie dodawaj nowych workflowów ani runnerów; nie zmieniaj triggerów w `.github/workflows/ci.yml` (budżet
Actions — `AGENTS.md`).

## M1 — ubuntu (`portable Python compile + unittest`)

Błędy z logu run `36111959541`:
- `FileNotFoundError: 'plutil'` — `test_run_log_regressions_20260902.TeamsDeferralVersionTests` (6 testów);
- `FileNotFoundError: 'ditto'` — `test_vendor_truth_handlers.test_vendor_direct_rejects_older_bundle_version`;
- `test_appstore_ios.test_track2_verify_lookup_failure_is_soft_fail` — `1 != 10`.

Testy wymagające narzędzi macOS oznacz `@unittest.skipUnless(shutil.which("plutil"), …)` (odpowiednio `ditto`,
`osascript`) albo `skipUnless(sys.platform == "darwin")` — **tylko** gdy narzędzie jest istotą testu. Gdzie da się,
zastąp narzędzie stubem w PATH. Sprawdź, co job ubuntu faktycznie uruchamia (`.github/workflows/ci.yml`), i
odtwórz lokalnie: `docker run --rm -v "$PWD":/w -w /w python:3.12 …` **albo** (bez Dockera) uruchom te testy z
PATH pozbawionym `plutil`/`ditto`/`osascript` (katalog z symlinkami tylko do `bash`, `python3`, coreutils).

## M2 — macOS runner (tag): testy zależne od tego Maca

Z logu run `36111959508`:
1. `test_chromium_updaters.test_google_omaha_shared_deadline` — exit 124 (timeout). Test nadpisuje funkcję
   `date`, ale kod może czytać czas inaczej albo czekać na prawdziwy updater. Test musi być deterministyczny:
   żadnego prawdziwego czekania, żadnego prawdziwego GoogleUpdatera.
2. `test_appstore_ios.test_track2_verify_lookup_failure_is_soft_fail` i
   `test_track2_verify_python_error_is_soft_fail_not_empty_pending` — `0 != 10`: na runnerze nie ma aplikacji
   iPad, więc Track 2 się nie uruchamia. Użyj fałszywego katalogu aplikacji z `Wrapper/iTunesMetadata.plist`
   (jeśli kod nie ma przełącznika katalogów, dodaj **testowy** override, np. `MAC_UPDATE_APP_DIRS`, domyślnie
   `/Applications:$HOME/Applications`, użyty w `ios_apps_scan` — i opisz go w `docs/agents/scripts.md`).
3. `test_docker_update.test_docker_stop_is_called_after_version_polling_loop` — czyta prawdziwą
   `/Applications/Docker.app`. Stub `app_version` albo fałszywy bundle w katalogu tymczasowym.
4. `test_safety_static.test_report_update_coverage_vendor_feed_label_and_exclusions` — oczekuje zainstalowanego
   `Ascendo`. Fikstura z fałszywym katalogiem aplikacji zamiast prawdziwego `/Applications`.
5. `test_vendor_truth_handlers.test_toolkit_launched_tracking_and_graceful_quit` — `com.test.appB` trafił do
   `toolkit_launched.txt`: stub `osascript` nie przechwycił wywołania (np. kod woła `/usr/bin/osascript` albo
   `run_with_timeout` omija PATH). Upewnij się, że test kontroluje każde wywołanie `osascript`.

## M3 — strażnik hermetyczności

Test statyczny `test_tests_do_not_read_real_applications_dir` (`tests/test_safety_static.py`): pliki `tests/*.py`
nie mogą zawierać literału `"/Applications/` poza fiksturami tworzonymi w katalogu tymczasowym (allowlista
konkretnych linii z uzasadnieniem w komentarzu). Ma paść przed M2 i przejść po.

## M4 — dowód

1. Lokalnie: `bash run_tests.sh` zielone **oraz** te same testy z PATH bez `plutil`/`ditto`/`osascript` (M1).
2. Push gałęzi `fix/ci-hermetic-tests` **jest dozwolony** (tylko ta gałąź, nie `main`, bez tagów): CI dla
   gałęzi uruchamia job ubuntu. Job macOS uruchom ręcznie **jeden raz**: `gh workflow run ci.yml --ref
   fix/ci-hermetic-tests` (repo publiczne — minuty standardowych runnerów są darmowe; nie uruchamiaj
   wielokrotnie). Oba joby muszą być zielone: wklej `gh run list --branch fix/ci-hermetic-tests --limit 3`.
3. `CHANGELOG.md`: `## [Unreleased]` → „CI: hermetic tests (no dependency on the owner's /Applications or macOS-only tools)”.
4. Raport: sekcja `## v8` w `scratch/DOCS_LANDING_REPORT_v6.md`. **Nie merguj do `main`** — merge robi właściciel
   po zielonym CI.

## M5 — landing: domena

`https://macosupdates.dev` (stała `SITE_URL` w `src/lib/site.ts`) **nie rozwiązuje się w DNS**
(`curl: Could not resolve host`). Nie zmieniaj niczego — sprawdź tylko (`vercel ls` / `vercel domains ls`,
jeśli CLI jest zalogowane; inaczej opisz) pod jakim adresem działa deploy z `2d4df4c` i wpisz to do raportu
jako decyzję dla właściciela (kupno/podpięcie domeny albo zmiana `SITE_URL`).
