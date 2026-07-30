# Quick Start (English)

**Apple Silicon Mac required** · macOS 13+ · **v1.0.21**

## One-line install (recommended)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

Then:

```bash
cd ~/Dev_Env/macOS_updates
bash update_all.sh --dry-run -y    # preview
bash update_all.sh -y              # full update
```

The installer builds **your** app inventory from what's already installed. It does not install apps from the maintainer's list or import another user's cloud backup.

## Language (7 locales)

After clone, `install.sh`, `setup.sh`, and `migration_setup.sh` show an **English** language menu (default: English). Your choice is saved in `.mac_update_prefs` as `MAC_LANG` (`en`, `pl`, `de`, `fr`, `es`, `it`, `pt`). All update scripts (`update_all.sh`, `update_*.sh`), `uninstall.sh`, and the coverage report use the same preference.

Set `MAC_UPDATE_LANG=pl` (etc.) before running the one-liner to skip the picker.

## Manual install

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh
bash build_inventory.sh
bash update_all.sh
```

## Owner (GitHub + cloud overlay)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

## Useful commands

| Command | Purpose |
|---------|---------|
| `bash scripts/report_update_coverage.sh` | Verified, triggered, external, manual and unknown coverage |
| `bash build_inventory.sh` | Refresh `APPLICATIONS.md` from this Mac |
| `bash update_all.sh --dry-run -y` | Preview all steps |
| `bash run_tests.sh` | Verify installation |
| `bash uninstall.sh` | Remove toolkit |

See [GUIDE.md](GUIDE.md), [../../INSTALL.md](../../INSTALL.md), [../../UNINSTALL.md](../../UNINSTALL.md).
