# Prompt wykonawczy — Gemini Flash 3.7 (high)

**Projekt:** `/Users/mk/Dev_Env/macOS_updates`
**Baza:** v1.4.3 (2026-09-02), 213 testów zielonych
**Źródło zadań:** `docs/reviews/ULTRA_REVIEW_2026-09-02.md`, sekcja „Rekomendacje" (R1–R7)

Skopiuj wszystko poniżej linii jako prompt.

---

Pracujesz w repozytorium `/Users/mk/Dev_Env/macOS_updates` na macOS 26.6.2, Apple Silicon. Zanim cokolwiek zmienisz, przeczytaj w tej kolejności: `AGENTS.md`, `docs/reviews/ULTRA_REVIEW_2026-09-02.md`, `docs/agents/critical_rules.md`, `docs/agents/exit_codes.md`, `docs/agents/architecture.md`.

## Zasada nadrzędna tego zadania

**Dowodem jest stan systemu docelowego, nigdy stan repozytorium.** Zielony test, który sprawdza treść pliku, nie dowodzi, że kod się wykonuje ani że coś naprawił. Jeśli czegoś nie da się zrobić lub zweryfikować — napisz `NIE WYKONANO, powód: …` i przejdź dalej. Nie pisz „przygotowano procedurę" ani „wygenerowano plik gotowy do wklejenia": to jest równoznaczne z niewykonaniem.

Przy każdym zadaniu podaj osobno:
- **Zrobione w repo:** (pliki, funkcje)
- **Zmierzone na systemie:** (dokładna komenda + jej wyjście)
- **Regresje:** co sprawdziłeś, że nadal działa

## Czego NIE ruszać — to już jest naprawione w v1.4.3

Te defekty zostały rozwiązane i zweryfikowane pomiarem 2026-09-02. Nie odtwarzaj ich, nie „poprawiaj" i nie cofaj:

1. Wygasanie kwarantanny MAU (`mau_quarantine_*` w `lib/internet_app_updates.sh`, `MAC_UPDATE_MAU_QUARANTINE_MAX_DAYS`). W szczególności: **ponowne uzbrojenie nie może resetować zegara**, a wpis bez zapisu liczy się jako wygasły.
2. `DeferralVersions.TEAMS21` — pin równy zainstalowanemu buildowi jest księgowością MAU, nie usterką. Nie przywracaj jego usuwania ani ostrzeżenia o formacie Major.Minor.
3. Zbiór wygasły idzie jako **argument oferty tego samego** wywołania `mau_reconcile_deferrals`. Nigdy nie dodawaj drugiego wywołania w jednym przebiegu — dwa cykle export/import ścigają się przez `cfprefsd`.
4. TOR 1 w `update_appstore.sh` przekazuje jawne ID + jeden retry per ID w sesji użytkownika. Retry ma zostać jednorazowy.
5. `run_counts.json` → `counts` w `run_summary_*.json`.
6. Brak auto-updatera u dostawcy (IPMIView, DJI) to `print_info`, nie `print_warn`.

## Reguły nienegocjowalne (z `AGENTS.md`)

1. `softwareupdate` MUSI mieć `-R`.
2. `mas upgrade` pod `sudo`, ale **z jawnymi ID** i fallbackiem w sesji użytkownika (zawężone w v1.4.3).
3. **Bash 3.2** — bez `declare -A`, `mapfile`, `readarray`. Puste tablice pod `set -u` to błąd, nie puste rozwinięcie; każde rozwinięcie tablicy potrzebuje własnego strażnika `(( ${#ARR[@]} > 0 ))`.
4. Bez nowych samodzielnych wejść pipeline'u w Pythonie — kod zostaje w heredocach albo w importowalnych czystych funkcjach w `lib/python/`.
5. Bez hardcode'owanych ścieżek — `SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"`.
6. Orkiestratory `update_*.sh`: `set -o pipefail`, **nigdy** `set -e`.
7. Metoda w `config/internet_app_methods.txt` jest ważna tylko wtedy, gdy istnieje handler.
8. Nigdy interaktywne `sudo` bez TTY.
9. Nowe komunikaty dla użytkownika: albo klucz w **wszystkich siedmiu** plikach `i18n/lang_*.sh`, albo zwykły angielski string (obie konwencje są w kodzie).

