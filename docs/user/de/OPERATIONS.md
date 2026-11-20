# Betrieb (Deutsch)

**macOS Updates 2.0.10** · für Menschen, die das Programm aus einem Terminal, einem Skript oder nach Zeitplan ausführen.

## Arten der Ausführung

| Befehl | Was passiert |
|--------|--------------|
| `mac-update` | Öffnet die Oberfläche (braucht ein Terminal). |
| `mac-update run [options]` | Lauf als reiner Text. Die Optionen gehen an das Update-Programm, zum Beispiel `-y`, `--skip-system`, `--non-interactive`. |
| `mac-update --cli [options]` | Dasselbe wie `mac-update run` (auch `--plain`). |
| `mac-update --tui` | Dasselbe wie `mac-update`: öffnet die Oberfläche. |
| `mac-update preview` | Geht jeden Schritt durch und zeigt, was passieren würde. Nichts wird aktualisiert. |
| `mac-update scan` | Erstellt die Liste der Apps auf diesem Mac neu. Liest nur. |
| `mac-update doctor` | Bereitschaftsbericht nur zum Lesen. Kein Passwort, kein Lauf-Protokoll. |
| `mac-update settings` | Öffnet die Oberfläche im Reiter Einstellungen. |
| `mac-update update-self` | Sucht nach einer neueren Version von mac-update (`--check`, die Voreinstellung, oder `--prepare`). |
| `mac-update migrate` | Übernimmt Einstellungen aus einer älteren git-Kopie: `--preview` (Voreinstellung), `--apply`, `--undo MANIFEST`. |
| `mac-update uninstall` | Entfernt mac-update. Siehe [UNINSTALL.md](../../UNINSTALL.md). |
| `mac-update version`, `mac-update help` | Version und Befehlsliste. |

`macos-update` ist derselbe Befehl wie `mac-update`, nur mit längerem Namen. Das Installationsprogramm verlinkt beide in `~/.local/bin`, und beide funktionieren in jedem Ordner.

`mac-update` ruft `update_all.sh` im Programmordner `~/.local/share/mac-update` auf. Wenn Sie stattdessen aus einem git-Checkout arbeiten, führen Sie dort `bash update_all.sh` aus; die Optionen unten sind dieselben. Mit `MAC_UPDATE_NONINTERACTIVE=1` öffnet sich die Oberfläche nie, und nichts wartet auf eine Antwort.

## Optionen von `update_all.sh`

| Option | Bedeutung |
|--------|-----------|
| `-y`, `--yes` | Die Bestätigungsfrage überspringen |
| `-h`, `--help` | Die Liste der Optionen zeigen |
| `--tui`, `--cli` | Oberfläche oder reinen Text wählen. `--tui` bricht mit einer Meldung ab, wenn es kein brauchbares Terminal gibt; nur `--dry-run` und `--skip-...` dürfen dazukommen. |
| `--dry-run` | Vorschau, nichts ändern |
| `--doctor` | Bereitschaftsbericht. Exit-Code 0 ok, 10 Warnungen, 1 Problem |
| `--verify-only` | Installierte App-Versionen mit dem Verlauf vergleichen, nichts ändern |
| `--json-summary` | Am Ende eine JSON-Zusammenfassung ausgeben |
| `--bootstrap-cli` | Auch ein fehlendes verwaltetes Node, Bun oder natives Kommandozeilen-Werkzeug installieren. Standardmäßig aus. |
| `--skip-prescan` | Die erste Prüfung der App-Liste überspringen |
| `--skip-appstore` | App-Store-Apps überspringen |
| `--skip-npm` | Terminal-Werkzeuge überspringen (npm, bun, native Kommandozeilen-Werkzeuge) |
| `--skip-brew` | Homebrew überspringen |
| `--skip-internet` | Apps aus dem Internet überspringen |
| `--skip-postupdate` | Das Aktualisieren von App-Liste und Verlauf überspringen |
| `--skip-system` | Das macOS-Update überspringen |
| `--skip-doctor` | `brew doctor` im Homebrew-Schritt überspringen |
| `--treat-appstore-ax-as-warning` | Eine fehlende Berechtigung für Bedienungshilfen als Warnung melden |
| `--non-interactive` | Für Zeitplaner: keine Fragen (wie `MAC_UPDATE_NONINTERACTIVE=1`) |
| `--notify` | Eine macOS-Mitteilung zeigen, wenn der Lauf endet |

