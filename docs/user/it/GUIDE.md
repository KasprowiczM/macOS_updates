# Guida utente (Italiano)

**Versione:** 1.7.1 · **Apple Silicon, macOS 13+**

## Configurazione sicura e fonti delle applicazioni

`bash setup.sh --inspect` verifica la disponibilità senza installare dipendenze, modificare profili o configurare Touch ID. Uno strumento mancante rende indisponibile la funzione dipendente. Nel terminale, `bash setup.sh --install-dependencies` mostra le dipendenze facoltative e chiede prima di ogni installazione; `bash setup.sh --configure-shell` mostra separatamente la modifica del profilo. Rifiutare una dipendenza non blocca funzioni indipendenti. Se Python manca, installarlo esplicitamente prima dell’inventario. `mas` mancante o vecchio viene segnalato senza installazione o aggiornamento automatico.

Questa è la versione sorgente 1.7.1 su main, senza un tag di rilascio separato. Il gestore agisce solo su obiettivi installati con fonte osservata e dopo una nuova approvazione. Gli adattatori generici nativi e dei produttori restano manuali finché non sono disponibili ricette verificate. Il catalogo pubblico facoltativo comprende 48 prodotti e offre link ufficiali verificati per l’acquisizione manuale; non esistono ricette approvate per la prima installazione automatica. L’elenco dei metodi qui sotto descrive capacità, non autorizza l’esecuzione. Il rapporto normale riguarda le applicazioni installate. `bash scripts/report_update_coverage.sh --show-supported` resta un elenco di riferimento. Il menu facoltativo si apre con `bash setup.sh --catalog` e non seleziona nulla. Dopo l’anteprima e una nuova approvazione, puoi acquisire manualmente un’app tramite un link ufficiale verificato. Cambiare la fonte di un’app esistente richiede una migrazione manuale. Una ricevuta App Store per CapCut conserva quella fonte. Un’app locale senza proprietà Homebrew confermata non viene adottata automaticamente.

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

La fase C attiva inventario JSON locale e piani con permessi specifici. `bash update_all.sh --plan` e `--dry-run` mostrano le stesse decisioni senza scrivere. Una sessione interattiva chiede una volta gli ambiti mostrati; `-y`, EOF e sessioni senza terminale non concedono nuovi permessi. Usa `--preferences` per rivedere o reimpostare le scelte. Gli aggiornamenti conservano fonte e destinazione osservate; conflitti, destinazioni assenti e prove incerte rinviano quel destinatario. `build_inventory.sh --migration --preview` conserva i byte Markdown originali e le note; accetta esplicitamente l’ID mostrato. Gli aggiornamenti generici del produttore restano manuali finché identità e adattatore non sono verificati. Una voce di catalogo non prova installazione né consenso.


## Catalogo facoltativo e prima installazione

I nuovi segnali sulle app sono proposte da verificare, non ricette eseguibili. `bash scripts/scan_update_feeds.sh` mostra un riepilogo aggregato. L’esportazione permette di visualizzare e accettare esplicitamente la proposta; è redatta, resta locale e non viene mai caricata. `bash setup.sh --catalog` apre il catalogo senza selezioni. `-y`, le esecuzioni non interattive e EOF non installano nulla. Nel menu, `check <number>` confronta solo le fonti scelte. I risultati indicano l’ultima versione stabile compatibile confermata e la data, con cache di 24 ore. Un dato sconosciuto resta tale. Una scheda pubblica del Mac App Store non dimostra che l’app sia offerta al tuo account.

Il catalogo pubblico conta 47 righe del registro per 48 prodotti e zero ricette approvate per la prima installazione automatica. Dopo l’anteprima e una nuova conferma, puoi scegliere link ufficiali verificati per l’acquisizione manuale. Aprire una pagina non installa l’app. Cambiare la fonte di un’app esistente richiede migrazione manuale. L’InstallPlan separato mostra fonte, destinazione, versione, requisiti e permessi; licenza e costo sconosciuti sono indicati come tali. Ogni ricetta futura richiederà approvazione prima dell’attivazione. Il catalogo non promette l’installazione automatica di tutti i prodotti.
