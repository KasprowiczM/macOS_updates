# Operazioni (italiano)

**Aggiornamenti macOS 2.0.10** · per chi usa il programma da un terminale, da uno script o da un'esecuzione automatica.

## Modi di eseguirlo

| Comando | Cosa succede |
|---------|--------------|
| `mac-update` | Apre l'interfaccia (serve un terminale). |
| `mac-update run [options]` | Esecuzione in solo testo. Le opzioni vanno al programma di aggiornamento, per esempio `-y`, `--skip-system`, `--non-interactive`. |
| `mac-update --cli [options]` | Equivale a `mac-update run` (anche `--plain`). |
| `mac-update --tui` | Equivale a `mac-update`: apre l'interfaccia. |
| `mac-update preview` | Passa per ogni passo e stampa cosa succederebbe. Non viene aggiornato nulla. |
| `mac-update scan` | Ricrea l'elenco delle app di questo Mac. Legge soltanto. |
| `mac-update doctor` | Rapporto di idoneità in sola lettura. Nessuna password, nessun registro dell'esecuzione. |
| `mac-update settings` | Apre l'interfaccia sulla scheda Impostazioni. |
| `mac-update update-self` | Cerca una versione più recente di mac-update (`--check`, il valore predefinito, oppure `--prepare`). |
| `mac-update migrate` | Porta le impostazioni da una vecchia copia basata su git: `--preview` (predefinito), `--apply`, `--undo MANIFEST`. |
| `mac-update uninstall` | Rimuove mac-update. Vedi [UNINSTALL.md](../../UNINSTALL.md) (in English). |
| `mac-update version`, `mac-update help` | Versione ed elenco dei comandi. |

`macos-update` è lo stesso comando di `mac-update`, con un nome più lungo. Il programma di installazione collega entrambi in `~/.local/bin`, ed entrambi funzionano da qualsiasi cartella.

`mac-update` chiama `update_all.sh` nella cartella del programma `~/.local/share/mac-update`. Se invece lavori da una copia git, esegui lì `bash update_all.sh`; le opzioni qui sotto sono le stesse. Con `MAC_UPDATE_NONINTERACTIVE=1` l'interfaccia non si apre mai e nulla aspetta una risposta.

## Opzioni di `update_all.sh`

| Opzione | Significato |
|---------|-------------|
| `-y`, `--yes` | Salta la domanda di conferma |
| `-h`, `--help` | Mostra l'elenco delle opzioni |
| `--tui`, `--cli` | Sceglie l'interfaccia o il solo testo. `--tui` fallisce con un messaggio se non c'è un terminale utilizzabile; si possono aggiungere solo `--dry-run` e `--skip-...`. |
| `--dry-run` | Anteprima, non cambia nulla |
| `--doctor` | Rapporto di idoneità. Codice di uscita 0 ok, 10 avvisi, 1 problema |
| `--verify-only` | Confronta le versioni delle app installate con la cronologia, non cambia nulla |
| `--json-summary` | Stampa un riepilogo JSON alla fine |
| `--bootstrap-cli` | Installa anche uno strumento da riga di comando gestito mancante (Node, Bun o nativo). Disattivato per impostazione predefinita. |
| `--skip-prescan` | Salta il primo controllo dell'elenco delle app |
| `--skip-appstore` | Salta le app dell'App Store |
| `--skip-npm` | Salta gli strumenti del Terminale (npm, bun, strumenti nativi da riga di comando) |
| `--skip-brew` | Salta Homebrew |
| `--skip-internet` | Salta le app da internet |
| `--skip-postupdate` | Salta l'aggiornamento dell'elenco delle app e della cronologia |
| `--skip-system` | Salta l'aggiornamento di macOS |
| `--skip-doctor` | Salta `brew doctor` dentro il passo Homebrew |
| `--treat-appstore-ax-as-warning` | Segnala come avviso un permesso Accessibilità mancante |
| `--non-interactive` | Per le esecuzioni automatiche: nessuna domanda (come `MAC_UPDATE_NONINTERACTIVE=1`) |
| `--notify` | Mostra una notifica di macOS al termine dell'esecuzione |

I passi vengono sempre eseguiti in quest'ordine: controllo del sistema, App Store, strumenti del Terminale, Homebrew, app da internet, elenco delle app, macOS. macOS è l'ultimo perché può riavviare il Mac. Se un passo precedente è fallito in modo grave, il passo di macOS aspetta l'esecuzione successiva.

