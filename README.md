# macOS Updates

[EN](README.md) | [PL](README.pl.md) | [ES](README.es.md) | [FR](README.fr.md) | [DE](README.de.md) | [IT](README.it.md) | [PT](README.pt.md)

[![CI](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml/badge.svg)](https://github.com/KasprowiczM/macOS_updates/actions/workflows/ci.yml)

> **v1.0.18** — Production-ready one-command updater for **Apple Silicon Macs**. Keeps macOS, App Store, Homebrew, and 40+ internet-downloaded apps up to date — **only software you already have installed**. **Multilingual** (7 languages). Optional private overlay via [`dev_sync/`](dev_sync/README.md).

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
| 1 | **System** — `softwareupdate -ia -R` |
| 2 | **App Store** — `sudo mas upgrade` + AppleScript fallback |
| 3 | **Native CLI + npm** — Node, Bun, global npm CLIs |
| 4 | **Homebrew** — `brew upgrade` + cleanup |
| 5 | **Internet apps** — only if installed (Chrome, VS Code, Microsoft 365, …) |
| 6 | **Postupdate** — bump versions in `APPLICATIONS.md`, append `UPDATES.md` |

**Important:** Updates only touch software already installed on your Mac. Supported-but-missing apps are reported, not installed. Unknown installed apps are listed so you (or an AI agent) can add handlers.

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
├── VERSION                     # Package version (1.0.18)
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
| `build_inventory.sh` | Prescan only → `APPLICATIONS.md` |
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

Categories (from `config/internet_app_methods.txt`): `keystone`, `github_dmg`, `silent_launch`, `msupdate`, `docker_cli`, `manual`.

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
