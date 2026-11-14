# macOS Updates

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

**Website:** [macos-updates.64bit.site](https://macos-updates.64bit.site) · **Repository:** [github.com/KasprowiczM/macOS_updates](https://github.com/KasprowiczM/macOS_updates) · **License:** [MIT](LICENSE) · **Changes:** [CHANGELOG.md](CHANGELOG.md)

> **v1.7.1** : One-command update orchestrator for **Apple Silicon Macs running macOS 13-27**. It coordinates verified package updates and honest in-app update triggers for **software already installed on this Mac**. **Multilingual** (7 languages). Optional private overlay via [`dev_sync/`](dev_sync/README.md).

| At a glance | |
|-------------|--|
| Platform | Apple Silicon (arm64) only · macOS 13 Ventura to macOS 27 · Bash 3.2 + Python 3 |
| Pipeline | 7 steps (0–6), macOS system update always last |
| Registry | 47 internet apps · 11 update methods (see [Update methods](#update-methods)) |
| Languages | EN, PL, ES, FR, DE, IT, PT (CLI and docs) |
| Tests | 1178 automated tests (`bash run_tests.sh`) |

Stage C activates local JSON inventory and scoped update plans. `bash update_all.sh --plan` and `--dry-run` show the same read-only decisions. A normal interactive run asks once for the displayed scopes; `-y`, EOF and unattended runs grant no new permission. Use `--preferences` to review or reset choices. Updates keep the observed source and exact destination; conflicts, missing targets and uncertain evidence defer that target. `build_inventory.sh --migration --preview` preserves old Markdown bytes and notes; accept the displayed proposal ID explicitly. Generic vendor updates remain manual until a reviewed identity and adapter are available. An old catalog entry is neither proof of installation nor consent.

This is the 1.7.1 source snapshot on main, without a separate release tag. Scoped manager updates act only on installed targets with an observed source and fresh approval. Generic native and vendor updater adapters remain manual until reviewed recipes are available. The optional public catalog covers 48 products and offers reviewed official links for manual acquisition, with zero approved automatic first-install recipes. The legacy method list below describes capabilities, not execution authority.

**New in v1.6.0:** Scheduled (launchd) runs find Homebrew and `mas`, and the installer verifies that the job is loaded (`--minute` and `--once-in` added). Apps you have open are never closed or replaced, Homebrew casks included. Every mid-run question times out with the safe answer "no". `bash update_all.sh --doctor` is a read-only readiness report, and real runs add pre-flight checks. Persistent vendor-feed state replaces opaque "stale feed" warnings, and HyperFrames, Superset and Open Design are installed or checked without hidden launches. Earlier 1.5.x releases are described in [CHANGELOG.md](CHANGELOG.md).

Legacy vendor-feed reporting is read-only. The current manager leaves generic native and vendor adapters manual until a reviewed recipe is available. The legacy `--bootstrap-cli` flag grants no first-install permission. Acquire missing CLIs separately through their reviewed official instructions. Open apps are not closed. Check feed state with `bash scripts/check_vendor_feeds.sh`.

## Safe setup and application sources

`bash setup.sh --inspect` checks readiness without installing dependencies, changing shell profiles or configuring Touch ID. Missing tools leave the affected feature unavailable. In a terminal, `bash setup.sh --install-dependencies` previews optional dependencies and asks before each installation; `bash setup.sh --configure-shell` separately previews a shell profile change. Declining a dependency leaves independent features usable. If Python is unavailable, install it explicitly before building inventory. Missing or outdated `mas` is reported during updates and is never installed or upgraded automatically.

The normal update report covers installed applications. `bash scripts/report_update_coverage.sh --show-supported` remains a reference list. Open the optional selection menu with `bash setup.sh --catalog`; it starts with nothing selected. A selected app can be acquired from a reviewed official link after preview and fresh confirmation. Changing an existing app source requires manual migration. A CapCut App Store receipt retains App Store routing. A local app without confirmed Homebrew ownership is never adopted automatically.

Latest stable source research is recorded in [SOURCE_RESEARCH.md](docs/catalog/SOURCE_RESEARCH.md). Versions from different editions are not comparable; a current snapshot does not prove which channel is historically fastest.

---

## One-line install (new users)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

The installer clones the repo, asks for the language, checks readiness and builds this Mac's inventory when Python is available. Dependency installation requires a separate choice in setup. Touch ID and shell profiles are not changed automatically.

See [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md)

---

## What this does

`update_all.sh` runs seven steps:

| Step | Action |
|------|--------|
| 0 | **Prescan** — discover installed apps → update `APPLICATIONS.md` |
| 1 | **App Store** — Track 1: `sudo mas upgrade <app-id>`; Track 2: AppleScript GUI for iPad apps |
| 2 | **Native CLI + npm** — existing native CLIs first, then Node, Bun and global npm CLIs |
| 3 | **Homebrew** — formulae and casks (`brew_cask` + downgrade protection) + cleanup and health check |
| 4 | **Internet apps** — verified direct handlers, `sparkle_appcast`, vendor CLIs and honest update triggers |
| 5 | **Postupdate/history** — refresh `APPLICATIONS.md`, append `UPDATES.md` atomically |
| 6 | **macOS (final)** — per-label `softwareupdate -i <label> -R` (restart-required labels in the final batch); deferred after a blocking hard failure in steps 1–4 or when authorization is unavailable |

**Important:** Normal updates act only on installed software whose source was observed and whose scoped action was approved. The separate optional catalog can show absent apps, but it does not install automatically. Manual acquisition requires preview and fresh confirmation. The final macOS step may restart the Mac, so it runs last and retains mandatory `-R`. Step 5 is reporting-only. Unknown installed apps are listed for review.

Coverage is deliberately explicit: **verified direct** means the updater confirmed the package/version path; **triggered-unverified** means an app was launched to let its vendor updater run but completion cannot be proven; **externally managed** means the vendor or App Store owns the update lifecycle; **manual** requires user action; **unknown** has no registered method.

```bash
bash scripts/report_update_coverage.sh   # coverage report
bash build_inventory.sh                  # rebuild APPLICATIONS.md from this Mac
```

### Update methods
The method table is a legacy capability reference. It describes registered methods and does not authorize a current action; the scoped manager requires observed source and fresh approval.

The registry ([`config/internet_apps.txt`](config/internet_apps.txt), [`config/internet_app_methods.txt`](config/internet_app_methods.txt)) maps 47 apps to 11 methods:

| Method | Apps | Coverage | How it updates |
|--------|-----:|----------|----------------|
| `brew_cask` | 11 | externally managed | Homebrew cask (greedy only for these tokens) with downgrade protection, e.g. Brave, Obsidian, Spotify, Inkscape |
| `silent_launch` | 14 | triggered-unverified | The app's own updater as a fallback; opportunistic check against a Sparkle / electron-updater feed, otherwise reported as "launched (unverified)". Apps that have a vendor feed (ChatGPT / Codex, Claude, Cursor, Warp, OpenCode, Proton Mail, ...) are decided by that feed instead and installed from the verified vendor artifact when behind. Without a feed the method never replaces the app itself |
| `github_dmg` | 5 | verified direct | Vendor/GitHub release DMG with signature and Team ID verification, staged swap and rollback (KeePassXC, VS Code, CodeEdit, Ledger Live, Trezor Suite) |
| `msupdate` | 5 | verified direct | Microsoft AutoUpdate (`msupdate`) for Word, Excel, PowerPoint, Outlook, OneNote |
| `keystone` | 3 | verified direct | Google updater (Omaha), checked against its update history: Chrome, Gemini, Google Drive |
| `appstore_gui` | 4 | externally managed | App Store Track 2 (AppleScript) for UniFi, WiFiman, Picsart, IPMIView |
| `sparkle_appcast` | 1 | verified direct | Sparkle appcast (Proton Drive) |
| `chromium_updater` | 1 | verified direct | Chromium-based updater proof (Comet) |
| `docker_cli` | 1 | verified direct | Docker Desktop: verified DMG from its appcast when idle; fallback `docker desktop update` |
| `mau_fallback_self_update` | 1 | triggered-unverified | Teams self-updater plus an observed, verified `TEAMS21` MAU fallback when Microsoft offers it |
| `mozilla_dmg` | 1 | verified direct | Mozilla product-details version plus verified DMG, staged swap and rollback (Firefox Developer Edition) |

---

## Command-line flags

`lib/cli.sh` is the authoritative list; `bash update_all.sh --help` prints it.

| Flag | Effect |
|------|--------|
| `-y`, `--yes` | Skip the confirmation prompt |
| `-h`, `--help` | Show usage and exit `0` |
| `--doctor` | Read-only readiness report (platform, tools, launchd `PATH`, LaunchAgent, sudo, disk, power, network, last run); no sudo prompt, no run log; exit `0` ok / `10` warnings / `1` problem |
| `--dry-run` | Preview every step, mutate nothing, never ask for credentials |
| `--verify-only` | Verify installed app versions against history without mutating |
| `--json-summary` | Print a JSON result object on stdout after the run |
| `--bootstrap-cli` | The legacy CLI flag grants no first-install permission. Acquire missing CLIs separately through their reviewed official instructions. |
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

**Pre-flight (real runs only):** before step 0 the run checks free disk space, battery and network. Low disk degrades the run, a low battery skips only the macOS step (softly), and no reachable host exits `1` before any step. The Mac is kept awake with `caffeinate` for the run (`MAC_UPDATE_NO_CAFFEINATE=1` opts out). Run `bash update_all.sh --doctor` to see the same checks without running anything.

**Prompts:** every mid-run question times out after `MAC_UPDATE_PROMPT_TIMEOUT` seconds with the safe answer "no"; unrecognised input is also "no". After the master confirmation, the Homebrew and App Store steps do not ask again; the macOS step still asks.

**Open apps:** a Homebrew cask whose app is open is never upgraded; it is deferred with a "quit the app" message and the step ends with a soft warning (exit `10`).

**Direct-only and never-launch apps:** `config/vendor_launch_policy.txt` lists apps the toolkit never launches. A `direct-only` app (HyperFrames, Superset) is updated only from its verified vendor artifact; a `never-launch` app (Open Design) is only checked and, when behind, reported as "open the app to update". Neither is opened or quit, not even as a fallback after an unreachable feed.

## Environment variables

Every flag has an equivalent variable (`MAC_UPDATE_DRY_RUN=1`, `MAC_UPDATE_SKIP_SYSTEM=1`, …); these are the commonly used ones with no flag. The complete list with defaults is in [docs/agents/scripts.md](docs/agents/scripts.md#environment-variables).

| Variable | Default | Meaning |
|----------|---------|---------|
| `MAC_UPDATE_NONINTERACTIVE` | `0` | Never prompt; skips App Store Track 2 GUI automation |
| `MAC_UPDATE_NOTIFY` | `0` | Desktop notification on completion (also implied by non-interactive) |
| `MAC_UPDATE_NO_SUDO` | *set automatically* | Exported by `update_all.sh` when there is no TTY; child scripts then skip root-only tracks instead of failing |
| `MAC_UPDATE_NO_SUDO_KEEPALIVE` | `0` | Set to `1` to disable the background `sudo` timestamp refresher |
| `MAC_UPDATE_STALE_DAYS` | `45` | Days after which an unverified app is reported as stale |
| `MAC_UPDATE_MAX_LOGS` | `30` | Run logs retained in `logs/` (run summaries rotate too) |
| `MAC_UPDATE_PROMPT_TIMEOUT` | `120` | Seconds (10–900, `0` = wait forever) a mid-run yes/no prompt waits; a timeout means "no" |
| `MAC_UPDATE_MIN_FREE_GB` | `15` | Pre-flight: free space below this degrades the run |
| `MAC_UPDATE_MIN_BATTERY` | `30` | Pre-flight: on battery below this percent only the macOS step is skipped |
| `MAC_UPDATE_INTERNET_SETTLE_SECONDS` | `15` | Pause that lets a launched vendor updater rewrite `Info.plist` (`0` disables, clamped to 120; skipped when no app was launched) |
| `MAC_UPDATE_QUIT_WAIT` | `60` | Seconds (0–300) a toolkit-launched app gets to exit after the graceful `quit`; never force-killed (v1.5.5) |
| `MAC_UPDATE_QUIT_RESEND` | `10` | Seconds (1–60) between repeated graceful `quit` requests inside the wait window (v1.5.5) |
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
bash scripts/install_launchagent.sh --once-in 5
bash scripts/install_launchagent.sh --uninstall
```

`setup_touchid_sudo.sh` never touches `/etc/sudoers` and never grants
passwordless `sudo`. On macOS 14+ it uses `/etc/pam.d/sudo_local`, which survives
OS updates; on macOS 13 it patches `/etc/pam.d/sudo`, which macOS updates wipe —
re-run it after a major upgrade.

### What the scheduled background run does and does not do

The LaunchAgent runs `update_all.sh -y --skip-system` with
`MAC_UPDATE_NONINTERACTIVE=1` and `MAC_UPDATE_NOTIFY=1`.

The plist sets an explicit `PATH` (`/opt/homebrew/bin:/opt/homebrew/sbin:/usr/bin:/bin:/usr/sbin:/sbin`) because launchd's default lacks Homebrew, and the installer verifies with `launchctl print` that the job is loaded; otherwise it prints the launchctl error and exits non-zero. `--minute N` (0-59) sets the minute, `--once-in N` (1-1440 minutes from now) installs a one-shot test run and cannot be combined with `--day`/`--hour`/`--minute`, and `--check` warns about a plist without the `PATH` key (re-run the installer to fix an older install).

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

## Requirements

| Tool | Auto-installed? |
|------|----------------|
| Apple Silicon (arm64) Mac | — |
| macOS 13 Ventura or later (tested through macOS 27) | — |
| Xcode Command Line Tools | Manual installation |
| Homebrew | Manual installation: https://brew.sh |
| `mas` (App Store CLI) | Explicit consent: `setup.sh --install-dependencies` |
| Python 3.9+ | Explicit consent: `setup.sh --install-dependencies` |
| `rclone` (optional) | ✅ if chosen as cloud provider |

Intel Macs and macOS 12 or older are not supported; the scripts exit before any change.

---

## Quick start

### New user (no cloud)

```bash
# Option A — one line (recommended)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"

# Option B — manual
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh --inspect
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
├── VERSION                     # Package version (single source of truth)
├── install.sh                  # One-line installer entrypoint
├── uninstall.sh                # Remove clone (keeps Homebrew/apps)
├── setup.sh                    # First-run setup (no cloud)
├── migration_setup.sh          # Full setup + cloud wizard
├── build_inventory.sh          # Build APPLICATIONS.md from this Mac
├── update_all.sh               # Master orchestrator
├── update_*.sh                 # Individual update steps
├── run_tests.sh                # Syntax + Python + unittest + secret scan
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
├── lib/                        # Shared Bash libraries (+ lib/python/ pure helpers)
├── i18n/                       # 7-language UI strings
├── scripts/                    # Utilities (coverage report, vendor feeds, scaffold, …)
├── templates/                  # APPLICATIONS.md.template (reference)
├── tests/                      # unittest + static safety checks
├── docs/
│   ├── INSTALL.md · UNINSTALL.md · PUBLIC_RELEASE.md
│   ├── user/                   # End-user guides (7 languages)
│   ├── agents/                 # Developer / AI agent reference
│   ├── reviews/                # Index + current development records (archive/ = history)
│   └── archive/                # Superseded implementation plans
│
├── CHANGELOG.md · CONTRIBUTING.md · SECURITY.md · LICENSE
└── AGENTS.md · CLAUDE.md · GEMINI.md · CODEX.md
```

**Private files (gitignored, cloud or local only):** `APPLICATIONS.md`, `UPDATES.md`, `.dev_sync_config.json`, `.mac_update_prefs`, `.env`, `logs/`

### Individual scripts

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

Full script reference: [docs/agents/scripts.md](docs/agents/scripts.md).

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

The test suite covers bash syntax, Python compilation, static safety contracts, documentation guards and unit tests (591 automated tests).
Pull requests run Ubuntu ShellCheck, portable Python tests, and the secret scan.
The full `run_tests.sh` suite on a macOS runner runs only on `workflow_dispatch` or a `v*` tag — not on every push.

```bash
bash run_tests.sh
bash update_all.sh --dry-run -y
```

---

## Critical technical notes

- **`softwareupdate` must use `-R`** — otherwise updates download but never apply.
- **`mas upgrade` must use `sudo` and explicit app IDs** on macOS 14.8.2+/15.7.2+/26.1+ (entitlement change, see https://github.com/orgs/Homebrew/discussions/6550).
- **Bash 3.2+** throughout — no `declare -A`, `mapfile`, `readarray`.
- Downloaded app bundles are verified, installed through a rollback-safe staged swap, and mounted at unique per-session DMG mountpoints.
- Private inventory/history writes and cloud imports use atomic replacement; imports stage accepted private files before committing them.

---

## Documentation

| Audience | Start here |
|----------|------------|
| Users | [docs/user/INDEX.md](docs/user/INDEX.md) (quick start, guide and operations runbook in 7 languages) · [English quick start](docs/user/en/QUICK_START.md) |
| Install / uninstall | [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md) |
| Public GitHub vs private overlay | [docs/PUBLIC_RELEASE.md](docs/PUBLIC_RELEASE.md) · [dev_sync/README.md](dev_sync/README.md) |
| Developers / agents | [docs/agents/scripts.md](docs/agents/scripts.md) · [critical rules](docs/agents/critical_rules.md) · [exit codes](docs/agents/exit_codes.md) · [troubleshooting](docs/agents/troubleshooting.md) · [acceptance checklist](docs/agents/acceptance_checklist.md) |
| AI agent context | [AGENTS.md](AGENTS.md) (shared contract) · [CLAUDE.md](CLAUDE.md) · [GEMINI.md](GEMINI.md) · [CODEX.md](CODEX.md) |
| Release history | [CHANGELOG.md](CHANGELOG.md) |
| Contributing / security | [CONTRIBUTING.md](CONTRIBUTING.md) · [SECURITY.md](SECURITY.md) |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| New Mac | `install.sh` or `setup.sh` + `build_inventory.sh` |
| Wrong app list | `build_inventory.sh` — never copy another user's `APPLICATIONS.md` |
| App not auto-updating | `scripts/report_update_coverage.sh` → add handler per GUIDE |
| Missing `APPLICATIONS.md` | `build_inventory.sh` or `dev_sync/dev-sync-import.sh` (owner) |
| `mas upgrade` fails | `sudo mas upgrade <app-id>` |
| Cloud not configured | `bash dev_sync/provider_setup.sh` |

Full list: [docs/agents/troubleshooting.md](docs/agents/troubleshooting.md)

---

## License

[MIT](LICENSE) © macOS Updates contributors


## Optional catalog and first installation

New app signals are review proposals, not executable recipes. `bash scripts/scan_update_feeds.sh` prints an aggregated summary. Proposal export supports preview and explicit acceptance; it is redacted, stays local, and is never uploaded. `bash setup.sh --catalog` opens the optional catalog with no selection. `-y`, noninteractive runs, and EOF install nothing. In the menu, `check <number>` compares only selected sources. Results show the latest confirmed compatible stable version and date, cached for 24 hours. Unknown stays unknown. A public Mac App Store listing does not prove availability to your account, and no channel is always fastest.

The public catalog has 47 registry rows for 48 separate products and zero approved automatic first-install recipes. After preview and fresh confirmation, you can choose reviewed official links for manual acquisition. Opening a page does not install the app. Changing an existing app's source requires manual migration. The separate InstallPlan shows source, destination, version, requirements, and permissions; unknown license or cost stays labeled unknown. Any future automatic recipe needs fresh-install acceptance before enablement. The catalog does not promise automatic installation for all 48 products.