## Variabili d'ambiente

Impostale davanti al comando, per esempio `MAC_UPDATE_MIN_FREE_GB=30 mac-update run`. La maggior parte esiste anche come voce in Impostazioni; una voce impostata da una variabile non si può cambiare nell'interfaccia.

| Variabile | Predefinito | Scopo |
|-----------|-------------|-------|
| `MAC_UPDATE_NONINTERACTIVE` | off | `1`: nessuna interfaccia, nessuna domanda |
| `MAC_UPDATE_DRY_RUN` | off | `1`: come `--dry-run` |
| `MAC_UPDATE_SKIP_APPSTORE`, `_NPM`, `_BREW`, `_INTERNET`, `_SYSTEM`, `_PRESCAN`, `_POSTUPDATE`, `_DOCTOR` | off | `1`: come la corrispondente opzione `--skip-...` |
| `MAC_UPDATE_SYSTEM_MODE` | `auto` | Aggiornamenti di macOS: `auto` li installa, `notify` si limita a segnalarli, `skip` non controlla |
| `MAC_UPDATE_NEW_APP_MODE` | in base alla certezza | `auto` o `manual` per le app appena trovate che non sono nell'elenco delle app testate |
| `MAC_UPDATE_NOTIFY` | off | `1`: notifica al termine. Per le esecuzioni automatiche: `always`, `needs_you` o `never` |
| `MAC_UPDATE_LANG` | lingua del sistema | `en`, `pl`, `de`, `fr`, `es`, `it`, `pt` |
| `MAC_UPDATE_HOME` | `~/.local/share/mac-update` | Cartella del programma |
| `MAC_UPDATE_CONFIG_DIR` | `~/.config/mac-update` | Cartella delle impostazioni |
| `MAC_UPDATE_STATE_DIR` | `~/.local/state/mac-update` | Registri, cache, copie di sicurezza |
| `MAC_UPDATE_LOGS_DIR` | `logs` nella cartella di stato | Registri delle esecuzioni |
| `MAC_UPDATE_OVERRIDES_FILE` | `overrides.tsv` nella cartella delle impostazioni | File delle scelte per app |
| `MAC_UPDATE_MAX_LOGS` | 30 | Registri delle esecuzioni da conservare |
| `MAC_UPDATE_PROMPT_TIMEOUT` | 120 | Secondi per rispondere a una domanda prima che venga usata la risposta più sicura |
| `MAC_UPDATE_MIN_FREE_GB` | 15 | Avvisa ed esegue in modo ridotto sotto questo spazio libero |
| `MAC_UPDATE_MIN_BATTERY` | 30 | Con la batteria sotto questa percentuale, salta il passo di macOS (un'esecuzione automatica viene saltata del tutto) |
| `MAC_UPDATE_NO_CAFFEINATE` | off | `1`: non tenere attivo il Mac durante l'esecuzione |
| `MAC_UPDATE_NO_SUDO_KEEPALIVE` | off | `1`: non mantenere valida la password di amministratore |
| `MAC_UPDATE_SUDO_KEEPALIVE_MAX` | 14400 | Secondi per cui mantenerla valida (da 300 a 14400) |
| `MAC_UPDATE_QUIT_WAIT` | 60 | Secondi di attesa della chiusura di un'app avviata dal programma (da 0 a 300) |
| `MAC_UPDATE_STAGE_WAIT` | 90 | Secondi di attesa perché un'app aperta dal programma installi il proprio aggiornamento (da 0 a 600) |
| `MAC_UPDATE_POST_QUIT_WAIT` | 10 | Secondi di attesa dopo la chiusura di tale app quando il suo aggiornamento è stato preparato |
| `MAC_UPDATE_POST_QUIT_WAIT_IDLE` | 3 | Lo stesso, quando nessun aggiornamento è stato preparato |
| `MAC_UPDATE_OMAHA_WAIT` | 45 | Secondi di attesa della risposta dell'updater di Google (da 0 a 180) |
| `MAC_UPDATE_OMAHA_MAX_AGE_H` | 6 | Ore in cui un controllo dell'updater di Google è considerato recente |
| `MAC_UPDATE_BTM_CHECK` | attivo | `0`: non controllare se macOS blocca un'app in Elementi login ed estensioni |
| `MAC_UPDATE_BTM_TIMEOUT` | 4 | Secondi concessi a quel controllo |
| `MAC_UPDATE_BTM_DUMP`, `MAC_UPDATE_GOOGLE_USER_LOG`, `MAC_UPDATE_GOOGLE_SYS_LOG` | nessuno | Solo per diagnostica e test: un elenco salvato degli elementi login o i file di log dell'updater di Google, letti al posto di quelli reali |
| `MAC_UPDATE_VENDOR_DIRECT` | on | `0`: nessun download diretto dal produttore dell'app |
| `MAC_UPDATE_ALLOW_MAJOR_UPGRADE` | off | `1`: consente i grandi salti di versione, compreso un grande aggiornamento di macOS |
| `MAC_UPDATE_MAU_DEFERRAL_DAYS` | 7 | Giorni di attesa prima di installare una nuova versione di Microsoft Office |
| `MAC_UPDATE_FEED_CACHE_TTL_H` | 24 | Ore per cui riusare le informazioni sulle versioni del produttore |
| `MAC_UPDATE_MAS_UPGRADE_TIMEOUT` | 1800 | Secondi prima che un aggiornamento dell'App Store venga interrotto e segnalato |
| `MAC_UPDATE_DOCTOR_PROBE_AX` | off | `1`: lascia che `doctor` provi il permesso Accessibilità (macOS può mostrare una richiesta) |
| `GITHUB_TOKEN` | nessuno | Facoltativo. Alza il limite di download di GitHub. Impostalo nel profilo della tua shell |

## Esecuzioni automatiche (facoltative)

Le esecuzioni automatiche sono disattivate per impostazione predefinita e non hanno un orario preimpostato. Attivale in **Impostazioni**, sezione **Esecuzioni automatiche**, voce «Automazione giornaliera». Scegli tu:

- quando: ogni giorno all'ora che scrivi (24 ore, per esempio 08:30), all'accesso, oppure entrambi;
- come essere avvisato: dopo ogni esecuzione, solo se qualcosa richiede te (il valore predefinito) oppure mai.

Vedi esattamente cosa verrà installato e confermi prima che venga scritto qualsiasi cosa. «Prova ora» pianifica un'esecuzione in più tra pochi minuti.

Lo stesso da un terminale, con `bash ~/.local/share/mac-update/scripts/install_launchagent.sh`:

```bash
bash scripts/install_launchagent.sh --daily 08:30 --notify needs_you      # every day at 08:30
bash scripts/install_launchagent.sh --daily 08:30 --days 1,3,5            # only on chosen weekdays (numbers 1 to 7)
bash scripts/install_launchagent.sh --at-login --delay-min 10             # at login, after 10 minutes of session time
bash scripts/install_launchagent.sh --once-in 5                           # one test run in 5 minutes
bash scripts/install_launchagent.sh --status                              # is it installed? (--check, or --status --json)
bash scripts/install_launchagent.sh --uninstall                           # remove every mac-update schedule
```

Esegui questi comandi dalla cartella del programma. `--notify` accetta `always`, `needs_you` o `never`. Con `--days` i numeri vanno da 1 a 7 e indicano i giorni della settimana.

Cosa fa un'esecuzione automatica:

- Viene eseguita senza terminale e non fa mai domande.
- Salta gli aggiornamenti di macOS, a meno che tu non li attivi; in quel caso macOS si limita a segnalare cosa è disponibile.
- Si salta da sola quando un'altra esecuzione è in corso, quando il Mac ha la batteria scarica o quando l'ultima esecuzione riuscita risale a meno di 12 ore prima.
- Tutto ciò che richiede la tua password o un riavvio viene saltato e segnalato come "Serve te". Esegui tu `mac-update` per finire.
- Invia una sola notifica, come hai scelto. L'output va in `launchd.out` e `launchd.err` nella cartella dei registri.

## Password

I passi di macOS e dell'App Store possono richiedere la tua password di amministratore. In un terminale il programma la chiede al massimo una volta per esecuzione e la mantiene valida per il resto dell'esecuzione. Non la chiede mai in un'anteprima, e mai senza un terminale (le esecuzioni automatiche saltano invece quei passi). Facoltativo: `bash scripts/setup_touchid_sudo.sh --check` mostra se Touch ID può sostituire la password per `sudo`. Eseguire lo script senza `--check` mostra un'anteprima e chiede prima conferma.

## Dove si trovano le cose

| Cosa | Dove |
|------|------|
| Il programma | `~/.local/share/mac-update` |
| Le tue impostazioni e le scelte per app | `~/.config/mac-update` (`overrides.tsv`, `lang`, `reports/`) |
| Registro di ogni esecuzione | `~/.local/state/mac-update/logs/update_all_<date>_<time>.log` (si conservano i 30 più recenti, modalità 600) |
| Risultato breve dell'ultima esecuzione | `~/.local/state/mac-update/logs/run_summary_latest.json` |
| Impostazioni dell'interfaccia | `~/.local/state/mac-update/tui-settings.json` |
| Output delle esecuzioni automatiche | `~/.local/state/mac-update/logs/launchd.out`, `launchd.err` |

Un'anteprima scrive il suo registro in una cartella temporanea e lascia invariata la tua cronologia. Nell'interfaccia, la scheda **Cronologia** elenca le esecuzioni passate e `L` apre il registro più recente. Arrivi da una vecchia copia basata su git? `mac-update migrate`.

Codice di uscita di `update_all.sh`: `0` quando l'esecuzione è andata bene o ha avuto solo avvisi (un'app che richiede te è un avviso), `1` quando qualcosa è fallito.

