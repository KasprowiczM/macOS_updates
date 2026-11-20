# Guía de usuario (español)

**macOS Updates 2.0.10** · Mac con Apple Silicon · macOS 13 o posterior

## Qué hace

Cada ejecución actualiza, en este orden:

1. Apps de App Store
2. Herramientas de Terminal (npm, bun y herramientas de línea de comandos que se actualizan solas)
3. Fórmulas y casks de Homebrew
4. Apps de internet: apps que descargaste de la web del fabricante, actualizadas desde su canal de actualizaciones, con una descarga directa verificada o con el actualizador de la propia app
5. La lista de tus apps (se renueva)
6. macOS, siempre al final

No te pide aprobar cada app. Solo actúa sobre lo que ya está instalado.

## Lo que nunca hace

- Nunca cierra una app que tengas abierta. Esa app se indica en "Requieren acción".
- Nunca instala una app que no tienes. (La pestaña opcional Catálogo es el único sitio que puede instalar, y solo lo que tú elijas.)
- Nunca se fía de una descarga a ciegas. Debe venir de un servidor permitido, llevar una firma de código válida y superar Gatekeeper.
- Nunca lo detiene todo porque un elemento falle. Los demás elementos, los pasos siguientes y la actualización de macOS se ejecutan igualmente.

## Abrir la interfaz

```bash
mac-update
```

En Terminal, esto abre la interfaz. En un script, por SSH sin terminal o con `MAC_UPDATE_NONINTERACTIVE=1`, obtienes texto sencillo. `mac-update run` siempre da texto sencillo. `mac-update --cli` (también `--plain`) es lo mismo que `mac-update run`, `mac-update --tui` es lo mismo que `mac-update` solo, y `macos-update` es el mismo comando con un nombre más largo. Todos funcionan desde cualquier carpeta. La ventana necesita al menos 40 columnas por 12 filas. Más grande es más cómodo: si dejas activada "Ajustar la ventana automáticamente", la interfaz pide al terminal 120 por 36 al iniciar y restaura el tamaño al salir.

Muévete con las flechas. Intro abre o confirma, Tab pasa al siguiente panel, Esc vuelve atrás, `1` a `7` saltan a una pestaña, `?` abre la ayuda, `L` muestra el registro completo y `q` sale. El ratón también funciona. La línea inferior siempre muestra las teclas que sirven en ese momento.

## Las pestañas

```
 macOS Updates                                  Última vez: listo, hace 2 h
 Panel   Apps   Catálogo   Historial   Ajustes   Diagnóstico   Ayuda
 +- Grupos de actualización -------------------------------------------+
 | > v Revisión del sistema  ############  listo                        |
 |   v App Store             ############  v3 .5                        |
 |   v Herramientas de Term. ############  v2 .9                        |
 |   * Homebrew              ######......  4/9  v1 .3                   |
 |   . Apps de internet      ............  en espera                    |
 |   . Lista de apps         ............  en espera                    |
 |   . Sistema macOS         ............  en espera                    |
 +---------------------------------------------------------------------+
   [ Actualizar todo ]   [ Vista previa (sin cambios) ]
   v actualizadas   . al día   ! requieren acción   x con error
```

Es un dibujo simplificado. La pantalla real usa colores y símbolos.

| Pestaña | Para qué sirve |
|---------|----------------|
| **Panel** | Iniciar una actualización. Muestra cada grupo con el progreso en directo (hechas de un total) y, mientras se ejecuta, una lista desplazable de las apps que contiene. Intro o la barra espaciadora sobre un grupo lo activa o desactiva para la próxima ejecución. Un panel lateral muestra la última ejecución, lo que aún requiere acción, la próxima ejecución automática y el estado de este Mac. |
| **Apps** | Todas las apps y paquetes que hay en este Mac (las apps auxiliares y de segundo plano se dejan fuera). Elige cómo se actualiza cada una. |
| **Catálogo** | Todas las apps probadas: primero las que aún se pueden añadir y después las ya instaladas (solo se muestran). No se selecciona nada hasta que lo eliges, y el instalador pregunta antes de cada cambio. Las ejecuciones de actualización nunca lo usan. |
| **Historial** | Ejecuciones anteriores, de la más reciente a la más antigua, cada una con su resultado. Elige una para ver qué se actualizó y qué requirió acción. Intro abre su registro completo. |
| **Ajustes** | Qué actualizar, límites de seguridad, programación, idioma y aspecto. Cada cambio se guarda al instante. |
| **Diagnóstico** | Comprobaciones que puedes ejecutar: revisar este Mac, comprobar requisitos, cómo se actualizan las apps (una tabla con todas las apps y cómo se averiguó su método), comprobar canales de actualización, rehacer la lista de apps, terminar actualizaciones interrumpidas, buscar actualización del programa. |
| **Ayuda** | Una guía breve: primeros pasos, cómo funciona la actualización, para qué sirve cada pestaña y qué significa "Requieren acción". |

## Ejecutar una actualización

