---
description: Update all Homebrew packages — formulae and casks, then run cleanup and doctor
---

Run the Homebrew update script:

```bash
cd ~/Dev_Env/macOS_updates && bash update_brew.sh
```

Steps performed:
1. `brew update` — sync Homebrew package database
2. `brew outdated --formula` and `--cask` — list what needs updating
3. `brew upgrade --formula` — update all CLI tools and libraries
4. `brew upgrade --cask` — update GUI apps installed via Homebrew
5. `brew doctor` — diagnose any issues (exit code ≠ 0 is normal with warnings)
6. `brew cleanup --prune=all` — remove old versions and cached downloads

If `brew: command not found`: run `eval "$(/opt/homebrew/bin/brew shellenv)"` first.
If disk space error: `brew cleanup --prune=all` to free space before upgrading.
