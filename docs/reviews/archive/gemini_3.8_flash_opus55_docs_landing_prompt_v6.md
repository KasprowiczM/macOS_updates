# Prompt v6 — Gemini 3.8 Flash — dokumentacja v1.5.0: projekt, landing, Agentic OS

Stan wyjściowy: **macOS Updates v1.5.0 jest na `main`** (`c33ece3`, tag `v1.5.0`, wypchnięte). 477 testów,
dwa prawdziwe przebiegi `update_all.sh` zaliczone. Kod jest gotowy. Ten prompt synchronizuje **dokumentację
i stronę produktu** z tym, co kod naprawdę robi, oraz poprawia jeden status (K1).

Obowiązują zasady z promptów v1–v5 (Bash 3.2, i18n ×7, najpierw test, który pada, gdy dotyczy kodu, jeden commit
na zadanie). Dodatkowo:
- **Nic nie pushuj** — ani w `macOS_updates`, ani w landingu (push `main` landingu = deploy na Vercel).
- Każda liczba i każde twierdzenie w dokumentacji ma pochodzić z repo (config, kod, wynik komendy), nie z
  pamięci. Przy każdej liczbie zapisz w raporcie komendę, którą ją policzyłeś.
- **Prywatność:** repozytoria są publiczne. Zero ścieżek `/Users/<nazwa>`, zero danych z `APPLICATIONS.md`/
  `UPDATES.md`, zero treści z vaultu Agentic OS w plikach repozytoriów (reguła `AGENTS.md`: vault → repo tylko
  przez `AGENTS.local.md`/`CLAUDE.local.md`). Nazwy aplikacji z publicznego rejestru (`config/*.txt`) są OK.

Najważniejsza zasada produktu, którą dokumentacja ma mówić wprost we wszystkich 7 językach:
**„Aplikacje, które masz otwarte, nigdy nie są zamykane. Skrypt zamyka tylko to, co sam uruchomił.”**
(EN: *“Apps you have open are never closed — the toolkit only quits what it launched itself.”*)

---

## K1 — (kod, P3) Chrome: „rollout w toku” zamiast „brak odpowiedzi”

Repo `~/Dev_Env/macOS_updates`, gałąź `fix/chrome-rollout-status` od `main`.

Na żywo (2026-09-25): Chrome 153.0.8010.53, Google VersionHistory = 154.0.8037.58, a strona „O Google Chrome”
pokazuje „aktualna”. To **rollout etapowy**: Google jeszcze nie zaoferował 154 temu Macowi. Toolkit pokazał
`⏳ Uruchomiono updater producenta (brak zapisanej odpowiedzi)`, co jest prawdą, ale nic nie wyjaśnia.

- W `evaluate_omaha_status` (`lib/internet_handlers.sh`) dla `com.google.chrome`: gdy nie ma odpowiedzi Omaha
  ani świeżego statusu (`MAC_UPDATE_OMAHA_MAX_AGE_H`), a `version_history_public` zwraca wersję nowszą niż
  zainstalowana → `L_INTERNET_STATUS_ROLLOUT_HOLD_FMT` (użyj istniejącego klucza, sprawdź argumenty),
  kod `rollout_hold`. To stan **informacyjny**: nie ustawia `INTERNET_SOFT_FAIL`, bo Google celowo jeszcze nie
  oferuje aktualizacji.
- Zainstalowana ≥ publicznej → dalej `✅` (VersionHistory). Brak VersionHistory → `⏳` jak dziś.
- Test w `tests/test_chromium_updaters.py` (stub `curl` z VersionHistory 154, puste logi Omaha, zainstalowana
  153) ⇒ status z `rollout_hold`, brak soft fail. Ma najpierw paść.
- Jeden commit `fix(chrome): report staged rollout instead of missing Omaha response (K1)`.

## K2 — Dokumentacja projektu `macOS_updates`

Gałąź `docs/v1.5.0-sync` od `main` (albo od `fix/chrome-rollout-status`, jeśli K1 jest gotowe).

