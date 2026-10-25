# macOS Updates

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

**Site web :** [macos-updates.64bit.site](https://macos-updates.64bit.site) · **Dépôt :** [github.com/KasprowiczM/macOS_updates](https://github.com/KasprowiczM/macOS_updates) · **Licence :** [MIT](LICENSE) · **Changements :** [CHANGELOG.md](CHANGELOG.md)

> **v1.5.5** — Orchestrateur de mises à jour en une seule commande, prêt pour la production, pour les **Mac Apple Silicon sous macOS 13–27**. Il coordonne des mises à jour de paquets vérifiées et des déclenchements honnêtes des programmes de mise à jour des applications, pour les **logiciels déjà installés sur ce Mac**. **Multilingue** (7 langues). Surcouche privée facultative via [`dev_sync/`](dev_sync/README.md).

| En un coup d'œil | |
|------------------|--|
| Plateforme | Apple Silicon (arm64) uniquement · de macOS 13 Ventura à macOS 27 · Bash 3.2 + Python 3 |
| Pipeline | 7 étapes (0–6), la mise à jour de macOS vient toujours en dernier |
| Registre | 43 applications Internet · 11 méthodes de mise à jour (voir [Méthodes de mise à jour](#méthodes-de-mise-à-jour)) |
| Langues | EN, PL, ES, FR, DE, IT, PT (CLI et documentation) |
| Tests | 590 tests automatisés (`bash run_tests.sh`) |

**Nouveautés de la v1.5.5 :** Une mise à jour Homebrew qui supprime `python3` en cours d'exécution ne casse plus l'étape d'inventaire/rapport (le shell recherche à nouveau dans `PATH`), et une étape de rapport en échec ne repousse plus les mises à jour de macOS. Les messages finaux sont honnêtes : plus d'affirmation « fichiers mis à jour » après un échec, et les avertissements de flux périmé ou d'application non fermée ne sont plus présentés comme des mises à jour non vérifiées. Les applications lancées par l'outil reçoivent des demandes de fermeture répétées (jamais de forçage). Les versions 1.5.x précédentes (flux périmés en avertissement, téléchargements éditeur pour ChatGPT/Proton, CLI natives avant npm, protection du remplacement de paquets) sont décrites dans [CHANGELOG.md](CHANGELOG.md).

**Vérité de l'éditeur (depuis v1.5.0) :** la version de chaque application est comparée au flux de son propre éditeur avant toute exécution. Les applications à jour ne sont pas modifiées ; les applications obsolètes sont mises à jour par leur propre programme de mise à jour, ou installées depuis l'éditeur avec vérification de la signature et du Team ID. Seuls les logiciels installés sont mis à jour (`--bootstrap-cli` installe volontairement les CLI manquantes). Les applications supprimées manuellement sont détectées et jamais réinstallées. **Les applications que vous avez ouvertes ne sont jamais fermées : l'outil ne quitte que ce qu'il a lancé lui-même.** Vérifiez l'état des éditeurs en lecture seule avec `bash scripts/check_vendor_feeds.sh`.

---

## Installation en une ligne (nouveaux utilisateurs)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

L'installateur clone le dépôt, demande la **langue** (menu en anglais, 7 langues), installe les dépendances, génère **votre** fichier `APPLICATIONS.md` à partir des applications déjà présentes sur ce Mac et indique celles que le projet peut mettre à jour. Il n'importe jamais l'inventaire d'une autre personne et n'installe pas d'applications à votre place.

Voir [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md)

---

## Ce que fait cet outil

`update_all.sh` exécute sept étapes :

| Étape | Action |
|-------|--------|
| 0 | **Pré-analyse** — détecte les applications installées → met à jour `APPLICATIONS.md` |
| 1 | **App Store** — Piste 1 : `sudo mas upgrade <app-id>` ; Piste 2 : GUI AppleScript pour les apps iPad |
| 2 | **CLI natives + npm** — d'abord les CLI natives existantes, puis Node, Bun et les CLI npm globales |
| 3 | **Homebrew** — formules et casks (`brew_cask` + protection contre la rétrogradation) + nettoyage et contrôle de santé |
| 4 | **Applications Internet** — gestionnaires directs vérifiés, `sparkle_appcast`, CLI d'éditeurs et déclenchements honnêtes des programmes de mise à jour |
| 5 | **Post-mise à jour/historique** — actualise `APPLICATIONS.md`, ajoute à `UPDATES.md` de façon atomique |
| 6 | **macOS (final)** — par étiquette `softwareupdate -i <label> -R` (étiquettes nécessitant un redémarrage dans le lot final) ; différé après un échec bloquant dur aux étapes 1–4 ou sans autorisation |

**Important :** Les mises à jour ne touchent que les logiciels déjà installés sur votre Mac. Les applications prises en charge mais absentes sont signalées, pas installées. L'étape finale macOS peut redémarrer le Mac ; elle passe donc en dernier et conserve l'option obligatoire `-R`. L'étape 5 ne sert qu'au rapport : son échec est une erreur mais ne diffère jamais l'étape macOS. Les applications installées inconnues sont listées pour que vous (ou un agent IA) puissiez ajouter des gestionnaires.

La couverture est volontairement explicite : **verified direct** signifie que le programme a confirmé le chemin paquet/version ; **triggered-unverified**, qu'une application a été lancée pour laisser son programme de mise à jour agir sans qu'on puisse prouver l'achèvement ; **externally managed**, que l'éditeur ou l'App Store gère le cycle de mise à jour ; **manual** exige une action de l'utilisateur ; **unknown** n'a aucune méthode enregistrée.

```bash
bash scripts/report_update_coverage.sh   # rapport de couverture
bash build_inventory.sh                  # reconstruit APPLICATIONS.md depuis ce Mac
```

### Méthodes de mise à jour

Le registre ([`config/internet_apps.txt`](config/internet_apps.txt), [`config/internet_app_methods.txt`](config/internet_app_methods.txt)) associe 43 applications à 11 méthodes :

| Méthode | Apps | Couverture | Fonctionnement |
|---------|-----:|------------|----------------|
| `brew_cask` | 11 | externally managed | Cask Homebrew (greedy uniquement pour ces jetons) avec protection contre la rétrogradation, p. ex. Brave, Obsidian, Spotify, Inkscape |
| `silent_launch` | 9 | triggered-unverified | Le programme de mise à jour propre à l'app ; vérification opportuniste auprès d'un flux Sparkle / electron-updater, sinon « lancé (non vérifié) ». Ne remplace jamais l'app elle-même |
| `github_dmg` | 6 | verified direct | DMG de l'éditeur/GitHub avec vérification de la signature et du Team ID, remplacement par étapes avec retour arrière (Firefox Developer Edition, KeePassXC, VS Code, CodeEdit, Ledger Live, Trezor Suite) |
| `msupdate` | 5 | verified direct | Microsoft AutoUpdate (`msupdate`) : Word, Excel, PowerPoint, Outlook, OneNote |
| `keystone` | 3 | verified direct | Programme de mise à jour Google (Omaha), contrôlé via son historique : Chrome, Gemini, Google Drive |
| `appstore_gui` | 3 | externally managed | App Store Piste 2 (AppleScript) : UniFi, WiFiman, Picsart |
| `sparkle_appcast` | 1 | verified direct | Appcast Sparkle (Proton Drive) |
| `chromium_updater` | 1 | verified direct | Preuve du programme de mise à jour basé sur Chromium (Comet) |
| `docker_cli` | 1 | verified direct | Docker Desktop : DMG vérifié depuis son appcast quand l'app est inactive ; repli `docker desktop update` |
| `mau_fallback_self_update` | 1 | triggered-unverified | Mise à jour propre à Teams plus repli MAU `TEAMS21` observé et vérifié quand Microsoft le propose |
| `manual` | 2 | manual | IPMIView et DJI Assistant 2 : notification uniquement |

---

## Options de la ligne de commande

`lib/cli.sh` fait foi ; `bash update_all.sh --help` l'affiche.

| Option | Effet |
|--------|-------|
| `-y`, `--yes` | Ignore la demande de confirmation |
| `-h`, `--help` | Affiche l'aide et termine avec le code `0` |
| `--dry-run` | Prévisualise chaque étape, ne modifie rien et ne demande jamais d'identifiants |
| `--verify-only` | Vérifie les versions installées par rapport à l'historique sans rien modifier |
| `--json-summary` | Affiche un objet JSON de résultat sur stdout après l'exécution |
| `--bootstrap-cli` | Installe explicitement les CLI manquantes (par défaut, seules les CLI installées sont mises à jour) |
| `--non-interactive` | Mode non interactif pour launchd / cron (implique aussi `-y`) |
| `--notify` | Envoie une notification macOS à la fin |
| `--treat-appstore-ax-as-warning` | Traite la sortie `2` de l'App Store (Accessibilité manquante) comme un avertissement |
| `--skip-prescan` | Ignore l'étape 0 (pré-analyse de `APPLICATIONS.md`) |
| `--skip-appstore` | Ignore l'étape 1 (App Store) |
| `--skip-npm` | Ignore l'étape 2 (CLI natives + npm) |
| `--skip-brew` | Ignore l'étape 3 (Homebrew) |
| `--skip-internet` | Ignore l'étape 4 (applications Internet) |
| `--skip-postupdate` | Ignore l'étape 5 (historique `APPLICATIONS.md` / `UPDATES.md`) |
| `--skip-system` | Ignore l'étape 6 (mise à jour de macOS) |
| `--skip-doctor` | Ignore `brew doctor` dans `update_brew.sh` |

Une option `-…` inconnue termine avec le code `2` après affichage de l'aide.

## Variables d'environnement

Chaque option a une variable équivalente (`MAC_UPDATE_DRY_RUN=1`, `MAC_UPDATE_SKIP_SYSTEM=1`, …) ; voici les plus courantes qui n'ont pas d'option. La liste complète avec les valeurs par défaut se trouve dans [docs/agents/scripts.md](docs/agents/scripts.md#environment-variables).

| Variable | Défaut | Signification |
|----------|--------|---------------|
| `MAC_UPDATE_NONINTERACTIVE` | `0` | Ne pose jamais de question ; ignore l'automatisation GUI de la Piste 2 de l'App Store |
| `MAC_UPDATE_NOTIFY` | `0` | Notification de bureau à la fin (aussi implicite en mode non interactif) |
| `MAC_UPDATE_NO_SUDO` | *définie automatiquement* | Exportée par `update_all.sh` sans TTY ; les scripts enfants ignorent alors les pistes root au lieu d'échouer |
| `MAC_UPDATE_NO_SUDO_KEEPALIVE` | `0` | `1` désactive le rafraîchissement en arrière-plan de l'horodatage `sudo` |
| `MAC_UPDATE_STALE_DAYS` | `45` | Nombre de jours après lesquels une app non vérifiée est signalée comme périmée |
| `MAC_UPDATE_MAX_LOGS` | `30` | Journaux d'exécution conservés dans `logs/` |
| `MAC_UPDATE_INTERNET_SETTLE_SECONDS` | `15` | Pause laissant un programme de mise à jour lancé réécrire `Info.plist` (`0` la désactive, plafonnée à 120 ; ignorée si aucune app n'a été lancée) |
| `MAC_UPDATE_QUIT_WAIT` | `60` | Secondes (0–300) dont dispose une app lancée par l'outil pour se fermer après le `quit` doux ; jamais forcée (v1.5.5) |
| `MAC_UPDATE_QUIT_RESEND` | `10` | Secondes (1–60) entre deux demandes `quit` douces dans la fenêtre d'attente (v1.5.5) |
| `MAC_UPDATE_MAS_CHECK_TIMEOUT` | `120` | Délai maximal de `mas outdated` |
| `MAC_UPDATE_MAS_UPGRADE_TIMEOUT` | `1800` | Délai maximal de `sudo mas upgrade` |
| `MAC_UPDATE_MAU_DEFERRAL_DAYS` | `7` | Fenêtre de quarantaine de Microsoft AutoUpdate (bornée à 1–28 selon Microsoft) |
| `MAC_UPDATE_MAU_CLEAR_DEFERRALS` | `0` | `1` supprime via `defaults delete` les clés de report MAU qui bloquent |
| `MAC_UPDATE_MAU_KEEP_DEFERRALS` | `0` | `1` : l'outil ne touche jamais aux préférences de report de MAU |
| `MAC_UPDATE_LANG` / `MAC_LANG` | depuis `.mac_update_prefs` | Langue de l'interface (`en pl es it pt de fr`) |

## sudo et Touch ID — le contrat

Réécrit en v1.3.1 / v1.4.0. `update_all.sh` n'a **qu'un seul** point d'appel interactif
à `sudo`, soumis à trois conditions :

1. **Au plus une fois par exécution.** Un unique `sudo -v` avant la redirection du
   journal, puis un processus d'arrière-plan rafraîchit l'horodatage toutes les
   50 s : une longue exécution ne redemande jamais rien. Le keep-alive démarre au
   plus une fois et le piège de nettoyage l'arrête sur toute sortie, y compris
   `INT`/`TERM` : il ne peut plus rester orphelin.
2. **Jamais sans TTY de contrôle.** Si stdin n'est pas un terminal (exécuteur de
   tâches d'IDE, shell d'agent, launchd, cron), l'outil n'appelle **pas** `sudo -v`.
   Un `sudo -v` sans TTY bascule vers la boîte de dialogue graphique askpass /
   Touch ID, ce qui donnait l'impression que chaque commande exigeait une
   élévation. À la place, `MAC_UPDATE_NO_SUDO=1` est exportée, les étapes root
   sont ignorées et l'exécution signale un avertissement doux.
3. **Jamais pendant `--dry-run`.** Une prévisualisation ne doit pas demander
   d'identifiants.

`sudo` n'est pas non plus demandé quand ni l'étape 1 (App Store) ni l'étape 6
(macOS) ne vont s'exécuter, p. ex. `bash update_all.sh --skip-appstore --skip-system`.

---

## Configuration par machine (**n'arrive pas** avec `git pull`)

Deux éléments vivent hors du dépôt et doivent donc être configurés une fois **sur
chaque Mac**. Cloner ou tirer le dépôt sur une seconde machine ne les transporte
pas : c'est la source de confusion la plus fréquente de ce projet.

| Étape | Commande | Pourquoi ce n'est pas dans Git |
|-------|----------|--------------------------------|
| Touch ID pour `sudo` | `bash scripts/setup_touchid_sudo.sh` | Écrit `/etc/pam.d/sudo_local` : fichier appartenant à root, local à la machine, hors du dépôt |
| Exécution hebdomadaire en arrière-plan | `bash scripts/install_launchagent.sh --day 1 --hour 9` | Écrit `~/Library/LaunchAgents/com.<user>.macos-updates.plist` : par utilisateur et par machine |

```bash
bash scripts/setup_touchid_sudo.sh --check      # rapport seul, n'écrit rien
bash scripts/setup_touchid_sudo.sh              # installer / réparer
bash scripts/setup_touchid_sudo.sh --uninstall

bash scripts/install_launchagent.sh --check
bash scripts/install_launchagent.sh --uninstall
```

`setup_touchid_sudo.sh` ne touche jamais `/etc/sudoers` et n'accorde jamais de
`sudo` sans mot de passe. Sous macOS 14+, il utilise `/etc/pam.d/sudo_local`, qui
survit aux mises à jour du système ; sous macOS 13, il modifie `/etc/pam.d/sudo`,
que les mises à jour de macOS effacent : relancez-le après une mise à jour majeure.

### Ce que l'exécution planifiée en arrière-plan fait et ne fait pas

Le LaunchAgent lance `update_all.sh -y --skip-system` avec
`MAC_UPDATE_NONINTERACTIVE=1` et `MAC_UPDATE_NOTIFY=1`.

- **Exécute :** Homebrew, CLI natives + npm, applications Internet, inventaire/historique.
- **N'exécute pas les mises à jour de macOS** : `--skip-system` est voulu. Sur
  Apple Silicon, `softwareupdate` exige les **identifiants du propriétaire du
  volume**, impossibles à fournir depuis une tâche launchd non surveillée, et
  l'étape peut redémarrer le Mac.
- **N'exécute pas les mises à jour de l'App Store** : `sudo mas upgrade` demande un
  mot de passe et la Piste 2 AppleScript pilote l'interface de l'App Store. Les
  deux sont ignorées dans une session sans TTY et signalées comme avertissement
  doux (code `10`), jamais comme un échec.

Les deux restent donc interactives, volontairement. Lancez `bash update_all.sh`
vous-même quand vous voulez appliquer les mises à jour de l'App Store et de macOS.

---

## Prérequis

| Outil | Installé automatiquement ? |
|-------|----------------------------|
| Mac Apple Silicon (arm64) | — |
| macOS 13 Ventura ou plus récent (testé jusqu'à macOS 27) | — |
| Xcode Command Line Tools | ✅ `setup.sh` / `install.sh` |
| Homebrew | ✅ |
| `mas` (CLI de l'App Store) | ✅ |
| Python 3 | ✅ via Homebrew s'il manque |
| `rclone` (facultatif) | ✅ s'il est choisi comme fournisseur cloud |

Les Mac Intel et macOS 12 ou antérieur ne sont pas pris en charge ; les scripts s'arrêtent avant toute modification.

---

## Démarrage rapide

### Nouvel utilisateur (sans cloud)

```bash
# Option A — une ligne (recommandé)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"

# Option B — manuel
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh
bash build_inventory.sh
bash update_all.sh
```

### Propriétaire (GitHub + surcouche cloud)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

---

## Structure du projet

```
macOS_updates/
├── VERSION                     # Version du paquet (source de vérité unique)
├── install.sh                  # Installateur en une ligne
├── uninstall.sh                # Supprime le clone (conserve Homebrew et les apps)
├── setup.sh                    # Configuration initiale (sans cloud)
├── migration_setup.sh          # Configuration complète + assistant cloud
├── build_inventory.sh          # Génère APPLICATIONS.md pour ce Mac
├── update_all.sh               # Orchestrateur principal
├── update_*.sh                 # Étapes de mise à jour individuelles
├── run_tests.sh                # Syntaxe + Python + unittest + analyse de secrets
│
├── dev_sync/                   # Synchronisation de la surcouche privée (cloud)
│   ├── provider_setup.sh
│   ├── dev-sync-export.sh      # (+ import, verify, prune, …)
│   └── dev_sync_*.py           # Backend Python
├── dev-sync-*.sh               # Enveloppes à la racine (compatibilité)
│
├── config/                     # Registre des applications Internet (public)
│   ├── internet_apps.txt
│   ├── internet_app_methods.txt
│   └── internet_dispatch_order.txt
│
├── lib/                        # Bibliothèques Bash partagées (+ lib/python/)
├── i18n/                       # Textes d'interface en 7 langues
├── scripts/                    # Utilitaires (rapport de couverture, flux éditeurs, générateur, …)
├── templates/                  # APPLICATIONS.md.template (référence)
├── tests/                      # unittest + contrôles statiques de sécurité
├── docs/
│   ├── INSTALL.md · UNINSTALL.md · PUBLIC_RELEASE.md
│   ├── user/                   # Guides utilisateur (7 langues)
│   ├── agents/                 # Référence pour développeurs / agents IA
│   ├── reviews/                # Index + notes de développement actuelles (archive/ = historique)
│   └── archive/                # Plans d'implémentation dépassés
│
├── CHANGELOG.md · CONTRIBUTING.md · SECURITY.md · LICENSE
└── AGENTS.md · CLAUDE.md · GEMINI.md · CODEX.md
```

**Fichiers privés (ignorés par git, locaux ou dans le cloud uniquement) :** `APPLICATIONS.md`, `UPDATES.md`, `.dev_sync_config.json`, `.mac_update_prefs`, `.env`, `logs/`

### Scripts individuels

| Script | Rôle |
|--------|------|
| `install.sh` | Clone + configure + crée l'inventaire pour les nouveaux utilisateurs |
| `setup.sh` | Dépendances et autorisations (sans cloud) |
| `migration_setup.sh` | Migration complète + cloud + analyse des apps |
| `build_inventory.sh` | Analyse en lecture seule → met à jour `APPLICATIONS.md` de façon atomique sans historique de mises à jour |
| `update_all.sh` | Toutes les étapes de mise à jour + journalisation |
| `update_system.sh` … `update_brew.sh` | Mises à jour d'une seule couche |
| `uninstall.sh` | Supprime le répertoire de l'outil |
| `run_tests.sh` | Syntaxe + Python + unittest + analyse de secrets |

Référence complète des scripts : [docs/agents/scripts.md](docs/agents/scripts.md).

---

## Ajouter la prise en charge d'une nouvelle application

1. Installez l'application vous-même (l'outil ne l'installe jamais à votre place).
2. Lancez `bash build_inventory.sh` pour l'ajouter à `APPLICATIONS.md`.
3. Pour la mise à jour automatique, demandez à un agent IA ou suivez [docs/user/fr/GUIDE.md](docs/user/fr/GUIDE.md) :

```bash
bash scripts/scaffold_internet_app.sh "Nom de l'app" silent_launch
bash run_tests.sh
```

Les méthodes du registre correspondent aux états de couverture ci-dessus. Par exemple, `github_dmg` et une CLI d'éditeur confirmée sont **verified direct** ; `silent_launch` est **triggered-unverified** ; les flux gérés par l'App Store ou l'éditeur peuvent être **externally managed** ; `manual` et les entrées absentes du registre restent explicites.

---

## Synchronisation cloud (`dev_sync`)

| GitHub (public) | Cloud (privé) |
|-----------------|---------------|
| Scripts, `config/`, `docs/`, tests | `APPLICATIONS.md`, `UPDATES.md`, `.env`, `.dev_sync_config.json` |

```bash
bash dev_sync/provider_setup.sh
bash dev_sync/dev-sync-export.sh
bash dev_sync/dev-sync-import.sh
bash dev_sync/dev-sync-verify-full.sh
```

Les enveloppes `dev-sync-*.sh` de la racine appellent les mêmes scripts de `dev_sync/`.

---

## Tests

La suite couvre la syntaxe bash, la compilation Python, les contrats statiques de sécurité, les garde-fous de documentation et les tests unitaires (590 tests automatisés).
Les pull requests exécutent ShellCheck sur Ubuntu, des tests Python portables et l'analyse de secrets.
La suite complète `run_tests.sh` sur un runner macOS ne s'exécute que via `workflow_dispatch` ou une étiquette `v*`, pas à chaque push.

```bash
bash run_tests.sh
bash update_all.sh --dry-run -y
```

---

## Notes techniques critiques

- **`softwareupdate` doit utiliser `-R`** : sinon les mises à jour sont téléchargées mais jamais appliquées.
- **`mas upgrade` doit utiliser `sudo` et des identifiants d'app explicites** sous macOS 14.8.2+/15.7.2+/26.1+ (changement d'autorisations, voir https://github.com/orgs/Homebrew/discussions/6550).
- **Bash 3.2+** partout : pas de `declare -A`, `mapfile` ni `readarray`.
- Les applications téléchargées sont vérifiées, installées par un remplacement par étapes avec retour arrière, et leurs DMG sont montés sur des points de montage uniques par session.
- L'écriture de l'inventaire/historique privés et les imports cloud sont atomiques ; les imports préparent les fichiers acceptés avant de les valider.

---

## Documentation

| Public | Point de départ |
|--------|-----------------|
| Utilisateurs | [docs/user/INDEX.md](docs/user/INDEX.md) (démarrage rapide, guide et manuel d'exploitation en 7 langues) · [démarrage rapide en français](docs/user/fr/QUICK_START.md) |
| Installation / désinstallation | [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md) |
| GitHub public et surcouche privée | [docs/PUBLIC_RELEASE.md](docs/PUBLIC_RELEASE.md) · [dev_sync/README.md](dev_sync/README.md) |
| Développeurs / agents | [docs/agents/scripts.md](docs/agents/scripts.md) · [règles critiques](docs/agents/critical_rules.md) · [codes de sortie](docs/agents/exit_codes.md) · [dépannage](docs/agents/troubleshooting.md) · [liste d'acceptation](docs/agents/acceptance_checklist.md) |
| Contexte des agents IA | [AGENTS.md](AGENTS.md) (contrat commun) · [CLAUDE.md](CLAUDE.md) · [GEMINI.md](GEMINI.md) · [CODEX.md](CODEX.md) |
| Historique des versions | [CHANGELOG.md](CHANGELOG.md) · [index des notes de développement](docs/reviews/README.md) |
| Contribuer / sécurité | [CONTRIBUTING.md](CONTRIBUTING.md) · [SECURITY.md](SECURITY.md) |

---

## Dépannage

| Problème | Solution |
|----------|----------|
| Nouveau Mac | `install.sh` ou `setup.sh` + `build_inventory.sh` |
| Mauvaise liste d'apps | `build_inventory.sh` : ne copiez jamais le `APPLICATIONS.md` d'une autre personne |
| Une app ne se met pas à jour seule | `scripts/report_update_coverage.sh` → ajoutez un gestionnaire selon le guide |
| `APPLICATIONS.md` manquant | `build_inventory.sh` ou `dev_sync/dev-sync-import.sh` (propriétaire) |
| `mas upgrade` échoue | `sudo mas upgrade <app-id>` |
| Cloud non configuré | `bash dev_sync/provider_setup.sh` |

Liste complète : [docs/agents/troubleshooting.md](docs/agents/troubleshooting.md)

---

## Licence

[MIT](LICENSE) © macOS Updates contributors
