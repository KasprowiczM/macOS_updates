# Benutzerhandbuch (Deutsch)

**Version:** 1.8.2 · **Apple Silicon, macOS 13+**

## Terminaloberfläche

Im interaktiven Terminal öffnet `bash update_all.sh` die Oberfläche und bis zum Abschluss den Einrichtungsassistenten. `bash setup.sh` öffnet den Assistenten, `bash build_inventory.sh` die Inventaransicht. Der Assistent lässt sich über die Navigation erneut öffnen. Abschluss und Anzeigeeinstellungen werden gespeichert und erteilen keine Update-Zustimmung. `--cli` wählt die bisherige Textoberfläche, `--tui` fordert die Oberfläche ausdrücklich an. Optionen wie `--dry-run` bleiben in der CLI; `--tui` nicht mit anderen Optionen kombinieren. Ausdrückliches `--tui` benötigt ein nutzbares Terminal und Python. Nichtinteraktive und Aufrufe ohne TTY bleiben bei der CLI.

Updategruppen vor dem Start wählen. Links steht die Navigation, in der Mitte Aktionen und laufende Ausgabe, rechts Hilfe und Details auf jedem Bildschirm. Es läuft jeweils ein überwachter Auftrag; bestehende Zustimmungen bleiben erforderlich. Einstellungen umfassen Sprache, Design, ASCII und automatische Größe. `?` öffnet Hilfe, Ctrl+P die Aktionspalette, `c` kopiert den fokussierten Befehl, die Ausgabe oder Zusammenfassung. Ctrl+V fügt nur im Antwortdialog ein; Enter sendet. Eingaben werden maskiert, wenn der Kindprozess Echo deaktiviert.

Mindestens 80 Spalten und 24 Zeilen sind erforderlich. Standardmäßig wird auf unterstützten Terminals mindestens 140 mal 38 angefordert und beim Beenden die ursprüngliche Größe; das Terminal kann Anfragen ignorieren. Die automatische Größe ist abschaltbar.

## Sicheres Setup und Anwendungsquellen

`bash setup.sh --inspect` prüft die Bereitschaft ohne Installation, Profiländerung oder Touch-ID-Konfiguration. Fehlende Werkzeuge machen nur die abhängige Funktion unverfügbar. Im Terminal zeigt `bash setup.sh --install-dependencies` optionale Abhängigkeiten und fragt vor jeder Installation; `bash setup.sh --configure-shell` zeigt eine getrennt zu bestätigende Profiländerung. Abgelehnte Abhängigkeiten blockieren unabhängige Funktionen nicht. Ohne Python muss dieses vor dem Inventar ausdrücklich installiert werden. Fehlendes oder veraltetes `mas` wird gemeldet und nicht automatisch installiert oder aktualisiert.

Im optionalen Katalog ist anfangs nichts ausgewählt. Eine separat genehmigte Homebrew-Installation für KeePassXC ist nach erneuter Quellen- und Abwesenheitsprüfung verfügbar. Die Vorschau zeigt den Manager-Befehl und deklarierte Auswirkungen; geprüft wird der Homebrew-Beleg, nicht die Annahme eines Herstellerrezepts. Andere Einträge behalten geprüfte offizielle Bezugswege. Bestehende Apps werden nie automatisch migriert. Quellenempfehlungen beruhen nur auf verfügbaren Daten stabiler Versionen.

Bei ungewissem Ergebnis einer Kataloginstallation den Katalog für eine erneute Wiederherstellungsprüfung öffnen. Sperren und Journale nicht manuell löschen. KeePassXC über Homebrew benötigt geprüfte stabile Versionsdaten innerhalb von sieben Tagen; danach bleibt der manuelle Weg.

## Funktion

macOS Updates orchestriert Updates auf **Apple-Silicon-Macs mit macOS 13+**:

1. Vorab-Scan und Inventar
2. App Store (`sudo mas upgrade <app-id>` + separater GUI Track 2)
3. Bestehende native CLIs zuerst, danach Node/Bun und npm-Fallbacks
4. Homebrew (greedy nur für als `brew_cask` registrierte Casks)
5. Installierte Apps: zustimmungsgebundene Aktionen; nicht akzeptierte Herstellerupdates bleiben manuell
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


