# User guide (English)

**macOS Updates 2.0.10** · Apple Silicon Mac · macOS 13 or later

## What it does

One run updates, in this order:

1. App Store apps
2. Terminal tools (npm, bun, and command-line tools that update themselves)
3. Homebrew formulae and casks
4. Internet apps: apps you downloaded from the maker's website, updated from the maker's update feed, a verified direct download, or the app's own updater
5. The list of your apps (refreshed)
6. macOS, always last

It does not ask you to approve each app. It acts only on what is already installed.

## What it never does

- It never closes an app you have open. That app is reported under "Needs you".
- It never installs an app you do not have. (The optional Catalog tab is the only place that can install, and only what you pick.)
- It never trusts a download blindly. A download must come from an allowed host, carry a valid code signature and pass Gatekeeper.
- It never stops everything because one item failed. The other items, the next steps and the macOS update still run.

## Opening the interface

```bash
mac-update
```

In a terminal, this opens the interface. In a script, over SSH without a terminal, or with `MAC_UPDATE_NONINTERACTIVE=1`, you get plain text instead. `mac-update run` always gives plain text. `mac-update --cli` (also `--plain`) is the same as `mac-update run`, `mac-update --tui` is the same as `mac-update` alone, and `macos-update` is the same command under a longer name. All of them work from any folder. The window needs at least 40 columns by 12 rows. Bigger is nicer: if you leave "Fit the window automatically" on, the interface asks the terminal for 120 by 36 at start and restores the size when you quit.

Move with the arrow keys. Enter opens or confirms, Tab goes to the next pane, Esc goes back, `1` to `7` jump to a tab, `?` opens help, `L` shows the full log, `q` quits. The mouse works too. The bottom line always lists the keys that work right now.

## The tabs

```
 macOS Updates                                  Last run: finished, 2 h ago
 Dashboard   Apps   Catalog   History   Settings   Diagnostics   Help
 +- Update groups -----------------------------------------------------+
 | > v System check     ############  done                              |
 |   v App Store        ############  v3 .5                             |
 |   v Terminal tools   ############  v2 .9                             |
 |   * Homebrew         ######......  4/9  v1 .3                        |
 |   . Internet apps    ............  waiting                           |
 |   . App list         ............  waiting                           |
 |   . macOS system     ............  waiting                           |
 +---------------------------------------------------------------------+
   [ Update everything ]   [ Preview (no changes) ]
   v updated   . up to date   ! needs you   x failed
```

This is a simplified drawing. The real screen uses colours and symbols.

| Tab | What it is for |
|-----|----------------|
| **Dashboard** | Start an update. Shows each group with live progress (done of total), and a scrollable list of the apps inside it while it runs. Enter or Space on a group turns it on or off for the next run. A side panel shows the last run, what still needs you, the next automatic run and the state of this Mac. |
| **Apps** | Every app and package found on this Mac (helper and background apps are left out). Choose how each one is updated. |
| **Catalog** | All tested apps: the ones that can still be added first, then the ones already installed (shown only). Nothing is selected until you choose, and the installer asks before each change. Update runs never use it. |
| **History** | Earlier runs, newest first, each with its result. Select a run to see what was updated and what needed you. Enter opens its full log. |
| **Settings** | What to update, safety limits, schedule, language and look. Every change is saved at once. |
| **Diagnostics** | Checks you can run: check this Mac, check requirements, how apps are updated (a table of every app and how its method was found), check update feeds, rebuild the app list, finish interrupted updates, check for a toolkit update. |
| **Help** | A short guide: first steps, how updating works, what each tab is for, what "Needs you" means. |

## Running an update

- **Update everything** checks and updates every group that is turned on.
- **Preview (no changes)** goes through the same steps and shows what would happen. It installs nothing and writes no history.

During a run you see each group and each app: checking, downloading, verifying, installing. Press `L` for the full log. **Stop** ends the run safely: apps already updated stay updated.

Questions (for example a restart) wait for your answer. If you do not answer in time, the safe answer is used. Your administrator password is typed in the terminal and is never saved or shown.

The result screen lists:

- **Updated**: now current.
- **Up to date**: nothing was needed.
- **Needs you**: see below.

## How internet apps are updated

- Apps with a verified download from their maker (for example Claude and Antigravity IDE) are installed directly instead of being opened and waited on. If that download fails, the app's own updater is still used.
- An app that was opened so it can update itself is closed as soon as its update is staged (Warp), instead of waiting the full time.
- Chrome during a gradual rollout is reported at once when Google's updater already answered "no update" for your version.
- Google apps (Gemini, Chrome, Google Drive) show when Google's own updater last checked and will check next, or that the app updated itself.
- A Homebrew app that was open and already updated itself is reported as up to date, with no warning.
- When macOS blocks an app in **Login Items & Extensions** (it closes right after opening), the result says so and where to allow it: System Settings › General › Login Items & Extensions.

## Per-app tuning

Open the **Apps** tab. Type `/` to search by name or source. Press Enter on an app. Space marks several apps so you can change them together.

| Mode | Meaning |
|------|---------|
| **automatic** | The toolkit updates it. This is the default. |
| **manual** | The toolkit only tells you when an update is waiting. |
| **skip** | The toolkit leaves it alone. |

