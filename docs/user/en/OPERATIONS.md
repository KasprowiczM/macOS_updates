# Operations Runbook

Human operator guide for daily and weekly macOS Updates maintenance.

## Platform

**Apple Silicon (arm64), macOS 13+ only.** Scripts exit before mutations on unsupported Macs.

## Weekly update

```bash
cd ~/Dev_Env/macOS_updates
bash update_all.sh
```

Review on failure: `logs/update_all_<timestamp>.log` (last 30 runs kept).

## Pipeline order (`update_all.sh`)

| Step | Script / action | Skip flag |
|------|-----------------|-----------|
| 0 | prescan → `APPLICATIONS.md` | `--skip-prescan` |
| 1 | `update_appstore.sh` | `--skip-appstore` |
| 2 | `update_npm_cli.sh` | `--skip-npm` |
| 3 | `update_brew.sh` | `--skip-brew` |
| 4 | `update_internet_apps.sh` | `--skip-internet` |
| 5 | postupdate/history → `APPLICATIONS.md`, `UPDATES.md` | `--skip-postupdate` |
| 6 | `update_system.sh` (`softwareupdate -ia -R`) | `--skip-system` |

Step 6 runs last because it may restart the Mac. It is automatically skipped when an earlier selected step fails.

Preview without mutations: `bash update_all.sh --dry-run -y`

## Failure triage

| Step failed | Check these files |
|-------------|-------------------|
| App Store | `$SESSION_DIR/appstore_diag.txt`, log snapshot |
| Internet apps | `$SESSION_DIR/internet_diag.txt`, `internet_before/after.txt` |
| Homebrew | `$SESSION_DIR/brew_*_before/after.txt` |
| Any | `logs/update_all_*.log` (snapshots appended on non-zero exit) |

App Store Accessibility missing → exit code `2`; use `--treat-appstore-ax-as-warning` or grant Accessibility to your terminal.

See `docs/agents/exit_codes.md` for full exit code reference.

## Private overlay (Proton Drive)

After editing private files locally:

```bash
bash dev_sync/dev-sync-export.sh
bash dev_sync/dev-sync-verify-full.sh
bash dev_sync/dev-sync-prune-excluded.sh   # should report zero candidates
```

## New Mac

**Public user:**

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
bash update_all.sh
```

**Owner (cloud overlay):**

```bash
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

Inventory is always built from apps on **this** Mac (`build_inventory.sh`). Never copy another user's `APPLICATIONS.md`.

```bash
bash scripts/report_update_coverage.sh   # supported vs missing apps
```

## Pre-update checklist

- [ ] App Store signed in (`mas account` or App Store app)
- [ ] Terminal has Accessibility (for iPad app track 2)
- [ ] Disk space ≥ 20 GB free for large macOS updates
- [ ] `sudo` available for `mas upgrade` and system updates

## Post-update verification

```bash
mas outdated
brew outdated
softwareupdate -l
```

For **triggered-unverified** apps, verify the About/version screen: launching the vendor updater does not prove completion. Manual coverage remains limited to IPMIView and DJI Assistant 2.
