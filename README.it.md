# Aggiornamenti macOS

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

**Versione 2.0.10** · Mac con Apple Silicon · macOS 13 o successivo · [Sito](https://macos-updates.64bit.site) · [Licenza MIT](LICENSE) · [Novità](CHANGELOG.md)

Un solo comando, `mac-update`, mantiene aggiornato il software del tuo Mac. Tocca solo ciò che è già installato.

## Cosa aggiorna

Una esecuzione passa in ordine per questi gruppi:

1. app dell'App Store
2. strumenti del Terminale (npm, bun, strumenti da riga di comando)
3. formule e app di Homebrew
4. app da internet (dal feed di aggiornamento del produttore, con un download diretto verificato o con l'aggiornatore dell'app stessa)
5. l'elenco delle tue app
6. macOS, sempre per ultimo

Non devi approvare le app una per una. Se vuoi un comportamento diverso per una app, impostala su manuale o salta nella scheda **App**. Per macOS puoi scegliere in **Impostazioni** se installare gli aggiornamenti, solo essere avvisato, oppure lasciarlo disattivato.

## Installazione

Incolla questo nel Terminale:

```bash
/bin/bash -c "$(curl -fsSL https://github.com/KasprowiczM/macOS_updates/releases/latest/download/install.sh)"
```

Il programma di installazione scarica l'ultima versione, ne controlla la somma di controllo SHA-256, mette il programma in `~/.local/share/mac-update` e collega il comando `mac-update` in `~/.local/bin`. Non serve `git`, non usa mai `sudo` e, quando aggiorni il programma, conserva le tue impostazioni. Per vedere prima cosa farebbe, aggiungi `--dry-run`: `... install.sh | bash -s -- --dry-run`. Dettagli: [docs/INSTALL.md](docs/INSTALL.md) (in English).

Se dopo l'installazione `mac-update` non viene trovato, apri una nuova finestra del Terminale. Se ancora non viene trovato, esegui di nuovo il programma di installazione con `--configure-shell`.

## Prima esecuzione

```bash
mac-update
```

In un terminale si apre un'interfaccia con le schede: Panoramica, App, Catalogo, Cronologia, Impostazioni, Diagnostica, Aiuto. Scegli **Anteprima (nessuna modifica)** per vedere cosa succederebbe, poi **Aggiorna tutto**. La schermata del risultato mostra cosa è stato **Aggiornate**, cosa è **Già aggiornate** e cosa **Serve te**, con un motivo e un passo successivo per ogni voce.

Solo testo: `mac-update run`. `mac-update --cli` (anche `--plain`) equivale a `mac-update run`, `mac-update --tui` equivale a `mac-update` da solo, e `macos-update` è lo stesso comando con un nome più lungo. Funzionano tutti da qualsiasi cartella. Anteprima in solo testo: `mac-update preview`. Controllo del Mac senza aggiornare: `mac-update doctor`. Tutti i comandi: `mac-update help`. Manca qualcosa (Command Line Tools, Homebrew nativo, Python, `mas`)? `mac-update doctor` lo elenca e `mac-update prepare` lo installa dopo una sola domanda.

Arrivi da una vecchia copia basata su git? Esegui `mac-update migrate` per spostare le tue impostazioni (prima mostra un'anteprima).

## Sicurezza

- Le app che hai aperte non vengono mai chiuse. Sono segnalate come "Serve te".
- I download arrivano solo da host consentiti e devono superare il controllo della firma del codice e Gatekeeper.
- Un aggiornamento non installa mai un'app che non hai.
- Un elemento che fallisce non ferma gli altri, e macOS si aggiorna comunque per ultimo.
- Le password si digitano nel Terminale e non vengono mai salvate. Un'esecuzione automatica non fa mai domande.

## Esecuzioni automatiche

Disattivate per impostazione predefinita, senza un orario preimpostato. Per attivarle apri **Impostazioni**, sezione **Esecuzioni automatiche**: scegli un'ora del giorno, «all'accesso» oppure entrambi, e come vuoi essere avvisato. Un'esecuzione automatica salta gli aggiornamenti di macOS, a meno che tu non li attivi. Vedi [Operazioni](docs/user/it/OPERATIONS.md).

## Documentazione

| Lingua | Avvio rapido | Guida | Operazioni |
|--------|--------------|-------|------------|
| Italiano | [Avvio rapido](docs/user/it/QUICK_START.md) | [Guida](docs/user/it/GUIDE.md) | [Operazioni](docs/user/it/OPERATIONS.md) |

Tutte le lingue: [docs/user/INDEX.md](docs/user/INDEX.md) · [Installazione](docs/INSTALL.md) · [Disinstallazione](docs/UNINSTALL.md)

## Licenza

[MIT](LICENSE)
