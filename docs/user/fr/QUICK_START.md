# Démarrage rapide (Français)

**Mac Apple Silicon requis** · macOS 13+ · **v1.7.7**

## Configuration sûre et sources des applications

`bash setup.sh --inspect` vérifie la disponibilité sans installation, modification du profil shell ni configuration Touch ID. Un outil absent rend sa fonction indisponible. Dans un terminal, `bash setup.sh --install-dependencies` présente les dépendances facultatives et demande avant chaque installation ; `bash setup.sh --configure-shell` présente séparément la modification du profil. Refuser une dépendance ne bloque pas les fonctions indépendantes. Sans Python, installez-le explicitement avant de construire l’inventaire. Un `mas` absent ou ancien est signalé, jamais installé ni mis à niveau automatiquement.

Le rapport normal montre les applications installées. `bash scripts/report_update_coverage.sh --show-supported` affiche les recettes absentes. Ce catalogue informatif n’est pas encore un menu d’installation. Un reçu App Store pour CapCut conserve la voie App Store même sans cask. Sans propriété Homebrew confirmée, une source est proposée sans adoption ni installation. La résolution complète et le choix interactif des sources restent prévus pour les étapes suivantes.

## Installation en une ligne

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

## Nouvel utilisateur (GitHub uniquement)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh --inspect
bash build_inventory.sh
bash update_all.sh
```


## Propriétaire (GitHub + overlay Proton Drive)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

Les fichiers privés (`APPLICATIONS.md`, `UPDATES.md`, `.env`) proviennent de votre overlay cloud — pas de GitHub.

## Commandes utiles

| Commande | Objectif |
|----------|----------|
| `bash update_all.sh --dry-run -y` | Aperçu de toutes les étapes |
| `bash update_system.sh` | macOS uniquement |
| `bash update_appstore.sh` | App Store uniquement |
| `bash update_brew.sh` | Homebrew uniquement |
| `bash run_tests.sh` | Vérifier l'installation |

Voir [GUIDE.md](GUIDE.md) et [OPERATIONS.md](OPERATIONS.md).

L’étape B (1.6.2) ajoute un inventaire observationnel facultatif : `bash build_inventory.sh --shadow`. Les identités locales, preuves de provenance et analyses incomplètes sont enregistrées en JSON privé, sans modifier `APPLICATIONS.md` ni le fonctionnement des mises à jour. `--dry-run` évite l’enregistrement, `--json` produit un résultat structuré et plusieurs options `--root CHEMIN` définissent les répertoires. Les conflits restent des observations ; le choix des sources et le contrôle d’exécution relèvent de l’étape C.
