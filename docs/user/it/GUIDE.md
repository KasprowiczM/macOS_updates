# Guida utente (italiano)

**Aggiornamenti macOS 2.0.10** · Mac con Apple Silicon · macOS 13 o successivo

## Cosa fa

Una esecuzione aggiorna, in quest'ordine:

1. app dell'App Store
2. strumenti del Terminale (npm, bun e strumenti da riga di comando che si aggiornano da soli)
3. formule e app di Homebrew
4. app da internet: le app scaricate dal sito del produttore, aggiornate dal feed di aggiornamento del produttore, con un download diretto verificato o con l'aggiornatore dell'app stessa
5. l'elenco delle tue app (aggiornato)
6. macOS, sempre per ultimo

Non ti chiede di approvare ogni app. Agisce solo su ciò che è già installato.

## Cosa non fa mai

- Non chiude mai un'app che hai aperta. Quell'app viene segnalata in "Serve te".
- Non installa mai un'app che non hai. (La scheda facoltativa Catalogo è l'unico posto che può installare, e solo ciò che scegli tu.)
- Non si fida mai ciecamente di un download. Un download deve arrivare da un host consentito, avere una firma del codice valida e superare Gatekeeper.
- Non ferma tutto perché un elemento è fallito. Gli altri elementi, i passi successivi e l'aggiornamento di macOS vengono eseguiti comunque.

## Aprire l'interfaccia

```bash
mac-update
```

In un terminale si apre l'interfaccia. In uno script, via SSH senza terminale, o con `MAC_UPDATE_NONINTERACTIVE=1`, ottieni invece il solo testo. `mac-update run` dà sempre il solo testo. `mac-update --cli` (anche `--plain`) equivale a `mac-update run`, `mac-update --tui` equivale a `mac-update` da solo, e `macos-update` è lo stesso comando con un nome più lungo. Funzionano tutti da qualsiasi cartella. La finestra deve essere di almeno 40 colonne per 12 righe. Più grande è meglio: se lasci attiva l'opzione «Adatta la finestra automaticamente», all'avvio l'interfaccia chiede al terminale 120 per 36 e ripristina la dimensione quando esci.

Spostati con i tasti freccia. Invio apre o conferma, Tab passa al riquadro successivo, Esc torna indietro, da `1` a `7` saltano a una scheda, `?` apre l'aiuto, `L` mostra il registro completo, `q` esce. Funziona anche il mouse. La riga in basso elenca sempre i tasti utilizzabili in quel momento.

## Le schede

```
 Aggiornamenti macOS                          Ultima volta: completata, 2 h fa
 Panoramica  App  Catalogo  Cronologia  Impostazioni  Diagnostica  Aiuto
 +- Gruppi di aggiornamento ------------------------------------------+
 | > v Controllo del sistema   ############  fatto                    |
 |   v App Store               ############  v3 .5                    |
 |   v Strumenti del Terminale ############  v2 .9                    |
 |   * Homebrew                ######......  4/9  v1 .3               |
 |   . App da internet         ............  in attesa                |
 |   . Elenco delle app        ............  in attesa                |
 |   . Sistema macOS           ............  in attesa                |
 +--------------------------------------------------------------------+
   [ Aggiorna tutto ]   [ Anteprima (nessuna modifica) ]
   v aggiornate  . già aggiornate  ! serve te  x errore
```

Questo è un disegno semplificato. La schermata vera usa colori e simboli.

