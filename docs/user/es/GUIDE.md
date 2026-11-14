# Guía de usuario (Español)

**Versión:** 1.8.2 · **Apple Silicon, macOS 13+**

## Interfaz de terminal

En un terminal interactivo, `bash update_all.sh` abre el panel y muestra el asistente hasta completarlo. `bash setup.sh` abre el asistente y `bash build_inventory.sh` el inventario. El asistente se puede volver a abrir desde la navegación. Su finalización y los ajustes visuales se guardan sin conceder permisos de actualización. `--cli` selecciona la interfaz de texto anterior y `--tui` solicita el panel explícitamente. Opciones como `--dry-run` siguen en CLI; no combines `--tui` con otras opciones. `--tui` requiere un terminal funcional y Python. Las ejecuciones sin TTY o no interactivas siguen en CLI.

Elige grupos antes de iniciar. La navegación está a la izquierda, las acciones y la salida en el centro y la ayuda y los detalles a la derecha en cada pantalla. Solo se supervisa una tarea a la vez; siguen vigentes las confirmaciones existentes. Los ajustes incluyen idioma, tema, ASCII y tamaño automático. `?` abre ayuda, Ctrl+P la paleta y `c` copia el comando, la salida o el resumen enfocado. Ctrl+V pega solo en el cuadro de respuesta; Enter envía. La entrada se oculta si el proceso desactiva el eco.

Se necesitan al menos 80 columnas y 24 filas. Por defecto se solicitan al menos 140 columnas y 38 filas en terminales compatibles y el tamaño original al salir; el terminal puede ignorar ambas solicitudes. El tamaño automático se puede desactivar.

## Configuración segura y fuentes de aplicaciones

`bash setup.sh --inspect` comprueba la preparación sin instalar dependencias, cambiar perfiles ni configurar Touch ID. Una herramienta ausente deja su función no disponible. En un terminal, `bash setup.sh --install-dependencies` muestra dependencias opcionales y pregunta antes de cada instalación; `bash setup.sh --configure-shell` presenta por separado el cambio de perfil. Rechazar una dependencia no bloquea funciones independientes. Si falta Python, instálalo explícitamente antes de crear el inventario. Un `mas` ausente o antiguo se indica sin instalarlo ni actualizarlo automáticamente.

El catálogo opcional comienza sin selecciones. KeePassXC puede instalarse mediante Homebrew con aprobación separada tras comprobar de nuevo la fuente y la ausencia. La vista previa muestra el comando y sus efectos; la verificación utiliza el recibo de Homebrew. Las demás entradas conservan sus vías oficiales de obtención. Las aplicaciones existentes nunca se migran automáticamente.

Si el resultado de una instalación del catálogo es incierto, vuelve a abrirlo para una nueva comprobación de recuperación. No elimines bloqueos ni diarios manualmente. La instalación de KeePassXC por Homebrew requiere evidencia estable revisada con una validez de siete días; después queda la vía manual.

## Qué hace

macOS Updates orquesta actualizaciones en **Macs Apple Silicon con macOS 13+**:

1. Escaneo previo e inventario
2. App Store (`sudo mas upgrade <app-id>` + Track 2 GUI separado)
3. Primero las CLI nativas existentes, después Node/Bun y alternativas npm
4. Homebrew (greedy solo para los casks registrados como `brew_cask`)
5. Apps instaladas: operaciones con alcance tras consentimiento; actualizaciones de proveedores no aceptadas manuales
6. Post-actualización atómica del inventario/historial
7. macOS (`softwareupdate -i <label> -R`) al final; aplazado ante un error bloqueante o falta de autorización

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
2. `bash build_inventory.sh --cli`
3. `bash scripts/scaffold_internet_app.sh "/path/to/Observed.app" --json`
4. Revisa la propuesta JSON no ejecutable; una implementación posterior requiere revisión y `bash run_tests.sh`.

Sustituye el ejemplo por la ruta exacta de la aplicación instalada. El comando muestra una propuesta con datos privados eliminados y no ejecutable para su revisión. La exportación opcional exige repetirlo con `--export --accept PREVIEW_ID` tras revisar el identificador mostrado. Activar actualizaciones requiere una implementación revisada y pruebas de aceptación separadas.

## Solución de problemas

| Problema | Solución |
|----------|----------|
| Mac Intel | No compatible |
| Catálogo incorrecto | `bash build_inventory.sh --cli` |
| App sin actualizar | `bash scripts/report_update_coverage.sh` |
| Falta `APPLICATIONS.md` | `build_inventory.sh` o `dev_sync/dev-sync-import.sh` |

Completo: [../../agents/troubleshooting.md](../../agents/troubleshooting.md)

