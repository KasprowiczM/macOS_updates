# macOS Updates

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

**Site web :** [macos-updates.64bit.site](https://macos-updates.64bit.site) · **Dépôt :** [github.com/KasprowiczM/macOS_updates](https://github.com/KasprowiczM/macOS_updates) · **Licence :** [MIT](LICENSE) · **Changements :** [CHANGELOG.md](CHANGELOG.md)

> **v1.7.7** : Orchestrateur de mises à jour en une seule commande, pour les **Mac Apple Silicon sous macOS 13-27**. Il coordonne des mises à jour de paquets vérifiées et des déclenchements honnêtes des programmes de mise à jour des applications, pour les **logiciels déjà installés sur ce Mac**. **Multilingue** (7 langues). Surcouche privée facultative via [`dev_sync/`](dev_sync/README.md).

| En un coup d'œil | |
|------------------|--|
| Plateforme | Apple Silicon (arm64) uniquement · de macOS 13 Ventura à macOS 27 · Bash 3.2 + Python 3 |
| Pipeline | 7 étapes (0–6), la mise à jour de macOS vient toujours en dernier |
| Registre | 47 applications Internet · 11 méthodes de mise à jour (voir [Méthodes de mise à jour](#méthodes-de-mise-à-jour)) |
| Langues | EN, PL, ES, FR, DE, IT, PT (CLI et documentation) |
| Tests | 1350 tests automatisés (`bash run_tests.sh`) |

L’étape C active l’inventaire JSON local et les plans avec autorisations précises. `bash update_all.sh --plan` et `--dry-run` affichent les mêmes décisions sans écriture. Un lancement interactif demande une fois les portées affichées ; `-y`, EOF et les lancements sans terminal ne donnent aucune nouvelle autorisation. Utilisez `--preferences` pour revoir ou réinitialiser les choix. Les mises à jour conservent la source et la destination observées ; conflits, cibles absentes et preuves incertaines reportent cette cible. `build_inventory.sh --migration --preview` conserve les octets Markdown originaux et les notes ; acceptez explicitement l’identifiant affiché. Les mises à jour génériques restent manuelles jusqu’à la vérification de l’identité et de l’adaptateur. Une entrée de catalogue ne prouve ni installation ni consentement.

Cette documentation décrit macOS Updates 1.7.7. Aucun tag de publication distinct n’a été créé. Le gestionnaire agit uniquement sur les cibles installées dont la source est observée et après une nouvelle autorisation. Les adaptateurs génériques natifs et éditeur restent manuels en attendant des recettes vérifiées. Le catalogue public facultatif couvre 48 produits et propose des liens officiels vérifiés pour une acquisition manuelle ; aucune recette de première installation automatique n’est approuvée. La liste des méthodes ci-dessous décrit des capacités, pas une autorisation d’exécution.

**Nouveautés de la v1.6.0 :** Les exécutions planifiées (launchd) trouvent Homebrew et `mas`, et l'installateur vérifie que la tâche est chargée (ajout de `--minute` et `--once-in`). Les apps ouvertes ne sont jamais fermées ni remplacées, casks Homebrew compris. Chaque question en cours d'exécution expire avec la réponse sûre « non ». `bash update_all.sh --doctor` est un rapport de préparation en lecture seule, et les exécutions réelles ajoutent des contrôles préalables. L'état persistant des flux éditeur remplace les avertissements opaques de « flux obsolète », et HyperFrames, Superset et Open Design sont installés ou vérifiés sans lancement caché. Les versions 1.5.x antérieures sont décrites dans [CHANGELOG.md](CHANGELOG.md).

Les anciens rapports de flux éditeur sont en lecture seule. Le gestionnaire actuel laisse les adaptateurs natifs et éditeur génériques en mode manuel jusqu’à disponibilité d’une recette vérifiée. L’ancienne option `--bootstrap-cli` n’autorise aucune première installation. Installez les CLI manquantes séparément selon les instructions officielles vérifiées. Les apps ouvertes ne sont pas fermées. Consultez les flux avec `bash scripts/check_vendor_feeds.sh`.

## Configuration sûre et sources des applications

`bash setup.sh --inspect` vérifie la disponibilité sans installation, modification du profil shell ni configuration Touch ID. Un outil absent rend sa fonction indisponible. Dans un terminal, `bash setup.sh --install-dependencies` présente les dépendances facultatives et demande avant chaque installation ; `bash setup.sh --configure-shell` présente séparément la modification du profil. Refuser une dépendance ne bloque pas les fonctions indépendantes. Sans Python, installez-le explicitement avant de construire l’inventaire. Un `mas` absent ou ancien est signalé, jamais installé ni mis à niveau automatiquement.

Le rapport normal porte sur les applications installées. `bash scripts/report_update_coverage.sh --show-supported` reste une liste de référence. Le menu facultatif s’ouvre avec `bash setup.sh --catalog`, sans sélection initiale. Après aperçu et nouvelle autorisation, une app peut être acquise manuellement via un lien officiel vérifié. Changer la source d’une app existante exige une migration manuelle. Un reçu App Store pour CapCut conserve cette source. Une app locale sans propriété Homebrew confirmée n’est jamais adoptée automatiquement.

La recherche latest stable figure dans [SOURCE_RESEARCH.md](docs/catalog/SOURCE_RESEARCH.md). Les éditions différentes ne sont pas comparables ; une observation ponctuelle ne prouve pas quel canal est habituellement le plus rapide.

---

## Installation en une ligne (nouveaux utilisateurs)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

L’installateur clone le dépôt, demande la langue, vérifie la disponibilité et construit l’inventaire de ce Mac si Python est disponible. Les dépendances nécessitent un choix séparé dans setup. Touch ID et les profils shell ne sont pas modifiés automatiquement.

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

**Important :** Les mises à jour normales ne concernent que les logiciels installés dont la source est observée et dont le périmètre d’action est autorisé. Le catalogue facultatif séparé peut afficher des apps absentes, mais ne les installe pas automatiquement. L’acquisition manuelle exige un aperçu et une nouvelle autorisation. L’étape macOS finale peut redémarrer le Mac ; elle passe en dernier avec l’option obligatoire `-R`. L’étape 5 sert uniquement au rapport. Les apps inconnues sont listées pour examen.

La couverture est volontairement explicite : **verified direct** signifie que le programme a confirmé le chemin paquet/version ; **triggered-unverified**, qu'une application a été lancée pour laisser son programme de mise à jour agir sans qu'on puisse prouver l'achèvement ; **externally managed**, que l'éditeur ou l'App Store gère le cycle de mise à jour ; **manual** exige une action de l'utilisateur ; **unknown** n'a aucune méthode enregistrée.

```bash
bash scripts/report_update_coverage.sh   # rapport de couverture
bash build_inventory.sh                  # reconstruit APPLICATIONS.md depuis ce Mac
```

### Méthodes de mise à jour
Le tableau des méthodes est une ancienne référence de capacités. Il décrit les méthodes enregistrées sans autoriser leur exécution ; le gestionnaire exige une source observée et une nouvelle autorisation.

Le registre ([`config/internet_apps.txt`](config/internet_apps.txt), [`config/internet_app_methods.txt`](config/internet_app_methods.txt)) associe 47 applications à 11 méthodes :

| Méthode | Apps | Couverture | Fonctionnement |
|---------|-----:|------------|----------------|
| `brew_cask` | 11 | externally managed | Cask Homebrew (greedy uniquement pour ces jetons) avec protection contre la rétrogradation, p. ex. Brave, Obsidian, Spotify, Inkscape |
| `silent_launch` | 14 | triggered-unverified | Le programme de mise à jour propre à l'app en repli ; vérification opportuniste contre un flux Sparkle / electron-updater, sinon « lancée (non vérifiée) ». Les apps dotées d'un flux éditeur (ChatGPT / Codex, Claude, Cursor, Warp, OpenCode, Proton Mail, ...) sont décidées par ce flux et, si elles sont en retard, installées depuis l'artefact éditeur vérifié. Sans flux, la méthode ne remplace jamais l'app elle-même |
| `github_dmg` | 5 | verified direct | DMG de l'éditeur/GitHub avec vérification de la signature et du Team ID, remplacement par étapes avec retour arrière (KeePassXC, VS Code, CodeEdit, Ledger Live, Trezor Suite) |
| `msupdate` | 5 | verified direct | Microsoft AutoUpdate (`msupdate`) : Word, Excel, PowerPoint, Outlook, OneNote |
| `keystone` | 3 | verified direct | Programme de mise à jour Google (Omaha), contrôlé via son historique : Chrome, Gemini, Google Drive |
| `appstore_gui` | 4 | externally managed | App Store Piste 2 (AppleScript) : UniFi, WiFiman, Picsart, IPMIView |
| `sparkle_appcast` | 1 | verified direct | Appcast Sparkle (Proton Drive) |
| `chromium_updater` | 1 | verified direct | Preuve du programme de mise à jour basé sur Chromium (Comet) |
| `docker_cli` | 1 | verified direct | Docker Desktop : DMG vérifié depuis son appcast quand l'app est inactive ; repli `docker desktop update` |
| `mau_fallback_self_update` | 1 | triggered-unverified | Mise à jour propre à Teams plus repli MAU `TEAMS21` observé et vérifié quand Microsoft le propose |
| `mozilla_dmg` | 1 | verified direct | Version product-details de Mozilla plus DMG vérifié, remplacement par étapes avec rollback (Firefox Developer Edition) |

---

## Options de la ligne de commande

`lib/cli.sh` fait foi ; `bash update_all.sh --help` l'affiche.

| Option | Effet |
|--------|-------|
| `-y`, `--yes` | Ignore la demande de confirmation |
| `-h`, `--help` | Affiche l'aide et termine avec le code `0` |
| `--doctor` | Rapport de préparation en lecture seule (plateforme, outils, `PATH` launchd, LaunchAgent, sudo, disque, alimentation, réseau, dernière exécution) ; pas de demande sudo, pas de journal d'exécution ; sortie `0` ok / `10` avertissements / `1` problème |
| `--dry-run` | Prévisualise chaque étape, ne modifie rien et ne demande jamais d'identifiants |
| `--verify-only` | Vérifie les versions installées par rapport à l'historique sans rien modifier |
| `--json-summary` | Affiche un objet JSON de résultat sur stdout après l'exécution |
| `--bootstrap-cli` | L’ancienne option CLI n’autorise aucune première installation. Installez les CLI manquantes séparément selon les instructions officielles vérifiées. |
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

**Contrôle préalable (exécutions réelles uniquement) :** avant l'étape 0, l'exécution vérifie l'espace disque libre, la batterie et le réseau. Un espace faible dégrade l'exécution, une batterie faible ignore seulement l'étape macOS (en douceur), et l'absence d'hôte joignable met fin à l'exécution avec le code `1` avant toute étape. Le Mac reste éveillé grâce à `caffeinate` pendant l'exécution (`MAC_UPDATE_NO_CAFFEINATE=1` désactive cela). Lancez `bash update_all.sh --doctor` pour voir les mêmes contrôles sans rien exécuter.

**Questions :** chaque question posée pendant l'exécution expire après `MAC_UPDATE_PROMPT_TIMEOUT` secondes avec la réponse sûre « non » ; une saisie non reconnue vaut aussi « non ». Après la confirmation générale, les étapes Homebrew et App Store ne redemandent pas ; l'étape macOS demande toujours.

**Applications ouvertes :** un cask Homebrew dont l'application est ouverte n'est jamais mis à jour ; il est reporté avec le message « quittez l'application » et l'étape se termine par un avertissement léger (code `10`).

**Apps direct-only et never-launch :** `config/vendor_launch_policy.txt` liste les apps que l'outil ne lance jamais. Une app `direct-only` (HyperFrames, Superset) n'est mise à jour que depuis son artefact éditeur vérifié ; une app `never-launch` (Open Design) est seulement vérifiée et, si elle est en retard, signalée « ouvrez l'app pour la mettre à jour ». Aucune n'est ouverte ni quittée, pas même en repli après un flux injoignable.

## Variables d'environnement

Chaque option a une variable équivalente (`MAC_UPDATE_DRY_RUN=1`, `MAC_UPDATE_SKIP_SYSTEM=1`, …) ; voici les plus courantes qui n'ont pas d'option. La liste complète avec les valeurs par défaut se trouve dans [docs/agents/scripts.md](docs/agents/scripts.md#environment-variables).

| Variable | Défaut | Signification |
|----------|--------|---------------|
| `MAC_UPDATE_NONINTERACTIVE` | `0` | Ne pose jamais de question ; ignore l'automatisation GUI de la Piste 2 de l'App Store |
| `MAC_UPDATE_NOTIFY` | `0` | Notification de bureau à la fin (aussi implicite en mode non interactif) |
| `MAC_UPDATE_NO_SUDO` | *définie automatiquement* | Exportée par `update_all.sh` sans TTY ; les scripts enfants ignorent alors les pistes root au lieu d'échouer |
| `MAC_UPDATE_NO_SUDO_KEEPALIVE` | `0` | `1` désactive le rafraîchissement en arrière-plan de l'horodatage `sudo` |
| `MAC_UPDATE_STALE_DAYS` | `45` | Nombre de jours après lesquels une app non vérifiée est signalée comme périmée |
| `MAC_UPDATE_MAX_LOGS` | `30` | Journaux d'exécution conservés dans `logs/` (les résumés d'exécution sont aussi rotés) |
| `MAC_UPDATE_PROMPT_TIMEOUT` | `120` | Secondes (10–900, `0` = attendre indéfiniment) pendant lesquelles une question oui/non en cours d'exécution attend ; l'expiration vaut « non » |
| `MAC_UPDATE_MIN_FREE_GB` | `15` | Contrôle préalable : un espace disque libre inférieur à cette valeur dégrade l'exécution |
| `MAC_UPDATE_MIN_BATTERY` | `30` | Contrôle préalable : sur batterie, en dessous de ce pourcentage, seule l'étape macOS est ignorée |
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
bash scripts/install_launchagent.sh --once-in 5
bash scripts/install_launchagent.sh --uninstall
```

`setup_touchid_sudo.sh` ne touche jamais `/etc/sudoers` et n'accorde jamais de
`sudo` sans mot de passe. Sous macOS 14+, il utilise `/etc/pam.d/sudo_local`, qui
survit aux mises à jour du système ; sous macOS 13, il modifie `/etc/pam.d/sudo`,
que les mises à jour de macOS effacent : relancez-le après une mise à jour majeure.

### Ce que l'exécution planifiée en arrière-plan fait et ne fait pas

Le LaunchAgent lance `update_all.sh -y --skip-system` avec
`MAC_UPDATE_NONINTERACTIVE=1` et `MAC_UPDATE_NOTIFY=1`.

Le plist définit un `PATH` explicite (`/opt/homebrew/bin:/opt/homebrew/sbin:/usr/bin:/bin:/usr/sbin:/sbin`) car celui de launchd n'inclut pas Homebrew, et l'installateur vérifie avec `launchctl print` que la tâche est chargée ; sinon il affiche l'erreur de launchctl et se termine avec un code non nul. `--minute N` (0-59) fixe la minute, `--once-in N` (1-1440 minutes à partir de maintenant) installe une exécution de test unique et ne se combine pas avec `--day`/`--hour`/`--minute`, et `--check` signale un plist sans clé `PATH` (relancez l'installateur pour réparer une ancienne installation).

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
| Xcode Command Line Tools | Installation manuelle |
| Homebrew | Installation manuelle: https://brew.sh |
| `mas` (CLI de l'App Store) | ✅ |
| Python 3.9+ | Consentement explicite : `setup.sh --install-dependencies` |
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
bash setup.sh --inspect
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
3. Pour examiner la prise en charge, suivez [docs/user/fr/GUIDE.md](docs/user/fr/GUIDE.md) ou consultez un agent IA :

```bash
bash scripts/scaffold_internet_app.sh "/path/to/Observed.app" --json
bash run_tests.sh
```

Remplacez l’exemple par le chemin exact de l’application installée. La commande affiche une proposition expurgée et non exécutable à examiner. L’export facultatif exige de répéter la commande avec `--export --accept PREVIEW_ID` après examen de l’identifiant affiché. L’activation des mises à jour exige une implémentation revue et des preuves d’acceptation distinctes.

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

La suite couvre la syntaxe bash, la compilation Python, les contrats statiques de sécurité, les garde-fous de documentation et les tests unitaires (591 tests automatisés).
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
| Historique des versions | [CHANGELOG.md](CHANGELOG.md) |
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


## Catalogue facultatif et première installation

Les nouveaux signaux d’applications sont des propositions à examiner, pas des recettes exécutables. `bash scripts/scan_update_feeds.sh` affiche un résumé agrégé. L’export permet l’aperçu et l’acceptation explicite ; il est expurgé, reste local et n’est jamais téléversé. `bash setup.sh --catalog` ouvre le catalogue sans sélection. `-y`, les exécutions non interactives et EOF n’installent rien. Dans le menu, `check <number>` compare uniquement les sources choisies. Les résultats indiquent la dernière version stable compatible confirmée et sa date ; le cache dure 24 heures. Une valeur inconnue le reste. Une fiche publique du Mac App Store ne prouve pas que l’app est proposée à votre compte.

Le catalogue public compte 47 lignes de registre pour 48 produits et zéro recette approuvée de première installation automatique. Après confirmation, choisissez des liens officiels vérifiés pour une acquisition manuelle. Ouvrir une page n’installe pas l’app. Changer la source d’une app existante exige une migration manuelle. L’InstallPlan indique source, destination, version, prérequis et autorisations ; licence et coût inconnus restent signalés comme tels. Toute recette automatique future exigera une validation avant activation. Le catalogue ne promet pas d’installer automatiquement tous les produits.

`--dry-run` affiche un aperçu lisible de 25 cibles maximum. `--dry-run --json-summary` ou `--plan` fournit le plan JSON complet. Cet aperçu ne donne aucune autorisation et ne lance aucune mise à jour.