## Internet-App hinzufügen

1. App auf dem Mac installieren.
2. `bash build_inventory.sh --cli`
3. `bash scripts/scaffold_internet_app.sh "/path/to/Observed.app" --json`
4. Prüfe den nicht ausführbaren JSON-Vorschlag; eine spätere Implementierung benötigt Review und `bash run_tests.sh`.

Ersetze das Beispiel durch den genauen Pfad der installierten App. Der Befehl zeigt einen redigierten, nicht ausführbaren Prüfvorschlag. Ein optionaler Export erfordert nach Prüfung der angezeigten Vorschau-ID einen erneuten Aufruf mit `--export --accept PREVIEW_ID`. Updates benötigen eine geprüfte Implementierung und gesonderte Akzeptanznachweise.

## Fehlerbehebung

| Problem | Lösung |
|---------|--------|
| Intel Mac | Nicht unterstützt |
| Falsches App-Inventar | `bash build_inventory.sh --cli` |
| App wird nicht aktualisiert | `bash scripts/report_update_coverage.sh` |
| `APPLICATIONS.md` fehlt | `build_inventory.sh` oder `dev_sync/dev-sync-import.sh` |

Vollständig: [../../agents/troubleshooting.md](../../agents/troubleshooting.md)

Lokales JSON-Inventar und zustimmungsgebundene Aktionen sind verfügbar. `bash update_all.sh --plan` und `--dry-run` zeigen denselben Plan ohne Speicherung. Ein interaktiver Lauf fragt einmal nach den angezeigten Umfängen; `-y`, EOF und unbeaufsichtigte Läufe erteilen keine neue Erlaubnis. Mit `--preferences` Entscheidungen prüfen oder zurücksetzen. Updates erhalten beobachtete Quelle und Zielpfad; Konflikte, fehlende Ziele und unsichere Belege stellen nur das betroffene Ziel zurück. `build_inventory.sh --migration --preview` erhält ursprüngliche Markdown-Bytes und Notizen; die angezeigte Vorschlags-ID ausdrücklich bestätigen. Allgemeine Herstellerupdates bleiben bis zur Prüfung von Identität und Adapter manuell. Ein Katalogeintrag belegt weder Installation noch Zustimmung.


## Optionaler Katalog und Erstinstallation

Neue App-Hinweise sind Vorschläge zur Prüfung, keine ausführbaren Rezepte. `bash scripts/scan_update_feeds.sh` gibt eine zusammengefasste Übersicht aus. Ein Proposal-Export ermöglicht Vorschau und ausdrückliche Annahme; er ist bereinigt, bleibt lokal und wird nie hochgeladen. `bash setup.sh --catalog` öffnet den Katalog ohne Vorauswahl. `-y`, nichtinteraktive Läufe und EOF installieren nichts. Im Menü vergleicht `check <number>` nur ausgewählte Quellen. Ergebnisse zeigen die neueste bestätigte kompatible stabile Version samt Datum; der Cache gilt 24 Stunden. Unbekannt bleibt unbekannt. Ein öffentlicher Mac-App-Store-Eintrag beweist nicht, dass die App für Ihr Konto angeboten wird. Kein Kanal ist immer am schnellsten.

Im optionalen Katalog ist anfangs nichts ausgewählt. Eine separat genehmigte Homebrew-Installation für KeePassXC ist nach erneuter Quellen- und Abwesenheitsprüfung verfügbar. Die Vorschau zeigt den Manager-Befehl und deklarierte Auswirkungen; geprüft wird der Homebrew-Beleg, nicht die Annahme eines Herstellerrezepts. Andere Einträge behalten geprüfte offizielle Bezugswege. Bestehende Apps werden nie automatisch migriert. Quellenempfehlungen beruhen nur auf verfügbaren Daten stabiler Versionen.

## Lokaler Status der Rezeptaktualisierungen

