# Guida utente (Italiano)

**Versione:** 1.7.7 · **Apple Silicon, macOS 13+**

## Configurazione sicura e fonti delle applicazioni

`bash setup.sh --inspect` verifica la disponibilità senza installare dipendenze, modificare profili o configurare Touch ID. Uno strumento mancante rende indisponibile la funzione dipendente. Nel terminale, `bash setup.sh --install-dependencies` mostra le dipendenze facoltative e chiede prima di ogni installazione; `bash setup.sh --configure-shell` mostra separatamente la modifica del profilo. Rifiutare una dipendenza non blocca funzioni indipendenti. Se Python manca, installarlo esplicitamente prima dell’inventario. `mas` mancante o vecchio viene segnalato senza installazione o aggiornamento automatico.

Questa guida descrive macOS Updates 1.7.7. Il gestore agisce solo su obiettivi installati con fonte osservata e dopo una nuova approvazione. Gli adattatori generici nativi e dei produttori restano manuali finché non sono disponibili ricette verificate. Il catalogo pubblico facoltativo comprende 48 prodotti e offre link ufficiali verificati per l’acquisizione manuale; non esistono ricette approvate per la prima installazione automatica. L’elenco dei metodi qui sotto descrive capacità, non autorizza l’esecuzione. Il rapporto normale riguarda le applicazioni installate. `bash scripts/report_update_coverage.sh --show-supported` resta un elenco di riferimento. Il menu facoltativo si apre con `bash setup.sh --catalog` e non seleziona nulla. Dopo l’anteprima e una nuova approvazione, puoi acquisire manualmente un’app tramite un link ufficiale verificato. Cambiare la fonte di un’app esistente richiede una migrazione manuale. Una ricevuta App Store per CapCut conserva quella fonte. Un’app locale senza proprietà Homebrew confermata non viene adottata automaticamente.

## Cosa fa

macOS Updates orchestra gli aggiornamenti su **Mac Apple Silicon con macOS 13+**:

1. Pre-scansione e inventario
2. App Store (`sudo mas upgrade <app-id>` + Track 2 GUI separato)
3. Prima le CLI native esistenti, poi Node/Bun e alternative npm
4. Homebrew (greedy solo per i cask registrati come `brew_cask`)
5. App installate: operazioni circoscritte dopo il consenso; aggiornamenti dei produttori non accettati restano manuali
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


## Aggiungere un'app Internet

1. Installare l'app sul Mac.
2. `bash build_inventory.sh`
3. `bash scripts/scaffold_internet_app.sh "/path/to/Observed.app" --json`
4. Esamina la proposta JSON non eseguibile; un’implementazione successiva richiede revisione e `bash run_tests.sh`.

Sostituisci l’esempio con il percorso esatto dell’app installata. Il comando mostra una proposta con dati privati rimossi e non eseguibile da esaminare. L’esportazione facoltativa richiede di ripeterlo con `--export --accept PREVIEW_ID` dopo aver verificato l’identificatore mostrato. L’attivazione degli aggiornamenti richiede un’implementazione revisionata e prove di accettazione separate.

## Risoluzione problemi

| Problema | Soluzione |
|----------|----------|
| Mac Intel | Non supportato |
| Catalogo errato | `bash build_inventory.sh` |
| App non aggiornata | `bash scripts/report_update_coverage.sh` |
| `APPLICATIONS.md` mancante | `build_inventory.sh` o `dev_sync/dev-sync-import.sh` |

Completo: [../../agents/troubleshooting.md](../../agents/troubleshooting.md)

Sono disponibili inventario JSON locale e piani con ambiti specifici. `bash update_all.sh --plan` e `--dry-run` mostrano le stesse decisioni senza scrivere. Una sessione interattiva chiede una volta gli ambiti mostrati; `-y`, EOF e sessioni senza terminale non concedono nuovi permessi. Usa `--preferences` per rivedere o reimpostare le scelte. Gli aggiornamenti conservano fonte e destinazione osservate; conflitti, destinazioni assenti e prove incerte rinviano quel destinatario. `build_inventory.sh --migration --preview` conserva i byte Markdown originali e le note; accetta esplicitamente l’ID mostrato. Gli aggiornamenti generici del produttore restano manuali finché identità e adattatore non sono verificati. Una voce di catalogo non prova installazione né consenso.


## Catalogo facoltativo e prima installazione

I nuovi segnali sulle app sono proposte da verificare, non ricette eseguibili. `bash scripts/scan_update_feeds.sh` mostra un riepilogo aggregato. L’esportazione permette di visualizzare e accettare esplicitamente la proposta; è redatta, resta locale e non viene mai caricata. `bash setup.sh --catalog` apre il catalogo senza selezioni. `-y`, le esecuzioni non interattive e EOF non installano nulla. Nel menu, `check <number>` confronta solo le fonti scelte. I risultati indicano l’ultima versione stabile compatibile confermata e la data, con cache di 24 ore. Un dato sconosciuto resta tale. Una scheda pubblica del Mac App Store non dimostra che l’app sia offerta al tuo account.

Il catalogo pubblico conta 47 righe del registro per 48 prodotti e zero ricette approvate per la prima installazione automatica. Dopo l’anteprima e una nuova conferma, puoi scegliere link ufficiali verificati per l’acquisizione manuale. Aprire una pagina non installa l’app. Cambiare la fonte di un’app esistente richiede migrazione manuale. L’InstallPlan separato mostra fonte, destinazione, versione, requisiti e permessi; licenza e costo sconosciuti sono indicati come tali. Ogni ricetta futura richiederà approvazione prima dell’attivazione. Il catalogo non promette l’installazione automatica di tutti i prodotti.

## Stato locale degli aggiornamenti con ricette

Questa guida descrive macOS Updates 1.7.7. Il catalogo pubblico comprende 48 prodotti in 47 righe di registro e zero ricette automatiche approvate per produttori, motore nativo o prima installazione. Il gestore supporta operazioni circoscritte sui target installati dopo il consenso; gli aggiornamenti dei produttori senza ricetta accettata restano manuali. I 48 dossier e le fixture sintetiche non dimostrano accettazione dal vivo. Acquisizione diretta ZIP, installazione esplicita e motore nativo sono implementati; l’accettazione dal vivo T6 e l’attivazione T7 restano in sospeso. Non esistono percorsi force, adopt, migrazione o bootstrap delle dipendenze. Le app utente esistenti sono protette. Le raccomandazioni sono stabili per prodotto, senza classifica universale del canale più rapido. Una scansione incompleta è un avviso, ma i target non sicuri vengono bloccati; controlla il JSON. I metadati Cask dell’host non vengono riparati. Lo scheduler consente al massimo due mutazioni indipendenti tra checkout cooperanti dello stesso utente di sistema; l’esecuzione pubblica resta seriale fino all’accettazione degli effetti indipendenti. L’aggiornamento di sistema acquisisce per ultimo il lock globale esclusivo. Riavvio in sospeso o helper sconosciuto possono bloccare mutazioni fino a una nuova prova di riconciliazione verificata. Non esistono ancora timeout automatico né riconciliazione all’avvio. Consulta la [ricevuta centrale d’implementazione](../../implementation/RECIPE_VERIFICATION_2026-11-14.md). Le app aperte restano protette. DeepSeek Harness è escluso finché non è stabile.

`--dry-run` mostra un riepilogo leggibile di massimo 25 elementi. `--dry-run --json-summary` o `--plan` fornisce il piano JSON completo. L’anteprima non concede permessi e non esegue aggiornamenti.
