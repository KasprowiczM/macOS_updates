# Installation

**Version:** see `VERSION` in repo root (currently **1.0.18**).

## One-line install (new Mac, Apple Silicon)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

This will:

1. Clone to `~/Dev_Env/macOS_updates` (override with `MAC_UPDATE_DIR`)
2. Show the **language picker** (English menu; default English) and save choice to `.mac_update_prefs`
3. Run `setup.sh` — Xcode CLT, Homebrew, `mas`, Python, permissions (localized UI)
4. Run `build_inventory.sh` — create `APPLICATIONS.md` from **your** installed apps only
5. Print `scripts/report_update_coverage.sh` — what the project can and cannot update (localized)

Pre-clone checks (arm64, macOS version, git) are shown in English because i18n files are not available until after the clone.

The installer **does not**:

- Import another user's `APPLICATIONS.md` from cloud
- Install applications from the maintainer's inventory
- Run `dev_sync` import (optional; for owners with a private overlay)

## Manual install

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh
bash build_inventory.sh
bash update_all.sh --dry-run -y
```

## Owner (GitHub + cloud overlay)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `MAC_UPDATE_DIR` | `~/Dev_Env/macOS_updates` | Clone location |
| `MAC_UPDATE_REPO` | GitHub URL | Alternate remote |
| `MAC_UPDATE_LANG` | (picker after clone) | Skip picker: `en`, `pl`, `de`, `fr`, `es`, `it`, `pt` |
| `MAC_UPDATE_NONINTERACTIVE` | `0` | `1` = default answers in `setup.sh` |
| `MAC_UPDATE_SKIP_INVENTORY` | `0` | `1` = skip inventory build in `install.sh` |

## Verify

```bash
bash run_tests.sh
```

See also [UNINSTALL.md](UNINSTALL.md) and [user/en/QUICK_START.md](user/en/QUICK_START.md).
