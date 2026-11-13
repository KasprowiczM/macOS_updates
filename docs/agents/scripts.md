# Scripts Reference

| Script | Purpose |
|--------|---------|
| `install.sh` | Clone, language, readiness inspection, inventory and coverage when Python 3.9+ is usable; exit 10 for incomplete readiness |
| `uninstall.sh` | Remove repo clone (optional `--purge` prefs) |
| `build_inventory.sh` | Read-only scan — atomically refresh `APPLICATIONS.md` (apps, Homebrew and native CLI versions) without adding update history |
| `setup.sh` | Read-only readiness by default or `--inspect`; explicit dependency and shell-profile consent flags |
| `migration_setup.sh` | First-run (owner) — phases 0a–16: language, cloud, deps, paths, app scan |
| `update_all.sh` | Master: prescan → App Store → npm CLI → Homebrew → internet apps → postupdate/history → macOS final |
| `update_system.sh` | per-label `softwareupdate -i <label> -R`, restart-required labels in one final batch |
| `update_appstore.sh` | `sudo mas upgrade` + AppleScript GUI for iPad apps |
| `update_internet_apps.sh` | Installed internet apps (see `config/internet_apps.txt`): verified direct handlers, vendor CLIs and honestly reported in-app updater triggers |
| `update_npm_cli.sh` | Existing native CLIs first, then Node/Bun and npm fallbacks; conservative redundant npm cleanup after native validation |
| `update_brew.sh` | `brew upgrade` + cleanup + doctor |
| `lib/brew.sh` | Resilient Homebrew queries: `brew_cask_versions`, `brew_formula_versions`, `brew_outdated_formulae`, `brew_outdated_casks` |
| `lib/python/inventory.py` | Pure Python library for inventory normalization, exclusions, and prescan |
| `lib/python/run_summary.py` | Pure Python library for building machine-readable run summary JSON (format 4) |
| `lib/python/cli_duplicates.py` | Known-prefix npm duplicate discovery and version/process guards for native CLI cleanup |
| `lib/python/http_fetch.py` | HTTPS download helper used by tests and the fetch adapter |
| `lib/python/log_rotation.py` | Rotation of `logs/`: run logs, `run_summary_*.json` (including stray names), stale temp files; never `run_summary_latest.json` / `version_history.tsv` |
| `lib/python/run_lock.py` | Exclusive run lock (`.mac-update.lock`); `kill(pid,0)` EPERM counts as alive |
| `lib/fetch.sh` | HTTPS-only download with emptiness and size checks (no curl-pipe-to-sh) |
| `lib/native_installers.sh` | Per-vendor CLI install/update (Claude positional `latest`, Codex `--release latest`, OpenCode repair) |
| `lib/run_lock.sh` | Shell wrapper for the Python run lock |
| `dev_sync/overlay_import.py` | Overlay import planner: expand directory manifests, skip Git/excluded, refuse symlink escapes |
| `config/inventory_exclusions.txt` | Explicit list of apps to ignore during inventory scans (e.g. `Ascendo`) |
| `dev_sync/*.sh` | Export/import/verify private files to/from cloud storage |
| `scripts/check_vendor_feeds.sh` | Read-only diagnostic query of vendor feeds and Omaha updaters (table and `--json`) |
| `scripts/report_update_coverage.sh` | Report installed vs supported vs unknown apps (by method category) |
| `scripts/setup_touchid_sudo.sh` | Optional standalone Touch ID configuration with terminal consent, preview binding, mandatory backup and exclusive PAM creation; foreign files refused |
| `scripts/install_launchagent.sh` | Install and manage weekly launchd update schedule; sets `EnvironmentVariables.PATH`, verifies the service is loaded with `launchctl print`, `--check` warns about plists without the `PATH` key; options `--day N`, `--hour N`, `--minute N` (0-59), `--once-in N` (one-shot test run 1-1440 minutes from now, exclusive with the weekly options), `--check`, `--uninstall`; `--day/--hour/--minute` set the weekly time, `--once-in N` installs a one-shot test run N minutes from now |
| `scripts/audit_cask_candidates.sh` | Audit installed internet apps against Homebrew Cask availability |
| `scripts/scan_update_feeds.sh` | Scan installed apps for Sparkle, Electron, and Keystone update frameworks |
| `scripts/scaffold_internet_app.sh` | Generate config entries and handler boilerplate for new internet apps |
| `scripts/report_chronic_warnings.sh` | Print trailing non-OK step streaks from historical run summaries (`lib/python/chronic_warnings.py`) |
| `scripts/scan_secrets.sh` | Lightweight secret scan used by CI and pre-push (gitleaks when installed) |
| `scripts/pre-commit.sh` | Fast staged-file checks (`bash -n`, `py_compile`); the full suite stays the integration gate |
| `scripts/fix_mcp_configs.py` | Repair user MCP configs (absolute `npx` path and `PATH` env); `fix_mcp_all.sh` applies it globally |
| `scripts/fix_inventory_dedup.py` | One-off inventory de-duplication helper |
| `scripts/migrate_internet_i18n.py` | One-shot migrator that moved Polish literals in `update_internet_apps.sh` into `L_INTERNET_*` keys (historical) |
| `lib/appstore_ios.sh` | iOS and iPad app detection and App Store lookup helpers (Bash 3.2+) |
| `lib/cli.sh` | Shared CLI flag parsing and usage definitions for orchestrators |
| `lib/github_release.sh` | GitHub release tag and download asset lookup helpers |
| `lib/internet_app_updates.sh` | Per-app update handler routines sourced by `update_internet_apps.sh` |
| `lib/internet_apps.sh` | Canonical internet-app inventory helpers and registry path resolver |
| `lib/internet_handlers.sh` | Shared internet app update handlers, Omaha status evaluation, and launch verification |
| `lib/internet_i18n.sh` | Localized printf message formatting helpers for internet app updaters |
| `lib/internet_registry.sh` | Parser and validator for `config/internet_app_methods.txt` mapping apps to update handlers |
| `lib/internet_status.sh` | Internet app status code mapping and summary report formatting (v1.5.0) |
| `lib/platform.sh` | Supported macOS platform and Apple Silicon architecture guards; `mac_update_ensure_homebrew_path` (runs when sourced) puts Homebrew on `PATH` for launchd runs |
| `lib/proc.sh` | Shared process execution, timeout, and child process management helpers |
| `lib/severity.sh` | Shared severity classification and exit code contract helpers across orchestrator scripts |
| `lib/ui.sh` | Terminal UX helpers: formatting, colors, and TTY-aware progress reporting |
| `lib/preflight.sh` | Read-only readiness checks: `update_all.sh --doctor` (exit 0/10/1) and the cheap pre-run subset (disk, power, network) with `caffeinate` policy |
| `lib/version.sh` | Package, bundle, and application version extraction and three-way comparison helpers |
| `lib/vendor_feeds.sh` | Vendor feed lookup and parsing helper |
| `lib/vendor_direct.sh` | Verified vendor direct download, Gatekeeper validation, and atomic swap |
| `lib/python/appstore_lookup.py` | Pure-function helpers for App Store iPad app metadata lookup via iTunes API |
| `lib/python/brew_casks.py` | Pure helpers for Homebrew casks: app targets parsing, orphan cask detection, and sudo privilege detection |
| `lib/python/chronic_warnings.py` | Streak detection for trailing non-OK step runs across historical run summary logs |
| `lib/python/node_releases.py` | Newest stable Node.js release from `nodejs.org/dist/index.json`; alpha/rc/nightly builds are never install targets |
| `lib/python/cli_retention.py` | Vendor CLI version retention and pruning helpers |
| `lib/python/system_updates.py` | Pure-function helpers for softwareupdate catalog parsing, label extraction, and reboot classification |
| `lib/python/vendor_feeds.py` | Pure Python vendor feed parsers (Sparkle, JSON, YML, KV, Omaha text log + `updater_history.jsonl`, VersionHistory) |
| `lib/python/feed_state.py` | Persistent per-app vendor feed state (last good version, high-water mark): cached proof on a failed fetch, vendor-side feed regressions; atomic 0600 writes |
| `lib/python/setup_safety.py` | Preview fingerprints, regular-file-only shell appends and backup-first PAM changes; no subprocess execution |
| `lib/python/inventory_sync.py` | Synchronization of all inventory groups without drift |
| `config/bun_version.txt` | Minimum floor version for Bun (`update_npm_cli.sh`) |
| `config/npm_global_clis.txt` | `display_name\|package\|method\|brew_formula\|command` rows for the managed CLI toolchain (npm, self-update, native installer, `n`, `bun upgrade`) |
| `config/vendor_feeds.txt` | Vendor truth feed configurations and download host allowlist |
| `config/vendor_appcasts.txt` | Sparkle appcasts used only to prove an installed rollout-channel build is a published vendor release (never an install source) |
| `config/vendor_direct_first.txt` | Apps that bypass updater launch cycle and install directly from vendor feeds (Cursor, OpenCode, ChatGPT, Proton Mail/Drive, HyperFrames, Superset) |
| `config/vendor_launch_policy.txt` | Apps the toolkit never launches: `direct-only` (HyperFrames, Superset: verified vendor artifact only, no launch fallback) and `never-launch` (Open Design: verify only, "open the app to update") |
| `config/cask_oracles.txt` | Read-only Homebrew Cask version oracle mappings for verifying unverified apps |
| `tests/_env.py` | Helper for test subprocess environments that strips PYTHONPATH so child shell processes do not inherit it |

