# Guide utilisateur (Français)

**Version :** 1.0.18 · **Apple Silicon uniquement**

## Fonctionnement

macOS Updates automatise les mises à jour sur **Mac Apple Silicon** :

1. Système macOS (`softwareupdate -ia -R`)
2. App Store (`sudo mas upgrade` + GUI pour apps iPad)
3. Node/Bun et CLI npm globaux
4. Homebrew
5. 40+ apps Internet — **uniquement si installées**
6. Catalogue `APPLICATIONS.md` et historique `UPDATES.md`

**N'installe jamais de nouvelles applications.** Chaque Mac construit son inventaire (`build_inventory.sh`).

## Installation

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Rapport de couverture

```bash
bash scripts/report_update_coverage.sh
```

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
