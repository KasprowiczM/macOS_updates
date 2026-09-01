# Changelog

All notable changes to **macOS Updates** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
semantic-ish versioning tracked in [`VERSION`](VERSION).

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