## Risoluzione dei problemi

Parti da `mac-update doctor`. Controlla la piattaforma, Python, curl, Homebrew, `mas`, Touch ID, spazio su disco, alimentazione, rete e il programma stesso.

| Problema | Cosa fare |
|----------|-----------|
| `mac-update: command not found` | Apri una nuova finestra del Terminale. Se persiste, `~/.local/bin` non è nel tuo `PATH`: esegui di nuovo il programma di installazione con `--configure-shell`, oppure aggiungi tu quella cartella. |
| `mac-update` avvia un altro programma | Un altro programma con quel nome compare prima nel tuo `PATH`. Il programma di installazione ti avvisa e indica il file di quel programma. Esegui direttamente `~/.local/bin/mac-update`, oppure elimina o rinomina l'altro file. |
| L'interfaccia non si apre | Servono un terminale, Python 3 e un `TERM` diverso da `dumb`. Altrimenti usa `mac-update run`. |
| Il programma di installazione dice che la somma di controllo non corrisponde | Non è stato installato nulla. Riprova più tardi; se si ripete, segnalalo. |
| Un'app è in "Serve te" | Vedi la tabella «Cosa significa "Serve te"» in [GUIDE.md](GUIDE.md). |
| Il passo dell'App Store si ferma con codice di uscita 2 | Al terminale manca il permesso Accessibilità. Consentilo in Impostazioni di Sistema, Privacy e sicurezza, Accessibilità, oppure aggiungi `--treat-appstore-ax-as-warning`. |
| `mas` manca o è troppo vecchio | Il programma lo segnala e non lo installa mai da solo. Installalo tu con Homebrew (`brew install mas`). |
| L'App Store richiede l'accesso | Apri App Store, accedi, esegui di nuovo. |
| Homebrew manca | Installalo da <https://brew.sh>, poi esegui di nuovo. |
| L'elenco delle app manca o è sbagliato | `mac-update scan`. Legge solo il tuo Mac. Non copiare mai l'elenco di un'altra persona. |
| Un'app non viene mai aggiornata | Diagnostica, «Come vengono aggiornate le app», mostra come viene gestita ogni app. Se non c'è un metodo, apri l'app e usa la sua opzione «Cerca aggiornamenti». |
| Le informazioni di aggiornamento di un produttore non sono raggiungibili | Riprova più tardi. Controlla i feed in Diagnostica, «Controlla i feed di aggiornamento». |
| Il Mac è andato in stop durante un'esecuzione | Lascia attiva «Tieni il Mac attivo» (predefinita). |
| Un aggiornamento è stato interrotto | Diagnostica, «Completa gli aggiornamenti interrotti». |
| Un'esecuzione dice che un'altra è in corso | Aspetta che finisca. Un indicatore rimasto da un'esecuzione interrotta viene ripulito all'inizio dell'esecuzione successiva. |
| Poco spazio su disco o batteria scarica | Libera spazio o collega l'alimentatore. I limiti sono in Impostazioni, «Controlli di sicurezza». |

Sei ancora bloccato? Apri il file più recente nella cartella dei registri e cerca la prima riga che dice error o warning.

## Disinstallazione

```bash
mac-update uninstall
```

Disattiva anche le esecuzioni automatiche. Vedi [UNINSTALL.md](../../UNINSTALL.md) (in English) per cosa viene rimosso e cosa no.
