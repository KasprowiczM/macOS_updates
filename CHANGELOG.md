# Changelog

All notable changes to **macOS Updates** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
semantic-ish versioning tracked in [`VERSION`](VERSION).

## [1.5.1] — 2026-09-25

### Fixed
- **Chrome staged rollout status (K1):** Report staged vendor rollout (`rollout_hold`) instead of missing Omaha response when Google VersionHistory indicates a newer public release not yet offered to the local Mac; avoids misleading unverified updater warnings.

### Changed
- **Documentation synced with v1.5.0 (K2):**
  - Updated `docs/agents/scripts.md` with complete documentation for all library modules, config mappings, and static guard tests (`test_every_lib_file_is_documented_in_scripts_md`).
  - Refreshed update methods table in `docs/agents/critical_rules.md` §5 with single-row vendor truth feeds, Homebrew casks, and unverified classifications.
  - Documented all v1.5.0 session files and lifecycle semantics in `docs/agents/architecture.md`.
  - Added troubleshooting entries for staged rollouts, open app preservation, Omaha recent check windows, and direct vendor installs in `docs/agents/troubleshooting.md`.
  - Synchronized core open-application safety principle across all 7 localized README files.

## [1.5.0] — 2026-09-24

Vendor truth release: version comparison against vendor release feeds, only installed applications and toolchains updated, orphan Homebrew cask detection, and drift-free inventory synchronization across all groups.

### Added

- **Vendor Feeds & Three-way Version Comparison (T1):**
  - Integrated `lib/python/vendor_feeds.py`, `lib/vendor_feeds.sh`, and `config/vendor_feeds.txt` to parse official vendor feeds (Sparkle RSS, JSON, YAML, Key-Value) with standard normalization and comparison (`version_cmp` in `lib/version.sh`).
- **Verified Vendor Direct Downloads & Atomic Bundle Swap (T2):**
  - Added `lib/vendor_direct.sh` implementing `copy_verified_app` with Gatekeeper verification (`spctl --assess`), CFBundleIdentifier and Apple Team ID validation, staged temporary swap, and automatic rollback on failure.
- **Sparkle & JSON Vendor Feed Integration (T3):**
  - Wired vendor feeds into internet app updates for ChatGPT, Claude, Cursor, Warp, Antigravity, Antigravity IDE, OpenCode, Proton Mail, and Docker Desktop.
- **Remote Desktop Manager Vendor Feed & Direct Verified Upgrade (T4):**
  - Added Devolutions productinfo Key-Value parsing and verified DMG download for Remote Desktop Manager.
- **Chromium & Google Updaters Live Status Check via Omaha Logs (T5):**
  - Re-routed Google Chrome and Gemini through Google Keystone, and Comet through `chromium_updater`, evaluating live Omaha updatecheck status (`noupdate`, `ok`, `error`).
- **Google Chrome VersionHistory Public Feed & Rollout Hold (T6):**
  - Integrated Google Chrome VersionHistory API to classify staged vendor rollouts (`rollout_hold`) cleanly without false failure alarms.
- **App Store iTunes Lookup Gate for Track 2 iPad Apps (T7):**
  - Added `lib/appstore_ios.sh` querying the public iTunes Lookup API to skip Track 2 AppleScript GUI automation cleanly when all iPad apps are already up to date.
- **Standardized Machine-Readable Internet Status Codes (T8):**
  - Standardized status codes (`ok`, `behind`, `current`, `feed_stale`, `rollout_hold`, etc.) exported to `$SESSION_DIR/internet_status_codes.txt`.
- **Orphan Homebrew Cask Detection & Interactive Cleanup (T9):**
  - Added orphan cask detection in `lib/python/brew_casks.py` (`find_orphan_casks`); orphan casks whose `.app` targets were manually deleted are skipped during upgrades and prompted for removal.
- **Only-Installed Native CLI Toolchains & Version Retention (T10):**
  - Gated CLI installations to only existing CLIs, invoking native `update` subcommands (`claude update`, `codex update`, `agent update`, `agy update`). Added `--bootstrap-cli` flag and automatic version retention pruning.
- **Drift-Free Inventory Synchronization Across All Groups (T11):**
  - Created `lib/python/inventory_sync.py` to synchronize all inventory groups (MAS, iPad, Internet, Formulae, Casks, CLI) without drift and recompute summary counts accurately.
- **Attribution of Between-Step Background Updates (T12):**
  - Added background update tracking in `lib/python/run_summary.py` comparing snapshots to attribute updates performed outside toolkit steps.
- **System Step Per-Label Installation & Batch Restart (T13):**
  - Split system updates into non-restart labels (installed individually with `-R`) and restart-required labels (installed in one batch call with `-R`). Filtered session snapshot dumps on degraded runs.
- **Vendor Feeds Diagnostic Tool (T14):**
  - Added `scripts/check_vendor_feeds.sh` for read-only inspection of vendor feeds, relations, and live Omaha updater logs in table and JSON formats.

### Fixed (post-review)

