# Podręcznik operacyjny

Przewodnik dla operatora — codzienna i tygodniowa obsługa macOS Updates.

## Platforma

**Tylko Apple Silicon (arm64).** Skrypty kończą działanie natychmiast na Macach z procesorem Intel.

## Tygodniowa aktualizacja

```bash
cd ~/Dev_Env/macOS_updates
bash update_all.sh
```

W razie błędu sprawdź: `logs/update_all_<timestamp>.log` (zachowywane są ostatnie 30 uruchomień).

## Kolejność potoku (`update_all.sh`)

| Krok | Skrypt / akcja | Flaga pominięcia |
|------|----------------|------------------|
| 0 | prescan → `APPLICATIONS.md` | `--skip-prescan` |
| 1 | `update_system.sh` | `--skip-system` |
| 2 | `update_appstore.sh` | `--skip-appstore` |
| 3 | `update_npm_cli.sh` | `--skip-npm` |
| 4 | `update_brew.sh` | `--skip-brew` |
| 5 | `update_internet_apps.sh` | `--skip-internet` |
| 6 | postupdate → `APPLICATIONS.md`, `UPDATES.md` | `--skip-postupdate` |

Podgląd bez zmian: `bash update_all.sh --dry-run -y`

## Diagnostyka awarii

| Nieudany krok | Sprawdź te pliki |
|---------------|------------------|
| App Store | `$SESSION_DIR/appstore_diag.txt`, migawka z logu |
| Aplikacje z internetu | `$SESSION_DIR/internet_diag.txt`, `internet_before/after.txt` |
| Homebrew | `$SESSION_DIR/brew_*_before/after.txt` |
| Dowolny | `logs/update_all_*.log` (migawki dołączane przy kodzie wyjścia ≠ 0) |

Brak Ułatwień dostępu dla App Store → kod wyjścia `2`; użyj `--treat-appstore-ax-as-warning` lub przyznaj Ułatwienia dostępu terminalowi.

Pełna lista kodów wyjścia: `docs/agents/exit_codes.md`.

## Prywatna nakładka (Proton Drive)

Po lokalnej edycji plików prywatnych:

```bash
bash dev_sync/dev-sync-export.sh
bash dev_sync/dev-sync-verify-full.sh
bash dev_sync/dev-sync-prune-excluded.sh   # should report zero candidates
```

## Nowy Mac

**Użytkownik publiczny:**

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
bash update_all.sh
```

**Właściciel (nakładka w chmurze):**

```bash
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

Inwentarz zawsze z tego Maca: `bash build_inventory.sh`

## Lista kontrolna przed aktualizacją

- [ ] Zalogowanie w App Store (`mas account` lub aplikacja App Store)
- [ ] Terminal ma Ułatwienia dostępu (dla ścieżki 2 aplikacji iPad)
- [ ] Wolne miejsce na dysku ≥ 20 GB na duże aktualizacje macOS
- [ ] Dostępne `sudo` dla `mas upgrade` i aktualizacji systemu

## Weryfikacja po aktualizacji

```bash
mas outdated
brew outdated
softwareupdate -l
```

Uruchom próbnie kluczowe aplikacje (przeglądarka, VPN, IDE), jeśli krok internetowy zgłosił ostrzeżenia.
