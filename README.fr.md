# Mises à jour macOS

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

> **v1.0.19** — Outil de mise à jour en une seule commande, prêt pour la production, destiné aux **Macs Apple Silicon**. Maintient à jour macOS, l'App Store, Homebrew et plus de 40 applications téléchargées sur Internet — **uniquement les logiciels que vous avez déjà installés**. **Multilingue** (7 langues). Couche privée optionnelle dans le cloud via [`dev_sync/`](dev_sync/README.md).

**Dépôt public :** [github.com/KasprowiczM/macOS_updates](https://github.com/KasprowiczM/macOS_updates) · Publication : [docs/PUBLIC_RELEASE.md](docs/PUBLIC_RELEASE.md)

---

## Installation en une ligne (nouveaux utilisateurs)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

L'installateur clone le dépôt, vous invite à choisir la **langue** (le français est l'une des 7 options), installe les dépendances, génère **votre** fichier `APPLICATIONS.md` à partir des applications déjà présentes sur votre Mac et affiche les applications qui peuvent être mises à jour. Il n'importe jamais l'inventaire d'un autre utilisateur ni n'installe de nouvelles applications pour vous.

Voir [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md)

---

## Ce que fait cet outil

`update_all.sh` exécute sept étapes :

| Étape | Action |
|------|--------|
| 0 | **Pré-analyse** — détecte les applications installées → met à jour `APPLICATIONS.md` |
| 1 | **Système** — `softwareupdate -ia -R` |
| 2 | **App Store** — `sudo mas upgrade` + solution de secours via AppleScript |
| 3 | **CLI natifs + npm** — Node, Bun, outils globaux npm |
| 4 | **Homebrew** — `brew upgrade` + nettoyage |
| 5 | **Applications Internet** — uniquement si elles sont installées (Chrome, VS Code, Microsoft 365, …) |
| 6 | **Post-mise à jour** — met à jour les versions dans `APPLICATIONS.md`, ajoute à `UPDATES.md` |

**Important :** Les mises à jour ne modifient que les logiciels déjà installés sur votre Mac. Les applications prises en charge mais absentes sont signalées, non installées.

```bash
bash scripts/report_update_coverage.sh   # rapport de couverture
bash build_inventory.sh                  # reconstruire APPLICATIONS.md
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

### Propriétaire (GitHub + couche cloud)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

---

## Documentation

| Public ciblé | Commencer ici |
|----------|------------|
| Utilisateurs | [docs/user/fr/QUICK_START.md](docs/user/fr/QUICK_START.md) |
| Installation / Désinstallation | [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md) |
| Développeurs | [docs/agents/scripts.md](docs/agents/scripts.md) |
| Synchronisation dev sync | [dev_sync/README.md](dev_sync/README.md) |
| Contexte IA | `AGENTS.md` |

---

## Notes techniques cruciales

- **`softwareupdate` doit utiliser `-R`** — sinon, les mises à jour se téléchargent mais ne s'appliquent jamais.
- **`mas upgrade` doit utiliser `sudo`** sous macOS 26.x (CVE-2025-43411).
- **Bash 3.2+** dans son intégralité — pas de `declare -A`, `mapfile` ou `readarray`.
