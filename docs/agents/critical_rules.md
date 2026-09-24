# Critical Rules — Do NOT Violate

## 1. softwareupdate MUST use `-R` and per-label selection
```bash
sudo softwareupdate -i "$label" -R --verbose   # CORRECT — writes boot metadata
# Without -R: update downloads but NEVER applies after reboot
```
`-R` only restarts or shuts down when required, so it is safe to keep on every install path. If the user declines a restart-required update, do not install it without `-R`; exit non-zero with manual instructions.

Never run bare `softwareupdate -ia`: it attempts to install all updates indiscriminately, including major macOS upgrades across releases (e.g. macOS 28.0 from macOS 27.0). Updates must be classified by major version:
- Point/security updates (`same_major` and `other` components) are installed per label.
- Major upgrades (`major`) require `MAC_UPDATE_ALLOW_MAJOR_UPGRADE=1` and explicit confirmation. If declined, exit code is 10 (`SKIPPED_BY_USER`).
- On macOS 27+, `softwareupdate -l` labels may omit marketing codenames (e.g. `macOS 28.0-26A...` or `macOS 27.1 Update`), parsed by Title and Version headers rather than relying on codenames.

## 2. mas MUST use `sudo` (macOS 15.7.2+/14.8.2+/26.1+ entitlement change, see https://github.com/orgs/Homebrew/discussions/6550)
```bash
export MAS_NO_AUTO_INDEX=1   # suppress Spotlight warnings
sudo env MAS_NO_AUTO_INDEX=1 mas upgrade $MAS_TOR1_IDS   # explicit IDs, never a bare upgrade
```

## 3. App Store — Two tracks
- **Track 1:** `sudo mas upgrade` — native macOS apps
- **Track 2:** AppleScript GUI (`osascript`) — iPad apps (UniFi, WiFiman, myCANAL, Picsart)
  - Requires Accessibility permission in System Settings
  - This is a separate track, not a fallback for Track 1; unexpected GUI states fail honestly
  - `mas outdated` cannot prove the state of iPad apps, so Track 2 keeps its own result

## 4. Version detection
```bash
defaults read "/Applications/App.app/Contents/Info" CFBundleShortVersionString
```
- **Firefox Dev Edition:** `application.ini` → `grep "^Version=" | cut -d= -f2` gives the **base** version (no beta suffix). Compare with `sort -V` against Mozilla product-details and never downgrade (local may legitimately be ahead of the published beta).
- **GitHub tags:** strip the leading `v` with `sed 's/^v//'` (never `tr -d 'v'`, which deletes every `v`) before comparing with `app_version()`.
- **iOS/iPadOS apps on Apple Silicon** (UniFi, WiFiman, …): no `Contents/Info` plist — `app_version()` falls back to `mdls -name kMDItemVersion`.

## 5. Cask Adoption & Validation Requirement
- **Config `brew_cask` requires live adoption:** Setting `brew_cask` in `config/internet_app_methods.txt` requires executing `brew install --cask --adopt <slug>`.
- **Validation Interlock:** `update_internet_apps.sh` validates `brew_cask` entries against `brew_cask_versions` (`lib/brew.sh`) mapped via `internet_cask_name_for_app`. Never call `brew list --cask --versions` directly — it regressed upstream on 2026-08-19 and silently returned nothing. Missing casks produce `L_INTERNET_STATUS_CASK_MISSING` soft warning.

## 6. Internet Handlers & Status Contract
- Handlers in `lib/internet_handlers.sh` pass status via `INTERNET_LAST_STATUS` global variable.
- Handlers must NEVER output status constants via `echo` on stdout. Format strings use `internet_msg` helper.
- **Why:** dispatchers used to capture handler output with `st="$(handler …)"`. Because the
  same handlers also print UI through `print_info` / `print_step`, that UI landed inside the
  status variable — 19 apps rendered a four-line block in a one-line summary cell, and the
  settle-loop comparing `$st` to a status constant never matched. The global is what makes
  that class of bug impossible.

## 6a. A config method name is only valid if a handler exists

Adding a method to `config/internet_app_methods.txt` without implementing its handler is a
**silent no-op**: the app falls through to whatever handler is still wired, and the config
advertises behaviour that does not run. This has shipped twice — `brew_cask` (v1.1.0, 18 apps
left unmanaged) and `vendor_latest` (v1.3.0, 9 apps still unverified).