Die Schritte laufen immer in dieser Reihenfolge: Systemprüfung, App Store, Terminal-Werkzeuge, Homebrew, Apps aus dem Internet, App-Liste, macOS. macOS kommt zuletzt, weil es den Mac neu starten kann. Ist ein früherer Schritt hart fehlgeschlagen, wartet der macOS-Schritt bis zum nächsten Lauf.

## Umgebungsvariablen

Setzen Sie sie vor den Befehl, zum Beispiel `MAC_UPDATE_MIN_FREE_GB=30 mac-update run`. Die meisten gibt es auch als Zeile in den Einstellungen; eine Zeile, die durch eine Variable gesetzt ist, lässt sich in der Oberfläche nicht ändern.

| Variable | Standard | Zweck |
|----------|----------|-------|
| `MAC_UPDATE_NONINTERACTIVE` | aus | `1`: keine Oberfläche, keine Fragen |
| `MAC_UPDATE_DRY_RUN` | aus | `1`: wie `--dry-run` |
| `MAC_UPDATE_SKIP_APPSTORE`, `_NPM`, `_BREW`, `_INTERNET`, `_SYSTEM`, `_PRESCAN`, `_POSTUPDATE`, `_DOCTOR` | aus | `1`: wie die passende Option `--skip-...` |
| `MAC_UPDATE_SYSTEM_MODE` | `auto` | macOS-Updates: `auto` installiert, `notify` meldet nur, `skip` prüft nicht |
| `MAC_UPDATE_NEW_APP_MODE` | nach Sicherheit | `auto` oder `manual` für neu gefundene Apps, die nicht auf der Liste der getesteten Apps stehen |
| `MAC_UPDATE_NOTIFY` | aus | `1`: Mitteilung nach dem Ende. Für automatische Läufe: `always`, `needs_you` oder `never` |
| `MAC_UPDATE_LANG` | Systemsprache | `en`, `pl`, `de`, `fr`, `es`, `it`, `pt` |
| `MAC_UPDATE_HOME` | `~/.local/share/mac-update` | Programmordner |
| `MAC_UPDATE_CONFIG_DIR` | `~/.config/mac-update` | Ordner für Einstellungen |
| `MAC_UPDATE_STATE_DIR` | `~/.local/state/mac-update` | Protokolle, Zwischenspeicher, Sicherungen |
| `MAC_UPDATE_LOGS_DIR` | `logs` im Statusordner | Lauf-Protokolle |
| `MAC_UPDATE_OVERRIDES_FILE` | `overrides.tsv` im Einstellungsordner | Datei mit der Auswahl pro App |
| `MAC_UPDATE_MAX_LOGS` | 30 | Aufzubewahrende Lauf-Protokolle |
| `MAC_UPDATE_PROMPT_TIMEOUT` | 120 | Sekunden für die Antwort auf eine Frage, bevor die sichere Antwort verwendet wird |
| `MAC_UPDATE_MIN_FREE_GB` | 15 | Unterhalb dieses freien Speichers warnen und eingeschränkt laufen |
| `MAC_UPDATE_MIN_BATTERY` | 30 | Im Akkubetrieb unterhalb dieses Prozentwerts den macOS-Schritt überspringen (ein automatischer Lauf wird ganz übersprungen) |
| `MAC_UPDATE_NO_CAFFEINATE` | aus | `1`: den Mac während des Laufs nicht wach halten |
| `MAC_UPDATE_NO_SUDO_KEEPALIVE` | aus | `1`: das Administratorpasswort nicht frisch halten |
| `MAC_UPDATE_SUDO_KEEPALIVE_MAX` | 14400 | Sekunden, die es frisch gehalten wird (300 bis 14400) |
| `MAC_UPDATE_QUIT_WAIT` | 60 | Sekunden, die auf das Schließen einer vom Programm gestarteten App gewartet wird (0 bis 300) |
| `MAC_UPDATE_STAGE_WAIT` | 90 | Sekunden, die darauf gewartet wird, dass eine vom Programm geöffnete App ihr eigenes Update installiert (0 bis 600) |
| `MAC_UPDATE_POST_QUIT_WAIT` | 10 | Sekunden Wartezeit nach dem Schließen einer solchen App, wenn ihr Update bereitgestellt wurde |
| `MAC_UPDATE_POST_QUIT_WAIT_IDLE` | 3 | Dasselbe, wenn kein Update bereitgestellt wurde |
| `MAC_UPDATE_OMAHA_WAIT` | 45 | Sekunden, die auf die Antwort des Google-Updaters gewartet wird (0 bis 180) |
| `MAC_UPDATE_OMAHA_MAX_AGE_H` | 6 | Stunden, in denen eine Prüfung des Google-Updaters als aktuell gilt |
| `MAC_UPDATE_BTM_CHECK` | an | `0`: nicht prüfen, ob macOS eine App unter Anmeldeobjekte & Erweiterungen blockiert |
| `MAC_UPDATE_BTM_TIMEOUT` | 4 | Sekunden für diese Prüfung |
| `MAC_UPDATE_BTM_DUMP`, `MAC_UPDATE_GOOGLE_USER_LOG`, `MAC_UPDATE_GOOGLE_SYS_LOG` | keiner | Nur für Diagnose und Tests: eine gespeicherte Liste der Anmeldeobjekte oder Logdateien des Google-Updaters, die statt der echten gelesen werden |
| `MAC_UPDATE_VENDOR_DIRECT` | an | `0`: keine direkten Downloads vom App-Hersteller |
| `MAC_UPDATE_ALLOW_MAJOR_UPGRADE` | aus | `1`: große Versionssprünge erlauben, auch ein großes macOS-Upgrade |
| `MAC_UPDATE_MAU_DEFERRAL_DAYS` | 7 | Tage, die vor der Installation einer neuen Microsoft-Office-Version gewartet wird |
| `MAC_UPDATE_FEED_CACHE_TTL_H` | 24 | Stunden, die die Versionsinformationen des Herstellers wiederverwendet werden |
| `MAC_UPDATE_MAS_UPGRADE_TIMEOUT` | 1800 | Sekunden, bevor ein App-Store-Update gestoppt und gemeldet wird |
| `MAC_UPDATE_DOCTOR_PROBE_AX` | aus | `1`: `doctor` die Berechtigung für Bedienungshilfen testen lassen (macOS zeigt eventuell eine Abfrage) |
| `GITHUB_TOKEN` | keiner | Optional. Erhöht das Download-Limit von GitHub. Setzen Sie es in Ihrem Shell-Profil |

