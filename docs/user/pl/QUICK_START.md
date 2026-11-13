# Szybki start (Polski)

**Wymagany Mac z Apple Silicon** · macOS 13+ · **v1.6.4**

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
bash build_inventory.sh
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