- **F0 — Test harness isolation & syntax safety:** Stop masking missing PYTHONPATH and child-process syntax errors in `run_tests.sh` and `lib/python/test_runner.py`.
- **F1 — Homebrew cask downgrade guard & .app target tracking:** Resolved Python 3 inline syntax error on multiline strings, corrected awk parser in `brew_cask_versions`, validated cask targets by `.app` bundle directory presence, and emitted `brew_cask_targets.txt`.
- **F2 — CLI version retention symlink protection:** Canonicalized symlink targets before pruning to prevent accidental deletion of active binary directories (`cursor-agent`, `codex`).
- **F3 — Drift-free inventory sync & formatting:** Handled Homebrew 7 / mas 1.9+ ndjson parsing, accurate iPad bundle identity detection via `appstore_ios.sh`, system line preservation, and formatting separators in `APPLICATIONS.md`.
- **F4 — Vendor direct atomic install & diagnostics:** Captured stderr diagnostics during Gatekeeper verification, migrated from `cp -R` to atomic `ditto`, added pre-install version checking, and enforced HTTPS redirects.
- **F5 — App Store iPad verify error handling:** iTunes Lookup API failure (`lookup_failed`) treated as unverifiable instead of false positive up-to-date success.
- **F6 — Native CLIs update without managed Node:** Native binary CLIs update independently when managed Node/npm is not installed.
- **F7 — Internet apps stale days calculation:** Stale threshold does not override verified `CURRENT` and `UPTODATE` statuses in status reporting table.
- **F8 — Docker Desktop update safety:** Polled version updates before stopping Docker background service to avoid interrupting active installations.
- **F9 — Google Omaha single wake & app targeting:** Wake Omaha / Google Keystone updater once per session and filter status checks specifically per application ID.
- **F10 — Run summary attribution & deduplication:** Attributed iPad updates to `appstore` category and deduplicated background entries for casks with alternate `.app` bundle names.
- **F11 — Documentation, i18n keys, and coverage labels:** Added localized keys across 7 languages, fixed `report_update_coverage.sh` vendor feed labels and exclusions classification, updated step 6 descriptions in all 7 READMEs, and synced environment variable defaults in `docs/agents/scripts.md`.
- **F12 — Vendor feed row exact field matching:** Replaced regex-based `grep -E` with exact field matching in `awk` to safely handle application names containing regex metacharacters.
- **G0 — Privacy guard:** review reports no longer carry inventory data; `test_tracked_files_have_no_personal_home_paths` blocks real home paths in tracked files.
- **G1–G4 — Small fixes:** `.app` hints for `pkg` casks (summary de-duplication), any iPad lookup failure is a soft warning, Omaha status also read from `updater.log.old`, npm diagnostics localized.
- **H1 / I1 — Homebrew step no longer aborts:** `brew outdated <names>` exits 1 when a named cask is outdated; only an `Error:` line on stderr counts as a failure (progress chatter is ignored).
- **H2 — Apps you have open are never closed:** only apps the toolkit launched itself are recorded and quit gracefully after the settle window; running apps get `NEEDS_RESTART`.
- **H3 — Check before launch:** OpenCode Desktop uses the vendor feed and Teams is not launched when already current.
- **H4 — Google Omaha:** one shared wait window for Chrome/Gemini/Drive, GoogleUpdater before the legacy agent, Chrome pre-check via VersionHistory, recent updater check (≤ `MAC_UPDATE_OMAHA_MAX_AGE_H`, default 6 h) accepted as proof.
- **H5 / I2 — Direct-first apps:** `config/vendor_direct_first.txt` (Cursor) skips the launch cycle and installs the verified vendor artifact when the app is not running.
- **H6 — App Store retry:** pending IDs are listed, retried in the user session and reported for manual update if still pending.
- **H7 — Test stability:** MAU process tests stub `pgrep`/`ps`.

## [1.4.6] — 2026-09-16

macOS 27 Golden Gate adaptation release. Upgrade to macOS 27 and Homebrew 7.0 revealed
gaps in cross-step toolchain coordination, major upgrade isolation, architecture awareness,
and launchd service management.

### Added

- **Xcode License Gate (P0-1):**
  - *Symptom:* Step 1 (App Store) upgraded Xcode to 27.0, after which step 3 (Homebrew) failed completely with `You have not agreed to the Xcode license`.
  - *Cause:* Upgrading Xcode resets acceptance of Apple's license agreement, breaking all downstream `git`, `clang`, and `brew` calls.
  - *Fix:* Added `xcode_license_check_and_prompt` in `lib/brew.sh` gating on `xcodebuild -checkFirstLaunchStatus` and prompting for `sudo xcodebuild -license accept`.
  - *Measurement:* `tests/test_xcode_license_gate.py`.
- **macOS System Step Honest State & Major Upgrade Policy (P0-3):**
  - *Symptom:* Declining macOS 27 major upgrade reported `OK completed` with `system_upgraded: 0` and lost available updates from summary.
  - *Cause:* `softwareupdate -ia` lumped major upgrades with security patches, and user cancellation returned 0 without recording pending state.
  - *Fix:* Added `classify_system_updates` in `lib/python/system_updates.py` to isolate same-major from major upgrades, prompting for major upgrade explicitly only when approved. Cancellation records `pending_system_updates` and exits with code 10.
  - *Measurement:* `tests/test_system_step.py`.
