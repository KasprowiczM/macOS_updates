# Inicio rápido (español)

**macOS Updates 2.0.10** · Mac con Apple Silicon · macOS 13 o posterior · unos 5 minutos

macOS Updates mantiene al día el software que ya está en tu Mac: apps de App Store, herramientas de Terminal, paquetes de Homebrew, apps que descargaste de internet y el propio macOS. Nunca instala apps que no tienes.

## 1. Instalar

Pega esto en Terminal:

```bash
/bin/bash -c "$(curl -fsSL https://github.com/KasprowiczM/macOS_updates/releases/latest/download/install.sh)"
```

El instalador descarga la versión, comprueba su suma de comprobación y añade el comando `mac-update`. No actualiza nada y no necesita `git` ni `sudo`. Necesitas Python 3.9 o posterior (si falta, el instalador te indica que ejecutes `xcode-select --install`). Detalles: [INSTALL.md](../../INSTALL.md).

Después abre una ventana nueva de Terminal para que se encuentre el comando. Si `mac-update` sigue sin encontrarse, vuelve a ejecutar el instalador con `bash -s -- --configure-shell` después de la tubería, como se explica en INSTALL.md.

## 2. Vista previa

```bash
mac-update
```

En Terminal se abre la interfaz en el **Panel**. Ve a **Vista previa (sin cambios)** con la flecha derecha y pulsa Intro. No se instala nada. Verás qué se actualizaría.

¿Prefieres texto sencillo? Ejecuta `mac-update preview`. `mac-update --cli` (también `--plain`) es lo mismo que `mac-update run`, `mac-update --tui` es lo mismo que `mac-update` solo, y `macos-update` es el mismo comando con un nombre más largo. Todos funcionan desde cualquier carpeta.

## 3. Actualizar

En el Panel elige **Actualizar todo** y pulsa Intro. Verás cada grupo (App Store, Herramientas de Terminal, Homebrew, Apps de internet, Lista de apps, Sistema macOS) y cada app mientras se actualiza. Si macOS te pide la contraseña, escríbela en Terminal; el programa nunca la guarda.

Puedes parar en cualquier momento. Las apps que ya se actualizaron siguen actualizadas.

## 4. Leer el resultado

La pantalla de resultados tiene tres listas:

- **Actualizadas**: estas apps ya están al día.
- **Al día**: no hizo falta nada.
- **Requieren acción**: el programa no pudo terminarlas por sí solo. Cada línea explica el motivo y qué hacer. Motivos típicos: la app estaba abierta, App Store necesita que inicies sesión o hace falta reiniciar. Consulta la [guía](GUIDE.md).

Las apps que tienes abiertas nunca se cierran. Ciérralas y vuelve a ejecutar la actualización.

## 5. Siguientes pasos

| Quiero... | Haz esto |
|-----------|----------|
| Cambiar cómo se actualiza una app | Pestaña Apps, Intro en la app: automático, manual u omitir |
| Desactivar un grupo o las actualizaciones de macOS | Panel: ve al grupo y pulsa la barra espaciadora. O Ajustes, "Actualizaciones de macOS" |
| Ejecutar sin la interfaz | `mac-update run` |
| Revisar mi Mac sin actualizar | `mac-update doctor` |
| Que se ejecute por sí solo | Ajustes, sección "Ejecuciones automáticas". Consulta [OPERATIONS.md](OPERATIONS.md) |
| Ver qué salió mal | Pestaña Historial, y Intro sobre una ejecución para abrir su registro |
| Traer los ajustes de una copia antigua basada en git | `mac-update migrate` (antes muestra una vista previa) |

Más: [GUIDE.md](GUIDE.md) · [OPERATIONS.md](OPERATIONS.md) · [UNINSTALL.md](../../UNINSTALL.md)