`tests/test_safety_static.py::test_every_config_method_has_a_handler` enforces this. Do not
weaken or skip it.

## 6b. "Verified" must mean a remote version was actually compared

A method may only appear in `DIRECT_METHODS` in `scripts/report_update_coverage.sh` if it
genuinely fetches a remote version and compares it to the installed one. Counting a
launch-and-hope method as verified inflates the coverage metric — the single number used to
judge this project — and hides apps that have silently stopped updating.

Corollary: `keystone` is valid **only** for Google products (Chrome, Google Drive, Gemini). The
Google Software Update agent serves no other vendor. Classifying a non-Google app as
`keystone` produces a green "Checked via CLI" for a check that never happened; Comet is a
Chromium-based browser that ships its own updater and uses `chromium_updater`.

## 6c. Never call interactive `sudo` without a controlling TTY

A bare `sudo -v` with no TTY escalates to the GUI askpass / Touch ID dialog. In an IDE task
runner or agent shell this fires on every invocation and makes ordinary commands look as
though they need elevation.

`update_all.sh` therefore has exactly **one** sudo acquisition block, governed by:

1. **At most one prompt per run** — `sudo -n true` is checked first, so a warm timestamp
   never re-prompts; a keep-alive then refreshes it every 50 s.
2. **Never without a TTY** — the toolkit exports `MAC_UPDATE_NO_SUDO=1` and child scripts
   skip their root-only tracks, reporting soft (`10`) instead of failing.
3. **Never during `--dry-run`** — a preview must not ask for credentials.

The keep-alive PID must be initialised **before** the process starts. Resetting
`SUDO_KEEPALIVE_PID` afterwards orphans the refresher so it outlives the script — that
regression shipped in v1.2.0. Four tests in `tests/test_safety_static.py` (`test_sudo_*`)
enforce all of the above; each fails if the guarantee is removed.

## 6d. Touch ID is per-machine and cannot be distributed by git

`scripts/setup_touchid_sudo.sh` writes `/etc/pam.d/sudo_local` — root-owned and outside the
repository. `git pull` on a second Mac never brings it. Every machine needs the script run
once. On macOS 14+ `sudo_local` survives OS updates; on macOS 13 the script patches
`/etc/pam.d/sudo`, which macOS upgrades overwrite, so it must be re-run after a major upgrade.
Never touch `/etc/sudoers`; never grant passwordless `sudo`.

## 5. Internet app update methods

| Method | Apps |
|--------|------|
| Mozilla product-details/download + DMG | Firefox Dev |
| GitHub API / Official Metadata + DMG | KeePassXC, CodeEdit, Trezor Suite, Ledger Wallet / Live |
| Google Keystone | Chrome, Google Drive, Gemini |
| Chromium Updater | Comet (Perplexity AI) |
| msupdate CLI | Word, Excel, PowerPoint, Outlook, OneNote; observed `TEAMS21` fallback when MAU offers it |
| Vendor self-updater + MAU fallback | Microsoft Teams normally owns its cadence; MAU may recover a failed Teams updater |
| Docker CLI | Docker Desktop v4.37+ |
| Native/npm/self-updating CLI | Node.js, npm, pnpm, bun, Claude Code CLI, Codex CLI, OpenCode CLI, Agy CLI, cursor-agent |
| Homebrew cask (greedy only for brew_cask-designated tokens) | Brave, Obsidian, Spotify, AppCleaner, CapCut, MEGAsync, ProtonVPN, zoom, LM Studio, Perplexity, Inkscape (avoids re-downloading :latest casks; downgrade guard in update_brew.sh protects against version regressions) |
| Built-in auto-updater (silent launch, triggered-unverified) | Brave, ChatGPT/Codex desktop, Claude, Perplexity, Antigravity, Antigravity IDE, LM Studio, OpenCode, ProtonVPN, Proton Mail, Proton Drive, MEGAsync, Zoom, Warp, AppCleaner, Spotify, CapCut, Remote Desktop Manager, Cursor, Obsidian |
| Hybrid self-update + MAU fallback | Teams (`TEAMS21` is accepted only when surfaced by MAU and is verified by a final `msupdate --list`) |
| App Store GUI Track 2 | UniFi, WiFiman, Picsart |
| Manual only | IPMIView, DJI Assistant 2 |

