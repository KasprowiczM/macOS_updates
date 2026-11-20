# Changelog

All notable user-visible changes to **macOS Updates**. The current version is in [`VERSION`](VERSION).
This file is the public summary; it is written for people who use the toolkit, not for its developers.

## 2.0.10

- Documentation refresh, no behaviour change: the README now mentions `mac-update doctor` and `mac-update prepare`; the installation guide explains how to verify a manual download with `shasum -a 256 -c SHA256SUMS`; the operations guide lists the new environment variables (wait times, Google updater check age, Login Items check); and the guide describes direct installs from the maker, early closing of apps that staged an update, Chrome rollouts, Google updater statuses, Homebrew apps that updated themselves and the Login Items hint.

## 2.0.9

- Google apps (Gemini, Chrome, Google Drive): the toolkit no longer waits 45 seconds for Google's updater when that updater is inside its own check interval. Instead of "updater triggered (no response)" it now says what happened: "updated by the app's own updater X → Y", or that Google's updater checks on its own schedule, with the time of the last check and of the next one.
- Open Design and other apps the toolkit never opens: when macOS blocks the app in Login Items & Extensions (it closes right after opening), the toolkit says so and tells you where to allow it. For other never-opened apps the plain "open the app to update" message now carries the same hint.
- Versions that land during a run are picked up by the end-of-step recheck and reported as updated.
- Known: the Login Items detection is only available in an interactive run where the administrator approval was given.
- The version number moves from 1.9.8 straight to 2.0.9; there are no 2.0.0 to 2.0.8 releases.

## 1.9.8

- Chrome no longer waits 45 seconds on every run during a staged rollout: when Google's updater already answered "no update" for your Chrome within the last 6 hours, the rollout is reported at once, and otherwise the wait ends as soon as the updater answers.
- Gemini updates are now confirmed instead of always showing "updater triggered (no response)": every Google app gets its own response window and the app id is matched regardless of letter case.
- No false Homebrew warning when an open app (for example iTerm) has already updated itself to the version Homebrew wants: it is reported as current and no longer ends the Homebrew step with warnings.
- Polish: the Diagnostics help for "Install missing requirements" no longer mentions consent.
- Section headers in the internet summary (VPN, Cloud, Network) use fixed-width emoji, so the text no longer shifts between terminals.

## 1.9.7

- Faster internet step. Claude and Antigravity IDE now install straight from the vendor's verified download instead of first opening the app and waiting up to 90 seconds for its own updater (about 110 seconds less each when an update exists). If the download fails, the old open-and-wait path still runs. Known: a running Claude or Antigravity IDE still goes through the wait cycle and is reported as "needs restart".
- After the toolkit quits an app it opened, it now waits 3 seconds instead of 10 when the app staged no update.
- Warp is quit as soon as its log shows the update was downloaded, instead of waiting the full 90 seconds.
- Item durations no longer include the end-of-step settle time: Gemini showed 188 seconds for about 1 second of work. The settle time is recorded separately.
- iTerm is now in the list (updated through the Homebrew cask `iterm2`; its own Sparkle updater is not launched).
- Every app, CLI and group has its own unique emoji, defined in one table, `config/app_glyphs.tsv`. The Dashboard shows it before the app name (not in ASCII mode).

## 1.9.6

- Version bump only: no functional changes since 1.9.5.

## 1.9.5

- Dashboard: tick the groups you want to run (Space toggles, A selects all or none). The choice lasts for the session and does not change Settings; the button reads "Update N of 7 groups" for a subset.
- Preview now really checks every group and lists what would be updated, with the old and new version. Apps that only their own updater can check are listed separately as "Not checked by preview". "Update now" starts the real run with the same groups. Before, Preview always showed zero. Preview installs nothing.
- Administrator approval is asked at most once per run, at the start, and only when App Store, Homebrew or macOS updates are ticked: Touch ID first, password as a fallback. If you cancel, nothing asks again and the affected items say "needs you". The interface no longer shows a password box before Touch ID.
- `mac-update prepare` (also `mac-update doctor --fix`, and "Install missing requirements" in Diagnostics) installs what the Mac is missing after one question: Command Line Tools, Homebrew, Python and `mas`. `mac-update doctor` and the new Requirements view show what is present and which groups need it. A missing Homebrew or `mas` no longer fails the run.
- App Store updates that plain `mas upgrade` ignores are retried, and what still cannot be installed tells you what to do. Microsoft AutoUpdate is closed politely, so the "Force Quit" dialog no longer appears. DeepSeek Harness is installed from its verified vendor download. Every "needs you" or failed item shows a reason and a next step.
- Progress bars are slim lines with one colour per state (blue running, green done, amber needs you, red failed). A lighter pulse runs along a bar while it works and a short segment glides across while an item is still being checked; idle screens stay still. Light terminals get lighter frames, and a group with a failed item is no longer drawn green.
- App rows under a group line up with the group bars and the status word sits after the bar. The live log no longer repeats group headers or shows the engine's text progress bar.
- The preview legend explains "– not checked". Groups that ran fine say "ok" or "no updates" instead of "nothing reported", and updated apps without versions show what happened. The preview reads the same npm as the real update, so it no longer offers an npm update that is already installed.
- Menu-bar apps installed with Homebrew (such as MEGAsync) update on their own: the app is closed politely, updated and reopened. Apps with windows are never closed for you.
- The App Store step prints its "Track 1" heading once. The result screen shows old and new versions for internet apps (for example DeepSeek Harness).

## 1.9.4

