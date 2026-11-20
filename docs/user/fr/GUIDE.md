# Guide utilisateur (Français)

**Mises à jour macOS 2.0.10** · Mac Apple Silicon · macOS 13 ou plus récent

## Ce que fait le programme

Une exécution met à jour, dans cet ordre :

1. Les apps de l'App Store
2. Les outils du Terminal (npm, bun et les outils en ligne de commande qui se mettent à jour eux-mêmes)
3. Les formules et les casks Homebrew
4. Les apps d'Internet : apps téléchargées depuis le site de l'éditeur, mises à jour depuis le flux de mises à jour de l'éditeur, par un téléchargement direct vérifié ou par l'outil de mise à jour de l'app
5. La liste de vos apps (actualisée)
6. macOS, toujours en dernier

Il ne vous demande pas de valider chaque app. Il n'agit que sur ce qui est déjà installé.

## Ce qu'il ne fait jamais

- Il ne ferme jamais une app que vous avez ouverte. Cette app est signalée dans « À faire par vous ».
- Il n'installe jamais une app que vous n'avez pas. (L'onglet facultatif Catalogue est le seul endroit qui peut installer, et seulement ce que vous choisissez.)
- Il ne fait jamais confiance aveuglément à un téléchargement. Un téléchargement doit venir d'un hôte autorisé, avoir une signature de code valide et réussir Gatekeeper.
- Il n'arrête jamais tout parce qu'un élément a échoué. Les autres éléments, les étapes suivantes et la mise à jour de macOS s'exécutent quand même.

## Ouvrir l'interface

```bash
mac-update
```

Dans un terminal, cela ouvre l'interface. Dans un script, par SSH sans terminal, ou avec `MAC_UPDATE_NONINTERACTIVE=1`, vous obtenez du texte simple. `mac-update run` donne toujours du texte simple. `mac-update --cli` (aussi `--plain`) équivaut à `mac-update run`, `mac-update --tui` équivaut à `mac-update` seul, et `macos-update` est la même commande sous un nom plus long. Tous fonctionnent depuis n'importe quel dossier. La fenêtre doit faire au moins 40 colonnes sur 12 lignes. Plus grande, c'est plus agréable : si « Ajuster la fenêtre automatiquement » reste activé, l'interface demande au terminal 120 sur 36 au démarrage et rétablit la taille quand vous quittez.

Déplacez-vous avec les flèches. Entrée ouvre ou confirme, Tab passe au panneau suivant, Échap revient en arrière, `1` à `7` sautent à un onglet, `?` ouvre l'aide, `L` affiche le journal complet, `q` quitte. La souris fonctionne aussi. La ligne du bas indique toujours les touches utilisables à cet instant.

## Les onglets

```
 Mises à jour macOS                       Dernière fois : terminé, il y a 2 h
 Accueil   Apps   Catalogue   Historique   Réglages   Diagnostic   Aide
 +- Groupes de mises à jour -------------------------------------------+
 | > v Vérification du système  ############  terminé                   |
 |   v App Store                ############  v3 .5                     |
 |   v Outils du Terminal       ############  v2 .9                     |
 |   * Homebrew                 ######......  4/9  v1 .3                |
 |   . Apps d'Internet          ............  en attente                |
 |   . Liste des apps           ............  en attente                |
 |   . Système macOS            ............  en attente                |
 +---------------------------------------------------------------------+
   [ Tout mettre à jour ]   [ Aperçu (sans modification) ]
   ✓ mis à jour  • à jour  ! à faire par vous  ✗ échec
```

Ce dessin est simplifié. L'écran réel utilise des couleurs et des symboles.

| Onglet | À quoi il sert |
|--------|----------------|
| **Accueil** | Lancer une mise à jour. Montre chaque groupe avec sa progression en direct (fait sur total), et une liste défilante des apps qu'il contient pendant l'exécution. Entrée ou Espace sur un groupe l'active ou le désactive pour la prochaine exécution. Un panneau latéral montre la dernière exécution, ce qui demande encore votre action, la prochaine exécution automatique et l'état de ce Mac. |
| **Apps** | Toutes les apps et tous les paquets trouvés sur ce Mac (les apps auxiliaires et d'arrière-plan sont laissées de côté). Choisissez comment chacun est mis à jour. |
| **Catalogue** | Toutes les apps testées : d'abord celles qu'on peut encore ajouter, puis celles déjà installées (affichées seulement). Rien n'est sélectionné tant que vous n'avez pas choisi, et l'installateur demande avant chaque changement. Les mises à jour ne l'utilisent jamais. |
| **Historique** | Les exécutions précédentes, la plus récente en premier, chacune avec son résultat. Sélectionnez une exécution pour voir ce qui a été mis à jour et ce qui demandait votre action. Entrée ouvre son journal complet. |
| **Réglages** | Quoi mettre à jour, limites de sécurité, planification, langue et apparence. Chaque modification est enregistrée aussitôt. |
| **Diagnostic** | Des vérifications à lancer : vérifier ce Mac, vérifier les prérequis, comment les apps sont mises à jour (un tableau de toutes les apps et de la façon dont leur méthode a été trouvée), vérifier les flux de mises à jour, refaire la liste des apps, terminer les mises à jour interrompues, chercher une mise à jour du programme. |
| **Aide** | Un court guide : premiers pas, comment fonctionne la mise à jour, à quoi sert chaque onglet, ce que signifie « À faire par vous ». |

## Lancer une mise à jour

- **Tout mettre à jour** vérifie et met à jour chaque groupe activé.
- **Aperçu (sans modification)** suit les mêmes étapes et montre ce qui se passerait. Il n'installe rien et n'écrit pas dans l'historique.

Pendant l'exécution, vous voyez chaque groupe et chaque app : vérification, téléchargement, contrôle, installation. Appuyez sur `L` pour le journal complet. **Arrêter** met fin à l'exécution sans risque : les apps déjà mises à jour le restent.

Les questions (par exemple un redémarrage) attendent votre réponse. Si vous ne répondez pas à temps, la réponse sûre est utilisée. Votre mot de passe administrateur se saisit dans le terminal et n'est jamais enregistré ni affiché.

L'écran de résultat liste :

- **Mises à jour** : maintenant à jour.
- **À jour** : rien n'était nécessaire.
- **À faire par vous** : voir plus bas.

## Comment les apps d'internet sont mises à jour

- Les apps avec un téléchargement vérifié de leur éditeur (par exemple Claude et Antigravity IDE) sont installées directement au lieu d'être ouvertes puis attendues. Si ce téléchargement échoue, le programme de mise à jour de l'app reste utilisé.
- Une app ouverte pour se mettre à jour elle-même est fermée dès que sa mise à jour est préparée (Warp), au lieu d'attendre tout le délai.
- Chrome pendant un déploiement progressif est signalé aussitôt que l'updater de Google a déjà répondu « aucune mise à jour » pour votre version.
- Les apps Google (Gemini, Chrome, Google Drive) indiquent quand l'updater de Google a vérifié pour la dernière fois et quand il vérifiera à nouveau, ou que l'app s'est mise à jour seule.
- Une app Homebrew ouverte qui s'est déjà mise à jour seule est signalée à jour, sans avertissement.
- Quand macOS bloque une app dans **Éléments d’ouverture et extensions** (elle se ferme juste après l'ouverture), le résultat le dit et indique où l'autoriser : Réglages Système › Général › Éléments d’ouverture et extensions.

## Réglage app par app

Ouvrez l'onglet **Apps**. Tapez `/` pour chercher par nom ou par source. Appuyez sur Entrée sur une app. Espace en marque plusieurs pour les modifier ensemble.

| Mode | Signification |
|------|---------------|
| **automatique** | Le programme la met à jour pour vous. C'est la valeur par défaut. |
| **manuel** | Le programme vous prévient seulement quand une mise à jour est disponible. |
| **ignorer** | Le programme n'y touche pas. |

Vous pouvez aussi choisir une **source préférée** quand une app en a plusieurs : source par défaut, Homebrew, App Store, site de l'éditeur ou outil de mise à jour intégré. La colonne **Méthode** montre comment le programme connaît l'app : testée (dans la liste testée du programme), détectée (trouvée grâce à un reçu de l'App Store, à Homebrew, à un flux de mises à jour ou à un outil de mise à jour intégré) ou manuelle (rien n'a été reconnu). Le réglage « Apps nouvellement trouvées » décide de ce qui arrive aux apps qu'une analyse trouve hors de la liste testée : selon la confiance (automatique quand la méthode de mise à jour est claire, sinon manuel), toujours automatique, ou toujours manuel.

Si la liste est vide, choisissez **Analyser maintenant**. L'analyse ne fait que lire les données de votre Mac.

Vos choix sont enregistrés dans `~/.config/mac-update/overrides.tsv`, une ligne par app : groupe, nom, mode, source (séparés par des tabulations). Supprimez le fichier pour remettre toutes les apps en automatique.

## Réglages

Choisissez un profil pour démarrer vite : **Entièrement automatique** (tout), **Prudent** (pas de mise à jour de macOS, pas de grands sauts de version), **Vérifier seulement** (rien n'est installé). Toute modification manuelle affiche **Personnalisé**.

| Section | Lignes |
|---------|--------|
| Quoi mettre à jour | Un interrupteur par groupe ; Vérifier seulement, jamais installer ; Autoriser les grosses mises à niveau (désactivé, vous restez sur la version principale actuelle) ; Mises à jour macOS : installer, signaler seulement ou désactivé (un redémarrage est toujours demandé avant) |
| Apps et sources | Apps nouvellement trouvées (selon la confiance, automatique, manuel) ; Mode et source par app (ouvre l'onglet Apps) ; Apps exclues (`config/inventory_exclusions.txt`) ; Outils npm suivis (`config/npm_global_clis.txt`) |
| Exécutions automatiques | Automatisation quotidienne (désactivée par défaut, sans heure préréglée) : quand elle s'exécute (chaque jour à l'heure choisie, à l'ouverture de session, ou les deux) et la notification après une exécution (après chaque exécution, seulement si quelque chose me demande, jamais) ; Tester maintenant |
| Contrôles de sécurité | Attendre la fermeture des apps (s) ; Télécharger depuis les sites des éditeurs ; Espace libre minimum (Go, 15 par défaut) ; Niveau de batterie minimum (%, 30 par défaut) |
| Réseau et vitesse | Réutiliser les vérifications pendant (heures) ; Temps pour répondre (s, 120 par défaut) ; Délai max. App Store (s) |
| Notifications et rapports | Notification à la fin ; Ouvrir le dernier journal ; Journaux à conserver (30 par défaut) |
| Langue et apparence | Langue (English, Polski, Deutsch, Español, Français, Italiano, Português ; elle suit la langue du système tant que vous n'en choisissez pas une) ; Couleurs ; Couleur d'accent (bleu par défaut, violet, ambre, vert sauge, rose, graphite) ; Espacement ; Caractères simples ; Ajuster la fenêtre automatiquement ; Souris ; Panneau d'aide ouvert au démarrage |
| Système et maintenance | Délai Microsoft Office (jours) ; Garder le Mac éveillé ; Refaire la liste des apps ; Mettre à jour ce programme ; Exporter les réglages ; Importer les réglages ; Rétablir les valeurs par défaut |

Les réglages sont enregistrés dans `~/.local/state/mac-update/tui-settings.json`, et votre langue dans `~/.config/mac-update/lang`. Une ligne définie par une variable d'environnement affiche cette variable et ne peut pas être modifiée dans la fenêtre. « Attendre la fermeture des apps » s'applique aux apps que le programme a lancées lui-même.

Les couleurs suivent votre terminal. Le réglage par défaut, **automatique**, demande au terminal si sa fenêtre est claire ou sombre et applique le jeu de couleurs correspondant. L'apparence claire laisse à la page le fond blanc et la couleur de texte propres à votre terminal ; seuls la barre du haut, la barre des touches, la ligne sélectionnée et les boîtes de dialogue sont en gris clair, et chaque couleur reste lisible sur une fenêtre blanche. Le jeu sombre est inchangé. Un « sombres » enregistré par une version précédente est traité une fois comme « automatique » ; si vous voulez toujours le sombre, choisissez-le de nouveau dans Réglages, Langue et apparence, Couleurs.

## Ce que signifie « À faire par vous »

Chaque ligne de l'écran de résultat a une raison et une marche à suivre.

| Raison | Que faire |
|--------|-----------|
| **L'app était ouverte** | Quittez l'app, puis relancez la mise à jour. Le programme ne la ferme jamais à votre place. |
| **Connexion requise** (App Store) | Ouvrez l'App Store, connectez-vous, puis relancez la mise à jour. |
| **Un mot de passe est nécessaire** | Relancez la mise à jour depuis un terminal et saisissez votre mot de passe administrateur quand il est demandé. Les exécutions automatiques ne peuvent pas le demander, elles le signalent donc. |
| **Un redémarrage est nécessaire** | La mise à jour est installée, mais ne prend effet qu'après un redémarrage. Redémarrez quand cela vous arrange. |
| **Pas de méthode automatique** | Il n'existe pas de moyen automatique sûr de mettre cette app à jour. Ouvrez l'app et utilisez sa propre option « Rechercher des mises à jour ». |
| **Le téléchargement a échoué** | Vérifiez votre connexion Internet et relancez la mise à jour. |
| **Somme de contrôle incorrecte** | Le téléchargement ne correspondait pas à sa somme de contrôle, rien n'a donc été installé. Réessayez plus tard ; si cela échoue encore, mettez l'app à jour manuellement. |
| **Mode manuel** | Vous avez réglé cette app sur manuel. Mettez-la à jour vous-même, ou passez-la en automatique dans l'onglet Apps. |
| **Les informations de mise à jour de l'éditeur sont inaccessibles** | Réessayez plus tard ; le site de l'éditeur est peut-être en panne. |
| **Une nouvelle version majeure est disponible** | Les grosses mises à niveau sont désactivées. Autorisez-les dans Réglages, ou mettez l'app à jour manuellement. |
| **Pas assez d'espace disque / batterie trop faible** | Libérez de l'espace, ou branchez l'adaptateur secteur, puis relancez. |
| **Cela a pris trop de temps** | Relancez la mise à jour ; ouvrez le journal complet (`L`) si cela se répète. |
| **L'outil de mise à jour de l'app s'est ouvert** | Terminez la mise à jour dans la fenêtre ouverte par l'app. |

Certaines apps installent leur mise à jour quand elles se ferment. Si le programme a lancé lui-même une telle app, il la ferme dès que la mise à jour est prête. Une app que vous avez ouverte vous-même n'est jamais fermée.

Si la raison indique « inconnue », ouvrez le journal complet avec `L`.

L'en-tête, l'Accueil et l'Historique affichent toujours les mêmes nombres. Une app iPad que l'App Store installe encore après la mise à jour est indiquée comme « encore en cours d'installation dans l'App Store », sans rien à cliquer : attendez quelques minutes et vérifiez de nouveau. Un programme de mise à jour en arrière-plan qui a été lancé sans signaler de résultat est indiqué comme « aucun résultat enregistré, rien à cliquer » ; sa version est relue ensuite, de sorte qu'une mise à jour terminée apparaît comme mise à jour.

## Où se trouvent les choses

| Quoi | Où |
|------|----|
| Journaux d'exécution (les 30 plus récents sont conservés) | `~/.local/state/mac-update/logs/` |
| Vos choix par app, la langue et la liste de vos apps | `~/.config/mac-update/` (`overrides.tsv`, `lang`, `reports/`) |
| Le programme | `~/.local/share/mac-update/` |

Pour les options, les variables d'environnement et le dépannage, voir [OPERATIONS.md](OPERATIONS.md). Pour installer, mettre à niveau ou retirer le programme, voir [INSTALL.md](../../INSTALL.md) et [UNINSTALL.md](../../UNINSTALL.md) (en anglais).
