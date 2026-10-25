# macOS Updates

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

**Sitio web:** [macos-updates.64bit.site](https://macos-updates.64bit.site) · **Repositorio:** [github.com/KasprowiczM/macOS_updates](https://github.com/KasprowiczM/macOS_updates) · **Licencia:** [MIT](LICENSE) · **Cambios:** [CHANGELOG.md](CHANGELOG.md)

> **v1.5.5** — Orquestador de actualizaciones en un solo comando, listo para producción, para **Macs con Apple Silicon y macOS 13–27**. Coordina actualizaciones de paquetes verificadas y activadores honestos de los actualizadores de cada app para el **software ya instalado en este Mac**. **Multilingüe** (7 idiomas). Capa privada opcional en la nube mediante [`dev_sync/`](dev_sync/README.md).

| De un vistazo | |
|---------------|--|
| Plataforma | Solo Apple Silicon (arm64) · de macOS 13 Ventura a macOS 27 · Bash 3.2 + Python 3 |
| Flujo | 7 pasos (0–6); la actualización de macOS va siempre al final |
| Registro | 43 apps de Internet · 11 métodos de actualización (véase [Métodos de actualización](#métodos-de-actualización)) |
| Idiomas | EN, PL, ES, FR, DE, IT, PT (CLI y documentación) |
| Pruebas | 591 pruebas automáticas (`bash run_tests.sh`) |

**Novedades de la v1.5.5:** Una actualización de Homebrew que elimina `python3` durante la ejecución ya no rompe el paso de inventario/informe (el shell vuelve a buscar en `PATH`), y un paso de informe fallido ya no pospone las actualizaciones de macOS. Los mensajes finales son honestos: no se afirma «archivos actualizados» tras un fallo, y las advertencias de feeds antiguos o de apps que no se cerraron ya no se presentan como actualizaciones sin verificar. A las apps iniciadas por la herramienta se les pide cerrarse repetidamente (nunca se fuerza). Las versiones 1.5.x anteriores (feeds antiguos como advertencias, descargas del proveedor para ChatGPT/Proton, CLI nativas antes de npm, protección del reemplazo de paquetes) se describen en [CHANGELOG.md](CHANGELOG.md).

**Verdad del proveedor (desde v1.5.0):** la versión de cada aplicación se compara con el feed de su propio proveedor antes de ejecutar cualquier acción. Las aplicaciones actualizadas no se tocan; las desactualizadas se actualizan mediante el actualizador del propio proveedor o se instalan desde el proveedor con verificación de firma y Team ID. Solo se actualiza el software que ya está instalado (`--bootstrap-cli` instala deliberadamente las CLI que faltan). Las aplicaciones eliminadas manualmente se detectan y nunca se reinstalan. **Las aplicaciones que tienes abiertas nunca se cierran: el kit de herramientas solo cierra lo que inició por sí mismo.** Comprueba el estado de los proveedores en modo de solo lectura con `bash scripts/check_vendor_feeds.sh`.

---

## Instalación en una sola línea (usuarios nuevos)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

El instalador clona el repositorio, solicita el **idioma** (menú en inglés, 7 idiomas), instala las dependencias, genera **tu** archivo `APPLICATIONS.md` a partir de las apps ya instaladas en este Mac y muestra qué apps puede actualizar el proyecto. Nunca importa el inventario de otra persona ni instala apps por ti.

Consulta [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md)

---

## Qué hace esta herramienta

`update_all.sh` ejecuta siete pasos:

| Paso | Acción |
|------|--------|
| 0 | **Escaneo previo** — detecta las apps instaladas → actualiza `APPLICATIONS.md` |
| 1 | **App Store** — Pista 1: `sudo mas upgrade <app-id>`; Pista 2: GUI con AppleScript para apps de iPad |
| 2 | **CLI nativa + npm** — primero las CLI nativas existentes, luego Node, Bun y las CLI globales de npm |
| 3 | **Homebrew** — fórmulas y casks (`brew_cask` + protección contra downgrades) + limpieza y comprobación de salud |
| 4 | **Apps de Internet** — controladores directos verificados, `sparkle_appcast`, CLI de proveedores y activadores honestos de actualizadores |
| 5 | **Post-actualización/historial** — actualiza `APPLICATIONS.md` y añade a `UPDATES.md` de forma atómica |
| 6 | **macOS (final)** — por etiqueta `softwareupdate -i <label> -R` (etiquetas que requieren reinicio en el lote final); se aplaza tras un fallo grave bloqueante en los pasos 1–4 o si no hay autorización |

**Importante:** Las actualizaciones solo afectan al software ya instalado en tu Mac. Las apps compatibles que faltan se informan, no se instalan. El paso final de macOS puede reiniciar el Mac, por eso va el último y conserva el obligatorio `-R`. El paso 5 solo genera informes: un fallo ahí es un error, pero nunca aplaza el paso de macOS. Las apps instaladas desconocidas se listan para que tú (o un agente de IA) añadáis controladores.

La cobertura es deliberadamente explícita: **verified direct** significa que el actualizador confirmó la ruta de paquete/versión; **triggered-unverified**, que se abrió la app para que su actualizador se ejecutara pero no se puede probar que terminó; **externally managed**, que el proveedor o el App Store gestionan el ciclo de actualización; **manual** requiere acción del usuario; **unknown** no tiene método registrado.

```bash
bash scripts/report_update_coverage.sh   # informe de cobertura
bash build_inventory.sh                  # reconstruye APPLICATIONS.md desde este Mac
```

### Métodos de actualización

El registro ([`config/internet_apps.txt`](config/internet_apps.txt), [`config/internet_app_methods.txt`](config/internet_app_methods.txt)) asigna 43 apps a 11 métodos:

| Método | Apps | Cobertura | Cómo actualiza |
|--------|-----:|-----------|----------------|
| `brew_cask` | 11 | externally managed | Cask de Homebrew (greedy solo para estos tokens) con protección contra downgrades, p. ej. Brave, Obsidian, Spotify, Inkscape |
| `silent_launch` | 9 | triggered-unverified | El actualizador propio de la app; comprobación oportunista contra un feed Sparkle / electron-updater, si no se informa «iniciado (sin verificar)». Nunca reemplaza la app |
| `github_dmg` | 6 | verified direct | DMG del proveedor/GitHub con verificación de firma y Team ID, reemplazo por etapas con rollback (Firefox Developer Edition, KeePassXC, VS Code, CodeEdit, Ledger Live, Trezor Suite) |
| `msupdate` | 5 | verified direct | Microsoft AutoUpdate (`msupdate`): Word, Excel, PowerPoint, Outlook, OneNote |
| `keystone` | 3 | verified direct | Actualizador de Google (Omaha) comprobado con su historial: Chrome, Gemini, Google Drive |
| `appstore_gui` | 3 | externally managed | App Store Pista 2 (AppleScript): UniFi, WiFiman, Picsart |
| `sparkle_appcast` | 1 | verified direct | Appcast de Sparkle (Proton Drive) |
| `chromium_updater` | 1 | verified direct | Prueba del actualizador basado en Chromium (Comet) |
| `docker_cli` | 1 | verified direct | Docker Desktop: DMG verificado de su appcast cuando está inactivo; alternativa `docker desktop update` |
| `mau_fallback_self_update` | 1 | triggered-unverified | Actualizador propio de Teams más un fallback MAU `TEAMS21` observado y verificado cuando Microsoft lo ofrece |
| `manual` | 2 | manual | IPMIView y DJI Assistant 2: solo notificación |

---

## Opciones de línea de comandos

`lib/cli.sh` es la lista autoritativa; `bash update_all.sh --help` la muestra.

| Opción | Efecto |
|--------|--------|
| `-y`, `--yes` | Omite la confirmación |
| `-h`, `--help` | Muestra la ayuda y sale con `0` |
| `--dry-run` | Previsualiza cada paso, no modifica nada y nunca pide credenciales |
| `--verify-only` | Verifica las versiones instaladas contra el historial sin modificar nada |
| `--json-summary` | Imprime un objeto JSON con el resultado en stdout al terminar |
| `--bootstrap-cli` | Instala explícitamente las CLI que faltan (por defecto solo se actualizan las instaladas) |
| `--non-interactive` | Modo no interactivo para launchd / cron (implica también `-y`) |
| `--notify` | Envía una notificación de macOS al terminar |
| `--treat-appstore-ax-as-warning` | Trata la salida `2` del App Store (falta de Accesibilidad) como advertencia |
| `--skip-prescan` | Omite el paso 0 (escaneo previo de `APPLICATIONS.md`) |
| `--skip-appstore` | Omite el paso 1 (App Store) |
| `--skip-npm` | Omite el paso 2 (CLI nativa + npm) |
| `--skip-brew` | Omite el paso 3 (Homebrew) |
| `--skip-internet` | Omite el paso 4 (apps de Internet) |
| `--skip-postupdate` | Omite el paso 5 (historial `APPLICATIONS.md` / `UPDATES.md`) |
| `--skip-system` | Omite el paso 6 (actualización de macOS) |
| `--skip-doctor` | Omite `brew doctor` dentro de `update_brew.sh` |

Una opción `-…` desconocida termina con código `2` tras mostrar la ayuda.

## Variables de entorno

Cada opción tiene una variable equivalente (`MAC_UPDATE_DRY_RUN=1`, `MAC_UPDATE_SKIP_SYSTEM=1`, …); a continuación las más usadas que no tienen opción propia. La lista completa con valores por defecto está en [docs/agents/scripts.md](docs/agents/scripts.md#environment-variables).

| Variable | Valor por defecto | Significado |
|----------|-------------------|-------------|
| `MAC_UPDATE_NONINTERACTIVE` | `0` | Nunca pregunta; omite la automatización GUI de la Pista 2 del App Store |
| `MAC_UPDATE_NOTIFY` | `0` | Notificación de escritorio al terminar (también implícita en modo no interactivo) |
| `MAC_UPDATE_NO_SUDO` | *se define automáticamente* | Lo exporta `update_all.sh` si no hay TTY; los scripts hijos omiten las pistas con root en lugar de fallar |
| `MAC_UPDATE_NO_SUDO_KEEPALIVE` | `0` | `1` desactiva el refresco en segundo plano de la marca de tiempo de `sudo` |
| `MAC_UPDATE_STALE_DAYS` | `45` | Días tras los cuales una app sin verificar se marca como obsoleta |
| `MAC_UPDATE_MAX_LOGS` | `30` | Registros de ejecución conservados en `logs/` |
| `MAC_UPDATE_INTERNET_SETTLE_SECONDS` | `15` | Pausa para que un actualizador de proveedor iniciado reescriba `Info.plist` (`0` la desactiva, máximo 120; se omite si no se inició ninguna app) |
| `MAC_UPDATE_QUIT_WAIT` | `60` | Segundos (0–300) que tiene una app iniciada por la herramienta para cerrarse tras el `quit` suave; nunca se fuerza (v1.5.5) |
| `MAC_UPDATE_QUIT_RESEND` | `10` | Segundos (1–60) entre peticiones `quit` suaves repetidas dentro de la ventana de espera (v1.5.5) |
| `MAC_UPDATE_MAS_CHECK_TIMEOUT` | `120` | Tiempo límite de `mas outdated` |
| `MAC_UPDATE_MAS_UPGRADE_TIMEOUT` | `1800` | Tiempo límite de `sudo mas upgrade` |
| `MAC_UPDATE_MAU_DEFERRAL_DAYS` | `7` | Ventana de cuarentena de Microsoft AutoUpdate (limitada al rango 1–28 de Microsoft) |
| `MAC_UPDATE_MAU_CLEAR_DEFERRALS` | `0` | `1` elimina con `defaults delete` las claves de aplazamiento de MAU que bloquean |
| `MAC_UPDATE_MAU_KEEP_DEFERRALS` | `0` | `1` hace que la herramienta nunca toque las preferencias de aplazamiento de MAU |
| `MAC_UPDATE_LANG` / `MAC_LANG` | de `.mac_update_prefs` | Idioma de la interfaz (`en pl es it pt de fr`) |

## sudo y Touch ID — el contrato

Reescrito en v1.3.1 / v1.4.0. `update_all.sh` tiene **exactamente un** punto de llamada
interactivo a `sudo`, sujeto a tres condiciones:

1. **A lo sumo una vez por ejecución.** Un único `sudo -v` antes de redirigir el
   registro; después un proceso en segundo plano refresca la marca de tiempo cada
   50 s, de modo que una ejecución larga nunca vuelve a preguntar. El keep-alive se
   inicia como máximo una vez y la trampa de limpieza lo termina en cualquier
   salida, incluidas `INT`/`TERM`: ya no puede quedar huérfano.
2. **Nunca sin un TTY de control.** Si stdin no es un terminal (ejecutor de tareas
   del IDE, shell de un agente, launchd, cron) la herramienta **no** llama a
   `sudo -v`. Un `sudo -v` sin TTY escala al diálogo gráfico askpass/Touch ID, y
   por eso cada comando parecía exigir elevación. En su lugar se exporta
   `MAC_UPDATE_NO_SUDO=1`, se omiten los pasos que requieren root y la ejecución
   informa una advertencia suave.
3. **Nunca con `--dry-run`.** Una previsualización no debe pedir credenciales.

Tampoco se solicita `sudo` cuando no se va a ejecutar ni el paso 1 (App Store) ni el
paso 6 (macOS), p. ej. `bash update_all.sh --skip-appstore --skip-system`.

---

## Configuración por equipo (**no** llega con `git pull`)

Dos elementos viven fuera del repositorio y, por tanto, deben configurarse una vez
**en cada Mac**. Clonar o hacer pull en un segundo equipo no los traslada: es la
confusión más frecuente en este proyecto.

| Paso | Comando | Por qué no puede estar en Git |
|------|---------|-------------------------------|
| Touch ID para `sudo` | `bash scripts/setup_touchid_sudo.sh` | Escribe `/etc/pam.d/sudo_local`: archivo propiedad de root, local al equipo y fuera del repositorio |
| Ejecución semanal en segundo plano | `bash scripts/install_launchagent.sh --day 1 --hour 9` | Escribe `~/Library/LaunchAgents/com.<user>.macos-updates.plist`: por usuario y por equipo |

```bash
bash scripts/setup_touchid_sudo.sh --check      # solo informa, no escribe nada
bash scripts/setup_touchid_sudo.sh              # instalar / reparar
bash scripts/setup_touchid_sudo.sh --uninstall

bash scripts/install_launchagent.sh --check
bash scripts/install_launchagent.sh --uninstall
```

`setup_touchid_sudo.sh` nunca toca `/etc/sudoers` ni concede `sudo` sin contraseña.
En macOS 14+ usa `/etc/pam.d/sudo_local`, que sobrevive a las actualizaciones del
sistema; en macOS 13 modifica `/etc/pam.d/sudo`, que las actualizaciones de macOS
borran: vuelve a ejecutarlo tras una actualización mayor.

### Qué hace y qué no hace la ejecución programada en segundo plano

El LaunchAgent ejecuta `update_all.sh -y --skip-system` con
`MAC_UPDATE_NONINTERACTIVE=1` y `MAC_UPDATE_NOTIFY=1`.

- **Ejecuta:** Homebrew, CLI nativa + npm, apps de Internet, inventario/historial.
- **No ejecuta las actualizaciones de macOS**: `--skip-system` es deliberado. En
  Apple Silicon `softwareupdate` necesita **credenciales de propietario del
  volumen**, imposibles de aportar desde un trabajo desatendido de launchd, y el
  paso puede reiniciar el Mac.
- **No ejecuta las actualizaciones del App Store**: `sudo mas upgrade` requiere
  contraseña y la Pista 2 con AppleScript maneja la interfaz del App Store. Ambas
  se omiten en una sesión sin TTY y se informan como advertencia suave (código
  `10`), nunca como fallo.

Por tanto ambas siguen siendo interactivas, a propósito. Ejecuta `bash update_all.sh`
tú mismo cuando quieras aplicar las actualizaciones del App Store y de macOS.

---

## Requisitos

| Herramienta | ¿Se instala automáticamente? |
|-------------|------------------------------|
| Mac con Apple Silicon (arm64) | — |
| macOS 13 Ventura o posterior (probado hasta macOS 27) | — |
| Xcode Command Line Tools | ✅ `setup.sh` / `install.sh` |
| Homebrew | ✅ |
| `mas` (CLI del App Store) | ✅ |
| Python 3 | ✅ vía Homebrew si falta |
| `rclone` (opcional) | ✅ si se elige como proveedor de nube |

Los Mac Intel y macOS 12 o anterior no son compatibles; los scripts terminan antes de hacer cualquier cambio.

---

## Inicio rápido

### Usuario nuevo (sin nube)

```bash
# Opción A — una línea (recomendada)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"

# Opción B — manual
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh
bash build_inventory.sh
bash update_all.sh
```

### Propietario (GitHub + capa privada en la nube)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

---

## Estructura del proyecto

```
macOS_updates/
├── VERSION                     # Versión del paquete (única fuente de verdad)
├── install.sh                  # Instalador de una línea
├── uninstall.sh                # Elimina el clon (conserva Homebrew y las apps)
├── setup.sh                    # Configuración inicial (sin nube)
├── migration_setup.sh          # Configuración completa + asistente de nube
├── build_inventory.sh          # Genera APPLICATIONS.md para este Mac
├── update_all.sh               # Orquestador principal
├── update_*.sh                 # Pasos de actualización individuales
├── run_tests.sh                # Sintaxis + Python + unittest + análisis de secretos
│
├── dev_sync/                   # Sincronización de la capa privada (nube)
│   ├── provider_setup.sh
│   ├── dev-sync-export.sh      # (+ import, verify, prune, …)
│   └── dev_sync_*.py           # Backend en Python
├── dev-sync-*.sh               # Envoltorios en la raíz (compatibilidad)
│
├── config/                     # Registro de apps de Internet (público)
│   ├── internet_apps.txt
│   ├── internet_app_methods.txt
│   └── internet_dispatch_order.txt
│
├── lib/                        # Bibliotecas Bash compartidas (+ lib/python/)
├── i18n/                       # Textos de la interfaz en 7 idiomas
├── scripts/                    # Utilidades (informe de cobertura, feeds de proveedores, generador, …)
├── templates/                  # APPLICATIONS.md.template (referencia)
├── tests/                      # unittest + comprobaciones estáticas de seguridad
├── docs/
│   ├── INSTALL.md · UNINSTALL.md · PUBLIC_RELEASE.md
│   ├── user/                   # Guías para usuarios finales (7 idiomas)
│   ├── agents/                 # Referencia para desarrolladores / agentes de IA
│   ├── reviews/                # Índice + registros de desarrollo vigentes (archive/ = historial)
│   └── archive/                # Planes de implementación superados
│
├── CHANGELOG.md · CONTRIBUTING.md · SECURITY.md · LICENSE
└── AGENTS.md · CLAUDE.md · GEMINI.md · CODEX.md
```

**Archivos privados (ignorados por git, solo locales o en la nube):** `APPLICATIONS.md`, `UPDATES.md`, `.dev_sync_config.json`, `.mac_update_prefs`, `.env`, `logs/`

### Scripts individuales

| Script | Finalidad |
|--------|-----------|
| `install.sh` | Clona + configura + crea el inventario para usuarios nuevos |
| `setup.sh` | Dependencias y permisos (sin nube) |
| `migration_setup.sh` | Migración completa + nube + escaneo de apps |
| `build_inventory.sh` | Escaneo de solo lectura → actualiza `APPLICATIONS.md` de forma atómica sin historial de actualizaciones |
| `update_all.sh` | Todos los pasos de actualización + registro |
| `update_system.sh` … `update_brew.sh` | Actualizaciones de una sola capa |
| `uninstall.sh` | Elimina el directorio de la herramienta |
| `run_tests.sh` | Sintaxis + Python + unittest + análisis de secretos |

Referencia completa de scripts: [docs/agents/scripts.md](docs/agents/scripts.md).

---

## Cómo añadir una app nueva

1. Instala la app tú mismo (el actualizador nunca la instala por ti).
2. Ejecuta `bash build_inventory.sh` para añadirla a `APPLICATIONS.md`.
3. Para la actualización automática, pide ayuda a un agente de IA o sigue [docs/user/es/GUIDE.md](docs/user/es/GUIDE.md):

```bash
bash scripts/scaffold_internet_app.sh "Nombre de la app" silent_launch
bash run_tests.sh
```

Los métodos del registro se asignan a los estados de cobertura anteriores. Por ejemplo, `github_dmg` y una CLI confirmada del proveedor son **verified direct**; `silent_launch` es **triggered-unverified**; los flujos gestionados por el App Store o el proveedor pueden ser **externally managed**; `manual` y las entradas ausentes del registro quedan explícitos.

---

## Sincronización en la nube (`dev_sync`)

| GitHub (público) | Nube (privado) |
|------------------|----------------|
| Scripts, `config/`, `docs/`, pruebas | `APPLICATIONS.md`, `UPDATES.md`, `.env`, `.dev_sync_config.json` |

```bash
bash dev_sync/provider_setup.sh
bash dev_sync/dev-sync-export.sh
bash dev_sync/dev-sync-import.sh
bash dev_sync/dev-sync-verify-full.sh
```

Los envoltorios `dev-sync-*.sh` de la raíz llaman a los mismos scripts de `dev_sync/`.

---

## Pruebas

La batería cubre la sintaxis de bash, la compilación de Python, los contratos estáticos de seguridad, las guardas de documentación y las pruebas unitarias (591 pruebas automáticas).
Los pull requests ejecutan ShellCheck en Ubuntu, pruebas portables de Python y el análisis de secretos.
La suite completa de `run_tests.sh` en un runner macOS solo se ejecuta con `workflow_dispatch` o una etiqueta `v*`, no en cada push.

```bash
bash run_tests.sh
bash update_all.sh --dry-run -y
```

---

## Notas técnicas críticas

- **`softwareupdate` debe usar `-R`**: de lo contrario las actualizaciones se descargan pero nunca se aplican.
- **`mas upgrade` debe usar `sudo` e identificadores de app explícitos** en macOS 14.8.2+/15.7.2+/26.1+ (cambio de permisos, véase https://github.com/orgs/Homebrew/discussions/6550).
- **Bash 3.2+** en todo el proyecto: sin `declare -A`, `mapfile` ni `readarray`.
- Las apps descargadas se verifican, se instalan mediante un reemplazo por etapas con rollback y se montan desde DMG en puntos de montaje únicos por sesión.
- La escritura del inventario/historial privados y las importaciones desde la nube son atómicas; las importaciones preparan los archivos aceptados antes de confirmarlos.

---

## Documentación

| Audiencia | Empieza aquí |
|-----------|--------------|
| Usuarios | [docs/user/INDEX.md](docs/user/INDEX.md) (inicio rápido, guía y manual de operaciones en 7 idiomas) · [inicio rápido en español](docs/user/es/QUICK_START.md) |
| Instalación / desinstalación | [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md) |
| GitHub público frente a capa privada | [docs/PUBLIC_RELEASE.md](docs/PUBLIC_RELEASE.md) · [dev_sync/README.md](dev_sync/README.md) |
| Desarrolladores / agentes | [docs/agents/scripts.md](docs/agents/scripts.md) · [reglas críticas](docs/agents/critical_rules.md) · [códigos de salida](docs/agents/exit_codes.md) · [solución de problemas](docs/agents/troubleshooting.md) · [lista de aceptación](docs/agents/acceptance_checklist.md) |
| Contexto para agentes de IA | [AGENTS.md](AGENTS.md) (contrato compartido) · [CLAUDE.md](CLAUDE.md) · [GEMINI.md](GEMINI.md) · [CODEX.md](CODEX.md) |
| Historial de versiones | [CHANGELOG.md](CHANGELOG.md) · [índice de registros de desarrollo](docs/reviews/README.md) |
| Contribuir / seguridad | [CONTRIBUTING.md](CONTRIBUTING.md) · [SECURITY.md](SECURITY.md) |

---

## Solución de problemas

| Problema | Solución |
|----------|----------|
| Mac nuevo | `install.sh` o `setup.sh` + `build_inventory.sh` |
| Lista de apps incorrecta | `build_inventory.sh`: nunca copies el `APPLICATIONS.md` de otra persona |
| Una app no se actualiza sola | `scripts/report_update_coverage.sh` → añade un controlador según la guía |
| Falta `APPLICATIONS.md` | `build_inventory.sh` o `dev_sync/dev-sync-import.sh` (propietario) |
| `mas upgrade` falla | `sudo mas upgrade <app-id>` |
| Nube sin configurar | `bash dev_sync/provider_setup.sh` |

Lista completa: [docs/agents/troubleshooting.md](docs/agents/troubleshooting.md)

---

## Licencia

[MIT](LICENSE) © macOS Updates contributors
