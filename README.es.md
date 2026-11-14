# macOS Updates

## Instalación y uso

Instala desde el repositorio público, comprueba la preparación y previsualiza las actualizaciones.

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git
cd macOS_updates
bash setup.sh --inspect
bash build_inventory.sh --cli
bash update_all.sh --dry-run -y
bash update_all.sh
```

El espacio de trabajo permite revisar programas instalados, opciones y exclusiones. Una elección guardada solo cubre el alcance aprobado; los cambios requieren revisión. Algunas aplicaciones requieren acciones manuales.

Un proceso pendiente o sin confirmar puede bloquear actualizaciones posteriores. Revisa la recuperación en Diagnóstico; no borres bloqueos ni registros manualmente.

En Acerca de puedes revisar y aplicar explícitamente una actualización de la herramienta. Se comprueban los cambios locales.

```bash
bash uninstall.sh
```

Tras sustituir el historial público, conserva el directorio anterior y tus archivos locales. Para una instalación nueva, elige un directorio inexistente y sustituye `vX.Y.Z` por la etiqueta de versión verificada. Ejecuta el comando desde el directorio que contiene `install.sh`.

```bash
MAC_UPDATE_DIR="$HOME/Dev_Env/macOS_updates-new" MAC_UPDATE_REF="vX.Y.Z" bash install.sh
```
