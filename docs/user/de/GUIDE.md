# Anleitung (Deutsch)

**macOS Updates 2.0.10** · Apple-Silicon-Mac · macOS 13 oder neuer

## Was es tut

Ein Lauf aktualisiert in dieser Reihenfolge:

1. Apps aus dem App Store
2. Terminal-Werkzeuge (npm, bun und Kommandozeilen-Werkzeuge, die sich selbst aktualisieren)
3. Homebrew-Formeln und -Casks
4. Apps aus dem Internet: Apps, die Sie von der Website des Herstellers geladen haben, aktualisiert über den Update-Feed des Herstellers, einen geprüften direkten Download oder den eigenen Updater der App
5. Die Liste Ihrer Apps (wird neu erstellt)
6. macOS, immer zuletzt

Es verlangt keine Bestätigung für jede einzelne App. Es arbeitet nur mit dem, was schon installiert ist.

## Was es nie tut

- Es schließt nie eine App, die Sie geöffnet haben. Diese App erscheint unter „Braucht Sie“.
- Es installiert nie eine App, die Sie nicht haben. (Der optionale Reiter Katalog ist die einzige Stelle, die installieren kann, und nur, was Sie auswählen.)
- Es vertraut nie blind einem Download. Ein Download muss von einem erlaubten Host kommen, eine gültige Code-Signatur tragen und Gatekeeper bestehen.
- Es stoppt nie alles, nur weil ein Eintrag fehlgeschlagen ist. Die anderen Einträge, die weiteren Schritte und das macOS-Update laufen trotzdem.

## Die Oberfläche öffnen

```bash
mac-update
```

Im Terminal öffnet sich damit die Oberfläche. In einem Skript, über SSH ohne Terminal oder mit `MAC_UPDATE_NONINTERACTIVE=1` bekommen Sie stattdessen reinen Text. `mac-update run` liefert immer reinen Text. `mac-update --cli` (auch `--plain`) ist dasselbe wie `mac-update run`, `mac-update --tui` dasselbe wie `mac-update` allein, und `macos-update` ist derselbe Befehl unter einem längeren Namen. Alle funktionieren in jedem Ordner. Das Fenster braucht mindestens 40 Spalten mal 12 Zeilen. Größer ist angenehmer: Lassen Sie „Fenstergröße automatisch anpassen“ eingeschaltet, fordert die Oberfläche beim Start 120 mal 36 vom Terminal an und stellt die Größe beim Beenden wieder her.

Bewegen Sie sich mit den Pfeiltasten. Die Eingabetaste öffnet oder bestätigt, Tab geht zum nächsten Bereich, Esc geht zurück, `1` bis `7` springen zu einem Reiter, `?` öffnet die Hilfe, `L` zeigt das ganze Protokoll, `q` beendet. Die Maus funktioniert auch. Die unterste Zeile listet immer die Tasten, die gerade gelten.

## Die Reiter

```
 macOS Updates                                  Zuletzt: fertig, vor 2 h
 Übersicht   Apps   Katalog   Verlauf   Einstellungen   Diagnose   Hilfe
 +- Update-Gruppen ----------------------------------------------------+
 | > v Systemprüfung         ############  fertig                      |
 |   v App Store             ############  v3 .5                       |
 |   v Terminal-Werkzeuge    ############  v2 .9                       |
 |   * Homebrew              ######......  4/9  v1 .3                  |
 |   . Apps aus dem Internet ............  wartet                      |
 |   . App-Liste             ............  wartet                      |
 |   . macOS-System          ............  wartet                      |
 +---------------------------------------------------------------------+
   [ Alles aktualisieren ]   [ Vorschau (ohne Änderungen) ]
   ✓ aktualisiert  • aktuell  ! braucht Sie  ✗ fehlgeschlagen
```

Das ist eine vereinfachte Zeichnung. Der echte Bildschirm nutzt Farben und Symbole.