- **Architecture Awareness & Rosetta Deprecation Warning (P0-2):**
  - *Symptom:* macOS 27 dropped Rosetta on upgrade; Intel x86_64 apps ceased functioning without warning.
  - *Cause:* Toolkit assumed all apps were native arm64 and did not scan binary architecture.
  - *Fix:* Added `app_architecture()` in `lib/python/inventory.py` to tag x86_64 binaries with warnings about missing Rosetta and upcoming macOS 28 EOL.
  - *Measurement:* `tests/test_architecture_rosetta.py`.
- **Homebrew Cask Oracle for silent_launch (P1-7):**
  - *Symptom:* Verified apps without sparkle feeds reported unverified status indefinitely.
  - *Cause:* No secondary source of truth for current upstream version.
  - *Fix:* Added `config/cask_oracles.txt` and `brew_cask_latest_versions` in `lib/brew.sh` to cross-reference installed versions with Homebrew Cask metadata.
  - *Measurement:* `tests/test_cask_oracle.py`.
- **Stable Step Status Codes & Schema v4 (P1-8):**
  - *Symptom:* Run summaries parsed localized status strings with fragile substring heuristics.
  - *Cause:* No machine-readable status enum was exported by shell steps.
  - *Fix:* Exported `STATUS_CODE_*` (`ok|warn|error|skipped|skipped_by_user|unconfirmed`) to `$SESSION_DIR/step_status_codes.txt`; bumped `run_summary.py` to schema v4.
  - *Measurement:* `tests/test_step_status_codes.py`.
- **LaunchAgent Modernization for macOS 27 (P1-9):**
  - *Symptom:* macOS 27 launchd rejected plists carrying quarantine extended attributes; `launchctl load -w` deprecated.
  - *Cause:* macOS 27 launchd enforcement changes.
  - *Fix:* Stripped `com.apple.quarantine` via `xattr -d`; migrated to `launchctl bootstrap gui/$(id -u)` and `launchctl enable` with fallback.
  - *Measurement:* `tests/test_launchagent.py`.

### Changed

- **`mas account` Deprecation Gate (P1-4):**
  - *Symptom:* mas 7.0.0 failed on `mas account` (subcommand removed in mas 5.0+).
  - *Fix:* Gated `mas account` behind `mas_version < 5.0.0` in `lib/appstore.sh` and `setup.sh`.
  - *Measurement:* `tests/test_appstore_mas.py`.
- **Command Line Tools macOS 27 Diagnosis (P1-5):**
  - *Symptom:* `brew doctor` flagged CLT on macOS 27 as Tier 2 when versions were below 27.0.0.
  - *Fix:* Added `clt_status_diagnosis` in `lib/python/clt_status.py` enforcing `27.0.0` minimum for macOS 27.
  - *Measurement:* `tests/test_clt_status.py`.
- **Platform Support Metadata (P2-10):**
  - Updated documentation and version ranges from macOS 13–26 to macOS 13–27 Golden Gate across all agent profiles and 7 localized README files.

## [1.4.5] — 2026-09-07

Ultra-review integrity release. Overlay import could replace Git-tracked descendants and
delete local files; a failed swap plus failed restore deleted the only backup; vendor CLI
installers reported success without a working binary; pending measurements became zero when
unknown.

### Fixed

- **Overlay import overwrote Git files and dropped unlisted local data (H1).** Directory
  manifest entries were set-diffed as exact paths, then `copytree` replaced the whole
  directory. Import now expands to leaves, skips tracked/excluded files, and refuses to
  directory-swap.
- **Failed overlay swap plus failed restore deleted recovery data (H2).** The transaction
  now journals after moving the original and raises `OverlayRecoveryError` with a recovery
  path; the backup directory is left in place when restore fails.
- **Symlink ancestors escaped the overlay source root (H3).** `validate_source` walks with
  `lstat`/`resolve_under` and refuses copy before any `copy2`.
- **Codex/agy bootstrap `latest` and curl-pipe success (H4/H5).** Per-vendor args, download
  to a temp file with size/emptiness checks, then exec. Existing Claude/agy binaries use
  `update`. Exit 0 without a working `--version` is a failure.
- **OpenCode `?` reported as success (M1).** Repair runs only for an existing stub in the
  managed prefix. npm 12's `allow-scripts` user allowlist skips `postinstall.mjs`
  even when `ignore-scripts` is false; the repair child uses
  `--allow-scripts=opencode-ai` and, if the binary is still a stub, `node
  postinstall.mjs` in the managed package tree. `NPM_CONFIG_ALLOW_SCRIPTS` is
  exported only inside the `opencode upgrade --method npm` subshell. The
  toolkit never writes `~/.npmrc`.
- **Codex UI printed the product name as the version.** `codex --version`
  prints `codex-cli 0.153.4`; taking the first token reported `codex-cli`.
  `report_cli_version_or_fail` now prefers the last token when the first has
  no digit, and requires a digit afterwards.
