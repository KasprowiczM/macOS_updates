# Schnellstart (Deutsch)

**Mac mit Apple Silicon erforderlich** · macOS 13+ · **v1.0.20**

## Einzeilige Installation

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Neuer Benutzer (nur GitHub)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh
bash build_inventory.sh
bash update_all.sh
```

`setup.sh` installiert Homebrew, `mas` und Python bei Bedarf und wählt Ihre Sprache.

## Eigentümer (GitHub + Proton-Drive-Overlay)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

Private Dateien (`APPLICATIONS.md`, `UPDATES.md`, `.env`) stammen aus Ihrem Cloud-Overlay — nicht von GitHub.

## Nützliche Befehle

| Befehl | Zweck |
|--------|-------|
| `bash update_all.sh --dry-run -y` | Alle Schritte in der Vorschau |
| `bash update_system.sh` | Nur macOS |
| `bash update_appstore.sh` | Nur App Store |
| `bash update_brew.sh` | Nur Homebrew |
| `bash run_tests.sh` | Installation prüfen |

Siehe [GUIDE.md](GUIDE.md) und [OPERATIONS.md](OPERATIONS.md).