| Reiter | Wofür er da ist |
|--------|-----------------|
| **Übersicht** | Ein Update starten. Zeigt jede Gruppe mit Live-Fortschritt (erledigt von gesamt) und darin eine scrollbare Liste der Apps, während sie läuft. Eingabe- oder Leertaste auf einer Gruppe schaltet sie für den nächsten Lauf ein oder aus. Ein Seitenbereich zeigt den letzten Lauf, was noch Sie braucht, den nächsten automatischen Lauf und den Zustand dieses Macs. |
| **Apps** | Jede App und jedes Paket, das auf diesem Mac gefunden wurde (Hilfs- und Hintergrund-Apps bleiben außen vor). Wählen Sie, wie jedes einzelne aktualisiert wird. |
| **Katalog** | Alle getesteten Apps: zuerst die, die noch hinzugefügt werden können, danach die bereits installierten (nur zur Ansicht). Nichts ist vorausgewählt, bis Sie wählen, und das Installationsprogramm fragt vor jeder Änderung. Update-Läufe nutzen ihn nie. |
| **Verlauf** | Frühere Läufe, die neuesten zuerst, jeweils mit Ergebnis. Wählen Sie einen Lauf, um zu sehen, was aktualisiert wurde und was Sie brauchte. Die Eingabetaste öffnet sein ganzes Protokoll. |
| **Einstellungen** | Was aktualisiert wird, Sicherheitsgrenzen, Zeitplan, Sprache und Aussehen. Jede Änderung wird sofort gespeichert. |
| **Diagnose** | Prüfungen, die Sie starten können: Diesen Mac prüfen, Voraussetzungen prüfen, So werden Apps aktualisiert (eine Tabelle aller Apps und woher die Update-Methode bekannt ist), Update-Feeds prüfen, App-Liste neu erstellen, Unterbrochene Updates beenden, Nach neuer Programmversion suchen. |
| **Hilfe** | Eine kurze Anleitung: erste Schritte, wie das Aktualisieren funktioniert, wofür jeder Reiter da ist, was „Braucht Sie“ bedeutet. |

## Ein Update ausführen

- **Alles aktualisieren** prüft und aktualisiert jede Gruppe, die eingeschaltet ist.
- **Vorschau (ohne Änderungen)** geht dieselben Schritte durch und zeigt, was passieren würde. Sie installiert nichts und schreibt keinen Verlauf.

Während eines Laufs sehen Sie jede Gruppe und jede App: prüfen, laden, verifizieren, installieren. Mit `L` öffnen Sie das ganze Protokoll. **Stopp** beendet den Lauf sicher: Apps, die schon aktualisiert sind, bleiben aktualisiert.

Fragen (zum Beispiel zu einem Neustart) warten auf Ihre Antwort. Wenn Sie nicht rechtzeitig antworten, wird die sichere Antwort verwendet. Ihr Administratorpasswort geben Sie im Terminal ein; es wird nie gespeichert oder angezeigt.

Der Ergebnisbildschirm listet:

- **Aktualisiert**: jetzt aktuell.
- **Aktuell**: Hier war nichts nötig.
- **Braucht Sie**: siehe unten.

## So werden Internet-Apps aktualisiert

- Apps mit einem geprüften Download des Herstellers (zum Beispiel Claude und Antigravity IDE) werden direkt installiert, statt geöffnet und abgewartet zu werden. Schlägt der Download fehl, wird weiterhin der eigene Updater der App genutzt.
- Eine App, die geöffnet wurde, damit sie sich selbst aktualisiert, wird geschlossen, sobald ihr Update bereitgestellt ist (Warp), statt die volle Zeit zu warten.
- Chrome wird bei einem schrittweisen Rollout sofort gemeldet, wenn der Google-Updater für Ihre Version bereits „kein Update“ geantwortet hat.
- Google-Apps (Gemini, Chrome, Google Drive) zeigen, wann der Google-Updater zuletzt geprüft hat und wieder prüfen wird, oder dass sich die App selbst aktualisiert hat.
- Eine Homebrew-App, die geöffnet war und sich schon selbst aktualisiert hat, wird ohne Warnung als aktuell gemeldet.
- Blockiert macOS eine App unter **Anmeldeobjekte & Erweiterungen** (sie schließt sich gleich nach dem Öffnen), sagt das Ergebnis es und wo sie erlaubt wird: Systemeinstellungen › Allgemein › Anmeldeobjekte & Erweiterungen.

## Einstellungen pro App

Öffnen Sie den Reiter **Apps**. Mit `/` suchen Sie nach Name oder Quelle. Drücken Sie die Eingabetaste auf einer App. Mit der Leertaste markieren Sie mehrere Apps, um sie gemeinsam zu ändern.

| Modus | Bedeutung |
|-------|-----------|
| **automatisch** | Das Programm aktualisiert sie für Sie. Das ist die Voreinstellung. |
| **manuell** | Das Programm sagt Ihnen nur, wenn ein Update bereitsteht. |
| **überspringen** | Das Programm lässt sie unberührt. |