1. **`docs/agents/scripts.md`** — brakuje wierszy dla: `lib/appstore_ios.sh`, `lib/internet_status.sh`,
   `lib/python/brew_casks.py`, `lib/python/cli_retention.py`, `lib/python/appstore_lookup.py`,
   `config/vendor_direct_first.txt`, `config/cask_oracles.txt`, `tests/_env.py`. Opis weź z nagłówka pliku
   (1 zdanie). Potem dodaj **test strażnika** `test_every_lib_file_is_documented_in_scripts_md`
   (`tests/test_safety_static.py`): każdy `lib/*.sh` i `lib/python/*.py` (bez `__init__.py`) musi występować
   w `docs/agents/scripts.md`. Test ma paść przed uzupełnieniem; uzupełnij **wszystkie** braki, które zgłosi.
2. **`docs/agents/critical_rules.md` §5 (tabela metod)** — jest nieaktualna. Wygeneruj ją z
   `config/internet_app_methods.txt` + `config/vendor_feeds.txt` + `config/vendor_direct_first.txt`:
   nowy wiersz „Vendor feed truth (verified)” z aplikacjami, które mają wiersz w `vendor_feeds.txt`
   (Cursor z adnotacją „direct-first”); z wiersza „Built-in auto-updater (triggered-unverified)” usuń wszystko,
   co jest weryfikowane feedem albo zarządzane przez Homebrew; Brave/Obsidian/Spotify/itd. tylko w wierszu
   Homebrew. Każda aplikacja w dokładnie jednym wierszu.
3. **`docs/agents/architecture.md`** — sekcja „Session Dir”: wypisz pliki sesji używane w v1.5.0 i ich
   znaczenie: `toolkit_launched.txt`, `google_omaha_init.txt`, `brew_cask_targets.txt`,
   `brew_orphan_casks.txt`, `brew_needs_interactive.txt`, `appstore_ios_before.txt`/`_after.txt`,
   `appstore_ios_pending.txt`, `internet_status_codes.txt`. Sprawdź każdą nazwę `grep`-em w kodzie.
4. **`docs/agents/troubleshooting.md`** — nowe wiersze: „Status: quit the app so its updater can install”
   (aplikacja była otwarta — celowo nietknięta); „Why did the toolkit open an app and close it again” (tylko
   aplikacje, których nie było otwartych); „Chrome: staged rollout” (po K1); „Google status ✅ with a time”
   (`MAC_UPDATE_OMAHA_MAX_AGE_H`); „App Store update stays pending after retry” (zaktualizuj ręcznie
   w App Store); „Cursor installs from the vendor without launching” (`config/vendor_direct_first.txt`).
5. **7 × README** — jeden punkt z główną zasadą o otwartych aplikacjach (tekst wyżej, przetłumacz na
   de/es/fr/it/pt) oraz aktualna liczba testów tam, gdzie README ją podaje (policz: `bash run_tests.sh`,
   linia `Ran N tests`).
6. **`CLAUDE.md`** (sekcja Quick Commands): dodaj `bash scripts/check_vendor_feeds.sh   # Vendor truth table (read-only)`.
7. **`CHANGELOG.md`**: sekcja `## [Unreleased]` z punktami K1 i „Documentation synced with v1.5.0”.
8. `bash run_tests.sh` i ShellCheck (jak w T15) — zielone. Jeden commit na punkt albo logiczną grupę
   (`docs(v1.5.0): …`).

## K3 — Landing `~/Dev_Env/macOS_updates_landing`

Stack: React 19 + Vite 8 + Tailwind 4, i18n w `src/i18n/locales` (7 języków), deploy Vercel. Obecnie strona
mówi o **v1.4.5** (`src/lib/site.ts`: `APP_VERSION`, `APP_VERSION_DATE`, `TEST_COUNT = 270`,
`INTERNET_APP_COUNT = 43`, `UPDATE_METHOD_COUNT = 10`), a zmiany z v1.4.6 i v1.5.0 w ogóle nie trafiły na stronę.
Gałąź `feat/landing-v1.5.0`.