## Automatische Läufe (optional)

Automatische Läufe sind standardmäßig aus und haben keine voreingestellte Uhrzeit. Schalten Sie sie in den **Einstellungen** im Abschnitt **Automatische Läufe** in der Zeile „Tägliche Automatik“ ein. Sie wählen:

- wann: jeden Tag zu einer Uhrzeit, die Sie eingeben (24 Stunden, zum Beispiel 08:30), bei der Anmeldung oder beides;
- wie Sie informiert werden: nach jedem Lauf, nur wenn etwas Sie braucht (die Voreinstellung) oder nie.

Sie sehen genau, was installiert wird, und bestätigen, bevor etwas geschrieben wird. „Jetzt testen“ plant einen zusätzlichen Lauf in wenigen Minuten.

Dasselbe im Terminal, mit `bash ~/.local/share/mac-update/scripts/install_launchagent.sh`:

```bash
bash scripts/install_launchagent.sh --daily 08:30 --notify needs_you      # jeden Tag um 08:30
bash scripts/install_launchagent.sh --daily 08:30 --days 1,3,5            # nur an gewählten Wochentagen (Zahlen 1 bis 7)
bash scripts/install_launchagent.sh --at-login --delay-min 10             # bei der Anmeldung, nach 10 Minuten Sitzungszeit
bash scripts/install_launchagent.sh --once-in 5                           # ein Testlauf in 5 Minuten
bash scripts/install_launchagent.sh --status                              # ist es installiert? (--check, oder --status --json)
bash scripts/install_launchagent.sh --uninstall                           # jeden mac-update-Zeitplan entfernen
```