- Colours now follow your terminal. The new default, **Auto**, asks the terminal whether its window is light or dark and picks the matching look, so a light Terminal window no longer shows pale text on white. You can still force dark or light in Settings, Language and look, Colours.
- The light look is cleaner: the page keeps your terminal's own white background and text colour, and only the top bar, the key bar, the selected row and dialogs are pale grey. Every colour is readable on a white window. The dark look is unchanged.
- A "dark" saved by an earlier version is treated as Auto once, because older versions saved it without you choosing it. If you want dark all the time, choose it again in Settings, Language and look, Colours.

## 1.9.3

- The light colour scheme is now readable: it paints its own white background instead of relying on your terminal's colours, and all text, status colours and accents have clear contrast. The dark scheme is unchanged.
- The Catalog tab shows the whole tested list: what can be added comes first (with a checkbox), then what is already installed, with its version and how it is updated. Installed apps can be read but not selected, and a one-line summary says how many are installed.
- One set of numbers: the header, the Dashboard and History now agree. Homebrew tap packages are no longer counted twice, and iPad apps are listed with their store names.
- An iPad app that the App Store is still installing after "Update everything" is reported as still installing, with nothing to click. A background updater that gave no result is reported as such, and the app's version is checked again so a finished update shows as updated.
- Clearer messages: no nested brackets or script names in status lines, no "finished with warnings" banners, the password request appears once, the log no longer glues progress lines together, and the session folder path is tidy. All seven languages.

## 1.9.2

- `mac-update --cli` (also `--plain`) runs the plain text update, the same as `mac-update run`, and `mac-update --tui` opens the interface, the same as `mac-update` alone. Both work from any folder.
- The command now has a second name, `macos-update`, which does exactly the same. The installer adds both, and warns you, naming the file, if another program on your `PATH` answers to either name. Running the installer again on a 1.9.1 install adds the new name.
- The Node.js and npm tools that mac-update manages for you (`node/` and `npm-global/` in the program folder) no longer get in the way of the installer. It accepts a folder that holds them and an upgrade leaves them untouched. If an upgrade is interrupted, it is rolled back, at once or on the next run.
- Uninstalling keeps those tools and tells you so, because your `PATH` may use them. Add `--purge-tools` to remove them too.
- Only one installer runs at a time, and uninstall waits for a running installer. If an upgrade finds an older copy of your managed tools in the kept previous version, it saves it in the program folder as `node.older.<time>` or `npm-global.older.<time>`, tells you once, and never deletes it. You can delete it yourself.

## 1.9.1

- A new installer: one command downloads a verified release into your home folder, adds the `mac-update` command, and upgrades without ever leaving the program half-installed. Uninstalling removes only what it added.
- Your settings, per-app choices and reports now live in `~/.config/mac-update`, logs in `~/.local/state/mac-update`. If you used a git copy before, your old files keep working; `mac-update migrate` copies them over when you are ready.
- The Apps list shows how each app updates (App Store, Homebrew, the app's own updater, and so on). Helper apps are hidden.
- Daily automation can run the update for you at a time you pick or when you log in, with one notification. It stays off until you set it up and confirm.
- New "macOS updates" setting: install, only notify, or off. The Careful profile only notifies.
- Clearer progress: every app and tool appears in the list, with download percentages for internet apps; apps that update themselves are closed as soon as their update is ready, so runs finish sooner.
- The interface follows your system language unless you choose another one.

## 1.9.0

- Updates run automatically again: one run updates the App Store apps, command-line tools, Homebrew packages, internet-downloaded apps and macOS already on your Mac, without approving each item first. Nothing new is installed.
- A new terminal interface: dashboard, Apps list, history and settings. `--cli` keeps the text mode.
- Choose per app: automatic, manual (check and report only) or skip, and pick another source where one exists.
- One failed update no longer stops the others, the next run or the macOS update.
- Scheduled runs never wait for an answer; anything that needs your password or a restart is reported.
- Open apps are never closed, downloads are verified, and a macOS update that needs a restart still asks first.

## 1.8.3

- Saved update choices are tied to the exact app and source you reviewed. New or changed targets get one grouped review; unchanged targets never ask again.
- Per-target update output is visible again, with bounded observation for supported package managers, managed Node and Bun, and eligible signed command-line tools.
- App Store iPad apps are handled only with an exact product identity and are reported honestly when an outcome cannot be confirmed.
- Installing into a separate directory is explained, and an existing checkout is preserved.
- Unsupported or unverified vendor tools stay manual.

## 1.8.2

- Text-mode progress is readable again: groups, targets, waiting and unconfirmed outcomes are shown instead of a silent run.
- One explicit, saved agreement can cover supported installed-app updates from current sources. Per-app exclusions, conflicts and protected targets still win.
- Homebrew ownership checks are narrower, so unrelated incomplete metadata no longer blocks every native app.
- After a run you get a specific next step for each outcome.

## 1.8.1

- Terminal controls were reworked: focusable buttons, saved search, filter and sort in the inventory, and persistent preview rows.
- Added the About screen with an explicit, pinned toolkit update preview and apply step that keeps your local settings.
- Internet-app updates can run concurrently under one shared reservation, with grouped Microsoft and Google work.

## 1.8.0

- New seven-language terminal workspace with a first-use wizard, group selection, saved display settings, live output and help.
- Bare interactive `update`, `setup` and inventory commands open the workspace; `--cli` selects the plain text interface.
- Requires a terminal of at least 80 by 24 characters.

## 1.7 and earlier

- 1.7: source-aware inventory, review-only proposals for unknown apps, and stricter verification of vendor downloads. Nothing is installed or updated without your consent.
- 1.6: local inventory as the source of truth, per-target safety checks for every update entry point, an optional catalog of apps you can install, and reviewed-source version advice.
- 1.5 and earlier: App Store, Homebrew, npm, system and Internet-app updates from one command, in seven languages (English, Polish, German, Spanish, French, Italian, Portuguese).
