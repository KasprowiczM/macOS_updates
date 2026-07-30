# Guía de usuario (Español)

**Versión:** 1.0.21 · **Apple Silicon, macOS 13+**

## Qué hace

macOS Updates orquesta actualizaciones en **Macs Apple Silicon con macOS 13+**:

1. Escaneo previo e inventario
2. App Store (`sudo mas upgrade` + Track 2 GUI separado)
3. Node/Bun y CLI npm globales
4. Homebrew (`--greedy`)
5. Apps instaladas: handlers directos, CLI o activadores integrados
6. Post-actualización atómica del inventario/historial
7. macOS (`softwareupdate -ia -R`) al final; omitido tras un fallo anterior

**No instala aplicaciones nuevas.** Cada Mac construye su inventario (`build_inventory.sh`).

## Instalación

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Informe de cobertura

```bash
bash scripts/report_update_coverage.sh
```

Estados: **verified direct**, **triggered-unverified**, **externally managed**, **manual**, **unknown**. Un inicio silencioso no prueba una actualización. Inkscape usa Homebrew; UniFi/WiFiman/Picsart Track 2; Office `msupdate`; Teams su propio updater con fallback MAU `TEAMS21` observado y verificado. Solo IPMIView y DJI Assistant 2 quedan manuales.

## Añadir app de Internet

1. Instalar la app en el Mac.
2. `bash build_inventory.sh`
3. `bash scripts/scaffold_internet_app.sh "Nombre" silent_launch`
4. `bash run_tests.sh`

## Solución de problemas

| Problema | Solución |
|----------|----------|
| Mac Intel | No compatible |
| Catálogo incorrecto | `bash build_inventory.sh` |
| App sin actualizar | `bash scripts/report_update_coverage.sh` |
| Falta `APPLICATIONS.md` | `build_inventory.sh` o `dev_sync/dev-sync-import.sh` |

Completo: [../../agents/troubleshooting.md](../../agents/troubleshooting.md)