Wo eine App mehrere Quellen hat, können Sie auch eine **bevorzugte Quelle** wählen: Standardquelle, Homebrew, App Store, Website des Herstellers oder eingebauter Updater. Die Spalte **Methode** zeigt, woher das Programm die App kennt: getestet (auf der Liste der getesteten Apps), automatisch erkannt (gefunden über einen App-Store-Beleg, Homebrew, einen Update-Feed oder einen eingebauten Updater) oder manuell (nichts erkannt). Die Einstellung „Neu gefundene Apps“ legt fest, was mit Apps passiert, die ein Suchlauf findet und die nicht auf der Liste der getesteten Apps stehen: nach Sicherheit (automatisch, wenn der Aktualisierungsweg klar ist, sonst manuell), immer automatisch oder immer manuell.

Ist die Liste leer, wählen Sie **Jetzt durchsuchen**. Das Durchsuchen liest Ihren Mac nur.

Ihre Auswahl wird in `~/.config/mac-update/overrides.tsv` gespeichert, eine Zeile pro App: Gruppe, Name, Modus, Quelle (durch Tabulatoren getrennt). Löschen Sie die Datei, um jede App wieder auf automatisch zu stellen.

## Einstellungen

Wählen Sie für einen schnellen Start ein Profil: **Voll automatisch** (alles), **Vorsichtig** (kein macOS-Update, keine großen Versionssprünge), **Nur prüfen** (nichts wird installiert). Jede manuelle Änderung zeigt **Eigene**.

| Bereich | Zeilen |
|---------|--------|
| Was aktualisiert wird | Ein Schalter pro Gruppe; Nur prüfen, nie installieren; Große Upgrades erlauben (ausgeschaltet bleibt die aktuelle Hauptversion); macOS-Updates: installieren, nur melden oder aus (vor einem Neustart wird immer gefragt) |
| Apps und Quellen | Neu gefundene Apps (nach Sicherheit, automatisch, manuell); Modus und Quelle pro App (öffnet den Reiter Apps); Ausgeschlossene Apps (`config/inventory_exclusions.txt`); Beobachtete npm-Werkzeuge (`config/npm_global_clis.txt`) |
| Automatische Läufe | Tägliche Automatik (standardmäßig aus, ohne voreingestellte Uhrzeit): wann sie läuft (jeden Tag zu einer gewählten Zeit, bei der Anmeldung oder beides) und die Mitteilung nach einem Lauf (nach jedem Lauf, nur wenn etwas mich braucht, nie); Jetzt testen |
| Sicherheitsprüfungen | Warten, bis Apps sich schließen (s); Von Hersteller-Websites laden; Mindestens freier Speicher (GB, Standard 15); Mindest-Akkustand (%, Standard 30) |
| Netzwerk und Tempo | Update-Prüfungen wiederverwenden (Stunden); Zeit für eine Antwort (s, Standard 120); Zeitlimit für App-Store-Updates (s) |
| Mitteilungen und Berichte | Mitteilung nach dem Ende; Letztes Protokoll öffnen; Aufbewahrte Protokolle (Standard 30) |
| Sprache und Aussehen | Sprache (English, Polski, Deutsch, Español, Français, Italiano, Português; sie folgt Ihrer Systemsprache, bis Sie eine wählen); Farben; Akzentfarbe (standardmäßig blau, außerdem violett, bernstein, salbeigrün, rosa, graphit); Abstände; Einfache Zeichen; Fenstergröße automatisch anpassen; Maus; Hilfebereich beim Start offen |
| System und Wartung | Microsoft-Office-Verzögerung (Tage); Mac wach halten; App-Liste neu erstellen; Dieses Programm aktualisieren; Einstellungen exportieren; Einstellungen importieren; Auf Standard zurücksetzen |

Die Einstellungen werden in `~/.local/state/mac-update/tui-settings.json` gespeichert, Ihre Sprache in `~/.config/mac-update/lang`. Eine Zeile, die durch eine Umgebungsvariable gesetzt ist, zeigt diese Variable und lässt sich im Fenster nicht ändern. „Warten, bis Apps sich schließen“ gilt für Apps, die das Programm selbst gestartet hat.

Die Farben folgen Ihrem Terminal. Die Voreinstellung **automatisch** fragt das Terminal, ob sein Fenster hell oder dunkel ist, und nimmt das passende Schema. Das helle Aussehen lässt der Seite den eigenen weißen Hintergrund und die Textfarbe Ihres Terminals; nur die obere Leiste, die Tastenleiste, die gewählte Zeile und Dialoge sind hellgrau, und jede Farbe bleibt auf einem weißen Fenster gut lesbar. Das dunkle Schema ist unverändert. Ein von einer früheren Version gespeichertes „dunkel“ wird einmal wie „automatisch“ behandelt; wenn Sie immer dunkel möchten, wählen Sie es in den Einstellungen unter Sprache und Aussehen, Farben erneut.