**Private files** (`.gitignore`d): `APPLICATIONS.md`, `UPDATES.md`, `.env`, `.dev_sync_config.json`

`update_all.sh` supports `--doctor` (read-only readiness report: no sudo, no run log, no summary; exit 0 ok / 10 warnings / 1 hard problem), `--dry-run`, `--yes`, `--verify-only`, `--bootstrap-cli` (explicitly install missing CLI tools), and selective `--skip-*` flags (see `lib/cli.sh`). It evaluates child script step severity: exit 0 indicates clean success, exit 10 indicates soft/degraded results (logged as warnings, non-blocking), and exit 1/127 indicates hard failures (blocking).

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `MAC_UPDATE_BOOTSTRAP_CLI` | `0` | Set to `1` (or pass `--bootstrap-cli`) to install missing native CLIs; by default only installed CLIs are updated |
| `MAC_UPDATE_STAGE_WAIT` | `90` | Seconds to wait for staging/install before verifying an updated bundle (0–600; covers the launched vendor updater's staging cycle) |
| `MAC_UPDATE_VENDOR_DIRECT` | `1` | Set to `0` to disable direct vendor installations when apps are behind |
| `MAC_UPDATE_OMAHA_WAIT` | `45` | Timeout (seconds) waiting for Omaha updater response |
| `MAC_UPDATE_OMAHA_MAX_AGE_H` | `6` | Maximum age (hours) of a previous Chromium-updater check (from `updater_history.jsonl`, same build as installed) accepted as current proof — the updater is then not woken |
| `MAC_UPDATE_APPSTORE_VERIFY_TIMEOUT` | `300` | Timeout (seconds) for post-Track-2 iPad app installation verification (0–1800) |
| `MAC_UPDATE_APP_DIRS` | `/Applications:$HOME/Applications` | Colon-separated list of application directories for scanning (used in tests and hermetic CI runs) |
| `MAC_UPDATE_KEEP_CLI_VERSIONS` | `0` | Set to `1` to disable pruning of old versions for standalone CLIs (Codex, cursor-agent) |
| `MAC_UPDATE_QUIT_WAIT` | `60` | Seconds (0–300) a toolkit-launched app gets to exit after the graceful `quit`; the AppleScript `quit` is re-sent while it keeps running, never force-killed (v1.5.5) |
| `MAC_UPDATE_QUIT_RESEND` | `10` | Interval in seconds (1–60) between repeated graceful `quit` requests inside `MAC_UPDATE_QUIT_WAIT` (v1.5.5) |
| `MAC_UPDATE_QUIT_MIN_AGE` | `30` | Seconds (0–300) a toolkit-launched app must have been running before the toolkit sends its first graceful `quit` (launch times in `toolkit_launched_at.txt`, 2026-11-10) |
| `MAC_UPDATE_PACKAGE_REVISION_FILE` | `~/.local/state/mac-update/package_revisions.tsv` | Package revision installed per product+version (`KeePassXC\|2.8.0\|1`); detects same-version vendor rebuilds |
| `MAC_UPDATE_FEED_STATE_FILE` | `~/.local/state/mac-update/feed_state.json` | Per-app vendor feed state (last successful version + time, high-water mark, last error); never an install source |
| `MAC_UPDATE_FEED_CACHE_TTL_H` | `24` | Hours (0–168, 0 disables) a successful feed check that listed the installed version stays valid proof when the feed is unreachable — the app is then reported current from the cached check and not launched |
| `MAC_UPDATE_MIN_FREE_GB` | `15` | Pre-flight / `--doctor`: warn (degraded run) when free space on the system volume is below this many GB |
| `MAC_UPDATE_MIN_BATTERY` | `30` | Pre-flight: on battery below this percent the macOS system step is skipped softly (other steps run) |
| `MAC_UPDATE_NO_CAFFEINATE` | `0` | Set to `1` to not run `caffeinate -i -w $$` for the duration of a real run |
| `MAC_UPDATE_SUDO_KEEPALIVE_MAX` | `14400` | Seconds after which the sudo keep-alive stops refreshing (clamped 300-14400); it also stops as soon as the parent shell is gone |
| `MAC_UPDATE_PARENT_CONFIRMED` | unset | Exported as `1` by `update_all.sh` once its master confirmation succeeded; children skip their own redundant confirmation |
| `MAC_UPDATE_DOCTOR_PROBE_AX` | `0` | `--doctor` only: set to `1` to probe Accessibility with `osascript` (can show a macOS permission prompt) |
| `MAC_UPDATE_PREFLIGHT_NET_RETRIES` | `3` | Extra network probe passes before a real run aborts for "no network" (clamp 1-10); `--doctor` does one pass |
| `MAC_UPDATE_PREFLIGHT_NET_RETRY_WAIT` | `10` | Seconds between those passes (clamp 0-60; tests use 0) |
| `MAC_UPDATE_PREFLIGHT_HOSTS` | `api.github.com formulae.brew.sh itunes.apple.com` | HTTPS hosts probed by pre-flight / `--doctor` (test override) |
| `MAC_UPDATE_PROMPT_TIMEOUT` | `120` | Seconds (clamp 10-900, 0 = wait forever) a mid-run yes/no prompt waits (`mac_update_prompt_yn`, `lib/ui.sh`); a timeout is a safe "no" |
| `MAC_UPDATE_HOMEBREW_PREFIX` | `/opt/homebrew` | Test-only override of the prefix `mac_update_ensure_homebrew_path` adds to `PATH` |
| `MAC_UPDATE_DEBUG` | `0` | Set to `1` to dump full session dir snapshots into the log on clean runs |
| `MAC_UPDATE_NONINTERACTIVE` | `0` | Never prompt; skips App Store Track 2 GUI automation (flag `--non-interactive`; the LaunchAgent sets it) |
| `MAC_UPDATE_NOTIFY` | `0` | Desktop notification when the run finishes (flag `--notify`; the LaunchAgent sets it) |
| `MAC_UPDATE_NO_SUDO` | set automatically | Exported by `update_all.sh` when sudo would be needed (App Store or macOS step enabled, not a dry run) but there is no TTY; child scripts skip root-only tracks and report soft (`10`) |
| `MAC_UPDATE_NO_SUDO_KEEPALIVE` | `0` | Set to `1` to disable the background sudo timestamp refresher |
| `MAC_UPDATE_ALLOW_MAJOR_UPGRADE` | `0` | Set to `1` to allow an explicitly confirmed major macOS upgrade; otherwise major releases are skipped (`update_system.sh`) |
| `MAC_UPDATE_TREAT_APPSTORE_AX_AS_WARNING` | `0` | Treat App Store exit `2` (missing Accessibility) as a warning (flag `--treat-appstore-ax-as-warning`) |
| `MAC_UPDATE_STALE_DAYS` | `45` | Days an unverified `silent_launch` app may stay unchanged before the internet step reports it as stale (`update_internet_apps.sh`) |
| `MAC_UPDATE_MAX_LOGS` | `30` | Number of `update_all_*.log` files kept in `logs/` (run summaries rotate too) |
| `MAC_UPDATE_INTERNET_SETTLE_SECONDS` | `15` | Pause that lets a launched vendor updater rewrite `Info.plist` (`0` disables, clamped to 120; skipped when no app was launched) |
| `MAC_UPDATE_MAS_CHECK_TIMEOUT` | `120` | Timeout in seconds for `mas outdated` |
| `MAC_UPDATE_MAS_UPGRADE_TIMEOUT` | `1800` | Timeout in seconds for `sudo mas upgrade` |
| `MAC_UPDATE_APPSTORE_GUI_TIMEOUT` | `180` | Timeout in seconds for one App Store Track 2 GUI attempt |
| `MAC_UPDATE_MSUPDATE_CHECK_TIMEOUT` | `120` | Timeout in seconds for `msupdate --list` |
| `MAC_UPDATE_MSUPDATE_INSTALL_TIMEOUT` | `1800` | Timeout in seconds for `msupdate --install` |
| `MAC_UPDATE_NATIVE_INSTALLER_TIMEOUT` | `360` | Timeout in seconds for a vendor native CLI installer (`lib/native_installers.sh`) |
| `MAC_UPDATE_MAU_DEFERRAL_DAYS` | `7` | Microsoft AutoUpdate quarantine window in days (clamped to Microsoft's 1-28) |
| `MAC_UPDATE_MAU_QUARANTINE_MAX_DAYS` | `14` | Maximum age in days (1-90) of a toolkit-armed Office quarantine before it is released |
| `MAC_UPDATE_MAU_KEEP_DEFERRALS` | `0` | Set to `1` to make the toolkit never touch MAU deferral preferences |
| `MAC_UPDATE_MAU_CLEAR_DEFERRALS` | `0` | Set to `1` to remove active deferrals via `defaults delete` (test feed recovery, clear a stale quarantine) |
| `MAC_UPDATE_MAU_IDLE_TIMEOUT` | `15` | Seconds to wait for Microsoft AutoUpdate to become idle before `msupdate` calls |
| `MAC_UPDATE_BREW_LINK_OVERWRITE` | `0` | Set to `1` only for an explicit recovery run: allow `brew link --overwrite` for kegs whose links failed |
| `MAC_UPDATE_INSTALL_ROSETTA` | `0` | Set to `1` to let the Intel-only app preflight run `softwareupdate --install-rosetta`; never installs by default |
| `MAC_UPDATE_NVM_OWNS_NODE` | `0` | Set to `1` to hand Node/npm back to nvm deliberately instead of the managed toolchain |
| `MAC_UPDATE_TOOLCHAIN_HOME` | `~/.local/share/mac-update` | Root of the managed Node/npm/Bun toolchain |
| `MAC_UPDATE_MAX_PROFILE_BACKUPS` | `5` | Shell profile backups kept when `update_npm_cli.sh` rewrites its PATH block |
| `MAC_UPDATE_SKIP_PROFILE_SCAN` | `0` | Set to `1` to skip the shell-profile scan (CI has no profiles) |
| `MAC_UPDATE_CHRONIC_WINDOW` | `10` | Number of recent run summaries `scripts/report_chronic_warnings.sh` inspects |
| `MAC_UPDATE_CHRONIC_THRESHOLD` | `3` | Minimum trailing non-OK streak that `scripts/report_chronic_warnings.sh` reports |
| `MAC_UPDATE_REPO / `MAC_UPDATE_REF` / `MAC_UPDATE_DIR` / `MAC_UPDATE_LANG`` | see `install.sh` | `install.sh` only: clone URL, tag/branch/SHA to check out, clone directory (default `~/Dev_Env/macOS_updates`) and language picker bypass |
| `MAC_UPDATE_NPX_PATH` / `MAC_UPDATE_NODE_PATH` | unset | `scripts/fix_mcp_configs.py`: override the `npx` / `node` path written into MCP configs |

Flag equivalents (`MAC_UPDATE_DRY_RUN`, `MAC_UPDATE_YES`, `MAC_UPDATE_VERIFY_ONLY`, `MAC_UPDATE_JSON_SUMMARY`, `MAC_UPDATE_SKIP_<STEP>`, ...) are set by `lib/cli.sh`. Variables not listed above are internal state exported between scripts (`MAC_UPDATE_SESSION_DIR`, `MAC_UPDATE_RESULT_*`, `MAC_UPDATE_RUN_STATUS`, ...) or test-only path overrides (`MAC_UPDATE_APPS_DIR`, `MAC_UPDATE_CLT_DIR`, `MAC_UPDATE_ROSETTA_DIR`, `MAC_UPDATE_PAM_SUDO*`, `MAC_UPDATE_MAU_APP` / `_CLI` / `_PREFS_FILE` / `_STATE_FILE`, `MAC_UPDATE_GOOGLE_*`, `MAC_UPDATE_DISK_PATH`, `MAC_UPDATE_FORCE_TIMEOUT_FALLBACK`, `MAC_UPDATE_MOCK_ACTIVE_PROCESSES`, `MAC_UPDATE_LAUNCHAGENT_NOW_EPOCH`) and are not a stable interface.

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

If any of steps 1–4 encounters a hard failure (`BLOCKING_EXIT`), step 6 (`softwareupdate`) is deferred to avoid rebooting into a broken state. Steps 0 and 5 are read-only/reporting and never block. Soft warnings (`exit 10`) surface in reporting while allowing system updates to proceed. See [exit_codes.md](exit_codes.md).

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
Phase  7: Check/install mas ≥4.0 (required for macOS 26.x; see the entitlement-change note in critical_rules.md)
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

## Stage B shadow inventory (1.6.2)

`build_inventory.sh --shadow` invokes the importable `lib/python/inventory_shadow.py` module directly and never enters `update_all.sh`. New modules: `lib/python/inventory_model.py` (schema), `lib/python/inventory_collect.py` (bounded observations and reconciliation), `lib/python/inventory_providers.py` (static manager metadata and bounded mas query), `lib/python/inventory_store.py` (private JSON and generation checks), `lib/python/app_recipes.py` (strict declarative catalog) and `lib/python/source_resolver.py` (pure decisions). `brew_casks.installed_inventory_source` and `brew_inventory_snapshot_json` expose the shared static Homebrew provider.

`--shadow --dry-run` observes without writing state. `--json` emits machine-readable decisions. Repeated `--root PATH` replaces the default scan roots. No vendor feed, application, npm script, Ruby cask or updater is executed. An explicit `mas list --json` query has a ten-second timeout. Normal build/update entrypoints retain stage A behavior until stage C activation.