Führen Sie diese Befehle im Programmordner aus. `--notify` akzeptiert `always`, `needs_you` oder `never`.

Was ein automatischer Lauf tut:

- Er läuft ohne Terminal und stellt nie eine Frage.
- Er überspringt macOS-Updates, solange Sie sie nicht aktivieren; macOS meldet dann nur, was verfügbar ist.
- Er überspringt sich selbst, wenn ein anderer Lauf aktiv ist, wenn der Akku des Macs schwach ist oder wenn der letzte erfolgreiche Lauf weniger als 12 Stunden her ist.
- Alles, was Ihr Passwort oder einen Neustart braucht, wird übersprungen und als „Braucht Sie“ gemeldet. Führen Sie `mac-update` selbst aus, um es abzuschließen.
- Er sendet eine Mitteilung, wie Sie es gewählt haben. Die Ausgabe landet in `launchd.out` und `launchd.err` im Ordner der Protokolle.

## Passwörter

Die Schritte für macOS und den App Store brauchen eventuell Ihr Administratorpasswort. Im Terminal fragt das Programm höchstens einmal pro Lauf und hält es für den Rest des Laufs frisch. In einer Vorschau fragt es nie, und ohne Terminal auch nie (automatische Läufe überspringen diese Schritte stattdessen). Optional: `bash scripts/setup_touchid_sudo.sh --check` zeigt, ob Touch ID das Passwort für `sudo` ersetzen kann. Ohne `--check` zeigt das Skript eine Vorschau und fragt zuerst nach.

## Wo was liegt

| Was | Wo |
|-----|----|
| Das Programm | `~/.local/share/mac-update` |
| Ihre Einstellungen und Auswahl pro App | `~/.config/mac-update` (`overrides.tsv`, `lang`, `reports/`) |
| Lauf-Protokoll jedes Laufs | `~/.local/state/mac-update/logs/update_all_<date>_<time>.log` (die neuesten 30 bleiben erhalten, Modus 600) |
| Kurzes Ergebnis des letzten Laufs | `~/.local/state/mac-update/logs/run_summary_latest.json` |
| Einstellungen der Oberfläche | `~/.local/state/mac-update/tui-settings.json` |
| Ausgabe automatischer Läufe | `~/.local/state/mac-update/logs/launchd.out`, `launchd.err` |

Eine Vorschau schreibt ihr Protokoll in einen temporären Ordner und lässt Ihren Verlauf unverändert. In der Oberfläche listet der Reiter **Verlauf** frühere Läufe, und `L` öffnet das neueste Protokoll. Sie kommen von einer älteren git-Kopie? `mac-update migrate`.

Exit-Code von `update_all.sh`: `0`, wenn der Lauf sauber war oder nur Warnungen hatte (eine App, die Sie braucht, ist eine Warnung), `1`, wenn etwas fehlgeschlagen ist.

## Fehlersuche

