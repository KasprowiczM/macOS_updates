# Ultra review produkcyjny — 2026-07-13

## Zakres i werdykt

Audyt objął orkiestrator `update_all.sh`, wszystkie warstwy aktualizacji, rejestr aplikacji i raport pokrycia, konfigurację pierwszego uruchomienia, prywatny overlay `dev_sync`, testy oraz aktywną dokumentację. Punktem odniesienia był najnowszy pełny log `update_all_20260713_100850.log`, analizowany bez kopiowania ścieżek użytkownika, prywatnego inwentarza ani historii aktualizacji do tego dokumentu.

Wersja 1.0.19 nie spełniała jeszcze rygoru produkcyjnego: kończyła się „na zielono” mimo błędu npm, zawyżała pewność dla updaterów uruchamianych w tle, miała niespójny rejestr aplikacji oraz wykonywała potencjalnie restartujący macOS jako pierwszy krok. Wersja 1.0.20 usuwa te klasy błędów i wprowadza fail-closed, rollback oraz jawne poziomy dowodu. Ostateczny release jest gotowy dopiero po spełnieniu bramek z sekcji „Kryteria produkcyjne”; sam status `triggered-unverified` nigdy nie jest dowodem aktualnej wersji aplikacji.

## Dowody z uruchomienia 2026-07-13

- Pełny przebieg trwał około 4 minut i 19 sekund i formalnie oznaczył wszystkie kroki jako poprawne, mimo że aktualizacja globalnych narzędzi npm zgłosiła błąd. To był krytyczny false green.
- 24 aplikacje miały jedynie uruchomiony wewnętrzny updater, sześć było klasyfikowanych jako ręczne, a około 15 używało bezpośredniej ścieżki lub narzędzia producenta. Stary raport nie odróżniał jakości dowodu.
- Siedem aktualizacji zakończyło się już po zamknięciu skryptu, więc snapshot wersji zapisany w tej samej sesji był chwilowo nieaktualny.
- Handler Proton Mail przez 15 kolejnych uruchomień odpytywał nieistniejące repozytorium GitHub i otrzymywał HTTP 404, ale wynik nie powodował uczciwego błędu metody.
- Agregat starego raportu wskazywał 45 zainstalowanych pozycji, dwie obsługiwane lecz nieobecne i 22 „unknown”. Wynik zawierał duplikaty, aliasy bundle oraz aplikacje zarządzane innymi warstwami, więc nie odzwierciedlał realnych luk.
- App Store Track 2 mógł przejść nieoczekiwaną gałąź AppleScript jako sukces; `mas outdated` nie potwierdza stanu aplikacji iPad na Apple Silicon.

## Walidacja końcowa 2026-07-14

- Produkcyjny przebieg `update_all.sh --yes --json-summary` zakończył wszystkie siedem kroków kodem 0 w 209 sekund. macOS 26.5.2 nie miał dostępnej aktualizacji.
- App Store GUI zaktualizował WhatsApp 26.26.73 → 26.27.73 i Whisper Transcription 13.23.1 → 13.24.2; końcowe `mas outdated --accurate` było puste. iPadowe ścieżki Track 2 odnotowały również aktualne Picsart 30.3.2 i UniFi 10.36.1.
- Homebrew zaktualizował `stripe` 1.43.7 → 1.43.8 i `tbb` 2023.0.0 → 2023.1.0. Końcowe `brew outdated --formula` oraz `brew outdated --cask --greedy` były puste. Jedynym surowym ostrzeżeniem `brew doctor` pozostał dokładnie `/usr/local/lib/libASAF.dylib`, filtrowany wyłącznie w tym wąskim przypadku.
- Natywna warstwa CLI zaktualizowała npm 12.0.0 → 12.0.1, pnpm 11.12.0 → 11.13.0 i OpenCode CLI 1.17.18 → 1.17.20. Node 26.5.0, Bun 1.3.14, Claude Code 2.1.207 i Codex CLI 0.144.3 przeszły kontrolę.
- Microsoft AutoUpdate zaoferował fallback `TEAMS21`, zainstalował go i zakończył czystym `msupdate --list`; Teams zmienił wersję na 26163.407.4839.8659.
- Końcowy raport obejmuje 66 unikalnych aplikacji: 15 `verified direct`, 24 `triggered-unverified`, 25 `externally managed`, 2 `manual`, 0 `unknown`. Znane pokrycie wynosi 100%, a konserwatywne pokrycie automatyczne 60,6%.
- ChatGPT Classic (`com.openai.chat`) został usunięty z `/Applications` do Kosza z zachowaniem danych. Aktywny ChatGPT/Codex ma bundle `com.openai.codex` i jest jedynym celem OpenAI o tej nazwie.

