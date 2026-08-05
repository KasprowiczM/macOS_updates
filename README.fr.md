# macOS Updates

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

> **v1.3.0** — Orchestrateur de mise à jour en une commande prêt pour la production pour **Macs Apple Silicon sous macOS 13–26**. Coordonne les mises à jour vérifiées pour les logiciels déjà installés sur ce Mac. **Multilingue** (7 langues). Couche cloud privée optionnelle via [`dev_sync/`](dev_sync/README.md).

**Dépôt public :** [github.com/KasprowiczM/macOS_updates](https://github.com/KasprowiczM/macOS_updates) · Release: [docs/PUBLIC_RELEASE.md](docs/PUBLIC_RELEASE.md)

---

## Installation en une ligne (nouveaux utilisateurs)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

Le programme d'installation clone le dépôt, demande la **sélection de la langue** (le français est disponible), installe les dépendances, génère votre fichier `APPLICATIONS.md` basé sur les applications présentes sur votre Mac et indique quelles applications peuvent être mises à jour.

Voir [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md)

---

## Ce que fait cet outil

`update_all.sh` exécute sept étapes :

| Étape | Action |
|-------|--------|
| 0 | **Analyse préalable** — détecte les applications installées → met à jour `APPLICATIONS.md` |
| 1 | **App Store** — Piste 1 : `sudo mas upgrade` ; Piste 2 : GUI AppleScript pour applications iPad |
| 2 | **CLI native + npm** — Node, Bun, outils globaux npm |
| 3 | **Homebrew** — Formules et Casks (`--greedy-auto-updates`) + protection contre la rétrogradation |
| 4 | **Applications Internet** — gestionnaires vérifiés, `vendor_latest`, Sparkle Appcast |
| 5 | **Post-mise à jour/Historique** — met à jour l'inventaire et l'historique de manière atomique |
| 6 | **macOS (dernière)** — `softwareupdate -ia -R` ; ignoré en cas d'erreur préalable |

---

## Fonctionnalités et variables d'environnement dans v1.3.0

- **Pré-autorisation Sudo / Touch ID** : Détecte `pam_tid.so` et maintient la session sudo active.
- **Support LaunchAgent & Arrière-plan** : Prise en charge de `MAC_UPDATE_NO_SUDO=1` pour les exécutions non surveillées.
- **Méthode `vendor_latest`** : Évite les rétrogradations de Homebrew Cask pour les applications à mise à jour rapide (Cursor, Warp, Antigravity, Proton Mail, Proton Drive, Claude, Comet, ChatGPT).
- **Variables de contrôle** :
  - `MAC_UPDATE_YES=1` (`-y`) — Confirmation non interactive de toutes les étapes.
  - `MAC_UPDATE_SKIP_SYSTEM=1` (`--skip-system`) — Ignore les mises à jour système macOS.
  - `MAC_UPDATE_NONINTERACTIVE=1` — Supprime les dialogues interactifs.

```bash
# Exemple d'exécution automatisée en arrière-plan :
MAC_UPDATE_NONINTERACTIVE=1 bash update_all.sh -y --skip-system
```

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

---

## Documentation

| Public | Commencer ici |
|--------|---------------|
| Utilisateurs | [docs/user/fr/QUICK_START.md](docs/user/fr/QUICK_START.md) |
| Installation / Désinstallation | [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md) |
| Développeurs | [docs/agents/scripts.md](docs/agents/scripts.md) |
| Synchro Cloud | [dev_sync/README.md](dev_sync/README.md) |
| Contexte IA | `AGENTS.md` |

---

## Remarques techniques critiques

- **`softwareupdate` DOIT utiliser `-R`** — sinon les mises à jour sont téléchargées mais ne sont jamais appliquées.
- **`mas upgrade` DOIT utiliser `sudo`** sous macOS 14.8+/15.7+/26.x (CVE-2025-43411).
- **Bash 3.2+** dans tout le projet — aucun `declare -A`, `mapfile` ou `readarray`.