- **Actualizar todo** revisa y actualiza cada grupo que esté activado.
- **Vista previa (sin cambios)** sigue los mismos pasos y muestra qué pasaría. No instala nada y no escribe historial.

Durante la ejecución ves cada grupo y cada app: comprobando, descargando, verificando, instalando. Pulsa `L` para ver el registro completo. **Detener** termina la ejecución de forma segura: las apps ya actualizadas siguen actualizadas.

Las preguntas (por ejemplo, un reinicio) esperan tu respuesta. Si no respondes a tiempo, se usa la respuesta segura. Tu contraseña de administrador se escribe en Terminal y nunca se guarda ni se muestra.

La pantalla de resultados enumera:

- **Actualizadas**: ya están al día.
- **Al día**: no hizo falta nada.
- **Requieren acción**: mira más abajo.

## Cómo se actualizan las apps de internet

- Las apps con una descarga verificada de su fabricante (por ejemplo Claude y Antigravity IDE) se instalan directamente en lugar de abrirlas y esperar. Si esa descarga falla, se sigue usando el actualizador propio de la app.
- Una app abierta para que se actualice sola se cierra en cuanto su actualización queda preparada (Warp), en lugar de esperar todo el tiempo.
- Chrome durante un despliegue gradual se informa de inmediato cuando el actualizador de Google ya respondió «sin actualización» para tu versión.
- Las apps de Google (Gemini, Chrome, Google Drive) muestran cuándo comprobó por última vez el actualizador de Google y cuándo volverá a hacerlo, o que la app se actualizó sola.
- Una app de Homebrew que estaba abierta y ya se actualizó sola se informa como al día, sin aviso.
- Cuando macOS bloquea una app en **Ítems de inicio y extensiones** (se cierra nada más abrirla), el resultado lo dice e indica dónde permitirla: Ajustes del Sistema › General › Ítems de inicio y extensiones.

## Ajuste por app

Abre la pestaña **Apps**. Escribe `/` para buscar por nombre u origen. Pulsa Intro sobre una app. La barra espaciadora marca varias apps para cambiarlas a la vez.

| Modo | Significado |
|------|-------------|
| **automático** | El programa la actualiza por ti. Es el valor predeterminado. |
| **manual** | El programa solo te avisa cuando hay una actualización pendiente. |
| **omitir** | El programa no la toca. |

También puedes elegir un **origen preferido** cuando una app tiene más de uno: origen predeterminado, Homebrew, App Store, web del fabricante o actualizador integrado. La columna **Método** indica cómo conoce el programa la app: probada (está en la lista de apps probadas del programa), detectada automáticamente (encontrada por un recibo de App Store, Homebrew, un canal de actualizaciones o un actualizador integrado) o manual (no se reconoció nada). El ajuste "Apps encontradas nuevas" decide qué pasa con las apps que un análisis encuentra y no están en la lista probada: según confianza (automático si el método de actualización es claro, manual si no), siempre automático o siempre manual.

Si la lista está vacía, elige **Analizar ahora**. Analizar solo lee tu Mac.

Tus elecciones se guardan en `~/.config/mac-update/overrides.tsv`, una línea por app: grupo, nombre, modo, origen (separados por tabuladores). Borra el archivo para devolver todas las apps a automático.

## Ajustes

Elige un perfil para empezar rápido: **Automático total** (todo), **Prudente** (sin actualización de macOS ni saltos grandes de versión), **Solo revisar** (no se instala nada). Cualquier cambio manual muestra **Personalizado**.

| Sección | Filas |
|---------|-------|
| Qué actualizar | Un interruptor por grupo; Solo revisar, nunca instalar; Permitir actualizaciones grandes (desactivado, te mantiene en la versión principal actual); Actualizaciones de macOS: instalar, solo avisar o desactivado (antes de reiniciar siempre se pregunta) |
| Apps y orígenes | Apps encontradas nuevas (según confianza, automático, manual); Modo y origen por app (abre la pestaña Apps); Apps excluidas (`config/inventory_exclusions.txt`); Herramientas npm vigiladas (`config/npm_global_clis.txt`) |
| Ejecuciones automáticas | Automatización diaria (desactivada por defecto, sin hora predeterminada): cuándo se ejecuta (cada día a la hora que elijas, al iniciar sesión, o ambas) y el aviso tras una ejecución (tras cada ejecución, solo si algo me necesita, nunca); Probar ahora |
| Comprobaciones de seguridad | Esperar a que se cierren las apps (s); Descargar de webs de fabricantes; Espacio libre mínimo (GB, 15 por defecto); Nivel mínimo de batería (%, 30 por defecto) |
| Red y velocidad | Reutilizar comprobaciones durante (horas); Tiempo para responder (s, 120 por defecto); Límite de tiempo de App Store (s) |
| Avisos e informes | Aviso al terminar; Abrir el último registro; Registros que conservar (30 por defecto) |
| Idioma y aspecto | Idioma (English, Polski, Deutsch, Español, Français, Italiano, Português; sigue el idioma de tu sistema hasta que elijas uno); Colores; Color de énfasis (azul por defecto, violeta, ámbar, verde salvia, rosa, grafito); Espaciado; Caracteres sencillos; Ajustar la ventana automáticamente; Ratón; Panel de ayuda abierto al iniciar |
| Sistema y mantenimiento | Retraso de Microsoft Office (días); Mantener el Mac activo; Rehacer la lista de apps; Actualizar este programa; Exportar ajustes; Importar ajustes; Restablecer valores |