You can also pick a **preferred source** where an app has more than one: default source, Homebrew, App Store, vendor website or built-in updater. The **Method** column shows how the toolkit knows the app: tested (on the toolkit's tested list), auto-detected (found from an App Store receipt, Homebrew, an update feed or a built-in updater) or manual (nothing recognised). The setting "Newly found apps" decides what happens to apps a scan finds that are not on the tested list: by confidence (automatic when the update method is clear, manual otherwise), always automatic, or always manual.

If the list is empty, choose **Scan now**. Scanning only reads your Mac.

Your choices are saved in `~/.config/mac-update/overrides.tsv`, one line per app: group, name, mode, source (separated by tabs). Delete the file to return every app to automatic.

## Settings

Choose a profile for a quick start: **Full automatic** (everything), **Careful** (no macOS update, no big version jumps), **Check only** (nothing is installed). Any manual change shows **Custom**.

| Section | Rows |
|---------|------|
| What to update | One switch per group; Only check, never install; Allow major upgrades (off keeps you on the current major version); macOS updates: install, notify only, or off (a restart is always asked first) |
| Apps and sources | Newly found apps (by confidence, automatic, manual); Per-app mode and source (opens the Apps tab); Excluded apps (`config/inventory_exclusions.txt`); Tracked npm tools (`config/npm_global_clis.txt`) |
| Automatic runs | Daily automation (off by default, no preset time): when it runs (every day at a time you choose, when you log in, or both) and the notification after a run (after every run, only when something needs me, never); Run a test now |
| Safety checks | Wait for apps to close (s); Download from vendor websites; Minimum free disk space (GB, default 15); Minimum battery level (%, default 30) |
| Network and speed | Reuse update checks for (hours); Time to answer a question (s, default 120); App Store update time limit (s) |
| Notifications and reports | Notification when done; Open the last log; Logs to keep (default 30) |
| Language and look | Language (English, Polski, Deutsch, Español, Français, Italiano, Português; it follows your system language until you choose one); Colours; Accent colour (blue by default, violet, amber, sage green, rose, graphite); Spacing; Simple characters; Fit the window automatically; Mouse; Help panel open at start |
| System and maintenance | Microsoft Office delay (days); Keep the Mac awake; Rebuild the app list; Update this toolkit; Export settings; Import settings; Reset to defaults |

Settings are saved in `~/.local/state/mac-update/tui-settings.json`, and your language in `~/.config/mac-update/lang`. A row set by an environment variable shows that variable and cannot be changed in the window. "Wait for apps to close" applies to apps the toolkit started itself.

Colours follow your terminal. The default, **Auto**, asks the terminal whether its window is light or dark and uses the matching scheme. The light look keeps your terminal's own white background and text colour for the page, with only the top bar, the key bar, the selected row and dialogs in pale grey, and every colour stays readable on a white window. The dark scheme is unchanged. A "dark" saved by an earlier version is treated as Auto once; if you want dark all the time, choose it again in Settings, Language and look, Colours.

## What "Needs you" means

Every line on the result screen has a reason and a next step.

| Reason | What to do |
|--------|------------|
| **The app is open** | Quit the app, then run the update again. The toolkit never closes it for you. |
| **Sign-in required** (App Store) | Open the App Store, sign in, then run the update again. |
| **A password is needed** | Run the update again from a terminal and type your administrator password when asked. Scheduled runs cannot ask, so they report this. |
| **A restart is needed** | The update is installed but takes effect after a restart. Restart when it suits you. |
| **No automatic method** | There is no safe automatic way to update this app. Open the app and use its own "Check for updates". |
| **The download failed** | Check your internet connection and run the update again. |
| **Checksum mismatch** | The file did not match its checksum, so nothing was installed. Try again later. If it keeps failing, update the app by hand. |
| **Manual mode** | You set this app to manual. Update it yourself, or switch it to automatic in the Apps tab. |
| **The maker's update information could not be reached** | Try again later. The maker's site may be down. |
| **A new major version is available** | Major upgrades are off. Allow them in Settings, or update by hand. |
| **Not enough disk space / battery too low** | Free some space, or connect the power adapter, then run again. |
| **Took too long** | Run again. Open the full log (`L`) if it repeats. |
| **The app's own updater opened** | Finish the update in the window the app opened. |

Some apps install their update when they quit. If the toolkit started such an app itself, it closes it as soon as the update is ready. An app you opened yourself is never closed.

If the reason says "unknown", open the full log with `L`.

The header, the Dashboard and History always show the same counts. An iPad app that the App Store is still installing after the update is listed as still installing in the App Store, with nothing to click: wait a few minutes and check again. A background updater that was started but reported no result is listed as "no result recorded, nothing to click"; its version is read again afterwards, so a finished update shows as updated.

## Where things are

| What | Where |
|------|-------|
| Run logs (newest 30 are kept) | `~/.local/state/mac-update/logs/` |
| Your per-app choices, language and the list of your apps | `~/.config/mac-update/` (`overrides.tsv`, `lang`, `reports/`) |
| The program | `~/.local/share/mac-update/` |

For flags, environment variables and troubleshooting, see [OPERATIONS.md](OPERATIONS.md). To install, upgrade or remove the toolkit, see [INSTALL.md](../../INSTALL.md) and [UNINSTALL.md](../../UNINSTALL.md).
