---
description: Update internet-downloaded apps — only installed apps from config/internet_apps.txt
---

Run internet app updates (installed apps only):

```bash
cd ~/Dev_Env/macOS_updates && bash update_internet_apps.sh
```

Registry: `config/internet_apps.txt` · Methods: `config/internet_app_methods.txt`

Examples (if installed): Chrome (Keystone), Firefox Dev (GitHub DMG), Claude/Cursor/Warp (silent_launch), Microsoft 365 (msupdate), Docker (CLI).

Apps not in registry: `bash scripts/report_update_coverage.sh` — add via `scripts/scaffold_internet_app.sh`.

Does **not** install missing apps.
