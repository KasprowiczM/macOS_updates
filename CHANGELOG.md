# Changelog

All notable changes to **macOS Updates** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
semantic-ish versioning tracked in [`VERSION`](VERSION).

## [1.3.1] — 2026-08-05

Release v1.3.1 implementing the `vendor_latest` update verification handler, fixing non-TTY sudo acquisition prompts, correcting update coverage metrics, and resolving version detection issues for Claude Desktop and ChatGPT Atlas.

### Added
- **`vendor_latest` Handler & Feed Support (G1):** Implemented `internet_handler_vendor_latest` in `lib/internet_handlers.sh` to check remote versions via Sparkle appcasts, `app-update.yml`, or feed URL overrides without bundle mutation. Extended `lib/internet_registry.sh` to support optional 4-column `feed_url` format in `config/internet_app_methods.txt`.
- **System Guard & Behavioral Tests (G1.4):** Added `test_every_config_method_has_a_handler` static test ensuring every config method has a handler implementation, plus behavioral tests `test_vendor_latest_handler_exists_and_sets_status`, `test_vendor_latest_detects_newer_remote`, and `test_vendor_latest_reports_current_when_equal`.
- **i18n Translations (G1.3):** Added `vendor_latest` labels across all 7 supported languages (`en`, `pl`, `de`, `fr`, `es`, `it`, `pt`) in `scripts/report_update_coverage.sh`.

### Fixed
- **Non-TTY Sudo Prompt Fix:** Resolved sudo / Touch ID prompts in non-interactive IDE environments in `update_all.sh` by exporting `MAC_UPDATE_NO_SUDO=1` and preventing orphaned keep-alive background processes.
- **Claude Desktop Path Resolution (G3.1):** Corrected `iu_claude` in `lib/internet_app_updates.sh` from `Claude Desktop` to `Claude` so `app_version` correctly locates `/Applications/Claude.app`.
- **ChatGPT Atlas Sparkle XML Tag Parser (G3.2):** Enhanced `internet_handler_sparkle_check` in `lib/internet_handlers.sh` to extract versions from XML element tags (`<sparkle:shortVersionString>`) as well as XML attributes.
- **Coverage Metric Accuracy (G2):** Corrected `scripts/report_update_coverage.sh` to accurately map verified updaters based on active feed availability.

---

## [1.3.0] — 2026-08-05

Production release introducing the `vendor_latest` update method, fixing the cask downgrade guard, eliminating inventory duplication with normalized matching, and enhancing Microsoft AutoUpdate channel diagnostics.

### Added
- **`vendor_latest` Update Method:** Established `vendor_latest` category for fast-moving applications (Cursor, Warp, Antigravity, Antigravity IDE, Comet, Proton Mail, Proton Drive, Claude Desktop, ChatGPT). Unlinked these 9 apps from Homebrew cask management via `brew uninstall --cask --force` while keeping application bundles in `/Applications` 100% intact.
- **Behavioral Behavioral Test Suite:** Added behavioral unit tests in `tests/test_safety_static.py` (`test_version_relation_detects_downgrade`, `test_no_app_listed_in_both_group3_and_casks` with normalized matching).

### Fixed
- **Cask Downgrade Guard Fix (F1):** Fixed dead logic in `update_brew.sh`. Uses `brew info --json=v2 --cask` to accurately parse versions and artifact `.app` paths. Inverted version relation logic (`rel == "newer"`) to reliably block Homebrew cask downgrades when local installed app version is higher than Homebrew cask.
- **Inventory Deduplication Fix (F3):** Updated `build_inventory.sh` and `scripts/fix_inventory_dedup.py` to remove Homebrew casks from GRUPA 3 using normalized string matching (lowercase, punctuation stripped). Filled `desc` fields for all Homebrew casks from the Homebrew API. Verified 0 normalized overlap between GRUPA 3 and Section 4c.
- **Greedy Cask Flag Optimization:** Switched `update_brew.sh` cask outdated checks to `--greedy-auto-updates` to eliminate unnecessary 1.4 GB re-downloads for `:latest` casks.
- **Enhanced MAU Diagnostics (F4):** Enhanced Microsoft AutoUpdate diagnostics to report active channel name (`External`), installed build, offered build, stale history warning (>45 days), and actionable remediation hints across all 7 supported languages.

### Changed
- **Documentation Parity (F5):** Substantively updated all 5 non-PL/EN `README*.md` files (`de, es, fr, it, pt`) with Touch ID, LaunchAgent background execution, environment variables, update methods, and coverage tables.

---

## [1.2.0] — 2026-08-05

Major reliability, non-interactive background execution, and inventory safety release.

