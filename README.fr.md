# Mises à jour macOS

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

> **v1.0.21** — Orchestrateur de mise à jour en une commande pour **Mac Apple Silicon sous macOS 13+**. Il coordonne les mises à jour vérifiées et signale honnêtement les déclenchements intégrés — **uniquement pour les logiciels déjà installés**. **Multilingue** (7 langues). Couche privée optionnelle via [`dev_sync/`](dev_sync/README.md).

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
| 1 | **App Store** — Track 1 : `sudo mas upgrade` ; Track 2 : interface AppleScript pour apps iPad |
| 2 | **CLI natifs + npm** — Node, Bun, outils globaux npm |
| 3 | **Homebrew** — formules et casks (`--greedy`) + nettoyage |
| 4 | **Applications Internet** — handlers vérifiés, CLI éditeurs et déclencheurs honnêtes |
| 5 | **Post-mise à jour/historique** — inventaire et historique atomiques |
| 6 | **macOS (en dernier)** — `softwareupdate -ia -R` ; ignoré si une étape précédente échoue |

**Important :** Les mises à jour ne modifient que les logiciels déjà installés sur votre Mac. Les applications prises en charge mais absentes sont signalées, non installées.

La couverture distingue **verified direct**, **triggered-unverified**, **externally managed**, **manual** et **unknown** ; lancer une app ne prouve pas sa mise à jour. Inkscape passe par Homebrew Cask ; UniFi, WiFiman et Picsart par App Store Track 2 ; Office par `msupdate` ; Teams par son propre programme avec un repli MAU `TEAMS21` observé et vérifié lorsque Microsoft le propose. Seuls IPMIView et DJI Assistant 2 restent manuels.

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