- **Unknown pending became zero (M2).** `merge_pending` keeps `null` plus verification
  (`missing`/`empty`/`unknown`/`invalid`/`verified`). App Store verify failure writes
  `unknown`; MAU does not write `0` before measuring.
- **TERM-ignoring timeout leftover children (M3).** Fallback timeout uses a process group
  and SIGKILL; GNU `timeout --kill-after=5` remains when not forced.
- **MCP rewrite 0600→0644 (M5).** `mkstemp` in the destination directory, `fchmod` 0600 or
  stricter original; dump failure leaves the original file.
- **Inventory table edits impersonated installs (M6).** Counts are
  `inventory_version_fields_changed` vs `observed_package_changes`. The
  postupdate UI prints both lines (seven languages) instead of one “total
  version changes” figure. Run JSON is format 2, mode 0600, with
  `run_id`/`run_status`; write errors are visible. Parallel runs take a
  per-repo lock.

### Changed

- Ubuntu portable Python gate on push/PR; macOS full suite remains manual/tag.
- Gitleaks scans tracked markdown. Installer honors `MAC_UPDATE_REF`.
- rclone export writes `.dev_sync_manifest.json`; import uses that manifest, not a full
  remote listing. `run_command` has timeout and limited retries.

### Evidence

- New regression files: `tests/test_dev_sync_import_boundaries.py`,
  `tests/test_dev_sync_transactions.py`, `tests/test_cli_installers.py`,
  `tests/test_run_summary.py`, `tests/test_process_timeout.py`,
  `tests/test_mcp_config_permissions.py`, `tests/test_run_lock.py`,
  `tests/test_http_fetch.py`, `tests/test_version_consistency.py`.
- `bash run_tests.sh` 270 OK on 2026-09-07; ShellCheck warning-clean; gitleaks
  clean. Live OpenCode repair path verified (stub → 1.18.29) via scoped
  `--allow-scripts=opencode-ai` (no `~/.npmrc` write). Isolated live macOS
  install/restore remains a separate release gate.

## [1.4.4] — 2026-09-03

Run-log review release. The 2026-09-03 run hung at the Claude Code update step and never reached
Homebrew, internet apps, postupdate, or the macOS system update. The binary landed correctly
(2.1.258 → 2.1.259) but the installer's post-install TUI blocked the pipeline indefinitely.

### Fixed

- **Claude Code native installer hung the entire pipeline every run (Z0).** Anthropic's
  `install.sh` downloads the binary and then calls `"$binary_path" install` — a TUI that issues
  `stty sane` on signal death and ignores SIGTERM. GNU `timeout` without `--kill-after` waited
  forever once the TUI caught the signal. Steps 3–6 (Homebrew, internet, postupdate, system
  update) never ran. Two changes close the gap: (1) `lib/proc.sh` adds `--kill-after=5` to the
  GNU timeout path so SIGTERM is followed by SIGKILL after five seconds; exit 137 is mapped to 124
  only when the elapsed time meets or exceeds the deadline, preserving the distinction between
  a timeout kill and an unrelated SIGKILL. (2) When `~/.local/bin/claude` already exists,
  `update_npm_cli.sh` calls `claude update` instead of re-running `install.sh`; the first-install
  bootstrap path (`curl | sh -s latest`) is retained for new machines. Measured: `timeout
  --kill-after=5 60 ~/.local/bin/claude update </dev/null` exits 0 in under 10 seconds; version
  confirmed 2.1.259.
- **OpenCode CLI switched to its own self-updater.** `opencode upgrade --method npm` is the
  vendor-documented update path and keeps the install inside the managed npm prefix. The manifest
  method changed from `npm` to `self-update`.
- **Chronic step-warning detector added (Z1).** `lib/python/chronic_warnings.py` scans the
  trailing window of dated run summaries and reports any step whose status has not started with
  `"OK"` for `MAC_UPDATE_CHRONIC_THRESHOLD` or more consecutive runs. A missing step key in a
  summary terminates the trailing streak rather than being silently skipped.
  `scripts/report_chronic_warnings.sh` is called by `update_all.sh` after `write_run_summary`
  and always exits 0. August run logs: internet step warned 4 consecutive times before v1.4.3
  landed; current last-10 is clean.
- **Guard audit — all three guards pass (Z2).** Cask downgrade guard, `internet_handler_vendor_latest`,
  and npm skip filters all re-evaluate from live state every run with no persistent hidden state.
  AGENTS.md rule 10 added: every mechanism that hides its own diagnostic input must declare a
  lifetime and a path back to re-evaluation.
- **`pending_after_run_*` counts added to `run_counts.json` (Z3).** Four new integer keys track
  how many updates remained after each step: App Store (`mas_outdated_ids` of `STILL_OUTDATED`),
  Homebrew formulae and casks (from `brew_outdated_formulae`/`brew_outdated_casks`, never raw
  `brew outdated`), and Microsoft AutoUpdate (pre-install count on failure, post-install
  `MAU_REMAINING` on success).
