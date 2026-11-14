# Inicio rápido (Español)

**Se requiere Mac con Apple Silicon** · macOS 13+ · **v1.7.4**

## Configuración segura y fuentes de aplicaciones

`bash setup.sh --inspect` comprueba la preparación sin instalar dependencias, cambiar perfiles ni configurar Touch ID. Una herramienta ausente deja su función no disponible. En un terminal, `bash setup.sh --install-dependencies` muestra dependencias opcionales y pregunta antes de cada instalación; `bash setup.sh --configure-shell` presenta por separado el cambio de perfil. Rechazar una dependencia no bloquea funciones independientes. Si falta Python, instálalo explícitamente antes de crear el inventario. Un `mas` ausente o antiguo se indica sin instalarlo ni actualizarlo automáticamente.

El informe normal muestra aplicaciones instaladas. `bash scripts/report_update_coverage.sh --show-supported` muestra recetas ausentes del catálogo. Todavía no es un menú de instalación. Un recibo de App Store para CapCut conserva esa fuente incluso sin cask. Sin propiedad Homebrew confirmada se propone elegir fuente, sin adopción ni instalación. La resolución completa y selección interactiva corresponden a etapas posteriores.

## Instalación en una línea

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Usuario nuevo (solo GitHub)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh --inspect
bash build_inventory.sh
bash update_all.sh
```


## Propietario (GitHub + capa Proton Drive)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

Los archivos privados (`APPLICATIONS.md`, `UPDATES.md`, `.env`) provienen de su capa en la nube — no de GitHub.

## Comandos útiles

| Comando | Propósito |
|---------|-----------|
| `bash update_all.sh --dry-run -y` | Vista previa de todos los pasos |
| `bash update_system.sh` | Solo macOS |
| `bash update_appstore.sh` | Solo App Store |
| `bash update_brew.sh` | Solo Homebrew |
| `bash run_tests.sh` | Verificar la instalación |

Consulte [GUIDE.md](GUIDE.md) y [OPERATIONS.md](OPERATIONS.md).

La etapa B (1.6.2) añade un inventario de observación opcional: `bash build_inventory.sh --shadow`. Guarda identidades locales, evidencias de origen y escaneos incompletos en JSON privado, sin cambiar `APPLICATIONS.md` ni la ejecución de actualizaciones. `--dry-run` evita guardar, `--json` devuelve resultados estructurados y `--root RUTA` permite indicar varios directorios. Los conflictos son observaciones; la selección de fuentes y la protección de ejecución corresponden a la etapa C.
