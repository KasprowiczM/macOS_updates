# Guide utilisateur (Français)

**Version :** 1.8.2 · **Apple Silicon, macOS 13+**

## Interface terminal

Dans un terminal interactif, `bash update_all.sh` ouvre le tableau de bord et affiche l’assistant jusqu’à sa fin. `bash setup.sh` ouvre l’assistant et `bash build_inventory.sh` la vue inventaire. L’assistant reste accessible depuis la navigation. Sa fin et les réglages d’affichage sont enregistrés sans autoriser de mise à jour. `--cli` choisit l’interface texte existante et `--tui` demande explicitement le tableau de bord. Les options comme `--dry-run` restent en CLI ; ne combinez pas `--tui` avec d’autres options. `--tui` exige un terminal utilisable et Python. Les appels non interactifs ou sans TTY restent en CLI.

Choisissez les groupes avant un lancement. La navigation est à gauche, les actions et la sortie au centre, l’aide et les détails à droite sur chaque écran. Une seule tâche est supervisée à la fois ; les confirmations existantes restent nécessaires. Les réglages couvrent langue, thème, ASCII et taille automatique. `?` ouvre l’aide, Ctrl+P la palette et `c` copie la commande, la sortie ou le résumé sélectionné. Ctrl+V colle uniquement dans la fenêtre de réponse ; Entrée envoie. La saisie est masquée si le processus désactive l’écho.

Il faut au moins 80 colonnes et 24 lignes. Par défaut, le programme demande au moins 140 colonnes et 38 lignes aux terminaux compatibles, puis demande la taille initiale à la sortie. Le terminal peut ignorer ces demandes. La taille automatique est désactivable.

## Configuration sûre et sources des applications

`bash setup.sh --inspect` vérifie la disponibilité sans installation, modification du profil shell ni configuration Touch ID. Un outil absent rend sa fonction indisponible. Dans un terminal, `bash setup.sh --install-dependencies` présente les dépendances facultatives et demande avant chaque installation ; `bash setup.sh --configure-shell` présente séparément la modification du profil. Refuser une dépendance ne bloque pas les fonctions indépendantes. Sans Python, installez-le explicitement avant de construire l’inventaire. Un `mas` absent ou ancien est signalé, jamais installé ni mis à niveau automatiquement.

Le catalogue facultatif ne présélectionne rien. KeePassXC peut être installé par Homebrew après une autorisation distincte et une nouvelle vérification de la source et de son absence. L’aperçu présente la commande et ses effets ; la vérification utilise le reçu Homebrew. Les autres entrées conservent leurs voies officielles. Les applications existantes ne migrent jamais automatiquement.

Si le résultat d’une installation du catalogue est incertain, rouvrez le catalogue pour une nouvelle vérification de récupération. Ne supprimez pas les verrous ni les journaux manuellement. L’installation de KeePassXC par Homebrew exige des données stables vérifiées valables sept jours ; ensuite la voie manuelle reste disponible.

## Fonctionnement

macOS Updates orchestre les mises à jour sur **Mac Apple Silicon sous macOS 13+** :

1. Pré-analyse et inventaire
2. App Store (`sudo mas upgrade <app-id>` + Track 2 GUI séparé)
3. CLI natives existantes d’abord, puis Node/Bun et solutions npm de secours
4. Homebrew (mise à jour greedy uniquement pour les casks enregistrés en `brew_cask`)
5. Apps installées : opérations ciblées après consentement ; mises à jour éditeur non acceptées manuelles
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


## Ajouter une app Internet

1. Installer l'app sur le Mac.
2. `bash build_inventory.sh --cli`
3. `bash scripts/scaffold_internet_app.sh "/path/to/Observed.app" --json`
4. Examinez la proposition JSON non exécutable ; toute implémentation ultérieure exige une revue et `bash run_tests.sh`.

Remplacez l’exemple par le chemin exact de l’application installée. La commande affiche une proposition expurgée et non exécutable à examiner. L’export facultatif exige de répéter la commande avec `--export --accept PREVIEW_ID` après examen de l’identifiant affiché. L’activation des mises à jour exige une implémentation revue et des preuves d’acceptation distinctes.

## Dépannage

| Problème | Solution |
|----------|----------|
| Mac Intel | Non pris en charge |
| Mauvais catalogue | `bash build_inventory.sh --cli` |
| App non mise à jour | `bash scripts/report_update_coverage.sh` |
| `APPLICATIONS.md` manquant | `build_inventory.sh` ou `dev_sync/dev-sync-import.sh` |

Complet : [../../agents/troubleshooting.md](../../agents/troubleshooting.md)

