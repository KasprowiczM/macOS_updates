---
name: "source-command-mac-status"
description: "Check macOS system status — version, pending updates, disk space, Homebrew health, pending App Store updates"
---

# source-command-mac-status

Use this skill when the user asks to run the migrated source command `mac-status`.

## Command Template

Run the following commands to get a full system status overview:

```bash
echo "=== macOS Version ===" && sw_vers
echo ""
echo "=== Pending macOS Updates ===" && softwareupdate -l
echo ""
echo "=== Disk Space ===" && df -h / | tail -1
echo ""
echo "=== Pending App Store Updates ===" && mas outdated 2>/dev/null || echo "mas not installed"
echo ""
echo "=== Pending Homebrew Updates ===" && brew outdated 2>/dev/null || echo "brew not found"
echo ""
echo "=== Homebrew Health ===" && brew doctor 2>&1 | tail -5
```

Interpret the results:
- `softwareupdate -l` → "No new software available" = up to date
- `mas outdated` → lists App Store apps with available updates
- `brew outdated` → lists Homebrew packages with newer versions available
- `brew doctor` → "Your system is ready to brew." = healthy
- Disk space: update_all.sh needs ≥ 10 GB free

Requires Apple Silicon. Scripts location: `~/Dev_Env/macOS_updates/` (or `$MAC_UPDATE_DIR`).
Inventory: `bash build_inventory.sh` · Coverage: `bash scripts/report_update_coverage.sh`