## Najważniejsze problemy i remediacje

| Priorytet | Problem | Remediacja w 1.0.20 |
|-----------|---------|---------------------|
| P0 | npm mógł zakończyć operację błędem, a cały krok zwracał kod 0 | Akumulator błędów, diagnostyka i niezerowy kod wyjścia; kontrolowana ścieżka natywnego Node/npm |
| P0 | `softwareupdate -R` działał przed pozostałymi warstwami i mógł zrestartować nieukończoną sesję | macOS jest krokiem końcowym; po wcześniejszym błędzie zostaje pominięty, a `-R` pozostaje obowiązkowe |
| P0 | Bezpośrednia podmiana `.app` usuwała starą aplikację przed pewnym sukcesem | Weryfikacja bundle ID i signing team, unikalny mountpoint DMG, staged swap, zachowana kopia i rollback po błędzie copy/Gatekeeper |
| P0 | Import rclone mógł kopiować całe zdalne drzewo bezpośrednio nad repozytorium | Fail-closed listing, allowlista bez plików śledzonych przez Git, staging pojedynczych ścieżek i transakcyjny commit z rollbackiem |
| P1 | App Store Track 2 oraz końcowe `mas outdated` mogły dawać false green | Track 1 i Track 2 mają osobne wyniki; nieoczekiwane stany GUI i nieudana weryfikacja zwracają błąd |
| P1 | Homebrew nie obejmował pewnie casków `auto_updates` i potrafił kontynuować po nieudanym sprawdzeniu | `brew outdated/upgrade --cask --greedy`, fail-closed weryfikacja końcowa, bez domyślnego ryzykownego link overwrite |
| P1 | Launch-only oznaczał pozorny sukces | Status `LAUNCHED_UNVERIFIED`; błąd uruchomienia jest błędem kroku, a potwierdzenie wersji pozostaje osobną czynnością |
| P1 | Rejestr zawierał duplikat OpenAI/Codex, nieistniejący handler Proton Mail i złe metody kilku aplikacji | Dopasowanie OpenAI po bundle ID, Proton Mail jako uczciwy updater wbudowany, aliasy/deduplikacja i skorygowana macierz metod |
| P1 | Inwentarz/historia i konfiguracja prywatna były zapisywane bez gwarancji atomowości | Same-directory temp, flush/fsync tam gdzie wymagane, `os.replace()`, konfiguracja prywatna `0600` |
| P1 | Setup/migracja mogły wyglądać na gotowe po niespełnionej kontroli | Centralna bramka Apple Silicon arm64 + macOS 13+, readiness fail-closed, bezpieczne tworzenie profilu shell |
| P2 | Test runner łapał ignorowane pliki robocze | Zakres ograniczony do śledzonego kodu/testów projektu |

## Docelowa kolejność pełnego przebiegu

1. Prescan: `/Applications` i `~/Applications`, Homebrew i App Store; atomowy inwentarz.
2. App Store: Track 1 przez `sudo mas upgrade`, niezależny Track 2 GUI dla aplikacji iPad.
3. Natywne Node/Bun i globalne CLI npm.
4. Homebrew: formuły oraz caski `--greedy`, cleanup i kontrola stanu.
5. Zainstalowane aplikacje internetowe: zweryfikowane handlery, CLI producentów lub jawne triggery.
6. Postupdate/historia: atomowe odświeżenie prywatnych plików.
7. macOS: `softwareupdate -ia -R --verbose` jako krok końcowy; automatycznie pomijany po wcześniejszym błędzie.

## Macierz pokrycia

| Stan raportu | Znaczenie | Przykłady docelowe | Obowiązek operatora |
|--------------|-----------|--------------------|---------------------|
| **verified direct** | Potwierdzona wersja/artefakt albo wynik CLI producenta | GitHub/Sparkle DMG z kontrolą wersji i podpisu, Google Keystone, Docker Desktop CLI, Office `msupdate` | Sprawdzić tylko ostrzeżenia lub błąd weryfikacji |
| **triggered-unverified** | Aplikacja została uruchomiona, ale skrypt nie może potwierdzić zakończenia jej updatera | Brave, Claude, Cursor, Warp, Proton Mail; Teams bez zaoferowanego fallbacku MAU | Po czasie sprawdzić ekran About/wersję; nie traktować startu jako sukcesu wersji |
| **externally managed** | Cykl aktualizacji należy do innej warstwy/producenta | Inkscape przez Homebrew cask; UniFi, WiFiman i Picsart przez App Store GUI Track 2 | Kontrolować wynik właściwej warstwy |
| **manual** | Nie istnieje bezpieczna i wspierana automatyzacja | IPMIView, DJI Assistant 2 | Zaktualizować ręcznie ze źródła producenta |
| **unknown** | Zainstalowana aplikacja nie pasuje do registry, aliasu ani znanego managera | Nowa lub nietypowo nazwana aplikacja | Zweryfikować pochodzenie i dodać bezpieczną metodę lub jawny manual |

