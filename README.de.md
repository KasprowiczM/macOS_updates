# macOS Updates

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

**Website:** [macos-updates.64bit.site](https://macos-updates.64bit.site) · **Repository:** [github.com/KasprowiczM/macOS_updates](https://github.com/KasprowiczM/macOS_updates) · **Lizenz:** [MIT](LICENSE) · **Änderungen:** [CHANGELOG.md](CHANGELOG.md)

> **v1.7.4** : Ein-Befehl-Orchestrator für Updates auf **Apple-Silicon-Macs mit macOS 13-27**. Er koordiniert verifizierte Paketaktualisierungen und ehrliche Auslöser der app-eigenen Updater für **Software, die bereits auf diesem Mac installiert ist**. **Mehrsprachig** (7 Sprachen). Optionales privates Overlay über [`dev_sync/`](dev_sync/README.md).

| Auf einen Blick | |
|-----------------|--|
| Plattform | Nur Apple Silicon (arm64) · macOS 13 Ventura bis macOS 27 · Bash 3.2 + Python 3 |
| Ablauf | 7 Schritte (0–6), das macOS-Systemupdate kommt immer zuletzt |
| Registry | 47 Internet-Apps · 11 Update-Methoden (siehe [Update-Methoden](#update-methoden)) |
| Sprachen | EN, PL, ES, FR, DE, IT, PT (CLI und Dokumentation) |
| Tests | 1178 automatisierte Tests (`bash run_tests.sh`) |

Phase C aktiviert lokales JSON-Inventar und ausdrücklich genehmigte Aktionen. `bash update_all.sh --plan` und `--dry-run` zeigen denselben Plan ohne Speicherung. Ein interaktiver Lauf fragt einmal nach den angezeigten Umfängen; `-y`, EOF und unbeaufsichtigte Läufe erteilen keine neue Erlaubnis. Mit `--preferences` Entscheidungen prüfen oder zurücksetzen. Updates erhalten beobachtete Quelle und Zielpfad; Konflikte, fehlende Ziele und unsichere Belege stellen nur das betroffene Ziel zurück. `build_inventory.sh --migration --preview` erhält ursprüngliche Markdown-Bytes und Notizen; die angezeigte Vorschlags-ID ausdrücklich bestätigen. Allgemeine Herstellerupdates bleiben bis zur Prüfung von Identität und Adapter manuell. Ein Katalogeintrag belegt weder Installation noch Zustimmung.

Dies ist der Quellstand 1.7.4 lokal, unveröffentlicht und ohne Release-Tag. Der Update-Manager arbeitet nur für installierte Ziele mit beobachteter Quelle und neuer Zustimmung. Allgemeine native und Hersteller-Updater bleiben manuell, bis geprüfte Rezepte vorliegen. Der optionale öffentliche Katalog umfasst 48 Produkte und bietet geprüfte offizielle Links zur manuellen Beschaffung; es gibt null freigegebene automatische Erstinstallationsrezepte. Die folgende Methodenliste beschreibt Fähigkeiten, keine Ausführungsberechtigung.

**Neu in v1.6.0:** Geplante Läufe (launchd) finden Homebrew und `mas`, und der Installer prüft, dass der Job geladen ist (neu: `--minute`, `--once-in`). Geöffnete Apps werden nie geschlossen oder ersetzt, auch Homebrew-Casks nicht. Jede Rückfrage während des Laufs läuft mit der sicheren Antwort „nein“ ab. `bash update_all.sh --doctor` ist ein schreibgeschützter Bereitschaftsbericht, und echte Läufe haben Vorabprüfungen. Ein dauerhafter Feed-Zustand ersetzt unklare „veralteter Feed“-Warnungen, und HyperFrames, Superset und Open Design werden ohne versteckte Starts installiert bzw. geprüft. Frühere 1.5.x-Versionen stehen im [CHANGELOG.md](CHANGELOG.md).

Ältere Hersteller-Feed-Berichte sind schreibgeschützt. Der aktuelle Manager lässt allgemeine native und Hersteller-Updater manuell, bis ein geprüftes Rezept vorliegt. Das alte Flag `--bootstrap-cli` erteilt keine Erlaubnis zur Erstinstallation. Fehlende CLIs separat anhand geprüfter offizieller Anleitungen installieren. Geöffnete Apps werden nicht geschlossen. Feed-Status mit `bash scripts/check_vendor_feeds.sh` prüfen.

## Sicheres Setup und Anwendungsquellen

`bash setup.sh --inspect` prüft die Bereitschaft ohne Installation, Profiländerung oder Touch-ID-Konfiguration. Fehlende Werkzeuge machen nur die abhängige Funktion unverfügbar. Im Terminal zeigt `bash setup.sh --install-dependencies` optionale Abhängigkeiten und fragt vor jeder Installation; `bash setup.sh --configure-shell` zeigt eine getrennt zu bestätigende Profiländerung. Abgelehnte Abhängigkeiten blockieren unabhängige Funktionen nicht. Ohne Python muss dieses vor dem Inventar ausdrücklich installiert werden. Fehlendes oder veraltetes `mas` wird gemeldet und nicht automatisch installiert oder aktualisiert.

Der normale Updatebericht umfasst installierte Apps. `bash scripts/report_update_coverage.sh --show-supported` bleibt eine Referenzliste. Das optionale Auswahlmenü öffnet `bash setup.sh --catalog` und startet ohne Vorauswahl. Nach Vorschau und erneuter Zustimmung kann eine App über einen geprüften offiziellen Link manuell beschafft werden. Ein Quellenwechsel für eine bestehende App erfordert manuelle Migration. Ein App-Store-Beleg für CapCut erhält den App-Store-Pfad. Eine lokale App ohne bestätigte Homebrew-Zuordnung wird nicht automatisch übernommen.

Die Untersuchung zu Latest Stable steht in [SOURCE_RESEARCH.md](docs/catalog/SOURCE_RESEARCH.md). Verschiedene Editionen sind nicht vergleichbar; eine Momentaufnahme beweist keinen dauerhaft schnellsten Kanal.

---

## Einzeilige Installation (neue Benutzer)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

Der Installer klont das Repository, fragt nach der Sprache, prüft die Bereitschaft und erstellt mit verfügbarem Python das Inventar dieses Macs. Abhängigkeiten erfordern eine getrennte Auswahl im Setup. Touch ID und Shell-Profile werden nicht automatisch geändert.

Siehe [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md)

---

## Was dieses Werkzeug macht

`update_all.sh` führt sieben Schritte aus:

| Schritt | Aktion |
|---------|--------|
| 0 | **Vorabscan** — installierte Apps erkennen → `APPLICATIONS.md` aktualisieren |
| 1 | **App Store** — Spur 1: `sudo mas upgrade <app-id>`; Spur 2: AppleScript-GUI für iPad-Apps |
| 2 | **Native CLI + npm** — zuerst vorhandene native CLIs, dann Node, Bun und globale npm-CLIs |
| 3 | **Homebrew** — Formeln und Casks (`brew_cask` + Downgrade-Schutz) + Aufräumen und Gesundheitsprüfung |
| 4 | **Internet-Apps** — verifizierte direkte Handler, `sparkle_appcast`, Hersteller-CLIs und ehrliche Updater-Auslöser |
| 5 | **Postupdate/Historie** — `APPLICATIONS.md` aktualisieren, `UPDATES.md` atomar ergänzen |
| 6 | **macOS (final)** — pro Label `softwareupdate -i <label> -R` (Labels mit Neustart im letzten Stapel); wird nach einem blockierenden harten Fehler in den Schritten 1–4 oder ohne Autorisierung verschoben |

**Wichtig:** Normale Updates betreffen nur installierte Software mit beobachteter Quelle und genehmigtem Aktionsumfang. Der separate optionale Katalog kann fehlende Apps anzeigen, installiert sie aber nicht automatisch. Manuelle Beschaffung erfordert Vorschau und neue Zustimmung. Der abschließende macOS-Schritt kann den Mac neu starten und läuft daher zuletzt mit dem zwingenden `-R`. Schritt 5 dient nur der Berichterstattung. Unbekannte installierte Apps werden zur Prüfung aufgelistet.

Die Abdeckung ist bewusst explizit: **verified direct** heißt, der Updater hat den Paket-/Versionspfad bestätigt; **triggered-unverified**, eine App wurde gestartet, damit ihr Hersteller-Updater arbeiten kann, der Abschluss ist aber nicht belegbar; **externally managed**, der Hersteller oder der App Store steuert den Update-Zyklus; **manual** erfordert eine Aktion des Benutzers; **unknown** hat keine registrierte Methode.

```bash
bash scripts/report_update_coverage.sh   # Abdeckungsbericht
bash build_inventory.sh                  # APPLICATIONS.md von diesem Mac neu aufbauen
```

### Update-Methoden
Die Methodentabelle ist eine ältere Fähigkeitsübersicht. Sie beschreibt registrierte Methoden, erteilt aber keine Ausführungsberechtigung; der Manager benötigt eine beobachtete Quelle und neue Zustimmung.

Die Registry ([`config/internet_apps.txt`](config/internet_apps.txt), [`config/internet_app_methods.txt`](config/internet_app_methods.txt)) ordnet 47 Apps 11 Methoden zu:

| Methode | Apps | Abdeckung | Vorgehen |
|---------|-----:|-----------|----------|
| `brew_cask` | 11 | externally managed | Homebrew-Cask (greedy nur für diese Tokens) mit Downgrade-Schutz, z. B. Brave, Obsidian, Spotify, Inkscape |
| `silent_launch` | 14 | triggered-unverified | Der eigene Updater der App als Rückfall; opportunistische Prüfung gegen einen Sparkle-/electron-updater-Feed, sonst „gestartet (nicht verifiziert)“. Apps mit Hersteller-Feed (ChatGPT / Codex, Claude, Cursor, Warp, OpenCode, Proton Mail, ...) werden stattdessen nach diesem Feed entschieden und bei Rückstand aus dem geprüften Hersteller-Artefakt installiert. Ohne Feed ersetzt die Methode die App selbst nie |
| `github_dmg` | 5 | verified direct | Hersteller-/GitHub-DMG mit Signatur- und Team-ID-Prüfung, gestufter Austausch mit Rollback (KeePassXC, VS Code, CodeEdit, Ledger Live, Trezor Suite) |
| `msupdate` | 5 | verified direct | Microsoft AutoUpdate (`msupdate`): Word, Excel, PowerPoint, Outlook, OneNote |
| `keystone` | 3 | verified direct | Google-Updater (Omaha), anhand seiner Update-Historie geprüft: Chrome, Gemini, Google Drive |
| `appstore_gui` | 4 | externally managed | App Store Spur 2 (AppleScript): UniFi, WiFiman, Picsart, IPMIView |
| `sparkle_appcast` | 1 | verified direct | Sparkle-Appcast (Proton Drive) |
| `chromium_updater` | 1 | verified direct | Nachweis des Chromium-basierten Updaters (Comet) |
| `docker_cli` | 1 | verified direct | Docker Desktop: verifiziertes DMG aus dem Appcast im Leerlauf; Rückfall `docker desktop update` |
| `mau_fallback_self_update` | 1 | triggered-unverified | Teams-Selbstupdate plus beobachteter, verifizierter MAU-Fallback `TEAMS21`, wenn Microsoft ihn anbietet |
| `mozilla_dmg` | 1 | verified direct | Mozilla-product-details-Version plus geprüftes DMG, gestufter Austausch mit Rollback (Firefox Developer Edition) |

---

## Kommandozeilen-Optionen

`lib/cli.sh` ist maßgeblich; `bash update_all.sh --help` gibt die Liste aus.

| Option | Wirkung |
|--------|---------|
| `-y`, `--yes` | Bestätigungsabfrage überspringen |
| `-h`, `--help` | Hilfe anzeigen und mit `0` beenden |
| `--doctor` | Schreibgeschützter Bereitschaftsbericht (Plattform, Werkzeuge, launchd-`PATH`, LaunchAgent, sudo, Speicher, Strom, Netzwerk, letzter Lauf); keine sudo-Abfrage, kein Laufprotokoll; Exit `0` ok / `10` Warnungen / `1` Problem |
| `--dry-run` | Jeden Schritt nur anzeigen, nichts ändern, nie nach Zugangsdaten fragen |
| `--verify-only` | Installierte App-Versionen gegen die Historie prüfen, ohne zu ändern |
| `--json-summary` | Nach dem Lauf ein JSON-Ergebnisobjekt auf stdout ausgeben |
| `--bootstrap-cli` | Das alte Flag CLI erteilt keine Erlaubnis zur Erstinstallation. Fehlende CLIs separat anhand geprüfter offizieller Anleitungen installieren. |
| `--non-interactive` | Nicht-interaktiver Modus für launchd / cron (impliziert auch `-y`) |
| `--notify` | Beim Ende eine macOS-Benachrichtigung senden |
| `--treat-appstore-ax-as-warning` | App-Store-Exit `2` (fehlende Bedienungshilfen) als Warnung behandeln |
| `--skip-prescan` | Schritt 0 überspringen (`APPLICATIONS.md`-Vorabscan) |
| `--skip-appstore` | Schritt 1 überspringen (App Store) |
| `--skip-npm` | Schritt 2 überspringen (native CLI + npm) |
| `--skip-brew` | Schritt 3 überspringen (Homebrew) |
| `--skip-internet` | Schritt 4 überspringen (Internet-Apps) |
| `--skip-postupdate` | Schritt 5 überspringen (Historie `APPLICATIONS.md` / `UPDATES.md`) |
| `--skip-system` | Schritt 6 überspringen (macOS-Systemupdate) |
| `--skip-doctor` | `brew doctor` in `update_brew.sh` überspringen |

Eine unbekannte Option `-…` beendet sich nach der Hilfeausgabe mit Code `2`.

**Vorprüfung (nur bei echten Läufen):** Vor Schritt 0 prüft der Lauf freien Speicher, Akku und Netzwerk. Wenig Speicher stuft den Lauf herab, ein niedriger Akkustand überspringt nur den macOS-Schritt (weich), und ohne erreichbaren Host endet der Lauf mit Code `1` vor jedem Schritt. Der Mac wird während des Laufs mit `caffeinate` wach gehalten (`MAC_UPDATE_NO_CAFFEINATE=1` deaktiviert das). Mit `bash update_all.sh --doctor` siehst du dieselben Prüfungen, ohne etwas auszuführen.

**Abfragen:** Jede Rückfrage während des Laufs läuft nach `MAC_UPDATE_PROMPT_TIMEOUT` Sekunden mit der sicheren Antwort „nein” ab; nicht erkannte Eingaben gelten ebenfalls als „nein”. Nach der Bestätigung im Hauptskript fragen die Homebrew- und App-Store-Schritte nicht erneut; der macOS-Schritt fragt weiterhin.

**Geöffnete Apps:** Ein Homebrew-Cask, dessen App geöffnet ist, wird nie aktualisiert; er wird mit der Meldung „Beende die App” zurückgestellt, und der Schritt endet mit einer weichen Warnung (Code `10`).

**Direct-only- und never-launch-Apps:** `config/vendor_launch_policy.txt` listet Apps, die das Werkzeug nie startet. Eine `direct-only`-App (HyperFrames, Superset) wird nur aus ihrem geprüften Hersteller-Artefakt aktualisiert; eine `never-launch`-App (Open Design) wird nur geprüft und bei Rückstand als „App öffnen, um zu aktualisieren“ gemeldet. Keine wird geöffnet oder beendet, auch nicht als Rückfall nach einem nicht erreichbaren Feed.

## Umgebungsvariablen

Jede Option hat eine gleichwertige Variable (`MAC_UPDATE_DRY_RUN=1`, `MAC_UPDATE_SKIP_SYSTEM=1`, …); hier die häufig genutzten ohne eigene Option. Die vollständige Liste mit Standardwerten steht in [docs/agents/scripts.md](docs/agents/scripts.md#environment-variables).

| Variable | Standard | Bedeutung |
|----------|----------|-----------|
| `MAC_UPDATE_NONINTERACTIVE` | `0` | Nie nachfragen; überspringt die GUI-Automatisierung von App-Store-Spur 2 |
| `MAC_UPDATE_NOTIFY` | `0` | Desktop-Benachrichtigung am Ende (auch im nicht-interaktiven Modus impliziert) |
| `MAC_UPDATE_NO_SUDO` | *automatisch gesetzt* | Von `update_all.sh` ohne TTY exportiert; Kindskripte überspringen dann Root-Spuren, statt zu scheitern |
| `MAC_UPDATE_NO_SUDO_KEEPALIVE` | `0` | `1` deaktiviert die Hintergrundauffrischung des `sudo`-Zeitstempels |
| `MAC_UPDATE_STALE_DAYS` | `45` | Tage, nach denen eine unverifizierte App als veraltet gemeldet wird |
| `MAC_UPDATE_MAX_LOGS` | `30` | In `logs/` aufbewahrte Laufprotokolle (Laufzusammenfassungen werden ebenfalls rotiert) |
| `MAC_UPDATE_PROMPT_TIMEOUT` | `120` | Sekunden (10–900, `0` = unbegrenzt warten), die eine Ja/Nein-Abfrage während des Laufs wartet; Zeitüberschreitung bedeutet „nein” |
| `MAC_UPDATE_MIN_FREE_GB` | `15` | Vorprüfung: freier Speicher unter diesem Wert stuft den Lauf herab |
| `MAC_UPDATE_MIN_BATTERY` | `30` | Vorprüfung: im Akkubetrieb unter diesem Prozentwert wird nur der macOS-Schritt übersprungen |
| `MAC_UPDATE_INTERNET_SETTLE_SECONDS` | `15` | Pause, damit ein gestarteter Hersteller-Updater `Info.plist` neu schreiben kann (`0` deaktiviert, auf 120 begrenzt; entfällt, wenn keine App gestartet wurde) |
| `MAC_UPDATE_QUIT_WAIT` | `60` | Sekunden (0–300), die eine vom Werkzeug gestartete App nach dem sanften `quit` zum Beenden hat; nie erzwungen (v1.5.5) |
| `MAC_UPDATE_QUIT_RESEND` | `10` | Sekunden (1–60) zwischen wiederholten sanften `quit`-Anforderungen im Wartefenster (v1.5.5) |
| `MAC_UPDATE_MAS_CHECK_TIMEOUT` | `120` | Zeitlimit für `mas outdated` |
| `MAC_UPDATE_MAS_UPGRADE_TIMEOUT` | `1800` | Zeitlimit für `sudo mas upgrade` |
| `MAC_UPDATE_MAU_DEFERRAL_DAYS` | `7` | Quarantänefenster von Microsoft AutoUpdate (auf Microsofts Bereich 1–28 begrenzt) |
| `MAC_UPDATE_MAU_CLEAR_DEFERRALS` | `0` | `1` entfernt blockierende MAU-Zurückstellungsschlüssel per `defaults delete` |
| `MAC_UPDATE_MAU_KEEP_DEFERRALS` | `0` | `1`: das Werkzeug fasst die MAU-Zurückstellungseinstellungen nie an |
| `MAC_UPDATE_LANG` / `MAC_LANG` | aus `.mac_update_prefs` | Sprache der Oberfläche (`en pl es it pt de fr`) |

## sudo und Touch ID — der Vertrag

Neu geschrieben in v1.3.1 / v1.4.0. `update_all.sh` hat **genau eine** interaktive
`sudo`-Aufrufstelle, die an drei Bedingungen gebunden ist:

1. **Höchstens einmal pro Lauf.** Ein einziges `sudo -v` vor der Log-Umleitung,
   danach frischt ein Hintergrundprozess den Zeitstempel alle 50 s auf, sodass ein
   langer Lauf nie ein zweites Mal fragt. Der Keep-alive startet höchstens einmal
   und wird von der Aufräum-Falle auf jedem Ausstiegspfad beendet, auch bei
   `INT`/`TERM` — er kann nicht mehr verwaisen.
2. **Nie ohne steuerndes TTY.** Ist stdin kein Terminal (IDE-Task-Runner,
   Agent-Shell, launchd, cron), ruft das Werkzeug **kein** `sudo -v` auf. Ein
   `sudo -v` ohne TTY eskaliert zum grafischen askpass-/Touch-ID-Dialog; deshalb
   schien jeder Befehl Rechteerhöhung zu verlangen. Stattdessen wird
   `MAC_UPDATE_NO_SUDO=1` exportiert, Root-Schritte werden übersprungen und der Lauf
   meldet eine weiche Warnung.
3. **Nie bei `--dry-run`.** Eine Vorschau darf keine Zugangsdaten verlangen.

`sudo` wird auch gar nicht angefordert, wenn weder Schritt 1 (App Store) noch
Schritt 6 (macOS) laufen, z. B. `bash update_all.sh --skip-appstore --skip-system`.

---

## Einrichtung pro Rechner (kommt **nicht** mit `git pull`)

Zwei Dinge liegen außerhalb des Repositorys und müssen daher einmal **auf jedem Mac**
eingerichtet werden. Klonen oder Pullen auf einem zweiten Rechner bringt sie nicht
mit — das ist der häufigste Stolperstein in diesem Projekt.

| Schritt | Befehl | Warum es nicht in Git sein kann |
|---------|--------|---------------------------------|
| Touch ID für `sudo` | `bash scripts/setup_touchid_sudo.sh` | Schreibt `/etc/pam.d/sudo_local` — eine root-eigene, rechnerlokale Datei außerhalb des Repos |
| Wöchentlicher Hintergrundlauf | `bash scripts/install_launchagent.sh --day 1 --hour 9` | Schreibt `~/Library/LaunchAgents/com.<user>.macos-updates.plist` — pro Benutzer und Rechner |

```bash
bash scripts/setup_touchid_sudo.sh --check      # nur Bericht, schreibt nichts
bash scripts/setup_touchid_sudo.sh              # installieren / reparieren
bash scripts/setup_touchid_sudo.sh --uninstall

bash scripts/install_launchagent.sh --check
bash scripts/install_launchagent.sh --once-in 5
bash scripts/install_launchagent.sh --uninstall
```

`setup_touchid_sudo.sh` berührt nie `/etc/sudoers` und gewährt nie `sudo` ohne
Passwort. Unter macOS 14+ nutzt es `/etc/pam.d/sudo_local`, das Systemupdates
übersteht; unter macOS 13 ändert es `/etc/pam.d/sudo`, das macOS-Updates
überschreiben — führe es nach einem großen Upgrade erneut aus.

### Was der geplante Hintergrundlauf tut und nicht tut

Der LaunchAgent startet `update_all.sh -y --skip-system` mit
`MAC_UPDATE_NONINTERACTIVE=1` und `MAC_UPDATE_NOTIFY=1`.

Die Plist setzt einen expliziten `PATH` (`/opt/homebrew/bin:/opt/homebrew/sbin:/usr/bin:/bin:/usr/sbin:/sbin`), weil der launchd-Standard Homebrew nicht enthält, und der Installer prüft mit `launchctl print`, dass der Job geladen ist; andernfalls gibt er den launchctl-Fehler aus und endet mit einem Fehlercode. `--minute N` (0-59) setzt die Minute, `--once-in N` (1-1440 Minuten ab jetzt) installiert einen einmaligen Testlauf und ist nicht mit `--day`/`--hour`/`--minute` kombinierbar, und `--check` warnt vor einer Plist ohne `PATH`-Schlüssel (eine ältere Installation durch erneutes Ausführen des Installers beheben).

- **Führt aus:** Homebrew, native CLI + npm, Internet-Apps, Inventar/Historie.
- **Führt keine macOS-Systemupdates aus** — `--skip-system` ist Absicht. Unter
  Apple Silicon braucht `softwareupdate` die **Zugangsdaten des Volume-Eigentümers**,
  die ein unbeaufsichtigter launchd-Job nicht liefern kann, und der Schritt kann
  den Mac neu starten.
- **Führt keine App-Store-Updates aus** — `sudo mas upgrade` braucht ein Passwort,
  und der AppleScript-Pfad von Spur 2 steuert die App-Store-Oberfläche. Beides wird
  in einer Sitzung ohne TTY übersprungen und als weiche Warnung (Code `10`)
  gemeldet, nie als Fehler.

Beides bleibt also absichtlich interaktiv. Starte `bash update_all.sh` selbst, wenn
du App-Store- und macOS-Updates einspielen möchtest.

---

## Voraussetzungen

| Werkzeug | Automatisch installiert? |
|----------|--------------------------|
| Apple-Silicon-Mac (arm64) | — |
| macOS 13 Ventura oder neuer (getestet bis macOS 27) | — |
| Xcode Command Line Tools | Manuelle Installation |
| Homebrew | Manuelle Installation: https://brew.sh |
| `mas` (App-Store-CLI) | ✅ |
| Python 3.9+ | Ausdrückliche Zustimmung: `setup.sh --install-dependencies` |
| `rclone` (optional) | ✅ falls als Cloud-Anbieter gewählt |

Intel-Macs und macOS 12 oder älter werden nicht unterstützt; die Skripte beenden sich vor jeder Änderung.

---

## Schnellstart

### Neuer Benutzer (ohne Cloud)

```bash
# Option A — eine Zeile (empfohlen)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"

# Option B — manuell
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh --inspect
bash build_inventory.sh
bash update_all.sh
```

### Eigentümer (GitHub + Cloud-Overlay)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

---

## Projektstruktur

```
macOS_updates/
├── VERSION                     # Paketversion (einzige Wahrheitsquelle)
├── install.sh                  # Einzeiliger Installer
├── uninstall.sh                # Entfernt den Klon (behält Homebrew und Apps)
├── setup.sh                    # Ersteinrichtung (ohne Cloud)
├── migration_setup.sh          # Vollständige Einrichtung + Cloud-Assistent
├── build_inventory.sh          # Erzeugt APPLICATIONS.md für diesen Mac
├── update_all.sh               # Haupt-Orchestrator
├── update_*.sh                 # Einzelne Update-Schritte
├── run_tests.sh                # Syntax + Python + unittest + Secret-Scan
│
├── dev_sync/                   # Synchronisation des privaten Overlays (Cloud)
│   ├── provider_setup.sh
│   ├── dev-sync-export.sh      # (+ import, verify, prune, …)
│   └── dev_sync_*.py           # Python-Backend
├── dev-sync-*.sh               # Wrapper im Wurzelverzeichnis (Kompatibilität)
│
├── config/                     # Registry der Internet-Apps (öffentlich)
│   ├── internet_apps.txt
│   ├── internet_app_methods.txt
│   └── internet_dispatch_order.txt
│
├── lib/                        # Gemeinsame Bash-Bibliotheken (+ lib/python/)
├── i18n/                       # Oberflächentexte in 7 Sprachen
├── scripts/                    # Werkzeuge (Abdeckungsbericht, Hersteller-Feeds, Generator, …)
├── templates/                  # APPLICATIONS.md.template (Referenz)
├── tests/                      # unittest + statische Sicherheitsprüfungen
├── docs/
│   ├── INSTALL.md · UNINSTALL.md · PUBLIC_RELEASE.md
│   ├── user/                   # Benutzerhandbücher (7 Sprachen)
│   ├── agents/                 # Referenz für Entwickler / KI-Agenten
│   ├── reviews/                # Index + aktuelle Entwicklungsunterlagen (archive/ = Historie)
│   └── archive/                # Überholte Implementierungspläne
│
├── CHANGELOG.md · CONTRIBUTING.md · SECURITY.md · LICENSE
└── AGENTS.md · CLAUDE.md · GEMINI.md · CODEX.md
```

**Private Dateien (von git ignoriert, nur lokal oder in der Cloud):** `APPLICATIONS.md`, `UPDATES.md`, `.dev_sync_config.json`, `.mac_update_prefs`, `.env`, `logs/`

### Einzelne Skripte

| Skript | Zweck |
|--------|-------|
| `install.sh` | Klonen + Einrichten + Inventar für neue Benutzer |
| `setup.sh` | Abhängigkeiten und Berechtigungen (ohne Cloud) |
| `migration_setup.sh` | Vollständige Migration + Cloud + App-Scan |
| `build_inventory.sh` | Schreibgeschützter Scan → `APPLICATIONS.md` atomar aktualisieren, ohne Update-Historie |
| `update_all.sh` | Alle Update-Schritte + Protokollierung |
| `update_system.sh` … `update_brew.sh` | Updates einzelner Ebenen |
| `uninstall.sh` | Werkzeugverzeichnis entfernen |
| `run_tests.sh` | Syntax + Python + unittest + Secret-Scan |

Vollständige Skriptreferenz: [docs/agents/scripts.md](docs/agents/scripts.md).

---

## Unterstützung für eine neue App hinzufügen

1. Installiere die App selbst (der Updater installiert sie nie für dich).
2. Führe `bash build_inventory.sh` aus, um sie in `APPLICATIONS.md` aufzunehmen.
3. Für automatische Updates frage einen KI-Agenten oder folge [docs/user/de/GUIDE.md](docs/user/de/GUIDE.md):

```bash
bash scripts/scaffold_internet_app.sh "App-Name" silent_launch
bash run_tests.sh
```

Die Methoden der Registry werden auf die oben genannten Abdeckungsstufen abgebildet. Beispiele: `github_dmg` und eine bestätigte Hersteller-CLI sind **verified direct**; `silent_launch` ist **triggered-unverified**; vom App Store oder Hersteller verwaltete Abläufe können **externally managed** sein; `manual` und fehlende Registry-Einträge bleiben ausdrücklich sichtbar.

---

## Cloud-Synchronisation (`dev_sync`)

| GitHub (öffentlich) | Cloud (privat) |
|---------------------|----------------|
| Skripte, `config/`, `docs/`, Tests | `APPLICATIONS.md`, `UPDATES.md`, `.env`, `.dev_sync_config.json` |

```bash
bash dev_sync/provider_setup.sh
bash dev_sync/dev-sync-export.sh
bash dev_sync/dev-sync-import.sh
bash dev_sync/dev-sync-verify-full.sh
```

Die `dev-sync-*.sh`-Wrapper im Wurzelverzeichnis rufen dieselben Skripte in `dev_sync/` auf.

---

## Tests

Die Testsuite deckt Bash-Syntax, Python-Kompilierung, statische Sicherheitsverträge, Dokumentationswächter und Unit-Tests ab (591 automatisierte Tests).
Pull Requests führen ShellCheck auf Ubuntu, portable Python-Tests und den Secret-Scan aus.
Die vollständige `run_tests.sh`-Suite auf einem macOS-Runner läuft nur bei `workflow_dispatch` oder einem `v*`-Tag, nicht bei jedem Push.

```bash
bash run_tests.sh
bash update_all.sh --dry-run -y
```

---

## Wichtige technische Hinweise

- **`softwareupdate` muss `-R` verwenden** — sonst werden Updates geladen, aber nie angewendet.
- **`mas upgrade` muss `sudo` und explizite App-IDs verwenden** unter macOS 14.8.2+/15.7.2+/26.1+ (geänderte Berechtigung, siehe https://github.com/orgs/Homebrew/discussions/6550).
- **Bash 3.2+** durchgehend — kein `declare -A`, `mapfile`, `readarray`.
- Heruntergeladene Apps werden verifiziert, per gestuftem Austausch mit Rollback installiert, und ihre DMGs liegen an eindeutigen Einhängepunkten pro Sitzung.
- Schreibvorgänge für privates Inventar/Historie und Cloud-Importe sind atomar; Importe stellen akzeptierte Dateien bereit, bevor sie übernommen werden.

---

## Dokumentation

| Zielgruppe | Hier beginnen |
|------------|---------------|
| Benutzer | [docs/user/INDEX.md](docs/user/INDEX.md) (Schnellstart, Handbuch und Betriebsanleitung in 7 Sprachen) · [Schnellstart auf Deutsch](docs/user/de/QUICK_START.md) |
| Installation / Deinstallation | [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md) |
| Öffentliches GitHub und privates Overlay | [docs/PUBLIC_RELEASE.md](docs/PUBLIC_RELEASE.md) · [dev_sync/README.md](dev_sync/README.md) |
| Entwickler / Agenten | [docs/agents/scripts.md](docs/agents/scripts.md) · [kritische Regeln](docs/agents/critical_rules.md) · [Exit-Codes](docs/agents/exit_codes.md) · [Fehlerbehebung](docs/agents/troubleshooting.md) · [Abnahmeliste](docs/agents/acceptance_checklist.md) |
| KI-Agenten-Kontext | [AGENTS.md](AGENTS.md) (gemeinsamer Vertrag) · [CLAUDE.md](CLAUDE.md) · [GEMINI.md](GEMINI.md) · [CODEX.md](CODEX.md) |
| Versionshistorie | [CHANGELOG.md](CHANGELOG.md) |
| Mitwirken / Sicherheit | [CONTRIBUTING.md](CONTRIBUTING.md) · [SECURITY.md](SECURITY.md) |

---

## Fehlerbehebung

| Problem | Lösung |
|---------|--------|
| Neuer Mac | `install.sh` oder `setup.sh` + `build_inventory.sh` |
| Falsche App-Liste | `build_inventory.sh` — nie die `APPLICATIONS.md` einer anderen Person kopieren |
| App aktualisiert sich nicht automatisch | `scripts/report_update_coverage.sh` → Handler laut Handbuch ergänzen |
| `APPLICATIONS.md` fehlt | `build_inventory.sh` oder `dev_sync/dev-sync-import.sh` (Eigentümer) |
| `mas upgrade` schlägt fehl | `sudo mas upgrade <app-id>` |
| Cloud nicht konfiguriert | `bash dev_sync/provider_setup.sh` |

Vollständige Liste: [docs/agents/troubleshooting.md](docs/agents/troubleshooting.md)

---

## Lizenz

[MIT](LICENSE) © macOS Updates contributors


## Optionaler Katalog und Erstinstallation

Neue App-Hinweise sind Vorschläge zur Prüfung, keine ausführbaren Rezepte. `bash scripts/scan_update_feeds.sh` gibt eine zusammengefasste Übersicht aus. Ein Proposal-Export ermöglicht Vorschau und ausdrückliche Annahme; er ist bereinigt, bleibt lokal und wird nie hochgeladen. `bash setup.sh --catalog` öffnet den Katalog ohne Vorauswahl. `-y`, nichtinteraktive Läufe und EOF installieren nichts. Im Menü vergleicht `check <number>` nur ausgewählte Quellen. Ergebnisse zeigen die neueste bestätigte kompatible stabile Version samt Datum; der Cache gilt 24 Stunden. Unbekannt bleibt unbekannt. Ein öffentlicher Mac-App-Store-Eintrag beweist nicht, dass die App für Ihr Konto angeboten wird. Kein Kanal ist immer am schnellsten.

Der öffentliche Katalog umfasst 47 Registry-Zeilen für 48 Produkte und null freigegebene automatische Erstinstallationsrezepte. Nach Vorschau und erneuter Bestätigung können Sie geprüfte offizielle Links zur manuellen Beschaffung auswählen. Das Öffnen einer Seite installiert die App nicht. Ein Quellenwechsel für eine bestehende App erfordert manuelle Migration. Der separate InstallPlan zeigt Quelle, Ziel, Version, Voraussetzungen und Berechtigungen; unbekannte Lizenz oder Kosten bleiben als unbekannt markiert. Jedes künftige automatische Rezept braucht vor der Aktivierung eine neue Erstinstallationsfreigabe. Der Katalog verspricht keine automatische Installation aller Produkte.
