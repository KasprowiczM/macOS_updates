# Schnellstart (Deutsch)

**Mac mit Apple Silicon erforderlich** · macOS 13+ · **v1.6.3**

## Sicheres Setup und Anwendungsquellen

`bash setup.sh --inspect` prüft die Bereitschaft ohne Installation, Profiländerung oder Touch-ID-Konfiguration. Fehlende Werkzeuge machen nur die abhängige Funktion unverfügbar. Im Terminal zeigt `bash setup.sh --install-dependencies` optionale Abhängigkeiten und fragt vor jeder Installation; `bash setup.sh --configure-shell` zeigt eine getrennt zu bestätigende Profiländerung. Abgelehnte Abhängigkeiten blockieren unabhängige Funktionen nicht. Ohne Python muss dieses vor dem Inventar ausdrücklich installiert werden. Fehlendes oder veraltetes `mas` wird gemeldet und nicht automatisch installiert oder aktualisiert.

Der normale Bericht zeigt installierte Anwendungen. `bash scripts/report_update_coverage.sh --show-supported` zeigt zusätzlich fehlende Katalogeinträge. Dies ist noch kein Installationsmenü. Ein App-Store-Beleg für CapCut erhält den App-Store-Pfad auch ohne Cask. Ohne bestätigte Homebrew-Zuordnung wird eine Quellenwahl empfohlen, ohne Übernahme oder Installation. Vollständige Quellenauflösung und interaktive Auswahl folgen später.

## Einzeilige Installation

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Neuer Benutzer (nur GitHub)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh --inspect
bash build_inventory.sh
bash update_all.sh
```


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

Phase B (1.6.2) ergänzt ein optionales Beobachtungsinventar: `bash build_inventory.sh --shadow`. Lokale App- und Paketidentitäten, Quellenbelege und unvollständige Scans werden in privatem JSON gespeichert. `APPLICATIONS.md` und die Update-Ausführung bleiben unverändert. `--dry-run` verhindert das Speichern, `--json` liefert strukturierte Ergebnisse und wiederholtes `--root PFAD` legt Scanverzeichnisse fest. Konflikte bleiben Beobachtungen; Quellenauswahl und Ausführungsschutz folgen in Phase C.
