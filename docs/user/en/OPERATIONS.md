# Operations (English)

**macOS Updates 2.0.10** · for people who run the toolkit from a terminal, a script or a schedule.

## Ways to run

| Command | What happens |
|---------|--------------|
| `mac-update` | Opens the interface (needs a terminal). |
| `mac-update run [options]` | Plain text run. Options go to the update program, for example `-y`, `--skip-system`, `--non-interactive`. |
| `mac-update --cli [options]` | Same as `mac-update run` (also `--plain`). |
| `mac-update --tui` | Same as `mac-update`: opens the interface. |
| `mac-update preview` | Walks every step and prints what would happen. Nothing is updated. |
| `mac-update scan` | Rebuilds the list of apps on this Mac. Reads only. |
| `mac-update doctor` | Read-only readiness report. No password, no run log. |
| `mac-update settings` | Opens the interface on the Settings tab. |
| `mac-update update-self` | Checks for a newer mac-update (`--check`, the default, or `--prepare`). |
| `mac-update migrate` | Brings settings from an older git copy: `--preview` (default), `--apply`, `--undo MANIFEST`. |
| `mac-update uninstall` | Removes mac-update. See [UNINSTALL.md](../../UNINSTALL.md). |
| `mac-update version`, `mac-update help` | Version and command list. |

`macos-update` is the same command as `mac-update` under a longer name. The installer links both into `~/.local/bin`, and both work from any folder.

`mac-update` calls `update_all.sh` in the program folder `~/.local/share/mac-update`. If you work from a git checkout instead, run `bash update_all.sh` there; the flags below are the same. With `MAC_UPDATE_NONINTERACTIVE=1` the interface never opens and nothing waits for an answer.

## Flags of `update_all.sh`

| Flag | Meaning |
|------|---------|
| `-y`, `--yes` | Skip the confirmation question |
| `-h`, `--help` | Show the flag list |
| `--tui`, `--cli` | Choose the interface or plain text. `--tui` fails with a message if there is no usable terminal; only `--dry-run` and `--skip-...` may be added to it. |
| `--dry-run` | Preview, change nothing |
| `--doctor` | Readiness report. Exit 0 ok, 10 warnings, 1 problem |
| `--verify-only` | Compare installed app versions with history, change nothing |
| `--json-summary` | Print a JSON summary at the end |
| `--bootstrap-cli` | Also install a missing managed Node, Bun or native command-line tool. Off by default. |
| `--skip-prescan` | Skip the first check of the app list |
| `--skip-appstore` | Skip App Store apps |
| `--skip-npm` | Skip terminal tools (npm, bun, native command-line tools) |
| `--skip-brew` | Skip Homebrew |
| `--skip-internet` | Skip internet apps |
| `--skip-postupdate` | Skip the app list and history refresh |
| `--skip-system` | Skip the macOS update |
| `--skip-doctor` | Skip `brew doctor` inside the Homebrew step |
| `--treat-appstore-ax-as-warning` | Report a missing Accessibility permission as a warning |
| `--non-interactive` | For schedulers: no questions (same as `MAC_UPDATE_NONINTERACTIVE=1`) |
| `--notify` | Show a macOS notification when the run ends |

Steps always run in this order: system check, App Store, terminal tools, Homebrew, internet apps, app list, macOS. macOS runs last because it can restart the Mac. If an earlier step failed hard, the macOS step waits for the next run.

## Environment variables

Set them in front of the command, for example `MAC_UPDATE_MIN_FREE_GB=30 mac-update run`. Most also exist as a row in Settings; a row set by a variable cannot be changed in the interface.

