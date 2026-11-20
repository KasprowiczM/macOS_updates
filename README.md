# macOS Updates

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

**Version 2.0.10** · Apple Silicon Mac · macOS 13 or later · [Website](https://macos-updates.64bit.site) · [MIT license](LICENSE) · [Changes](CHANGELOG.md)

One command, `mac-update`, keeps the software on your Mac up to date. It only touches what is already installed.

## What it updates

One run goes through these groups, in this order:

1. App Store apps
2. Terminal tools (npm, bun, command-line tools)
3. Homebrew formulae and casks
4. Internet apps (from the maker's update feed, a verified direct download, or the app's own updater)
5. The list of your apps
6. macOS, always last

There is nothing to approve app by app. If you want a different behaviour for one app, set it to manual or skip in the **Apps** tab. macOS itself can be set to install, to notify only, or to off in **Settings**.

## Install

Paste this into Terminal:

```bash
/bin/bash -c "$(curl -fsSL https://github.com/KasprowiczM/macOS_updates/releases/latest/download/install.sh)"
```

The installer downloads the latest release package, checks its SHA-256 checksum, puts the program in `~/.local/share/mac-update` and links the `mac-update` command into `~/.local/bin`. It needs no `git`, never uses `sudo`, and keeps your settings when you upgrade. To see what it would do first, add `--dry-run`: `... install.sh | bash -s -- --dry-run`. Details: [docs/INSTALL.md](docs/INSTALL.md) (in English).

If `mac-update` is not found afterwards, open a new terminal window. If it still is not, run the installer again with `--configure-shell`.

## First run

```bash
mac-update
```

In a terminal this opens an interface with tabs: Dashboard, Apps, Catalog, History, Settings, Diagnostics, Help. Choose **Preview (no changes)** to see what would happen, then **Update everything**. The result screen shows what was **Updated**, what was **Up to date** and what **Needs you**, with a reason and a next step for each.

Plain text instead: `mac-update run`. `mac-update --cli` (also `--plain`) is the same as `mac-update run`, `mac-update --tui` is the same as `mac-update` alone, and `macos-update` is the same command under a longer name. All of them work from any folder. Preview in plain text: `mac-update preview`. Check your Mac without updating: `mac-update doctor`. All commands: `mac-update help`. Missing something (Command Line Tools, native Homebrew, Python, `mas`)? `mac-update doctor` lists it and `mac-update prepare` installs it after one question.

Coming from an older git-based copy? Run `mac-update migrate` to move your settings (it shows a preview first).

## Safety

- Apps you have open are never closed. They are reported as "Needs you".
- Downloads come only from allowed hosts and must pass a code signature check and Gatekeeper.
- An update run never installs an app you do not have.
- One failed item does not stop the others, and macOS still updates last.
- Passwords are typed in the terminal and never saved. An automatic run never asks questions.

## Automatic runs

Off by default, with no preset time. To turn them on, open **Settings**, section **Automatic runs**: choose a time of day, "at login", or both, and how you want to be notified. A scheduled run skips macOS updates unless you enable them. See [Operations](docs/user/en/OPERATIONS.md).

## Documentation

| Language | Quick start | Guide | Operations |
|----------|-------------|-------|------------|
| English | [Quick start](docs/user/en/QUICK_START.md) | [Guide](docs/user/en/GUIDE.md) | [Operations](docs/user/en/OPERATIONS.md) |

All languages: [docs/user/INDEX.md](docs/user/INDEX.md) · [Install](docs/INSTALL.md) · [Uninstall](docs/UNINSTALL.md)

## License

[MIT](LICENSE)
