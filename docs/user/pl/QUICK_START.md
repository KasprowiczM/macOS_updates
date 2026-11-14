# Szybki start (Polski)

**Wymagany Mac z Apple Silicon** · macOS 13+ · **v1.8.0**

## Środowisko terminalowe

W interaktywnym terminalu `bash update_all.sh` otwiera panel i pokazuje kreator pierwszego uruchomienia do czasu jego ukończenia. `bash setup.sh` otwiera kreator, a `bash build_inventory.sh` widok inwentarza. Kreator można ponownie otworzyć z nawigacji. Ukończenie i ustawienia wyglądu są zapisywane; nie udzielają zgody na aktualizacje. `--cli` wybiera dotychczasowy tryb tekstowy, a `--tui` jawnie otwiera panel. Opcje takie jak `--dry-run` pozostają w CLI; nie łącz `--tui` z innymi opcjami. Jawny `--tui` wymaga sprawnego terminala i Pythona. Uruchomienia bez terminala i nieinteraktywne zachowują tryb CLI.

Przed uruchomieniem wybierz grupy aktualizacji. Po lewej jest nawigacja, w środku działania i bieżące wyjście, a po prawej szczegóły, gdy pozwala na to miejsce. Jednocześnie działa jedno nadzorowane zadanie; dotychczasowe zgody nadal obowiązują. Ustawienia obejmują język, motyw, ASCII i automatyczny rozmiar. `?` otwiera pomoc, Ctrl+P paletę działań, a `c` kopiuje aktywne polecenie, wyjście lub podsumowanie. Ctrl+V wkleja tylko do okna odpowiedzi; Enter wysyła odpowiedź. Dane są maskowane, gdy proces wyłącza echo.

Panel wymaga co najmniej 80 kolumn i 24 wierszy. Domyślnie na obsługiwanych terminalach prosi o co najmniej 140 kolumn i 38 wierszy oraz o poprzedni rozmiar przy wyjściu; terminal może zignorować te prośby. Automatyczny rozmiar można wyłączyć w ustawieniach.

## Bezpieczny setup i źródła aplikacji

`bash setup.sh --inspect` sprawdza gotowość bez instalowania zależności, zmiany profilu powłoki i konfiguracji Touch ID. Brak narzędzia oznacza niedostępność zależnej funkcji. W terminalu `bash setup.sh --install-dependencies` pokazuje plan opcjonalnych zależności i pyta przed każdą instalacją; `bash setup.sh --configure-shell` osobno pokazuje zmianę profilu powłoki. Odrzucenie zależności nie blokuje niezależnych funkcji. Jeśli brak Pythona, zainstaluj go świadomie przed budowaniem inventory. Brakujący lub stary `mas` jest zgłaszany podczas aktualizacji, bez automatycznej instalacji lub aktualizacji narzędzia.

Zwykły raport aktualizacji pokazuje lokalne aplikacje. Katalog obsługiwanych, lecz nieobecnych aplikacji otwiera `bash scripts/report_update_coverage.sh --show-supported`. To katalog informacyjny, jeszcze nie menu instalacji. Receipt App Store dla CapCut zachowuje obsługę przez App Store również bez caska. Lokalna aplikacja bez potwierdzonej rejestracji Homebrew otrzymuje propozycję wyboru źródła, bez przejmowania lub instalacji. Pełny resolver i interaktywny wybór źródła należą do kolejnych etapów.

## Instalacja jedną linią

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Nowy użytkownik (tylko GitHub)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh --inspect
bash build_inventory.sh --cli
bash update_all.sh
```


## Właściciel (GitHub + nakładka Proton Drive)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

Pliki prywatne (`APPLICATIONS.md`, `UPDATES.md`, `.env`) pochodzą z nakładki w chmurze — nie z GitHub.

## Przydatne polecenia

| Polecenie | Cel |
|-----------|-----|
| `bash update_all.sh --dry-run -y` | Podgląd wszystkich kroków |
| `bash update_system.sh` | Tylko macOS |
| `bash update_appstore.sh` | Tylko App Store |
| `bash update_brew.sh` | Tylko Homebrew |
| `bash run_tests.sh` | Weryfikacja instalacji |

Zobacz [GUIDE.md](GUIDE.md) i [OPERATIONS.md](OPERATIONS.md).

Etap B (1.6.2) dodaje opcjonalne inventory obserwacyjne: `bash build_inventory.sh --shadow`. Zapisuje lokalne tożsamości aplikacji i pakietów, dowody źródeł oraz niepełne skany w prywatnym JSON, bez zmiany `APPLICATIONS.md` ani sposobu wykonywania aktualizacji. Opcja `--dry-run` wyłącza zapis, `--json` zwraca wynik strukturalny, a powtarzalne `--root ŚCIEŻKA` wskazuje katalogi skanu. Konflikty pozostają obserwacjami; wybór źródła i guard wykonania należą do etapu C.
