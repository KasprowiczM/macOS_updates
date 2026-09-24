---
description: Run macOS system update only (softwareupdate). Uses -R flag to properly apply update during reboot via macOS update framework.
---

Run the macOS system update script:

```bash
cd ~/Dev_Env/macOS_updates && bash update_system.sh
```

Key behavior:
- Checks for available updates with `softwareupdate -l`
- Classifies updates into non-restart and restart-required labels
- Installs non-restart updates individually: `sudo softwareupdate -i "<label>" -R --verbose`
- Installs all restart-required updates in one batch call: `sudo softwareupdate -i "<label1>" "<label2>" -R --verbose`
- The `-R` flag is critical: it routes the restart through the macOS update framework
  so the update is actually applied during boot (unlike `sudo reboot` which bypasses this)
- `-R` only restarts when required; if the user declines a restart-required update, the script exits non-zero instead of installing without `-R`

If the user reports that macOS downloaded an update but it wasn't applied after reboot,
the root cause is missing `-R` flag or using `sudo reboot` instead of softwareupdate's restart.
