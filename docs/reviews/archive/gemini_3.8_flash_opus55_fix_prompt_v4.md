# Prompt poprawkowy v4 — Gemini 3.8 Flash — macOS Updates v1.5.0 (`feat/vendor-truth-v1.5`)

Źródło: pierwszy **prawdziwy** przebieg `update_all.sh` na gałęzi (2026-09-24 22:38, 8 min 13 s). Kroki 0, 2, 5 i 6
są czyste. VS Code (1.138→1.139) i Cursor (3.21.18→3.22.7) zaktualizowały się z weryfikacją. Poniższe błędy
wyszły dopiero na żywo. Zasady jak w v1–v3 (najpierw test, który pada; jeden commit na H; Bash 3.2; i18n ×7;
bez danych z `APPLICATIONS.md` w trackowanych plikach; nie pushuj, nie merguj).

---

## H1 — (P0) Homebrew: „outdated” to nie błąd

`lib/brew.sh::brew_outdated_casks` wywołuje `brew outdated --cask --greedy-auto-updates <tokeny>`.
Z nazwanymi argumentami Homebrew **kończy się kodem 1, gdy któryś z nich jest nieaktualny**. Na żywo:
`brew outdated --cask --greedy-auto-updates brave-browser capcut` → stdout `brave-browser`, `capcut`,
stderr pusty, rc 1. Funkcja uznaje to za awarię, a `update_brew.sh` (~l.203) wypisuje
`brew outdated --cask failed; update state is unknown` i kończy krok **bez żadnego upgrade'u** (ani casków,
ani formulae).

- W obu wywołaniach `brew outdated` w `brew_outdated_casks`: rc 0 → OK. rc 1 **i pusty stderr** → OK (wynik =
  stdout). Każdy inny przypadek (rc ≥ 2 albo niepusty stderr) → błąd jak dotąd.
- Sprawdź tak samo `brew_outdated_formulae`, jeśli dostaje nazwy.
- Testy (stub `brew`): rc 1 + stdout `brave-browser` + pusty stderr ⇒ funkcja zwraca 0 i zawiera
  `brave-browser`; rc 1 + stderr `Error: Cask 'x' is unavailable` ⇒ rc ≠ 0. Test `update_brew.sh` ze stubem:
  outdated greedy cask ⇒ w logu stuba jest `upgrade --cask brave-browser`.

## H2 — (P1) Zamykaj to, co toolkit sam uruchomił

Na żywo OpenCode Desktop i Microsoft Teams zostały uruchomione w tle i **nie zostały zamknięte**. Reguła §15:
toolkit zamyka tylko to, co sam uruchomił, i tylko łagodnie.

- Przy każdym ukrytym uruchomieniu na potrzeby updatera (`silent_launch_app` i handlery, które go wołają,
  m.in. OpenCode, Teams, Proton Drive, Comet) sprawdź **przed** uruchomieniem `internet_app_is_running <bundle id>`.
  Jeśli aplikacja nie działała, dopisz bundle ID do `$MAC_UPDATE_SESSION_DIR/toolkit_launched.txt`.
- Na końcu `update_internet_apps.sh`, **po** istniejącym settle (`MAC_UPDATE_INTERNET_SETTLE_SECONDS`), dla
  każdego ID z pliku wywołaj `internet_app_quit_gracefully`. Nigdy `kill`, nigdy aplikacji spoza pliku. Nie
  zamknięta w 60 s → komunikat `L_INTERNET_APP_STILL_RUNNING_FMT` (soft, bez zmiany statusu aplikacji).
- Test: stub `osascript` (stan running per ID). Aplikacja A nie działała → uruchomiona → na końcu `quit A`;
  aplikacja B działała wcześniej → brak `quit B`.

## H3 — (P1) OpenCode Desktop i Teams: najpierw sprawdź, potem uruchamiaj

- `iu_opencode_desktop` pomija ścieżkę vendor truth, choć `config/vendor_feeds.txt` ma wiersz `OpenCode`
  (na żywo feed = zainstalowana 1.18.32). Mimo to aplikacja została uruchomiona. Po ustaleniu
  `OPENCODE_APP_PATH` wołaj `internet_handler_vendor_truth "OpenCode" "$OPENCODE_APP_PATH" "$OPENCODE_APP_PATH"`
  i ustaw `STATUS_OPENCODE`. Sprawdź też, czy OpenCode ma wiersz w tabeli podsumowania — w logu go **nie było**.
  Jeśli go brak, dodaj.
- `iu_microsoft_teams`: jeśli kontrola wersji (cask oracle albo MAU) już daje „aktualna”, **nie uruchamiaj**
  Teams. Uruchamiaj tylko przy wykrytej zaległości albo braku jakiejkolwiek kontroli.
- Testy: feed równy ⇒ log `open` pusty dla OpenCode; Teams aktualny wg oracle ⇒ brak `open`.

## H4 — (P1) Google Omaha: jedno okno czekania i dowód z ostatniej kontroli

Na żywo: `--wake-all` wykonało się (exit 0), ale GoogleUpdater **nie wysłał** nowego zapytania, bo ostatnia
kontrola była 19 min wcześniej, a stare katalogi 148–151 dołożyły ~60 s timeoutu. Każda z trzech aplikacji
czekała osobno do 45 s na odpowiedź, która nie przyszła. Efekt: kilka minut i trzy statusy ⏳.

