# macOS Updates

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

> **v1.3.1** — Orchestratore di aggiornamenti in un singolo comando pronto per la produzione per **Mac Apple Silicon con macOS 13–26**. Coordina gli aggiornamenti verificati dei pacchetti per i software già installati su questo Mac. **Multilingue** (7 lingue). Layer cloud privato opzionale tramite [`dev_sync/`](dev_sync/README.md).

**Repository pubblico:** [github.com/KasprowiczM/macOS_updates](https://github.com/KasprowiczM/macOS_updates) · Release: [docs/PUBLIC_RELEASE.md](docs/PUBLIC_RELEASE.md)

---

## Installazione in una singola riga (nuovi utenti)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

L'installer clona il repository, richiede la **selezione della lingua** (italiano disponibile), installa le dipendenze, crea il file `APPLICATIONS.md` in base alle app presenti sul tuo Mac e mostra quali app possono essere aggiornate.

Vedi [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md)

---

## Cosa fa questo strumento

`update_all.sh` esegue sette passaggi:

| Passaggio | Azione |
|-----------|--------|
| 0 | **Scansione preliminare** — rileva le app installate → aggiorna `APPLICATIONS.md` |
| 1 | **App Store** — Traccia 1: `sudo mas upgrade`; Traccia 2: GUI AppleScript per app iPad |
| 2 | **CLI nativa + npm** — Node, Bun, strumenti npm globali |
| 3 | **Homebrew** — Formule e Cask (`--greedy-auto-updates`) + protezione dai downgrade |
| 4 | **App Internet** — gestori verificati, `vendor_latest`, Sparkle Appcast e aggiornamenti diretti |
| 5 | **Post-aggiornamento/Cronologia** — aggiorna inventario e cronologia in modo atomico |
| 6 | **macOS (finale)** — `softwareupdate -ia -R`; omesso in caso di errore precedente |

---

## Configurazione per macchina (**non** arriva con `git pull`)

Due elementi risiedono fuori dal repository e vanno quindi configurati una volta **su ogni
Mac**. Clonare o fare pull su una seconda macchina non li trasferisce — è l'equivoco più
comune in questo progetto.

| Passo | Comando | Perché non può stare in Git |
|-------|---------|-----------------------------|
| Touch ID per `sudo` | `bash scripts/setup_touchid_sudo.sh` | Scrive `/etc/pam.d/sudo_local` — file di proprietà di root, locale alla macchina |
| Esecuzione settimanale in background | `bash scripts/install_launchagent.sh --day 1 --hour 9` | Scrive `~/Library/LaunchAgents/…plist` — per utente e macchina |

`setup_touchid_sudo.sh` non tocca mai `/etc/sudoers` e non concede mai `sudo` senza password.

**L'esecuzione pianificata non installa aggiornamenti macOS né App Store.** Entrambi
richiedono l'autenticazione dell'utente — su Apple Silicon `softwareupdate` richiede le
credenziali del proprietario del volume. Esegui `bash update_all.sh` in modo interattivo per
applicarli.

**Contratto sudo (v1.3.1):** al massimo una richiesta per esecuzione; **mai** senza un TTY di
controllo (viene invece esportata `MAC_UPDATE_NO_SUDO=1`); mai con `--dry-run`.

---

## Funzionalità e variabili di ambiente in v1.3.1

- **Pre-autorizzazione Sudo / Touch ID**: Rileva `pam_tid.so` e mantiene attiva la sessione sudo.
- **Supporto LaunchAgent e Esecuzione in Background**: Supporta `MAC_UPDATE_NO_SUDO=1` per esecuzioni non presidiate.
- **Metodo `vendor_latest`**: Evita il downgrade dei Cask Homebrew per app ad aggiornamento rapido (Cursor, Warp, Antigravity, Proton Mail, Proton Drive, Claude, Comet, ChatGPT).
- **Variabili di controllo**:
  - `MAC_UPDATE_YES=1` (`-y`) — Conferma non interattiva di tutti i passaggi.
  - `MAC_UPDATE_SKIP_SYSTEM=1` (`--skip-system`) — Salta gli aggiornamenti del sistema macOS.
  - `MAC_UPDATE_NONINTERACTIVE=1` — Sopprime i dialoghi interattivi.

```bash
# Esempio di esecuzione automatizzata in background:
MAC_UPDATE_NONINTERACTIVE=1 bash update_all.sh -y --skip-system
```

---

## Guida rapida

### Nuovo utente (senza cloud)

```bash
# Opzione A — una riga (consigliato)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"

# Opzione B — manuale
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh
bash build_inventory.sh
bash update_all.sh
```

---

## Documentazione

| Destinatari | Inizia qui |
|-------------|------------|
| Utenti | [docs/user/it/QUICK_START.md](docs/user/it/QUICK_START.md) |
| Installazione / Disinstallazione | [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md) |
| Sviluppatori | [docs/agents/scripts.md](docs/agents/scripts.md) |
| Sincronizzazione Cloud | [dev_sync/README.md](dev_sync/README.md) |
| Contesto AI | `AGENTS.md` |

---

## Note tecniche critiche

- **`softwareupdate` DEVE usare `-R`** — altrimenti gli aggiornamenti vengono scaricati ma mai applicati.
- **`mas upgrade` DEVE usare `sudo`** su macOS 14.8+/15.7+/26.x (CVE-2025-43411).
- **Bash 3.2+** in tutto il progetto — nessun `declare -A`, `mapfile` o `readarray`.
