# User Guide (English)

## What this toolkit does

macOS Updates orchestrates updates across six layers on **Apple Silicon Macs running macOS 13+**. The full pipeline runs in this order:

1. Prescan and per-Mac inventory
2. App Store (`sudo mas upgrade` plus a separate GUI Track 2 for iPad apps)
3. Native Node/Bun and npm global CLIs
4. Homebrew formulae and casks (`--greedy`)
5. Installed internet apps through direct handlers, vendor CLIs or in-app update triggers
6. Atomic inventory/history postupdate
7. macOS (`softwareupdate -ia -R`) last; skipped if an earlier step failed

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

Shows five evidence-based states:

- **verified direct** — a package/version path or vendor CLI result was confirmed
- **triggered-unverified** — the app launched its built-in updater, but completion is not asserted
- **externally managed** — App Store or vendor lifecycle owns the update
- **manual** — user action is intentionally required
- **unknown** — the installed app has no registered method

### Update method categories

| Method | Examples | AI agent hint |
|--------|----------|---------------|
| `keystone` | Chrome, Google Drive | Keystone handler in `lib/internet_app_updates.sh` |
| `github_dmg` | Firefox Dev, KeePassXC | `scripts/scaffold_internet_app.sh "App" github_dmg` |
| `silent_launch` | Claude, Cursor, Warp | Triggered-unverified; verify the About/version screen |
| `msupdate` | Microsoft Office | Shared Office `msupdate` handler |
| `mau_fallback_self_update` | Microsoft Teams | Teams self-updater plus an observed, verified `TEAMS21` MAU fallback when offered |
| `docker_cli` | Docker Desktop | `docker desktop update` |
| `brew_cask` | Inkscape | Homebrew cask with `--greedy` |
| `appstore_gui` | UniFi, WiFiman, Picsart | App Store GUI Track 2 |
| `manual` | IPMIView, DJI Assistant 2 | Notification only |

## Adding an internet app

1. Install the app on your Mac.
2. `bash build_inventory.sh`
3. `bash scripts/scaffold_internet_app.sh "App Name" silent_launch`
4. Follow the printed checklist; run `bash run_tests.sh`

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Intel Mac / macOS 12 or older | Not supported — Apple Silicon and macOS 13+ only |
| Wrong app catalog | `bash build_inventory.sh` — do not use another user's `APPLICATIONS.md` |
| App not updating | `bash scripts/report_update_coverage.sh` |
| `mas` fails | Sign in to App Store; use `sudo mas upgrade` |
| iPad apps not updating | Grant Accessibility to Terminal |
| Missing `APPLICATIONS.md` | `bash build_inventory.sh` or `dev_sync/dev-sync-import.sh` (owner) |

Full troubleshooting: [../../agents/troubleshooting.md](../../agents/troubleshooting.md)
