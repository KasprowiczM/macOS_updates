# Architecture

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
- **Key session files used in v1.5.0:**
  - `toolkit_launched.txt` — Records bundle identifiers and names of applications launched by the toolkit during the update session; used to ensure the toolkit only quits what it launched itself and leaves user-opened apps untouched.
  - `google_omaha_init.txt` — Session-scoped marker indicating Google Keystone / GoogleUpdater daemon was triggered, preventing redundant `--wake-all` wakeups across Chrome, Gemini, and Drive.
  - `brew_cask_targets.txt` — Maps installed Homebrew casks to their `.app` bundle targets (`cask_token|Target.app`) for target validation and downgrade protection.
  - `brew_orphan_casks.txt` — Lists installed Homebrew casks whose `.app` bundles are missing from `/Applications` and `~/Applications`, allowing the pipeline to skip them.
  - `brew_needs_interactive.txt` — Records Homebrew casks requiring administrator/sudo privileges or interactive installers.
  - `appstore_ios_before.txt` / `appstore_ios_after.txt` — Pre- and post-update snapshots of installed iOS/iPadOS applications and versions for Track 2 GUI verification.
  - `appstore_ios_pending.txt` — Tracks iOS/iPadOS apps awaiting installation or verification after Track 2 GUI execution.
  - `internet_status_codes.txt` — Machine-readable status codes (`current_verified`, `current_vendor`, `rollout_hold`, `behind`, `needs_restart`, `feed_stale`, `unverified`, etc.) per internet app for severity and run summary generation.

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
