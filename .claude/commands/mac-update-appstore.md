---
description: Update App Store apps — Track 1 via sudo mas upgrade (native macOS apps), Track 2 via AppleScript GUI automation (iPad apps on Apple Silicon like UniFi, WiFiman)
---

Run the App Store update script:

```bash
cd ~/Dev_Env/macOS_updates && bash update_appstore.sh
```

Two-track strategy:

**Track 1 — `sudo mas upgrade`** (native macOS apps):
Amphetamine, Canva, iMovie, KeePassium, Keynote, NordVPN, Notion Web Clipper,
Numbers, OneDrive, Pages, Perplexity, Prime Video, Telegram, WhatsApp, Xcode, myCANAL

- Requires `sudo mas upgrade` with explicit app IDs
- `mas` auto-installed via Homebrew if not present
- Requires mas ≥ 4.0

**Track 2 — AppleScript GUI automation** (iPad apps on Apple Silicon):
UniFi, WiFiman, Picsart — `mas` officially doesn't support iPad apps.
- **iTunes Lookup Pre-check Gate:** Checks the official App Store iTunes Lookup API first. If all iPad apps are already current, Track 2 GUI automation is cleanly skipped without opening App Store windows.
- When updates are pending, script opens App Store Updates page and clicks "Update All" (or individual Update buttons).

- Requires **Accessibility permission** for your terminal (Terminal.app / Warp / iTerm)
- Script auto-detects missing permission and opens System Settings → Privacy → Accessibility
- One-time setup: add your terminal to the Accessibility list

If mas login error: open App Store manually, sign in, then re-run.
If Track 2 fails after granting Accessibility: restart terminal and re-run.