L’inventaire JSON local et les plans d’action ciblés sont disponibles. `bash update_all.sh --plan` et `--dry-run` affichent les mêmes décisions sans écriture. Un lancement interactif demande une fois les portées affichées ; `-y`, EOF et les lancements sans terminal ne donnent aucune nouvelle autorisation. Utilisez `--preferences` pour revoir ou réinitialiser les choix. Les mises à jour conservent la source et la destination observées ; conflits, cibles absentes et preuves incertaines reportent cette cible. `build_inventory.sh --migration --preview` conserve les octets Markdown originaux et les notes ; acceptez explicitement l’identifiant affiché. Les mises à jour génériques restent manuelles jusqu’à la vérification de l’identité et de l’adaptateur. Une entrée de catalogue ne prouve ni installation ni consentement.


## Catalogue facultatif et première installation

Les nouveaux signaux d’applications sont des propositions à examiner, pas des recettes exécutables. `bash scripts/scan_update_feeds.sh` affiche un résumé agrégé. L’export permet l’aperçu et l’acceptation explicite ; il est expurgé, reste local et n’est jamais téléversé. `bash setup.sh --catalog` ouvre le catalogue sans sélection. `-y`, les exécutions non interactives et EOF n’installent rien. Dans le menu, `check <number>` compare uniquement les sources choisies. Les résultats indiquent la dernière version stable compatible confirmée et sa date ; le cache dure 24 heures. Une valeur inconnue le reste. Une fiche publique du Mac App Store ne prouve pas que l’app est proposée à votre compte.

Le catalogue facultatif ne sélectionne rien au départ. KeePassXC peut être installé via Homebrew après accord séparé et vérification récente de la source et de son absence. L’aperçu montre la commande et les effets déclarés ; la preuve est le reçu Homebrew, pas l’acceptation d’une recette fournisseur. Les autres entrées gardent leurs voies officielles vérifiées. Aucune migration automatique des applications existantes. Les recommandations reposent sur les données disponibles des versions stables.

## État local des mises à jour par recette

Le catalogue facultatif ne sélectionne rien au départ. KeePassXC peut être installé via Homebrew après accord séparé et vérification récente de la source et de son absence. L’aperçu montre la commande et les effets déclarés ; la preuve est le reçu Homebrew, pas l’acceptation d’une recette fournisseur. Les autres entrées gardent leurs voies officielles vérifiées. Aucune migration automatique des applications existantes. Les recommandations reposent sur les données disponibles des versions stables.

`--dry-run` affiche un aperçu lisible de 10 cibles maximum. `--dry-run --json-summary` ou `--plan` fournit le plan JSON complet. Cet aperçu ne donne aucune autorisation et ne lance aucune mise à jour.

L’écran d’autorisation affiche dix éléments admissibles par page. Saisissez des numéros comme `1,3` pour autoriser uniquement leurs actions affichées ; `n` et `p` changent de page. Entrée ou `q` poursuit sans nouvelle autorisation. Le délai de 120 secondes est expliqué ; son expiration ne donne aucun accord. Les éléments bloqués sont résumés séparément. Utilisez `--preferences` pour les choix manuels, ignorés ou reportés. Le journal commence avant cette revue.

## Commandes et liste des applications

Tab passe entre la navigation, la zone de travail, la sortie et les boutons inférieurs. Les flèches sélectionnent, Espace coche et Entrée active le bouton sélectionné. Les questions ouvrent automatiquement le champ de réponse. Envoyer confirme ; Annuler ferme le champ sans répondre.

L’inventaire affiche les applications enregistrées par source, avec recherche, filtres et tri. Enregistrer la sélection conserve les exclusions sans installer ni désinstaller. Réactiver une application nécessite un consentement distinct pour la mise à jour. La liste reste visible après la simulation. Le journal détaillé est séparé du statut des applications.

À propos contient l’auteur, les liens et la recherche explicite des mises à jour de l’outil. L’aperçu fixe une révision. Appliquer ferme l’interface et demande confirmation dans le terminal. Du code modifié, une branche inattendue ou des conflits de fichiers bloquent la mise à jour. Les changements locaux ne sont jamais envoyés au dépôt de l’auteur.

Le mode automatique utilise l’accord enregistré s’il couvre le groupe admissible ; sinon il propose une vérification AUTO séparée. Les fenêtres natives autorisées s’ouvrent en parallèle et les téléchargements partagent le groupe supervisé ; les tâches Microsoft et Google sont regroupées. La gestion App Store et Homebrew est conservée. DeepSeek Harness reste manuel ; Open Design signale actuellement une méthode automatique indisponible. L’éditeur choisit les versions selon les réglages de canal existants. Un changement de version ne prouve pas la fin de la mise à jour. Le travail non confirmé conserve le verrou du groupe et reporte la mise à jour système ; Diagnostic propose une récupération explicite avec nouvelle vérification d’identité. L’autorisation Google couvre tous les produits enregistrés auprès de son outil, y compris hors catalogue, dont la liste complète est inconnue. Cela reste distinct de l’acceptation d’une recette pour une version précise. `bash update_all.sh --cli --automatic-internet-batch` présente la même vérification sans interface de terminal ; ajoutez `--dry-run` pour un aperçu sans modification.