## Was „Braucht Sie“ bedeutet

Jede Zeile auf dem Ergebnisbildschirm hat einen Grund und einen nächsten Schritt.

| Grund | Was zu tun ist |
|-------|----------------|
| **Die App war geöffnet** | Beenden Sie die App und starten Sie das Update erneut. Das Programm schließt sie nie für Sie. |
| **Anmeldung nötig** (App Store) | Öffnen Sie den App Store, melden Sie sich an und starten Sie das Update erneut. |
| **Ein Passwort wird gebraucht** | Starten Sie das Update erneut aus dem Terminal und geben Sie Ihr Administratorpasswort ein, wenn Sie gefragt werden. Automatische Läufe können nicht fragen und melden das deshalb. |
| **Ein Neustart ist nötig** | Das Update ist installiert, wirkt aber erst nach einem Neustart. Starten Sie den Mac neu, wann es Ihnen passt. |
| **Kein automatischer Weg** | Es gibt keinen sicheren automatischen Weg, diese App zu aktualisieren. Öffnen Sie die App und nutzen Sie ihre eigene Funktion „Nach Updates suchen“. |
| **Der Download wurde nicht abgeschlossen** | Prüfen Sie die Internetverbindung und starten Sie das Update erneut. |
| **Prüfsumme stimmt nicht** | Der Download stimmte nicht mit seiner Prüfsumme überein, deshalb wurde nichts installiert. Versuchen Sie es später noch einmal. Wenn es weiter scheitert, aktualisieren Sie die App von Hand. |
| **Manueller Modus** | Sie haben diese App auf manuell gestellt, deshalb wurde sie nur geprüft. Aktualisieren Sie sie selbst oder stellen Sie sie im Reiter Apps auf automatisch. |
| **Die Update-Informationen des Herstellers waren nicht erreichbar** | Versuchen Sie es später noch einmal. Die Website des Herstellers ist vielleicht nicht erreichbar. |
| **Eine neue Hauptversion ist verfügbar** | Große Upgrades sind ausgeschaltet. Erlauben Sie sie in den Einstellungen oder aktualisieren Sie von Hand. |
| **Nicht genug freier Speicherplatz / Akku zu schwach** | Schaffen Sie Platz oder schließen Sie das Netzteil an und starten Sie dann erneut. |
| **Hat zu lange gedauert** | Starten Sie erneut. Öffnen Sie das ganze Protokoll (`L`), wenn es sich wiederholt. |
| **Der eigene Updater der App wurde geöffnet** | Schließen Sie das Update in dem Fenster ab, das die App geöffnet hat. |

Manche Apps installieren ihr Update erst beim Beenden. Hat das Programm eine solche App selbst gestartet, schließt es sie, sobald das Update bereit ist. Eine App, die Sie selbst geöffnet haben, wird nie geschlossen.

Wenn als Grund „nicht bekannt“ steht, öffnen Sie das ganze Protokoll mit `L`.

Kopfzeile, Übersicht und Verlauf zeigen immer dieselben Zahlen. Eine iPad-App, die der App Store nach dem Update noch installiert, wird als „wird noch im App Store installiert“ ohne etwas zum Anklicken aufgeführt: Warten Sie einige Minuten und prüfen Sie erneut. Ein Hintergrund-Updater, der gestartet wurde, aber kein Ergebnis gemeldet hat, steht als „kein Ergebnis aufgezeichnet, nichts zu tun“ in der Liste. Seine Version wird danach erneut gelesen, sodass ein abgeschlossenes Update als aktualisiert erscheint.

## Wo was liegt

| Was | Wo |
|-----|----|
| Lauf-Protokolle (die neuesten 30 bleiben erhalten) | `~/.local/state/mac-update/logs/` |
| Ihre Auswahl pro App, Ihre Sprache und die Liste Ihrer Apps | `~/.config/mac-update/` (`overrides.tsv`, `lang`, `reports/`) |
| Das Programm | `~/.local/share/mac-update/` |

Zu Optionen, Umgebungsvariablen und Fehlersuche siehe [OPERATIONS.md](OPERATIONS.md). Zum Installieren, Upgraden oder Entfernen des Programms siehe [INSTALL.md](../../INSTALL.md) und [UNINSTALL.md](../../UNINSTALL.md).