These methods are not equivalent proof levels:

- **verified direct** — the script verifies a version/package path or a vendor CLI reports completion.
- **triggered-unverified** — the app was launched to trigger its built-in updater; completion is not asserted.
- **externally managed** — the App Store or vendor owns the update lifecycle outside a directly verifiable handler.
- **manual** — the registry intentionally requires user action.
- **unknown** — no supported registry method matches the installed app.

## 6. Downloaded installers
- Use random temp paths under `$MAC_UPDATE_SESSION_DIR` or `mktemp`.
- Run `hdiutil verify` before mounting downloaded DMGs.
- Mount each DMG at a unique mountpoint inside `$MAC_UPDATE_SESSION_DIR`; never discover an installer by scanning shared `/Volumes` names.
- Copy `.app` bundles with `ditto` (preserves code signature, xattrs, resource forks — `cp -R` does not). Quit the running app first, verify the incoming bundle's identifier and signing team against the installed target, run `spctl --assess --type execute`, stage the replacement, then swap it in with a retained backup. If the copy or post-swap validation fails, restore the original app before returning non-zero.
- Verify `.pkg` installers with `pkgutil --check-signature` before `sudo installer`.
- Do not report success after a failed copy/install; return a non-zero exit so `update_all.sh` records a failed step.
- **Honest status:** a GUI app that is only launched reports `LAUNCHED_UNVERIFIED` (⏳), not success; a failed launch reports `LAUNCH_FAILED` (⚠️) and fails the step. Only a confirmed version change reports `UPDATED`/`CURRENT`.

## 7. Private state and imports

- Write `APPLICATIONS.md`, `UPDATES.md`, provider config and logs through a same-directory temporary file, flush/fsync where implemented, then `os.replace()`.
- Private config is mode `0600`; log/config directories are private to the user.
- Cloud imports stage only allowlisted, safe relative paths. Commit the staged set transactionally and roll back already replaced targets if any later file fails.
- Rclone listing/copy failures are fatal; never turn an incomplete remote listing into a successful empty import.

## 8. APPLICATIONS.md structure
- GRUPA 1: Apple system apps
- GRUPA 2: App Store (mas IDs)
- GRUPA 3: Internet apps
- GRUPA 4: Tooling (4a key ⭐, 4b deps, 4c casks, 4d native CLI + npm)
- Never paste `APPLICATIONS.md`/`UPDATES.md` content or diffs into tracked files — keep them in `scratch/`.

## 9. Microsoft AutoUpdate version regressions

- Treat `Installer succeeded with no version change`, PackageKit `Skipping component`, or delta `postinstall` code 112 as a package-version investigation, not proof that MAU itself is broken.
- Compare both `CFBundleShortVersionString` and `CFBundleVersion` for the installed Office app and offered package. PackageKit can reject a package with a newer build number when its short version is lower.
- Never bypass that protection by editing a signed Office bundle, deleting it, or forcing a lower short-version component into place.
- If Microsoft has published a malformed `Recommended` Preview update, use its documented per-app `OptionalUpdatesDeferrals` mechanism as a temporary quarantine. Preserve existing nested deferrals; critical updates must remain eligible.
- Deferral-day preferences persist across releases. Remove only the incident-specific app IDs after Microsoft corrects the feed, then require a clean `msupdate --list`.
- The evidence and reversible commands for the 2026-07-14 and 2026-07-28 Preview incidents are in `docs/agents/troubleshooting.md`.

### 9a. Automated regression guard (`lib/internet_app_updates.sh`)

The quarantine is now maintained by the toolkit instead of by hand:

- `mau_regressed_entries` compares the **short version** the feed offers for each
  pending product ID against the installed `CFBundleShortVersionString`. Only a
  **strictly older** offer counts as a regression — an equal short version with a
  newer build is a legitimate build-only update that PackageKit accepts, and
  quarantining it would block real updates.
- Never compare `CFBundleVersion` against a short version. `16.111.26071215` and
  `16.111.5` are different numbering scales and mixing them inverts the test.
- Regressed products are **not** passed to `msupdate --install`. Retrying them
  re-downloads multi-hundred-MB packages that provably cannot install.
