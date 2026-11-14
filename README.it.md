# macOS Updates

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

**Sito web:** [macos-updates.64bit.site](https://macos-updates.64bit.site) · **Repository:** [github.com/KasprowiczM/macOS_updates](https://github.com/KasprowiczM/macOS_updates) · **Licenza:** [MIT](LICENSE) · **Modifiche:** [CHANGELOG.md](CHANGELOG.md)

> **v1.7.6** : Orchestratore di aggiornamenti con un solo comando, per **Mac Apple Silicon con macOS 13-27**. Coordina aggiornamenti di pacchetti verificati e avvii onesti degli updater delle app per il **software già installato su questo Mac**. **Multilingue** (7 lingue). Overlay privato facoltativo tramite [`dev_sync/`](dev_sync/README.md).

La fase C attiva inventario JSON locale e piani con permessi specifici. `bash update_all.sh --plan` e `--dry-run` mostrano le stesse decisioni senza scrivere. Una sessione interattiva chiede una volta gli ambiti mostrati; `-y`, EOF e sessioni senza terminale non concedono nuovi permessi. Usa `--preferences` per rivedere o reimpostare le scelte. Gli aggiornamenti conservano fonte e destinazione osservate; conflitti, destinazioni assenti e prove incerte rinviano quel destinatario. `build_inventory.sh --migration --preview` conserva i byte Markdown originali e le note; accetta esplicitamente l’ID mostrato. Gli aggiornamenti generici del produttore restano manuali finché identità e adattatore non sono verificati. Una voce di catalogo non prova installazione né consenso.

| In breve | |
|----------|--|
| Piattaforma | Solo Apple Silicon (arm64) · da macOS 13 Ventura a macOS 27 · Bash 3.2 + Python 3 |
| Flusso | 7 passaggi (0–6), l'aggiornamento di macOS è sempre l'ultimo |
| Registro | 47 app da Internet · 11 metodi di aggiornamento (vedi [Metodi di aggiornamento](#metodi-di-aggiornamento)) |
| Lingue | EN, PL, ES, FR, DE, IT, PT (CLI e documentazione) |
| Test | 1329 test automatici (`bash run_tests.sh`) |

Questa è la versione sorgente 1.7.6 locale, non pubblicata e senza tag di rilascio. Il gestore agisce solo su obiettivi installati con fonte osservata e dopo una nuova approvazione. Gli adattatori generici nativi e dei produttori restano manuali finché non sono disponibili ricette verificate. Il catalogo pubblico facoltativo comprende 48 prodotti e offre link ufficiali verificati per l’acquisizione manuale; non esistono ricette approvate per la prima installazione automatica. L’elenco dei metodi qui sotto descrive capacità, non autorizza l’esecuzione.

**Novità della v1.6.0:** Le esecuzioni pianificate (launchd) trovano Homebrew e `mas`, e l'installer verifica che il job sia caricato (aggiunti `--minute` e `--once-in`). Le app aperte non vengono mai chiuse né sostituite, cask Homebrew inclusi. Ogni domanda durante l'esecuzione scade con la risposta sicura «no». `bash update_all.sh --doctor` è un rapporto di prontezza in sola lettura e le esecuzioni reali aggiungono controlli preliminari. Lo stato persistente dei feed dei produttori sostituisce gli opachi avvisi di «feed obsoleto», e HyperFrames, Superset e Open Design vengono installati o verificati senza avvii nascosti. Le versioni 1.5.x precedenti sono descritte in [CHANGELOG.md](CHANGELOG.md).

I vecchi rapporti sui feed dei produttori sono in sola lettura. Il gestore attuale lascia manuali gli adattatori generici nativi e dei produttori finché non è disponibile una ricetta verificata. La vecchia opzione `--bootstrap-cli` non autorizza una prima installazione. Installa le CLI mancanti separatamente seguendo istruzioni ufficiali verificate. Le app aperte non vengono chiuse. Controlla i feed con `bash scripts/check_vendor_feeds.sh`.

## Configurazione sicura e fonti delle applicazioni

`bash setup.sh --inspect` verifica la disponibilità senza installare dipendenze, modificare profili o configurare Touch ID. Uno strumento mancante rende indisponibile la funzione dipendente. Nel terminale, `bash setup.sh --install-dependencies` mostra le dipendenze facoltative e chiede prima di ogni installazione; `bash setup.sh --configure-shell` mostra separatamente la modifica del profilo. Rifiutare una dipendenza non blocca funzioni indipendenti. Se Python manca, installarlo esplicitamente prima dell’inventario. `mas` mancante o vecchio viene segnalato senza installazione o aggiornamento automatico.

Il rapporto normale riguarda le applicazioni installate. `bash scripts/report_update_coverage.sh --show-supported` resta un elenco di riferimento. Il menu facoltativo si apre con `bash setup.sh --catalog` e non seleziona nulla. Dopo l’anteprima e una nuova approvazione, puoi acquisire manualmente un’app tramite un link ufficiale verificato. Cambiare la fonte di un’app esistente richiede una migrazione manuale. Una ricevuta App Store per CapCut conserva quella fonte. Un’app locale senza proprietà Homebrew confermata non viene adottata automaticamente.

La ricerca latest stable è in [SOURCE_RESEARCH.md](docs/catalog/SOURCE_RESEARCH.md). Edizioni diverse non sono confrontabili; una singola osservazione non prova quale canale sia normalmente più veloce.

---

## Installazione in una riga (nuovi utenti)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

L’installer clona il repository, chiede la lingua, verifica la disponibilità e crea l’inventario di questo Mac se Python è disponibile. Le dipendenze richiedono una scelta separata in setup. Touch ID e profili shell non vengono modificati automaticamente.

Vedi [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md)

---

## Cosa fa questo strumento

`update_all.sh` esegue sette passaggi:

| Passaggio | Azione |
|-----------|--------|
| 0 | **Prescansione** — rileva le app installate → aggiorna `APPLICATIONS.md` |
| 1 | **App Store** — Corsia 1: `sudo mas upgrade <app-id>`; Corsia 2: GUI AppleScript per le app iPad |
| 2 | **CLI native + npm** — prima le CLI native esistenti, poi Node, Bun e le CLI npm globali |
| 3 | **Homebrew** — formule e cask (`brew_cask` + protezione dal downgrade) + pulizia e controllo di integrità |
| 4 | **App da Internet** — gestori diretti verificati, `sparkle_appcast`, CLI dei produttori e avvii onesti degli updater |
| 5 | **Post-aggiornamento/cronologia** — aggiorna `APPLICATIONS.md`, aggiunge a `UPDATES.md` in modo atomico |
| 6 | **macOS (finale)** — per etichetta `softwareupdate -i <label> -R` (etichette che richiedono riavvio nell'ultimo gruppo); rinviato dopo un errore grave bloccante nei passaggi 1–4 o senza autorizzazione |

**Importante:** Gli aggiornamenti normali agiscono solo sul software installato con fonte osservata e ambito approvato. Il catalogo facoltativo separato può mostrare app assenti, ma non le installa automaticamente. L’acquisizione manuale richiede anteprima e nuova approvazione. Il passaggio finale di macOS può riavviare il Mac, quindi viene eseguito per ultimo e mantiene l’obbligatorio `-R`. Il passaggio 5 serve solo al rapporto. Le app sconosciute sono elencate per la revisione.

La copertura è volutamente esplicita: **verified direct** significa che l'updater ha confermato il percorso pacchetto/versione; **triggered-unverified**, che l'app è stata avviata per lasciar lavorare il suo updater ma il completamento non è dimostrabile; **externally managed**, che il ciclo di aggiornamento è gestito dal produttore o dall'App Store; **manual** richiede un'azione dell'utente; **unknown** non ha un metodo registrato.

```bash
bash scripts/report_update_coverage.sh   # report di copertura
bash build_inventory.sh                  # ricostruisce APPLICATIONS.md da questo Mac
```

### Metodi di aggiornamento
La tabella dei metodi è un riferimento storico alle capacità. Descrive metodi registrati ma non ne autorizza l’esecuzione; il gestore richiede fonte osservata e nuova approvazione.

Il registro ([`config/internet_apps.txt`](config/internet_apps.txt), [`config/internet_app_methods.txt`](config/internet_app_methods.txt)) associa 47 app a 11 metodi:

| Metodo | App | Copertura | Come aggiorna |
|--------|----:|-----------|---------------|
| `brew_cask` | 11 | externally managed | Cask Homebrew (greedy solo per questi token) con protezione dal downgrade, ad es. Brave, Obsidian, Spotify, Inkscape |
| `silent_launch` | 14 | triggered-unverified | L'updater proprio dell'app come ripiego; controllo opportunistico su un feed Sparkle / electron-updater, altrimenti «avviata (non verificata)». Le app con feed del produttore (ChatGPT / Codex, Claude, Cursor, Warp, OpenCode, Proton Mail, ...) sono decise da quel feed e, se indietro, installate dall'artefatto verificato del produttore. Senza feed il metodo non sostituisce mai l'app stessa |
| `github_dmg` | 5 | verified direct | DMG del produttore/GitHub con verifica di firma e Team ID, sostituzione a fasi con rollback (KeePassXC, VS Code, CodeEdit, Ledger Live, Trezor Suite) |
| `msupdate` | 5 | verified direct | Microsoft AutoUpdate (`msupdate`): Word, Excel, PowerPoint, Outlook, OneNote |
| `keystone` | 3 | verified direct | Updater di Google (Omaha), verificato con la sua cronologia: Chrome, Gemini, Google Drive |
| `appstore_gui` | 4 | externally managed | App Store Corsia 2 (AppleScript): UniFi, WiFiman, Picsart, IPMIView |
| `sparkle_appcast` | 1 | verified direct | Appcast Sparkle (Proton Drive) |
| `chromium_updater` | 1 | verified direct | Prova dell'updater basato su Chromium (Comet) |
| `docker_cli` | 1 | verified direct | Docker Desktop: DMG verificato dal suo appcast quando è inattivo; ripiego `docker desktop update` |
| `mau_fallback_self_update` | 1 | triggered-unverified | Aggiornamento autonomo di Teams più fallback MAU `TEAMS21` osservato e verificato quando Microsoft lo offre |
| `mozilla_dmg` | 1 | verified direct | Versione da product-details di Mozilla più DMG verificato, sostituzione a stadi con rollback (Firefox Developer Edition) |

---

## Opzioni da riga di comando

`lib/cli.sh` è l'elenco di riferimento; `bash update_all.sh --help` lo stampa.

| Opzione | Effetto |
|---------|---------|
| `-y`, `--yes` | Salta la richiesta di conferma |
| `-h`, `--help` | Mostra l'aiuto ed esce con `0` |
| `--doctor` | Rapporto di prontezza in sola lettura (piattaforma, strumenti, `PATH` di launchd, LaunchAgent, sudo, disco, alimentazione, rete, ultima esecuzione); nessuna richiesta sudo, nessun log di esecuzione; uscita `0` ok / `10` avvisi / `1` problema |
| `--dry-run` | Anteprima di ogni passaggio, nessuna modifica, non chiede mai credenziali |
| `--verify-only` | Verifica le versioni delle app installate rispetto alla cronologia senza modificare nulla |
| `--json-summary` | Stampa su stdout un oggetto JSON con il risultato al termine |
| `--bootstrap-cli` | La vecchia opzione CLI non autorizza una prima installazione. Installa le CLI mancanti separatamente seguendo istruzioni ufficiali verificate. |
| `--non-interactive` | Modalità non interattiva per launchd / cron (implica anche `-y`) |
| `--notify` | Invia una notifica di macOS al termine |
| `--treat-appstore-ax-as-warning` | Tratta l'uscita `2` dell'App Store (Accessibilità mancante) come avviso |
| `--skip-prescan` | Salta il passaggio 0 (prescansione di `APPLICATIONS.md`) |
| `--skip-appstore` | Salta il passaggio 1 (App Store) |
| `--skip-npm` | Salta il passaggio 2 (CLI native + npm) |
| `--skip-brew` | Salta il passaggio 3 (Homebrew) |
| `--skip-internet` | Salta il passaggio 4 (app da Internet) |
| `--skip-postupdate` | Salta il passaggio 5 (cronologia `APPLICATIONS.md` / `UPDATES.md`) |
| `--skip-system` | Salta il passaggio 6 (aggiornamento di macOS) |
| `--skip-doctor` | Salta `brew doctor` in `update_brew.sh` |

Un'opzione `-…` sconosciuta termina con codice `2` dopo aver stampato l'aiuto.

**Verifica preliminare (solo esecuzioni reali):** prima del passaggio 0 l'esecuzione controlla spazio libero su disco, batteria e rete. Poco spazio degrada l'esecuzione, una batteria scarica salta solo il passaggio macOS (in modo non bloccante), e se nessun host è raggiungibile l'esecuzione termina con codice `1` prima di qualsiasi passaggio. Il Mac viene tenuto sveglio con `caffeinate` durante l'esecuzione (`MAC_UPDATE_NO_CAFFEINATE=1` lo disattiva). Esegui `bash update_all.sh --doctor` per vedere gli stessi controlli senza eseguire nulla.

**Domande:** ogni domanda durante l'esecuzione scade dopo `MAC_UPDATE_PROMPT_TIMEOUT` secondi con la risposta sicura "no"; anche un input non riconosciuto vale "no". Dopo la conferma principale, i passaggi Homebrew e App Store non chiedono di nuovo; il passaggio macOS chiede ancora.

**App aperte:** un cask Homebrew la cui app è aperta non viene mai aggiornato; viene rinviato con il messaggio "chiudi l'app" e il passaggio termina con un avviso non bloccante (codice `10`).

**App direct-only e never-launch:** `config/vendor_launch_policy.txt` elenca le app che lo strumento non avvia mai. Un'app `direct-only` (HyperFrames, Superset) viene aggiornata solo dal suo artefatto verificato del produttore; un'app `never-launch` (Open Design) viene solo verificata e, se indietro, segnalata come «apri l'app per aggiornare». Nessuna viene aperta o chiusa, nemmeno come ripiego dopo un feed irraggiungibile.

## Variabili d'ambiente

Ogni opzione ha una variabile equivalente (`MAC_UPDATE_DRY_RUN=1`, `MAC_UPDATE_SKIP_SYSTEM=1`, …); queste sono le più usate senza un'opzione dedicata. L'elenco completo con i valori predefiniti è in [docs/agents/scripts.md](docs/agents/scripts.md#environment-variables).

| Variabile | Predefinito | Significato |
|-----------|-------------|-------------|
| `MAC_UPDATE_NONINTERACTIVE` | `0` | Non chiede mai nulla; salta l'automazione GUI della Corsia 2 dell'App Store |
| `MAC_UPDATE_NOTIFY` | `0` | Notifica sul desktop al termine (implicita anche in modalità non interattiva) |
| `MAC_UPDATE_NO_SUDO` | *impostata automaticamente* | Esportata da `update_all.sh` senza TTY; gli script figli saltano le corsie root invece di fallire |
| `MAC_UPDATE_NO_SUDO_KEEPALIVE` | `0` | `1` disattiva l'aggiornamento in background del timestamp di `sudo` |
| `MAC_UPDATE_STALE_DAYS` | `45` | Giorni dopo i quali un'app non verificata è segnalata come obsoleta |
| `MAC_UPDATE_MAX_LOGS` | `30` | Log di esecuzione conservati in `logs/` (anche i riepiloghi di esecuzione vengono ruotati) |
| `MAC_UPDATE_PROMPT_TIMEOUT` | `120` | Secondi (10–900, `0` = attendi sempre) in cui una domanda sì/no durante l'esecuzione resta in attesa; allo scadere vale "no" |
| `MAC_UPDATE_MIN_FREE_GB` | `15` | Verifica preliminare: spazio libero sotto questo valore degrada l'esecuzione |
| `MAC_UPDATE_MIN_BATTERY` | `30` | Verifica preliminare: a batteria sotto questa percentuale viene saltato solo il passaggio macOS |
| `MAC_UPDATE_INTERNET_SETTLE_SECONDS` | `15` | Pausa che permette a un updater di produttore avviato di riscrivere `Info.plist` (`0` la disattiva, limitata a 120; omessa se non è stata avviata alcuna app) |
| `MAC_UPDATE_QUIT_WAIT` | `60` | Secondi (0–300) che un'app avviata dallo strumento ha per chiudersi dopo il `quit` gentile; mai forzata (v1.5.5) |
| `MAC_UPDATE_QUIT_RESEND` | `10` | Secondi (1–60) tra richieste `quit` gentili ripetute nella finestra di attesa (v1.5.5) |
| `MAC_UPDATE_MAS_CHECK_TIMEOUT` | `120` | Timeout di `mas outdated` |
| `MAC_UPDATE_MAS_UPGRADE_TIMEOUT` | `1800` | Timeout di `sudo mas upgrade` |
| `MAC_UPDATE_MAU_DEFERRAL_DAYS` | `7` | Finestra di quarantena di Microsoft AutoUpdate (limitata all'intervallo 1–28 di Microsoft) |
| `MAC_UPDATE_MAU_CLEAR_DEFERRALS` | `0` | `1` rimuove con `defaults delete` le chiavi di rinvio MAU che bloccano |
| `MAC_UPDATE_MAU_KEEP_DEFERRALS` | `0` | `1`: lo strumento non tocca mai le preferenze di rinvio di MAU |
| `MAC_UPDATE_LANG` / `MAC_LANG` | da `.mac_update_prefs` | Lingua dell'interfaccia (`en pl es it pt de fr`) |

## sudo e Touch ID — il contratto

Riscritto nella v1.3.1 / v1.4.0. `update_all.sh` ha **un solo** punto di chiamata
interattivo a `sudo`, vincolato a tre condizioni:

1. **Al massimo una volta per esecuzione.** Un unico `sudo -v` prima del
   reindirizzamento del log, poi un processo in background aggiorna il timestamp
   ogni 50 s, così un'esecuzione lunga non chiede mai una seconda volta. Il
   keep-alive parte al massimo una volta ed è terminato dalla trap di pulizia su
   ogni percorso di uscita, inclusi `INT`/`TERM`: non può più restare orfano.
2. **Mai senza un TTY di controllo.** Se stdin non è un terminale (task runner
   dell'IDE, shell di un agente, launchd, cron) lo strumento **non** chiama
   `sudo -v`. Un `sudo -v` senza TTY passa al dialogo grafico askpass/Touch ID, ed
   è per questo che ogni comando sembrava richiedere privilegi elevati. Viene invece
   esportata `MAC_UPDATE_NO_SUDO=1`, i passaggi che richiedono root sono saltati e
   l'esecuzione segnala un avviso lieve.
3. **Mai durante `--dry-run`.** Un'anteprima non deve chiedere credenziali.

`sudo` non viene richiesto affatto quando non vengono eseguiti né il passaggio 1
(App Store) né il passaggio 6 (macOS), ad es. `bash update_all.sh --skip-appstore --skip-system`.

---

## Configurazione per singolo Mac (**non** arriva con `git pull`)

Due elementi vivono fuori dal repository e vanno quindi configurati una volta **su
ogni Mac**. Clonare o fare pull su un secondo computer non li porta con sé: è la
confusione più frequente in questo progetto.

| Passaggio | Comando | Perché non può stare in Git |
|-----------|---------|-----------------------------|
| Touch ID per `sudo` | `bash scripts/setup_touchid_sudo.sh` | Scrive `/etc/pam.d/sudo_local`: file di proprietà di root, locale al computer, fuori dal repository |
| Esecuzione settimanale in background | `bash scripts/install_launchagent.sh --day 1 --hour 9` | Scrive `~/Library/LaunchAgents/com.<user>.macos-updates.plist`: per utente e per computer |

```bash
bash scripts/setup_touchid_sudo.sh --check      # solo report, non scrive nulla
bash scripts/setup_touchid_sudo.sh              # installa / ripara
bash scripts/setup_touchid_sudo.sh --uninstall

bash scripts/install_launchagent.sh --check
bash scripts/install_launchagent.sh --once-in 5
bash scripts/install_launchagent.sh --uninstall
```

`setup_touchid_sudo.sh` non tocca mai `/etc/sudoers` e non concede mai `sudo` senza
password. Su macOS 14+ usa `/etc/pam.d/sudo_local`, che sopravvive agli
aggiornamenti di sistema; su macOS 13 modifica `/etc/pam.d/sudo`, che gli
aggiornamenti di macOS cancellano: rieseguilo dopo un aggiornamento maggiore.

### Cosa fa e cosa non fa l'esecuzione pianificata in background

Il LaunchAgent esegue `update_all.sh -y --skip-system` con
`MAC_UPDATE_NONINTERACTIVE=1` e `MAC_UPDATE_NOTIFY=1`.

Il plist imposta un `PATH` esplicito (`/opt/homebrew/bin:/opt/homebrew/sbin:/usr/bin:/bin:/usr/sbin:/sbin`) perché quello predefinito di launchd non include Homebrew, e l'installer verifica con `launchctl print` che il job sia caricato; altrimenti stampa l'errore di launchctl ed esce con codice diverso da zero. `--minute N` (0-59) imposta il minuto, `--once-in N` (1-1440 minuti da ora) installa un'esecuzione di prova singola e non si combina con `--day`/`--hour`/`--minute`, e `--check` avvisa di un plist senza la chiave `PATH` (per un'installazione vecchia, riesegui l'installer).

- **Esegue:** Homebrew, CLI native + npm, app da Internet, inventario/cronologia.
- **Non esegue gli aggiornamenti di macOS**: `--skip-system` è voluto. Su Apple
  Silicon `softwareupdate` richiede le **credenziali del proprietario del volume**,
  impossibili da fornire da un job launchd non presidiato, e il passaggio può
  riavviare il Mac.
- **Non esegue gli aggiornamenti dell'App Store**: `sudo mas upgrade` richiede una
  password e il percorso AppleScript della Corsia 2 pilota l'interfaccia dell'App
  Store. Entrambi vengono saltati in una sessione senza TTY e segnalati come avviso
  lieve (codice `10`), mai come errore.

Entrambi restano quindi interattivi, di proposito. Esegui `bash update_all.sh` tu
stesso quando vuoi applicare gli aggiornamenti dell'App Store e di macOS.

---

## Requisiti

| Strumento | Installato automaticamente? |
|-----------|-----------------------------|
| Mac Apple Silicon (arm64) | — |
| macOS 13 Ventura o successivo (testato fino a macOS 27) | — |
| Xcode Command Line Tools | Installazione manuale |
| Homebrew | Installazione manuale: https://brew.sh |
| `mas` (CLI dell'App Store) | ✅ |
| Python 3.9+ | Consenso esplicito: `setup.sh --install-dependencies` |
| `rclone` (facoltativo) | ✅ se scelto come provider cloud |

I Mac Intel e macOS 12 o precedente non sono supportati; gli script terminano prima di qualsiasi modifica.

---

## Avvio rapido

### Nuovo utente (senza cloud)

```bash
# Opzione A — una riga (consigliata)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"

# Opzione B — manuale
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh --inspect
bash build_inventory.sh
bash update_all.sh
```

### Proprietario (GitHub + overlay cloud)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

---

## Struttura del progetto

```
macOS_updates/
├── VERSION                     # Versione del pacchetto (unica fonte di verità)
├── install.sh                  # Installer in una riga
├── uninstall.sh                # Rimuove il clone (mantiene Homebrew e le app)
├── setup.sh                    # Configurazione iniziale (senza cloud)
├── migration_setup.sh          # Configurazione completa + procedura guidata cloud
├── build_inventory.sh          # Genera APPLICATIONS.md per questo Mac
├── update_all.sh               # Orchestratore principale
├── update_*.sh                 # Singoli passaggi di aggiornamento
├── run_tests.sh                # Sintassi + Python + unittest + scansione segreti
│
├── dev_sync/                   # Sincronizzazione dell'overlay privato (cloud)
│   ├── provider_setup.sh
│   ├── dev-sync-export.sh      # (+ import, verify, prune, …)
│   └── dev_sync_*.py           # Backend Python
├── dev-sync-*.sh               # Wrapper nella radice (compatibilità)
│
├── config/                     # Registro delle app da Internet (pubblico)
│   ├── internet_apps.txt
│   ├── internet_app_methods.txt
│   └── internet_dispatch_order.txt
│
├── lib/                        # Librerie Bash condivise (+ lib/python/)
├── i18n/                       # Testi dell'interfaccia in 7 lingue
├── scripts/                    # Utility (report di copertura, feed dei produttori, generatore, …)
├── templates/                  # APPLICATIONS.md.template (riferimento)
├── tests/                      # unittest + controlli statici di sicurezza
├── docs/
│   ├── INSTALL.md · UNINSTALL.md · PUBLIC_RELEASE.md
│   ├── user/                   # Guide per gli utenti finali (7 lingue)
│   ├── agents/                 # Riferimento per sviluppatori / agenti IA
│   ├── reviews/                # Indice + registri di sviluppo correnti (archive/ = storico)
│   └── archive/                # Piani di implementazione superati
│
├── CHANGELOG.md · CONTRIBUTING.md · SECURITY.md · LICENSE
└── AGENTS.md · CLAUDE.md · GEMINI.md · CODEX.md
```

**File privati (ignorati da git, solo locali o nel cloud):** `APPLICATIONS.md`, `UPDATES.md`, `.dev_sync_config.json`, `.mac_update_prefs`, `.env`, `logs/`

### Singoli script

| Script | Scopo |
|--------|-------|
| `install.sh` | Clona + configura + crea l'inventario per i nuovi utenti |
| `setup.sh` | Dipendenze e permessi (senza cloud) |
| `migration_setup.sh` | Migrazione completa + cloud + scansione delle app |
| `build_inventory.sh` | Scansione in sola lettura → aggiorna `APPLICATIONS.md` in modo atomico senza cronologia degli aggiornamenti |
| `update_all.sh` | Tutti i passaggi di aggiornamento + log |
| `update_system.sh` … `update_brew.sh` | Aggiornamenti di un singolo livello |
| `uninstall.sh` | Rimuove la cartella dello strumento |
| `run_tests.sh` | Sintassi + Python + unittest + scansione segreti |

Riferimento completo degli script: [docs/agents/scripts.md](docs/agents/scripts.md).

---

## Aggiungere il supporto per una nuova app

1. Installa l'app da solo (l'updater non la installa mai al posto tuo).
2. Esegui `bash build_inventory.sh` per aggiungerla a `APPLICATIONS.md`.
3. Per l'aggiornamento automatico, chiedi a un agente IA o segui [docs/user/it/GUIDE.md](docs/user/it/GUIDE.md):

```bash
bash scripts/scaffold_internet_app.sh "Nome app" silent_launch
bash run_tests.sh
```

I metodi del registro sono associati agli stati di copertura sopra descritti. Ad esempio `github_dmg` e una CLI del produttore confermata sono **verified direct**; `silent_launch` è **triggered-unverified**; i flussi gestiti dall'App Store o dal produttore possono essere **externally managed**; `manual` e le voci mancanti nel registro restano esplicite.

---

## Sincronizzazione cloud (`dev_sync`)

| GitHub (pubblico) | Cloud (privato) |
|-------------------|-----------------|
| Script, `config/`, `docs/`, test | `APPLICATIONS.md`, `UPDATES.md`, `.env`, `.dev_sync_config.json` |

```bash
bash dev_sync/provider_setup.sh
bash dev_sync/dev-sync-export.sh
bash dev_sync/dev-sync-import.sh
bash dev_sync/dev-sync-verify-full.sh
```

I wrapper `dev-sync-*.sh` nella radice richiamano gli stessi script di `dev_sync/`.

---

## Test

La suite copre la sintassi bash, la compilazione Python, i contratti statici di sicurezza, le protezioni della documentazione e i test unitari (591 test automatici).
Le pull request eseguono ShellCheck su Ubuntu, test Python portabili e la scansione dei segreti.
La suite completa `run_tests.sh` su un runner macOS viene eseguita solo con `workflow_dispatch` o un tag `v*`, non a ogni push.

```bash
bash run_tests.sh
bash update_all.sh --dry-run -y
```

---

## Note tecniche critiche

- **`softwareupdate` deve usare `-R`**: altrimenti gli aggiornamenti vengono scaricati ma mai applicati.
- **`mas upgrade` deve usare `sudo` e ID app espliciti** su macOS 14.8.2+/15.7.2+/26.1+ (modifica dei permessi, vedi https://github.com/orgs/Homebrew/discussions/6550).
- **Bash 3.2+** ovunque: niente `declare -A`, `mapfile`, `readarray`.
- Le app scaricate vengono verificate, installate con una sostituzione a fasi con rollback, e i loro DMG sono montati in punti di mount univoci per sessione.
- Le scritture di inventario/cronologia privati e le importazioni dal cloud sono atomiche; le importazioni preparano i file accettati prima di confermarli.

---

## Documentazione

| Destinatario | Da dove iniziare |
|--------------|------------------|
| Utenti | [docs/user/INDEX.md](docs/user/INDEX.md) (avvio rapido, guida e manuale operativo in 7 lingue) · [avvio rapido in italiano](docs/user/it/QUICK_START.md) |
| Installazione / disinstallazione | [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md) |
| GitHub pubblico e overlay privato | [docs/PUBLIC_RELEASE.md](docs/PUBLIC_RELEASE.md) · [dev_sync/README.md](dev_sync/README.md) |
| Sviluppatori / agenti | [docs/agents/scripts.md](docs/agents/scripts.md) · [regole critiche](docs/agents/critical_rules.md) · [codici di uscita](docs/agents/exit_codes.md) · [risoluzione dei problemi](docs/agents/troubleshooting.md) · [lista di accettazione](docs/agents/acceptance_checklist.md) |
| Contesto per agenti IA | [AGENTS.md](AGENTS.md) (contratto condiviso) · [CLAUDE.md](CLAUDE.md) · [GEMINI.md](GEMINI.md) · [CODEX.md](CODEX.md) |
| Storico delle versioni | [CHANGELOG.md](CHANGELOG.md) |
| Contribuire / sicurezza | [CONTRIBUTING.md](CONTRIBUTING.md) · [SECURITY.md](SECURITY.md) |

---

## Risoluzione dei problemi

| Problema | Soluzione |
|----------|-----------|
| Mac nuovo | `install.sh` oppure `setup.sh` + `build_inventory.sh` |
| Elenco app errato | `build_inventory.sh`: non copiare mai l'`APPLICATIONS.md` di un'altra persona |
| Un'app non si aggiorna da sola | `scripts/report_update_coverage.sh` → aggiungi un gestore secondo la guida |
| `APPLICATIONS.md` mancante | `build_inventory.sh` oppure `dev_sync/dev-sync-import.sh` (proprietario) |
| `mas upgrade` fallisce | `sudo mas upgrade <app-id>` |
| Cloud non configurato | `bash dev_sync/provider_setup.sh` |

Elenco completo: [docs/agents/troubleshooting.md](docs/agents/troubleshooting.md)

---

## Licenza

[MIT](LICENSE) © macOS Updates contributors


## Catalogo facoltativo e prima installazione

I nuovi segnali sulle app sono proposte da verificare, non ricette eseguibili. `bash scripts/scan_update_feeds.sh` mostra un riepilogo aggregato. L’esportazione permette di visualizzare e accettare esplicitamente la proposta; è redatta, resta locale e non viene mai caricata. `bash setup.sh --catalog` apre il catalogo senza selezioni. `-y`, le esecuzioni non interattive e EOF non installano nulla. Nel menu, `check <number>` confronta solo le fonti scelte. I risultati indicano l’ultima versione stabile compatibile confermata e la data, con cache di 24 ore. Un dato sconosciuto resta tale. Una scheda pubblica del Mac App Store non dimostra che l’app sia offerta al tuo account.

Il catalogo pubblico conta 47 righe del registro per 48 prodotti e zero ricette approvate per la prima installazione automatica. Dopo l’anteprima e una nuova conferma, puoi scegliere link ufficiali verificati per l’acquisizione manuale. Aprire una pagina non installa l’app. Cambiare la fonte di un’app esistente richiede migrazione manuale. L’InstallPlan separato mostra fonte, destinazione, versione, requisiti e permessi; licenza e costo sconosciuti sono indicati come tali. Ogni ricetta futura richiederà approvazione prima dell’attivazione. Il catalogo non promette l’installazione automatica di tutti i prodotti.