## Zadania do wykonania

### Z1 (wysoki) — Detektor chronicznych ostrzeżeń  → R2

20 kolejnych przebiegów było `degraded` i nic nie eskalowało. Ostrzeżenie powtarzalne przestaje być stanem, a staje się defektem.

Zbuduj `scripts/report_chronic_warnings.sh`:
- czyta ostatnie N (`MAC_UPDATE_CHRONIC_WINDOW`, domyślnie 10) plików `logs/run_summary_*.json`, sortowanych po nazwie;
- dla każdego kroku (`prescan`, `appstore`, `npmcli`, `brew`, `internet`, `postupdate`, `system`) liczy, ile kolejnych ostatnich przebiegów zakończyło go inaczej niż `OK`;
- jeśli seria ≥ `MAC_UPDATE_CHRONIC_THRESHOLD` (domyślnie 3) — wypisuje wyraźny raport: krok, długość serii, znacznik czasu pierwszego przebiegu w serii;
- wywołaj go na końcu `update_all.sh`, po zapisaniu podsumowania, i **nigdy** nie pozwól mu zmienić exit code przebiegu;
- Python trzymaj w heredocu albo w `lib/python/` (reguła 4).

Weryfikacja: uruchom na prawdziwym `logs/` tej maszyny. Ma wykryć serię `internet`/`appstore` w plikach z sierpnia. Pokaż wyjście.

### Z2 (wysoki) — Audyt strażników pod kątem tłumienia własnego dowodu  → R1

Klasa defektu, która wysadziła kwarantannę Office: mechanizm ukrywa własne wejście diagnostyczne i przez to nigdy nie może się ponownie ocenić.

Przejrzyj pod tym kątem:
- strażnik cofania wersji casków w `update_brew.sh`,
- ścieżkę `vendor_latest` w `lib/internet_app_updates.sh`,
- filtry pomijania w `update_npm_cli.sh`.

Dla każdego odpowiedz na trzy pytania i **udokumentuj odpowiedzi w `docs/reviews/GUARD_AUDIT_2026-09.md`**:
1. Czy ten strażnik ukrywa dane, na podstawie których podejmuje decyzję?
2. Jeśli tak — co musiałoby się zdarzyć, żeby go zwolnić, i czy to zdarzenie jest w ogóle obserwowalne, gdy strażnik jest aktywny?
3. Jeśli nie jest obserwowalne — dodaj okno życia i drogę do ponownej oceny, wzorowane na `mau_quarantine_expired_ids`.

Nie zmieniaj zachowania strażnika, który przejdzie audyt. Napisz wtedy wprost, dlaczego przechodzi.

Na koniec dopisz do `AGENTS.md` regułę nienegocjowalną nr 10: *każdy mechanizm, który ukrywa własne wejście diagnostyczne, musi mieć zadeklarowane okno życia i drogę do ponownej oceny.*

### Z3 (średni) — `counts` o tym, co się NIE udało  → R3

Dziś `counts` mówi, ile pakietów się ruszyło. Nie mówi, ile powinno. Dodaj do `run_counts.json` liczby pozostałych po przebiegu (np. `pending_after_run` per krok — App Store z `mas outdated`, Homebrew z `brew_outdated_*`, MAU z `msupdate --list`). To jest fundament pod Z1.

Uwaga: `brew_outdated_formulae` / `brew_outdated_casks` z `lib/brew.sh`, **nigdy** `brew outdated` bezpośrednio i **nigdy** `2>&1` na przechwyceniu. Nigdy `brew list --cask --versions` — użyj `brew_cask_versions`.

### Z4 (średni) — Logowanie rozbieżności mas ↔ App Store GUI  → R4

