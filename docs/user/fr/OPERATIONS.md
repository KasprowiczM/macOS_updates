# Opérations (Français)

**Mises à jour macOS 2.0.10** · pour ceux qui lancent le programme depuis un terminal, un script ou une planification.

## Façons de lancer

| Commande | Ce qui se passe |
|----------|-----------------|
| `mac-update` | Ouvre l'interface (il faut un terminal). |
| `mac-update run [options]` | Exécution en texte simple. Les options sont transmises au programme de mise à jour, par exemple `-y`, `--skip-system`, `--non-interactive`. |
| `mac-update --cli [options]` | Équivaut à `mac-update run` (aussi `--plain`). |
| `mac-update --tui` | Équivaut à `mac-update` : ouvre l'interface. |
| `mac-update preview` | Parcourt chaque étape et affiche ce qui se passerait. Rien n'est mis à jour. |
| `mac-update scan` | Refait la liste des apps de ce Mac. Lecture seule. |
| `mac-update doctor` | Bilan de préparation en lecture seule. Pas de mot de passe, pas de journal d'exécution. |
| `mac-update settings` | Ouvre l'interface sur l'onglet Réglages. |
| `mac-update update-self` | Cherche une version plus récente de mac-update (`--check`, par défaut, ou `--prepare`). |
| `mac-update migrate` | Reprend les réglages d'une ancienne copie git : `--preview` (par défaut), `--apply`, `--undo MANIFEST`. |
| `mac-update uninstall` | Retire mac-update. Voir [UNINSTALL.md](../../UNINSTALL.md) (en anglais). |
| `mac-update version`, `mac-update help` | Version et liste des commandes. |

`macos-update` est la même commande que `mac-update`, sous un nom plus long. L'installateur crée les deux liens dans `~/.local/bin`, et les deux fonctionnent depuis n'importe quel dossier.

`mac-update` appelle `update_all.sh` dans le dossier du programme `~/.local/share/mac-update`. Si vous travaillez plutôt depuis une copie git, lancez `bash update_all.sh` dedans ; les options ci-dessous sont les mêmes. Avec `MAC_UPDATE_NONINTERACTIVE=1`, l'interface ne s'ouvre jamais et rien n'attend de réponse.

## Options de `update_all.sh`

| Option | Signification |
|--------|---------------|
| `-y`, `--yes` | Ne pas poser la question de confirmation |
| `-h`, `--help` | Afficher la liste des options |
| `--tui`, `--cli` | Choisir l'interface ou le texte simple. `--tui` échoue avec un message s'il n'y a pas de terminal utilisable ; seuls `--dry-run` et `--skip-...` peuvent s'y ajouter. |
| `--dry-run` | Aperçu, rien n'est modifié |
| `--doctor` | Bilan de préparation. Code de sortie 0 : ok, 10 : avertissements, 1 : problème |
| `--verify-only` | Comparer les versions des apps installées avec l'historique, sans rien modifier |
| `--json-summary` | Afficher un résumé JSON à la fin |
| `--bootstrap-cli` | Installer aussi un Node, un Bun ou un outil natif en ligne de commande géré qui manque. Désactivé par défaut. |
| `--skip-prescan` | Ignorer la première vérification de la liste des apps |
| `--skip-appstore` | Ignorer les apps de l'App Store |
| `--skip-npm` | Ignorer les outils du Terminal (npm, bun, outils natifs en ligne de commande) |
| `--skip-brew` | Ignorer Homebrew |
| `--skip-internet` | Ignorer les apps d'Internet |
| `--skip-postupdate` | Ignorer l'actualisation de la liste des apps et de l'historique |
| `--skip-system` | Ignorer la mise à jour de macOS |
| `--skip-doctor` | Ignorer `brew doctor` dans l'étape Homebrew |
| `--treat-appstore-ax-as-warning` | Signaler l'absence de l'autorisation d'accessibilité comme un avertissement |
| `--non-interactive` | Pour les planificateurs : aucune question (comme `MAC_UPDATE_NONINTERACTIVE=1`) |
| `--notify` | Afficher une notification macOS à la fin de l'exécution |

Les étapes s'exécutent toujours dans cet ordre : vérification du système, App Store, outils du Terminal, Homebrew, apps d'Internet, liste des apps, macOS. macOS passe en dernier parce qu'il peut redémarrer le Mac. Si une étape précédente a échoué gravement, l'étape macOS attend la prochaine exécution.

## Variables d'environnement

