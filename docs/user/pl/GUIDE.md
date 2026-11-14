# Przewodnik użytkownika (Polski)

**Wersja:** 1.7.5 · **Apple Silicon, macOS 13+**

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

Lokalny inwentarz JSON i zakresowy plan działań są dostępne. `bash update_all.sh --plan` oraz `--dry-run` pokazują ten sam podgląd bez zapisu. Zwykły przebieg interaktywny pyta raz o pokazane zakresy; `-y`, EOF i działanie bez terminala nie nadają nowych zgód. `--preferences` pozwala przejrzeć lub wyzerować wybory. Aktualizacje zachowują wykryte źródło i dokładną lokalizację; konflikt, zniknięcie aplikacji albo niepewne dane odraczają dany cel. `build_inventory.sh --migration --preview` zachowuje oryginalne bajty Markdown i notatki; akceptacja wymaga podania identyfikatora propozycji. Generyczne aktualizacje producenta pozostają ręczne do czasu weryfikacji tożsamości i adaptera. Dawny wpis katalogowy nie jest dowodem instalacji ani zgodą.


## Opcjonalny katalog i pierwsza instalacja

Nowe sygnały o aplikacjach są propozycjami do sprawdzenia, a nie recepturami instalacji. `bash scripts/scan_update_feeds.sh` wyświetla zbiorcze podsumowanie. Eksport propozycji umożliwia podgląd i jawne zatwierdzenie; jest zredagowany, pozostaje lokalnie i nigdy nie jest wysyłany. `bash setup.sh --catalog` otwiera katalog z pustym wyborem. `-y`, tryb bez interakcji i EOF niczego nie instalują. W menu `check <number>` porównuje tylko wybrane źródła. Wyniki pokazują najnowszą potwierdzoną zgodną wersję stabilną i jej datę, z pamięcią podręczną na 24 godziny. Nieznane pozostaje nieznane. Publiczna oferta w Mac App Store nie dowodzi dostępności aplikacji na koncie. Żaden kanał nie jest zawsze najszybszy.

Katalog publiczny obejmuje 47 wierszy rejestru i 48 osobnych produktów, a liczba zatwierdzonych automatycznych receptur pierwszej instalacji wynosi zero. Po podglądzie i ponownym jawnym potwierdzeniu można wybrać sprawdzone oficjalne linki do ręcznego pobrania. Otwarcie strony nie instaluje aplikacji. Zmiana źródła istniejącej aplikacji wymaga ręcznej migracji. Osobny InstallPlan pokazuje źródło, miejsce docelowe, wersję, wymagania i uprawnienia; nieznana licencja lub cena są tak oznaczane. Każda przyszła automatyczna receptura wymaga osobnej akceptacji pierwszej instalacji. Katalog nie obiecuje automatycznej instalacji wszystkich produktów.

## Lokalny status receptur aktualizacji

To lokalny checkpoint źródła, nieopublikowany i nieotagowany. Publiczny katalog obejmuje 48 produktów w 47 wierszach rejestru i ma zero zatwierdzonych automatycznych receptur producentów, natywnych i pierwszej instalacji. Menedżer obsługuje zakresowe działania na zainstalowanych celach po zgodzie; niezaakceptowane aktualizacje producentów pozostają ręczne. 48 dossier i syntetyczne fixtures nie oznaczają akceptacji na żywo. Bezpośrednie pobieranie ZIP, jawna instalacja i silnik natywny są zaimplementowane; akceptacja na żywo T6 i aktywacja T7 pozostają w toku. Brak ścieżki force, adopt, migracji i bootstrapu zależności. Istniejące aplikacje użytkownika są chronione. Rekomendacje są stabilne dla pojedynczego produktu, bez rankingu najszybszego kanału. Niepełny skan dostawcy jest ostrzeżeniem, ale niebezpieczne cele są blokowane; sprawdź źródła w JSON. Metadane Cask hosta nie są naprawiane. Scheduler dopuszcza najwyżej dwie niezależne mutacje w checkoutach tego samego użytkownika systemu; publiczne wykonanie pozostaje sekwencyjne do akceptacji niezależnych efektów. Aktualizacja systemu pobiera wyłączną blokadę globalną na końcu. Oczekujący restart lub nieznany helper może blokować mutacje do nowego, sprawdzonego dowodu uzgodnienia. Brak automatycznego timeoutu i uzgadniania przy starcie. Zobacz [centralny zapis implementacji](../../implementation/RECIPE_VERIFICATION_2026-11-14.md). Otwarte aplikacje pozostają chronione. DeepSeek Harness jest wykluczony do czasu stabilności.