| Scheda | A cosa serve |
|--------|--------------|
| **Panoramica** | Avviare un aggiornamento. Mostra ogni gruppo con l'avanzamento in tempo reale (fatti su totale) e, durante l'esecuzione, un elenco scorrevole delle app al suo interno. Invio o Spazio su un gruppo lo attiva o lo disattiva per la prossima esecuzione. Un pannello laterale mostra l'ultima esecuzione, cosa serve ancora da te, la prossima esecuzione automatica e lo stato di questo Mac. |
| **App** | Ogni app e pacchetto trovati su questo Mac (le app di supporto e quelle in background sono escluse). Scegli come aggiornare ciascuno. |
| **Catalogo** | Tutte le app testate: prima quelle che si possono ancora aggiungere, poi quelle già installate (solo mostrate). Non viene selezionato nulla finché non scegli tu, e il programma di installazione chiede prima di ogni modifica. Le esecuzioni di aggiornamento non lo usano mai. |
| **Cronologia** | Le esecuzioni precedenti, dalla più recente, ciascuna con il suo risultato. Seleziona un'esecuzione per vedere cosa è stato aggiornato e cosa ha richiesto te. Invio ne apre il registro completo. |
| **Impostazioni** | Cosa aggiornare, limiti di sicurezza, esecuzioni automatiche, lingua e aspetto. Ogni modifica viene salvata subito. |
| **Diagnostica** | Controlli che puoi eseguire: controlla questo Mac, controlla i requisiti, come vengono aggiornate le app (una tabella di tutte le app con il modo in cui è stato individuato il metodo), controlla i feed di aggiornamento, ricrea l'elenco delle app, completa gli aggiornamenti interrotti, cerca un aggiornamento del programma. |
| **Aiuto** | Una breve guida: primi passi, come funziona l'aggiornamento, a cosa serve ogni scheda, cosa significa "Serve te". |

## Eseguire un aggiornamento

- **Aggiorna tutto** controlla e aggiorna ogni gruppo attivo.
- **Anteprima (nessuna modifica)** esegue gli stessi passi e mostra cosa succederebbe. Non installa nulla e non scrive la cronologia.

Durante l'esecuzione vedi ogni gruppo e ogni app: controllo, download, verifica, installazione. Premi `L` per il registro completo. **Stop** termina l'esecuzione in sicurezza: le app già aggiornate restano aggiornate.

Le domande (per esempio un riavvio) aspettano la tua risposta. Se non rispondi in tempo, viene usata la risposta più sicura. La password di amministratore si digita nel Terminale e non viene mai salvata né mostrata.

La schermata del risultato elenca:

- **Aggiornate**: ora sono al passo.
- **Già aggiornate**: non serviva nulla.
- **Serve te**: vedi sotto.

## Come vengono aggiornate le app da internet

- Le app con un download verificato del produttore (per esempio Claude e Antigravity IDE) vengono installate direttamente invece di essere aperte e attese. Se il download fallisce, si usa ancora l'updater dell'app.
- Un'app aperta perché si aggiorni da sola viene chiusa non appena il suo aggiornamento è pronto (Warp), invece di attendere tutto il tempo.
- Chrome durante un rilascio graduale viene segnalato subito quando l'updater di Google ha già risposto «nessun aggiornamento» per la tua versione.
- Le app Google (Gemini, Chrome, Google Drive) mostrano quando l'updater di Google ha controllato l'ultima volta e quando controllerà di nuovo, oppure che l'app si è aggiornata da sola.
- Un'app Homebrew che era aperta e si è già aggiornata da sola viene segnalata aggiornata, senza avviso.
- Quando macOS blocca un'app in **Elementi login ed estensioni** (si chiude subito dopo l'apertura), il risultato lo dice e indica dove consentirla: Impostazioni di Sistema › Generali › Elementi login ed estensioni.

## Impostazioni per singola app

Apri la scheda **App**. Digita `/` per cercare per nome o origine. Premi Invio su un'app. Spazio ne seleziona più d'una, così puoi cambiarle insieme.

| Modalità | Significato |
|----------|-------------|
| **automatica** | Il programma la aggiorna per te. È l'impostazione predefinita. |
| **manuale** | Il programma ti avvisa soltanto quando c'è un aggiornamento in attesa. |
| **salta** | Il programma non la tocca. |

