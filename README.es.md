# macOS Updates

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

> **v1.0.18** — Actualizador de un solo comando listo para producción para **Macs con Apple Silicon**. Mantiene actualizados macOS, la App Store, Homebrew y más de 40 aplicaciones descargadas de internet — **solo el software que ya tienes instalado**. **Multilingüe** (7 idiomas). Capa privada opcional en la nube a través de [`dev_sync/`](dev_sync/README.md).

**Repositorio público:** [github.com/KasprowiczM/macOS_updates](https://github.com/KasprowiczM/macOS_updates) · Lanzamiento público: [docs/PUBLIC_RELEASE.md](docs/PUBLIC_RELEASE.md)

---

## Instalación de una línea (nuevos usuarios)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

El instalador clona el repositorio, solicita el **idioma** (español entre los 7 disponibles), instala las dependencias, construye **tu** archivo `APPLICATIONS.md` a partir de las aplicaciones ya presentes en tu Mac, e imprime qué aplicaciones pueden actualizarse. Nunca importa el inventario de otro usuario ni instala aplicaciones por ti.

Ver [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md)

---

## ¿Qué hace esto?

`update_all.sh` ejecuta siete pasos:

| Paso | Acción |
|------|--------|
| 0 | **Escaneo previo** — descubre aplicaciones instaladas → actualiza `APPLICATIONS.md` |
| 1 | **Sistema** — `softwareupdate -ia -R` |
| 2 | **App Store** — `sudo mas upgrade` + opción de contingencia con AppleScript |
| 3 | **CLI Nativos + npm** — Node, Bun, herramientas globales de npm |
| 4 | **Homebrew** — `brew upgrade` + limpieza |
| 5 | **Aplicaciones de internet** — solo si están instaladas (Chrome, VS Code, Microsoft 365, …) |
| 6 | **Post-actualización** — incrementa versiones en `APPLICATIONS.md`, añade a `UPDATES.md` |

**Importante:** Las actualizaciones solo modifican el software que ya está instalado en tu Mac. Las aplicaciones soportadas pero ausentes se reportan, no se instalan.

```bash
bash scripts/report_update_coverage.sh   # reporte de cobertura
bash build_inventory.sh                  # reconstruir APPLICATIONS.md
```

---

## Requisitos

| Herramienta | ¿Instalación automática? |
|------|----------------|
| Mac con Apple Silicon (arm64) | — |
| macOS 13 Ventura o superior | — |
| Herramientas de línea de comandos de Xcode | ✅ `setup.sh` / `install.sh` |
| Homebrew | ✅ |
| `mas` (CLI para la App Store) | ✅ |
| Python 3 | ✅ (a través de Homebrew si falta) |
| `rclone` (opcional) | ✅ si se elige como proveedor de nube |

---

## Inicio Rápido

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

### Propietario (GitHub + capa en la nube)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

---

## Documentación

| Audiencia | Comienza aquí |
|----------|------------|
| Usuarios | [docs/user/es/QUICK_START.md](docs/user/es/QUICK_START.md) |
| Instalar / Desinstalar | [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md) |
| Desarrolladores | [docs/agents/scripts.md](docs/agents/scripts.md) |
| Sincronización dev sync | [dev_sync/README.md](dev_sync/README.md) |
| Contexto AI | `AGENTS.md` |

---

## Notas Técnicas Críticas

- **`softwareupdate` debe usar `-R`** — de lo contrario, las actualizaciones se descargan pero nunca se aplican.
- **`mas upgrade` debe usar `sudo`** en macOS 26.x (CVE-2025-43411).
- **Bash 3.2+** en su totalidad — nada de `declare -A`, `mapfile`, `readarray`.
