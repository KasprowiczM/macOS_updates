---
description: Run full MacBook update — prescan, macOS, App Store, npm CLI, Homebrew, internet apps, postupdate
---

Run the full MacBook update sequence:

```bash
cd ~/Dev_Env/macOS_updates && bash update_all.sh
```

Steps (see VERSION):
0. Prescan → `APPLICATIONS.md` (installed apps on **this** Mac only)
1. App Store (`sudo mas upgrade` + AppleScript GUI for iPad apps)
2. Native CLI + npm global CLI
3. Homebrew formulae & casks (`brew upgrade`)
4. Internet apps (vendor truth feeds & app updaters)
5. Inventory update (`APPLICATIONS.md`, `UPDATES.md`)
6. macOS system (`softwareupdate -i <label> -R`)

Before running, remind the user:
- ≥ 10 GB free disk space
- Stable Wi‑Fi
- Battery ≥ 50% or plugged in
- Time Machine backup recommended

New Mac without inventory: `bash build_inventory.sh` first (or `bash install.sh`).

Coverage report: `bash scripts/report_update_coverage.sh`
