# Guide utilisateur (Français)

**Version :** 1.6.1 · **Apple Silicon, macOS 13+**

## Configuration sûre et sources des applications

`bash setup.sh --inspect` vérifie la disponibilité sans installation, modification du profil shell ni configuration Touch ID. Un outil absent rend sa fonction indisponible. Dans un terminal, `bash setup.sh --install-dependencies` présente les dépendances facultatives et demande avant chaque installation ; `bash setup.sh --configure-shell` présente séparément la modification du profil. Refuser une dépendance ne bloque pas les fonctions indépendantes. Sans Python, installez-le explicitement avant de construire l’inventaire. Un `mas` absent ou ancien est signalé, jamais installé ni mis à niveau automatiquement.

Le rapport normal montre les applications installées. `bash scripts/report_update_coverage.sh --show-supported` affiche les recettes absentes. Ce catalogue informatif n’est pas encore un menu d’installation. Un reçu App Store pour CapCut conserve la voie App Store même sans cask. Sans propriété Homebrew confirmée, une source est proposée sans adoption ni installation. La résolution complète et le choix interactif des sources restent prévus pour les étapes suivantes.

## Fonctionnement

macOS Updates orchestre les mises à jour sur **Mac Apple Silicon sous macOS 13+** :

1. Pré-analyse et inventaire
2. App Store (`sudo mas upgrade <app-id>` + Track 2 GUI séparé)
3. CLI natives existantes d’abord, puis Node/Bun et solutions npm de secours
4. Homebrew (mise à jour greedy uniquement pour les casks enregistrés en `brew_cask`)
5. Apps installées : handlers directs, CLI ou déclencheurs intégrés
6. Post-mise à jour atomique de l'inventaire/historique
7. macOS (`softwareupdate -i <label> -R`) en dernier ; différé après une erreur bloquante ou sans autorisation

**N'installe jamais de nouvelles applications.** Chaque Mac construit son inventaire (`build_inventory.sh`).

## Installation

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Rapport de couverture

```bash
bash scripts/report_update_coverage.sh
```

États : **verified direct**, **triggered-unverified**, **externally managed**, **manual**, **unknown**. Un lancement silencieux ne prouve pas une mise à jour. Inkscape utilise Homebrew ; UniFi/WiFiman/Picsart Track 2 ; Office `msupdate` ; Teams son propre updater avec repli MAU `TEAMS21` observé et vérifié. Actuellement aucune app enregistrée n'est « manual » ; IPMIView passe par App Store Track 2.

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
