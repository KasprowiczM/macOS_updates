# macOS Updates

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

**Version 2.0.10** · Apple-Silicon-Mac · macOS 13 oder neuer · [Website](https://macos-updates.64bit.site) · [MIT-Lizenz](LICENSE) · [Änderungen](CHANGELOG.md)

Ein Befehl, `mac-update`, hält die Software auf Ihrem Mac aktuell. Er berührt nur, was bereits installiert ist.

## Was aktualisiert wird

Ein Lauf geht der Reihe nach durch diese Gruppen:

1. Apps aus dem App Store
2. Terminal-Werkzeuge (npm, bun, Kommandozeilen-Werkzeuge)
3. Homebrew-Formeln und -Casks
4. Apps aus dem Internet (über den Update-Feed des Herstellers, einen geprüften direkten Download oder den eigenen Updater der App)
5. Die Liste Ihrer Apps
6. macOS, immer zuletzt

Sie müssen nicht jede App einzeln bestätigen. Wenn eine App anders behandelt werden soll, stellen Sie sie im Reiter **Apps** auf manuell oder überspringen. macOS selbst können Sie in den **Einstellungen** auf installieren, nur melden oder aus stellen.

## Installation

Fügen Sie dies im Terminal ein:

```bash
/bin/bash -c "$(curl -fsSL https://github.com/KasprowiczM/macOS_updates/releases/latest/download/install.sh)"
```

Das Installationsprogramm lädt das neueste Release-Paket herunter, prüft dessen SHA-256-Prüfsumme, legt das Programm in `~/.local/share/mac-update` ab und verknüpft den Befehl `mac-update` in `~/.local/bin`. Es braucht kein `git`, verwendet nie `sudo` und behält Ihre Einstellungen bei einem Upgrade. Um vorher zu sehen, was es tun würde, fügen Sie `--dry-run` hinzu: `... install.sh | bash -s -- --dry-run`. Details: [docs/INSTALL.md](docs/INSTALL.md) (in English).

Wird `mac-update` danach nicht gefunden, öffnen Sie ein neues Terminalfenster. Wenn es dann immer noch fehlt, führen Sie das Installationsprogramm erneut mit `--configure-shell` aus.

## Erster Start

```bash
mac-update
```

Im Terminal öffnet sich eine Oberfläche mit Reitern: Übersicht, Apps, Katalog, Verlauf, Einstellungen, Diagnose, Hilfe. Wählen Sie **Vorschau (ohne Änderungen)**, um zu sehen, was passieren würde, und danach **Alles aktualisieren**. Der Ergebnisbildschirm zeigt, was **Aktualisiert** wurde, was **Aktuell** ist und was **Braucht Sie**, jeweils mit Grund und nächstem Schritt.

Stattdessen als reiner Text: `mac-update run`. `mac-update --cli` (auch `--plain`) ist dasselbe wie `mac-update run`, `mac-update --tui` dasselbe wie `mac-update` allein, und `macos-update` ist derselbe Befehl unter einem längeren Namen. Alle funktionieren in jedem Ordner. Vorschau als reiner Text: `mac-update preview`. Mac prüfen, ohne zu aktualisieren: `mac-update doctor`. Alle Befehle: `mac-update help`. Fehlt etwas (Command Line Tools, natives Homebrew, Python, `mas`)? `mac-update doctor` listet es auf, `mac-update prepare` installiert es nach einer einzigen Rückfrage.

Sie kommen von einer älteren Kopie, die mit git installiert wurde? Führen Sie `mac-update migrate` aus, um Ihre Einstellungen zu übernehmen (es zeigt zuerst eine Vorschau).

## Sicherheit

- Apps, die Sie geöffnet haben, werden nie geschlossen. Sie erscheinen unter „Braucht Sie“.
- Downloads kommen nur von erlaubten Hosts und müssen die Prüfung der Code-Signatur und Gatekeeper bestehen.
- Ein Update-Lauf installiert nie eine App, die Sie nicht haben.
- Ein fehlgeschlagener Eintrag stoppt die anderen nicht, und macOS wird weiterhin zuletzt aktualisiert.
- Passwörter geben Sie im Terminal ein; sie werden nie gespeichert. Ein automatischer Lauf stellt nie Fragen.

## Automatische Läufe

Standardmäßig aus und ohne voreingestellte Uhrzeit. Zum Einschalten öffnen Sie die **Einstellungen**, Abschnitt **Automatische Läufe**: Wählen Sie eine Tageszeit, „bei der Anmeldung“ oder beides und legen Sie fest, wie Sie benachrichtigt werden möchten. Ein geplanter Lauf überspringt macOS-Updates, solange Sie sie nicht aktivieren. Siehe [Betrieb](docs/user/de/OPERATIONS.md).

## Dokumentation

| Sprache | Schnellstart | Anleitung | Betrieb |
|---------|--------------|-----------|---------|
| Deutsch | [Schnellstart](docs/user/de/QUICK_START.md) | [Anleitung](docs/user/de/GUIDE.md) | [Betrieb](docs/user/de/OPERATIONS.md) |

Alle Sprachen: [docs/user/INDEX.md](docs/user/INDEX.md) · [Installation](docs/INSTALL.md) · [Deinstallation](docs/UNINSTALL.md)

## Lizenz

[MIT](LICENSE)
