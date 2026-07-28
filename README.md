# macOS Updates

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

> **v1.0.21** — Production-ready one-command update orchestrator for **Apple Silicon Macs running macOS 13+**. It coordinates verified package updates and honest in-app update triggers for **software already installed on this Mac**. **Multilingual** (7 languages). Optional private overlay via [`dev_sync/`](dev_sync/README.md).

**Public repo:** [github.com/KasprowiczM/macOS_updates](https://github.com/KasprowiczM/macOS_updates) · Going public: [docs/PUBLIC_RELEASE.md](docs/PUBLIC_RELEASE.md)

---

## One-line install (new users)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

The installer clones the repo, prompts for **language** (English menu, 7 locales), installs dependencies, builds **your** `APPLICATIONS.md` from apps already on this Mac, and prints which apps the project can update. It never imports another user's inventory or installs apps for you.

See [docs/INSTALL.md](docs/INSTALL.md) · [docs/UNINSTALL.md](docs/UNINSTALL.md)

---

## What this does

`update_all.sh` runs seven steps:

| Step | Action |
|------|--------|
| 0 | **Prescan** — discover installed apps → update `APPLICATIONS.md` |
| 1 | **App Store** — Track 1: `sudo mas upgrade`; Track 2: AppleScript GUI for iPad apps |
| 2 | **Native CLI + npm** — Node, Bun, global npm CLIs |
| 3 | **Homebrew** — formulae and casks (`--greedy`) + cleanup and health check |
| 4 | **Internet apps** — verified direct handlers, vendor CLIs and honest update triggers |
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
├── VERSION                     # Package version (1.0.21)
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
- **`mas upgrade` must use `sudo`** on macOS 26.x (CVE-2025-43411).
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
