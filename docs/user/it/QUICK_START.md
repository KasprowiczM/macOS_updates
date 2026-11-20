# Avvio rapido (italiano)

**Aggiornamenti macOS 2.0.10** · Mac con Apple Silicon · macOS 13 o successivo · circa 5 minuti

Aggiornamenti macOS mantiene aggiornato il software già presente sul tuo Mac: app dell'App Store, strumenti del Terminale, pacchetti Homebrew, app scaricate da internet e macOS stesso. Non installa mai app che non hai.

## 1. Installazione

Incolla questo nel Terminale:

```bash
/bin/bash -c "$(curl -fsSL https://github.com/KasprowiczM/macOS_updates/releases/latest/download/install.sh)"
```

Il programma di installazione scarica la versione, ne controlla la somma di controllo e aggiunge il comando `mac-update`. Non aggiorna nulla e non servono `git` né `sudo`. Serve Python 3.9 o successivo (se manca, il programma di installazione ti dice di eseguire `xcode-select --install`). Dettagli: [INSTALL.md](../../INSTALL.md) (in English).

Poi apri una nuova finestra del Terminale, così il comando viene trovato. Se `mac-update` non viene ancora trovato, esegui di nuovo il programma di installazione con `bash -s -- --configure-shell` dopo la pipe, come spiegato in INSTALL.md.

## 2. Anteprima

```bash
mac-update
```

In un terminale si apre l'interfaccia sulla **Panoramica**. Spostati su **Anteprima (nessuna modifica)** con la freccia destra e premi Invio. Non viene installato nulla. Vedi cosa verrebbe aggiornato.

Preferisci il solo testo? Esegui `mac-update preview`. `mac-update --cli` (anche `--plain`) equivale a `mac-update run`, `mac-update --tui` equivale a `mac-update` da solo, e `macos-update` è lo stesso comando con un nome più lungo. Funzionano tutti da qualsiasi cartella.

## 3. Aggiornamento

Nella Panoramica scegli **Aggiorna tutto** e premi Invio. Vedrai ogni gruppo (App Store, Strumenti del Terminale, Homebrew, App da internet, Elenco delle app, Sistema macOS) e ogni app mentre viene aggiornata. Se macOS chiede la password, digitala nel Terminale: il programma non la salva mai.

Puoi fermarti in qualsiasi momento. Le app già aggiornate restano aggiornate.

## 4. Leggi il risultato

La schermata del risultato ha tre elenchi:

- **Aggiornate**: queste app ora sono al passo.
- **Già aggiornate**: non serviva nulla.
- **Serve te**: il programma non ha potuto finire da solo. Ogni riga dice perché e cosa fare. Motivi tipici: l'app era aperta, l'App Store ti chiede di accedere, oppure serve un riavvio. Vedi la [guida](GUIDE.md).

Le app che hai aperte non vengono mai chiuse. Chiudile ed esegui di nuovo l'aggiornamento.

## 5. Passi successivi

| Voglio... | Fai così |
|-----------|----------|
| Cambiare come si aggiorna una app | Scheda App, Invio sull'app: automatica, manuale o salta |
| Disattivare un gruppo o gli aggiornamenti di macOS | Panoramica: vai sul gruppo e premi Spazio. Oppure Impostazioni, «Aggiornamenti macOS» |
| Eseguire senza l'interfaccia | `mac-update run` |
| Controllare il Mac senza aggiornare | `mac-update doctor` |
| Eseguire da solo | Impostazioni, sezione «Esecuzioni automatiche». Vedi [OPERATIONS.md](OPERATIONS.md) |
| Vedere cosa è andato storto | Scheda Cronologia, poi Invio su un'esecuzione per aprirne il registro |
| Portare le impostazioni da una vecchia copia git | `mac-update migrate` (prima mostra un'anteprima) |

Altro: [GUIDE.md](GUIDE.md) · [OPERATIONS.md](OPERATIONS.md) · [UNINSTALL.md](../../UNINSTALL.md)
