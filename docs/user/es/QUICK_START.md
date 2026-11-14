# Inicio rápido (Español)

**Se requiere Mac con Apple Silicon** · macOS 13+ · **v1.8.0**

## Interfaz de terminal

En un terminal interactivo, `bash update_all.sh` abre el panel y muestra el asistente hasta completarlo. `bash setup.sh` abre el asistente y `bash build_inventory.sh` el inventario. El asistente se puede volver a abrir desde la navegación. Su finalización y los ajustes visuales se guardan sin conceder permisos de actualización. `--cli` selecciona la interfaz de texto anterior y `--tui` solicita el panel explícitamente. Opciones como `--dry-run` siguen en CLI; no combines `--tui` con otras opciones. `--tui` requiere un terminal funcional y Python. Las ejecuciones sin TTY o no interactivas siguen en CLI.

Elige grupos antes de iniciar. La navegación está a la izquierda, las acciones y la salida en el centro y los detalles a la derecha cuando hay espacio. Solo se supervisa una tarea a la vez; siguen vigentes las confirmaciones existentes. Los ajustes incluyen idioma, tema, ASCII y tamaño automático. `?` abre ayuda, Ctrl+P la paleta y `c` copia el comando, la salida o el resumen enfocado. Ctrl+V pega solo en el cuadro de respuesta; Enter envía. La entrada se oculta si el proceso desactiva el eco.

Se necesitan al menos 80 columnas y 24 filas. Por defecto se solicitan al menos 140 columnas y 38 filas en terminales compatibles y el tamaño original al salir; el terminal puede ignorar ambas solicitudes. El tamaño automático se puede desactivar.

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
bash build_inventory.sh --cli
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
