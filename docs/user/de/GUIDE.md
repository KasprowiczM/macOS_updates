# Benutzerhandbuch (Deutsch)

**Version:** 1.6.3 · **Apple Silicon, macOS 13+**

## Sicheres Setup und Anwendungsquellen

`bash setup.sh --inspect` prüft die Bereitschaft ohne Installation, Profiländerung oder Touch-ID-Konfiguration. Fehlende Werkzeuge machen nur die abhängige Funktion unverfügbar. Im Terminal zeigt `bash setup.sh --install-dependencies` optionale Abhängigkeiten und fragt vor jeder Installation; `bash setup.sh --configure-shell` zeigt eine getrennt zu bestätigende Profiländerung. Abgelehnte Abhängigkeiten blockieren unabhängige Funktionen nicht. Ohne Python muss dieses vor dem Inventar ausdrücklich installiert werden. Fehlendes oder veraltetes `mas` wird gemeldet und nicht automatisch installiert oder aktualisiert.

Der normale Bericht zeigt installierte Anwendungen. `bash scripts/report_update_coverage.sh --show-supported` zeigt zusätzlich fehlende Katalogeinträge. Dies ist noch kein Installationsmenü. Ein App-Store-Beleg für CapCut erhält den App-Store-Pfad auch ohne Cask. Ohne bestätigte Homebrew-Zuordnung wird eine Quellenwahl empfohlen, ohne Übernahme oder Installation. Vollständige Quellenauflösung und interaktive Auswahl folgen später.

## Funktion

macOS Updates orchestriert Updates auf **Apple-Silicon-Macs mit macOS 13+**:

1. Vorab-Scan und Inventar
2. App Store (`sudo mas upgrade <app-id>` + separater GUI Track 2)
3. Bestehende native CLIs zuerst, danach Node/Bun und npm-Fallbacks
4. Homebrew (greedy nur für als `brew_cask` registrierte Casks)
5. Installierte Internet-Apps: direkte Handler, CLIs oder Update-Auslöser
6. Atomarer Post-Update-Verlauf
7. macOS (`softwareupdate -i <label> -R`) zuletzt; bei blockierenden Fehlern oder fehlender Autorisierung verschoben

**Installiert keine neuen Apps.** Jeder Mac erstellt zuerst sein eigenes Inventar (`build_inventory.sh`).

## Installation

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Abdeckungsbericht

```bash
bash scripts/report_update_coverage.sh
```

Status: **verified direct**, **triggered-unverified**, **externally managed**, **manual**, **unknown**. Ein stiller Start beweist kein fertiges Update. Inkscape nutzt Homebrew; UniFi/WiFiman/Picsart Track 2; Office `msupdate`; Teams den eigenen Updater mit beobachtetem, verifiziertem MAU-Fallback `TEAMS21`. Derzeit ist keine registrierte App „manual“; IPMIView läuft über App Store Track 2.

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

Phase C aktiviert lokales JSON-Inventar und ausdrücklich genehmigte Aktionen. `bash update_all.sh --plan` und `--dry-run` zeigen denselben Plan ohne Speicherung. Ein interaktiver Lauf fragt einmal nach den angezeigten Umfängen; `-y`, EOF und unbeaufsichtigte Läufe erteilen keine neue Erlaubnis. Mit `--preferences` Entscheidungen prüfen oder zurücksetzen. Updates erhalten beobachtete Quelle und Zielpfad; Konflikte, fehlende Ziele und unsichere Belege stellen nur das betroffene Ziel zurück. `build_inventory.sh --migration --preview` erhält ursprüngliche Markdown-Bytes und Notizen; die angezeigte Vorschlags-ID ausdrücklich bestätigen. Allgemeine Herstellerupdates bleiben bis zur Prüfung von Identität und Adapter manuell. Ein Katalogeintrag belegt weder Installation noch Zustimmung.