- **App Store three-way diagnostic always written (Z4).** `appstore_diag.txt` now always contains
  three sections: `mas outdated` before TRACK 1, the TRACK 2 AppleScript result (including
  `NO_UPDATES_FOUND`), and `mas outdated` after both tracks. Previously the TOR 2 success branch
  wrote nothing, so the GUI-vs-native discrepancy seen on 2026-09-01 was not recorded.
- **Firefox Developer Edition reports both bundle version and channel (Z5).** The updated/current
  message now shows `"<version> (kanał <channel>)"`, e.g. `156.0 (kanał 156.0b1)`. The stale
  `FIREFOX_DEV_CHANNEL_VERSION=150.0b10` key deleted from `.mac_update_prefs` (local machine
  only; was not read by any script).

### Added

- `tests/test_run_log_regressions_20260903.py` — 16 regression tests covering the timeout
  kill-after semantics, Claude self-update gating, chronic streak detection, pending-after-run
  wiring, App Store diag sections, Firefox channel message, and opencode native updater method.
  229 tests total, green.

## [1.4.3] — 2026-09-02

Run-log review release. The 2026-09-01 run exited 0 but `degraded: true`, and so had 20 of the
last 26 runs. The warnings were not noise: one of them had been hiding a real Office update for
seven weeks, another had been reporting a write it could not keep ten runs in a row, and a third
had left a pending App Store update uninstalled while calling the step "unverified".

### Fixed

- **The Office quarantine could never release itself, and hid a real update for seven weeks.**
  The five `DeferralDays` entries armed by the 2026-07-14 Office Preview regression were still
  live on 2026-09-01. The release rule requires an offer whose short version is newer than what
  is installed — but an armed `DeferralDays` entry hides its product from `msupdate --list`
  entirely, so the evidence needed to release the quarantine was suppressed by the quarantine
  itself. The code assumed the entry "lapses on its own after `MAC_UPDATE_MAU_DEFERRAL_DAYS`";
  it does not — `DeferralDays` is a per-update delay that stays in the domain indefinitely.
  Result: 20 consecutive runs reported "held by deferral", every run came back `degraded`, and
  the toolkit stayed blind to Office while MAU's own daemon shipped 16.112 → 16.112.1 → 16.112.2
  behind its back. Measured on 2026-09-02 with the quarantine lifted, the feed was offering
  **16.112.3 against 16.112.2 installed** — an upgrade, quarantined for seven weeks.
  A quarantine now carries an expiry the guard controls itself
  (`MAC_UPDATE_MAU_QUARANTINE_MAX_DAYS`, default 14, clamped 1–90) recorded in
  `~/.local/state/mac-update/mau_quarantine.tsv`. Past the window it is released so the next run
  can see the feed again; if the offer is still a downgrade, `mau_regressed_entries` re-arms it
  on that run. Re-arming deliberately does **not** restart the clock — that would reproduce the
  original defect. An entry with no record counts as expired, because it predates the
  bookkeeping. The expired set is passed as the offer argument of the *same* `mau_reconcile_deferrals`
  call, never a second one: two export/import cycles in one run race each other through `cfprefsd`.
- **`DeferralVersions.TEAMS21` was released ten times and re-created every time.** A pin *at* the
  installed build is not a stale pin — it is Microsoft AutoUpdate's own bookkeeping for a product
  that owns its update cadence. Every run rewrote the user's preference domain, reported a release
  MAU undid within hours, and raised a health warning ("not the documented Major.Minor form") that
  no operator could act on. A `DeferralVersions` pin is now released only when it is **strictly
  older** than the installed build — that one genuinely caps the product forever — and the
  Major.Minor health warning is suppressed when the value matches the installed build. The
  installed build is read from MAU's own `AppVersions` register, the only like-for-like operand
  for a value MAU wrote, with `CFBundleShortVersionString` as fallback.
- **`sudo mas upgrade` silently skipped a pending App Store update.** TRACK 1 ran a bare
  `mas upgrade`, which makes `mas` re-enumerate the outdated set itself — under `sudo` that
  enumeration runs in root's context, not the one the run measured. On 2026-09-01 the pre-scan
  listed Copilot **and** WhatsApp; the command upgraded Copilot, never mentioned WhatsApp, and the
  step closed "unverified" with WhatsApp at 26.33.73 against 26.34.72 available. TRACK 1 now
  passes the explicit IDs the pre-scan measured, and anything still outdated afterwards gets one
  per-ID retry in the invoking user's session — App Store receipts and the signed-in Apple ID
  belong to the user, not to root. Measured: the same `mas upgrade 310633997` that `sudo` skipped
  completed as the user in three seconds.
- **Every `run_summary_*.json` ever written carried `"counts": {}`.** `build_run_summary()` has
  always accepted a counts mapping and the caller never passed one, so 26 consecutive summaries
  shipped an empty block and anything consuming the JSON had to re-parse the human log to learn
  how many packages moved. Step 5 now writes the numbers it already computes to
  `run_counts.json` in the session dir, and the summary reads them.

### Changed

