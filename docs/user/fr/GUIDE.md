# Guide utilisateur (Français)

**Version :** 1.0.21 · **Apple Silicon, macOS 13+**

## Fonctionnement

macOS Updates orchestre les mises à jour sur **Mac Apple Silicon sous macOS 13+** :

1. Pré-analyse et inventaire
2. App Store (`sudo mas upgrade` + Track 2 GUI séparé)
3. Node/Bun et CLI npm globaux
4. Homebrew (`--greedy`)
5. Apps installées : handlers directs, CLI ou déclencheurs intégrés
6. Post-mise à jour atomique de l'inventaire/historique
7. macOS (`softwareupdate -ia -R`) en dernier ; ignoré après un échec antérieur

**N'installe jamais de nouvelles applications.** Chaque Mac construit son inventaire (`build_inventory.sh`).

## Installation

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Rapport de couverture

```bash
bash scripts/report_update_coverage.sh
```

États : **verified direct**, **triggered-unverified**, **externally managed**, **manual**, **unknown**. Un lancement silencieux ne prouve pas une mise à jour. Inkscape utilise Homebrew ; UniFi/WiFiman/Picsart Track 2 ; Office `msupdate` ; Teams son propre updater avec repli MAU `TEAMS21` observé et vérifié. Seuls IPMIView et DJI Assistant 2 restent manuels.

## Ajouter une app Internet

1. Installer l'app sur le Mac.
2. `bash build_inventory.sh`
3. `bash scripts/scaffold_internet_app.sh "Nom" silent_launch`
4. `bash run_tests.sh`

## Dépannage

| Problème | Solution |
|----------|----------|
| Mac Intel | Non pris en charge |
| Mauvais catalogue | `bash build_inventory.sh` |
| App non mise à jour | `bash scripts/report_update_coverage.sh` |
| `APPLICATIONS.md` manquant | `build_inventory.sh` ou `dev_sync/dev-sync-import.sh` |

Complet : [../../agents/troubleshooting.md](../../agents/troubleshooting.md)
