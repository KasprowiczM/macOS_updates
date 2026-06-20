# Architecture

## Shell
- **Bash 3.2+ only** — no `declare -A`, no `mapfile`, no `readarray`, no bash 4+ features
- **No hardcoded paths** — always `SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"`
- **Apple Silicon only** — `lib/platform.sh` exits on non-arm64
- **Homebrew prefix:** `/opt/homebrew` (arm64)
- **Native CLI toolchain:** keep npm global binaries outside Homebrew, under user-space paths managed by `update_npm_cli.sh`
- **Internet-app bundle replacement:** `copy_verified_app` quits the running app, copies with `ditto` (not `cp -R`) to a staging path, swaps in atomically with `mv`, and `spctl`-verifies before and after. Status reporting is honest — `LAUNCHED_UNVERIFIED` / `LAUNCH_FAILED` / `CURRENT` / `UPDATED`, never an unconditional "checked".
- **Version detection:** `app_version()` reads `CFBundleShortVersionString`, then `CFBundleVersion`, then falls back to `mdls -name kMDItemVersion` (covers iOS/iPadOS apps on Apple Silicon that have no `Contents/Info` plist).

## Python
- Update pipeline Python is inline via heredocs written to session dir.
- Existing standalone Python is limited to the `dev_sync/` backend and `scripts/fix_mcp_configs.py`.
- Used for `APPLICATIONS.md` / `UPDATES.md` processing, cloud sync, and MCP config repair.
- **Atomic config writes:** JSON writes (`dev_sync/`, `scripts/fix_mcp_configs.py`) use a temp file + `os.replace()`; user-owned configs (`~/.claude.json`, MCP) are copied to `.bak` first.

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
- Exclude rebuildable/dependency/external-skill folders from Proton (`node_modules/`, caches, build output, `.agent/skills/`, `.claude/skills/`, `.gemini/skills/`).
- `migration_setup.sh` is idempotent — single source of truth for first-run.

## Data Files
- `APPLICATIONS.md` / `UPDATES.md` are auto-maintained — manual edits will be overwritten