- `mau_deferral_preflight` must **not** clear the Office `DeferralDays`
  quarantine — it runs before `msupdate --list`, so it cannot yet know whether a
  deferral is stale or still protective. Clearing it there unconditionally is what
  caused a failing re-download on every run. Only `mau_reconcile_deferrals`, which
  runs after the list, may arm or release it.
- An **active `DeferralDays` entry hides the product from `msupdate --list`**.
  An empty list is therefore *not* evidence the feed was corrected, and the
  quarantine must never be released on that basis — doing so armed and released
  it on alternating runs forever. Release only on positive evidence: an offer
  whose short version is newer than what is installed.
- Arming uses `MAC_UPDATE_MAU_DEFERRAL_DAYS` (default 7, clamped to Microsoft's
  documented 1-28). The window doubles as how long the toolkit stays blind to a
  corrected package, so the 28 maximum is deliberately *not* the default.
- **Never `killall cfprefsd` after `defaults import`.** The import hands the
  write to the preference daemon, which flushes lazily; killing it immediately
  discards the write while the script still reports success. Restart MAU only.
  `mau_reconcile_deferrals` re-reads the domain afterwards and fails loudly if
  the change did not land.
- Exactly one function may import preferences. `mau_deferral_preflight` is
  read-only: two export/import cycles in one run raced each other and
  resurrected entries the first pass had removed.
- A live quarantine reports `L_INTERNET_STATUS_MAU_QUARANTINED`, classified as a
  **soft** failure (exit 10). It surfaces as a warning and never defers the macOS
  system update.
- `MAC_UPDATE_MAU_KEEP_DEFERRALS=1` disables all deferral mutation; `--dry-run`
  reports the intended change without writing preferences.
- `MAC_UPDATE_MAU_CLEAR_DEFERRALS=1` forces removal of active deferrals via
  `defaults delete` to test feed recovery or clear stale quarantines.

## 10. npm 12 lifecycle scripts stay per-package

npm 12 does not run dependency `postinstall` unless the package is on the
user `allow-scripts` allowlist. Scope `--allow-scripts=<pkg>` (and
`NPM_CONFIG_ALLOW_SCRIPTS`) to the child that installs that package. Never
write a global `~/.npmrc` exception from this toolkit. A CLI whose
`--version` is `?` or whose binary is the vendor stub is a failed update,
not success.

## 11. Centralized Version Normalization (`lib/version.sh`)

- `app_version()` and `internet_version_relation()` must be sourced from `lib/version.sh` across all components (`update_brew.sh`, `update_internet_apps.sh`, `lib/internet_app_updates.sh`).
- Never maintain duplicate or diverging implementations of `app_version()` or version comparison functions across scripts.

## 12. Inventory Exclusions (`config/inventory_exclusions.txt`)

- Apps listed in `config/inventory_exclusions.txt` (such as `Ascendo`, which was intentionally removed from the update pipeline on 2026-08-14) are excluded from `APPLICATIONS.md` discovery and inventory scans.
- `lib/python/inventory.py:load_exclusions()` parses this file and filters matches during prescan.

## 13. Step Severity Contract and Non-blocking Update Gating

- Child `update_*.sh` scripts return exit codes adhering to the severity contract:
  - `0`: Clean execution without issues.
  - `10`: Soft / degraded result (e.g. offline check, unverified launch, missing remote feed). Surfaces as warnings in banners, logs, and `UPDATES.md`.
  - `1` / `127`: Hard failure (e.g. broken installation, corrupt download, failed bundle swap).
- `update_all.sh` tracks `BLOCKING_EXIT` separately from `OVERALL_EXIT`. Only hard failures defer the final `softwareupdate -i <label> -R` step. Soft warnings never suppress macOS system updates.

## 14. macOS 27 Golden Gate Constraints and Ecosystem Rules

