# Architecture

This page describes the structural rules of the toolkit (shell, Python, session directory, i18n, cloud sync). Per-release behavior changes that shaped them are summarized under *Recent changes* at the end; `CHANGELOG.md` is the full history.

## Shell
- **Bash 3.2+ only** — no `declare -A`, no `mapfile`, no `readarray`, no bash 4+ features
- **No hardcoded paths** — always `SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"`
- **Apple Silicon + macOS 13+ only** — `lib/platform.sh` exits on non-arm64 or an older system before setup/update mutations
- **Homebrew prefix:** `/opt/homebrew` (arm64)
- **Native CLI toolchain:** keep npm global binaries outside Homebrew, under user-space paths managed by `update_npm_cli.sh` (Note: `/usr/local/bin` and `/opt/homebrew/bin` are appended to `PATH` as low-priority fallback lookup paths for system node managers, without overriding user-space toolchain paths)
- **Internet-app handler contract:** Handlers in `lib/internet_handlers.sh` pass status via `INTERNET_LAST_STATUS` global variable, NEVER returning status via stdout `echo` (which contaminates status when called inside command substitution). Format strings use `internet_msg` rather than raw `printf`.
- **Cask validation interlock:** Entries marked as `brew_cask` in `config/internet_app_methods.txt` are mapped to Homebrew cask names via `internet_cask_name_for_app` and validated against `brew_cask_versions` (`lib/brew.sh`), never a raw `brew list --cask --versions`. Missing casks produce `L_INTERNET_STATUS_CASK_MISSING` soft warning.
- **Version detection:** `app_version()` reads `CFBundleShortVersionString`, then `CFBundleVersion`, then falls back to `mdls -name kMDItemVersion` (covers iOS/iPadOS apps on Apple Silicon that have no `Contents/Info` plist).

## Python
- Update pipeline Python is inline via heredocs written to the session dir, or importable pure-function modules under `lib/python/` (`run_tests.sh` compiles and tests them). Do not add new standalone pipeline entrypoints.
- Existing standalone tools: `dev_sync/` (including `overlay_import.py`) and `scripts/fix_mcp_configs.py`.
- Used for `APPLICATIONS.md` / `UPDATES.md` processing, cloud sync, run summary/lock, and MCP config repair.
- **Atomic private writes:** JSON, inventory and history writes use a same-directory temp file + `os.replace()`; user-owned MCP configs use `mkstemp` in the destination directory with `fchmod` min(original, 0600). Private provider config and logs use restrictive permissions.

## Session Dir
- Path: `mktemp -d "${TMPDIR:-/tmp}/mac_update.XXXXXX"` stored in `$MAC_UPDATE_SESSION_DIR`
- All temp files go here. Guard every use: `[ -n "$MAC_UPDATE_SESSION_DIR" ]`
- The master script registers cleanup traps and uses mode `700` where supported.
- **Key session files:**
  - `toolkit_launched.txt` — Records bundle identifiers and names of applications launched by the toolkit during the update session; used to ensure the toolkit only quits what it launched itself and leaves user-opened apps untouched.
  - `google_omaha_init.txt` — Session-scoped marker indicating Google Keystone / GoogleUpdater daemon was triggered, preventing redundant `--wake-all` wakeups across Chrome, Gemini, and Drive.
  - `brew_cask_targets.txt` — Maps installed Homebrew casks to their `.app` bundle targets (`cask_token|Target.app`) for target validation and downgrade protection.
  - `brew_orphan_casks.txt` — Lists installed Homebrew casks whose `.app` bundles are missing from `/Applications` and `~/Applications`, allowing the pipeline to skip them.
  - `brew_needs_interactive.txt` — Records Homebrew casks requiring administrator/sudo privileges or interactive installers.
  - `appstore_ios_before.txt` / `appstore_ios_after.txt` — Pre- and post-update snapshots of installed iOS/iPadOS applications and versions for Track 2 GUI verification.
  - `appstore_ios_pending.txt` — Tracks iOS/iPadOS apps awaiting installation or verification after Track 2 GUI execution.
  - `internet_status_codes.txt` — Machine-readable status codes (`current_verified`, `current_vendor`, `rollout_hold`, `behind`, `needs_restart`, `feed_stale`, `unverified`, etc.) per internet app for severity and run summary generation.

## Session files and persistent state (2026-11-09)

- `brew_deferred_running.txt` — `cask|App.app` rows for casks deferred because their app was open or its running state unknown.
- `toolkit_launched_at.txt` — `bundle_id|epoch` rows written by `silent_launch_app` next to `toolkit_launched.txt`; `internet_app_quit_gracefully` waits until the app has been up `MAC_UPDATE_QUIT_MIN_AGE` seconds before its first graceful `quit`, so an app that is still starting is never quit.
- `rosetta_missing_apps.txt` — installed Intel-only apps when Rosetta is absent (`internet_rosetta_finalize`).
- `advisories.txt` — `source|severity|text` rows (severity `security` or `info`), appended by steps (currently `brew doctor`) and merged into the run summary's `advisories` field and the final "Advisories" block.
- **Persistent feed state:** `~/.local/state/mac-update/feed_state.json` (`MAC_UPDATE_FEED_STATE_FILE`, mode 0600, same-directory temp + `os.replace`) via `lib/python/feed_state.py`. It outlives the session directory and holds, per app, the last good vendor version/time, a high-water mark and the last error. Corrupt or unknown files load as empty state.
- **Other persistent state** (all under `~/.local/state/mac-update/`, outside the session directory): `package_revisions.tsv` (`MAC_UPDATE_PACKAGE_REVISION_FILE`, same-version package revisions such as KeePassXC `2.8.0-1`) and `mau_quarantine.tsv` (`MAC_UPDATE_MAU_STATE_FILE`, arming time of toolkit-set Office deferrals). `logs/version_history.tsv` and `logs/run_summary_*.json` live in the repository's gitignored `logs/`.
- Run summary stays format 4 with additive fields: top-level `advisories`, `steps.<step>.duration_seconds`, `counts.inventory_entries_added` / `inventory_entries_removed`.
- Pre-flight (`lib/preflight.sh`) runs before step 0 on real runs and keeps the Mac awake with `caffeinate -i -w $$`; `logs/` rotation (`lib/python/log_rotation.py`) also prunes `run_summary_*.json`.

