# macOS Updates

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

> **v1.4.0** — Produktionsbereiter Ein-Befehl-Update-Orchestrierer für **Apple Silicon Macs unter macOS 13–26**. Koordiniert verifizierte Paket-Updates für bereits auf diesem Mac installierte Software. **Mehrsprachig** (7 Sprachen). Optionale private Cloud-Schicht über [`dev_sync/`](dev_sync/README.md).

**Öffentliches Repository:** [github.com/KasprowiczM/macOS_updates](https://github.com/KasprowiczM/macOS_updates) · Release: [docs/PUBLIC_RELEASE.md](docs/PUBLIC_RELEASE.md)

---

## Einzeilige Installation (neue Benutzer)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

Das Installationsprogramm klont das Repository, bittet um die **Sprachauswahl** (Deutsch ist verfügbar), installiert Abhängigkeiten, erstellt **Ihre** `APPLICATIONS.md`-Datei basierend auf den bereits auf Ihrem Mac vorhandenen Apps und zeigt an, welche Apps aktualisiert werden können. Es importiert niemals das Inventar eines anderen Benutzers und installiert keine neuen Apps.

Siehe [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md)

---

## Was dieses Tool macht

`update_all.sh` führt sieben Schritte aus:

| Schritt | Aktion |
|------|--------|
| 0 | **Vorab-Scan** — findet installierte Apps → aktualisiert `APPLICATIONS.md` |
| 1 | **App Store** — Track 1: `sudo mas upgrade`; Track 2: AppleScript-GUI für iPad-Apps |
| 2 | **Native CLI + npm** — Node, Bun, globale npm-Tools |
| 3 | **Homebrew** — Formeln und Casks (`--greedy-auto-updates`) + Downgrade-Schutz |
| 4 | **Internet-Apps** — verifizierte Handler, `vendor_latest`, Sparkle Appcast & direkte Updates |
| 5 | **Post-Update/Verlauf** — aktualisiert Inventar und Verlauf atomar |
| 6 | **macOS (zuletzt)** — `softwareupdate -ia -R`; entfällt bei einem früheren Fehler |

---

## Einrichtung pro Rechner (kommt **nicht** mit `git pull`)

Zwei Dinge liegen außerhalb des Repositorys und müssen daher einmal **auf jedem Mac**
eingerichtet werden. Klonen oder Pullen auf einem zweiten Rechner bringt sie nicht mit —
das ist die häufigste Verwechslung in diesem Projekt.

| Schritt | Befehl | Warum nicht in Git |
|---------|--------|--------------------|
| Touch ID für `sudo` | `bash scripts/setup_touchid_sudo.sh` | Schreibt `/etc/pam.d/sudo_local` — root-eigene, rechnerlokale Datei |
| Wöchentlicher Hintergrundlauf | `bash scripts/install_launchagent.sh --day 1 --hour 9` | Schreibt `~/Library/LaunchAgents/…plist` — pro Benutzer und Rechner |

`setup_touchid_sudo.sh` fasst `/etc/sudoers` nie an und gewährt niemals passwortloses `sudo`.

**Der geplante Hintergrundlauf installiert weder macOS- noch App-Store-Updates.** Beide
erfordern eine Benutzerauthentifizierung — auf Apple Silicon verlangt `softwareupdate`
Volume-Owner-Anmeldedaten. Führen Sie `bash update_all.sh` interaktiv aus, wenn Sie diese
Updates einspielen möchten.

**sudo-Kontrakt (v1.3.1 / v1.4.0):** höchstens eine Abfrage pro Lauf; **nie** ohne steuerndes TTY
(stattdessen wird `MAC_UPDATE_NO_SUDO=1` exportiert); nie bei `--dry-run`.

---

## Funktionen & Umgebungsvariablen in v1.4.0

- **Touch ID / Sudo Pre-Authorization**: Erkennt Touch ID `pam_tid.so` und hält Sudo-Sitzungen aktiv.
- **Hintergrund & LaunchAgent Support**: Unterstützt `MAC_UPDATE_NO_SUDO=1` für unbewachte Hintergrundausführungen.
- **`vendor_latest` & Downgrade-Schutz**: Verhindert Homebrew Cask Downgrades für schnell aktualisierte Apps.
- **Steuerungs-Flags**:
  - `MAC_UPDATE_YES=1` (`-y`) — Nicht-interaktive Bestätigung aller Schritte.
  - `MAC_UPDATE_SKIP_SYSTEM=1` (`--skip-system`) — Überspringt macOS Systemupdates.
  - `MAC_UPDATE_VERIFY_ONLY=1` (`--verify-only`) — Überprüft Versionen installierter Apps anhand des Verlaufs ohne Änderungen.
  - `MAC_UPDATE_NONINTERACTIVE=1` — Unterdrückt interaktive Dialoge.
  - `MAC_UPDATE_MAU_CLEAR_DEFERRALS=1` — Entfernt blockierende MAU-Aufschubschlüssel.

```bash
# Beispiel für Versionsüberprüfung ohne Aktualisierung:
bash update_all.sh --verify-only
```

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

---

## Dokumentation

| Zielgruppe | Start hier |
|----------|------------|
| Benutzer | [docs/user/de/QUICK_START.md](docs/user/de/QUICK_START.md) |
| Installieren / Deinstallieren | [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md) |
| Entwickler | [docs/agents/scripts.md](docs/agents/scripts.md) |
| Cloud Sync | [dev_sync/README.md](dev_sync/README.md) |
| KI-Kontext | `AGENTS.md` |

---

## Wichtige technische Hinweise

- **`softwareupdate` muss `-R` verwenden** — andernfalls werden Updates heruntergeladen, aber nie angewendet.
- **`mas upgrade` muss `sudo` verwenden** unter macOS 14.8+/15.7+/26.x (CVE-2025-43411).
- **Bash 3.2+** überall — keine `declare -A`, `mapfile` oder `readarray`.
