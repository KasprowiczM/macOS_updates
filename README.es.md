# macOS Updates

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

**Versión 2.0.10** · Mac con Apple Silicon · macOS 13 o posterior · [Web](https://macos-updates.64bit.site) · [Licencia MIT](LICENSE) · [Cambios](CHANGELOG.md)

Un solo comando, `mac-update`, mantiene al día el software de tu Mac. Solo toca lo que ya está instalado.

## Qué actualiza

Cada ejecución recorre estos grupos, en este orden:

1. Apps de App Store
2. Herramientas de Terminal (npm, bun, herramientas de línea de comandos)
3. Fórmulas y casks de Homebrew
4. Apps de internet (desde el canal de actualizaciones del fabricante, una descarga directa verificada o el actualizador de la propia app)
5. La lista de tus apps
6. macOS, siempre al final

No tienes que aprobar nada app por app. Si quieres un comportamiento distinto para una app, ponla en manual o en omitir en la pestaña **Apps**. Las actualizaciones de macOS se pueden poner en instalar, solo avisar o desactivado en **Ajustes**.

## Instalación

Pega esto en Terminal:

```bash
/bin/bash -c "$(curl -fsSL https://github.com/KasprowiczM/macOS_updates/releases/latest/download/install.sh)"
```

El instalador descarga el paquete de la última versión, comprueba su suma de comprobación SHA-256, coloca el programa en `~/.local/share/mac-update` y enlaza el comando `mac-update` en `~/.local/bin`. No necesita `git`, nunca usa `sudo` y conserva tus ajustes al actualizar. Para ver antes qué haría, añade `--dry-run`: `... install.sh | bash -s -- --dry-run`. Detalles: [docs/INSTALL.md](docs/INSTALL.md) (en inglés).

Si después no se encuentra `mac-update`, abre una ventana nueva de Terminal. Si sigue sin encontrarse, vuelve a ejecutar el instalador con `--configure-shell`.

## Primera ejecución

```bash
mac-update
```

En Terminal se abre una interfaz con pestañas: Panel, Apps, Catálogo, Historial, Ajustes, Diagnóstico, Ayuda. Elige **Vista previa (sin cambios)** para ver qué pasaría y después **Actualizar todo**. La pantalla de resultados muestra qué quedó **Actualizadas**, qué estaba **Al día** y qué **Requieren acción**, con el motivo y el siguiente paso de cada una.

En texto sencillo: `mac-update run`. `mac-update --cli` (también `--plain`) es lo mismo que `mac-update run`, `mac-update --tui` es lo mismo que `mac-update` solo, y `macos-update` es el mismo comando con un nombre más largo. Todos funcionan desde cualquier carpeta. Vista previa en texto sencillo: `mac-update preview`. Revisar tu Mac sin actualizar: `mac-update doctor`. Todos los comandos: `mac-update help`. ¿Falta algo (Command Line Tools, Homebrew nativo, Python, `mas`)? `mac-update doctor` lo enumera y `mac-update prepare` lo instala tras una sola pregunta.

¿Vienes de una copia antigua basada en git? Ejecuta `mac-update migrate` para trasladar tus ajustes (antes muestra una vista previa).

## Seguridad

- Las apps que tienes abiertas nunca se cierran. Se indican como "Requieren acción".
- Las descargas solo vienen de servidores permitidos y deben superar la comprobación de firma de código y Gatekeeper.
- Una ejecución de actualización nunca instala una app que no tienes.
- Un elemento que falla no detiene a los demás, y macOS se actualiza igualmente al final.
- Las contraseñas se escriben en Terminal y nunca se guardan. Una ejecución automática nunca hace preguntas.

## Ejecuciones automáticas

Desactivadas por defecto, sin hora predeterminada. Para activarlas, abre **Ajustes**, sección **Ejecuciones automáticas**: elige una hora del día, "al iniciar sesión" o ambas, y cómo quieres recibir el aviso. Una ejecución automática omite las actualizaciones de macOS salvo que las actives. Consulta [Operaciones](docs/user/es/OPERATIONS.md).

## Documentación

| Idioma | Inicio rápido | Guía | Operaciones |
|--------|---------------|------|-------------|
| Español | [Inicio rápido](docs/user/es/QUICK_START.md) | [Guía](docs/user/es/GUIDE.md) | [Operaciones](docs/user/es/OPERATIONS.md) |

Todos los idiomas: [docs/user/INDEX.md](docs/user/INDEX.md) · [Instalación](docs/INSTALL.md) · [Desinstalación](docs/UNINSTALL.md)

## Licencia

[MIT](LICENSE)