- **Xcode License Gate after App Store Update:** macOS 27 invalidates or requires re-acceptance of the Xcode license agreement upon upgrading Xcode via `mas`. `update_brew.sh` and any toolchain consumers must gate on `xcodebuild -checkFirstLaunchStatus` and prompt the user to accept (`sudo xcodebuild -license accept`) before running Homebrew commands to avoid catastrophic failure across the entire Homebrew step.
- **Rosetta Translation Lifecycle & EOL 28:** macOS 27 drops preinstalled Rosetta; Apple Silicon systems do not retain it across upgrades. Any Intel-only x86_64 apps (e.g. DJI Assistant 2) must be flagged with `[x86_64: Rosetta missing — will not run]` (or warning in inventory) and warned that Rosetta is completely removed in macOS 28. Do not attempt silent background reinstallation of Rosetta.
- **Command Line Tools on macOS 27:** Homebrew 7.0+ sets `minimum_version "27.0.0"` for CLT on macOS 27. Older CLT versions (e.g., 26.x CLT from macOS 26) trigger `CLT does not support macOS 27` Tier 2 warnings under `brew doctor`.
- **Installer Packages (`.pkg`) Default to arm64:** On macOS 27, package installers without an explicit `hostArchitecture` tag default to `arm64`. Any custom `.pkg` scripts must specify hostArchitecture or be verified arm64-native.
- **Launchd Quarantined Plist Rejection:** `launchd` on macOS 27 strictly rejects loading property lists carrying extended quarantine attributes (`com.apple.quarantine`). `scripts/install_launchagent.sh` must strip quarantine (`xattr -d com.apple.quarantine`) and use domain-targeted `launchctl bootstrap gui/$(id -u)` and `launchctl enable` instead of legacy `load -w`.
- **TCC.db Inaccessibility:** Direct read or query of `TCC.db` is blocked by SIP on macOS 27. Permission checks (such as Accessibility for Track 2 App Store updates) must use API/AppleScript probes (`osascript`) rather than SQLite inspection.
- **TLS 1.2+ / ATS for Update Handlers:** Network requests and sparkle/vendor feed downloads must comply with App Transport Security and TLS 1.2+ minimums.

## 15. Vendor Truth (v1.5.0)

- **Source of truth:** The vendor's own release feed (`config/vendor_feeds.txt`) or live Omaha updater query is the authoritative truth for version comparison. Homebrew cask version is only a second voice: it may confirm that an app is behind, but equality confirms "current" only when no vendor feed is configured (`current_cask_only`).
- **Feed stale guard:** When `remote < local`, the condition is treated as `feed_stale`, preserving the local installed version rather than regressing or downgrading.
- **Check before action:** Do not launch applications, virtual machines, or vendor updaters if the vendor feed reports the app is already up to date.
- **Never terminate user-running applications:** Only quit what the toolkit itself launched, and always perform soft graceful termination (`quit`), never forced `kill`.
  An app that is already open when `update_all.sh` reaches it is in use: it is never quit, relaunched or
  replaced. The handler reports `NEEDS_RESTART` ("quit the app so its updater can install") and moves on.
  `silent_launch_app` records only apps that were **not** running before it opened them
  (`$MAC_UPDATE_SESSION_DIR/toolkit_launched.txt`); `quit_toolkit_launched_apps` quits exactly those after
  the settle window. `vendor_direct_install` refuses to swap a running app, and Docker Desktop is stopped
  only when the toolkit started it.
- **Verified downloads only:** Direct downloads must use `https://`, validate against exact allowlisted hosts (`config/vendor_feeds.txt`), verify checksums (SHA256/SHA512) when published by the vendor, and install via `copy_verified_app` (spctl Gatekeeper check, CFBundleIdentifier and Apple Team ID match, staged atomic swap, and automatic rollback on failure).

## 16. Only Installed Applications & CLI Toolchains (v1.5.0)

- The update pipeline updates **only** what is already installed on the Mac.
- Missing native CLI tools (`claude`, `codex`, `opencode`, `agent`, `agy`) and node toolchains are skipped without error.
- Missing CLIs are installed only when explicitly requested via the `--bootstrap-cli` flag (`MAC_UPDATE_BOOTSTRAP_CLI=1`).

## 17. Orphan Homebrew Casks (v1.5.0)

- Casks whose `.app` bundles have been deleted manually from `/Applications` or `~/Applications` are classified as orphan casks.
- Orphan casks are skipped during `brew upgrade --cask` (protecting against ghost reinstallations) and recorded in `$MAC_UPDATE_SESSION_DIR/brew_orphan_casks.txt`.
- In interactive mode, the user is prompted to clean up the stale Homebrew record via `brew uninstall --cask --force <token>`.
