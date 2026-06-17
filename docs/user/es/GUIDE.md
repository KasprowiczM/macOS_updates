# Guía de usuario (Español)

**Versión:** 1.0.19 · **Solo Apple Silicon**

## Qué hace

macOS Updates automatiza actualizaciones en **Macs Apple Silicon**:

1. Sistema macOS (`softwareupdate -ia -R`)
2. App Store (`sudo mas upgrade` + GUI para apps iPad)
3. Node/Bun y CLI npm globales
4. Homebrew
5. 40+ apps de Internet — **solo si están instaladas**
6. Catálogo `APPLICATIONS.md` e historial `UPDATES.md`

**No instala aplicaciones nuevas.** Cada Mac construye su inventario (`build_inventory.sh`).

## Instalación

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Informe de cobertura

```bash
bash scripts/report_update_coverage.sh
```

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
