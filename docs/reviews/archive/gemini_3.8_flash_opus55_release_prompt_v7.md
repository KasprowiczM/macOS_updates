# Prompt v7 — Gemini 3.8 Flash — wydanie v1.5.1 i checklista akceptacji produkcyjnej

Stan (zweryfikowany przez Opus 5.5, 2026-09-25):
- `macOS_updates`: `main` = v1.5.0 (`c33ece3`, tag `v1.5.0`, wypchnięte). Gałąź `docs/v1.5.0-sync` (`fa5afad`)
  zawiera K1 (`8dae7e6`, status rollout Chrome) + K2 (dokumentacja). 480/480 testów, ShellCheck czysty.
- `macOS_updates_landing`: `main` = v1.4.5; gałąź `feat/landing-v1.5.0` (`fafd8e1`), lint i build zielone.
- Nic z v6 nie jest wypchnięte.

K1 zmienia zachowanie (nowy status), więc wydajemy **v1.5.1**. Zasady z v1–v6 obowiązują: Bash 3.2, i18n ×7
w toolkicie, najpierw test, który pada (gdy dotyczy kodu), jeden commit na zadanie, liczby tylko z komend,
zero danych prywatnych w trackowanych plikach. **Nic nie pushuj i nie merguj do `main`** — merge, tag i push
robi właściciel po review.

---

## L1 — Wersja 1.5.1 w `macOS_updates` (na gałęzi `docs/v1.5.0-sync`)

1. `CHANGELOG.md`: zamień `## [Unreleased]` na `## [1.5.1] — 2026-09-25` (K1: Chrome staged rollout status;
   dokumentacja zsynchronizowana z v1.5.0; strażnik `test_every_lib_file_is_documented_in_scripts_md`).
2. `VERSION` = `1.5.1` i wszystkie pliki sprawdzane przez `tests/test_version_consistency.py` (lista `LIVING`).
   Najpierw uruchom ten test po zmianie samego `VERSION`: ma paść i wskazać pliki do poprawy.
3. `bash run_tests.sh` → zapisz `Ran N tests` (oczekiwane 480 lub więcej). ShellCheck jak w T15.
4. Commit: `chore(release): v1.5.1 — Chrome staged rollout status and docs sync (L1)`.

## L2 — Landing na v1.5.1 (na gałęzi `feat/landing-v1.5.0`)

1. `src/lib/site.ts`: `APP_VERSION = 'v1.5.1'`, `APP_VERSION_DATE = '2026-09-25'`, `TEST_COUNT` = `N` z L1.3.
   `INTERNET_APP_COUNT` i `UPDATE_METHOD_COUNT` przelicz tymi samymi komendami co w v6 (raport:
   `scratch/DOCS_LANDING_REPORT_v6.md` w `macOS_updates`) — jeśli się nie zmieniły, zostaw.
2. `ChangelogPage.tsx`: wpis `v1.5.1` (2 zdania: Chrome w trakcie rolloutu Google pokazuje stan
   informacyjny zamiast „brak odpowiedzi”; dokumentacja zsynchronizowana).
3. `src/i18n/locales/en.json` i `pl.json`: każde „477” zamień na nową liczbę (grep). Landing ma tylko te dwa
   języki — nie dodawaj nowych.
4. `npm run lint`, `npm run build` zielone. `grep -rn "477\|v1\.5\.0" src index.html` — trafienia tylko
   w historii changelogu.
5. Commit: `feat(landing): v1.5.1 (L2)`.

## L3 — Checklista akceptacji produkcyjnej `docs/agents/acceptance_checklist.md` (nowy plik, `macOS_updates`)

Te ścieżki przeszły testy jednostkowe, ale **nie wystąpiły jeszcze w prawdziwym przebiegu**. Dokument ma
powiedzieć właścicielowi, jak rozpoznać każdą w logu `logs/update_all_*.log` i co jest poprawnym wynikiem.
Dla każdej: warunek wystąpienia, linia/komunikat w logu (klucz i18n + tekst EN), poprawny wynik, co zrobić
przy złym wyniku, oraz kolumna `Zaobserwowano (data / log)` do ręcznego wypełnienia.

| Ścieżka | Kiedy wystąpi |
|---|---|
| App Store Track 2 (GUI) dla aplikacji iPad | gdy lookup iTunes pokaże aktualizację UniFi/WiFiman/Picsart/… |
| Instalacja aktualizacji macOS: etykiety bez restartu + jedno wywołanie wsadowe z restartem | przy następnej aktualizacji macOS |
| Blokada dużego upgrade'u (np. macOS 28) | gdy `softwareupdate -l` pokaże nową wersję główną |
| Sierota Homebrew (usunięta `.app`, został cask) | po ręcznym usunięciu aplikacji z caska |
| `vendor_direct` z artefaktem DMG i ewentualny rollback `copy_verified_app` | aplikacja z feedem typu `dmg` będzie za wersją i zamknięta |
| Chrome rollout (K1) | gdy VersionHistory > zainstalowana, a Google nie zaoferował jeszcze aktualizacji |
| Zamykanie aplikacji uruchomionych przez toolkit | aplikacja była zamknięta, toolkit ją uruchomił (powinna zostać zamknięta na końcu) |

Źródła komunikatów weź z kodu (`grep` po kluczach w `i18n/lang_en.sh`). Dodaj plik do `docs/agents/scripts.md`
jeśli strażnik dokumentacji tego wymaga, i link w `CLAUDE.md` → „Reference Docs”
(`@docs/agents/acceptance_checklist.md — live acceptance paths for v1.5.x`).
Commit: `docs(v1.5.1): live acceptance checklist (L3)`.

## L4 — Agentic OS

1. `atlas/projects/project.macos-updates.md` i `project.macos-updates-landing.md`: jedna linia w State/Next
   Steps o v1.5.1 (gałęzie, commity, „czeka na merge/push właściciela”).
2. `agentic handoff "<stan + następne kroki>" -p macos-updates` i `-p macos-updates-landing`.
3. `agentic sync`, `agentic lint` → 0 błędów. Commituj w vaultcie tylko pliki, które sam zmieniłeś.

## Raport

Dopisz sekcję `## v7` do `scratch/DOCS_LANDING_REPORT_v6.md` (ignorowany przez git): tabela
`L | Status | Repo | Gałąź | Commit | Komenda/test`, liczby z komendami, wynik lint/build/testów.
W czacie 3 linie: gałęzie + commity, liczba testów, „nic nie wypchnięte”.