Los ajustes se guardan en `~/.local/state/mac-update/tui-settings.json` y tu idioma en `~/.config/mac-update/lang`. Una fila definida por una variable de entorno muestra esa variable y no se puede cambiar en la ventana. "Esperar a que se cierren las apps" se aplica a las apps que el propio programa abrió.

Los colores siguen a tu terminal. El valor por defecto, **automático**, pregunta a la terminal si su ventana es clara u oscura y usa el esquema que corresponde. El aspecto claro deja a la página el fondo blanco y el color de texto propios de tu terminal; solo la barra superior, la barra de teclas, la fila seleccionada y los cuadros de diálogo van en gris claro, y todos los colores se leen bien en una ventana blanca. El esquema oscuro no ha cambiado. Un «oscuro» guardado por una versión anterior se trata una vez como automático; si quieres oscuro siempre, elígelo de nuevo en Ajustes, Idioma y aspecto, Colores.

## Qué significa "Requieren acción"

Cada línea de la pantalla de resultados tiene un motivo y un siguiente paso.

| Motivo | Qué hacer |
|--------|-----------|
| **La app estaba abierta** | Cierra la app y vuelve a ejecutar la actualización. El programa nunca la cierra por ti. |
| **La tienda necesita que vuelvas a iniciar sesión** (App Store) | Abre App Store, inicia sesión y vuelve a ejecutar la actualización. |
| **Hacía falta una contraseña de administrador** | Vuelve a ejecutar la actualización desde Terminal e introduce tu contraseña de administrador cuando se pida. Las ejecuciones automáticas no pueden preguntar, así que lo indican. |
| **Hace falta reiniciar** | La actualización está instalada, pero surte efecto tras reiniciar. Reinicia el Mac cuando te venga bien. |
| **No hay una forma automática segura** | No hay una forma automática segura de actualizar esta app. Abre la app y usa su propia opción "Buscar actualizaciones". |
| **La descarga no terminó** | Comprueba la conexión a internet y vuelve a ejecutar la actualización. |
| **La suma de comprobación no coincide** | La descarga no coincidía con su suma de comprobación, así que no se instaló nada. Inténtalo más tarde; si sigue fallando, actualiza la app a mano. |
| **Modo manual** | Configuraste esta app como manual, así que solo se revisó. Actualízala tú mismo o cámbiala a automático en la pestaña Apps. |
| **No se pudo acceder a la información de actualizaciones del fabricante** | Inténtalo más tarde; puede que la web del fabricante esté caída. |
| **Hay una versión principal nueva** | Las actualizaciones grandes están desactivadas. Permítelas en Ajustes o actualiza la app a mano. |
| **No hay suficiente espacio en disco / batería demasiado baja** | Libera algo de espacio o conecta el adaptador de corriente, y vuelve a ejecutar la actualización. |
| **Tardó demasiado** | Vuelve a ejecutar la actualización; abre el registro completo (`L`) si se repite. |
| **Se abrió el actualizador de la propia app** | Termina la actualización en la ventana que abrió la app. |

Algunas apps instalan su actualización al cerrarse. Si el programa abrió esa app por sí mismo, la cierra en cuanto la actualización está lista. Una app que abriste tú nunca se cierra.

Si el motivo dice "No se conoce el motivo", abre el registro completo con `L`.

El encabezado, el Panel y el Historial muestran siempre las mismas cifras. Una app de iPad que la App Store sigue instalando tras la actualización aparece como «se sigue instalando en la App Store», sin nada que pulsar: espera unos minutos y comprueba de nuevo. Un actualizador en segundo plano que se puso en marcha pero no informó de ningún resultado aparece como «sin resultado registrado, nada que pulsar»; después se vuelve a leer su versión, de modo que una actualización terminada se muestra como actualizada.

## Dónde está cada cosa

| Qué | Dónde |
|-----|-------|
| Registros de ejecución (se conservan los 30 más recientes) | `~/.local/state/mac-update/logs/` |
| Tus elecciones por app, el idioma y la lista de tus apps | `~/.config/mac-update/` (`overrides.tsv`, `lang`, `reports/`) |
| El programa | `~/.local/share/mac-update/` |

Para opciones, variables de entorno y solución de problemas, consulta [OPERATIONS.md](OPERATIONS.md). Para instalar o quitar el programa, consulta [INSTALL.md](../../INSTALL.md) y [UNINSTALL.md](../../UNINSTALL.md).