Placez-les devant la commande, par exemple `MAC_UPDATE_MIN_FREE_GB=30 mac-update run`. La plupart existent aussi comme ligne dans Réglages ; une ligne définie par une variable ne peut pas être modifiée dans l'interface.

| Variable | Par défaut | Rôle |
|----------|------------|------|
| `MAC_UPDATE_NONINTERACTIVE` | désactivé | `1` : pas d'interface, pas de questions |
| `MAC_UPDATE_DRY_RUN` | désactivé | `1` : comme `--dry-run` |
| `MAC_UPDATE_SKIP_APPSTORE`, `_NPM`, `_BREW`, `_INTERNET`, `_SYSTEM`, `_PRESCAN`, `_POSTUPDATE`, `_DOCTOR` | désactivé | `1` : comme l'option `--skip-...` correspondante |
| `MAC_UPDATE_SYSTEM_MODE` | `auto` | Mises à jour macOS : `auto` installe, `notify` signale seulement, `skip` ne vérifie pas |
| `MAC_UPDATE_NEW_APP_MODE` | selon la confiance | `auto` ou `manual` pour les apps nouvellement trouvées qui ne sont pas dans la liste testée |
| `MAC_UPDATE_NOTIFY` | désactivé | `1` : notification à la fin. Pour les exécutions automatiques : `always`, `needs_you` ou `never` |
| `MAC_UPDATE_LANG` | langue du système | `en`, `pl`, `de`, `fr`, `es`, `it`, `pt` |
| `MAC_UPDATE_HOME` | `~/.local/share/mac-update` | Dossier du programme |
| `MAC_UPDATE_CONFIG_DIR` | `~/.config/mac-update` | Dossier des réglages |
| `MAC_UPDATE_STATE_DIR` | `~/.local/state/mac-update` | Journaux, caches, sauvegardes |
| `MAC_UPDATE_LOGS_DIR` | `logs` dans le dossier d'état | Journaux d'exécution |
| `MAC_UPDATE_OVERRIDES_FILE` | `overrides.tsv` dans le dossier des réglages | Fichier des choix par app |
| `MAC_UPDATE_MAX_LOGS` | 30 | Journaux d'exécution à conserver |
| `MAC_UPDATE_PROMPT_TIMEOUT` | 120 | Secondes pour répondre à une question avant que la réponse sûre soit utilisée |
| `MAC_UPDATE_MIN_FREE_GB` | 15 | Avertir et exécuter en mode réduit sous cet espace libre |
| `MAC_UPDATE_MIN_BATTERY` | 30 | Sur batterie sous ce pourcentage, ignorer l'étape macOS (une exécution automatique est alors ignorée en entier) |
| `MAC_UPDATE_NO_CAFFEINATE` | désactivé | `1` : ne pas garder le Mac éveillé pendant l'exécution |
| `MAC_UPDATE_NO_SUDO_KEEPALIVE` | désactivé | `1` : ne pas garder le mot de passe administrateur valide |
| `MAC_UPDATE_SUDO_KEEPALIVE_MAX` | 14400 | Secondes pendant lesquelles le garder valide (300 à 14400) |
| `MAC_UPDATE_QUIT_WAIT` | 60 | Secondes d'attente de la fermeture d'une app lancée par le programme (0 à 300) |
| `MAC_UPDATE_STAGE_WAIT` | 90 | Secondes d'attente pour qu'une app ouverte par le programme installe sa propre mise à jour (0 à 600) |
| `MAC_UPDATE_POST_QUIT_WAIT` | 10 | Secondes d'attente après la fermeture d'une telle app lorsque sa mise à jour est préparée |
| `MAC_UPDATE_POST_QUIT_WAIT_IDLE` | 3 | La même chose lorsqu'aucune mise à jour n'est préparée |
| `MAC_UPDATE_OMAHA_WAIT` | 45 | Secondes d'attente de la réponse de l'updater de Google (0 à 180) |
| `MAC_UPDATE_OMAHA_MAX_AGE_H` | 6 | Heures pendant lesquelles une vérification de l'updater de Google est considérée comme récente |
| `MAC_UPDATE_BTM_CHECK` | activé | `0` : ne pas vérifier si macOS bloque une app dans Éléments d’ouverture et extensions |
| `MAC_UPDATE_BTM_TIMEOUT` | 4 | Secondes accordées à cette vérification |
| `MAC_UPDATE_BTM_DUMP`, `MAC_UPDATE_GOOGLE_USER_LOG`, `MAC_UPDATE_GOOGLE_SYS_LOG` | aucun | Uniquement pour le diagnostic et les tests : une liste enregistrée des éléments d'ouverture ou des fichiers journaux de l'updater de Google, lus à la place des vrais |
| `MAC_UPDATE_VENDOR_DIRECT` | activé | `0` : pas de téléchargement direct chez l'éditeur de l'app |
| `MAC_UPDATE_ALLOW_MAJOR_UPGRADE` | désactivé | `1` : autoriser les grands sauts de version, y compris une mise à niveau majeure de macOS |
| `MAC_UPDATE_MAU_DEFERRAL_DAYS` | 7 | Jours d'attente avant d'installer une nouvelle version de Microsoft Office |
| `MAC_UPDATE_FEED_CACHE_TTL_H` | 24 | Heures pendant lesquelles les informations de version de l'éditeur sont réutilisées |
| `MAC_UPDATE_MAS_UPGRADE_TIMEOUT` | 1800 | Secondes avant qu'une mise à jour de l'App Store soit arrêtée et signalée |
| `MAC_UPDATE_DOCTOR_PROBE_AX` | désactivé | `1` : laisser `doctor` tester l'autorisation d'accessibilité (macOS peut afficher une demande) |
| `GITHUB_TOKEN` | aucun | Facultatif. Relève la limite de téléchargement de GitHub. À définir dans le profil de votre shell |

