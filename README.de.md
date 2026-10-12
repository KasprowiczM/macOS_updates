# macOS Updates

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

**Website:** [macos-updates.64bit.site](https://macos-updates.64bit.site) · **Repository:** [github.com/KasprowiczM/macOS_updates](https://github.com/KasprowiczM/macOS_updates) · **Lizenz:** [MIT](LICENSE) · **Änderungen:** [CHANGELOG.md](CHANGELOG.md)

> **v1.5.5** — Produktionsreifer Ein-Befehl-Orchestrator für Updates auf **Apple-Silicon-Macs mit macOS 13–27**. Er koordiniert verifizierte Paketaktualisierungen und ehrliche Auslöser der app-eigenen Updater für **Software, die bereits auf diesem Mac installiert ist**. **Mehrsprachig** (7 Sprachen). Optionales privates Overlay über [`dev_sync/`](dev_sync/README.md).

| Auf einen Blick | |
|-----------------|--|
| Plattform | Nur Apple Silicon (arm64) · macOS 13 Ventura bis macOS 27 · Bash 3.2 + Python 3 |
| Ablauf | 7 Schritte (0–6), das macOS-Systemupdate kommt immer zuletzt |
| Registry | 43 Internet-Apps · 11 Update-Methoden (siehe [Update-Methoden](#update-methoden)) |
| Sprachen | EN, PL, ES, FR, DE, IT, PT (CLI und Dokumentation) |
| Tests | 561 automatisierte Tests (`bash run_tests.sh`) |

**Neu in v1.5.5:** Ein Homebrew-Upgrade, das `python3` mitten im Lauf entfernt, bricht den Inventar-/Berichtsschritt nicht mehr (die Shell durchsucht `PATH` erneut), und ein fehlgeschlagener Berichtsschritt verschiebt macOS-Updates nicht mehr. Die Abschlussmeldungen sind ehrlich: keine Behauptung „Dateien aktualisiert“ nach einem Fehler, und Warnungen zu veralteten Feeds oder nicht beendeten Apps gelten nicht mehr als unverifizierte Updates. Vom Werkzeug gestartete Apps werden wiederholt höflich zum Beenden aufgefordert (nie erzwungen). Frühere 1.5.x-Versionen (veraltete Hersteller-Feeds als Warnung, Hersteller-Downloads für ChatGPT/Proton, native CLIs vor npm, Schutz beim Austausch von Paketen) beschreibt [CHANGELOG.md](CHANGELOG.md).

**Herstellerwahrheit (seit v1.5.0):** Die Version jeder Anwendung wird vor jeder Ausführung mit dem Feed des Herstellers abgeglichen. Aktuelle Apps bleiben unberührt; veraltete Apps werden vom eigenen Updater der App aktualisiert oder vom Hersteller mit Signatur- und Team-ID-Prüfung installiert. Es wird nur installierte Software aktualisiert (`--bootstrap-cli` installiert fehlende CLIs bewusst). Manuell entfernte Apps werden erkannt und nie neu installiert. **Apps, die du geöffnet hast, werden nie geschlossen — das Werkzeug beendet nur, was es selbst gestartet hat.** Den Herstellerstatus prüfst du schreibgeschützt mit `bash scripts/check_vendor_feeds.sh`.

---

## Einzeilige Installation (neue Benutzer)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

Der Installer klont das Repository, fragt die **Sprache** ab (englisches Menü, 7 Sprachen), installiert Abhängigkeiten, erstellt **deine** `APPLICATIONS.md` aus den bereits auf diesem Mac vorhandenen Apps und zeigt, welche Apps das Projekt aktualisieren kann. Er importiert nie das Inventar einer anderen Person und installiert keine Apps für dich.

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

**Wichtig:** Updates betreffen nur Software, die bereits auf deinem Mac installiert ist. Unterstützte, aber fehlende Apps werden gemeldet, nicht installiert. Der abschließende macOS-Schritt kann den Mac neu starten; er läuft deshalb zuletzt und behält das zwingende `-R`. Schritt 5 dient nur der Berichterstattung: Ein Fehler dort ist ein Fehler, verschiebt den macOS-Schritt aber nie. Unbekannte installierte Apps werden aufgelistet, damit du (oder ein KI-Agent) Handler ergänzen kannst.

Die Abdeckung ist bewusst explizit: **verified direct** heißt, der Updater hat den Paket-/Versionspfad bestätigt; **triggered-unverified**, eine App wurde gestartet, damit ihr Hersteller-Updater arbeiten kann, der Abschluss ist aber nicht belegbar; **externally managed**, der Hersteller oder der App Store steuert den Update-Zyklus; **manual** erfordert eine Aktion des Benutzers; **unknown** hat keine registrierte Methode.

```bash
bash scripts/report_update_coverage.sh   # Abdeckungsbericht
bash build_inventory.sh                  # APPLICATIONS.md von diesem Mac neu aufbauen
```

### Update-Methoden

Die Registry ([`config/internet_apps.txt`](config/internet_apps.txt), [`config/internet_app_methods.txt`](config/internet_app_methods.txt)) ordnet 43 Apps 11 Methoden zu:

| Methode | Apps | Abdeckung | Vorgehen |
|---------|-----:|-----------|----------|
| `brew_cask` | 11 | externally managed | Homebrew-Cask (greedy nur für diese Tokens) mit Downgrade-Schutz, z. B. Brave, Obsidian, Spotify, Inkscape |
| `silent_launch` | 9 | triggered-unverified | Der eigene Updater der App; opportunistische Prüfung gegen einen Sparkle-/electron-updater-Feed, sonst „gestartet (nicht verifiziert)“. Ersetzt die App nie selbst |
| `github_dmg` | 6 | verified direct | Hersteller-/GitHub-DMG mit Signatur- und Team-ID-Prüfung, gestufter Austausch mit Rollback (Firefox Developer Edition, KeePassXC, VS Code, CodeEdit, Ledger Live, Trezor Suite) |
| `msupdate` | 5 | verified direct | Microsoft AutoUpdate (`msupdate`): Word, Excel, PowerPoint, Outlook, OneNote |
| `keystone` | 3 | verified direct | Google-Updater (Omaha), anhand seiner Update-Historie geprüft: Chrome, Gemini, Google Drive |
| `appstore_gui` | 3 | externally managed | App Store Spur 2 (AppleScript): UniFi, WiFiman, Picsart |
| `sparkle_appcast` | 1 | verified direct | Sparkle-Appcast (Proton Drive) |
| `chromium_updater` | 1 | verified direct | Nachweis des Chromium-basierten Updaters (Comet) |
| `docker_cli` | 1 | verified direct | Docker Desktop: verifiziertes DMG aus dem Appcast im Leerlauf; Rückfall `docker desktop update` |
| `mau_fallback_self_update` | 1 | triggered-unverified | Teams-Selbstupdate plus beobachteter, verifizierter MAU-Fallback `TEAMS21`, wenn Microsoft ihn anbietet |
| `manual` | 2 | manual | IPMIView und DJI Assistant 2: nur Hinweis |

---

## Kommandozeilen-Optionen

`lib/cli.sh` ist maßgeblich; `bash update_all.sh --help` gibt die Liste aus.

| Option | Wirkung |
|--------|---------|
| `-y`, `--yes` | Bestätigungsabfrage überspringen |
| `-h`, `--help` | Hilfe anzeigen und mit `0` beenden |
| `--dry-run` | Jeden Schritt nur anzeigen, nichts ändern, nie nach Zugangsdaten fragen |
| `--verify-only` | Installierte App-Versionen gegen die Historie prüfen, ohne zu ändern |
| `--json-summary` | Nach dem Lauf ein JSON-Ergebnisobjekt auf stdout ausgeben |
| `--bootstrap-cli` | Fehlende CLI-Werkzeuge ausdrücklich installieren (standardmäßig werden nur installierte CLIs aktualisiert) |
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

## Umgebungsvariablen

Jede Option hat eine gleichwertige Variable (`MAC_UPDATE_DRY_RUN=1`, `MAC_UPDATE_SKIP_SYSTEM=1`, …); hier die häufig genutzten ohne eigene Option. Die vollständige Liste mit Standardwerten steht in [docs/agents/scripts.md](docs/agents/scripts.md#environment-variables).

| Variable | Standard | Bedeutung |
|----------|----------|-----------|
| `MAC_UPDATE_NONINTERACTIVE` | `0` | Nie nachfragen; überspringt die GUI-Automatisierung von App-Store-Spur 2 |
| `MAC_UPDATE_NOTIFY` | `0` | Desktop-Benachrichtigung am Ende (auch im nicht-interaktiven Modus impliziert) |
| `MAC_UPDATE_NO_SUDO` | *automatisch gesetzt* | Von `update_all.sh` ohne TTY exportiert; Kindskripte überspringen dann Root-Spuren, statt zu scheitern |
| `MAC_UPDATE_NO_SUDO_KEEPALIVE` | `0` | `1` deaktiviert die Hintergrundauffrischung des `sudo`-Zeitstempels |
| `MAC_UPDATE_STALE_DAYS` | `45` | Tage, nach denen eine unverifizierte App als veraltet gemeldet wird |
| `MAC_UPDATE_MAX_LOGS` | `30` | In `logs/` aufbewahrte Laufprotokolle |
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
bash scripts/install_launchagent.sh --uninstall
```

`setup_touchid_sudo.sh` berührt nie `/etc/sudoers` und gewährt nie `sudo` ohne
Passwort. Unter macOS 14+ nutzt es `/etc/pam.d/sudo_local`, das Systemupdates
übersteht; unter macOS 13 ändert es `/etc/pam.d/sudo`, das macOS-Updates
überschreiben — führe es nach einem großen Upgrade erneut aus.

### Was der geplante Hintergrundlauf tut und nicht tut

Der LaunchAgent startet `update_all.sh -y --skip-system` mit
`MAC_UPDATE_NONINTERACTIVE=1` und `MAC_UPDATE_NOTIFY=1`.

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
| Xcode Command Line Tools | ✅ `setup.sh` / `install.sh` |
| Homebrew | ✅ |
| `mas` (App-Store-CLI) | ✅ |
| Python 3 | ✅ über Homebrew, falls es fehlt |
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
bash setup.sh
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

Die Testsuite deckt Bash-Syntax, Python-Kompilierung, statische Sicherheitsverträge, Dokumentationswächter und Unit-Tests ab (561 automatisierte Tests).
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
| Versionshistorie | [CHANGELOG.md](CHANGELOG.md) · [Index der Entwicklungsunterlagen](docs/reviews/README.md) |
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
