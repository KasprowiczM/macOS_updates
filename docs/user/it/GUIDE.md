# Guida utente (Italiano)

**Versione:** 1.0.19 · **Solo Apple Silicon**

## Cosa fa

macOS Updates automatizza gli aggiornamenti su **Mac Apple Silicon**:

1. Sistema macOS (`softwareupdate -ia -R`)
2. App Store (`sudo mas upgrade` + GUI per app iPad)
3. Node/Bun e CLI npm globali
4. Homebrew
5. 40+ app da Internet — **solo se installate**
6. Catalogo `APPLICATIONS.md` e cronologia `UPDATES.md`

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