### Fixed
- **Sudo Pre-Authentication & Background Runs (P1):** Resolved missing sudo pre-authentication for Step 1 (`sudo mas upgrade`). Separated `_needs_sudo` pre-auth logic to check both Step 1 and Step 6. In non-TTY background sessions (launchd/cron), `update_appstore.sh` gracefully skips Track 1 with `$L_APPSTORE_NO_SUDO_SKIPPED` soft status (10) instead of failing.
- **Inventory Deduplication (P2):** Updated `build_inventory.sh` and prescan script in `update_all.sh` to remove adopted Homebrew casks from GRUPA 3 so they live exclusively in Section 4c. Added static safety test `test_no_app_listed_in_both_group3_and_casks`.
- **Cask Downgrade Protection (P3):** Added global downgrade guard in `update_brew.sh` using `internet_version_relation`. If Homebrew cask formula version is older than installed app version (e.g. Comet or Proton Mail), upgrade is safely skipped with `L_BREW_CASK_WOULD_DOWNGRADE_FMT` soft warning. Added test `test_brew_upgrade_guards_against_downgrade`.
- **Microsoft AutoUpdate Channel Diagnostics (P4):** Implemented `mau_current_channel()` helper. When MAU package holdback occurs, `update_internet_apps.sh` reports detected MAU channel (`External`, `Preview`, `Beta`, `Current`) and actionable remediation hints.
- **Documentation Parity (P5):** Updated all 7 `README*.md` files (`en, pl, de, es, fr, it, pt`) and `docs/agents/exit_codes.md` with Touch ID, launchd non-TTY behaviors, non-interactive flags, and new methods.

### Known Technical Debt
- **Stage E Refactor:** `lib/internet_app_updates.sh` refactoring deferred to future minor release to preserve verified handler stability.

---

## [1.1.1] — 2026-08-05

Production-hardening & verification release.

### Fixed
- **Desync & Verification Safety:** Implemented `internet_cask_name_for_app` slug mapping and live Homebrew cask verification check in `update_internet_apps.sh` with `L_INTERNET_STATUS_CASK_MISSING` warning.
- **Non-Interactive GUI Safety:** Explicitly skip Track 2 App Store GUI automation when `MAC_UPDATE_NONINTERACTIVE=1` or non-TTY session.
- **Format String Safety:** Replaced raw `printf "$L_..."` with `internet_msg` across `lib/internet_handlers.sh`.
- **LaunchAgent Argument Hygiene:** Added `--help` and `--day` (1-7) / `--hour` (0-23) range validation in `scripts/install_launchagent.sh`.

### Changed
- **Sparkle Coverage:** Expanded `sparkle_appcast` to `Remote Desktop Manager` and updated `scripts/report_update_coverage.sh` to classify Sparkle appcasts as verified direct updaters.
- **Version History & Rotation:** Activated `version_history.tsv` read-back, stale days warning (`MAC_UPDATE_STALE_DAYS`), and automated 365-day rotation.

---

## [1.1.0] — 2026-08-05

Major automation, verification, and bugfix release.

### Fixed
- **BUG-1 (stdout pollution):** Refactored handler functions in `lib/internet_handlers.sh` to pass status via `INTERNET_LAST_STATUS` global variable instead of stdout `echo`. Prevents UI text from polluting status variables.
- **BUG-1b & BUG-2 (settle-loop):** Fixed `STATUS_PROTON_MAIL` and `STATUS_PROTON_DRIVE` typos and unblocked settle-loop by dynamically reading `silent_launch` apps from `config/internet_app_methods.txt`.
- **BUG-3 (sudo keep-alive):** Added background sudo keep-alive process in `update_all.sh` refreshing credentials every 50s, preventing re-authentication prompts during long runs.
- **BUG-4 (sudo -v stderr):** Only suppress stderr when `MAC_UPDATE_JSON_SUMMARY=1` so interactive PAM messages are visible.

### Added
- **Homebrew Cask Migration (Faza 2):** Migrated 18 internet applications to Homebrew Cask (`brew install --cask --adopt`), reducing `silent_launch` apps from 24 down to 6.
- **Sparkle Appcast Verification (Faza 3):** Added `internet_handler_sparkle_check` to query Sparkle `SUFeedURL` directly for remote version verification.
- **Update Feed Scanner (Faza 3):** Added `scripts/scan_update_feeds.sh` to detect Sparkle/Electron/Keystone frameworks.
- **Version History TSV (Faza 3):** Automated version tracking in `logs/version_history.tsv` (chmod 600).
- **Touch ID Onboarding & Verification (Faza 4):** Integrated `scripts/setup_touchid_sudo.sh` into `install.sh` and `update_all.sh`.
- **LaunchAgent Scheduling (Faza 4):** Added `scripts/install_launchagent.sh` for weekly non-interactive launchd updates with desktop notifications (`osascript`).

---

## [1.0.21] — 2026-07-30

Hardening release. No new user-facing features; the focus was correctness of the
**step-severity contract**, integrity of downloaded payloads, and closing gaps between
what the documentation promised and what the code did.

The headline fix: several ordinary, non-mutating conditions were being reported as hard
failures, which silently deferred `softwareupdate -ia -R` — the macOS security update.
On a typical developer Mac this could suppress security updates indefinitely.

