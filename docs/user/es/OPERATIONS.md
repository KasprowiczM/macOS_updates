# Operaciones (español)

**macOS Updates 2.0.10** · para quien ejecuta el programa desde Terminal, un script o una programación.

## Formas de ejecutar

| Comando | Qué ocurre |
|---------|------------|
| `mac-update` | Abre la interfaz (necesita un terminal). |
| `mac-update run [opciones]` | Ejecución en texto sencillo. Las opciones pasan al programa de actualización, por ejemplo `-y`, `--skip-system`, `--non-interactive`. |
| `mac-update --cli [options]` | Lo mismo que `mac-update run` (también `--plain`). |
| `mac-update --tui` | Lo mismo que `mac-update`: abre la interfaz. |
| `mac-update preview` | Recorre cada paso e imprime qué pasaría. No se actualiza nada. |
| `mac-update scan` | Rehace la lista de apps de este Mac. Solo lee. |
| `mac-update doctor` | Informe de preparación de solo lectura. Sin contraseña y sin registro de ejecución. |
| `mac-update settings` | Abre la interfaz en la pestaña Ajustes. |
| `mac-update update-self` | Busca una versión más reciente de mac-update (`--check`, el valor predeterminado, o `--prepare`). |
| `mac-update migrate` | Trae los ajustes de una copia antigua basada en git: `--preview` (predeterminado), `--apply`, `--undo MANIFEST`. |
| `mac-update uninstall` | Quita mac-update. Consulta [UNINSTALL.md](../../UNINSTALL.md). |
| `mac-update version`, `mac-update help` | Versión y lista de comandos. |

`macos-update` es el mismo comando que `mac-update`, con un nombre más largo. El instalador enlaza ambos en `~/.local/bin`, y ambos funcionan desde cualquier carpeta.

`mac-update` llama a `update_all.sh` en la carpeta del programa `~/.local/share/mac-update`. Si en cambio trabajas desde una copia de git, ejecuta `bash update_all.sh` allí; las opciones de abajo son las mismas. Con `MAC_UPDATE_NONINTERACTIVE=1` la interfaz nunca se abre y nada espera una respuesta.

## Opciones de `update_all.sh`

| Opción | Significado |
|--------|-------------|
| `-y`, `--yes` | Omite la pregunta de confirmación |
| `-h`, `--help` | Muestra la lista de opciones |
| `--tui`, `--cli` | Elige la interfaz o el texto sencillo. `--tui` falla con un mensaje si no hay un terminal utilizable; solo se pueden añadir `--dry-run` y `--skip-...`. |
| `--dry-run` | Vista previa, no cambia nada |
| `--doctor` | Informe de preparación. Salida 0 correcto, 10 avisos, 1 problema |
| `--verify-only` | Compara las versiones de las apps instaladas con el historial, no cambia nada |
| `--json-summary` | Imprime un resumen en JSON al final |
| `--bootstrap-cli` | Instala también un Node, Bun o una herramienta nativa de línea de comandos gestionados que falten. Desactivado por defecto. |
| `--skip-prescan` | Omite la primera revisión de la lista de apps |
| `--skip-appstore` | Omite las apps de App Store |
| `--skip-npm` | Omite las herramientas de Terminal (npm, bun, herramientas nativas de línea de comandos) |
| `--skip-brew` | Omite Homebrew |
| `--skip-internet` | Omite las apps de internet |
| `--skip-postupdate` | Omite la renovación de la lista de apps y del historial |
| `--skip-system` | Omite la actualización de macOS |
| `--skip-doctor` | Omite `brew doctor` dentro del paso de Homebrew |
| `--treat-appstore-ax-as-warning` | Indica como aviso la falta del permiso de Accesibilidad |
| `--non-interactive` | Para programadores de tareas: sin preguntas (igual que `MAC_UPDATE_NONINTERACTIVE=1`) |
| `--notify` | Muestra una notificación de macOS cuando termina la ejecución |

Los pasos siempre se ejecutan en este orden: revisión del sistema, App Store, herramientas de Terminal, Homebrew, apps de internet, lista de apps, macOS. macOS va al final porque puede reiniciar el Mac. Si un paso anterior falló gravemente, el paso de macOS espera a la siguiente ejecución.

## Variables de entorno

