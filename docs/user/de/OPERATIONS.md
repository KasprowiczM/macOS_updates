# Betriebshandbuch

Leitfaden für den Operator — tägliche und wöchentliche Wartung des macOS Updates.

## Plattform

**Nur Apple Silicon (arm64), macOS 13+.** Skripte beenden sich vor Änderungen auf nicht unterstützten Macs.

## Wöchentliche Aktualisierung

```bash
cd ~/Dev_Env/macOS_updates
bash update_all.sh
```

Bei Fehlern prüfen: `logs/update_all_<timestamp>.log` (die letzten 30 Läufe werden aufbewahrt).

## Pipeline-Reihenfolge (`update_all.sh`)

| Schritt | Skript / Aktion | Überspringen-Flag |
|---------|-----------------|-------------------|
| 0 | prescan → `APPLICATIONS.md` | `--skip-prescan` |
| 1 | `update_appstore.sh` | `--skip-appstore` |
| 2 | `update_npm_cli.sh` | `--skip-npm` |
| 3 | `update_brew.sh` | `--skip-brew` |
| 4 | `update_internet_apps.sh` | `--skip-internet` |
| 5 | Post-Update/Verlauf → `APPLICATIONS.md`, `UPDATES.md` | `--skip-postupdate` |
| 6 | `update_system.sh` (`softwareupdate -ia -R`) | `--skip-system` |

Schritt 6 läuft wegen eines möglichen Neustarts zuletzt und wird nach einem früheren Fehler automatisch übersprungen.

Vorschau ohne Änderungen: `bash update_all.sh --dry-run -y`

## Fehleranalyse

| Fehlgeschlagener Schritt | Diese Dateien prüfen |
|--------------------------|----------------------|
| App Store | `$SESSION_DIR/appstore_diag.txt`, Log-Snapshot |
| Internet-Apps | `$SESSION_DIR/internet_diag.txt`, `internet_before/after.txt` |
| Homebrew | `$SESSION_DIR/brew_*_before/after.txt` |
| Beliebig | `logs/update_all_*.log` (Snapshots bei Exit-Code ≠ 0 angehängt) |

Fehlende Bedienungshilfen für App Store → Exit-Code `2`; `--treat-appstore-ax-as-warning` verwenden oder Bedienungshilfen für das Terminal gewähren.

Vollständige Exit-Code-Referenz: `docs/agents/exit_codes.md`.

## Privates Overlay (Proton Drive)

Nach lokaler Bearbeitung privater Dateien:

```bash
bash dev_sync/dev-sync-export.sh
bash dev_sync/dev-sync-verify-full.sh
bash dev_sync/dev-sync-prune-excluded.sh   # should report zero candidates
```

## Neuer Mac

**Öffentlicher Nutzer:**

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
bash update_all.sh
```

**Eigentümer (Cloud-Overlay):**

```bash
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

Inventar: `bash build_inventory.sh`

## Checkliste vor der Aktualisierung

- [ ] In App Store angemeldet (`mas account` oder App-Store-App)
- [ ] Terminal hat Bedienungshilfen (für iPad-App-Pfad 2)
- [ ] ≥ 20 GB freier Speicher für große macOS-Updates
- [ ] `sudo` verfügbar für `mas upgrade` und Systemaktualisierungen

## Verifikation nach der Aktualisierung

```bash
mas outdated
brew outdated
softwareupdate -l
```

Kritische Apps (Browser, VPN, IDE) testweise starten, wenn der Internet-Schritt Warnungen meldete.
