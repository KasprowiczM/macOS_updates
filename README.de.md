# macOS Updates

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

> **v1.2.0** — Produktionsbereiter Ein-Befehl-Update-Orchestrierer für **Apple Silicon Macs unter macOS 13+**. Koordiniert verifizierte Paket-Updates für bereits auf diesem Mac installierte Software. **Mehrsprachig** (7 Sprachen). Optionale private Cloud-Schicht über [`dev_sync/`](dev_sync/README.md).

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
| 3 | **Homebrew** — Formeln und Casks (`--greedy`) + Bereinigung |
| 4 | **Internet-Apps** — verifizierte Handler, Hersteller-CLIs und ehrliche Update-Auslöser |
| 5 | **Post-Update/Verlauf** — aktualisiert Inventar und Verlauf atomar |
| 6 | **macOS (zuletzt)** — `softwareupdate -ia -R`; entfällt bei einem früheren Fehler |

**Wichtig:** Updates wirken sich nur auf Software aus, die bereits auf Ihrem Mac installiert ist. Unterstützte, aber fehlende Apps werden gemeldet, nicht installiert.

Der Abdeckungsbericht unterscheidet **verified direct**, **triggered-unverified**, **externally managed**, **manual** und **unknown**. Ein stiller App-Start bestätigt keine fertige Aktualisierung. Inkscape läuft über Homebrew Cask; UniFi, WiFiman und Picsart über App Store Track 2; Office über `msupdate`; Teams über den eigenen Updater mit beobachtetem, verifiziertem MAU-Fallback `TEAMS21`, wenn Microsoft ihn anbietet. Nur IPMIView und DJI Assistant 2 bleiben manuell.

```bash
bash scripts/report_update_coverage.sh   # Abdeckungsbericht
bash build_inventory.sh                  # APPLICATIONS.md neu erstellen
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

### Eigentümer (GitHub + Cloud-Schicht)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
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
- **`mas upgrade` muss `sudo` verwenden** unter macOS 26.x (CVE-2025-43411).
- **Bash 3.2+** überall — keine `declare -A`, `mapfile` oder `readarray`.