## Exécutions automatiques (facultatif)

Les exécutions automatiques sont désactivées par défaut et n'ont pas d'heure préréglée. Activez-les dans **Réglages**, section **Exécutions automatiques**, ligne « Automatisation quotidienne ». Vous choisissez :

- quand : chaque jour à une heure que vous saisissez (24 h, par exemple 08:30), à l'ouverture de session, ou les deux ;
- comment vous êtes prévenu : après chaque exécution, seulement si quelque chose me demande (par défaut), ou jamais.

Vous voyez exactement ce qui sera installé et vous confirmez avant que quoi que ce soit soit écrit. « Tester maintenant » planifie une exécution supplémentaire dans quelques minutes.

La même chose depuis un terminal, avec `bash ~/.local/share/mac-update/scripts/install_launchagent.sh` :

```bash
bash scripts/install_launchagent.sh --daily 08:30 --notify needs_you      # every day at 08:30
bash scripts/install_launchagent.sh --daily 08:30 --days 1,3,5            # only on chosen weekdays (numbers 1 to 7)
bash scripts/install_launchagent.sh --at-login --delay-min 10             # at login, after 10 minutes of session time
bash scripts/install_launchagent.sh --once-in 5                           # one test run in 5 minutes
bash scripts/install_launchagent.sh --status                              # is it installed? (--check, or --status --json)
bash scripts/install_launchagent.sh --uninstall                           # remove every mac-update schedule
```

Lancez-les depuis le dossier du programme. `--notify` accepte `always`, `needs_you` ou `never`.

Ce que fait une exécution automatique :

- Elle s'exécute sans terminal et ne pose jamais de question.
- Elle ignore les mises à jour de macOS, sauf si vous les activez ; macOS signale alors seulement ce qui est disponible.
- Elle s'ignore elle-même quand une autre exécution est active, quand la batterie du Mac est faible, ou quand la dernière exécution réussie date de moins de 12 heures.
- Tout ce qui demande votre mot de passe ou un redémarrage est ignoré et signalé dans « À faire par vous ». Lancez `mac-update` vous-même pour terminer.
- Elle envoie une notification, comme vous l'avez choisi. La sortie va dans `launchd.out` et `launchd.err` dans le dossier des journaux.

## Mots de passe

Les étapes macOS et App Store peuvent demander votre mot de passe administrateur. Dans un terminal, le programme le demande au plus une fois par exécution et le garde valide pour le reste de l'exécution. Il ne le demande jamais dans un aperçu, ni sans terminal (les exécutions automatiques ignorent alors ces étapes). Facultatif : `bash scripts/setup_touchid_sudo.sh --check` indique si Touch ID peut remplacer le mot de passe pour `sudo`. Lancer le script sans `--check` affiche un aperçu et demande d'abord confirmation.

## Où se trouvent les choses

