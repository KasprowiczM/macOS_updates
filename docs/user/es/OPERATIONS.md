# Manual de operaciones

Guía para el operador — mantenimiento diario y semanal del macOS Updates.

## Plataforma

**Solo Apple Silicon (arm64).** Los scripts terminan de inmediato en Mac Intel.

## Actualización semanal

```bash
cd ~/Dev_Env/macOS_updates
bash update_all.sh
```

En caso de fallo, revise: `logs/update_all_<timestamp>.log` (se conservan las últimas 30 ejecuciones).

## Orden del pipeline (`update_all.sh`)

| Paso | Script / acción | Flag de omisión |
|------|-----------------|-----------------|
| 0 | prescan → `APPLICATIONS.md` | `--skip-prescan` |
| 1 | `update_system.sh` | `--skip-system` |
| 2 | `update_appstore.sh` | `--skip-appstore` |
| 3 | `update_npm_cli.sh` | `--skip-npm` |
| 4 | `update_brew.sh` | `--skip-brew` |
| 5 | `update_internet_apps.sh` | `--skip-internet` |
| 6 | postupdate → `APPLICATIONS.md`, `UPDATES.md` | `--skip-postupdate` |

Vista previa sin cambios: `bash update_all.sh --dry-run -y`

## Análisis de fallos

| Paso fallido | Archivos a revisar |
|--------------|-------------------|
| App Store | `$SESSION_DIR/appstore_diag.txt`, instantánea del registro |
| Apps de Internet | `$SESSION_DIR/internet_diag.txt`, `internet_before/after.txt` |
| Homebrew | `$SESSION_DIR/brew_*_before/after.txt` |
| Cualquiera | `logs/update_all_*.log` (instantáneas añadidas con código de salida ≠ 0) |

Accesibilidad de App Store ausente → código de salida `2`; use `--treat-appstore-ax-as-warning` o conceda Accesibilidad al terminal.

Referencia completa de códigos de salida: `docs/agents/exit_codes.md`.

## Capa privada (Proton Drive)

Tras editar archivos privados localmente:

```bash
bash dev_sync/dev-sync-export.sh
bash dev_sync/dev-sync-verify-full.sh
bash dev_sync/dev-sync-prune-excluded.sh   # should report zero candidates
```

## Mac nuevo

**Usuario público:**

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
bash update_all.sh
```

**Propietario (capa en la nube):**

```bash
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

Inventario: `bash build_inventory.sh`

## Lista de verificación previa a la actualización

- [ ] Sesión iniciada en App Store (`mas account` o app App Store)
- [ ] Terminal con Accesibilidad (para la vía 2 de apps iPad)
- [ ] Espacio en disco ≥ 20 GB para actualizaciones grandes de macOS
- [ ] `sudo` disponible para `mas upgrade` y actualizaciones del sistema

## Verificación posterior a la actualización

```bash
mas outdated
brew outdated
softwareupdate -l
```

Lance de prueba aplicaciones críticas (navegador, VPN, IDE) si el paso de Internet reportó advertencias.
