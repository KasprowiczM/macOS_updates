# Prompt poprawkowy v3 — Gemini 3.8 Flash — macOS Updates v1.5.0 (`feat/vendor-truth-v1.5`)

Weryfikacja poprawek v2 (F0–F12) wypadła **pozytywnie**: 450/450 testów, skaner importów i kompilacja
`python3 -c` działają, poprawki P0/P1 potwierdzone w kodzie i na żywo (guard casków zwraca
`version|installed|targets` bez `PYTHONPATH`, inwentarz spełnia wszystkie kryteria F3.7). Zostały: **jedna
blokada przed publikacją (prywatność)** i cztery drobne poprawki. Nic poza tym nie zmieniaj.

Obowiązują wszystkie zasady z promptu v1 §0–§2 i v2 §1 (najpierw test, który pada; jeden commit na zadanie;
Bash 3.2; i18n ×7; tylko komendy tylko-do-odczytu na żywo; **nie pushuj, nie merguj**).

---

## G0 — (BLOKADA) Prywatne dane w commitowanych raportach

Repozytorium jest **publiczne**. `APPLICATIONS.md` jest celowo w `.gitignore`, a mimo to dwa commitowane
raporty zawierają jego diff (nazwy i wersje aplikacji z tego Maca, nazwę użytkownika, ścieżkę domową):

| Plik | `/Users/…` | wiersze inwentarza |
|------|-----------|--------------------|
| `docs/reviews/archive/IMPLEMENTATION_REPORT_opus55_v1.md` (commit `f817377`) | 1 | ~118 |
| `docs/reviews/archive/FIX_REPORT_opus55_v2.md` (commit `fc3019b`) | 1 | ~35 |

Gałąź **nie jest wypchnięta**, więc da się to usunąć z historii, zanim trafi na GitHub.

1. **Redakcja treści.** W obu plikach zastąp każdy blok diffu `APPLICATIONS.md` listą kryteriów akceptacji
   z wynikiem, np. `- GarageBand w tabeli GRUPY 2 — ✅`. Dozwolone są tylko nazwy aplikacji wymienione
   w kryteriach promptów. Bez wierszy tabel inwentarza, bez wersji, bez nazwy użytkownika. Ścieżki domowe
   zapisuj jako `~`. Pełne diffy trzymaj wyłącznie w `scratch/` (ignorowany przez git).
2. **Przepisanie historii tylko tej gałęzi** (lokalnej, niewypchniętej):
   ```bash
   git branch backup/vendor-truth-v1.5-pre-redact          # kopia zapasowa: przywrócenie = git reset --hard na nią
   REDACT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/mac_update_redact.XXXXXX")"
   cp docs/reviews/archive/IMPLEMENTATION_REPORT_opus55_v1.md docs/reviews/archive/FIX_REPORT_opus55_v2.md "$REDACT_DIR/"   # już zredagowane
   export REDACT_DIR FILTER_BRANCH_SQUELCH_WARNING=1
   git filter-branch -f --tree-filter '
     for f in docs/reviews/archive/IMPLEMENTATION_REPORT_opus55_v1.md docs/reviews/archive/FIX_REPORT_opus55_v2.md; do
       [ -f "$f" ] && cp "$REDACT_DIR/$(basename "$f")" "$f"
     done; true' -- main..HEAD
   ```
   Weryfikacja (wklej wyniki do raportu):
   ```bash
   git log -p main..HEAD -- docs/reviews/ | grep -c '/Users/'                          # 0
   git diff --stat backup/vendor-truth-v1.5-pre-redact HEAD                             # tylko te 2 pliki
   git log --oneline main..HEAD | wc -l                                                 # tyle samo commitów co przed
   ```
   **Nie ruszaj `main`** ani żadnej innej gałęzi.
3. **Redakcja w przód na `main`** (zwykły nowy commit na tej gałęzi, bez przepisywania historii `main`):
   w `docs/reviews/archive/GEMINI_TASK_2026-09-02.md`, `docs/reviews/archive/ULTRA_REVIEW_2026-06-20.md`,
   `docs/reviews/archive/ULTRA_REVIEW_2026-08-05.md` i `docs/archive/plans/2026-09-03-v144-observability-claude-hang.md`
   zamień `/Users/<nazwa>/` na `~/`.
4. **Strażnik (test, który najpierw pada):** `test_tracked_files_have_no_personal_home_paths`
   w `tests/test_safety_static.py`. Dla każdego pliku z `git ls-files` (pomiń binaria i pliki, których nie da
   się zdekodować jako UTF-8) wyciągnij nazwy regexem `/Users/([A-Za-z0-9._-]+)`. Błędem (z `plik:linia`) jest
   każda nazwa **spoza** allowlisty syntetycznych nazw, które już są w testach i szablonach:
   `{"USER", "test", "testuser", "fake", "runner_user", "Shared"}` (plus zapisy `/Users/<user>` i `/Users/$…`,
   których regex nie złapie). Nowych nazw do allowlisty nie dodawaj. Jeśli `git` nie jest dostępny albo nie
   jesteśmy w repozytorium → `skipTest`. Test ma paść przed krokami 1–3 (6 plików z `docs/`) i przejść po nich.
5. W `docs/agents/handoff.md` albo w szablonie raportu (sekcja z wynikami) dopisz jedną regułę: *„Never paste
   `APPLICATIONS.md`/`UPDATES.md` content or diffs into tracked files — keep them in `scratch/`.”*

