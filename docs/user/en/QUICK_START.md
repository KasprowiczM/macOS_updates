# Quick Start (English)

**Apple Silicon Mac required** · macOS 13+ · **v1.6.2**

## Safe setup and application sources

`bash setup.sh --inspect` checks readiness without installing dependencies, changing shell profiles or configuring Touch ID. Missing tools leave the affected feature unavailable. In a terminal, `bash setup.sh --install-dependencies` previews optional dependencies and asks before each installation; `bash setup.sh --configure-shell` separately previews a shell profile change. Declining a dependency leaves independent features usable. If Python is unavailable, install it explicitly before building inventory. Missing or outdated `mas` is reported during updates and is never installed or upgraded automatically.

The normal update report lists installed applications. Browse supported but absent recipes with `bash scripts/report_update_coverage.sh --show-supported`. This is a reference catalog, not an installation menu. A CapCut App Store receipt retains App Store routing even without a cask. A local app without confirmed Homebrew ownership gets a source recommendation, not adoption or installation. The full source resolver and interactive source selection are planned for later stages.

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

After clone, `install.sh` and `migration_setup.sh` show an **English** language menu (default: English). Your choice is saved in `.mac_update_prefs` as `MAC_LANG` (`en`, `pl`, `de`, `fr`, `es`, `it`, `pt`). All update scripts (`update_all.sh`, `update_*.sh`), `uninstall.sh`, and the coverage report use the same preference.

Set `MAC_UPDATE_LANG=pl` (etc.) before running the one-liner to skip the picker.

## Manual install

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh --inspect
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

Stage B (1.6.2) adds an opt-in observational inventory: `bash build_inventory.sh --shadow`. It records local app/package identities, source evidence and incomplete scans in private JSON, without changing `APPLICATIONS.md` or update routing. Add `--dry-run` to avoid saving state, `--json` for structured results, or repeat `--root PATH` to specify scan roots. Conflicts remain observations; source choices and execution guards arrive in stage C.