## i18n
- `i18n/loader.sh` reads `MAC_LANG` from `.mac_update_prefs`
- Languages: `en` `pl` `es` `it` `pt` `de` `fr`

## Cloud Sync
- Providers: `protondrive`, `icloud`, `googledrive`, `onedrive`, `mega`, `rclone`, `local`
- GitHub = code + AI context. Cloud = private files.
- Config via `dev_sync/provider_setup.sh`
- Local filesystem **and rclone** exports write `.dev_sync_manifest.json` in the provider mirror; import uses that manifest (a missing rclone manifest is an empty list — no full remote `lsf` fallback).
- Imports go through `dev_sync/overlay_import.py`: directory manifests expand to leaves, Git-tracked and excluded paths are skipped, destination-escaping leaf symlinks are refused, and a failed swap+restore leaves the transaction directory in place (`OverlayRecoveryError`).
- Exclude rebuildable/dependency/external-skill folders from Proton (`node_modules/`, caches, build output, `.agent/skills/`, `.claude/skills/`, `.gemini/skills/`).
- `migration_setup.sh` is idempotent — single source of truth for first-run.

## Data Files
- `APPLICATIONS.md` / `UPDATES.md` are auto-maintained — manual edits will be overwritten

## Recent changes (v1.5.3 to v1.5.5; 1.6.0 is described in `CHANGELOG.md`)

v1.5.5 hardens the master process against toolchain changes made by its own children: every long-lived orchestrator enables `shopt -s checkhash` (and `update_all.sh` runs `hash -r` between steps) so a `python3` link removed by a Homebrew upgrade cannot leave a stale hashed path. Step 5 is reporting-only and never defers macOS updates; a failed summary write relabels the stale `run_status: "started"` file as `"failed"`. Toolkit-launched apps receive a repeated graceful `quit` (`MAC_UPDATE_QUIT_WAIT`, `MAC_UPDATE_QUIT_RESEND`; never force-killed), and soft internet warnings that carry no pending update use their own wording (`L_INTERNET_WARNINGS_ONLY`).

v1.5.4 keeps run-summary format **4** with additive item support: `status="warning"` represents manufacturer evidence issues, and optional `installed_version` / `vendor_version` fields preserve both observations. A stale feed has `old_version=null` and `new_version=null`; it is not an installation target. Consumers that enumerate statuses must recognize `warning`; consumers counting updates continue to filter `status="updated"`. Known per-app warnings suppress duplicate generic Internet warnings, while hard failures and unknown/malformed status input retain the generic diagnostic.

v1.5.3 verifies vendor versions before GUI work and uses direct-first vendor artifacts for ChatGPT. Known current/stale feeds avoid launches; unknown feeds retain the native fallback. The final settle loop runs only for toolkit-launched applications. App-copy transactions check running state before staging and immediately before replacement; unknown state defers without closing user apps.

The CLI step updates existing native installations before Node/npm and uses `lib/python/cli_duplicates.py` to discover redundant npm packages conservatively. Package removal requires native version validation, supported location, PATH ownership and process checks; failed migration retains the fallback.

## Stage B shadow model (1.6.2)

The opt-in shadow path keeps a schema-1 snapshot with source completeness, independent app instances and manager/prefix packages. It uses `${XDG_STATE_HOME:-$HOME/.local/state}/mac-update/inventory.json` (0700 directory, 0600 file); `MAC_UPDATE_STATE_DIR` provides an explicit local override. Store writes use a lock, expected generation, profile/ancestry checks and an atomic replace. Existing state with unsafe ownership, permissions or symlinks is refused, not overwritten.

`MAC_UPDATE_APP_DIRS`, `MAC_UPDATE_BREW_PREFIXES` and `MAC_UPDATE_CLI_PREFIXES` override bounded source roots for isolated testing or explicit configuration. Shell command names are not identities. Incomplete sources preserve prior observations as stale/unobserved. The resolver has no executor and grants no consent. Current legacy aliases and Markdown routing remain until coordinated activation in stage C; the new resolver does not use those aliases.

## Active source-aware execution (1.6.3)

The default inventory builder now uses the shared collector and transactional JSON/Markdown store. Shadow mode is observational once the active generation marker exists. Markdown preserves notes but never controls membership or permission. All app leaf entrypoints require the same immutable action plan; legacy broad dispatch is unreachable. The plan binds its saved base generation, local target identity, source, scope and effects for at most 15 minutes. Version changes alone preserve consent. Recovery runs before collection, and a pending uncertain recovery prevents new consent.

Coverage, Markdown, JSON and the terminal consume the common resolver. Unknown app capabilities are proposals, never executable recipes. Manager execution is deliberately narrow: undeclared dependencies, opaque cask installers, npm lifecycle scripts and global binary changes remain manual. Casks retain their observed app directory. First installation belongs to a separate InstallPlan.
