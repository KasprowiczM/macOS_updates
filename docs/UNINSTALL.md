# Uninstall

**macOS Updates 2.0.10.** Removing it never touches your apps.

## Steps

```bash
mac-update uninstall
```

It lists what it will remove, asks whether to keep your settings and whether to keep logs, and asks for a final confirmation. It never uses `sudo`.

It refuses to run while the installer is running; wait for it to finish and try again.

Useful options:

| Option | Meaning |
|--------|---------|
| `--dry-run` | Show what would be removed. Removes nothing. |
| `--yes` | Do not ask. Keeps your settings and removes the logs folder. |
| `--purge` | Also remove your settings folder. |
| `--keep-state` | Keep logs, caches and backups. |
| `--keep-config` | Keep your settings (the default). |
| `--purge-tools` | Also remove the Node.js and npm tools mac-update manages (`node/` and `npm-global/` in the program folder). Kept by default. |

Example: `mac-update uninstall --dry-run`, then `mac-update uninstall`.

## What is removed

- Any scheduled run (automatic run) that belongs to mac-update, stopped first.
- The commands `~/.local/bin/mac-update` and `~/.local/bin/macos-update`, only if they are mac-update's own links. A file with that name that is not ours is left alone.
- The program files in `~/.local/share/mac-update`, its `.previous` copy and leftovers of an interrupted upgrade. `node/` and `npm-global/` stay unless you use `--purge-tools`.
- The state folder `~/.local/state/mac-update` (logs, caches, backups), unless you keep it.
- Your settings folder `~/.config/mac-update` only with `--purge` or if you answer no to keeping it.

## What is not removed

- Your apps, Homebrew, `mas`, Python or any other tool.
- The Node.js and npm tools mac-update manages (`node/` and `npm-global/` in the program folder), because your `PATH` may use them. The uninstaller says so when it keeps them. Add `--purge-tools` to remove them too.
- Any `node.older.<time>` or `npm-global.older.<time>` copy an upgrade set aside in the program folder. They are kept the same way; delete them yourself if you like.
- Your shell profile. If you let the installer add `~/.local/bin` to `PATH`, a small block between `# >>> mac-update >>>` and `# <<< mac-update <<<` stays. Delete those lines if you like.
- A Touch ID setting for `sudo`, if you configured one. Undo it with `bash scripts/setup_touchid_sudo.sh --uninstall` from the program folder before uninstalling.

## If `mac-update` does not run

```bash
bash ~/.local/share/mac-update/uninstall.sh
```

As a last resort, remove the folders yourself: `~/.local/share/mac-update` (this also deletes its `node/` and `npm-global/`), `~/.local/state/mac-update`, optionally `~/.config/mac-update`, and the links `~/.local/bin/mac-update` and `~/.local/bin/macos-update`. Turn off scheduled runs first with `bash ~/.local/share/mac-update/scripts/install_launchagent.sh --uninstall`.

See also [INSTALL.md](INSTALL.md).
