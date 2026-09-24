---
description: Update internet-downloaded apps — only installed apps from config/internet_apps.txt
---

Run internet app updates (installed apps only):

```bash
cd ~/Dev_Env/macOS_updates && bash update_internet_apps.sh
```

Registry: `config/internet_apps.txt` · Methods: `config/internet_app_methods.txt` · Vendor feeds: `config/vendor_feeds.txt`

Examples (if installed):
- Vendor truth feeds: ChatGPT, Claude, Cursor, Warp, Antigravity, Antigravity IDE, OpenCode, Proton Mail, Docker Desktop, Remote Desktop Manager
- Google Keystone: Chrome, Google Drive, Gemini
- Chromium Updater: Comet
- Mozilla DMG: Firefox Developer Edition
- Microsoft 365: msupdate CLI with package regression guard

Apps not in registry: `bash scripts/report_update_coverage.sh` — add via `scripts/scaffold_internet_app.sh`.
Diagnose vendor feeds read-only: `bash scripts/check_vendor_feeds.sh`.

Does **not** install missing apps.
