# Przewodnik użytkownika (Polski)

**Wersja:** 1.8.0 · **Apple Silicon, macOS 13+**

## Środowisko terminalowe

W interaktywnym terminalu `bash update_all.sh` otwiera panel i pokazuje kreator pierwszego uruchomienia do czasu jego ukończenia. `bash setup.sh` otwiera kreator, a `bash build_inventory.sh` widok inwentarza. Kreator można ponownie otworzyć z nawigacji. Ukończenie i ustawienia wyglądu są zapisywane; nie udzielają zgody na aktualizacje. `--cli` wybiera dotychczasowy tryb tekstowy, a `--tui` jawnie otwiera panel. Opcje takie jak `--dry-run` pozostają w CLI; nie łącz `--tui` z innymi opcjami. Jawny `--tui` wymaga sprawnego terminala i Pythona. Uruchomienia bez terminala i nieinteraktywne zachowują tryb CLI.

Przed uruchomieniem wybierz grupy aktualizacji. Po lewej jest nawigacja, w środku działania i bieżące wyjście, a po prawej szczegóły, gdy pozwala na to miejsce. Jednocześnie działa jedno nadzorowane zadanie; dotychczasowe zgody nadal obowiązują. Ustawienia obejmują język, motyw, ASCII i automatyczny rozmiar. `?` otwiera pomoc, Ctrl+P paletę działań, a `c` kopiuje aktywne polecenie, wyjście lub podsumowanie. Ctrl+V wkleja tylko do okna odpowiedzi; Enter wysyła odpowiedź. Dane są maskowane, gdy proces wyłącza echo.

Panel wymaga co najmniej 80 kolumn i 24 wierszy. Domyślnie na obsługiwanych terminalach prosi o co najmniej 140 kolumn i 38 wierszy oraz o poprzedni rozmiar przy wyjściu; terminal może zignorować te prośby. Automatyczny rozmiar można wyłączyć w ustawieniach.

## Bezpieczny setup i źródła aplikacji

`bash setup.sh --inspect` sprawdza gotowość bez instalowania zależności, zmiany profilu powłoki i konfiguracji Touch ID. Brak narzędzia oznacza niedostępność zależnej funkcji. W terminalu `bash setup.sh --install-dependencies` pokazuje plan opcjonalnych zależności i pyta przed każdą instalacją; `bash setup.sh --configure-shell` osobno pokazuje zmianę profilu powłoki. Odrzucenie zależności nie blokuje niezależnych funkcji. Jeśli brak Pythona, zainstaluj go świadomie przed budowaniem inventory. Brakujący lub stary `mas` jest zgłaszany podczas aktualizacji, bez automatycznej instalacji lub aktualizacji narzędzia.


## Co robi ten zestaw

macOS Updates koordynuje aktualizacje na **Macach Apple Silicon z macOS 13+** w kolejności:

1. Prescan i inwentarz tego Maca
2. App Store (`sudo mas upgrade <app-id>` + osobny GUI Track 2 dla aplikacji iPad)
3. Najpierw istniejące natywne CLI, potem Node/Bun i zapasowe instalacje npm
4. Homebrew (formuły i caski; `--greedy` tylko dla casków zarejestrowanych jako `brew_cask`)
5. Zainstalowane aplikacje: zakresowe działania po zgodzie; niezaakceptowane aktualizacje producentów pozostają ręczne
6. Atomowy postupdate inwentarza i historii
7. macOS (`softwareupdate -i <label> -R`) na końcu; odraczany po blokującym błędzie lub bez autoryzacji

**Nie instaluje nowych aplikacji.** Każdy Mac buduje własny katalog (`build_inventory.sh` lub prescan w `update_all.sh`).

## Instalacja

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Raport pokrycia

```bash
bash scripts/report_update_coverage.sh
```


## Dodawanie aplikacji z internetu

1. Zainstaluj aplikację na Macu.
2. `bash build_inventory.sh --cli`
3. `bash scripts/scaffold_internet_app.sh "/path/to/Observed.app" --json`
4. Przejrzyj niewykonywalną propozycję JSON; późniejsza implementacja wymaga przeglądu i `bash run_tests.sh`.

Zastąp przykład dokładną ścieżką zainstalowanej aplikacji. Polecenie pokazuje zredagowaną, niewykonywalną propozycję do przeglądu. Opcjonalny eksport wymaga ponowienia go z `--export --accept PREVIEW_ID` po sprawdzeniu wyświetlonego identyfikatora podglądu. Włączenie aktualizacji wymaga przeglądu implementacji i osobnych dowodów akceptacji.

## Rozwiązywanie problemów

| Problem | Rozwiązanie |
|---------|-------------|
| Intel Mac | Nieobsługiwany |
| Zły katalog aplikacji | `bash build_inventory.sh --cli` |
| Brak aktualizacji aplikacji | `bash scripts/report_update_coverage.sh` |
| Brak `APPLICATIONS.md` | `build_inventory.sh` lub `dev_sync/dev-sync-import.sh` (właściciel) |

Pełna lista: [../../agents/troubleshooting.md](../../agents/troubleshooting.md)

