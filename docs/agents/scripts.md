# Scripts Reference

| Script | Purpose |
|--------|---------|
| `install.sh` | One-line new-user install: clone, `setup.sh`, `build_inventory.sh`, coverage report |
| `uninstall.sh` | Remove repo clone (optional `--purge` prefs) |
| `build_inventory.sh` | Read-only scan — atomically refresh `APPLICATIONS.md` (apps, Homebrew and native CLI versions) without adding update history |
| `setup.sh` | First-run (public users) — language, deps, paths |
| `migration_setup.sh` | First-run (owner) — phases 0a–16: language, cloud, deps, paths, app scan |
| `update_all.sh` | Master: prescan → App Store → npm CLI → Homebrew → internet apps → postupdate/history → macOS final |
| `update_system.sh` | per-label `softwareupdate -i <label> -R`, restart-required labels in one final batch |
| `update_appstore.sh` | `sudo mas upgrade` + AppleScript GUI for iPad apps |
| `update_internet_apps.sh` | Installed internet apps (see `config/internet_apps.txt`): verified direct handlers, vendor CLIs and honestly reported in-app updater triggers |
| `update_npm_cli.sh` | Native Node/Bun + npm global CLI (`claude`, `codex`, `opencode`) + self-updating `agy` |
| `update_brew.sh` | `brew upgrade` + cleanup + doctor |
| `lib/brew.sh` | Resilient Homebrew queries: `brew_cask_versions`, `brew_formula_versions`, `brew_outdated_formulae`, `brew_outdated_casks` |
| `lib/python/inventory.py` | Pure Python library for inventory normalization, exclusions, and prescan |
| `lib/python/run_summary.py` | Pure Python library for building machine-readable run summary JSON (format 2) |
| `lib/python/http_fetch.py` | HTTPS download helper used by tests and the fetch adapter |
| `lib/python/run_lock.py` | Exclusive run lock (`.mac-update.lock`); `kill(pid,0)` EPERM counts as alive |
| `lib/fetch.sh` | HTTPS-only download with emptiness and size checks (no curl-pipe-to-sh) |
| `lib/native_installers.sh` | Per-vendor CLI install/update (Claude positional `latest`, Codex `--release latest`, OpenCode repair) |
| `lib/run_lock.sh` | Shell wrapper for the Python run lock |
| `dev_sync/overlay_import.py` | Overlay import planner: expand directory manifests, skip Git/excluded, refuse symlink escapes |
| `config/inventory_exclusions.txt` | Explicit list of apps to ignore during inventory scans (e.g. `Ascendo`) |
| `dev_sync/*.sh` | Export/import/verify private files to/from cloud storage |
| `scripts/check_vendor_feeds.sh` | Read-only diagnostic query of vendor feeds and Omaha updaters (table and `--json`) |
| `scripts/report_update_coverage.sh` | Report installed vs supported vs unknown apps (by method category) |
| `scripts/setup_touchid_sudo.sh` | Per-machine Touch ID for sudo PAM configuration (`/etc/pam.d/sudo_local`) |
| `scripts/install_launchagent.sh` | Install and manage weekly launchd update schedule |
| `scripts/audit_cask_candidates.sh` | Audit installed internet apps against Homebrew Cask availability |
| `scripts/scan_update_feeds.sh` | Scan installed apps for Sparkle, Electron, and Keystone update frameworks |
| `scripts/scaffold_internet_app.sh` | Generate config entries and handler boilerplate for new internet apps |
| `lib/appstore_ios.sh` | iOS and iPad app detection and App Store lookup helpers (Bash 3.2+) |
| `lib/cli.sh` | Shared CLI flag parsing and usage definitions for orchestrators |
| `lib/github_release.sh` | GitHub release tag and download asset lookup helpers |
| `lib/internet_app_updates.sh` | Per-app update handler routines sourced by `update_internet_apps.sh` |
| `lib/internet_apps.sh` | Canonical internet-app inventory helpers and registry path resolver |
| `lib/internet_handlers.sh` | Shared internet app update handlers, Omaha status evaluation, and launch verification |
| `lib/internet_i18n.sh` | Localized printf message formatting helpers for internet app updaters |
| `lib/internet_registry.sh` | Parser and validator for `config/internet_app_methods.txt` mapping apps to update handlers |
| `lib/internet_status.sh` | Internet app status code mapping and summary report formatting (v1.5.0) |
| `lib/platform.sh` | Supported macOS platform and Apple Silicon architecture guards |
| `lib/proc.sh` | Shared process execution, timeout, and child process management helpers |
| `lib/severity.sh` | Shared severity classification and exit code contract helpers across orchestrator scripts |
| `lib/ui.sh` | Terminal UX helpers: formatting, colors, and TTY-aware progress reporting |
| `lib/version.sh` | Package, bundle, and application version extraction and three-way comparison helpers |
| `lib/vendor_feeds.sh` | Vendor feed lookup and parsing helper |
| `lib/vendor_direct.sh` | Verified vendor direct download, Gatekeeper validation, and atomic swap |
| `lib/python/appstore_lookup.py` | Pure-function helpers for App Store iPad app metadata lookup via iTunes API |
| `lib/python/brew_casks.py` | Pure helpers for Homebrew casks: app targets parsing, orphan cask detection, and sudo privilege detection |
| `lib/python/chronic_warnings.py` | Streak detection for trailing non-OK step runs across historical run summary logs |
| `lib/python/cli_retention.py` | Vendor CLI version retention and pruning helpers |
| `lib/python/system_updates.py` | Pure-function helpers for softwareupdate catalog parsing, label extraction, and reboot classification |
| `lib/python/vendor_feeds.py` | Pure Python vendor feed parsers (Sparkle, JSON, YML, KV, Omaha, VersionHistory) |
| `lib/python/inventory_sync.py` | Synchronization of all inventory groups without drift |
| `config/vendor_feeds.txt` | Vendor truth feed configurations and download host allowlist |
| `config/vendor_direct_first.txt` | Apps that bypass updater launch cycle and install directly from vendor feeds |
| `config/cask_oracles.txt` | Read-only Homebrew Cask version oracle mappings for verifying unverified apps |
| `tests/_env.py` | Helper for test subprocess environments that strips PYTHONPATH so child shell processes do not inherit it |

