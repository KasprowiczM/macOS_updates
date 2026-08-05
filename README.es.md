# macOS Updates

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

> **v1.3.0** — Orquestador de actualizaciones en un solo comando listo para producción en **Macs con Apple Silicon en macOS 13–26**. Coordina actualizaciones verificadas para aplicaciones instaladas en este Mac. **Multilingüe** (7 idiomas). Capa privada opcional en la nube vía [`dev_sync/`](dev_sync/README.md).

**Repositorio público:** [github.com/KasprowiczM/macOS_updates](https://github.com/KasprowiczM/macOS_updates) · Release: [docs/PUBLIC_RELEASE.md](docs/PUBLIC_RELEASE.md)

---

## Instalación en una sola línea (nuevos usuarios)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

El instalador clona el repositorio, solicita la **selección de idioma** (español disponible), instala dependencias, genera su archivo `APPLICATIONS.md` basado en las aplicaciones instaladas en su Mac y muestra qué aplicaciones pueden actualizarse.

Consulte [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md)

---

## Qué hace esta herramienta

`update_all.sh` ejecuta siete pasos:

| Paso | Acción |
|------|--------|
| 0 | **Escaneo previo** — detecta aplicaciones instaladas → actualiza `APPLICATIONS.md` |
| 1 | **App Store** — Pista 1: `sudo mas upgrade`; Pista 2: GUI AppleScript para apps de iPad |
| 2 | **CLI nativa + npm** — Node, Bun, herramientas globales npm |
| 3 | **Homebrew** — Fórmulas y Casks (`--greedy-auto-updates`) + protección contra downgrades |
| 4 | **Aplicaciones de Internet** — controladores verificados, `vendor_latest`, Sparkle Appcast |
| 5 | **Post-actualización/Historial** — actualiza inventario e historial de forma atómica |
| 6 | **macOS (final)** — `softwareupdate -ia -R`; se omite si ocurre un error previo |

---

## Características y variables de entorno en v1.3.0

- **Preautorización Sudo / Touch ID**: Detecta `pam_tid.so` y mantiene viva la sesión de sudo.
- **Soporte para LaunchAgent y tareas en segundo plano**: Admite `MAC_UPDATE_NO_SUDO=1` para ejecuciones desatendidas.
- **Método `vendor_latest`**: Evita degradaciones de Homebrew Cask para apps de actualización rápida (Cursor, Warp, Antigravity, Proton Mail, Proton Drive, Claude, Comet, ChatGPT).
- **Variables de control**:
  - `MAC_UPDATE_YES=1` (`-y`) — Confirmación no interactiva de todos los pasos.
  - `MAC_UPDATE_SKIP_SYSTEM=1` (`--skip-system`) — Omite las actualizaciones del sistema macOS.
  - `MAC_UPDATE_NONINTERACTIVE=1` — Suprime diálogos interactivos.

```bash
# Ejemplo de ejecución automatizada en segundo plano:
MAC_UPDATE_NONINTERACTIVE=1 bash update_all.sh -y --skip-system
```

---

## Inicio rápido

### Nuevo usuario (sin nube)

```bash
# Opción A — una línea (recomendado)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"

# Opción B — manual
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh
bash build_inventory.sh
bash update_all.sh
```

---

## Documentación

| Audiencia | Comenzar aquí |
|-----------|---------------|
| Usuarios | [docs/user/es/QUICK_START.md](docs/user/es/QUICK_START.md) |
| Instalación / Desinstalación | [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md) |
| Desarrolladores | [docs/agents/scripts.md](docs/agents/scripts.md) |
| Sincronización en la nube | [dev_sync/README.md](dev_sync/README.md) |
| Contexto IA | `AGENTS.md` |

---

## Notas técnicas críticas

- **`softwareupdate` DEBE usar `-R`** — de lo contrario las actualizaciones se descargan pero nunca se aplican.
- **`mas upgrade` DEBE usar `sudo`** en macOS 14.8+/15.7+/26.x (CVE-2025-43411).
- **Bash 3.2+** en todo el proyecto — sin `declare -A`, `mapfile` o `readarray`.
