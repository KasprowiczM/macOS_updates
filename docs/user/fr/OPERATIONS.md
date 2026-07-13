# Guide opérationnel

Guide pour l'opérateur — maintenance quotidienne et hebdomadaire du macOS Updates.

## Plateforme

**Apple Silicon (arm64), macOS 13+ uniquement.** Les scripts s'arrêtent avant toute modification sur un Mac non pris en charge.

## Mise à jour hebdomadaire

```bash
cd ~/Dev_Env/macOS_updates
bash update_all.sh
```

En cas d'échec, consulter : `logs/update_all_<timestamp>.log` (30 dernières exécutions conservées).

## Ordre du pipeline (`update_all.sh`)

| Étape | Script / action | Flag d'ignorer |
|-------|-----------------|----------------|
| 0 | prescan → `APPLICATIONS.md` | `--skip-prescan` |
| 1 | `update_appstore.sh` | `--skip-appstore` |
| 2 | `update_npm_cli.sh` | `--skip-npm` |
| 3 | `update_brew.sh` | `--skip-brew` |
| 4 | `update_internet_apps.sh` | `--skip-internet` |
| 5 | postupdate/historique → `APPLICATIONS.md`, `UPDATES.md` | `--skip-postupdate` |
| 6 | `update_system.sh` (`softwareupdate -ia -R`) | `--skip-system` |

L'étape 6 s'exécute en dernier à cause du redémarrage possible et est automatiquement ignorée après un échec antérieur.

Aperçu sans modifications : `bash update_all.sh --dry-run -y`

## Analyse des échecs

| Étape en échec | Fichiers à vérifier |
|----------------|---------------------|
| App Store | `$SESSION_DIR/appstore_diag.txt`, instantané du journal |
| Apps Internet | `$SESSION_DIR/internet_diag.txt`, `internet_before/after.txt` |
| Homebrew | `$SESSION_DIR/brew_*_before/after.txt` |
| Toute | `logs/update_all_*.log` (instantanés ajoutés en cas de code de sortie ≠ 0) |

Accessibilité App Store manquante → code de sortie `2` ; utiliser `--treat-appstore-ax-as-warning` ou accorder l'accessibilité au terminal.

Référence complète des codes de sortie : `docs/agents/exit_codes.md`.

## Overlay privé (Proton Drive)

Après modification locale des fichiers privés :

```bash
bash dev_sync/dev-sync-export.sh
bash dev_sync/dev-sync-verify-full.sh
bash dev_sync/dev-sync-prune-excluded.sh   # should report zero candidates
```

## Nouveau Mac

**Utilisateur public :**

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
bash update_all.sh
```

**Propriétaire (overlay cloud) :**

```bash
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

Inventaire : `bash build_inventory.sh`

## Liste de contrôle avant mise à jour

- [ ] Connecté à l'App Store (`mas account` ou app App Store)
- [ ] Terminal avec accessibilité (pour la piste 2 des apps iPad)
- [ ] Espace disque ≥ 20 Go pour les grosses mises à jour macOS
- [ ] `sudo` disponible pour `mas upgrade` et les mises à jour système

## Vérification après mise à jour

```bash
mas outdated
brew outdated
softwareupdate -l
```

Lancer un échantillon d'apps critiques (navigateur, VPN, IDE) si l'étape Internet a signalé des avertissements.
