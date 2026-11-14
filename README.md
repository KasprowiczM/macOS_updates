# macOS Updates

## Install and use

Install from the public repository, inspect readiness, then preview updates.

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git
cd macOS_updates
bash setup.sh --inspect
bash build_inventory.sh --cli
bash update_all.sh --dry-run -y
bash update_all.sh
```

The workspace lets you review installed software, update choices and exclusions. A saved choice applies only to its approved scope; new or changed scope requires review. Some apps require manual action.

A pending or unconfirmed helper can block later updates. Open Diagnostics to review recovery; do not delete journals or locks.

Use About in the workspace to review and explicitly apply a toolkit update. The updater checks local changes before applying.

```bash
bash uninstall.sh
```

After a public history replacement, keep the old checkout and your local files. For a fresh installation, choose a new directory that does not exist and replace `vX.Y.Z` below with the verified release tag. Run this from the directory containing `install.sh`.

```bash
MAC_UPDATE_DIR="$HOME/Dev_Env/macOS_updates-new" MAC_UPDATE_REF="vX.Y.Z" bash install.sh
```
