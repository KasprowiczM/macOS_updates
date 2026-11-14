# macOS Updates

## Installation et utilisation

Installez depuis le dépôt public, vérifiez la préparation puis prévisualisez les mises à jour.

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git
cd macOS_updates
bash setup.sh --inspect
bash build_inventory.sh --cli
bash update_all.sh --dry-run -y
bash update_all.sh
```

L’espace de travail permet de vérifier les logiciels installés, les choix et les exclusions. Un choix enregistré couvre uniquement le périmètre approuvé; tout changement demande une vérification. Certaines applications nécessitent une action manuelle.

Un processus en attente ou non confirmé peut bloquer les mises à jour suivantes. Consultez la récupération dans Diagnostics; ne supprimez pas les journaux ni les verrous.

Dans À propos, examinez et appliquez explicitement une mise à jour de l’outil. Les modifications locales sont vérifiées.

```bash
bash uninstall.sh
```

Après le remplacement de l’historique public, conservez l’ancien dossier et vos fichiers locaux. Pour une nouvelle installation, choisissez un dossier inexistant et remplacez `vX.Y.Z` par le tag de version vérifié. Exécutez la commande depuis le dossier contenant `install.sh`.

```bash
MAC_UPDATE_DIR="$HOME/Dev_Env/macOS_updates-new" MAC_UPDATE_REF="vX.Y.Z" bash install.sh
```
