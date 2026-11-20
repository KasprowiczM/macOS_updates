# Mises à jour macOS

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

**Version 2.0.10** · Mac Apple Silicon · macOS 13 ou plus récent · [Site web](https://macos-updates.64bit.site) · [Licence MIT](LICENSE) · [Modifications](CHANGELOG.md)

Une seule commande, `mac-update`, maintient à jour les logiciels de votre Mac. Elle ne touche que ce qui est déjà installé.

## Ce qui est mis à jour

Une exécution parcourt ces groupes, dans cet ordre :

1. Les apps de l'App Store
2. Les outils du Terminal (npm, bun, outils en ligne de commande)
3. Les formules et les casks Homebrew
4. Les apps d'Internet (depuis le flux de mises à jour de l'éditeur, un téléchargement direct vérifié ou l'outil de mise à jour de l'app)
5. La liste de vos apps
6. macOS, toujours en dernier

Il n'y a rien à valider app par app. Si vous voulez un comportement différent pour une app, réglez-la sur manuel ou ignorer dans l'onglet **Apps**. macOS lui-même peut être réglé sur installer, signaler seulement ou désactivé dans **Réglages**.

## Installation

Collez ceci dans le Terminal :

```bash
/bin/bash -c "$(curl -fsSL https://github.com/KasprowiczM/macOS_updates/releases/latest/download/install.sh)"
```

L'installateur télécharge le dernier paquet de la version, vérifie sa somme de contrôle SHA-256, place le programme dans `~/.local/share/mac-update` et relie la commande `mac-update` dans `~/.local/bin`. Il n'a pas besoin de `git`, n'utilise jamais `sudo` et conserve vos réglages lors d'une mise à niveau. Pour voir d'abord ce qu'il ferait, ajoutez `--dry-run` : `... install.sh | bash -s -- --dry-run`. Détails : [docs/INSTALL.md](docs/INSTALL.md) (en anglais).

Si `mac-update` est introuvable ensuite, ouvrez une nouvelle fenêtre de terminal. Si ce n'est toujours pas le cas, relancez l'installateur avec `--configure-shell`.

## Premier lancement

```bash
mac-update
```

Dans un terminal, cela ouvre une interface à onglets : Accueil, Apps, Catalogue, Historique, Réglages, Diagnostic, Aide. Choisissez **Aperçu (sans modification)** pour voir ce qui se passerait, puis **Tout mettre à jour**. L'écran de résultat montre ce qui a été **Mises à jour**, ce qui est **À jour** et ce qui est **À faire par vous**, avec une raison et une marche à suivre pour chaque ligne.

En texte simple : `mac-update run`. `mac-update --cli` (aussi `--plain`) équivaut à `mac-update run`, `mac-update --tui` équivaut à `mac-update` seul, et `macos-update` est la même commande sous un nom plus long. Tous fonctionnent depuis n'importe quel dossier. Aperçu en texte simple : `mac-update preview`. Vérifier votre Mac sans rien mettre à jour : `mac-update doctor`. Toutes les commandes : `mac-update help`. Il manque quelque chose (Command Line Tools, Homebrew natif, Python, `mas`) ? `mac-update doctor` le liste et `mac-update prepare` l'installe après une seule question.

Vous venez d'une ancienne copie installée avec git ? Lancez `mac-update migrate` pour reprendre vos réglages (un aperçu s'affiche d'abord).

## Sécurité

- Les apps que vous avez ouvertes ne sont jamais fermées. Elles sont signalées dans « À faire par vous ».
- Les téléchargements viennent uniquement d'hôtes autorisés et doivent réussir la vérification de la signature du code et Gatekeeper.
- Une mise à jour n'installe jamais une app que vous n'avez pas.
- Un élément en échec n'arrête pas les autres, et macOS se met quand même à jour en dernier.
- Les mots de passe sont saisis dans le terminal et ne sont jamais enregistrés. Une exécution automatique n'en attend jamais.

## Exécutions automatiques

Désactivées par défaut, sans heure préréglée. Pour les activer, ouvrez **Réglages**, section **Exécutions automatiques** : choisissez une heure du jour, « à l'ouverture de session », ou les deux, et la façon dont vous voulez être prévenu. Une exécution automatique ignore les mises à jour de macOS, sauf si vous les activez. Voir [Opérations](docs/user/fr/OPERATIONS.md).

## Documentation

| Langue | Démarrage rapide | Guide | Opérations |
|--------|------------------|-------|------------|
| Français | [Démarrage rapide](docs/user/fr/QUICK_START.md) | [Guide](docs/user/fr/GUIDE.md) | [Opérations](docs/user/fr/OPERATIONS.md) |

Toutes les langues : [docs/user/INDEX.md](docs/user/INDEX.md) · [Installation](docs/INSTALL.md) (en anglais) · [Désinstallation](docs/UNINSTALL.md) (en anglais)

## Licence

[MIT](LICENSE)