1. **`src/lib/site.ts`** — wartości policz z repo `macOS_updates` na tagu `v1.5.0` i wpisz komendy do raportu:
   - `APP_VERSION = 'v1.5.0'`, `APP_VERSION_DATE = '2026-09-25'`;
   - `TEST_COUNT` = `N` z `bash run_tests.sh` (`Ran N tests`) na `v1.5.0`;
   - `INTERNET_APP_COUNT` = liczba niepustych, niekomentowanych linii `config/internet_apps.txt`;
   - `UPDATE_METHOD_COUNT` = liczba unikalnych metod (kolumna 2) w `config/internet_app_methods.txt`, bez
     komentarzy i pustych. Jeśli strona definiuje „metodę” inaczej (np. grupuje), zachowaj tę definicję
     i opisz ją w raporcie.
2. **`ChangelogPage.tsx`** — wpisy `v1.4.6` (2026-09-16) i `v1.5.0` (2026-09-25) na podstawie `CHANGELOG.md`
   (streszczenie dla użytkownika, nie kopia 1:1).
3. **Treści (Features / Docs / Security / FAQ / Landing, 7 języków):**
   - dodaj: prawda od producenta (feed producenta i Omaha decydują, Homebrew tylko potwierdza); aktualizowane
     jest tylko to, co zainstalowane (`--bootstrap-cli` dla chętnych); osierocone caski są pomijane;
     **otwarte aplikacje nigdy nie są zamykane**; zweryfikowane instalacje od producenta (allowlista hostów,
     podpis + Team ID, rollback); inwentarz synchronizuje wszystkie grupy; `scripts/check_vendor_feeds.sh`;
   - usuń albo popraw twierdzenia, które przestały być prawdą (sprawdź `grep`-em: `-ia`, `greedy`, „launch”,
     „auto-updater”, stare liczby testów/aplikacji, `v1.4.5`), np. `softwareupdate -ia -R` → aktualizacja
     per etykieta z jednym restartem na końcu;
   - każdy nowy klucz tekstowy we wszystkich 7 plikach `locales` (jeśli landing ma test albo skrypt parzystości
     kluczy — uruchom go).
4. `index.html` (meta/wersja), jeśli zawiera wersję.
5. Weryfikacja: `npm run lint`, `npm run build` — bez błędów. `grep -rn "1\.4\.5\|1\.4\.6" src index.html`
   może trafić **tylko** w historię changelogu. `grep -rn "/Users/" src index.html` → 0.
6. Jeden lub kilka commitów `feat(landing): sync with macOS Updates v1.5.0 …`. **Bez pusha.**

## K4 — Agentic OS (vault `~/Dev_Env/AI_Agentic_OS`)

Postępuj według `AGENTS.md` i `protocols/session-end.md` vaultu.

1. `atlas/projects/project.macos-updates-landing.md`: w „Next Steps” zaznacz synchronizację z v1.5.0 (hash
   commita landingu, data), dodaj „## State (2026-09-25)” (2–4 zdania: co strona teraz mówi, że czeka na push/deploy).
2. `atlas/projects/project.macos-updates.md`: zaznacz „macos-updates-landing: sync to v1.5.0” (lokalnie, bez
   pusha) i punkt Chrome (po K1 — rollout zamiast „behind”); dopisz jedną linię o K2.
3. `agentic remember "<1 zdanie>" -p macos-updates-landing` (np. że liczby na stronie liczy się z repo na tagu).
4. `agentic handoff "<stan + następne kroki: review i push landingu (Vercel), push docs/K1>" -p macos-updates`
   oraz to samo `-p macos-updates-landing`.
5. `agentic sync` i `agentic lint` → 0 błędów. Nie commituj w vaultcie cudzych zmian (sprawdź `git status`
   vaultu; commituj tylko pliki, które zmieniłeś, jeśli vault ma taki zwyczaj — inaczej zostaw).

## Raport

Utwórz **`scratch/DOCS_LANDING_REPORT_v6.md`** w `macOS_updates` (ignorowany przez git — raport zawiera
ścieżki lokalne). Zawartość: tabela `K | Status | Repo | Gałąź | Commit(y) | Test/komenda`, każda liczba
z komendą, wynik `npm run lint`/`build`, `run_tests.sh`, lista zmienionych plików, co wymaga decyzji
użytkownika (push obu repozytoriów). W czacie: 3 linie — gałęzie, liczba commitów, „nic nie wypchnięte”.
