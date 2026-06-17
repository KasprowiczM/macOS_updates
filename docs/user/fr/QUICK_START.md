# Démarrage rapide (Français)

**Mac Apple Silicon requis** · macOS 13+ · **v1.0.19**

## Installation en une ligne

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Nouvel utilisateur (GitHub uniquement)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh
bash build_inventory.sh
bash update_all.sh
```

`setup.sh` installe Homebrew, `mas` et Python si nécessaire, et choisit votre langue.

## Propriétaire (GitHub + overlay Proton Drive)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

Les fichiers privés (`APPLICATIONS.md`, `UPDATES.md`, `.env`) proviennent de votre overlay cloud — pas de GitHub.

## Commandes utiles

| Commande | Objectif |
|----------|----------|
| `bash update_all.sh --dry-run -y` | Aperçu de toutes les étapes |
| `bash update_system.sh` | macOS uniquement |
| `bash update_appstore.sh` | App Store uniquement |
| `bash update_brew.sh` | Homebrew uniquement |
| `bash run_tests.sh` | Vérifier l'installation |

Voir [GUIDE.md](GUIDE.md) et [OPERATIONS.md](OPERATIONS.md).
