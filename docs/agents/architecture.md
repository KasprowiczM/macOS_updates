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
- Update pipeline Python is inline via heredocs written to session dir.
- Existing standalone Python is limited to the `dev_sync/` backend and `scripts/fix_mcp_configs.py`.
- Used for `APPLICATIONS.md` / `UPDATES.md` processing, cloud sync, and MCP config repair.
- **Atomic private writes:** JSON, inventory and history writes use a same-directory temp file + `os.replace()`; user-owned MCP configs are copied to `.bak` first. Private provider config and logs use restrictive permissions.

## Session Dir
- Path: `mktemp -d "${TMPDIR:-/tmp}/mac_update.XXXXXX"` stored in `$MAC_UPDATE_SESSION_DIR`
- All temp files go here. Guard every use: `[ -n "$MAC_UPDATE_SESSION_DIR" ]`
- The master script registers cleanup traps and uses mode `700` where supported.

## i18n
- `i18n/loader.sh` reads `MAC_LANG` from `.mac_update_prefs`
- Languages: `en` `pl` `es` `it` `pt` `de` `fr`

## Cloud Sync
- Providers: `protondrive`, `icloud`, `googledrive`, `onedrive`, `mega`, `rclone`, `local`
- GitHub = code + AI context. Cloud = private files.
- Config via `dev_sync/provider_setup.sh`
- Local filesystem exports write `.dev_sync_manifest.json` in the provider mirror; import prefers it to avoid restoring stale provider files.
- Imports are transactional: allowlisted files are copied into a private staging directory, then committed with retained backups and rollback. Rclone imports list and stage individual accepted paths instead of copying the remote tree over the repository.
- Exclude rebuildable/dependency/external-skill folders from Proton (`node_modules/`, caches, build output, `.agent/skills/`, `.claude/skills/`, `.gemini/skills/`).
- `migration_setup.sh` is idempotent — single source of truth for first-run.

## Data Files
- `APPLICATIONS.md` / `UPDATES.md` are auto-maintained — manual edits will be overwritten