Commit: `docs(v1.5.0): redact private inventory from review reports and add home-path guard (G0)`.
Przepisanie historii z kroku 2 nie ma własnego commita.

---

## G1 — (P3) Cele `.app` dla casków `pkg` (dedupe w podsumowaniu)

Cask `zoom` nie ma artefaktu `app` (instaluje `pkg`), więc `brew_cask_targets.txt` nie dostaje `zoom.us`
i F10 nie zapobiega duplikatowi `zoom` / `zoom.us` na prawdziwym Macu. Homebrew podaje ścieżkę w stanzy
`uninstall`: `"delete": ["/Applications/zoom.us.app", …]`.

- `lib/python/brew_casks.py`: nowa `pkg_app_hints(cask) -> list[str]` zwraca basenames wpisów
  `uninstall[].delete` pasujących do `^/Applications/[^/]+\.app$` (string albo lista; `uninstall` jako dict albo
  lista). W `cask_guard_facts` trzecie pole = `app_targets(cask)` **albo**, gdy puste, `pkg_app_hints(cask)`.
- **`app_targets` i `find_orphan_casks` zostają bez zmian.** Wskazówki z `delete` nie mogą wpływać na
  wykrywanie sierot: stanza `delete` bywa sprzątaniem po starych nazwach, a to dałoby fałszywe sieroty.
- Testy: `test_cask_guard_facts_pkg_cask_uses_delete_hint` (JSON jak `zoom` ⇒ `…|zoom.us.app`),
  `test_orphan_detection_ignores_delete_hints` (cask `pkg` z `delete` do nieistniejącej `.app` ⇒ **nie** jest
  sierotą).

---

## G2 — (P3) App Store: każdy błąd lookupu, nie tylko rc 2

`update_appstore.sh`, blok po pętli weryfikacji: zamień `elif [ "$_verify_rc" -eq 2 ]` na
`elif [ "$_verify_rc" -ne 0 ]`. Teraz rc 1 (np. błąd Pythona w `ios_apps_pending`) daje komunikat
„still pending” z **pustą** listą nazw. Test: stub, w którym `python3` zwraca rc 1 w `ios_apps_pending`
⇒ komunikat `L_APPSTORE_IOS_VERIFY_LOOKUP_FAILED`, exit 10, brak `L_APPSTORE_IOS_VERIFIED`.

---

## G3 — (P3) Omaha: rotacja `updater.log`

Na żywo (2026-09-24): `~/Library/Application Support/Google/GoogleUpdater/updater.log` po rotacji ma 996 B,
a wszystkie wpisy `com.google.chrome` i `com.google.geminimacos` są w `updater.log.old`. Dlatego
`scripts/check_vendor_feeds.sh` pokazuje `-` dla Chrome i Gemini. To nie jest regresja F9, ale diagnoza jest
ślepa po każdej rotacji.

1. `scripts/check_vendor_feeds.sh`: przy odczycie „ostatniego statusu” czytaj dla każdej lokalizacji
   (użytkownik, system) `updater.log.old`, a potem `updater.log`, w tej kolejności (sklejone; decyduje
   ostatnie wystąpienie).
2. `omaha_read_increment` (używany przez `google_keystone_check` i handler Comet): gdy `cur_size < init_size`
   (rotacja w trakcie czekania), zwróć `tail -c +$((init_size + 1)) "<log>.old"`, jeśli plik istnieje,
   a potem cały nowy `<log>`.
3. Testy: fikstura, w której status Chrome jest tylko w `.old` ⇒ tabela pokazuje `noupdate`; rotacja
   w trakcie (init 100 B, nowy log 20 B, `.old` ma status po bajcie 100) ⇒ status znaleziony.

---

## G4 — (P3) Napis na sztywno

`update_npm_cli.sh`: `print_info "Diagnostyka: $MAC_UPDATE_SESSION_DIR/npm_cli_errors.log"` pojawia się w
`install_latest_npm_packages` i w nowym `update_native_clis` (skopiowany). Dodaj
`L_NPM_DIAGNOSTICS_PATH_FMT` (EN `Diagnostics: %s`, PL `Diagnostyka: %s`, pozostałe 5 przetłumacz) i użyj
w obu miejscach. To samo dla `print_warn "Ostatnia diagnostyka npm/self-update (sanityzowana):"`: nowy klucz
`L_NPM_LAST_DIAGNOSTICS` (EN `Last npm/self-update diagnostics (sanitized):`).

---

## G5 — Weryfikacja końcowa

```bash
bash run_tests.sh
find . -type f -name '*.sh' ! -path './.git/*' ! -path './graphify-out/*' ! -path './dev_sync_logs/*' -print0 | xargs -0 shellcheck --severity=warning
git log -p main..HEAD | grep -c '/Users/'          # 0
bash scripts/check_vendor_feeds.sh                  # Chrome/Gemini mają status (jeśli .old go zawiera)
git log --oneline main..HEAD | head -8
```

Raport: dopisz sekcję `## v3 (G0–G5)` na końcu `docs/reviews/archive/FIX_REPORT_opus55_v2.md` (tabela
`G | Status | Commit | Test, który padł | Testy po` + skrócone wyniki). **W raporcie nie może być żadnych
danych z `APPLICATIONS.md`.** W czacie: gałąź, liczba commitów, liczba testów przed i po, wynik
`git log -p main..HEAD | grep -c '/Users/'`. Nie pushuj, nie merguj.