| Variable | Default | Purpose |
|----------|---------|---------|
| `MAC_UPDATE_NONINTERACTIVE` | off | `1`: no interface, no questions |
| `MAC_UPDATE_DRY_RUN` | off | `1`: same as `--dry-run` |
| `MAC_UPDATE_SKIP_APPSTORE`, `_NPM`, `_BREW`, `_INTERNET`, `_SYSTEM`, `_PRESCAN`, `_POSTUPDATE`, `_DOCTOR` | off | `1`: same as the matching `--skip-...` flag |
| `MAC_UPDATE_SYSTEM_MODE` | `auto` | macOS updates: `auto` installs, `notify` only reports, `skip` does not check |
| `MAC_UPDATE_NEW_APP_MODE` | by confidence | `auto` or `manual` for newly found apps that are not on the tested list |
| `MAC_UPDATE_NOTIFY` | off | `1`: notification when done. For scheduled runs: `always`, `needs_you` or `never` |
| `MAC_UPDATE_LANG` | system language | `en`, `pl`, `de`, `fr`, `es`, `it`, `pt` |
| `MAC_UPDATE_HOME` | `~/.local/share/mac-update` | Program folder |
| `MAC_UPDATE_CONFIG_DIR` | `~/.config/mac-update` | Settings folder |
| `MAC_UPDATE_STATE_DIR` | `~/.local/state/mac-update` | Logs, caches, backups |
| `MAC_UPDATE_LOGS_DIR` | `logs` in the state folder | Run logs |
| `MAC_UPDATE_OVERRIDES_FILE` | `overrides.tsv` in the settings folder | Per-app choices file |
| `MAC_UPDATE_MAX_LOGS` | 30 | Run logs to keep |
| `MAC_UPDATE_PROMPT_TIMEOUT` | 120 | Seconds to answer a question before the safe answer is used |
| `MAC_UPDATE_MIN_FREE_GB` | 15 | Warn and run in a reduced way below this free space |
| `MAC_UPDATE_MIN_BATTERY` | 30 | On battery below this percent, skip the macOS step (a scheduled run is skipped completely) |
| `MAC_UPDATE_NO_CAFFEINATE` | off | `1`: do not keep the Mac awake during the run |
| `MAC_UPDATE_NO_SUDO_KEEPALIVE` | off | `1`: do not keep the administrator password fresh |
| `MAC_UPDATE_SUDO_KEEPALIVE_MAX` | 14400 | Seconds to keep it fresh (300 to 14400) |
| `MAC_UPDATE_QUIT_WAIT` | 60 | Seconds to wait for an app the toolkit started to close (0 to 300) |
| `MAC_UPDATE_STAGE_WAIT` | 90 | Seconds to wait for an app the toolkit opened to install its own update (0 to 600) |
| `MAC_UPDATE_POST_QUIT_WAIT` | 10 | Seconds to wait after closing such an app when its update was staged |
| `MAC_UPDATE_POST_QUIT_WAIT_IDLE` | 3 | The same, when no update was staged |
| `MAC_UPDATE_OMAHA_WAIT` | 45 | Seconds to wait for Google's updater to answer (0 to 180) |
| `MAC_UPDATE_OMAHA_MAX_AGE_H` | 6 | Hours a check by Google's updater counts as recent |
| `MAC_UPDATE_BTM_CHECK` | on | `0`: do not check whether macOS blocks an app in Login Items & Extensions |
| `MAC_UPDATE_BTM_TIMEOUT` | 4 | Seconds allowed for that check |
| `MAC_UPDATE_BTM_DUMP`, `MAC_UPDATE_GOOGLE_USER_LOG`, `MAC_UPDATE_GOOGLE_SYS_LOG` | none | For diagnostics and tests only: a saved Login Items listing, or Google updater log files, read instead of the real ones |
| `MAC_UPDATE_VENDOR_DIRECT` | on | `0`: no direct downloads from the app maker |
| `MAC_UPDATE_ALLOW_MAJOR_UPGRADE` | off | `1`: allow big version jumps, including a major macOS upgrade |
| `MAC_UPDATE_MAU_DEFERRAL_DAYS` | 7 | Days to wait before installing a new Microsoft Office release |
| `MAC_UPDATE_FEED_CACHE_TTL_H` | 24 | Hours to reuse the maker's version information |
| `MAC_UPDATE_MAS_UPGRADE_TIMEOUT` | 1800 | Seconds before one App Store update is stopped and reported |
| `MAC_UPDATE_DOCTOR_PROBE_AX` | off | `1`: let `doctor` test the Accessibility permission (macOS may show a prompt) |
| `GITHUB_TOKEN` | none | Optional. Raises the GitHub download limit. Set it in your shell profile |

## Automatic runs (optional)

Automatic runs are off by default and have no preset time. Turn them on in **Settings**, section **Automatic runs**, row "Daily automation". You choose:

- when: every day at a time you type (24-hour, for example 08:30), when you log in, or both;
- how you are told: after every run, only when something needs you (the default), or never.

You see exactly what will be installed and confirm before anything is written. "Run a test now" schedules one extra run a few minutes from now.

The same from a terminal, with `bash ~/.local/share/mac-update/scripts/install_launchagent.sh`:

