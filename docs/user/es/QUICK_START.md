# Inicio rápido (Español)

**Se requiere Mac con Apple Silicon** · macOS 13+ · **v1.0.18**

## Instalación en una línea

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Usuario nuevo (solo GitHub)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh
bash build_inventory.sh
bash update_all.sh
```

`setup.sh` instala Homebrew, `mas` y Python si faltan, y selecciona su idioma.

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
