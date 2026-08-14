# Scripts Reference

| Script | Purpose |
|--------|---------|
| `install.sh` | One-line new-user install: clone, `setup.sh`, `build_inventory.sh`, coverage report |
| `uninstall.sh` | Remove repo clone (optional `--purge` prefs) |
| `build_inventory.sh` | Read-only scan — atomically refresh `APPLICATIONS.md` (apps, Homebrew and native CLI versions) without adding update history |
| `setup.sh` | First-run (public users) — language, deps, paths |
| `migration_setup.sh` | First-run (owner) — phases 0a–16: language, cloud, deps, paths, app scan |
| `update_all.sh` | Master: prescan → App Store → npm CLI → Homebrew → internet apps → postupdate/history → macOS final |
| `update_system.sh` | macOS via `softwareupdate -ia -R --verbose` |
| `update_appstore.sh` | `sudo mas upgrade` + AppleScript GUI for iPad apps |
| `update_internet_apps.sh` | Installed internet apps (see `config/internet_apps.txt`): verified direct handlers, vendor CLIs and honestly reported in-app updater triggers |
| `update_npm_cli.sh` | Native Node/Bun + npm global CLI (`claude`, `codex`, `opencode`) + self-updating `agy` |
| `update_brew.sh` | `brew upgrade` + cleanup + doctor |
| `lib/python/inventory.py` | Pure Python library for inventory normalization, exclusions, and prescan |
| `lib/python/run_summary.py` | Pure Python library for building machine-readable run summary JSON |
| `config/inventory_exclusions.txt` | Explicit list of apps to ignore during inventory scans (e.g. `Ascendo`) |
| `dev_sync/*.sh` | Export/import/verify private files to/from cloud storage |
| `scripts/report_update_coverage.sh` | Report installed vs supported vs unknown apps (by method category) |
| `scripts/setup_touchid_sudo.sh` | Per-machine Touch ID for sudo PAM configuration (`/etc/pam.d/sudo_local`) |
| `scripts/install_launchagent.sh` | Install and manage weekly launchd update schedule |
| `scripts/audit_cask_candidates.sh` | Audit installed internet apps against Homebrew Cask availability |
| `scripts/scan_update_feeds.sh` | Scan installed apps for Sparkle, Electron, and Keystone update frameworks |
| `scripts/scaffold_internet_app.sh` | Generate config entries and handler boilerplate for new internet apps |

**Private files** (`.gitignore`d): `APPLICATIONS.md`, `UPDATES.md`, `.env`, `.dev_sync_config.json`

`update_all.sh` supports `--dry-run`, `--yes`, `--verify-only`, and selective `--skip-*` flags (see `lib/cli.sh`). It evaluates child script step severity: exit 0 indicates clean success, exit 10 indicates soft/degraded results (logged as warnings, non-blocking), and exit 1/127 indicates hard failures (blocking).

## update_all.sh Step Order

```
Step 0: prescan             — scan /Applications + ~/Applications + brew + mas → write installed_apps_scan.txt → atomically update APPLICATIONS.md
Step 1: update_appstore.sh  — Track 1: sudo mas; Track 2: AppleScript GUI for iPad apps
Step 2: update_npm_cli.sh   — native Node/Bun + npm global CLI migration/update + `agy update`
Step 3: update_brew.sh      — Homebrew formulae/casks (--greedy) + cleanup + doctor
Step 4: update_internet_apps.sh — installed internet apps; direct updates and honest triggers
Step 5: postupdate.py       — capture fresh /Applications to installed_apps_after.txt → refresh APPLICATIONS.md and append UPDATES.md
Step 6: update_system.sh    — macOS via softwareupdate -ia -R; last because it may restart
```

If any step before step 6 encounters a hard failure (`BLOCKING_EXIT`), step 6 (`softwareupdate`) is deferred to avoid rebooting into a broken state. Soft warnings (`exit 10`) surface warnings in reporting while allowing system updates to proceed.

## migration_setup.sh — Phases 0a–16 (New Mac First-Run)

Run once before `update_all.sh` when copying project to a new Mac.

```
Phase 0a/16: Language selection (before localized banner)
Phase 0b/16: Cloud storage provider setup
Phase  1: Validate Apple Silicon (arm64) and macOS 13+, then detect user, home, version, hostname, shell, terminal app
Phase  2: Extract old username from CLAUDE.md path patterns
Phase  3: Fix paths in all .md files (username, project dir, Homebrew prefix)
Phase  4: Update macOS version + arch strings in all AI context files
Phase  5: Check/install Xcode Command Line Tools
Phase  6: Check/install Homebrew at /opt/homebrew (Apple Silicon only — Intel not supported)
Phase  7: Check/install mas ≥4.0 (CVE-2025-43411 requirement)
Phase  8: Detect Python 3; install python@3.11 if missing
Phase  9: Check curl, git availability
Phase 10: Check optional tools: msupdate, Docker CLI ≥4.37, Google Keystone
Phase 11: chmod +x all *.sh scripts
Phase 12: Verify App Store login via mas list
Phase 13: Test Accessibility for terminal; open System Settings if missing
Phase 14: Inline Python scans /Applications + ~/Applications + brew + mas → atomically updates APPLICATIONS.md
Phase 15: Fix MCP configs for Gemini/Windsurf
Phase 16: Append migration entry to UPDATES.md; print ✅/⚠️/❌ summary
```

`migration_setup.sh` is **idempotent** — safe to re-run. Its readiness checks are fail-closed: unmet required dependencies produce a non-zero exit instead of a success-looking summary.

## Dev Sync Commands

```bash
bash dev_sync/dev-sync-export.sh        # Push private files to cloud storage
bash dev_sync/dev-sync-import.sh        # Pull private files from cloud storage
bash dev_sync/dev-sync-verify-git.sh    # Verify: clean tree, upstream set, not ahead
bash dev_sync/dev-sync-verify-full.sh   # Full verify: git + cloud completeness
bash dev_sync/dev-sync-prune-excluded.sh # Report stale/generated provider files
bash dev_sync/dev-sync-proton-status.sh --full # Check Proton upload before offload
```

## New Mac Complete Setup

**Public user (no cloud):**

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
bash update_all.sh
```

**Owner (cloud overlay):**

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

Never copy another user's `APPLICATIONS.md` — use `build_inventory.sh` or prescan on a fresh Mac.

## Adding a New Internet App

1. Add app name to `config/internet_apps.txt` (canonical list)
2. Add method row to `config/internet_app_methods.txt` (`AppName|method|STATUS_VAR`)
3. Run `bash scripts/scaffold_internet_app.sh "App Name" silent_launch` for boilerplate
4. Implement `iu_<slug>()` in `lib/internet_app_updates.sh`
5. Append `iu_<slug>` to `config/internet_dispatch_order.txt` (execution order)
6. Add `STATUS_*` init, summary `printf`, and failure-scan entry in `update_internet_apps.sh`
7. Add `L_INTERNET_*` keys to all 7 `i18n/lang_*.sh` files (English first)
8. `bash run_tests.sh` — handler + dispatch + registry parity tests must pass

`lib/internet_apps.sh` and `migration_setup.sh` phase 14 read the config automatically.
