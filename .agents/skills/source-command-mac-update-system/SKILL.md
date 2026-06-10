---
name: "source-command-mac-update-system"
description: "Run macOS system update only (softwareupdate). Uses -R flag to properly apply update during reboot via macOS update framework."
---

# source-command-mac-update-system

Use this skill when the user asks to run the migrated source command `mac-update-system`.

## Command Template

Run the macOS system update script:

```bash
cd ~/Dev_Env/macOS_updates && bash update_system.sh
```

Key behavior:
- Checks for available updates with `softwareupdate -l`
- If restart-required updates are found (e.g. macOS upgrade), prompts user
- Uses `sudo softwareupdate -ia -R --verbose` for every install path
  - The `-R` flag is critical: it routes the restart through the macOS update framework
    so the update is actually applied during boot (unlike `sudo reboot` which bypasses this)
- `-R` only restarts when required; if the user declines a restart-required update, the script exits non-zero instead of installing without `-R`

If the user reports that macOS downloaded an update but it wasn't applied after reboot,
the root cause is missing `-R` flag or using `sudo reboot` instead of softwareupdate's restart.