- Microsoft AutoUpdate channel moved from `Preview` to `Current` on the reference machine
  (`defaults write com.microsoft.autoupdate2 ChannelName -string Current`). `Preview` while Office
  is built for `Current` was the root cause of the 2026-07-14 package regression and therefore of
  the whole quarantine; it had been an open decision since 2026-08-19. Note that this MAU build's
  `msupdate --config` only *displays* configuration — it cannot set it.
- `AGENTS.md` non-negotiable rule 2 narrowed: `mas upgrade` still runs under `sudo`, but with
  explicit IDs and a user-session fallback rather than as a bare command.

### Added

- `tests/test_run_log_regressions_20260902.py` — 20 regression tests covering quarantine expiry
  (including the "re-arming must not restart the clock" property), the TEAMS21 bookkeeping
  distinction, TRACK 1 explicit IDs and its single user-session retry, and the run-summary counts.
  209 tests total, green.

## [1.4.2] — 2026-08-26

Run-log review release. The 2026-08-26 run exited 0 but `degraded: true`, with four of seven
steps reporting warnings. None of the warnings were transient: every one of them was a defect
that reproduced on every run and blocked a real update indefinitely.

### Fixed

- **`codex-cli` failed on every run (`exit=124`).** The vendor native installer defaults to
  `CODEX_NON_INTERACTIVE=false` and asks `Start Codex now?` on `/dev/tty`, so redirecting stdin
  could not help; the installer blocked until `run_with_timeout 120` killed it. `codex` had been
  stuck at an old build while the step reported only a soft warning. Native installers now run
  through `native_installer_env()` (which passes `CODEX_NON_INTERACTIVE=1`) with stdin detached,
  and the hard backstop moved from 120s to `native_installer_timeout()` (default 360s) — the
  vendor script alone allows 300s for the release download, so the old cap could kill a healthy
  install. Verified live: `codex` updated 0.149.1 → 0.150.0 in under 45s.
- **Ledger Live could never pass its checksum.** `latest-mac.yml` lists the `.zip` first and
  repeats that entry's digest as the top-level `sha512:`; the handler took the *first* `sha512:`
  in the document and compared it against the `.dmg` it downloads. The mismatch was structural,
  not a corrupt download, so Ledger was pinned at 4.15.0 while 4.17.1 shipped. The DMG url and its
  digest are now read from the same manifest entry. Verified by downloading 4.17.1 and checking
  both digests: the DMG's matches, the ZIP's does not.
- **`brave-browser` was skipped by the cask downgrade guard, permanently.** The guard compared the
  app bundle's `CFBundleShortVersionString` (`151.1.93.138` — the Chromium major prefixed to
  Brave's own version) against the cask version (`1.93.138.0`), read `151 > 1`, and concluded the
  installed app was newer. The guard now prefers Homebrew's own recorded installed version, and
  the bundle-version fallback goes through the new scheme-aware
  `app_vs_package_version_relation()` in `lib/version.sh`, which realigns a vendor prefix before
  comparing and reports `unknown` rather than inventing a downgrade out of incomparable numbers.
- **Microsoft AutoUpdate deferral releases were reported without being verified.** The reconcile
  step verified `armed` writes against the live domain but took `removed` on the strength of
  `plutil -remove` exiting 0 against an exported copy. Three runs in a row printed
  `✅ Released … DeferralVersions.TEAMS21` while the pin was still in
  `com.microsoft.autoupdate2`. Removals are now measured against the live domain; a pin MAU
  re-created is reported as still present (`L_INTERNET_MS_DEFERRALS_NOT_RELEASED_FMT`) and marks
  the step soft-failed instead of being claimed as cleared.
- **The prescan re-reported its own bookkeeping as new applications.** `norm_name()` did not strip
  the `🆕` marker the toolkit appends when it adds an app to `APPLICATIONS.md`, so
  `GarageBand 🆕` never matched the installed `GarageBand` again. Two inline copies of
  `norm_name()` in `update_all.sh` shadowed the canonical one and reintroduced the old rules;
  both are gone, and the canonical normalizer drops symbol, modifier and format characters.

### Changed

- **Antigravity no longer warns `⏭️ Nieznana wersja` on every run.** Its electron-updater endpoint
  expects platform and arch parameters and answers 404 to `latest-mac.yml`, so there is no
  manifest to parse and nothing wrong with the run. An unreachable manifest on an app that has a
  feed is now reported as informational (`L_INTERNET_FEED_NOT_MACHINE_READABLE_FMT`); a feed that
  responds but yields no version still warns.

### Added

- **`app_vs_package_version_relation()`** in `lib/version.sh` — scheme-aware version comparison for
  package-manager records against application bundle versions.
- **`tests/test_run_log_regressions_20260826.py`** — 19 regression tests, one group per root cause
  above, including a check that every language file defines the three new i18n keys (189 tests
  total, all green).

## [1.4.1] — 2026-08-19

Post-migration hardening release. First full run on a new MacBook (macOS 26.6.2, Homebrew
6.0.18-48-gad5738c) exited 1 and deferred the macOS system update; none of the three causes
were real breakage.

### Fixed

