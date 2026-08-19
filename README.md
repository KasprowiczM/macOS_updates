# macOS Updates

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

> **v1.4.0** — Production-ready one-command update orchestrator for **Apple Silicon Macs running macOS 13–26**. It coordinates verified package updates and honest in-app update triggers for **software already installed on this Mac**. **Multilingual** (7 languages). Optional private overlay via [`dev_sync/`](dev_sync/README.md).

**Public repo:** [github.com/KasprowiczM/macOS_updates](https://github.com/KasprowiczM/macOS_updates) · Going public: [docs/PUBLIC_RELEASE.md](docs/PUBLIC_RELEASE.md) · Changes: [CHANGELOG.md](CHANGELOG.md)

---

## One-line install (new users)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

The installer clones the repo, prompts for **language** (English menu, 7 locales), installs dependencies, builds **your** `APPLICATIONS.md` from apps already on this Mac, and prints which apps the project can update. It never imports another user's inventory or installs apps for you.

See [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md)

---

## Per-machine bootstrap (does **not** arrive with `git pull`)

Two things live outside the repository and therefore have to be set up once **on
every Mac**. Cloning or pulling the repo on a second machine does not bring them
along — this is the single most common point of confusion in this project.

| Step | Command | Why it cannot be in git |
|------|---------|-------------------------|
| Touch ID for `sudo` | `bash scripts/setup_touchid_sudo.sh` | Writes `/etc/pam.d/sudo_local` — a root-owned, machine-local file outside the repo |
| Weekly background run | `bash scripts/install_launchagent.sh --day 1 --hour 9` | Writes `~/Library/LaunchAgents/com.<user>.macos-updates.plist` — per-user, per-machine |

```bash
bash scripts/setup_touchid_sudo.sh --check      # report only, writes nothing
bash scripts/setup_touchid_sudo.sh              # install / repair
bash scripts/setup_touchid_sudo.sh --uninstall

bash scripts/install_launchagent.sh --check
bash scripts/install_launchagent.sh --uninstall
```

`setup_touchid_sudo.sh` never touches `/etc/sudoers` and never grants
passwordless `sudo`. On macOS 14+ it uses `/etc/pam.d/sudo_local`, which survives
OS updates; on macOS 13 it patches `/etc/pam.d/sudo`, which macOS updates wipe —
re-run it after a major upgrade.

### What the scheduled background run does and does not do

The LaunchAgent runs `update_all.sh -y --skip-system` with
`MAC_UPDATE_NONINTERACTIVE=1` and `MAC_UPDATE_NOTIFY=1`.

- **Runs:** Homebrew, native CLI + npm, internet apps, inventory/history.
- **Does not run macOS system updates** — `--skip-system` is deliberate. On Apple
  Silicon `softwareupdate` needs **volume-owner credentials**, which cannot be
  supplied from an unattended launchd job, and the step may restart the Mac.
- **Does not run App Store updates** — `sudo mas upgrade` needs a password, and
  the Track 2 AppleScript path drives the App Store GUI. Both are skipped in a
  non-TTY session and reported as a soft warning (exit `10`), never as a failure.

Both therefore remain interactive, on purpose. Run `bash update_all.sh` yourself
when you want App Store and macOS updates applied.

---

## Command-line flags

`lib/cli.sh` is the authoritative list; `bash update_all.sh --help` prints it.

| Flag | Effect |
|------|--------|
| `-y`, `--yes` | Skip the confirmation prompt |
| `-h`, `--help` | Show usage and exit `0` |
| `--dry-run` | Preview every step, mutate nothing, never ask for credentials |
| `--verify-only` | Verify installed app versions against history without mutating |
| `--json-summary` | Print a JSON result object on stdout after the run |
| `--non-interactive` | Non-interactive mode for launchd / cron (also implies `-y`) |
| `--notify` | Post a macOS notification when the run finishes |
| `--treat-appstore-ax-as-warning` | Treat App Store exit `2` (missing Accessibility) as a warning |
| `--skip-prescan` | Skip step 0 (`APPLICATIONS.md` prescan) |
| `--skip-appstore` | Skip step 1 (App Store) |
| `--skip-npm` | Skip step 2 (native CLI + npm) |
| `--skip-brew` | Skip step 3 (Homebrew) |
| `--skip-internet` | Skip step 4 (internet apps) |
| `--skip-postupdate` | Skip step 5 (`APPLICATIONS.md` / `UPDATES.md` history) |
| `--skip-system` | Skip step 6 (macOS system update) |
| `--skip-doctor` | Skip `brew doctor` inside `update_brew.sh` |

An unknown `-…` option exits `2` after printing usage.

## Environment variables

Every flag has an equivalent variable; these are the ones with no flag.

| Variable | Default | Meaning |
|----------|---------|---------|
| `MAC_UPDATE_NONINTERACTIVE` | `0` | Never prompt; skips App Store Track 2 GUI automation |
| `MAC_UPDATE_NOTIFY` | `0` | Desktop notification on completion (also implied by non-interactive) |
| `MAC_UPDATE_NO_SUDO` | *set automatically* | Exported by `update_all.sh` when there is no TTY; child scripts then skip root-only tracks instead of failing |
| `MAC_UPDATE_NO_SUDO_KEEPALIVE` | `0` | Set to `1` to disable the background `sudo` timestamp refresher |
| `MAC_UPDATE_STALE_DAYS` | `45` | Days after which an unverified app is reported as stale |
| `MAC_UPDATE_MAX_LOGS` | `30` | Run logs retained in `logs/` |
| `MAC_UPDATE_INTERNET_SETTLE_SECONDS` | `10` | Pause that lets a launched vendor updater rewrite `Info.plist` (`0` disables, clamped to 120) |
| `MAC_UPDATE_MAS_CHECK_TIMEOUT` | `120` | Timeout for `mas outdated` |
| `MAC_UPDATE_MAS_UPGRADE_TIMEOUT` | `1800` | Timeout for `sudo mas upgrade` |
| `MAC_UPDATE_MAU_DEFERRAL_DAYS` | `7` | Microsoft AutoUpdate quarantine window (clamped to Microsoft's 1–28) |
| `MAC_UPDATE_MAU_CLEAR_DEFERRALS` | `0` | Set to `1` to remove blocking MAU deferral keys via `defaults delete` |
| `MAC_UPDATE_MAU_KEEP_DEFERRALS` | `0` | Set to `1` to make the toolkit never touch MAU deferral preferences |
| `MAC_UPDATE_LANG` / `MAC_LANG` | from `.mac_update_prefs` | UI language (`en pl es it pt de fr`) |

## sudo and Touch ID — the contract

Rewritten in v1.3.1 / v1.4.0. `update_all.sh` has **exactly one** interactive `sudo` call
site, and it is governed by three conditions:

1. **At most once per run.** A single `sudo -v` before the log redirect, then a
   background keep-alive refreshes the timestamp every 50 s so a long run never
   prompts a second time. The keep-alive is started at most once and is killed by
   the cleanup trap on every exit path, including `INT`/`TERM` — it can no longer
   be orphaned.
2. **Never without a controlling TTY.** If stdin is not a terminal — IDE task
   runner, agent shell, launchd, cron — the toolkit does **not** call `sudo -v`.
   A bare `sudo -v` there escalates to the GUI askpass/Touch ID dialog, which is
   what made every command appear to demand elevation. Instead
   `MAC_UPDATE_NO_SUDO=1` is exported, root-only steps are skipped, and the run
   reports a soft warning.
3. **Never during `--dry-run`.** A preview must not ask for credentials.

`sudo` is also not requested at all when neither step 1 (App Store) nor step 6
(macOS) is going to run, e.g. `bash update_all.sh --skip-appstore --skip-system`.

---

## What this does

`update_all.sh` runs seven steps:

| Step | Action |
|------|--------|
| 0 | **Prescan** — discover installed apps → update `APPLICATIONS.md` |
| 1 | **App Store** — Track 1: `sudo mas upgrade`; Track 2: AppleScript GUI for iPad apps |
| 2 | **Native CLI + npm** — Node, Bun, global npm CLIs |
| 3 | **Homebrew** — formulae and casks (`brew_cask` + downgrade protection) + cleanup and health check |
| 4 | **Internet apps** — verified direct handlers, `sparkle_appcast`, vendor CLIs and honest update triggers |
| 5 | **Postupdate/history** — refresh `APPLICATIONS.md`, append `UPDATES.md` atomically |
| 6 | **macOS (final)** — `softwareupdate -ia -R`; skipped when any earlier step failed |

**Important:** Updates only touch software already installed on your Mac. Supported-but-missing apps are reported, not installed. The final macOS step may restart the Mac, so it runs last and retains mandatory `-R`. Unknown installed apps are listed so you (or an AI agent) can add handlers.

Coverage is deliberately explicit: **verified direct** means the updater confirmed the package/version path; **triggered-unverified** means an app was launched to let its vendor updater run but completion cannot be proven; **externally managed** means the vendor or App Store owns the update lifecycle; **manual** requires user action; **unknown** has no registered method. Today Inkscape is a Homebrew cask, UniFi/WiFiman/Picsart use App Store Track 2, Microsoft Office uses `msupdate`, and Teams uses its self-updater with an observed, verified `TEAMS21` MAU fallback when Microsoft offers it. Only IPMIView and DJI Assistant 2 remain manual.

```bash
bash scripts/report_update_coverage.sh   # coverage report
bash build_inventory.sh                  # rebuild APPLICATIONS.md from this Mac
```

---

## Requirements

| Tool | Auto-installed? |
|------|----------------|
| Apple Silicon (arm64) Mac | — |
| macOS 13 Ventura or later | — |
| Xcode Command Line Tools | ✅ `setup.sh` / `install.sh` |
| Homebrew | ✅ |
| `mas` (App Store CLI) | ✅ |
| Python 3 | ✅ via Homebrew if missing |
| `rclone` (optional) | ✅ if chosen as cloud provider |

---

## Quick start

### New user (no cloud)

```bash
# Option A — one line (recommended)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"

# Option B — manual
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh
bash build_inventory.sh
bash update_all.sh
```

### Owner (GitHub + cloud overlay)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

---

## Project structure

```
macOS_updates/
├── VERSION                     # Package version (1.4.0)
├── install.sh                  # One-line installer entrypoint
├── uninstall.sh                # Remove clone (keeps Homebrew/apps)
├── setup.sh                    # First-run setup (no cloud)
├── migration_setup.sh          # Full setup + cloud wizard
├── build_inventory.sh          # Build APPLICATIONS.md from this Mac
├── update_all.sh               # Master orchestrator
├── update_*.sh                 # Individual update steps
│
├── dev_sync/                   # Private overlay sync (cloud)
│   ├── provider_setup.sh
│   ├── dev-sync-export.sh      # (+ import, verify, prune, …)
│   └── dev_sync_*.py           # Python backend
├── dev-sync-*.sh               # Root wrappers (backward compatible)
│
├── config/                     # Internet app registry (public)
│   ├── internet_apps.txt
│   ├── internet_app_methods.txt
│   └── internet_dispatch_order.txt
│
├── lib/                        # Shared Bash libraries
├── i18n/                       # 7-language UI strings
├── scripts/                    # Utilities (coverage report, scaffold, …)
├── templates/                  # APPLICATIONS.md.template (reference)
├── tests/                      # unittest + static safety checks
├── docs/
│   ├── INSTALL.md · UNINSTALL.md
│   ├── user/                   # End-user guides (7 languages)
│   └── agents/                 # Developer / AI agent reference
│
├── CLAUDE.md · AGENTS.md · GEMINI.md · CODEX.md
└── run_tests.sh
```

**Private files (gitignored, cloud or local only):** `APPLICATIONS.md`, `UPDATES.md`, `.dev_sync_config.json`, `.mac_update_prefs`, `.env`

---

## Individual scripts

| Script | Purpose |
|--------|---------|
| `install.sh` | Clone + setup + inventory for new users |
| `setup.sh` | Dependencies and permissions (no cloud) |
| `migration_setup.sh` | Full migration + cloud + app scan |
| `build_inventory.sh` | Read-only system scan → atomically refresh `APPLICATIONS.md` without update history |
| `update_all.sh` | All update steps + logging |
| `update_system.sh` … `update_brew.sh` | Single-layer updates |
| `uninstall.sh` | Remove toolkit directory |
| `run_tests.sh` | Syntax + Python + unittest + secret scan |

---

## Adding support for a new app

1. Install the app yourself (the updater never installs it for you).
2. Run `bash build_inventory.sh` to add it to `APPLICATIONS.md`.
3. For auto-updates, ask an AI agent or follow [docs/user/en/GUIDE.md](docs/user/en/GUIDE.md):

```bash
bash scripts/scaffold_internet_app.sh "App Name" silent_launch
bash run_tests.sh
```

Coverage methods are mapped to the user-facing states above. Examples: `github_dmg` and a confirmed vendor CLI are **verified direct**; `silent_launch` is **triggered-unverified**; App Store/vendor-owned flows can be **externally managed**; `manual` and missing registry entries remain explicit.

---

## Cloud sync (`dev_sync`)

| GitHub (public) | Cloud (private) |
|-----------------|-----------------|
| Scripts, `config/`, `docs/`, tests | `APPLICATIONS.md`, `UPDATES.md`, `.env`, `.dev_sync_config.json` |

```bash
bash dev_sync/provider_setup.sh
bash dev_sync/dev-sync-export.sh
bash dev_sync/dev-sync-import.sh
bash dev_sync/dev-sync-verify-full.sh
```

Root `dev-sync-*.sh` wrappers call the same scripts in `dev_sync/`.

---

## Test

```bash
bash run_tests.sh
bash update_all.sh --dry-run -y
```

---

## Critical technical notes

- **`softwareupdate` must use `-R`** — otherwise updates download but never apply.
- **`mas upgrade` must use `sudo`** on macOS 14.8.2+/15.7.2+/26.x (entitlement change, see https://github.com/orgs/Homebrew/discussions/6550).
- **Bash 3.2+** throughout — no `declare -A`, `mapfile`, `readarray`.
- Downloaded app bundles are verified, installed through a rollback-safe staged swap, and mounted at unique per-session DMG mountpoints.
- Private inventory/history writes and cloud imports use atomic replacement; imports stage accepted private files before committing them.

---

## Documentation

| Audience | Start here |
|----------|------------|
| Users | [docs/user/en/QUICK_START.md](docs/user/en/QUICK_START.md) |
| Install / uninstall | [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md) |
| Developers / agents | [docs/agents/scripts.md](docs/agents/scripts.md) |
| Dev sync | [dev_sync/README.md](dev_sync/README.md) |
| AI context | `CLAUDE.md`, `AGENTS.md` |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| New Mac | `install.sh` or `setup.sh` + `build_inventory.sh` |
| Wrong app list | `build_inventory.sh` — never copy another user's `APPLICATIONS.md` |
| App not auto-updating | `scripts/report_update_coverage.sh` → add handler per GUIDE |
| Missing `APPLICATIONS.md` | `build_inventory.sh` or `dev_sync/dev-sync-import.sh` (owner) |
| `mas upgrade` fails | `sudo mas upgrade` |
| Cloud not configured | `bash dev_sync/provider_setup.sh` |

Full list: [docs/agents/troubleshooting.md](docs/agents/troubleshooting.md)
