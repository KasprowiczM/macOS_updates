# macOS Updates

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

> **v1.0.19** — Produktionsbereiter Ein-Befehl-Updater für **Apple Silicon Macs**. Hält macOS, den App Store, Homebrew und über 40 aus dem Internet heruntergeladene Apps auf dem neuesten Stand — **nur Software, die Sie bereits installiert haben**. **Mehrsprachig** (7 Sprachen). Optionale private Cloud-Schicht über [`dev_sync/`](dev_sync/README.md).

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
| 1 | **System** — `softwareupdate -ia -R` |
| 2 | **App Store** — `sudo mas upgrade` + AppleScript-Fallback |
| 3 | **Native CLI + npm** — Node, Bun, globale npm-Tools |
| 4 | **Homebrew** — `brew upgrade` + Bereinigung |
| 5 | **Internet-Apps** — nur wenn installiert (Chrome, VS Code, Microsoft 365, …) |
| 6 | **Post-Update** — aktualisiert Versionen in `APPLICATIONS.md`, fügt Historie zu `UPDATES.md` hinzu |

**Wichtig:** Updates wirken sich nur auf Software aus, die bereits auf Ihrem Mac installiert ist. Unterstützte, aber fehlende Apps werden gemeldet, nicht installiert.

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
