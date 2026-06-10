# Uninstall

macOS Updates is a folder of scripts — uninstall by removing the clone.

```bash
cd ~/Dev_Env/macOS_updates
bash uninstall.sh
```

Use `bash uninstall.sh --purge` to also delete `.mac_update_prefs` inside the repo.

## What is removed

- The repository directory (`~/Dev_Env/macOS_updates` by default)
- Optional local language prefs (with `--purge`)

## What is **not** removed

- Homebrew, `mas`, Python, or other tools installed by `setup.sh`
- Any applications on your Mac
- Private files in cloud storage (`APPLICATIONS.md`, `UPDATES.md`, `.env`)
- Logs under `logs/` if you copied them elsewhere

## Manual removal

```bash
rm -rf ~/Dev_Env/macOS_updates
```

To remove Homebrew itself (optional, unrelated to this project):

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/uninstall.sh)"
```
