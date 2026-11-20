# Démarrage rapide (Français)

**Mises à jour macOS 2.0.10** · Mac Apple Silicon · macOS 13 ou plus récent · environ 5 minutes

Mises à jour macOS maintient à jour les logiciels déjà présents sur votre Mac : apps de l'App Store, outils du Terminal, paquets Homebrew, apps téléchargées sur Internet et macOS lui-même. Il n'installe jamais d'apps que vous n'avez pas.

## 1. Installer

Collez ceci dans le Terminal :

```bash
/bin/bash -c "$(curl -fsSL https://github.com/KasprowiczM/macOS_updates/releases/latest/download/install.sh)"
```

L'installateur télécharge la version, vérifie sa somme de contrôle et ajoute la commande `mac-update`. Il ne met rien à jour, et il n'a besoin ni de `git` ni de `sudo`. Il vous faut Python 3.9 ou plus récent (s'il manque, l'installateur vous indique de lancer `xcode-select --install`). Détails : [INSTALL.md](../../INSTALL.md) (en anglais).

Ouvrez ensuite une nouvelle fenêtre de terminal pour que la commande soit trouvée. Si `mac-update` reste introuvable, relancez l'installateur avec `bash -s -- --configure-shell` après le tube, comme expliqué dans INSTALL.md.

## 2. Aperçu

```bash
mac-update
```

Dans un terminal, cela ouvre l'interface sur l'**Accueil**. Allez sur **Aperçu (sans modification)** avec la flèche droite et appuyez sur Entrée. Rien n'est installé. Vous voyez ce qui serait mis à jour.

Vous préférez le texte simple ? Lancez `mac-update preview`. `mac-update --cli` (aussi `--plain`) équivaut à `mac-update run`, `mac-update --tui` équivaut à `mac-update` seul, et `macos-update` est la même commande sous un nom plus long. Tous fonctionnent depuis n'importe quel dossier.

## 3. Mettre à jour

Sur l'Accueil, choisissez **Tout mettre à jour** et appuyez sur Entrée. Vous voyez chaque groupe (App Store, Outils du Terminal, Homebrew, Apps d'Internet, Liste des apps, Système macOS) et chaque app au fil de sa mise à jour. Si macOS demande votre mot de passe, saisissez-le dans le terminal ; le programme ne l'enregistre jamais.

Vous pouvez arrêter à tout moment. Les apps déjà mises à jour le restent.

## 4. Lire le résultat

L'écran de résultat contient trois listes :

- **Mises à jour** : ces apps sont maintenant à jour.
- **À jour** : rien n'était nécessaire.
- **À faire par vous** : le programme n'a pas pu terminer seul. Chaque ligne dit pourquoi et que faire. Raisons fréquentes : l'app était ouverte, l'App Store demande que vous vous connectiez, ou un redémarrage est nécessaire. Voir le [guide](GUIDE.md).

Les apps que vous avez ouvertes ne sont jamais fermées. Quittez-les et relancez la mise à jour.

## 5. Et ensuite

| Je veux... | Faites ceci |
|------------|-------------|
| Changer la façon dont une app est mise à jour | Onglet Apps, Entrée sur l'app : automatique, manuel ou ignorer |
| Désactiver un groupe, ou les mises à jour de macOS | Accueil : allez sur le groupe, appuyez sur Espace. Ou Réglages, « Mises à jour macOS » |
| Lancer sans l'interface | `mac-update run` |
| Vérifier mon Mac sans rien mettre à jour | `mac-update doctor` |
| Lancer automatiquement | Réglages, section « Exécutions automatiques ». Voir [OPERATIONS.md](OPERATIONS.md) |
| Voir ce qui s'est mal passé | Onglet Historique, puis Entrée sur une exécution pour ouvrir son journal |
| Reprendre les réglages d'une ancienne copie git | `mac-update migrate` (un aperçu s'affiche d'abord) |

Pour aller plus loin : [GUIDE.md](GUIDE.md) · [OPERATIONS.md](OPERATIONS.md) · [UNINSTALL.md](../../UNINSTALL.md) (en anglais)
