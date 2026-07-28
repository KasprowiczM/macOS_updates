# Aggiornamenti macOS

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

> **v1.0.21** — Orchestratore di aggiornamenti in un comando per **Mac Apple Silicon con macOS 13+**. Coordina aggiornamenti verificati e segnala onestamente gli avvii degli updater integrati — **solo per software già installato**. **Multilingua** (7 lingue). Livello cloud privato opzionale tramite [`dev_sync/`](dev_sync/README.md).

**Repository pubblico:** [github.com/KasprowiczM/macOS_updates](https://github.com/KasprowiczM/macOS_updates) · Release: [docs/PUBLIC_RELEASE.md](docs/PUBLIC_RELEASE.md)

---

## Installazione con un solo comando (nuovi utenti)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

L'installer clona il repository, chiede di selezionare la **lingua** (italiano disponibile), installa le dipendenze, crea il **tuo** file `APPLICATIONS.md` basandosi sulle app già presenti sul tuo Mac e mostra quali app possono essere aggiornate. Non importa mai l'inventario di un altro utente né installa nuove app per te.

Vedi [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md)

---

## Cosa fa questo strumento

`update_all.sh` esegue sette passaggi:

| Passaggio | Azione |
|------|--------|
| 0 | **Pre-scansione** — rileva le app installate → aggiorna `APPLICATIONS.md` |
| 1 | **App Store** — Track 1: `sudo mas upgrade`; Track 2: GUI AppleScript per app iPad |
| 2 | **CLI Nativi + npm** — Node, Bun, strumenti globali npm |
| 3 | **Homebrew** — formule e cask (`--greedy`) + pulizia |
| 4 | **App Internet** — handler verificati, CLI del fornitore e trigger onesti |
| 5 | **Post-aggiornamento/cronologia** — inventario e cronologia atomici |
| 6 | **macOS (per ultimo)** — `softwareupdate -ia -R`; saltato se un passaggio precedente fallisce |

**Importante:** Gli aggiornamenti modificano solo il software già installato sul tuo Mac. Le app supportate ma non presenti vengono segnalate, non installate.

La copertura distingue **verified direct**, **triggered-unverified**, **externally managed**, **manual** e **unknown**; avviare un'app non dimostra l'aggiornamento. Inkscape usa Homebrew Cask; UniFi, WiFiman e Picsart App Store Track 2; Office `msupdate`; Teams il proprio updater con fallback MAU `TEAMS21` osservato e verificato quando Microsoft lo offre. Solo IPMIView e DJI Assistant 2 restano manuali.

```bash
bash scripts/report_update_coverage.sh   # report di copertura
bash build_inventory.sh                  # ricostruisce APPLICATIONS.md
```

---

## Guida rapida

### Nuovo utente (senza cloud)

```bash
# Opzione A — un solo comando (consigliata)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"

# Opzione B — manuale
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh
bash build_inventory.sh
bash update_all.sh
```

### Proprietario (GitHub + cloud)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

---

## Documentazione

| Pubblico | Inizia qui |
|----------|------------|
| Utenti | [docs/user/it/QUICK_START.md](docs/user/it/QUICK_START.md) |
| Installazione / Disinstallazione | [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md) |
| Sviluppatori | [docs/agents/scripts.md](docs/agents/scripts.md) |
| Sincronizzazione cloud | [dev_sync/README.md](dev_sync/README.md) |
| Contesto IA | `AGENTS.md` |

---

## Note tecniche critiche

- **`softwareupdate` deve usare `-R`** — altrimenti gli aggiornamenti vengono scaricati ma mai applicati.
- **`mas upgrade` deve usare `sudo`** su macOS 26.x (CVE-2025-43411).
- **Bash 3.2+** ovunque — nessun `declare -A`, `mapfile` o `readarray`.
