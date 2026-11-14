# Avvio rapido (Italiano)

**Richiesto Mac con Apple Silicon** · macOS 13+ · **v1.7.4**

## Configurazione sicura e fonti delle applicazioni

`bash setup.sh --inspect` verifica la disponibilità senza installare dipendenze, modificare profili o configurare Touch ID. Uno strumento mancante rende indisponibile la funzione dipendente. Nel terminale, `bash setup.sh --install-dependencies` mostra le dipendenze facoltative e chiede prima di ogni installazione; `bash setup.sh --configure-shell` mostra separatamente la modifica del profilo. Rifiutare una dipendenza non blocca funzioni indipendenti. Se Python manca, installarlo esplicitamente prima dell’inventario. `mas` mancante o vecchio viene segnalato senza installazione o aggiornamento automatico.

Il rapporto normale mostra le applicazioni installate. `bash scripts/report_update_coverage.sh --show-supported` mostra le ricette assenti. Non è ancora un menu di installazione. Una ricevuta App Store per CapCut mantiene quella fonte anche senza cask. Senza proprietà Homebrew confermata viene proposta una fonte, senza adozione o installazione. Risoluzione completa e selezione interattiva delle fonti appartengono alle fasi successive.

## Installazione con una riga

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Nuovo utente (solo GitHub)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh --inspect
bash build_inventory.sh
bash update_all.sh
```


## Proprietario (GitHub + overlay Proton Drive)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

I file privati (`APPLICATIONS.md`, `UPDATES.md`, `.env`) provengono dall'overlay cloud — non da GitHub.

## Comandi utili

| Comando | Scopo |
|---------|-------|
| `bash update_all.sh --dry-run -y` | Anteprima di tutti i passaggi |
| `bash update_system.sh` | Solo macOS |
| `bash update_appstore.sh` | Solo App Store |
| `bash update_brew.sh` | Solo Homebrew |
| `bash run_tests.sh` | Verifica dell'installazione |

Vedi [GUIDE.md](GUIDE.md) e [OPERATIONS.md](OPERATIONS.md).

La fase B (1.6.2) aggiunge un inventario osservativo facoltativo: `bash build_inventory.sh --shadow`. Salva identità locali, prove delle fonti e scansioni incomplete in JSON privato, senza modificare `APPLICATIONS.md` o gli aggiornamenti. `--dry-run` evita il salvataggio, `--json` restituisce risultati strutturati e più opzioni `--root PERCORSO` indicano le directory. I conflitti restano osservazioni; scelta delle fonti e controlli di esecuzione appartengono alla fase C.
