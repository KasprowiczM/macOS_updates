# Guida utente (Italiano)

**Versione:** 1.8.2 · **Apple Silicon, macOS 13+**

## Interfaccia terminale

In un terminale interattivo, `bash update_all.sh` apre il pannello e mostra la procedura iniziale fino al completamento. `bash setup.sh` apre la procedura e `bash build_inventory.sh` la vista inventario. La procedura si riapre dalla navigazione. Completamento e impostazioni visive sono salvati senza autorizzare aggiornamenti. `--cli` seleziona la precedente interfaccia testuale e `--tui` richiede esplicitamente il pannello. Opzioni come `--dry-run` restano nella CLI; non combinare `--tui` con altre opzioni. `--tui` richiede un terminale funzionante e Python. Gli avvii non interattivi o senza TTY restano nella CLI.

Scegli i gruppi prima di iniziare. A sinistra c’è la navigazione, al centro azioni e output, a destra guida e dettagli in ogni schermata. Un solo lavoro è supervisionato alla volta; restano necessarie le conferme esistenti. Le impostazioni includono lingua, tema, ASCII e dimensione automatica. `?` apre la guida, Ctrl+P la tavolozza e `c` copia comando, output o riepilogo selezionato. Ctrl+V incolla solo nella finestra di risposta; Invio invia. L’input è mascherato quando il processo disabilita l’eco.

Servono almeno 80 colonne e 24 righe. Per impostazione predefinita viene richiesta una dimensione minima di 140 colonne e 38 righe sui terminali compatibili e quella originale all’uscita; il terminale può ignorare le richieste. La dimensione automatica si può disattivare.

## Configurazione sicura e fonti delle applicazioni

`bash setup.sh --inspect` verifica la disponibilità senza installare dipendenze, modificare profili o configurare Touch ID. Uno strumento mancante rende indisponibile la funzione dipendente. Nel terminale, `bash setup.sh --install-dependencies` mostra le dipendenze facoltative e chiede prima di ogni installazione; `bash setup.sh --configure-shell` mostra separatamente la modifica del profilo. Rifiutare una dipendenza non blocca funzioni indipendenti. Se Python manca, installarlo esplicitamente prima dell’inventario. `mas` mancante o vecchio viene segnalato senza installazione o aggiornamento automatico.

Il catalogo facoltativo non seleziona nulla inizialmente. KeePassXC può essere installato tramite Homebrew con consenso separato dopo controlli aggiornati della fonte e dell’assenza. L’anteprima mostra comando ed effetti dichiarati; la prova è la ricevuta Homebrew, non l’accettazione di una ricetta del produttore. Le altre voci mantengono percorsi ufficiali verificati. Le applicazioni esistenti non vengono mai migrate automaticamente. Le raccomandazioni dipendono dai dati disponibili sulle versioni stabili.

Se il risultato di un’installazione dal catalogo è incerto, riapri il catalogo per una nuova verifica di recupero. Non eliminare blocchi o registri manualmente. KeePassXC tramite Homebrew richiede dati stabili verificati entro sette giorni; altrimenti rimane il percorso manuale.

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
2. `bash build_inventory.sh --cli`
3. `bash scripts/scaffold_internet_app.sh "/path/to/Observed.app" --json`
4. Esamina la proposta JSON non eseguibile; un’implementazione successiva richiede revisione e `bash run_tests.sh`.

Sostituisci l’esempio con il percorso esatto dell’app installata. Il comando mostra una proposta con dati privati rimossi e non eseguibile da esaminare. L’esportazione facoltativa richiede di ripeterlo con `--export --accept PREVIEW_ID` dopo aver verificato l’identificatore mostrato. L’attivazione degli aggiornamenti richiede un’implementazione revisionata e prove di accettazione separate.

## Risoluzione problemi

| Problema | Soluzione |
|----------|----------|
| Mac Intel | Non supportato |
| Catalogo errato | `bash build_inventory.sh --cli` |
| App non aggiornata | `bash scripts/report_update_coverage.sh` |
| `APPLICATIONS.md` mancante | `build_inventory.sh` o `dev_sync/dev-sync-import.sh` |

Completo: [../../agents/troubleshooting.md](../../agents/troubleshooting.md)

Sono disponibili inventario JSON locale e piani con ambiti specifici. `bash update_all.sh --plan` e `--dry-run` mostrano le stesse decisioni senza scrivere. Una sessione interattiva chiede una volta gli ambiti mostrati; `-y`, EOF e sessioni senza terminale non concedono nuovi permessi. Usa `--preferences` per rivedere o reimpostare le scelte. Gli aggiornamenti conservano fonte e destinazione osservate; conflitti, destinazioni assenti e prove incerte rinviano quel destinatario. `build_inventory.sh --migration --preview` conserva i byte Markdown originali e le note; accetta esplicitamente l’ID mostrato. Gli aggiornamenti generici del produttore restano manuali finché identità e adattatore non sono verificati. Una voce di catalogo non prova installazione né consenso.


