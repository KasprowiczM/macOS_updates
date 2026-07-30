# Szybki start (Polski)

**Wymagany Mac z Apple Silicon** · macOS 13+ · **v1.0.21**

## Instalacja jedną linią

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Nowy użytkownik (tylko GitHub)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh
bash build_inventory.sh
bash update_all.sh
```

`setup.sh` instaluje Homebrew, `mas` i Pythona, jeśli ich brakuje, oraz pozwala wybrać język interfejsu.

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
