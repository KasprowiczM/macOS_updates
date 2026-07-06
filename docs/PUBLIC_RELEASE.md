# Public GitHub vs Private Cloud Overlay

**Production release:** v**1.0.19** · Repository: [github.com/KasprowiczM/macOS_updates](https://github.com/KasprowiczM/macOS_updates)

This repository is designed for **public GitHub** plus an optional **private overlay** synced to your cloud provider (Proton Drive, iCloud, Google Drive, etc.).

## What lives on GitHub (public)

| Path | Purpose |
|------|---------|
| `install.sh`, `setup.sh`, `migration_setup.sh` | First-run and one-line install |
| `build_inventory.sh` | Build `APPLICATIONS.md` from **this Mac only** |
| `update_*.sh`, `lib/` | Update orchestrators and shared libraries |
| `dev_sync/` | Cloud export/import/verify (Python backend) |
| `config/` | Internet app registry (`internet_apps.txt`, methods, dispatch) |
| `i18n/` | 7 language packs (English is source of truth) |
| `templates/APPLICATIONS.md.template` | Reference structure (not a user catalog) |
| `tests/`, `run_tests.sh`, `.github/workflows/` | CI (62 unittest + shellcheck + gitleaks) |
| `docs/` | User and developer documentation |
| `VERSION` | Package version |
| `.env.example` | Template only (no secrets) |

## What lives in cloud overlay only (private)

Synced via `bash dev_sync/dev-sync-export.sh` — **never commit these**:

| File | Purpose |
|------|---------|
| `.env` | API tokens (e.g. optional `GITHUB_TOKEN`) |
| `.dev_sync_config.json` | Cloud provider path and credentials |
| `.mac_update_prefs` | Language and UI preferences |
| `APPLICATIONS.md` | **Your** personal app catalog (built on each Mac) |
| `UPDATES.md` | Your update session history |

## New user workflow (no cloud)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
cd ~/Dev_Env/macOS_updates
bash update_all.sh --dry-run -y
bash update_all.sh
```

The installer **does not** import another user's `APPLICATIONS.md` or install apps from the maintainer's inventory.

## Owner workflow (GitHub + cloud)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

After local changes to private files:

```bash
bash dev_sync/dev-sync-export.sh
bash dev_sync/dev-sync-verify-full.sh
```

## Production checklist

- [x] `APPLICATIONS.md` and `UPDATES.md` gitignored
- [x] `.env`, `.dev_sync_config.json` gitignored
- [x] `bash run_tests.sh` passes (62 tests + gitleaks)
- [x] CI: macOS test job + Ubuntu shellcheck (see `.shellcheckrc`)
- [x] One-line install documented in `README.md` and `docs/INSTALL.md`
- [x] New users build inventory locally (`build_inventory.sh`)
- [ ] Rotate any secrets that ever lived in git before public push
- [ ] Confirm GitHub repo visibility: **Public**

Local secret scan: `brew install gitleaks && bash scripts/scan_secrets.sh`

See also: [agents/security.md](agents/security.md), [INSTALL.md](INSTALL.md), [UNINSTALL.md](UNINSTALL.md)