Lokalny inwentarz JSON i zakresowy plan działań są dostępne. `bash update_all.sh --plan` oraz `--dry-run` pokazują ten sam podgląd bez zapisu. Zwykły przebieg interaktywny pyta raz o pokazane zakresy; `-y`, EOF i działanie bez terminala nie nadają nowych zgód. `--preferences` pozwala przejrzeć lub wyzerować wybory. Aktualizacje zachowują wykryte źródło i dokładną lokalizację; konflikt, zniknięcie aplikacji albo niepewne dane odraczają dany cel. `build_inventory.sh --migration --preview` zachowuje oryginalne bajty Markdown i notatki; akceptacja wymaga podania identyfikatora propozycji. Generyczne aktualizacje producenta pozostają ręczne do czasu weryfikacji tożsamości i adaptera. Dawny wpis katalogowy nie jest dowodem instalacji ani zgodą.


## Opcjonalny katalog i pierwsza instalacja

Nowe sygnały o aplikacjach są propozycjami do sprawdzenia, a nie recepturami instalacji. `bash scripts/scan_update_feeds.sh` wyświetla zbiorcze podsumowanie. Eksport propozycji umożliwia podgląd i jawne zatwierdzenie; jest zredagowany, pozostaje lokalnie i nigdy nie jest wysyłany. `bash setup.sh --catalog` otwiera katalog z pustym wyborem. `-y`, tryb bez interakcji i EOF niczego nie instalują. W menu `check <number>` porównuje tylko wybrane źródła. Wyniki pokazują najnowszą potwierdzoną zgodną wersję stabilną i jej datę, z pamięcią podręczną na 24 godziny. Nieznane pozostaje nieznane. Publiczna oferta w Mac App Store nie dowodzi dostępności aplikacji na koncie. Żaden kanał nie jest zawsze najszybszy.

Katalog publiczny obejmuje 47 wierszy rejestru i 48 osobnych produktów, a liczba zatwierdzonych automatycznych receptur pierwszej instalacji wynosi zero. Po podglądzie i ponownym jawnym potwierdzeniu można wybrać sprawdzone oficjalne linki do ręcznego pobrania. Otwarcie strony nie instaluje aplikacji. Zmiana źródła istniejącej aplikacji wymaga ręcznej migracji. Osobny InstallPlan pokazuje źródło, miejsce docelowe, wersję, wymagania i uprawnienia; nieznana licencja lub cena są tak oznaczane. Każda przyszła automatyczna receptura wymaga osobnej akceptacji pierwszej instalacji. Katalog nie obiecuje automatycznej instalacji wszystkich produktów.

## Lokalny status receptur aktualizacji

Przewodnik dotyczy macOS Updates 1.8.0. Publiczny katalog obejmuje 48 produktów w 47 wierszach rejestru i ma zero zatwierdzonych automatycznych receptur producentów, natywnych i pierwszej instalacji. Menedżer obsługuje zakresowe działania na zainstalowanych celach po zgodzie; niezaakceptowane aktualizacje producentów pozostają ręczne. 48 dossier i syntetyczne fixtures nie oznaczają akceptacji na żywo. Bezpośrednie pobieranie ZIP, jawna instalacja i silnik natywny są zaimplementowane; testy na osobnym Macu w T6 i aktywacja T7 pozostają do wykonania. Brak ścieżki force, adopt, migracji i bootstrapu zależności. Istniejące aplikacje użytkownika są chronione. Rekomendacje dotyczą najnowszej wersji stable konkretnego produktu. Żaden kanał nie jest zawsze najszybszy. Niepełny skan dostawcy jest ostrzeżeniem, ale niebezpieczne cele są blokowane; sprawdź źródła w JSON. Metadane Cask hosta nie są naprawiane. Scheduler dopuszcza najwyżej dwie niezależne mutacje w checkoutach tego samego użytkownika systemu; publiczne wykonanie pozostaje sekwencyjne do akceptacji niezależnych efektów. Aktualizacja systemu pobiera wyłączną blokadę globalną na końcu. Oczekujący restart lub nieznany helper może blokować mutacje do nowego, sprawdzonego dowodu uzgodnienia. Blokada nie wygasa po czasie. Automatyczne uzgadnianie stanu przy starcie nie jest jeszcze dostępne. Zobacz [centralny zapis implementacji](../../implementation/RECIPE_VERIFICATION_2026-11-14.md). Otwarte aplikacje pozostają chronione. DeepSeek Harness jest wykluczony do czasu stabilności.

Zwykły `--dry-run` pokazuje czytelny podgląd maksymalnie 10 celów. Pełny plan JSON jest dostępny przez `--dry-run --json-summary` lub `--plan`. Podgląd nie nadaje zgody i nie wykonuje aktualizacji.

Ekran zgód pokazuje dziesięć możliwych do zatwierdzenia pozycji na stronę. Wpisz np. `1,3`, aby zatwierdzić tylko pokazane działania tych pozycji; `n` i `p` zmieniają stronę. Enter lub `q` kontynuuje bez nowych zgód. Ekran wyjaśnia limit 120 sekund na odpowiedź; upływ czasu nie oznacza zgody. Zablokowane pozycje mają osobne podsumowanie. Ręczne, ignorowane i odroczone wybory przejrzysz przez `--preferences`. Logowanie zaczyna się przed tym przeglądem.
