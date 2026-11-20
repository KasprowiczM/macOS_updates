# Installation

**macOS Updates 2.0.10** · Apple Silicon Mac (arm64) · macOS 13 or later · Website: <https://macos-updates.64bit.site>

Installing does not update any app. It puts the program on your Mac and adds the `mac-update` command (also under the longer name `macos-update`).

## Requirements

| Need | Notes |
|------|-------|
| Apple Silicon Mac, macOS 13 or later | Intel Macs are not supported. The installer stops before changing anything. |
| Python 3.9 or later | If it is missing, run `xcode-select --install` and then the installer again. The installer never starts that for you. |
| Internet access | To download the release package from GitHub. |
| Homebrew (Apple Silicon, `/opt/homebrew`) | Needed for the Homebrew group. An Intel Homebrew in `/usr/local` does not count and is never touched. |
| `mas` 4.1 or later | Needed for the App Store group. |

You do not need `git` and you do not need `sudo` to install.

### Preparing the Mac

`mac-update doctor` lists every requirement as present, missing, wrong architecture or too old, and which update groups depend on it. `mac-update prepare` (also `mac-update doctor --fix`, or the Diagnostics screen) installs what is missing after one confirmation: Command Line Tools, then Homebrew for Apple Silicon (this one needs your administrator password), then Python if the Command Line Tools one is not usable, then `mas`. `--yes` skips the question; without a terminal and without `--yes` nothing is changed. It is safe to run again. Not installable automatically, and shown with a hint: the Accessibility permission for your terminal, App Store sign-in, Rosetta and Touch ID for sudo.

## Install

```bash
/bin/bash -c "$(curl -fsSL https://github.com/KasprowiczM/macOS_updates/releases/latest/download/install.sh)"
```

The installer:

1. Checks that this is an Apple Silicon Mac with macOS 13 or later and that Python 3.9 or later is available.
2. Finds the latest release and downloads the package and its `SHA256SUMS` file.
3. Checks the package against its SHA-256 checksum. If it does not match, nothing is installed.
4. Unpacks it next to the target folder and swaps it in. The program folder is `~/.local/share/mac-update`. If it already holds the Node.js and npm tools mac-update manages (`node/` and `npm-global/`), the installer accepts it and leaves them where they are; only the program's own files are replaced.
5. Links `~/.local/bin/mac-update` and `~/.local/bin/macos-update` (the same command under a longer name) to the program. An existing file there that is not from mac-update is left alone.
6. Tells you whether `~/.local/bin` is on your `PATH`, and warns, naming that program's file, when another program on your `PATH` answers to `mac-update` or `macos-update`.

It never touches your settings, never edits a shell profile unless you ask, never uses `sudo`, and asks no questions.

Options. When you use the one-liner, put them after `bash -s --`, for example `... install.sh | bash -s -- --dry-run`:

| Option | Meaning |
|--------|---------|
| `--dry-run` | Print what would happen. Writes nothing and uses no network. |
| `--version X` | Install release `X` instead of the latest. |
| `--configure-shell` | Add `~/.local/bin` to `PATH` in your zsh or bash profile (a small marked block). |
| `--dir DIR` | Use another program folder. |
| `--quiet` | Print only warnings and errors. |
| `-h`, `--help` | Show the options. |

Environment variables (optional): `MAC_UPDATE_HOME` (program folder), `MAC_UPDATE_INSTALL_VERSION` (same as `--version`), `NO_COLOR`.

Exit codes: 0 done, 1 failed, 2 wrong usage, 3 this Mac is missing a prerequisite.

## Verifying a download by hand

If you download the package yourself instead of using the one-liner, open the release page, download `mac-update-X.Y.Z.tar.gz` and `SHA256SUMS` into the same folder and run:

```bash
shasum -a 256 -c SHA256SUMS
```

It must print `mac-update-X.Y.Z.tar.gz: OK`. If it does not, do not use the file. The installer runs the same check for you.

## Where things go

| What | Where |
|------|-------|
| The program | `~/.local/share/mac-update` (the previous version is kept next to it as `mac-update.previous`) |
| The commands | `~/.local/bin/mac-update` and `~/.local/bin/macos-update` (the same command under a longer name) |
| Node.js that mac-update manages | `~/.local/share/mac-update/node` (an upgrade never moves or replaces it) |
| Global npm tools that mac-update manages | `~/.local/share/mac-update/npm-global` (an upgrade never moves or replaces it) |
| Your settings and per-app choices | `~/.config/mac-update` (`overrides.tsv`, `lang`, `reports/`) |
| Logs and other disposable files | `~/.local/state/mac-update` (`logs/`, `events/`) |

## First run

```bash
mac-update
```

Choose **Preview (no changes)** first, then **Update everything**. For plain text use `mac-update preview` and then `mac-update run`. See [the quick start](user/en/QUICK_START.md).

## If mac-update does not run

If the command is not found, open a new terminal window, or run the installer again with `--configure-shell`. If another program answers to `mac-update` or `macos-update`, the installer warns and names that program's file; run `~/.local/bin/mac-update` directly, or remove or rename the other file.

If the installer says another installer is running, wait for it to finish and run it again. A lock left behind by a killed run is taken over by the next run. If it reports that it could not take the lock, no installer is running: delete the folder `~/.local/share/mac-update.lock` it names, then run the installer again.

If an upgrade tells you it set aside an older copy of `node` or `npm-global` as `node.older.<time>` or `npm-global.older.<time>` in the program folder, nothing uses it and mac-update never deletes it. Delete it yourself when you no longer need it.

## Upgrading

Run the installer again. It replaces the program files, keeps the old version as `mac-update.previous`, and leaves your settings and `node/` and `npm-global/` alone. Running it on a 1.9.1 install also adds the `macos-update` link. If an upgrade is interrupted, it is undone at once on an error or Ctrl-C, and the next run undoes it if the run was killed. You can also check from the program: `mac-update update-self` (checks only) or **Settings**, "Update this toolkit".

## Coming from an older git copy

Earlier versions ran from a git checkout of the repository. To bring your settings and app choices over:

```bash
mac-update migrate              # preview: shows what would be copied
mac-update migrate --apply      # copy it, with a backup and a manifest
mac-update migrate --undo PATH  # put things back, using the manifest PATH printed by --apply
```

Nothing is moved without `--apply`. Then you can delete the old folder when you are ready.

## Optional extras

| Command | What it does |
|---------|--------------|
| `mac-update doctor` | Read-only readiness report. |
| `mac-update scan` | Rebuild the list of apps on this Mac. |
| `bash scripts/setup_touchid_sudo.sh` | Run from the program folder. Lets Touch ID replace the administrator password for `sudo` (macOS 14 or later). Shows a preview and asks first. |

## For developers

If you work from a git checkout of the repository, run `bash update_all.sh` from the checkout. A checkout is used as it is and is never replaced by the installer.

See also [UNINSTALL.md](UNINSTALL.md) and the [documentation index](user/INDEX.md).
