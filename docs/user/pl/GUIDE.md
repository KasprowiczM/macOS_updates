# Przewodnik użytkownika (Polski)

**Wersja:** 1.7.2 · **Apple Silicon, macOS 13+**

## Bezpieczny setup i źródła aplikacji

`bash setup.sh --inspect` sprawdza gotowość bez instalowania zależności, zmiany profilu powłoki i konfiguracji Touch ID. Brak narzędzia oznacza niedostępność zależnej funkcji. W terminalu `bash setup.sh --install-dependencies` pokazuje plan opcjonalnych zależności i pyta przed każdą instalacją; `bash setup.sh --configure-shell` osobno pokazuje zmianę profilu powłoki. Odrzucenie zależności nie blokuje niezależnych funkcji. Jeśli brak Pythona, zainstaluj go świadomie przed budowaniem inventory. Brakujący lub stary `mas` jest zgłaszany podczas aktualizacji, bez automatycznej instalacji lub aktualizacji narzędzia.

To wersja źródłowa 1.7.2 na main, bez osobnego tagu wydania. Menedżer aktualizacji działa w określonym zakresie tylko dla zainstalowanych celów o wykrytym źródle i po nowej zgodzie. Ogólne adaptery natywne i producentów pozostają ręczne do czasu przygotowania sprawdzonych receptur. Opcjonalny katalog publiczny obejmuje 48 produktów i udostępnia sprawdzone oficjalne linki do ręcznego pobrania; nie ma zatwierdzonych automatycznych receptur pierwszej instalacji. Poniższa lista metod jest wykazem możliwości, nie upoważnieniem do ich wykonania. Zwykły raport aktualizacji obejmuje zainstalowane aplikacje. `bash scripts/report_update_coverage.sh --show-supported` pozostaje wykazem informacyjnym. Opcjonalne menu wyboru otwiera `bash setup.sh --catalog`; początkowo nic nie jest wybrane. Po podglądzie i ponownej zgodzie można ręcznie pobrać wybraną aplikację ze sprawdzonego oficjalnego linku. Zmiana źródła istniejącej aplikacji wymaga ręcznej migracji. Receipt App Store dla CapCut zachowuje źródło App Store. Lokalna aplikacja bez potwierdzonego przypisania Homebrew nie jest automatycznie przejmowana.

## Co robi ten zestaw

macOS Updates koordynuje aktualizacje na **Macach Apple Silicon z macOS 13+** w kolejności:

1. Prescan i inwentarz tego Maca
2. App Store (`sudo mas upgrade <app-id>` + osobny GUI Track 2 dla aplikacji iPad)
3. Najpierw istniejące natywne CLI, potem Node/Bun i zapasowe instalacje npm
4. Homebrew (formuły i caski; `--greedy` tylko dla casków zarejestrowanych jako `brew_cask`)
5. Zainstalowane aplikacje internetowe: bezpośrednie handlery, CLI lub wyzwalanie aktualizatora
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

Pokazuje stany: **verified direct**, **triggered-unverified**, **externally managed**, **manual** i **unknown**. Ciche uruchomienie nie jest dowodem zakończonej aktualizacji. Inkscape obsługuje Homebrew; UniFi/WiFiman/Picsart — App Store Track 2; Office — `msupdate`; Teams — własny updater z obserwowanym, weryfikowanym fallbackiem MAU `TEAMS21`. Obecnie żadna zarejestrowana aplikacja nie jest „manual”; IPMIView obsługuje App Store Track 2.

## Dodawanie aplikacji z internetu

1. Zainstaluj aplikację na Macu.
2. `bash build_inventory.sh`
3. `bash scripts/scaffold_internet_app.sh "Nazwa" silent_launch`
4. `bash run_tests.sh`

## Rozwiązywanie problemów

| Problem | Rozwiązanie |
|---------|-------------|
| Intel Mac | Nieobsługiwany |
| Zły katalog aplikacji | `bash build_inventory.sh` |
| Brak aktualizacji aplikacji | `bash scripts/report_update_coverage.sh` |
| Brak `APPLICATIONS.md` | `build_inventory.sh` lub `dev_sync/dev-sync-import.sh` (właściciel) |

Pełna lista: [../../agents/troubleshooting.md](../../agents/troubleshooting.md)

Etap C aktywuje lokalny inwentarz JSON i plan ze zgodami na konkretne działania. `bash update_all.sh --plan` oraz `--dry-run` pokazują ten sam podgląd bez zapisu. Zwykły przebieg interaktywny pyta raz o pokazane zakresy; `-y`, EOF i działanie bez terminala nie nadają nowych zgód. `--preferences` pozwala przejrzeć lub wyzerować wybory. Aktualizacje zachowują wykryte źródło i dokładną lokalizację; konflikt, zniknięcie aplikacji albo niepewne dane odraczają dany cel. `build_inventory.sh --migration --preview` zachowuje oryginalne bajty Markdown i notatki; akceptacja wymaga podania identyfikatora propozycji. Generyczne aktualizacje producenta pozostają ręczne do czasu weryfikacji tożsamości i adaptera. Dawny wpis katalogowy nie jest dowodem instalacji ani zgodą.


## Opcjonalny katalog i pierwsza instalacja

Nowe sygnały o aplikacjach są propozycjami do sprawdzenia, a nie recepturami instalacji. `bash scripts/scan_update_feeds.sh` wyświetla zbiorcze podsumowanie. Eksport propozycji umożliwia podgląd i jawne zatwierdzenie; jest zredagowany, pozostaje lokalnie i nigdy nie jest wysyłany. `bash setup.sh --catalog` otwiera katalog z pustym wyborem. `-y`, tryb bez interakcji i EOF niczego nie instalują. W menu `check <number>` porównuje tylko wybrane źródła. Wyniki pokazują najnowszą potwierdzoną zgodną wersję stabilną i jej datę, z pamięcią podręczną na 24 godziny. Nieznane pozostaje nieznane. Publiczna oferta w Mac App Store nie dowodzi dostępności aplikacji na koncie. Żaden kanał nie jest zawsze najszybszy.

Katalog publiczny obejmuje 47 wierszy rejestru i 48 osobnych produktów, a liczba zatwierdzonych automatycznych receptur pierwszej instalacji wynosi zero. Po podglądzie i ponownym jawnym potwierdzeniu można wybrać sprawdzone oficjalne linki do ręcznego pobrania. Otwarcie strony nie instaluje aplikacji. Zmiana źródła istniejącej aplikacji wymaga ręcznej migracji. Osobny InstallPlan pokazuje źródło, miejsce docelowe, wersję, wymagania i uprawnienia; nieznana licencja lub cena są tak oznaczane. Każda przyszła automatyczna receptura wymaga osobnej akceptacji pierwszej instalacji. Katalog nie obiecuje automatycznej instalacji wszystkich produktów.