- **False hard failure: "Formulae still outdated after upgrade".** `REMAINING_FORMULAE=$(brew outdated --formula 2>&1 | strip_ansi)` merged brew's stderr progress chatter (`==> Downloading Homebrew API data`, `✔︎ JSON API packages...jws.json`) into the captured value. A non-empty value meant "still outdated" → `HARD_FAIL=1` → `BLOCKING_EXIT=1` → step 6 (macOS security updates) skipped on a machine where every formula was current. All four `brew outdated` capture sites now route through `brew_outdated_formulae` / `brew_outdated_casks` in `lib/brew.sh`, which keep stderr out of the value and drop progress lines.
- **Upstream Homebrew regression `uninitialized constant Cask::CaskLoader`.** `brew list --cask --versions` broke in brew commit `ad5738cd77`; `brew update` pulled it mid-run. The post-update cask snapshot failed, and `update_internet_apps.sh` reported all 11 `brew_cask` apps as "cask not installed" while all 12 casks were in fact present. New `brew_cask_versions()` falls back to `brew list --cask` plus the `$(brew --prefix)/Caskroom/<token>/<version>` layout.
- **Split-brain Node/CLI toolchain.** `ensure_toolchain_paths` handed Node/npm ownership to nvm whenever `~/.nvm/nvm.sh` merely existed, while still installing global CLIs into `~/.local/share/mac-update/`. Nothing on the interactive `PATH` pointed there, so the pipeline reported green against copies the user never ran (terminal node v24.13.0 vs "updated" v26.7.0; npm 11.13.0 vs 12.0.2; codex 0.147.0 vs 0.148.0; opencode 1.17.18 vs 1.18.18). The managed prefix now wins by default; set `MAC_UPDATE_NVM_OWNS_NODE=1` to opt back into the old behaviour.
- **"SCRIPT 4 COMPLETED SUCCESSFULLY" banner printed above a non-zero exit** in `update_brew.sh`, and soft warnings were reported with the same red error text as hard failures.
- **Missing markdown table headers in `APPLICATIONS.md`.** 14 GRUPA 3 tables had a separator row with no header row above it, so they did not render as tables.

### Changed

- **`claude-code` and `codex-cli` now update through their own updaters** (`claude update`, `codex update`) instead of `npm install -g @latest`, joining `agy-cli`. Self-updaters that shell out to a bare `npm install -g` are run with `npm_config_prefix` pinned to the managed prefix — without it, `codex update` silently installed into the *node* prefix, which loses to `NPM_GLOBAL_BIN` on `PATH`, reporting success while the stale binary kept winning `command -v`.
- **Profile backups are rotated and mode-600.** `declare_profile_backup` kept one copy of `~/.zshrc` per run forever; 36 had accumulated, each a frozen copy of whatever secrets the live profile held. Keeps the newest `MAC_UPDATE_MAX_PROFILE_BACKUPS` (default 5).
- **`scripts/scan_secrets.sh` gained a local, advisory-only dotfile scan.** gitleaks only sees tracked git content, so a plaintext credential in `~/.zshrc` / `~/.zshenv` was invisible to the whole test suite. Never fatal; skip with `MAC_UPDATE_SKIP_PROFILE_SCAN=1`.

### Removed

- **ChatGPT Atlas.** Uninstalled by the user (browser discontinued). Purged from `config/internet_apps.txt`, `config/internet_app_methods.txt`, `config/internet_dispatch_order.txt`, `lib/internet_apps.sh`, `lib/internet_app_updates.sh` (`iu_chatgpt_atlas`), `update_internet_apps.sh` (`STATUS_ATLAS`), `scripts/report_update_coverage.sh`, `scripts/audit_cask_candidates.sh`, `APPLICATIONS.md` and `UPDATES.md`. A regression test asserts no live surface references it.

### Added

- **`lib/brew.sh`** — resilient Homebrew query helpers (`brew_cask_versions`, `brew_formula_versions`, `brew_outdated_formulae`, `brew_outdated_casks`), so a single upstream `brew` bug can never block the macOS security-update step again.
- **7 new regression tests** in `tests/test_safety_static.py` covering every fix above (167 total, all green).

## [1.4.0] — 2026-08-14

Major quality, observability, and architecture release based on the comprehensive August 2026 review.

### Added

- **`lib/version.sh` shared version utilities.** Canonical `app_version()` (with `CFBundleShortVersionString` → `CFBundleVersion` → `mdls` fallback) and `internet_version_relation()` now live in a single shared library sourced across `update_brew.sh`, `update_internet_apps.sh`, and `lib/internet_app_updates.sh`.
- **`lib/python/inventory.py` & `lib/python/run_summary.py`.** Pure-function Python modules for app normalization, bundle discovery, version detection, exclusions loading, and structured JSON run summary generation (strictly complying with AGENTS.md rule 4).
- **`config/inventory_exclusions.txt`.** Dedicated exclusion list allowing specific installed apps (such as `Ascendo` or `Utilities`) to be excluded from prescan discovery and auto-insertion into `APPLICATIONS.md`.
- **`--verify-only` mode.** Re-verifies installed application versions against `logs/version_history.tsv` without performing any system mutations; emits a formatted verification table and exits 0 (clean) or 10 (soft unverified).
- **Machine-readable JSON run report.** Generates structured run summary at `logs/run_summary_<timestamp>.json` and updates `logs/run_summary_latest.json`.
- **Gated Microsoft AutoUpdate remediation (`MAC_UPDATE_MAU_CLEAR_DEFERRALS=1`).** Safely clears blocking MAU update deferrals via `defaults delete com.microsoft.autoupdate2` when explicitly requested.

