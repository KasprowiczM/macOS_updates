---
name: "source-command-mac-update-internet"
description: "Update internet-downloaded apps — only installed apps from config/internet_apps.txt"
---

# source-command-mac-update-internet

Use this skill when the user asks to run the migrated source command `mac-update-internet`.

## Command Template

Run internet app updates (installed apps only):

```bash
cd ~/Dev_Env/macOS_updates && bash update_internet_apps.sh
```

Registry: `config/internet_apps.txt` · Methods: `config/internet_app_methods.txt`

Examples (if installed): Chrome (Keystone), Firefox Dev (GitHub DMG), Codex/Cursor/Warp (silent_launch), Microsoft 365 (msupdate), Docker (CLI).

Apps not in registry: `bash scripts/report_update_coverage.sh` — add via `scripts/scaffold_internet_app.sh`.

Does **not** install missing apps.
