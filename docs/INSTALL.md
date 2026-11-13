# Installation

**Version:** see `VERSION` in repo root (currently **1.6.4**) · **Platform:** Apple Silicon (arm64), macOS 13 to 27 · Website: <https://macos-updates.64bit.site>

## One-line install (new Mac, Apple Silicon)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/KasprowiczM/macOS_updates/main/install.sh)"
```

This will:

1. Clone to `~/Dev_Env/macOS_updates` (override with `MAC_UPDATE_DIR`)
2. Show the **language picker** (English menu; default English) and save choice to `.mac_update_prefs`
3. Run `setup.sh --inspect` to report readiness without changing dependencies, profiles or PAM
4. When Python is available, run `build_inventory.sh` to create `APPLICATIONS.md` from this Mac; otherwise report the unavailable scan
5. Print `scripts/report_update_coverage.sh` — what the project can and cannot update (localized)

Pre-clone checks (arm64, macOS version, git) are shown in English because i18n files are not available until after the clone.

Both setup paths fail before dependency or update mutations unless the Mac is Apple Silicon (arm64) and runs macOS 13 or later.

The installer **does not**:

- Import another user's `APPLICATIONS.md` from cloud
- Install applications from the maintainer's inventory
- Run `dev_sync` import (optional; for owners with a private overlay)

## Manual install

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash setup.sh --inspect
bash build_inventory.sh
bash update_all.sh --dry-run -y
```

## Explicit optional setup

`bash setup.sh --inspect` checks readiness without installing dependencies, changing shell profiles or configuring Touch ID. Missing tools leave the affected feature unavailable. In a terminal, `bash setup.sh --install-dependencies` previews optional dependencies and asks before each installation; `bash setup.sh --configure-shell` separately previews a shell profile change. Declining a dependency leaves independent features usable. If Python is unavailable, install it explicitly before building inventory. Missing or outdated `mas` is reported during updates and is never installed or upgraded automatically.

The normal update report lists installed applications. Browse supported but absent recipes with `bash scripts/report_update_coverage.sh --show-supported`. This is a reference catalog, not an installation menu. A CapCut App Store receipt retains App Store routing even without a cask. A local app without confirmed Homebrew ownership gets a source recommendation, not adoption or installation. The full source resolver and interactive source selection are planned for later stages.

Touch ID configuration remains a separate, explicitly invoked command with its own preview and confirmation, Python 3.9+ and a successful backup. Automatic PAM changes are available only on macOS 14+; macOS 13 requires manual administration. A foreign PAM configuration is never replaced by setup. The source-channel research is [here](catalog/SOURCE_RESEARCH.md).

## Owner (GitHub + cloud overlay)

```bash
git clone https://github.com/KasprowiczM/macOS_updates.git ~/Dev_Env/macOS_updates
cd ~/Dev_Env/macOS_updates
bash migration_setup.sh
bash dev_sync/dev-sync-import.sh
bash update_all.sh
```

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `MAC_UPDATE_DIR` | `~/Dev_Env/macOS_updates` | Clone location |
| `MAC_UPDATE_REPO` | GitHub URL | Alternate remote |
| `MAC_UPDATE_LANG` | (picker after clone) | Skip picker: `en`, `pl`, `de`, `fr`, `es`, `it`, `pt` |
| `MAC_UPDATE_NONINTERACTIVE` | `0` | `1` = inspection only; no mutation consent |
| `MAC_UPDATE_SKIP_INVENTORY` | `0` | `1` = skip inventory build in `install.sh` |
| `MAC_UPDATE_REF` | (clone default branch) | Tag, branch, or SHA to check out after clone (`main`, an existing release tag, …) |

The installer exits `10` when optional sources or Python are unavailable; it reports what to configure and does not claim full readiness. Homebrew itself is acquired separately from its official site.

## Verify

```bash
bash run_tests.sh
```

See also [UNINSTALL.md](UNINSTALL.md), [user/en/QUICK_START.md](user/en/QUICK_START.md) and the [documentation index in the README](../README.md#documentation).

Stage B (1.6.2) adds an opt-in observational inventory: `bash build_inventory.sh --shadow`. It records local app/package identities, source evidence and incomplete scans in private JSON, without changing `APPLICATIONS.md` or update routing. Add `--dry-run` to avoid saving state, `--json` for structured results, or repeat `--root PATH` to specify scan roots. Conflicts remain observations; source choices and execution guards arrive in stage C.

## Local inventory and scoped consent

`build_inventory.sh` collects this Mac into private JSON and renders `APPLICATIONS.md`.
Existing or manually edited Markdown is never overwritten automatically. Review
`bash build_inventory.sh --migration --preview`, then accept the exact proposal ID
with `--migration --accept ID`. Original bytes, SHA-256 and orphan notes remain local.
A migration does not inherit update permission from the old file.

Preview `bash update_all.sh --plan` or `--dry-run`; both avoid inventory, history and
preference writes. An interactive run offers concrete targets and scopes. `-y` and
unattended runs use only existing valid decisions. Use `--preferences` to change or
reset those decisions. Missing Homebrew or mas produces a capability status, never
an implicit install. Conflicting receipts and manager records defer that target.
Reviewed direct-download recipes are currently empty, so unreviewed vendor paths
remain manual. Standalone updater scripts also require the scoped plan.