Beginnen Sie mit `mac-update doctor`. Es prüft Plattform, Python, curl, Homebrew, `mas`, Touch ID, Speicherplatz, Stromversorgung, Netzwerk und das Programm selbst.

| Problem | Was zu tun ist |
|---------|----------------|
| `mac-update: command not found` | Öffnen Sie ein neues Terminalfenster. Besteht das Problem weiter, liegt `~/.local/bin` nicht in Ihrem `PATH`: Führen Sie das Installationsprogramm erneut mit `--configure-shell` aus oder tragen Sie den Ordner selbst ein. |
| `mac-update` startet ein anderes Programm | Ein anderes Programm mit diesem Namen steht in Ihrem `PATH` weiter vorn. Das Installationsprogramm warnt davor und nennt die Datei dieses Programms. Starten Sie `~/.local/bin/mac-update` direkt oder entfernen oder benennen Sie die andere Datei um. |
| Die Oberfläche öffnet sich nicht | Sie braucht ein Terminal, Python 3 und ein `TERM`, das nicht `dumb` ist. Nutzen Sie sonst `mac-update run`. |
| Das Installationsprogramm meldet, dass die Prüfsumme nicht stimmt | Es wurde nichts installiert. Versuchen Sie es später noch einmal; wenn es sich wiederholt, melden Sie es. |
| Eine App steht unter „Braucht Sie“ | Siehe die Tabelle „Was „Braucht Sie“ bedeutet“ in [GUIDE.md](GUIDE.md). |
| Der App-Store-Schritt stoppt mit Exit-Code 2 | Dem Terminal fehlt die Berechtigung für Bedienungshilfen. Erlauben Sie sie in Systemeinstellungen, Datenschutz & Sicherheit, Bedienungshilfen, oder fügen Sie `--treat-appstore-ax-as-warning` hinzu. |
| `mas` fehlt oder ist zu alt | Das Programm meldet es und installiert es nie von selbst. Installieren Sie es selbst mit Homebrew (`brew install mas`). |
| Der App Store braucht eine Anmeldung | Öffnen Sie den App Store, melden Sie sich an und starten Sie erneut. |
| Homebrew fehlt | Installieren Sie es von <https://brew.sh> und starten Sie dann erneut. |
| Die App-Liste fehlt oder ist falsch | `mac-update scan`. Es liest nur Ihren Mac. Kopieren Sie nie die Liste einer anderen Person. |
| Eine App wird nie aktualisiert | Diagnose, „So werden Apps aktualisiert“, zeigt, wie jede App behandelt wird. Öffnen Sie die App und nutzen Sie ihre eigene Funktion „Nach Updates suchen“, wenn es keine Methode gibt. |
| Die Update-Informationen eines Herstellers sind nicht erreichbar | Versuchen Sie es später. Prüfen Sie die Feeds in der Diagnose unter „Update-Feeds prüfen“. |
| Der Mac ist während eines Laufs in den Ruhezustand gegangen | Lassen Sie „Mac wach halten“ eingeschaltet (Standard). |
| Ein Update wurde unterbrochen | Diagnose, „Unterbrochene Updates beenden“. |
| Ein Lauf meldet, dass ein anderer Lauf aktiv ist | Warten Sie, bis er fertig ist. Eine Markierung, die ein abgestürzter Lauf hinterlassen hat, wird zu Beginn des nächsten Laufs aufgeräumt. |
| Wenig Speicherplatz oder Akku | Schaffen Sie Platz oder schließen Sie das Ladegerät an. Die Grenzen stehen in den Einstellungen unter „Sicherheitsprüfungen“. |

Immer noch nicht gelöst? Öffnen Sie die neueste Datei im Ordner der Protokolle und suchen Sie die erste Zeile mit „error“ oder „warning“.

## Deinstallation

```bash
mac-update uninstall
```

Der Befehl schaltet auch die automatischen Läufe aus. Was entfernt wird und was nicht, steht in [UNINSTALL.md](../../UNINSTALL.md).