El inventario JSON local y los planes de acciones delimitadas están disponibles. `bash update_all.sh --plan` y `--dry-run` muestran las mismas decisiones sin guardar. Un proceso interactivo pregunta una vez por los alcances mostrados; `-y`, EOF y ejecución desatendida no conceden permisos nuevos. Use `--preferences` para revisar o restablecer decisiones. Las actualizaciones conservan origen y destino observados; conflictos, destinos ausentes o evidencia incierta aplazan ese destino. `build_inventory.sh --migration --preview` conserva bytes originales de Markdown y notas; acepte expresamente el ID mostrado. Las actualizaciones genéricas del proveedor siguen siendo manuales hasta verificar identidad y adaptador. Una entrada de catálogo no demuestra instalación ni consentimiento.


## Catálogo opcional y primera instalación

Las nuevas señales de aplicaciones son propuestas para revisar, no recetas ejecutables. `bash scripts/scan_update_feeds.sh` muestra un resumen agregado. La exportación permite previsualizar y aceptar explícitamente; se redacta, permanece local y nunca se sube. `bash setup.sh --catalog` abre el catálogo sin elementos seleccionados. `-y`, las ejecuciones no interactivas y EOF no instalan nada. En el menú, `check <number>` compara solo las fuentes elegidas. Los resultados indican la última versión estable compatible confirmada y fecha, con caché de 24 horas. Lo desconocido sigue siendo desconocido. Una ficha pública de Mac App Store no demuestra que la app esté disponible para tu cuenta.

El catálogo opcional comienza sin selecciones. KeePassXC permite instalación separadamente aprobada mediante Homebrew tras comprobar la fuente y su ausencia. La vista previa muestra el comando y los efectos declarados; se verifica el recibo Homebrew, no una receta del fabricante. Las demás entradas conservan vías oficiales revisadas. Las aplicaciones existentes nunca se migran automáticamente. Las recomendaciones se basan en datos disponibles de versiones estables.

## Estado local de las actualizaciones por receta

Las observaciones incompletas siguen siendo explícitas y los objetivos inseguros se bloquean. Las ventanas nativas y los mecanismos supervisados elegibles pueden ejecutarse en grupo con consentimiento y reservas compartidas. El actualizador del sistema requiere el bloqueo global exclusivo. Un reinicio pendiente o helper desconocido puede bloquear otras operaciones hasta una reconciliación revisada. Las pruebas con fixtures no prueban aceptación real. DeepSeek Harness permanece manual.

`--dry-run` muestra una vista previa legible de hasta 10 objetivos. `--dry-run --json-summary` o `--plan` ofrece el plan JSON completo. La vista previa no concede permiso ni ejecuta actualizaciones.

La pantalla de permisos muestra diez elementos elegibles por página. Escribe números como `1,3` para autorizar solo sus acciones mostradas; `n` y `p` cambian de página. Intro o `q` continúa sin nuevos permisos. Se explica el límite de 120 segundos; agotarlo no concede permiso. Los elementos bloqueados se resumen por separado. Usa `--preferences` para revisar decisiones manuales, ignoradas o aplazadas. El registro comienza antes de esta revisión.

## Controles y lista de aplicaciones

Tab cambia entre navegación, área de trabajo, salida y botones inferiores. Las flechas seleccionan, Espacio marca casillas y Enter activa el botón resaltado. Las preguntas abren automáticamente el campo de respuesta. Enviar confirma; Cancelar cierra el campo sin responder.

El inventario muestra aplicaciones guardadas agrupadas por origen, con búsqueda, filtros y ordenación. Guardar selección guarda exclusiones, sin instalar ni desinstalar aplicaciones. Volver a habilitar requiere consentimiento independiente para actualizar. La lista de vista previa permanece tras la simulación. El registro detallado está separado del estado de las aplicaciones.

Acerca de contiene el autor, enlaces y la comprobación explícita de actualizaciones de la herramienta. La vista previa fija una revisión. Aplicar cierra la interfaz y solicita confirmación en el terminal. El código modificado, una rama inesperada o conflictos de archivos bloquean la actualización. Los cambios locales nunca se envían al repositorio del autor.

El modo automático utiliza el permiso guardado si cubre el grupo elegible; de lo contrario ofrece una revisión AUTO separada. Las ventanas nativas autorizadas se abren en paralelo y las descargas comparten el grupo supervisado; las tareas Microsoft y Google se agrupan. Se conserva la gestión por App Store y Homebrew. DeepSeek Harness sigue manual; Open Design indica actualmente que no dispone de un método automático. El proveedor elige versiones según la configuración del canal existente. Un cambio de versión no equivale a finalización verificada. El trabajo sin confirmar mantiene el bloqueo del grupo y aplaza la actualización del sistema; Diagnóstico ofrece una revisión explícita de recuperación con nueva verificación de identidad. El permiso Google cubre todos los productos registrados con su actualizador, incluso fuera del catálogo, cuya lista completa se desconoce. Esto es independiente de aceptar una receta para una versión concreta. `bash update_all.sh --cli --automatic-internet-batch` permite la misma revisión sin interfaz de terminal; añade `--dry-run` para una vista previa sin cambios.
