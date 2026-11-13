# Przewodnik użytkownika (Polski)

**Wersja:** 1.6.2 · **Apple Silicon, macOS 13+**

## Bezpieczny setup i źródła aplikacji

`bash setup.sh --inspect` sprawdza gotowość bez instalowania zależności, zmiany profilu powłoki i konfiguracji Touch ID. Brak narzędzia oznacza niedostępność zależnej funkcji. W terminalu `bash setup.sh --install-dependencies` pokazuje plan opcjonalnych zależności i pyta przed każdą instalacją; `bash setup.sh --configure-shell` osobno pokazuje zmianę profilu powłoki. Odrzucenie zależności nie blokuje niezależnych funkcji. Jeśli brak Pythona, zainstaluj go świadomie przed budowaniem inventory. Brakujący lub stary `mas` jest zgłaszany podczas aktualizacji, bez automatycznej instalacji lub aktualizacji narzędzia.

Zwykły raport aktualizacji pokazuje lokalne aplikacje. Katalog obsługiwanych, lecz nieobecnych aplikacji otwiera `bash scripts/report_update_coverage.sh --show-supported`. To katalog informacyjny, jeszcze nie menu instalacji. Receipt App Store dla CapCut zachowuje obsługę przez App Store również bez caska. Lokalna aplikacja bez potwierdzonej rejestracji Homebrew otrzymuje propozycję wyboru źródła, bez przejmowania lub instalacji. Pełny resolver i interaktywny wybór źródła należą do kolejnych etapów.

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

Etap B (1.6.2) dodaje opcjonalne inventory obserwacyjne: `bash build_inventory.sh --shadow`. Zapisuje lokalne tożsamości aplikacji i pakietów, dowody źródeł oraz niepełne skany w prywatnym JSON, bez zmiany `APPLICATIONS.md` ani sposobu wykonywania aktualizacji. Opcja `--dry-run` wyłącza zapis, `--json` zwraca wynik strukturalny, a powtarzalne `--root ŚCIEŻKA` wskazuje katalogi skanu. Konflikty pozostają obserwacjami; wybór źródła i guard wykonania należą do etapu C.