## Catalogo facoltativo e prima installazione

I nuovi segnali sulle app sono proposte da verificare, non ricette eseguibili. `bash scripts/scan_update_feeds.sh` mostra un riepilogo aggregato. L’esportazione permette di visualizzare e accettare esplicitamente la proposta; è redatta, resta locale e non viene mai caricata. `bash setup.sh --catalog` apre il catalogo senza selezioni. `-y`, le esecuzioni non interattive e EOF non installano nulla. Nel menu, `check <number>` confronta solo le fonti scelte. I risultati indicano l’ultima versione stabile compatibile confermata e la data, con cache di 24 ore. Un dato sconosciuto resta tale. Una scheda pubblica del Mac App Store non dimostra che l’app sia offerta al tuo account.

Il catalogo facoltativo non seleziona nulla inizialmente. KeePassXC può essere installato tramite Homebrew con consenso separato dopo controlli aggiornati della fonte e dell’assenza. L’anteprima mostra comando ed effetti dichiarati; la prova è la ricevuta Homebrew, non l’accettazione di una ricetta del produttore. Le altre voci mantengono percorsi ufficiali verificati. Le applicazioni esistenti non vengono mai migrate automaticamente. Le raccomandazioni dipendono dai dati disponibili sulle versioni stabili.

## Stato locale degli aggiornamenti con ricette

Il catalogo facoltativo non seleziona nulla inizialmente. KeePassXC può essere installato tramite Homebrew con consenso separato dopo controlli aggiornati della fonte e dell’assenza. L’anteprima mostra comando ed effetti dichiarati; la prova è la ricevuta Homebrew, non l’accettazione di una ricetta del produttore. Le altre voci mantengono percorsi ufficiali verificati. Le applicazioni esistenti non vengono mai migrate automaticamente. Le raccomandazioni dipendono dai dati disponibili sulle versioni stabili.

`--dry-run` mostra un riepilogo leggibile di massimo 10 elementi. `--dry-run --json-summary` o `--plan` fornisce il piano JSON completo. L’anteprima non concede permessi e non esegue aggiornamenti.

La schermata dei consensi mostra dieci elementi idonei per pagina. Inserisci numeri come `1,3` per autorizzare solo le azioni mostrate; `n` e `p` cambiano pagina. Invio o `q` continua senza nuovi consensi. Il limite di 120 secondi viene spiegato; la scadenza non concede permessi. Gli elementi bloccati sono riepilogati separatamente. Usa `--preferences` per le scelte manuali, ignorate o rimandate. Il registro inizia prima di questa revisione.

## Comandi ed elenco applicazioni

Tab passa tra navigazione, area di lavoro, output e pulsanti inferiori. Le frecce selezionano, Spazio attiva le caselle e Invio aziona il pulsante evidenziato. Le domande aprono automaticamente il campo di risposta. Invia conferma; Annulla chiude il campo senza rispondere.

L’inventario mostra le applicazioni salvate raggruppate per origine, con ricerca, filtri e ordinamento. Salva selezione memorizza le esclusioni senza installare o disinstallare. Riattivare richiede un consenso separato agli aggiornamenti. L’elenco resta visibile dopo la simulazione. Il registro dettagliato è separato dallo stato delle applicazioni.

Informazioni contiene autore, collegamenti e verifica esplicita degli aggiornamenti dello strumento. L’anteprima fissa una revisione. Applica chiude l’interfaccia e chiede conferma nel terminale. Codice modificato, un ramo inatteso o conflitti di file bloccano l’aggiornamento. Le modifiche locali non vengono mai inviate al repository dell’autore.

La modalità automatica usa il consenso salvato se copre il gruppo idoneo; altrimenti offre una revisione AUTO separata. Le finestre native autorizzate si aprono in parallelo e i download condividono il gruppo supervisionato; le attività Microsoft e Google sono raggruppate. La gestione App Store e Homebrew resta distinta. DeepSeek Harness rimane manuale; Open Design segnala attualmente un metodo automatico non disponibile. Il produttore sceglie le versioni secondo le impostazioni del canale esistenti. Un cambio di versione non dimostra il completamento verificato. Il lavoro non confermato mantiene il blocco del gruppo e rinvia l’aggiornamento del sistema; Diagnostica offre un recupero esplicito con nuova verifica dell’identità. Il consenso Google comprende tutti i prodotti registrati presso il suo updater, anche fuori catalogo, la cui lista completa è sconosciuta. Questo resta distinto dall’accettazione di una ricetta per una versione precisa. `bash update_all.sh --cli --automatic-internet-batch` presenta la stessa verifica senza interfaccia terminale; aggiungi `--dry-run` per una simulazione senza modifiche.