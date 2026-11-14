# User Guide (English)

**Version:** 1.7.2 · **Apple Silicon, macOS 13+**

## Safe setup and application sources

`bash setup.sh --inspect` checks readiness without installing dependencies, changing shell profiles or configuring Touch ID. Missing tools leave the affected feature unavailable. In a terminal, `bash setup.sh --install-dependencies` previews optional dependencies and asks before each installation; `bash setup.sh --configure-shell` separately previews a shell profile change. Declining a dependency leaves independent features usable. If Python is unavailable, install it explicitly before building inventory. Missing or outdated `mas` is reported during updates and is never installed or upgraded automatically.

This is the 1.7.2 source snapshot on main, without a separate release tag. Scoped manager updates act only on installed targets with an observed source and fresh approval. Generic native and vendor updater adapters remain manual until reviewed recipes are available. The optional public catalog covers 48 products and offers reviewed official links for manual acquisition, with zero approved automatic first-install recipes. The legacy method list below describes capabilities, not execution authority. The normal update report covers installed applications. `bash scripts/report_update_coverage.sh --show-supported` remains a reference list. Open the optional selection menu with `bash setup.sh --catalog`; it starts with nothing selected. A selected app can be acquired from a reviewed official link after preview and fresh confirmation. Changing an existing app source requires manual migration. A CapCut App Store receipt retains App Store routing. A local app without confirmed Homebrew ownership is never adopted automatically.

## What this toolkit does

macOS Updates orchestrates updates in seven steps on **Apple Silicon Macs running macOS 13+**. The full pipeline runs in this order:

1. Prescan and per-Mac inventory
2. App Store (`sudo mas upgrade <app-id>` plus a separate GUI Track 2 for iPad apps)
3. Existing native CLIs first, then Node/Bun and npm fallbacks
4. Homebrew formulae and casks (greedy upgrade only for casks registered as `brew_cask`)
5. Installed internet apps through direct handlers, vendor CLIs or in-app update triggers
6. Atomic inventory/history postupdate
7. macOS (`softwareupdate -i <label> -R`) last; deferred after a blocking hard failure or unavailable authorization

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

The registry maps 47 apps to 11 methods (`config/internet_app_methods.txt`; the README has the full per-method table):

| Method | Examples | Coverage state | AI agent hint |
|--------|----------|----------------|---------------|
| `brew_cask` | Brave, Obsidian, Inkscape | externally managed | Homebrew cask, greedy only for these tokens, with downgrade protection |
| `silent_launch` | Claude, Cursor, Warp | triggered-unverified | Fallback: launches the app's own updater; verify the About/version screen. Apps with a vendor feed are decided by that feed and installed from the verified vendor artifact when behind; `config/vendor_launch_policy.txt` lists apps that are never launched |
| `github_dmg` | KeePassXC, Visual Studio Code | verified direct | `scripts/scaffold_internet_app.sh "App" github_dmg`; signature and Team ID are verified |
| `msupdate` | Microsoft Word, Excel, Outlook | verified direct | Shared Office `msupdate` handler |
| `keystone` | Chrome, Gemini, Google Drive | verified direct | Google updater (Omaha) handler in `lib/internet_app_updates.sh` |
| `appstore_gui` | UniFi, WiFiman, Picsart, IPMIView | externally managed | App Store GUI Track 2 |
| `sparkle_appcast` | Proton Drive | verified direct | Sparkle appcast |
| `chromium_updater` | Comet | verified direct | Chromium-based updater proof |
| `docker_cli` | Docker Desktop | verified direct | Idle: verified DMG from Docker's appcast; running: left alone (quit it to update); fallback `docker desktop update` |
| `mau_fallback_self_update` | Microsoft Teams | triggered-unverified | Teams self-updater plus an observed, verified `TEAMS21` MAU fallback when offered |
| `mozilla_dmg` | Firefox Developer Edition | verified direct | Mozilla product-details version plus verified DMG, staged swap and rollback |

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
| `mas` fails | Sign in to App Store; use `sudo mas upgrade <app-id>` |
| iPad apps not updating | Grant Accessibility to Terminal |
| Missing `APPLICATIONS.md` | `bash build_inventory.sh` or `dev_sync/dev-sync-import.sh` (owner) |

Full troubleshooting: [../../agents/troubleshooting.md](../../agents/troubleshooting.md)

Stage C activates local JSON inventory and scoped update plans. `bash update_all.sh --plan` and `--dry-run` show the same read-only decisions. A normal interactive run asks once for the displayed scopes; `-y`, EOF and unattended runs grant no new permission. Use `--preferences` to review or reset choices. Updates keep the observed source and exact destination; conflicts, missing targets and uncertain evidence defer that target. `build_inventory.sh --migration --preview` preserves old Markdown bytes and notes; accept the displayed proposal ID explicitly. Generic vendor updates remain manual until a reviewed identity and adapter are available. An old catalog entry is neither proof of installation nor consent.


## Optional catalog and first installation

New app signals are review proposals, not executable recipes. `bash scripts/scan_update_feeds.sh` prints an aggregated summary. Proposal export supports preview and explicit acceptance; it is redacted, stays local, and is never uploaded. `bash setup.sh --catalog` opens the optional catalog with no selection. `-y`, noninteractive runs, and EOF install nothing. In the menu, `check <number>` compares only selected sources. Results show the latest confirmed compatible stable version and date, cached for 24 hours. Unknown stays unknown. A public Mac App Store listing does not prove availability to your account, and no channel is always fastest.

The public catalog has 47 registry rows for 48 separate products and zero approved automatic first-install recipes. After preview and fresh confirmation, you can choose reviewed official links for manual acquisition. Opening a page does not install the app. Changing an existing app's source requires manual migration. The separate InstallPlan shows source, destination, version, requirements, and permissions; unknown license or cost stays labeled unknown. Any future automatic recipe needs fresh-install acceptance before enablement. The catalog does not promise automatic installation for all 48 products.