2026-09-01 GUI App Store raportowało „brak oczekujących aktualizacji", a `mas outdated` widział WhatsAppa 26.33.73 → 26.34.72. Rozbieżność między torami to najlepszy sygnał, że jeden z nich kłamie, a nigdzie nie jest zapisywana.

W `update_appstore.sh` zapisuj do `$MAC_UPDATE_SESSION_DIR/appstore_diag.txt` porównanie: co widział `mas outdated` przed TOR 1, co zwrócił AppleScript w TOR 2, i co `mas outdated` widzi po obu torach. Bez zmiany logiki decyzyjnej.

### Z5 (niski) — Sprzątanie  → R5, R6

- `.mac_update_prefs`: `FIREFOX_DEV_CHANNEL_VERSION=150.0b10` nie jest czytany przez żaden skrypt (`grep -rn FIREFOX_DEV_CHANNEL_VERSION` daje tylko ten plik). Usuń klucz albo podłącz go jako cache kanału — wybierz jedno i uzasadnij.
- Firefox Developer Edition raportuje „zaktualizowany do wersji 156.0" po pobraniu `156.0b1`. Bundle deklaruje `156.0`, więc porównanie jest poprawne — ale komunikat gubi kanał. Pokazuj obie wartości: `156.0 (kanał 156.0b1)`.

## Definicja ukończenia

Zadanie jest skończone dopiero, gdy **wszystkie** poniższe są spełnione:

1. `bash run_tests.sh` — zielone, z **nowymi testami regresji dla każdego zadania**. Test ma być behawioralny wszędzie tam, gdzie się da: uruchamiaj funkcje bashowe przez `subprocess` i sprawdzaj wyjście, zamiast szukać regexem w treści pliku. Wzorzec: `tests/test_run_log_regressions_20260902.py`.
2. `python3 -m unittest tests/test_dev_sync_safety.py` — osobno, `tests/run_all.sh` tego nie łapie.
3. `bash -n` na każdym zmienionym `.sh`, `shellcheck -S error` bez błędów.
4. `bash scripts/scan_secrets.sh` — czysto.
5. **Przebieg na żywo** `MAC_UPDATE_YES=1 bash update_internet_apps.sh` oraz `bash update_all.sh --dry-run`. Wklej exit code i liczbę ostrzeżeń. Stan bazowy do porównania: krok internetowy = **0 ostrzeżeń, exit 0**. Każda regresja względem tego jest błędem twojej zmiany.
6. `VERSION` → 1.4.4, wpis w `CHANGELOG.md` w formacie istniejących wpisów: objaw → przyczyna źródłowa → naprawa → dowód pomiarowy.
7. Handoff przez CLI huba, nie ręcznie:
   `agentic handoff -p macos-updates "<podsumowanie>"`
8. Git: branch → commit → push brancha → `merge --no-ff` do `main` → push `main`.

## Pułapki z historii tego projektu — nie powtórz ich

- Zielony test jednostkowy nie dowodzi podpięcia. `rotate_old_artifacts()` miała przechodzący test i zero wywołań produkcyjnych od marca do sierpnia; `logs/` urosło do 1183 plików.
- Instalatory dostawców czytają prompt z `/dev/tty`, nie ze stdin. `</dev/null` ich nie ominie — potrzebny jest ich własny przełącznik non-interactive. Nigdy nie „naprawiaj" promptu dłuższym timeoutem.
- Nigdy nie porównuj wersji z bundla z wersją z menedżera pakietów na surowo. Bundle Brave to `151.1.93.138`, cask to `1.93.138.0`. Preferuj ewidencję menedżera; nieporównywalne schematy dają `unknown`, nigdy „downgrade".
- `latest-mac.yml` electron-buildera powtarza digest **pierwszego** pliku z listy jako `sha512:` najwyższego poziomu. Zawsze paruj URL z digestem z tego samego wpisu.
- Nie rób `killall cfprefsd` po `defaults import` — to odrzuca właśnie wykonany zapis.
- `norm_name()` żyje **wyłącznie** w `lib/python/inventory.py` i musi ignorować marker `🆕`, który toolkit sam dopisuje. Nie twórz lokalnych kopii.