Dove un'app ha più di un'origine puoi anche scegliere l'**origine preferita**: origine predefinita, Homebrew, App Store, sito del produttore o aggiornatore integrato. La colonna **Metodo** mostra come il programma conosce l'app: verificato (nell'elenco delle app testate dal programma), rilevato automaticamente (trovato da una ricevuta dell'App Store, da Homebrew, da un feed di aggiornamento o da un aggiornatore integrato) o manuale (nulla riconosciuto). L'impostazione «App appena trovate» decide cosa succede alle app che un'analisi trova e che non sono nell'elenco delle app testate: in base alla certezza (automatico quando il metodo di aggiornamento è chiaro, altrimenti manuale), sempre automatico o sempre manuale.

Se l'elenco è vuoto, scegli **Analizza ora**. L'analisi legge soltanto il tuo Mac.

Le tue scelte sono salvate in `~/.config/mac-update/overrides.tsv`, una riga per app: gruppo, nome, modalità, origine (separati da tabulazioni). Elimina il file per riportare ogni app su automatica.

## Impostazioni

Scegli un profilo per partire in fretta: **Automatico completo** (tutto), **Prudente** (nessun aggiornamento di macOS, nessun grande salto di versione), **Solo controllo** (non viene installato nulla). Qualsiasi modifica manuale mostra **Personalizzato**.

| Sezione | Voci |
|---------|------|
| Cosa aggiornare | Un interruttore per gruppo; Solo controllo, mai installare; Consenti grandi aggiornamenti (se disattivato resti sulla versione principale attuale); Aggiornamenti macOS: installa, solo avvisa o disattivato (prima di riavviare viene sempre chiesto) |
| App e origini | App appena trovate (in base alla certezza, automatico, manuale); Modalità e origine per app (apre la scheda App); App escluse (`config/inventory_exclusions.txt`); Strumenti npm seguiti (`config/npm_global_clis.txt`) |
| Esecuzioni automatiche | Automazione giornaliera (disattivata per impostazione predefinita, senza un orario preimpostato): quando eseguire (ogni giorno all'ora che scegli, all'accesso, oppure entrambi) e la notifica dopo un'esecuzione (dopo ogni esecuzione, solo se qualcosa richiede me, mai); Prova ora |
| Controlli di sicurezza | Attesa chiusura delle app (s); Scarica dai siti dei produttori; Spazio libero minimo (GB, predefinito 15); Livello minimo della batteria (%, predefinito 30) |
| Rete e velocità | Riusa i controlli per (ore); Tempo per rispondere (s, predefinito 120); Tempo massimo App Store (s) |
| Notifiche e rapporti | Avviso al termine; Apri l'ultimo registro; Registri da conservare (predefinito 30) |
| Lingua e aspetto | Lingua (English, Polski, Deutsch, Español, Français, Italiano, Português; segue la lingua del sistema finché non ne scegli una); Colori; Colore di risalto (blu per impostazione predefinita, viola, ambra, verde salvia, rosa, grafite); Spaziatura; Caratteri semplici; Adatta la finestra automaticamente; Mouse; Pannello di aiuto aperto all'avvio |
| Sistema e manutenzione | Ritardo Microsoft Office (giorni); Tieni il Mac attivo; Ricrea l'elenco delle app; Aggiorna questo programma; Esporta impostazioni; Importa impostazioni; Ripristina i valori predefiniti |

Le impostazioni sono salvate in `~/.local/state/mac-update/tui-settings.json`, e la tua lingua in `~/.config/mac-update/lang`. Una voce impostata da una variabile d'ambiente mostra quella variabile e non si può cambiare nella finestra. "Attesa chiusura delle app" vale per le app avviate dal programma stesso.

I colori seguono il tuo terminale. L'impostazione predefinita, **automatico**, chiede al terminale se la sua finestra è chiara o scura e usa la combinazione adatta. L'aspetto chiaro lascia alla pagina lo sfondo bianco e il colore del testo propri del terminale; solo la barra in alto, la barra dei tasti, la riga selezionata e le finestre di dialogo sono grigio chiaro, e ogni colore resta leggibile su una finestra bianca. Quello scuro non è cambiato. Uno «scuri» salvato da una versione precedente viene trattato una volta come automatico; se vuoi sempre lo scuro, sceglilo di nuovo in Impostazioni, Lingua e aspetto, Colori.