| Quoi | Où |
|------|----|
| Le programme | `~/.local/share/mac-update` |
| Vos réglages et vos choix par app | `~/.config/mac-update` (`overrides.tsv`, `lang`, `reports/`) |
| Journal de chaque exécution | `~/.local/state/mac-update/logs/update_all_<date>_<time>.log` (les 30 plus récents sont conservés, mode 600) |
| Résultat court de la dernière exécution | `~/.local/state/mac-update/logs/run_summary_latest.json` |
| Réglages de l'interface | `~/.local/state/mac-update/tui-settings.json` |
| Sortie des exécutions automatiques | `~/.local/state/mac-update/logs/launchd.out`, `launchd.err` |

Un aperçu écrit son journal dans un dossier temporaire et laisse votre historique inchangé. Dans l'interface, l'onglet **Historique** liste les exécutions passées et `L` ouvre le journal le plus récent. Vous venez d'une ancienne copie git : `mac-update migrate`.

Code de sortie de `update_all.sh` : `0` quand l'exécution s'est bien passée ou n'a eu que des avertissements (une app qui demande votre action est un avertissement), `1` quand quelque chose a échoué.

## Dépannage

Commencez par `mac-update doctor`. Il vérifie la plateforme, Python, curl, Homebrew, `mas`, Touch ID, l'espace disque, l'alimentation, le réseau et le programme lui-même.

| Problème | Que faire |
|----------|-----------|
| `mac-update: command not found` | Ouvrez une nouvelle fenêtre de terminal. Si cela persiste, `~/.local/bin` n'est pas dans votre `PATH` : relancez l'installateur avec `--configure-shell`, ou ajoutez ce dossier vous-même. |
| `mac-update` lance un autre programme | Un autre programme du même nom se trouve plus tôt dans votre `PATH`. L'installateur vous en avertit et nomme le fichier de ce programme. Lancez directement `~/.local/bin/mac-update`, ou supprimez ou renommez l'autre fichier. |
| L'interface ne s'ouvre pas | Il lui faut un terminal, Python 3 et un `TERM` différent de `dumb`. Sinon, utilisez `mac-update run`. |
| L'installateur dit que la somme de contrôle ne correspond pas | Rien n'a été installé. Réessayez plus tard ; si cela se répète, signalez-le. |
| Une app est dans « À faire par vous » | Voir le tableau « Ce que signifie « À faire par vous » » dans [GUIDE.md](GUIDE.md). |
| L'étape App Store s'arrête avec le code de sortie 2 | Le terminal n'a pas l'autorisation d'accessibilité. Autorisez-le dans Réglages Système, Confidentialité et sécurité, Accessibilité, ou ajoutez `--treat-appstore-ax-as-warning`. |
| `mas` est absent ou trop ancien | Le programme le signale et ne l'installe jamais tout seul. Installez-le vous-même avec Homebrew (`brew install mas`). |
| L'App Store demande de se connecter | Ouvrez l'App Store, connectez-vous, relancez. |
| Homebrew est absent | Installez-le depuis <https://brew.sh>, puis relancez. |
| La liste des apps est absente ou fausse | `mac-update scan`. Il ne lit que votre Mac. Ne copiez jamais la liste de quelqu'un d'autre. |
| Une app n'est jamais mise à jour | Diagnostic, « Comment les apps sont mises à jour », montre comment chaque app est traitée. Ouvrez l'app et utilisez sa propre option « Rechercher des mises à jour » s'il n'y a pas de méthode. |
| Les informations de mise à jour d'un éditeur sont inaccessibles | Réessayez plus tard. Testez les flux dans Diagnostic, « Vérifier les flux de mises à jour ». |
| Le Mac s'est mis en veille pendant une exécution | Laissez « Garder le Mac éveillé » activé (par défaut). |
| Une mise à jour a été interrompue | Diagnostic, « Terminer les mises à jour interrompues ». |
| Une exécution dit qu'une autre est en cours | Attendez qu'elle se termine. Un marqueur laissé par une exécution plantée est nettoyé au début de la suivante. |
| Disque ou batterie insuffisants | Libérez de l'espace ou branchez le chargeur. Les limites sont dans Réglages, « Contrôles de sécurité ». |

Toujours bloqué ? Ouvrez le fichier le plus récent du dossier des journaux et cherchez la première ligne qui mentionne une erreur ou un avertissement.

## Désinstallation

```bash
mac-update uninstall
```

Cela désactive aussi les exécutions automatiques. Voir [UNINSTALL.md](../../UNINSTALL.md) (en anglais) pour ce qui est retiré et ce qui ne l'est pas.
