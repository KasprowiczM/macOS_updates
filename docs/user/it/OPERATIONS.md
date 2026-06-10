# Manuale operativo

Guida per l'operatore — manutenzione quotidiana e settimanale del macOS Updates.

## Piattaforma

**Solo Apple Silicon (arm64).** Gli script terminano immediatamente sui Mac Intel.

## Aggiornamento settimanale

```bash
cd ~/Dev_Env/macOS_updates
bash update_all.sh
```

In caso di errore, consultare: `logs/update_all_<timestamp>.log` (ultime 30 esecuzioni conservate).

## Ordine della pipeline (`update_all.sh`)

| Passo | Script / azione | Flag di salto |
|-------|-----------------|---------------|
| 0 | prescan → `APPLICATIONS.md` | `--skip-prescan` |
| 1 | `update_system.sh` | `--skip-system` |
| 2 | `update_appstore.sh` | `--skip-appstore` |
| 3 | `update_npm_cli.sh` | `--skip-npm` |
| 4 | `update_brew.sh` | `--skip-brew` |
| 5 | `update_internet_apps.sh` | `--skip-internet` |
| 6 | postupdate → `APPLICATIONS.md`, `UPDATES.md` | `--skip-postupdate` |

Anteprima senza modifiche: `bash update_all.sh --dry-run -y`

## Analisi degli errori

| Passo fallito | File da controllare |
|---------------|---------------------|
| App Store | `$SESSION_DIR/appstore_diag.txt`, snapshot del log |
| App Internet | `$SESSION_DIR/internet_diag.txt`, `internet_before/after.txt` |
| Homebrew | `$SESSION_DIR/brew_*_before/after.txt` |
| Qualsiasi | `logs/update_all_*.log` (snapshot allegati con codice di uscita ≠ 0) |

Accessibilità App Store assente → codice di uscita `2`; usare `--treat-appstore-ax-as-warning` o concedere Accessibilità al terminale.

Riferimento completo dei codici di uscita: `docs/agents/exit_codes.md`.

## Overlay privato (Proton Drive)

Dopo la modifica locale dei file privati:

```bash
bash dev_sync/dev-sync-export.sh
bash dev_sync/dev-sync-verify-full.sh
bash dev_sync/dev-sync-prune-excluded.sh   # should report zero candidates
```

## Nuovo Mac

**Utente pubblico:**

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
bash update_all.sh
```

**Proprietario (overlay cloud):**

```bash
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

Inventario: `bash build_inventory.sh`

## Checklist pre-aggiornamento

- [ ] Accesso all'App Store effettuato (`mas account` o app App Store)
- [ ] Terminale con Accessibilità (per la traccia 2 delle app iPad)
- [ ] Spazio su disco ≥ 20 GB per aggiornamenti macOS di grandi dimensioni
- [ ] `sudo` disponibile per `mas upgrade` e aggiornamenti di sistema

## Verifica post-aggiornamento

```bash
mas outdated
brew outdated
softwareupdate -l
```

Avviare un campione di app critiche (browser, VPN, IDE) se il passo Internet ha segnalato avvisi.
