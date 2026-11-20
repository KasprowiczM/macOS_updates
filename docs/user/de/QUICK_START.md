# Schnellstart (Deutsch)

**macOS Updates 2.0.10** · Apple-Silicon-Mac · macOS 13 oder neuer · etwa 5 Minuten

macOS Updates hält die Software aktuell, die schon auf Ihrem Mac ist: Apps aus dem App Store, Terminal-Werkzeuge, Homebrew-Pakete, Apps aus dem Internet und macOS selbst. Es installiert nie Apps, die Sie nicht haben.

## 1. Installieren

Fügen Sie dies im Terminal ein:

```bash
/bin/bash -c "$(curl -fsSL https://github.com/KasprowiczM/macOS_updates/releases/latest/download/install.sh)"
```

Das Installationsprogramm lädt das Release herunter, prüft die Prüfsumme und richtet den Befehl `mac-update` ein. Es aktualisiert nichts und braucht weder `git` noch `sudo`. Sie brauchen Python 3.9 oder neuer (fehlt es, sagt Ihnen das Installationsprogramm, dass Sie `xcode-select --install` ausführen sollen). Details: [INSTALL.md](../../INSTALL.md).

Öffnen Sie danach ein neues Terminalfenster, damit der Befehl gefunden wird. Wird `mac-update` immer noch nicht gefunden, führen Sie das Installationsprogramm erneut aus, mit `bash -s -- --configure-shell` hinter dem Pipe-Zeichen, wie in INSTALL.md erklärt.

## 2. Vorschau

```bash
mac-update
```

Im Terminal öffnet sich die Oberfläche auf der **Übersicht**. Gehen Sie mit der Pfeiltaste nach rechts zu **Vorschau (ohne Änderungen)** und drücken Sie die Eingabetaste. Es wird nichts installiert. Sie sehen, was aktualisiert würde.

Lieber als reiner Text? Führen Sie `mac-update preview` aus. `mac-update --cli` (auch `--plain`) ist dasselbe wie `mac-update run`, `mac-update --tui` dasselbe wie `mac-update` allein, und `macos-update` ist derselbe Befehl unter einem längeren Namen. Alle funktionieren in jedem Ordner.

## 3. Aktualisieren

Wählen Sie auf der Übersicht **Alles aktualisieren** und drücken Sie die Eingabetaste. Sie sehen jede Gruppe (App Store, Terminal-Werkzeuge, Homebrew, Apps aus dem Internet, App-Liste, macOS-System) und jede App, während sie aktualisiert wird. Wenn macOS nach Ihrem Passwort fragt, geben Sie es im Terminal ein; das Programm speichert es nie.

Sie können jederzeit abbrechen. Apps, die schon aktualisiert sind, bleiben aktualisiert.

## 4. Ergebnis lesen

Der Ergebnisbildschirm hat drei Listen:

- **Aktualisiert**: Diese Apps sind jetzt aktuell.
- **Aktuell**: Hier war nichts nötig.
- **Braucht Sie**: Das Programm konnte diese nicht allein abschließen. Jede Zeile nennt den Grund und was zu tun ist. Typische Gründe: Die App war geöffnet, der App Store braucht Ihre Anmeldung oder ein Neustart ist nötig. Siehe die [Anleitung](GUIDE.md).

Apps, die Sie geöffnet haben, werden nie geschlossen. Beenden Sie sie und starten Sie das Update erneut.

## 5. Nächste Schritte

| Ich möchte ... | So geht es |
|----------------|------------|
| ändern, wie eine App aktualisiert wird | Reiter Apps, Eingabetaste auf der App: automatisch, manuell oder überspringen |
| eine Gruppe oder die macOS-Updates ausschalten | Übersicht: zur Gruppe gehen, Leertaste drücken. Oder Einstellungen, „macOS-Updates“ |
| ohne die Oberfläche arbeiten | `mac-update run` |
| meinen Mac prüfen, ohne zu aktualisieren | `mac-update doctor` |
| von selbst aktualisieren | Einstellungen, Abschnitt „Automatische Läufe“. Siehe [OPERATIONS.md](OPERATIONS.md) |
| sehen, was schiefgelaufen ist | Reiter Verlauf, dann Eingabetaste auf einem Lauf, um sein Protokoll zu öffnen |
| Einstellungen aus einer älteren git-Kopie übernehmen | `mac-update migrate` (zeigt zuerst eine Vorschau) |

Mehr: [GUIDE.md](GUIDE.md) · [OPERATIONS.md](OPERATIONS.md) · [UNINSTALL.md](../../UNINSTALL.md)