Microsoft Teams normalnie korzysta z własnego cyklu aktualizacji. Oficjalna dokumentacja Microsoft wymienia jednak `TEAMS21` i wyjaśnia, że MAU może być fallbackiem, gdy updater Teams zawiedzie. Live-run 2026-07-14 wykrył, zainstalował i końcowym `msupdate --list` zweryfikował właśnie taki fallback (wersja Teams zmieniła się z 26072.608.4595.8484 na 26163.407.4839.8659). Registry pozostaje konserwatywne: bez zaoferowanego `TEAMS21` Teams nadal ma status `triggered-unverified`.

## Ograniczenia, których nie należy ukrywać

- AppleScript GUI zależy od wersji interfejsu App Store, uprawnienia Accessibility i aktywnej sesji użytkownika. Dla aplikacji iPad nie istnieje równoważna, w pełni obserwowalna ścieżka `mas`.
- Wbudowane aktualizatory Electron/Sparkle/Squirrel mogą kończyć pracę po zamknięciu `update_all.sh`. Potrzebny jest późniejszy skan, aby udowodnić zmianę wersji.
- Ręczne IPMIView i DJI Assistant 2 pozostają świadomymi lukami, nie błędami „unknown”. Nie wolno pobierać nieoficjalnych instalatorów w celu sztucznego osiągnięcia 100% automatyzacji.
- `softwareupdate -R` może przejąć restart i nie zwrócić sterowania. Historia zachowuje wtedy stan oczekujący zamiast fałszywego „completed”.
- `brew doctor` może raportować pliki pozostawione przez oprogramowanie producentów. Ostrzeżenie wymaga oceny; projekt nie usuwa obcych plików automatycznie.

## Kryteria produkcyjne

- [x] `/bin/bash -n` przechodzi dla wszystkich skryptów i nie ma funkcji Bash 4+.
- [x] `bash run_tests.sh` przechodzi w całości, łącznie z rollbackiem importu, uprawnieniami prywatnych logów i parytetem registry (77 testów).
- [x] Shellcheck oraz gitleaks przechodzą tymi samymi komendami co CI.
- [x] `bash update_all.sh --dry-run --yes --json-summary` nie wykonuje mutacji i pokazuje nową kolejność.
- [x] Test wykonawczy na Apple Silicon/macOS 13+ zwraca niezerowy kod po zasymulowanym błędzie npm/App Store/Homebrew/internet i pomija macOS.
- [x] Pełny udany przebieg kończy się kontrolą `mas outdated`, `brew outdated --cask --greedy`, `softwareupdate -l`, przebudową inwentarza i ponownym raportem pokrycia.
- [x] Raport nie zawiera duplikatów aliasów, aplikacji systemowych ani ogólnych pozycji już zarządzanych przez Homebrew/App Store.
- [x] Prywatne `APPLICATIONS.md`, `UPDATES.md`, `.env`, `.dev_sync_config.json` i `logs/` są ignorowane i nie trafiają do commita ani logu publicznego.
- [x] Commit wersji 1.0.20 i push są zweryfikowane względem zdalnego `main`.

## Oficjalne źródła

- [Homebrew Manpage — `outdated`, `upgrade`, `--greedy`](https://docs.brew.sh/Manpage)
- [mas README — `outdated`, `upgrade`/`update` i ograniczenia App Store](https://github.com/mas-cli/mas)
- [Microsoft Learn — Update Office for Mac by using msupdate](https://learn.microsoft.com/en-us/microsoft-365-apps/mac/update-office-for-mac-using-msupdate)
- [mas issue #128 — non-interactive update can hang](https://github.com/mas-cli/mas/issues/128)
- [Docker Docs — Docker Desktop CLI, w tym `docker desktop update`](https://docs.docker.com/desktop/features/desktop-cli/)
- [Apple Platform Deployment — Manage macOS software updates](https://support.apple.com/guide/deployment/manage-macos-updates-depafd2fad80/web)
- Lokalna dokumentacja systemowa: `man softwareupdate` na wspieranym Macu; instalacja zachowuje `-R`, aby framework aktualizacji mógł poprawnie zastosować pakiet wymagający restartu.
