# Guida utente (Italiano)

**Versione:** 1.6.1 · **Apple Silicon, macOS 13+**

## Configurazione sicura e fonti delle applicazioni

`bash setup.sh --inspect` verifica la disponibilità senza installare dipendenze, modificare profili o configurare Touch ID. Uno strumento mancante rende indisponibile la funzione dipendente. Nel terminale, `bash setup.sh --install-dependencies` mostra le dipendenze facoltative e chiede prima di ogni installazione; `bash setup.sh --configure-shell` mostra separatamente la modifica del profilo. Rifiutare una dipendenza non blocca funzioni indipendenti. Se Python manca, installarlo esplicitamente prima dell’inventario. `mas` mancante o vecchio viene segnalato senza installazione o aggiornamento automatico.

Il rapporto normale mostra le applicazioni installate. `bash scripts/report_update_coverage.sh --show-supported` mostra le ricette assenti. Non è ancora un menu di installazione. Una ricevuta App Store per CapCut mantiene quella fonte anche senza cask. Senza proprietà Homebrew confermata viene proposta una fonte, senza adozione o installazione. Risoluzione completa e selezione interattiva delle fonti appartengono alle fasi successive.

## Cosa fa

macOS Updates orchestra gli aggiornamenti su **Mac Apple Silicon con macOS 13+**:

1. Pre-scansione e inventario
2. App Store (`sudo mas upgrade <app-id>` + Track 2 GUI separato)
3. Prima le CLI native esistenti, poi Node/Bun e alternative npm
4. Homebrew (greedy solo per i cask registrati come `brew_cask`)
5. App installate: handler diretti, CLI o trigger integrati
6. Post-aggiornamento atomico di inventario/cronologia
7. macOS (`softwareupdate -i <label> -R`) per ultimo; rinviato dopo un errore bloccante o senza autorizzazione

**Non installa nuove applicazioni.** Ogni Mac costruisce il proprio inventario (`build_inventory.sh`).

## Installazione

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Report copertura

```bash
bash scripts/report_update_coverage.sh
```

Stati: **verified direct**, **triggered-unverified**, **externally managed**, **manual**, **unknown**. Un avvio silenzioso non prova l'aggiornamento. Inkscape usa Homebrew; UniFi/WiFiman/Picsart Track 2; Office `msupdate`; Teams il proprio updater con fallback MAU `TEAMS21` osservato e verificato. Attualmente nessuna app registrata è «manual»; IPMIView usa App Store Track 2.

## Aggiungere un'app Internet

1. Installare l'app sul Mac.
2. `bash build_inventory.sh`
3. `bash scripts/scaffold_internet_app.sh "Nome" silent_launch`
4. `bash run_tests.sh`

## Risoluzione problemi

| Problema | Soluzione |
|----------|----------|
| Mac Intel | Non supportato |
| Catalogo errato | `bash build_inventory.sh` |
| App non aggiornata | `bash scripts/report_update_coverage.sh` |
| `APPLICATIONS.md` mancante | `build_inventory.sh` o `dev_sync/dev-sync-import.sh` |

Completo: [../../agents/troubleshooting.md](../../agents/troubleshooting.md)