### Fixed

- **Dead cask downgrade guard in `update_brew.sh`.** Sourced `lib/version.sh` and `lib/internet_i18n.sh`, ensuring `app_version()` and `internet_version_relation()` are always available and active during Homebrew cask upgrades.
- **`installed_apps_after.txt` snapshot semantics.** Prescan now writes to `installed_apps_scan.txt`, while Step 5 captures a fresh post-update snapshot to `installed_apps_after.txt` (or copies in `--inventory-only` mode).
- **Deprecated `datetime.utcnow()` warnings.** Replaced all instances in `lib/internet_apps.sh` with timezone-aware `datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)`.
- **Repository hygiene.** Moved large history archive to `scratch/` and cleaned local temporary artifacts.

## [1.3.1] — 2026-08-05

Production release. Closes the verification gap for self-updating applications, removes
two classes of false reporting, and makes unattended and IDE-hosted runs stop asking for
credentials they do not need.

### Added

- **Opportunistic feed verification for self-updating apps.** An app whose only documented
  update path is its own updater may still publish a machine-readable version feed. The
  `silent_launch` dispatcher now probes for one — Sparkle `SUFeedURL` in `Info.plist`, then
  electron-updater `Contents/Resources/app-update.yml` — and when a feed answers, reports a
  real comparison (`Up to date (x)` / `Update available: x → y`) instead of
  `Launched (unverified)`. When no feed exists, or it cannot be parsed, the status degrades
  to the historical launch-and-report behaviour rather than claiming a check that did not
  happen. Verification never installs or replaces a bundle — the app's own updater still
  does all installing.
- **`internet_handler_vendor_latest()`** in `lib/internet_handlers.sh` — the shared feed
  reader behind the above, with a 15 s timeout and two retries.
- **`test_every_config_method_has_a_handler`** — a systemic guard asserting that every
  method name appearing in `config/internet_app_methods.txt` resolves to a real handler.
  This makes it impossible to ship a config label with no implementation behind it, which
  had happened twice before.
- **Behavioural sudo tests** — `test_sudo_is_never_attempted_without_a_tty`,
  `test_sudo_is_acquired_at_exactly_one_place`, `test_dry_run_never_requests_sudo`,
  `test_sudo_keepalive_pid_is_not_reset_after_start`. Each fails if the corresponding
  guarantee is removed.

### Fixed

- **Comet reported a verified status for a check that never ran.** It was classified as
  `keystone`, but Google Keystone only serves Google products; the agent was invoked and
  the run reported `✅ Checked via CLI` while nothing had verified Comet. Reclassified, and
  the remaining `keystone` entries audited down to Google Chrome and Google Drive.
- **sudo prompted on every invocation from an IDE or agent shell.** `update_all.sh` called a
  bare `sudo -v` on the branch taken when stdin is not a TTY, which escalates to the GUI
  askpass / Touch ID dialog. Without a controlling terminal the toolkit now requests nothing,
  exports `MAC_UPDATE_NO_SUDO=1`, and the child steps skip their root-only tracks and report
  soft (10) instead of failing.
- **`--dry-run` asked for credentials.** A preview now never requests sudo.
- **The sudo keep-alive was orphaned once per run.** `SUDO_KEEPALIVE_PID` was reset to empty
  *after* the refresher had started, so `cleanup_session_dir()` killed the wrong PID and the
  process outlived the script. Acquisition is now a single block: initialised before start,
  started exactly once, killed on every exit path including `INT`/`TERM`.
- **A warm sudo timestamp no longer triggers a second prompt** — `sudo -n true` is checked
  before prompting.
- **Coverage metric counted unverified methods as verified.** `scripts/report_update_coverage.sh`
  no longer advertises a method in `DIRECT_METHODS` that cannot compare a remote version.
- **Claude Desktop** — `iu_claude` looked for `Claude Desktop`; corrected to `Claude` so
  `app_version` resolves `/Applications/Claude.app`.
- **ChatGPT Atlas** — `internet_handler_sparkle_check` now reads
  `<sparkle:shortVersionString>` as an element as well as an attribute.

### Changed

- Development artefacts (ultra reviews, implementation reports and prompts) moved out of the
  repository root into `docs/reviews/`. The root now contains only product files.

### Known debt

- `lib/internet_app_updates.sh` is ~86 KB across 36 per-app handler functions. The
  config-driven registry now exists alongside it; collapsing those handlers into generic
  config-driven ones is deferred to a later release.
- macOS system updates on Apple Silicon require volume-owner credentials, so scheduled
  background runs deliberately pass `--skip-system` and do not install macOS or App Store
  updates. Both remain available in interactive runs.

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
