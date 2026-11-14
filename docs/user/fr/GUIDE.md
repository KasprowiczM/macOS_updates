# Guide utilisateur (Français)

**Version :** 1.7.4 · **Apple Silicon, macOS 13+**

## Configuration sûre et sources des applications

`bash setup.sh --inspect` vérifie la disponibilité sans installation, modification du profil shell ni configuration Touch ID. Un outil absent rend sa fonction indisponible. Dans un terminal, `bash setup.sh --install-dependencies` présente les dépendances facultatives et demande avant chaque installation ; `bash setup.sh --configure-shell` présente séparément la modification du profil. Refuser une dépendance ne bloque pas les fonctions indépendantes. Sans Python, installez-le explicitement avant de construire l’inventaire. Un `mas` absent ou ancien est signalé, jamais installé ni mis à niveau automatiquement.

Il s’agit d’un checkpoint source local, non publié et non étiqueté. Le gestionnaire agit uniquement sur les cibles installées dont la source est observée et après une nouvelle autorisation. Les adaptateurs génériques natifs et éditeur restent manuels en attendant des recettes vérifiées. Le catalogue public facultatif couvre 48 produits et propose des liens officiels vérifiés pour une acquisition manuelle ; aucune recette de première installation automatique n’est approuvée. La liste des méthodes ci-dessous décrit des capacités, pas une autorisation d’exécution. Le rapport normal porte sur les applications installées. `bash scripts/report_update_coverage.sh --show-supported` reste une liste de référence. Le menu facultatif s’ouvre avec `bash setup.sh --catalog`, sans sélection initiale. Après aperçu et nouvelle autorisation, une app peut être acquise manuellement via un lien officiel vérifié. Changer la source d’une app existante exige une migration manuelle. Un reçu App Store pour CapCut conserve cette source. Une app locale sans propriété Homebrew confirmée n’est jamais adoptée automatiquement.

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

L’inventaire JSON local et les plans d’action ciblés sont disponibles. `bash update_all.sh --plan` et `--dry-run` affichent les mêmes décisions sans écriture. Un lancement interactif demande une fois les portées affichées ; `-y`, EOF et les lancements sans terminal ne donnent aucune nouvelle autorisation. Utilisez `--preferences` pour revoir ou réinitialiser les choix. Les mises à jour conservent la source et la destination observées ; conflits, cibles absentes et preuves incertaines reportent cette cible. `build_inventory.sh --migration --preview` conserve les octets Markdown originaux et les notes ; acceptez explicitement l’identifiant affiché. Les mises à jour génériques restent manuelles jusqu’à la vérification de l’identité et de l’adaptateur. Une entrée de catalogue ne prouve ni installation ni consentement.


## Catalogue facultatif et première installation

Les nouveaux signaux d’applications sont des propositions à examiner, pas des recettes exécutables. `bash scripts/scan_update_feeds.sh` affiche un résumé agrégé. L’export permet l’aperçu et l’acceptation explicite ; il est expurgé, reste local et n’est jamais téléversé. `bash setup.sh --catalog` ouvre le catalogue sans sélection. `-y`, les exécutions non interactives et EOF n’installent rien. Dans le menu, `check <number>` compare uniquement les sources choisies. Les résultats indiquent la dernière version stable compatible confirmée et sa date ; le cache dure 24 heures. Une valeur inconnue le reste. Une fiche publique du Mac App Store ne prouve pas que l’app est proposée à votre compte.

Le catalogue public compte 47 lignes de registre pour 48 produits et zéro recette approuvée de première installation automatique. Après confirmation, choisissez des liens officiels vérifiés pour une acquisition manuelle. Ouvrir une page n’installe pas l’app. Changer la source d’une app existante exige une migration manuelle. L’InstallPlan indique source, destination, version, prérequis et autorisations ; licence et coût inconnus restent signalés comme tels. Toute recette automatique future exigera une validation avant activation. Le catalogue ne promet pas d’installer automatiquement tous les produits.

## État local des mises à jour par recette

Il s’agit d’un checkpoint source local, non publié et non étiqueté. Le catalogue public comprend 48 produits répartis sur 47 lignes de registre et zéro recette automatique approuvée pour les éditeurs, le moteur natif ou la première installation. Le gestionnaire prend en charge les opérations ciblées sur les cibles installées après consentement ; les mises à jour éditeur sans recette acceptée restent manuelles. Les 48 dossiers et fixtures synthétiques ne prouvent pas une acceptation réelle. L’acquisition directe de ZIP, l’installation explicite et le moteur natif sont implémentés ; l’acceptation réelle T6 et l’activation T7 restent en attente. Aucun chemin force, adopt, migration ou bootstrap des dépendances n’existe. Les apps utilisateur existantes sont protégées. Les recommandations sont stables par produit, sans classement universel du canal le plus rapide. Un scan fournisseur incomplet est un avis, mais les cibles dangereuses sont bloquées ; consultez le JSON. Les métadonnées Cask de l’hôte ne sont pas réparées. Le planificateur autorise au plus deux mutations indépendantes entre checkouts coopérants du même utilisateur système ; l’exécution publique reste séquentielle jusqu’à l’acceptation des effets indépendants. La mise à jour système prend en dernier le verrou global exclusif. Un redémarrage en attente ou un helper inconnu peut bloquer les mutations jusqu’à une nouvelle preuve de réconciliation vérifiée. Aucun délai automatique ni réconciliation au démarrage n’existe encore. Voir le [reçu central d’implémentation](../../implementation/RECIPE_VERIFICATION_2026-11-14.md). Les apps ouvertes restent protégées. DeepSeek Harness est exclu jusqu’à stabilité.
