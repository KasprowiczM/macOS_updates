# Quick start (English)

**macOS Updates 2.0.10** · Apple Silicon Mac · macOS 13 or later · about 5 minutes

macOS Updates keeps the software already on your Mac up to date: App Store apps, terminal tools, Homebrew packages, apps you downloaded from the internet, and macOS itself. It never installs apps you do not have.

## 1. Install

Paste this into Terminal:

```bash
/bin/bash -c "$(curl -fsSL https://github.com/KasprowiczM/macOS_updates/releases/latest/download/install.sh)"
```

The installer downloads the release, checks its checksum and adds the `mac-update` command. It does not update anything, and it does not need `git` or `sudo`. You need Python 3.9 or later (if it is missing, the installer tells you to run `xcode-select --install`). Details: [INSTALL.md](../../INSTALL.md).

Then open a new terminal window so the command is found. If `mac-update` is still not found, run the installer again with `bash -s -- --configure-shell` after the pipe, as explained in INSTALL.md.

## 2. Preview

```bash
mac-update
```

In a terminal this opens the interface on the **Dashboard**. Move to **Preview (no changes)** with the right arrow and press Enter. Nothing is installed. You see what would be updated.

Prefer plain text? Run `mac-update preview`. `mac-update --cli` (also `--plain`) is the same as `mac-update run`, `mac-update --tui` is the same as `mac-update` alone, and `macos-update` is the same command under a longer name. All of them work from any folder.

## 3. Update

On the Dashboard choose **Update everything** and press Enter. You see each group (App Store, Terminal tools, Homebrew, Internet apps, App list, macOS system) and each app as it is updated. If macOS asks for your password, type it in the terminal; the toolkit never stores it.

You can stop at any time. Apps that are already updated stay updated.

## 4. Read the result

The result screen has three lists:

- **Updated**: these apps are now current.
- **Up to date**: nothing was needed.
- **Needs you**: the toolkit could not finish these by itself. Each line says why and what to do. Typical reasons: the app was open, the App Store needs you to sign in, or a restart is needed. See the [guide](GUIDE.md).

Apps you have open are never closed. Quit them and run the update again.

## 5. Next steps

| I want to... | Do this |
|--------------|---------|
| Change how one app is updated | Apps tab, Enter on the app: automatic, manual or skip |
| Turn off a group, or macOS updates | Dashboard: move to the group, press Space. Or Settings, "macOS updates" |
| Run without the interface | `mac-update run` |
| Check my Mac without updating | `mac-update doctor` |
| Run by itself | Settings, section "Automatic runs". See [OPERATIONS.md](OPERATIONS.md) |
| See what went wrong | History tab, then Enter on a run to open its log |
| Bring settings from an older git copy | `mac-update migrate` (shows a preview first) |

More: [GUIDE.md](GUIDE.md) · [OPERATIONS.md](OPERATIONS.md) · [UNINSTALL.md](../../UNINSTALL.md)