```bash
bash scripts/install_launchagent.sh --daily 08:30 --notify needs_you      # every day at 08:30
bash scripts/install_launchagent.sh --daily 08:30 --days 1,3,5            # only on chosen weekdays (numbers 1 to 7)
bash scripts/install_launchagent.sh --at-login --delay-min 10             # at login, after 10 minutes of session time
bash scripts/install_launchagent.sh --once-in 5                           # one test run in 5 minutes
bash scripts/install_launchagent.sh --status                              # is it installed? (--check, or --status --json)
bash scripts/install_launchagent.sh --uninstall                           # remove every mac-update schedule
```

Run these from the program folder. `--notify` accepts `always`, `needs_you` or `never`.

What an automatic run does:

- It runs without a terminal and never asks a question.
- It skips macOS updates unless you enable them; macOS then only reports what is available.
- It skips itself when another run is active, when the Mac is on a low battery, or when the last successful run was less than 12 hours ago.
- Anything that needs your password or a restart is skipped and reported as "Needs you". Run `mac-update` yourself to finish it.
- It sends one notification, as you chose. Output goes to `launchd.out` and `launchd.err` in the logs folder.

## Passwords

macOS and App Store steps may need your administrator password. In a terminal the toolkit asks at most once per run and keeps it fresh for the rest of the run. It never asks in a preview, and never without a terminal (automatic runs skip those steps instead). Optional: `bash scripts/setup_touchid_sudo.sh --check` shows whether Touch ID can replace the password for `sudo`. Running the script without `--check` shows a preview and asks first.

## Where things are

| What | Where |
|------|-------|
| The program | `~/.local/share/mac-update` |
| Your settings and per-app choices | `~/.config/mac-update` (`overrides.tsv`, `lang`, `reports/`) |
| Run log of each run | `~/.local/state/mac-update/logs/update_all_<date>_<time>.log` (newest 30 kept, mode 600) |
| Short result of the last run | `~/.local/state/mac-update/logs/run_summary_latest.json` |
| Interface settings | `~/.local/state/mac-update/tui-settings.json` |
| Automatic run output | `~/.local/state/mac-update/logs/launchd.out`, `launchd.err` |

A preview writes its log to a temporary folder and leaves your history unchanged. Inside the interface, the **History** tab lists past runs and `L` opens the newest log. Coming from an older git copy: `mac-update migrate`.

Exit code of `update_all.sh`: `0` when the run was clean or only had warnings (an app that needs you is a warning), `1` when something failed.

## Troubleshooting

Start with `mac-update doctor`. It checks the platform, Python, curl, Homebrew, `mas`, Touch ID, disk space, power, network and the program itself.

| Problem | What to do |
|---------|------------|
| `mac-update: command not found` | Open a new terminal window. If it persists, `~/.local/bin` is not on your `PATH`: run the installer again with `--configure-shell`, or add that folder yourself. |
| `mac-update` starts a different program | Another program with that name comes earlier on your `PATH`. The installer warns about this and names that program's file. Run `~/.local/bin/mac-update` directly, or remove or rename the other file. |
| The interface does not open | It needs a terminal, Python 3 and a `TERM` that is not `dumb`. Use `mac-update run` otherwise. |
| The installer says the checksum does not match | Nothing was installed. Try again later; if it repeats, report it. |
| An app is under "Needs you" | See the table "What Needs you means" in [GUIDE.md](GUIDE.md). |
| The App Store step stops with exit code 2 | The terminal lacks the Accessibility permission. Allow it in System Settings, Privacy & Security, Accessibility, or add `--treat-appstore-ax-as-warning`. |
| `mas` is missing or too old | The toolkit reports it and never installs it by itself. Install it yourself with Homebrew (`brew install mas`). |
| App Store needs sign-in | Open the App Store, sign in, run again. |
| Homebrew is missing | Install it from <https://brew.sh>, then run again. |
| The app list is missing or wrong | `mac-update scan`. It reads only your Mac. Never copy another person's list. |
| An app is never updated | Diagnostics, "How apps are updated", shows how each app is handled. Open the app and use its own "Check for updates" if there is no method. |
| A vendor's update information cannot be reached | Try later. Check feeds in Diagnostics, "Check update feeds". |
| The Mac went to sleep during a run | Keep "Keep the Mac awake" on (default). |
| An update was interrupted | Diagnostics, "Finish interrupted updates". |
| A run says another run is active | Wait for it to finish. A leftover marker from a crashed run is cleaned up at the start of the next run. |
| Low disk or battery | Free space or plug in the charger. Limits are in Settings, "Safety checks". |

Still stuck? Open the newest file in the logs folder and look for the first line that says error or warning.

## Uninstall

```bash
mac-update uninstall
```

It also turns off automatic runs. See [UNINSTALL.md](../../UNINSTALL.md) for what is and is not removed.