Ponlas delante del comando, por ejemplo `MAC_UPDATE_MIN_FREE_GB=30 mac-update run`. La mayoría también existen como fila en Ajustes; una fila definida por una variable no se puede cambiar en la interfaz.

| Variable | Valor predeterminado | Para qué sirve |
|----------|----------------------|----------------|
| `MAC_UPDATE_NONINTERACTIVE` | desactivado | `1`: sin interfaz y sin preguntas |
| `MAC_UPDATE_DRY_RUN` | desactivado | `1`: igual que `--dry-run` |
| `MAC_UPDATE_SKIP_APPSTORE`, `_NPM`, `_BREW`, `_INTERNET`, `_SYSTEM`, `_PRESCAN`, `_POSTUPDATE`, `_DOCTOR` | desactivado | `1`: igual que la opción `--skip-...` correspondiente |
| `MAC_UPDATE_SYSTEM_MODE` | `auto` | Actualizaciones de macOS: `auto` instala, `notify` solo avisa, `skip` no comprueba |
| `MAC_UPDATE_NEW_APP_MODE` | según confianza | `auto` o `manual` para las apps encontradas nuevas que no están en la lista probada |
| `MAC_UPDATE_NOTIFY` | desactivado | `1`: notificación al terminar. En ejecuciones automáticas: `always`, `needs_you` o `never` |
| `MAC_UPDATE_LANG` | idioma del sistema | `en`, `pl`, `de`, `fr`, `es`, `it`, `pt` |
| `MAC_UPDATE_HOME` | `~/.local/share/mac-update` | Carpeta del programa |
| `MAC_UPDATE_CONFIG_DIR` | `~/.config/mac-update` | Carpeta de ajustes |
| `MAC_UPDATE_STATE_DIR` | `~/.local/state/mac-update` | Registros, cachés, copias de seguridad |
| `MAC_UPDATE_LOGS_DIR` | `logs` en la carpeta de estado | Registros de ejecución |
| `MAC_UPDATE_OVERRIDES_FILE` | `overrides.tsv` en la carpeta de ajustes | Archivo de elecciones por app |
| `MAC_UPDATE_MAX_LOGS` | 30 | Registros de ejecución que conservar |
| `MAC_UPDATE_PROMPT_TIMEOUT` | 120 | Segundos para responder una pregunta antes de usar la respuesta segura |
| `MAC_UPDATE_MIN_FREE_GB` | 15 | Avisa y ejecuta de forma reducida si hay menos espacio libre que este |
| `MAC_UPDATE_MIN_BATTERY` | 30 | Con batería por debajo de este porcentaje, omite el paso de macOS (una ejecución automática se omite por completo) |
| `MAC_UPDATE_NO_CAFFEINATE` | desactivado | `1`: no mantiene el Mac activo durante la ejecución |
| `MAC_UPDATE_NO_SUDO_KEEPALIVE` | desactivado | `1`: no mantiene vigente la contraseña de administrador |
| `MAC_UPDATE_SUDO_KEEPALIVE_MAX` | 14400 | Segundos que se mantiene vigente (300 a 14400) |
| `MAC_UPDATE_QUIT_WAIT` | 60 | Segundos que se espera a que se cierre una app que abrió el programa (0 a 300) |
| `MAC_UPDATE_STAGE_WAIT` | 90 | Segundos que se espera a que una app abierta por el programa instale su propia actualización (0 a 600) |
| `MAC_UPDATE_POST_QUIT_WAIT` | 10 | Segundos de espera tras cerrar esa app cuando su actualización quedó preparada |
| `MAC_UPDATE_POST_QUIT_WAIT_IDLE` | 3 | Lo mismo, cuando no quedó preparada ninguna actualización |
| `MAC_UPDATE_OMAHA_WAIT` | 45 | Segundos que se espera la respuesta del actualizador de Google (0 a 180) |
| `MAC_UPDATE_OMAHA_MAX_AGE_H` | 6 | Horas durante las que una comprobación del actualizador de Google se considera reciente |
| `MAC_UPDATE_BTM_CHECK` | activado | `0`: no comprobar si macOS bloquea una app en Ítems de inicio y extensiones |
| `MAC_UPDATE_BTM_TIMEOUT` | 4 | Segundos permitidos para esa comprobación |
| `MAC_UPDATE_BTM_DUMP`, `MAC_UPDATE_GOOGLE_USER_LOG`, `MAC_UPDATE_GOOGLE_SYS_LOG` | ninguno | Solo para diagnóstico y pruebas: una lista guardada de ítems de inicio o archivos de registro del actualizador de Google, que se leen en lugar de los reales |
| `MAC_UPDATE_VENDOR_DIRECT` | activado | `0`: sin descargas directas del creador de la app |
| `MAC_UPDATE_ALLOW_MAJOR_UPGRADE` | desactivado | `1`: permite saltos grandes de versión, incluida una actualización principal de macOS |
| `MAC_UPDATE_MAU_DEFERRAL_DAYS` | 7 | Días de espera antes de instalar una nueva versión de Microsoft Office |
| `MAC_UPDATE_FEED_CACHE_TTL_H` | 24 | Horas durante las que se reutiliza la información de versiones del fabricante |
| `MAC_UPDATE_MAS_UPGRADE_TIMEOUT` | 1800 | Segundos antes de que una actualización de App Store se detenga y se notifique |
| `MAC_UPDATE_DOCTOR_PROBE_AX` | desactivado | `1`: deja que `doctor` pruebe el permiso de Accesibilidad (macOS puede mostrar un aviso) |
| `GITHUB_TOKEN` | ninguno | Opcional. Aumenta el límite de descargas de GitHub. Defínelo en el perfil de tu shell |