Im optionalen Katalog ist anfangs nichts ausgewählt. Eine separat genehmigte Homebrew-Installation für KeePassXC ist nach erneuter Quellen- und Abwesenheitsprüfung verfügbar. Die Vorschau zeigt den Manager-Befehl und deklarierte Auswirkungen; geprüft wird der Homebrew-Beleg, nicht die Annahme eines Herstellerrezepts. Andere Einträge behalten geprüfte offizielle Bezugswege. Bestehende Apps werden nie automatisch migriert. Quellenempfehlungen beruhen nur auf verfügbaren Daten stabiler Versionen.

`--dry-run` zeigt eine lesbare Vorschau mit bis zu 10 Zielen. `--dry-run --json-summary` oder `--plan` liefert den vollständigen JSON-Plan. Die Vorschau erteilt keine Zustimmung und führt keine Updates aus.

Die Zustimmung zeigt zehn zulässige Einträge pro Seite. Zahlen wie `1,3` erlauben nur deren angezeigte Aktionen; `n` und `p` wechseln die Seite. Enter oder `q` setzt ohne neue Zustimmung fort. Das Zeitlimit von 120 Sekunden wird erklärt; sein Ablauf erteilt keine Zustimmung. Blockierte Einträge werden separat zusammengefasst. Manuelle, ignorierte oder verschobene Entscheidungen stehen unter `--preferences`. Die Protokollierung beginnt vor dieser Prüfung.

## Bedienung und Anwendungsliste

Tab wechselt zwischen Navigation, Arbeitsbereich, Ausgabe und unteren Schaltflächen. Pfeile wählen Einträge, die Leertaste schaltet Kontrollkästchen um und Enter aktiviert die markierte Schaltfläche. Fragen öffnen das Antwortfeld automatisch. Senden bestätigt; Abbrechen schließt das Feld ohne Antwort.

Das Inventar zeigt gespeicherte Anwendungen nach Quelle gruppiert, mit Suche, Filter und Sortierung. Auswahl speichern speichert Ausschlüsse und installiert oder deinstalliert nichts. Erneutes Aktivieren erfordert eine separate Aktualisierungszustimmung. Die Vorschauliste bleibt nach dem Probelauf sichtbar. Das detaillierte Protokoll ist vom Anwendungsstatus getrennt.

Über enthält Autor, Projektlinks und eine ausdrückliche Aktualisierungsprüfung des Werkzeugs. Die Vorschau bindet die Aktualisierung an eine Revision. Anwenden beendet die Oberfläche und verlangt eine Bestätigung im Terminal. Geänderter Code, ein unerwarteter Branch oder Dateikonflikte blockieren die Aktualisierung. Lokale Änderungen werden niemals hochgeladen.

Der automatische Internet-Modus nutzt die gespeicherte Zustimmung, wenn sie die geeignete Gruppe abdeckt; andernfalls bietet er eine separate AUTO-Prüfung an. Genehmigte native Fenster öffnen parallel, Download-Verfahren laufen in derselben überwachten Gruppe; Microsoft- und Google-Aufgaben werden zusammengefasst. Gemeinsame Microsoft- und Google-Updater werden gruppiert. App Store und Homebrew behalten ihre Zuständigkeit. DeepSeek Harness bleibt manuell; Open Design meldet derzeit eine nicht verfügbare automatische Methode. Der Hersteller wählt Versionen nach vorhandenen Kanaleinstellungen. Eine Versionsänderung ist kein bestätigter Abschluss. Unbestätigte Arbeit behält die Gruppensperre und verschiebt das Systemupdate; Diagnose bietet eine ausdrückliche Wiederherstellungsprüfung mit neuer Identitätsprüfung. Die Google-Zustimmung umfasst ausdrücklich alle beim Updater registrierten Produkte, auch außerhalb des Katalogs; deren vollständige Liste ist unbekannt. Dies ersetzt keine Akzeptanz einer Rezeptur für eine konkrete Version. `bash update_all.sh --cli --automatic-internet-batch` bietet dieselbe Gruppenprüfung ohne Terminal-Oberfläche; mit `--dry-run` bleibt sie rein beobachtend.