**Private files** (`.gitignore`d): `APPLICATIONS.md`, `UPDATES.md`, `.env`, `.dev_sync_config.json`

`update_all.sh` supports `--dry-run`, `--yes`, `--verify-only`, `--bootstrap-cli` (explicitly install missing CLI tools), and selective `--skip-*` flags (see `lib/cli.sh`). It evaluates child script step severity: exit 0 indicates clean success, exit 10 indicates soft/degraded results (logged as warnings, non-blocking), and exit 1/127 indicates hard failures (blocking).

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `MAC_UPDATE_BOOTSTRAP_CLI` | `0` | Set to `1` (or pass `--bootstrap-cli`) to install missing native CLIs; by default only installed CLIs are updated |
| `MAC_UPDATE_STAGE_WAIT` | `90` | Seconds to wait for staging/install before verifying an updated bundle (0–600, cykl uruchomienia updatera producenta) |
| `MAC_UPDATE_VENDOR_DIRECT` | `1` | Set to `0` to disable direct vendor installations when apps are behind |
| `MAC_UPDATE_OMAHA_WAIT` | `45` | Timeout (seconds) waiting for Omaha updater response |
| `MAC_UPDATE_OMAHA_MAX_AGE_H` | `6` | Maximum age (hours) of previous Omaha noupdate check to accept as current proof |
| `MAC_UPDATE_APPSTORE_VERIFY_TIMEOUT` | `300` | Timeout (seconds) for post-Track-2 iPad app installation verification (0–1800) |
| `MAC_UPDATE_KEEP_CLI_VERSIONS` | `0` | Set to `1` to disable pruning of old versions for standalone CLIs (Codex, cursor-agent) |
| `MAC_UPDATE_DEBUG` | `0` | Set to `1` to dump full session dir snapshots into the log on clean runs |

## update_all.sh Step Order

```
Step 0: prescan             — scan /Applications + ~/Applications + brew + mas → write installed_apps_scan.txt → atomically update APPLICATIONS.md
Step 1: update_appstore.sh  — Track 1: sudo mas; Track 2: AppleScript GUI for iPad apps
Step 2: update_npm_cli.sh   — native Node/Bun + npm global CLI migration/update + `agy update`
Step 3: update_brew.sh      — formulae + casks (greedy only for brew_cask-designated tokens) + orphan skip + cleanup + doctor
Step 4: update_internet_apps.sh — installed internet apps; direct updates and honest triggers
Step 5: postupdate.py       — capture fresh /Applications to installed_apps_after.txt → refresh APPLICATIONS.md and append UPDATES.md
Step 6: update_system.sh    — macOS via softwareupdate -i <label> -R (per-label no-restart + batch restart); last because it may restart
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

## Production Acceptance

- `docs/agents/acceptance_checklist.md` — Live acceptance paths for v1.5.x covering iPad GUI automation, split system updates, major upgrade guards, orphan casks, vendor direct DMG rollbacks, Chrome staged rollouts, and toolkit-launched application cleanup.
