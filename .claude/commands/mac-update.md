---
description: Run full MacBook update — prescan, macOS, App Store, npm CLI, Homebrew, internet apps, postupdate
---

Run the full MacBook update sequence:

```bash
cd ~/Dev_Env/macOS_updates && bash update_all.sh
```

Steps (v1.0.17):
0. Prescan → `APPLICATIONS.md` (installed apps on **this** Mac only)
1. macOS (`softwareupdate -ia -R`)
2. App Store (`sudo mas upgrade` + AppleScript for iPad apps)
3. Native Node/Bun + npm global CLI
4. Homebrew upgrade + cleanup
5. Internet apps (only if installed — see `config/internet_apps.txt`)
6. Postupdate → `APPLICATIONS.md`, `UPDATES.md`

Before running, remind the user:
- ≥ 10 GB free disk space
- Stable Wi‑Fi
- Battery ≥ 50% or plugged in
- Time Machine backup recommended

New Mac without inventory: `bash build_inventory.sh` first (or `bash install.sh`).

Coverage report: `bash scripts/report_update_coverage.sh`