### Fixed — release blockers

- **macOS security updates are no longer deferred by non-failures.** The soft-exit code
  (`10`) contract described in `docs/agents/critical_rules.md` §10 was only implemented by
  `update_internet_apps.sh`; `update_appstore.sh`, `update_brew.sh` and `update_npm_cli.sh`
  had no soft path, so every unverifiable condition became a blocking hard failure. All four
  leaf orchestrators now share `lib/severity.sh` and classify correctly.
- **`brew doctor` warnings and `--greedy` cask residue no longer fail the run.** `brew doctor`
  is advisory, and casks with `auto_updates true` / `version :latest` can never stop being
  listed by `brew outdated --greedy`. Both previously produced a permanent hard failure.
- **`update_all.sh` no longer hangs on exit.** A `wait` on the `tee` process ran while the
  shell's descriptors were still attached to it, deadlocking the EXIT trap. Descriptors are
  now saved and restored before the wait, so failure diagnostics still reach the run log.
- **App Store Track 2 restored.** The AppleScript payload is written to a file instead of
  being piped as a heredoc through `run_with_timeout`, which silently lost the script on
  stock macOS and stopped iPad-app updates (UniFi, WiFiman, Picsart).
- **Shell profile edits are non-destructive.** `~/.zshrc` and `~/.npmrc` were replaced via
  `mv`, destroying symlinks into dotfiles repositories and resetting file modes. Edits now
  resolve symlinks, write in place, and take a timestamped backup.
- **`update_npm_cli.sh` reports mid-transaction failures as hard.** Node and Bun toolchain
  installs move the live toolchain aside before swapping; those failures are no longer
  silently discarded.

### Fixed — integrity and correctness

- Ledger Live downloads are verified against the publisher `sha512` from `latest-mac.yml`.
- Visual Studio Code uses the official update API for version, URL **and** `sha256hash`,
  and extracts with `ditto` instead of `unzip` (which does not preserve code signatures).
- Every `curl` download in `lib/internet_app_updates.sh` uses `--fail`, so HTTP errors are
  no longer written into `.dmg`/`.zip` files and misreported as mount failures.
- ChatGPT Atlas is registered as `silent_launch` to match its handler, so the coverage
  report no longer overstates its proof level; it also no longer claims the ChatGPT/Codex
  bundle.
- The Microsoft AutoUpdate quarantine no longer oscillates for products hidden by their own
  active deferral, which caused repeated multi-hundred-megabyte re-downloads.
- `softwareupdate -l` is parsed under `LANG=C LC_ALL=C`, and the Accessibility probe matches
  AppleScript error `-1743` instead of localised English text.
- `strip_ansi` uses ANSI-C quoting so it works under BSD `sed`.

### Added

- `lib/severity.sh` — shared soft/hard exit-code helpers.
- `lib/proc.sh` — single `run_with_timeout` implementation (was duplicated three times).
- Secret redaction in the `dev_sync` Python error paths and logger.
- `sudo` pre-authentication before the tee redirect, so long unattended runs do not stall
  on a password prompt at step 6.
- Inline heredoc Python is now extracted and `py_compile`d by `run_tests.sh` and CI.
- Behavioural test scenarios that execute the real leaf orchestrators against a mocked
  `PATH` and a sandboxed `HOME`.

### Changed

- Console output for steps 0, 2 and 5 is fully localised; all seven language files carry
  identical key sets (653 keys each).
- 19 silent-launch handlers migrated to the shared `internet_dispatch_silent_launch`.
- Bun resolves its latest release tag at runtime; `config/bun_version.txt` is now a
  documented minimum floor rather than a hard pin.
- `mas` gate raised to ≥ 4.1. The `sudo` requirement is now attributed to the macOS
  `installd` entitlement change rather than to an unrelated CVE.

### Security

- `.claude/settings.local.json` and two `.DS_Store` files were tracked despite `.gitignore`;
  they are untracked, and the Claude `deny` rules now ship in the tracked settings file.
- `scripts/scan_secrets.sh` and the CI workflow now fail on **any** tracked-but-gitignored
  file, not just four hardcoded names.

### Known limitations

- ~1,100 lines of Python remain embedded in `update_all.sh` heredocs. They are syntax- and
  lint-checked by CI, but not unit-tested; extracting the pure functions into `lib/python/`
  is the next planned change.
- `internet_version_relation` still spawns a Python interpreter per comparison. This is an
  accepted trade-off — an `awk` port risked altering the version-ordering semantics that the
  Microsoft AutoUpdate regression guard depends on.
- `setup.sh` and `migration_setup.sh` retain local `print_*` definitions because their
  output padding differs from `lib/ui.sh`.

---

## [1.0.20] and earlier

See `git log` and the review documents in the repository root for the history preceding this
release.

[1.0.21]: https://github.com/KasprowiczM/macOS_updates/releases/tag/v1.0.21
