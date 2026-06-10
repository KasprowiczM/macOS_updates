# User Guide (English)

## What this toolkit does

macOS Updates automates updates across six layers on **Apple Silicon Macs**:

1. macOS system updates (`softwareupdate -ia -R`)
2. App Store apps (`sudo mas upgrade` + GUI fallback for iPad apps)
3. Native Node/Bun and npm global CLIs
4. Homebrew formulae and casks
5. 40+ internet-downloaded apps — **only if already installed**
6. Personal catalog (`APPLICATIONS.md`) and history (`UPDATES.md`)

It **never installs new applications** for you. Each Mac builds its own inventory first (`build_inventory.sh` or prescan in `update_all.sh`).

## Languages

Seven UI languages: EN, PL, DE, FR, ES, IT, PT. Set during `setup.sh` / `install.sh`; stored in `.mac_update_prefs`.

## Public vs private data

| Source | Contents |
|--------|----------|
| **GitHub** | Scripts, `config/`, tests, docs |
| **Cloud overlay** | `APPLICATIONS.md`, `UPDATES.md`, `.env`, `.dev_sync_config.json` |

## Coverage report

After install or when adding apps:

```bash
bash scripts/report_update_coverage.sh
```

Shows:

- Installed apps the project can update (by method category)
- Supported apps **not** installed (skipped — install yourself if wanted)
- Installed apps **not** in the registry (add handlers with an AI agent)

### Update method categories

| Method | Examples | AI agent hint |
|--------|----------|---------------|
| `keystone` | Chrome, Google Drive | Keystone handler in `lib/internet_app_updates.sh` |
| `github_dmg` | Firefox Dev, KeePassXC | `scripts/scaffold_internet_app.sh "App" github_dmg` |
| `silent_launch` | Claude, Cursor, Warp | `scripts/scaffold_internet_app.sh "App" silent_launch` |
| `msupdate` | Microsoft 365 suite | Shared `msupdate` handler |
| `docker_cli` | Docker Desktop | `docker desktop update` |
| `manual` | IPMIView, Inkscape | Notification only |

## Adding an internet app

1. Install the app on your Mac.
2. `bash build_inventory.sh`
3. `bash scripts/scaffold_internet_app.sh "App Name" silent_launch`
4. Follow the printed checklist; run `bash run_tests.sh`

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Intel Mac | Not supported — Apple Silicon only |
| Wrong app catalog | `bash build_inventory.sh` — do not use another user's `APPLICATIONS.md` |
| App not updating | `bash scripts/report_update_coverage.sh` |
| `mas` fails | Sign in to App Store; use `sudo mas upgrade` |
| iPad apps not updating | Grant Accessibility to Terminal |
| Missing `APPLICATIONS.md` | `bash build_inventory.sh` or `dev_sync/dev-sync-import.sh` (owner) |

Full troubleshooting: [../../agents/troubleshooting.md](../../agents/troubleshooting.md)
