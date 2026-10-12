# macOS Updates

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

**Sito web:** [macosupdates.dev](https://macosupdates.dev) · **Repository:** [github.com/KasprowiczM/macOS_updates](https://github.com/KasprowiczM/macOS_updates) · **Licenza:** [MIT](LICENSE) · **Modifiche:** [CHANGELOG.md](CHANGELOG.md)

> **v1.5.5** — Orchestratore di aggiornamenti con un solo comando, pronto per la produzione, per **Mac Apple Silicon con macOS 13–27**. Coordina aggiornamenti di pacchetti verificati e avvii onesti degli updater delle app per il **software già installato su questo Mac**. **Multilingue** (7 lingue). Overlay privato facoltativo tramite [`dev_sync/`](dev_sync/README.md).

| In breve | |
|----------|--|
| Piattaforma | Solo Apple Silicon (arm64) · da macOS 13 Ventura a macOS 27 · Bash 3.2 + Python 3 |
| Flusso | 7 passaggi (0–6), l'aggiornamento di macOS è sempre l'ultimo |
| Registro | 43 app da Internet · 11 metodi di aggiornamento (vedi [Metodi di aggiornamento](#metodi-di-aggiornamento)) |
| Lingue | EN, PL, ES, FR, DE, IT, PT (CLI e documentazione) |
| Test | 561 test automatici (`bash run_tests.sh`) |

**Novità della v1.5.5:** Un upgrade di Homebrew che rimuove `python3` durante l'esecuzione non interrompe più il passaggio di inventario/report (la shell cerca di nuovo in `PATH`), e un passaggio di report fallito non rinvia più gli aggiornamenti di macOS. I messaggi finali sono onesti: nessuna dichiarazione «file aggiornati» dopo un errore, e gli avvisi su feed obsoleti o app non chiuse non sono più presentati come aggiornamenti non verificati. Alle app avviate dallo strumento viene chiesto ripetutamente di chiudersi (mai forzato). Le versioni 1.5.x precedenti (feed obsoleti come avvisi, download del produttore per ChatGPT/Proton, CLI native prima di npm, protezione della sostituzione dei pacchetti) sono descritte in [CHANGELOG.md](CHANGELOG.md).

**Verità del produttore (dalla v1.5.0):** la versione di ciascuna applicazione viene verificata rispetto al feed del rispettivo produttore prima di qualsiasi azione. Le app aggiornate non vengono toccate; quelle obsolete vengono aggiornate dall'updater della stessa app oppure installate dal produttore con verifica di firma e Team ID. Viene aggiornato solo il software installato (`--bootstrap-cli` installa deliberatamente le CLI mancanti). Le app rimosse manualmente vengono riconosciute e mai reinstallate. **Le app che hai aperto non vengono mai chiuse: lo strumento chiude solo ciò che ha avviato lui stesso.** Controlla lo stato dei produttori in sola lettura con `bash scripts/check_vendor_feeds.sh`.

---

## Installazione in una riga (nuovi utenti)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

L'installer clona il repository, chiede la **lingua** (menu in inglese, 7 lingue), installa le dipendenze, genera **il tuo** `APPLICATIONS.md` dalle app già presenti su questo Mac e mostra quali app il progetto può aggiornare. Non importa mai l'inventario di un'altra persona e non installa app al posto tuo.

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

**Importante:** Gli aggiornamenti riguardano solo il software già installato sul tuo Mac. Le app supportate ma mancanti vengono segnalate, non installate. Il passaggio finale di macOS può riavviare il Mac, quindi viene eseguito per ultimo e mantiene l'obbligatorio `-R`. Il passaggio 5 serve solo al report: un suo errore è un errore ma non rinvia mai il passaggio macOS. Le app installate sconosciute vengono elencate in modo che tu (o un agente IA) possa aggiungere gestori.

La copertura è volutamente esplicita: **verified direct** significa che l'updater ha confermato il percorso pacchetto/versione; **triggered-unverified**, che l'app è stata avviata per lasciar lavorare il suo updater ma il completamento non è dimostrabile; **externally managed**, che il ciclo di aggiornamento è gestito dal produttore o dall'App Store; **manual** richiede un'azione dell'utente; **unknown** non ha un metodo registrato.

```bash
bash scripts/report_update_coverage.sh   # report di copertura
bash build_inventory.sh                  # ricostruisce APPLICATIONS.md da questo Mac
```

### Metodi di aggiornamento

Il registro ([`config/internet_apps.txt`](config/internet_apps.txt), [`config/internet_app_methods.txt`](config/internet_app_methods.txt)) associa 43 app a 11 metodi:

| Metodo | App | Copertura | Come aggiorna |
|--------|----:|-----------|---------------|
| `brew_cask` | 11 | externally managed | Cask Homebrew (greedy solo per questi token) con protezione dal downgrade, ad es. Brave, Obsidian, Spotify, Inkscape |
| `silent_launch` | 9 | triggered-unverified | L'updater proprio dell'app; controllo opportunistico su un feed Sparkle / electron-updater, altrimenti «avviata (non verificata)». Non sostituisce mai l'app stessa |
| `github_dmg` | 6 | verified direct | DMG del produttore/GitHub con verifica di firma e Team ID, sostituzione a fasi con rollback (Firefox Developer Edition, KeePassXC, VS Code, CodeEdit, Ledger Live, Trezor Suite) |
| `msupdate` | 5 | verified direct | Microsoft AutoUpdate (`msupdate`): Word, Excel, PowerPoint, Outlook, OneNote |
| `keystone` | 3 | verified direct | Updater di Google (Omaha), verificato con la sua cronologia: Chrome, Gemini, Google Drive |
| `appstore_gui` | 3 | externally managed | App Store Corsia 2 (AppleScript): UniFi, WiFiman, Picsart |
| `sparkle_appcast` | 1 | verified direct | Appcast Sparkle (Proton Drive) |
| `chromium_updater` | 1 | verified direct | Prova dell'updater basato su Chromium (Comet) |
| `docker_cli` | 1 | verified direct | Docker Desktop: DMG verificato dal suo appcast quando è inattivo; ripiego `docker desktop update` |
| `mau_fallback_self_update` | 1 | triggered-unverified | Aggiornamento autonomo di Teams più fallback MAU `TEAMS21` osservato e verificato quando Microsoft lo offre |
| `manual` | 2 | manual | IPMIView e DJI Assistant 2: solo notifica |

---

## Opzioni da riga di comando

`lib/cli.sh` è l'elenco di riferimento; `bash update_all.sh --help` lo stampa.

| Opzione | Effetto |
|---------|---------|
| `-y`, `--yes` | Salta la richiesta di conferma |
| `-h`, `--help` | Mostra l'aiuto ed esce con `0` |
| `--dry-run` | Anteprima di ogni passaggio, nessuna modifica, non chiede mai credenziali |
| `--verify-only` | Verifica le versioni delle app installate rispetto alla cronologia senza modificare nulla |
| `--json-summary` | Stampa su stdout un oggetto JSON con il risultato al termine |
| `--bootstrap-cli` | Installa esplicitamente le CLI mancanti (per impostazione predefinita si aggiornano solo quelle installate) |
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

## Variabili d'ambiente

Ogni opzione ha una variabile equivalente (`MAC_UPDATE_DRY_RUN=1`, `MAC_UPDATE_SKIP_SYSTEM=1`, …); queste sono le più usate senza un'opzione dedicata. L'elenco completo con i valori predefiniti è in [docs/agents/scripts.md](docs/agents/scripts.md#environment-variables).

| Variabile | Predefinito | Significato |
|-----------|-------------|-------------|
| `MAC_UPDATE_NONINTERACTIVE` | `0` | Non chiede mai nulla; salta l'automazione GUI della Corsia 2 dell'App Store |
| `MAC_UPDATE_NOTIFY` | `0` | Notifica sul desktop al termine (implicita anche in modalità non interattiva) |
| `MAC_UPDATE_NO_SUDO` | *impostata automaticamente* | Esportata da `update_all.sh` senza TTY; gli script figli saltano le corsie root invece di fallire |
| `MAC_UPDATE_NO_SUDO_KEEPALIVE` | `0` | `1` disattiva l'aggiornamento in background del timestamp di `sudo` |
| `MAC_UPDATE_STALE_DAYS` | `45` | Giorni dopo i quali un'app non verificata è segnalata come obsoleta |
| `MAC_UPDATE_MAX_LOGS` | `30` | Log di esecuzione conservati in `logs/` |
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
bash scripts/install_launchagent.sh --uninstall
```

`setup_touchid_sudo.sh` non tocca mai `/etc/sudoers` e non concede mai `sudo` senza
password. Su macOS 14+ usa `/etc/pam.d/sudo_local`, che sopravvive agli
aggiornamenti di sistema; su macOS 13 modifica `/etc/pam.d/sudo`, che gli
aggiornamenti di macOS cancellano: rieseguilo dopo un aggiornamento maggiore.

### Cosa fa e cosa non fa l'esecuzione pianificata in background

Il LaunchAgent esegue `update_all.sh -y --skip-system` con
`MAC_UPDATE_NONINTERACTIVE=1` e `MAC_UPDATE_NOTIFY=1`.

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
| Xcode Command Line Tools | ✅ `setup.sh` / `install.sh` |
| Homebrew | ✅ |
| `mas` (CLI dell'App Store) | ✅ |
| Python 3 | ✅ tramite Homebrew se manca |
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
bash setup.sh
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

La suite copre la sintassi bash, la compilazione Python, i contratti statici di sicurezza, le protezioni della documentazione e i test unitari (561 test automatici).
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
| Storico delle versioni | [CHANGELOG.md](CHANGELOG.md) · [indice dei registri di sviluppo](docs/reviews/README.md) |
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
