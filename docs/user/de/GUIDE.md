# Benutzerhandbuch (Deutsch)

**Version:** 1.0.20 · **Apple Silicon, macOS 13+**

## Funktion

macOS Updates orchestriert Updates auf **Apple-Silicon-Macs mit macOS 13+**:

1. Vorab-Scan und Inventar
2. App Store (`sudo mas upgrade` + separater GUI Track 2)
3. Node/Bun und globale npm-CLIs
4. Homebrew (`--greedy`)
5. Installierte Internet-Apps: direkte Handler, CLIs oder Update-Auslöser
6. Atomarer Post-Update-Verlauf
7. macOS (`softwareupdate -ia -R`) zuletzt; entfällt nach einem früheren Fehler

**Installiert keine neuen Apps.** Jeder Mac erstellt zuerst sein eigenes Inventar (`build_inventory.sh`).

## Installation

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Abdeckungsbericht

```bash
bash scripts/report_update_coverage.sh
```

Status: **verified direct**, **triggered-unverified**, **externally managed**, **manual**, **unknown**. Ein stiller Start beweist kein fertiges Update. Inkscape nutzt Homebrew; UniFi/WiFiman/Picsart Track 2; Office `msupdate`; Teams den eigenen Updater mit beobachtetem, verifiziertem MAU-Fallback `TEAMS21`. Nur IPMIView und DJI Assistant 2 bleiben manuell.

## Internet-App hinzufügen

1. App auf dem Mac installieren.
2. `bash build_inventory.sh`
3. `bash scripts/scaffold_internet_app.sh "App Name" silent_launch`
4. `bash run_tests.sh`

## Fehlerbehebung

| Problem | Lösung |
|---------|--------|
| Intel Mac | Nicht unterstützt |
| Falsches App-Inventar | `bash build_inventory.sh` |
| App wird nicht aktualisiert | `bash scripts/report_update_coverage.sh` |
| `APPLICATIONS.md` fehlt | `build_inventory.sh` oder `dev_sync/dev-sync-import.sh` |

Vollständig: [../../agents/troubleshooting.md](../../agents/troubleshooting.md)