## Ejecuciones automáticas (opcional)

Las ejecuciones automáticas están desactivadas por defecto y no tienen hora predeterminada. Actívalas en **Ajustes**, sección **Ejecuciones automáticas**, fila "Automatización diaria". Tú eliges:

- cuándo: cada día a la hora que escribas (formato de 24 horas, por ejemplo 08:30), al iniciar sesión, o ambas;
- cómo se te avisa: tras cada ejecución, solo si algo te necesita (el valor predeterminado) o nunca.

Ves exactamente qué se va a instalar y confirmas antes de que se escriba nada. "Probar ahora" programa una ejecución adicional dentro de unos minutos.

Lo mismo desde Terminal, con `bash ~/.local/share/mac-update/scripts/install_launchagent.sh`:

```bash
bash scripts/install_launchagent.sh --daily 08:30 --notify needs_you      # every day at 08:30
bash scripts/install_launchagent.sh --daily 08:30 --days 1,3,5            # only on chosen weekdays (numbers 1 to 7)
bash scripts/install_launchagent.sh --at-login --delay-min 10             # at login, after 10 minutes of session time
bash scripts/install_launchagent.sh --once-in 5                           # one test run in 5 minutes
bash scripts/install_launchagent.sh --status                              # is it installed? (--check, or --status --json)
bash scripts/install_launchagent.sh --uninstall                           # remove every mac-update schedule
```

Ejecuta esto desde la carpeta del programa. `--notify` acepta `always`, `needs_you` o `never`.

Qué hace una ejecución automática:

- Se ejecuta sin terminal y nunca hace una pregunta.
- Omite las actualizaciones de macOS salvo que las actives; entonces macOS solo indica qué hay disponible.
- Se omite sola si hay otra ejecución en marcha, si el Mac tiene la batería baja o si la última ejecución correcta fue hace menos de 12 horas.
- Todo lo que necesite tu contraseña o un reinicio se omite y se indica como "Requieren acción". Ejecuta `mac-update` tú mismo para terminarlo.
- Envía una notificación, según lo que elegiste. La salida va a `launchd.out` y `launchd.err` en la carpeta de registros.

## Contraseñas

Los pasos de macOS y de App Store pueden necesitar tu contraseña de administrador. En Terminal, el programa la pide como mucho una vez por ejecución y la mantiene vigente el resto de la ejecución. Nunca la pide en una vista previa, ni sin terminal (las ejecuciones automáticas omiten esos pasos). Opcional: `bash scripts/setup_touchid_sudo.sh --check` indica si Touch ID puede sustituir la contraseña en `sudo`. Si ejecutas el script sin `--check`, muestra una vista previa y pregunta antes.

## Dónde está cada cosa

