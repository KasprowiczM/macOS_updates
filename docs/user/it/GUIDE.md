# Guida utente (Italiano)

**Versione:** 1.0.20 · **Apple Silicon, macOS 13+**

## Cosa fa

macOS Updates orchestra gli aggiornamenti su **Mac Apple Silicon con macOS 13+**:

1. Pre-scansione e inventario
2. App Store (`sudo mas upgrade` + Track 2 GUI separato)
3. Node/Bun e CLI npm globali
4. Homebrew (`--greedy`)
5. App installate: handler diretti, CLI o trigger integrati
6. Post-aggiornamento atomico di inventario/cronologia
7. macOS (`softwareupdate -ia -R`) per ultimo; saltato dopo un errore precedente

**Non installa nuove applicazioni.** Ogni Mac costruisce il proprio inventario (`build_inventory.sh`).

## Installazione

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Report copertura

```bash
bash scripts/report_update_coverage.sh
```

Stati: **verified direct**, **triggered-unverified**, **externally managed**, **manual**, **unknown**. Un avvio silenzioso non prova l'aggiornamento. Inkscape usa Homebrew; UniFi/WiFiman/Picsart Track 2; Office `msupdate`; Teams il proprio updater con fallback MAU `TEAMS21` osservato e verificato. Solo IPMIView e DJI Assistant 2 restano manuali.

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