1. **Wspólny termin:** pierwsze wywołanie `google_keystone_check` zapisuje w `google_omaha_init.txt` także
   `deadline=$(( $(date +%s) + MAC_UPDATE_OMAHA_WAIT ))`. Kolejne aplikacje czekają tylko do tego terminu.
   Łączny czas czekania na 3 aplikacje ≤ `MAC_UPDATE_OMAHA_WAIT`.
2. **Kolejność wyzwalania:** najpierw `GoogleUpdater --wake-all` (użytkownika, potem systemowy), a legacy
   `GoogleSoftwareUpdateAgent --runMode ondemand` tylko gdy GoogleUpdater nie istnieje. Timeout 60 s (było 180).
3. **Chrome — najpierw sprawdź:** przed wyzwoleniem porównaj wersję zainstalowaną z VersionHistory
   (`version_history_public`, już używane). Zainstalowana ≥ publicznej → `✅ … (Google VersionHistory)` bez
   wyzwalania.
4. **Dowód z ostatniej kontroli:** gdy w oknie nie ma nowej odpowiedzi, weź ostatni status danego appid z
   `updater.log.old` + `updater.log` razem ze znacznikiem czasu z prefiksu linii (`[pid:tid:MMDD/HHMMSS.…]`).
   Jeśli jest nie starszy niż `MAC_UPDATE_OMAHA_MAX_AGE_H` (domyślnie 6), `noupdate` →
   `L_INTERNET_STATUS_OMAHA_RECENT_FMT` (EN `Up to date (Google updater check at %s)`, PL `Aktualna (kontrola
   updatera Google o %s)`), klasyfikowane jako `current_vendor`. Starszy albo brak → `⏳` jak dziś.
   Dopisz zmienną do `docs/agents/scripts.md`.
5. Testy: trzy appid bez nowej odpowiedzi ⇒ łączny `sleep` ≤ OMAHA_WAIT (stub `sleep` sumuje); status
   `noupdate` sprzed 2 h ⇒ ✅ z godziną; sprzed 8 h ⇒ ⏳; Chrome równy VersionHistory ⇒ zero wywołań updatera.

## H5 — (P2) Cursor: najpierw instalacja od producenta

Na żywo Cursor zużył 90 s na uruchomienie updatera i 60 s na polling — bez zmiany wersji. Updater Cursora
tylko pobiera w tle i instaluje przy restarcie. Wersję 3.22.7 zainstalowało dopiero `vendor_direct`
(downloads.cursor.com, podpis i Team ID zweryfikowane).

- Nowy plik `config/vendor_direct_first.txt` (jedna nazwa z rejestru na linię, `#` = komentarz), na start
  `Cursor`. W `internet_handler_vendor_truth`: jeśli aplikacja jest na liście, **nie** działa,
  `ART != "-"` i `MAC_UPDATE_VENDOR_DIRECT != 0` → pomiń cykl uruchomienia i przejdź od razu do
  `vendor_direct_install`. To nadal oryginalny artefakt producenta z tego samego hosta z allowlisty.
- Test: Cursor na liście, feed nowszy, app nie działa ⇒ brak `open`, jest wywołanie `vendor_direct_install`.

## H6 — (P2) App Store: pusty „retry”

W logu: `sudo mas upgrade left these App Store updates pending; retrying in the user session:` bez listy ID,
bez widocznego wyniku ponowienia. `Whisper Transcription (15.1.1 -> 15.2.1)` został w kolejce.
Odtwórz ze stubem `mas` (po `sudo mas upgrade` `outdated` nadal zwraca to ID): komunikat ma wymieniać ID
i nazwy, ponowienie ma się wykonać (`mas upgrade <id>` bez sudo), a jego wynik trafić do
`appstore_diag.txt`. Jeśli po ponowieniu nadal wisi, status końcowy wskazuje aplikację i sugeruje ręczną
aktualizację w App Store (soft).

## H7 — (P3) Niestabilne testy MAU

`tests/test_run_log_regressions_20260910.py::test_mau_active_processes_when_none_running` i
`test_mau_install_success_requires_version_change_or_clean_listing` padły w pełnym przebiegu, a osobno
przechodzą. Prawdopodobnie zależą od prawdziwej listy procesów (Microsoft AutoUpdate budzi się okresowo).
Zastąp prawdziwe `pgrep`/`ps` stubem w PATH. Test ma przejść 5× z rzędu (`for i in 1 2 3 4 5`).

---

## Weryfikacja końcowa

```bash
bash run_tests.sh
find . -type f -name '*.sh' ! -path './.git/*' ! -path './graphify-out/*' ! -path './dev_sync_logs/*' -print0 | xargs -0 shellcheck --severity=warning
env -u PYTHONPATH bash -c 'source lib/brew.sh; brew_outdated_casks brave-browser capcut; echo rc=$?'   # rc=0 i lista (jeśli nadal nieaktualne)
git log -p main..HEAD | grep '^+[^+]' | grep -c '/Users/'                                              # 0 poza nazwami syntetycznymi z testów
```

Raport: sekcja `## 7. Poprawki v4 (H1–H7)` w `docs/reviews/archive/FIX_REPORT_opus55_v2.md` (tabela jak w v3). W czacie:
gałąź, liczba commitów, liczba testów przed/po. Nie pushuj, nie merguj.