| Qué | Dónde |
|-----|-------|
| El programa | `~/.local/share/mac-update` |
| Tus ajustes y elecciones por app | `~/.config/mac-update` (`overrides.tsv`, `lang`, `reports/`) |
| Registro de cada ejecución | `~/.local/state/mac-update/logs/update_all_<date>_<time>.log` (se conservan los 30 más recientes, modo 600) |
| Resultado breve de la última ejecución | `~/.local/state/mac-update/logs/run_summary_latest.json` |
| Ajustes de la interfaz | `~/.local/state/mac-update/tui-settings.json` |
| Salida de las ejecuciones automáticas | `~/.local/state/mac-update/logs/launchd.out`, `launchd.err` |

Una vista previa escribe su registro en una carpeta temporal y deja tu historial sin cambios. Dentro de la interfaz, la pestaña **Historial** enumera las ejecuciones pasadas y `L` abre el registro más reciente. Si vienes de una copia antigua basada en git: `mac-update migrate`.

Código de salida de `update_all.sh`: `0` si la ejecución fue limpia o solo tuvo avisos (una app que requiere acción es un aviso), `1` si algo falló.

## Solución de problemas

Empieza con `mac-update doctor`. Comprueba la plataforma, Python, curl, Homebrew, `mas`, Touch ID, el espacio en disco, la alimentación, la red y el propio programa.

| Problema | Qué hacer |
|----------|-----------|
| `mac-update: command not found` | Abre una ventana nueva de Terminal. Si persiste, `~/.local/bin` no está en tu `PATH`: vuelve a ejecutar el instalador con `--configure-shell` o añade esa carpeta tú mismo. |
| `mac-update` inicia otro programa | Otro programa con ese nombre aparece antes en tu `PATH`. El instalador avisa de ello y nombra el archivo de ese programa. Ejecuta `~/.local/bin/mac-update` directamente, o elimina o renombra el otro archivo. |
| La interfaz no se abre | Necesita un terminal, Python 3 y un `TERM` que no sea `dumb`. Si no, usa `mac-update run`. |
| El instalador dice que la suma de comprobación no coincide | No se instaló nada. Inténtalo más tarde; si se repite, avísalo. |
| Una app aparece en "Requieren acción" | Consulta la tabla "Qué significa "Requieren acción"" en [GUIDE.md](GUIDE.md). |
| El paso de App Store se detiene con el código de salida 2 | Al terminal le falta el permiso de Accesibilidad. Permítelo en Ajustes del Sistema, Privacidad y seguridad, Accesibilidad, o añade `--treat-appstore-ax-as-warning`. |
| Falta `mas` o es demasiado antiguo | El programa lo indica y nunca lo instala por sí solo. Instálalo tú mismo con Homebrew (`brew install mas`). |
| App Store necesita que inicies sesión | Abre App Store, inicia sesión y vuelve a ejecutar. |
| Falta Homebrew | Instálalo desde <https://brew.sh> y vuelve a ejecutar. |
| La lista de apps falta o es incorrecta | `mac-update scan`. Solo lee tu Mac. Nunca copies la lista de otra persona. |
| Una app nunca se actualiza | Diagnóstico, "Cómo se actualizan las apps", muestra cómo se trata cada app. Si no hay método, abre la app y usa su propia opción "Buscar actualizaciones". |
| No se puede acceder a la información de actualizaciones de un fabricante | Inténtalo más tarde. Comprueba los canales en Diagnóstico, "Comprobar canales de actualización". |
| El Mac se suspendió durante una ejecución | Deja activada "Mantener el Mac activo" (valor predeterminado). |
| Una actualización se interrumpió | Diagnóstico, "Terminar actualizaciones interrumpidas". |
| Una ejecución dice que hay otra en marcha | Espera a que termine. Una marca sobrante de una ejecución que falló se limpia al empezar la siguiente. |
| Poco espacio en disco o poca batería | Libera espacio o conecta el cargador. Los límites están en Ajustes, "Comprobaciones de seguridad". |

¿Sigues atascado? Abre el archivo más reciente de la carpeta de registros y busca la primera línea que diga error o warning.

## Desinstalar

```bash
mac-update uninstall
```

También desactiva las ejecuciones automáticas. Consulta [UNINSTALL.md](../../UNINSTALL.md) para saber qué se quita y qué no.