## Cosa significa "Serve te"

Ogni riga della schermata del risultato ha un motivo e un passo successivo.

| Motivo | Cosa fare |
|--------|-----------|
| **L'app è aperta** | Chiudi l'app ed esegui di nuovo l'aggiornamento. Il programma non la chiude mai per te. |
| **Serve accedere** (App Store) | Apri App Store, accedi, poi esegui di nuovo l'aggiornamento. |
| **Serve una password** | Esegui di nuovo l'aggiornamento da un terminale e inserisci la password di amministratore quando richiesto. Le esecuzioni automatiche non possono chiederla, quindi lo segnalano. |
| **Serve un riavvio** | L'aggiornamento è installato, ma ha effetto dopo un riavvio. Riavvia il Mac quando ti fa comodo. |
| **Nessun metodo automatico** | Non esiste un modo automatico sicuro per aggiornare questa app. Apri l'app e usa la sua opzione «Cerca aggiornamenti». |
| **Il download non è terminato** | Controlla la connessione a internet ed esegui di nuovo l'aggiornamento. |
| **Somma di controllo diversa** | Il file non corrispondeva alla sua somma di controllo, quindi non è stato installato nulla. Riprova più tardi. Se continua a fallire, aggiorna l'app a mano. |
| **Modalità manuale** | Hai impostato questa app su manuale. Aggiornala tu, oppure passala ad automatica nella scheda App. |
| **Le informazioni di aggiornamento del produttore non erano raggiungibili** | Riprova più tardi. Il sito del produttore potrebbe essere fuori servizio. |
| **È disponibile una nuova versione principale** | I grandi aggiornamenti sono disattivati. Consentili in Impostazioni oppure aggiorna a mano. |
| **Spazio su disco insufficiente / batteria troppo scarica** | Libera un po' di spazio, oppure collega l'alimentatore, poi esegui di nuovo. |
| **Ha impiegato troppo tempo** | Esegui di nuovo. Apri il registro completo (`L`) se si ripete. |
| **È stato aperto l'aggiornatore dell'app** | Completa l'aggiornamento nella finestra aperta dall'app. |

Alcune app installano il loro aggiornamento quando si chiudono. Se il programma ha avviato lui stesso una di queste app, la chiude appena l'aggiornamento è pronto. Un'app che hai aperto tu non viene mai chiusa.

Se il motivo dice "non è noto", apri il registro completo con `L`.

L'intestazione, la Panoramica e la Cronologia mostrano sempre gli stessi numeri. Un'app per iPad che l'App Store sta ancora installando dopo l'aggiornamento è indicata come «ancora in installazione nell'App Store», senza nulla da cliccare: aspetta qualche minuto e controlla di nuovo. Un programma di aggiornamento in background avviato ma senza risultato è indicato come «nessun risultato registrato, niente da cliccare»; la sua versione viene riletta dopo, così un aggiornamento concluso risulta aggiornato.

## Dove si trovano le cose

| Cosa | Dove |
|------|------|
| Registri delle esecuzioni (si conservano i 30 più recenti) | `~/.local/state/mac-update/logs/` |
| Le tue scelte per app, la lingua e l'elenco delle tue app | `~/.config/mac-update/` (`overrides.tsv`, `lang`, `reports/`) |
| Il programma | `~/.local/share/mac-update/` |

Per opzioni, variabili d'ambiente e risoluzione dei problemi, vedi [OPERATIONS.md](OPERATIONS.md). Per installare, aggiornare o rimuovere il programma, vedi [INSTALL.md](../../INSTALL.md) (in English) e [UNINSTALL.md](../../UNINSTALL.md).
