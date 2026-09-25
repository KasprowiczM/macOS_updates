# Production Acceptance Checklist — v1.5.x Live Execution Paths

This checklist covers critical update and safety paths that have passed static, unit, and integration tests (`run_tests.sh`), but await live observation in a real `update_all.sh` run on macOS hardware.

When running `update_all.sh`, inspect the execution log in `logs/update_all_<YYYYMMDD_HHMMSS>.log` or session diagnostics in `$MAC_UPDATE_SESSION_DIR` to confirm that each path behaves according to specification.

---

## Acceptance Summary Matrix

| # | Execution Path | Trigger Condition | Log Signal (i18n Key / EN Message) | Expected Valid Outcome | Observed (Date & Log File) |
|---|---|---|---|---|---|
| **1** | **App Store Track 2 (iPad Apps GUI)** | iTunes Lookup API detects an available update for an installed iPad app (UniFi, WiFiman, Picsart, etc.). | `L_APPSTORE_IOS_PENDING_FMT`<br>`"iPad app update available: %s %s → %s"`<br>`L_TOR_2_HEADER`<br>`"⬇️ TRACK 2: App Store GUI Automation (iPad apps)"` | Interactive: App Store GUI opens, clicks update, verifies closure, `ios_apps_pending` clears.<br>Non-interactive: Emits soft warning (`L_APPSTORE_IOS_NEEDS_INTERACTIVE`), writes `appstore_ios_pending.txt`, soft exit 10. | `[ ]` |
| **2** | **macOS System Update (No-Restart + Restart Batch)** | `softwareupdate -l` returns both non-restart updates (Safari, CLT, XProtect) and restart-required system builds. | No-restart: `"Installing: <label>..."`<br>Restart batch: `L_SYSTEM_INSTALLING_RESTART_BATCH_FMT`<br>`"Installing (restart required): %s..."`<br>`L_SYSTEM_RESTARTING`<br>`"Update complete. System will restart automatically..."` | Non-restart labels install individually; restart-required labels install in ONE batch with `-R --verbose`; records each to `system_installed_labels.txt`; system triggers restart cleanly. | `[ ]` |
| **3** | **Major macOS Upgrade Guard (macOS 28+)** | `softwareupdate -l` offers a major OS release (different major version from current host). | `L_SYSTEM_MAJOR_AVAILABLE`<br>`"Major macOS upgrade available: %s (%s) — skipped (requires MAC_UPDATE_ALLOW_MAJOR_UPGRADE=1)"` | Major version upgrade is filtered out (`should_install=0`); only minor/security labels are installed; system does not perform unintended major OS upgrade. | `[ ]` |
| **4** | **Homebrew Orphan Cask Handling** | User manually removed a `.app` bundle from `/Applications`, leaving a stale Homebrew cask record. | `L_BREW_ORPHAN_CASK_FMT`<br>`"Cask %s: the app was removed manually (%s missing) — skipping. Remove the Homebrew record: brew uninstall --cask --force %s"` | Cask is skipped from upgrade targets; recorded in `brew_orphan_casks.txt`; pipeline never redownloads or reinstalls deleted app. | `[ ]` |
| **5** | **Direct Vendor DMG Install & Atomic Rollback** | An internet app with a direct DMG feed (`config/vendor_feeds.txt`) is outdated and closed. | `L_INTERNET_GATEKEEPER_REJECTED`<br>`"Gatekeeper rejected signature: %s"`<br>Post-swap failure:<br>`"Post-install signature check failed for %s"` | DMG is downloaded from verified allowlist, Gatekeeper signature confirmed, staged in `/Applications/.macupd_staging.*`, swapped atomically with backup in `.macupd_backup.*`. On any verification failure, automatic rollback restores backup. | `[ ]` |
| **6** | **Chrome Staged Rollout Status (K1)** | Google VersionHistory API has newer public version, but Google Omaha returns `noupdate` / no response. | `L_INTERNET_STATUS_ROLLOUT_HOLD_FMT`<br>`"ℹ️  Vendor rollout: %s installed, %s public — not offered to this Mac yet"` | Reported as informational hold `rollout_hold` (`⏸` / `ℹ️`) with `INTERNET_LAST_VERIFIED=1`; no misleading unverified updater warnings or pipeline failures. | `[ ]` |
| **7** | **Preserve User Apps & Quit Toolkit-Launched** | An app was closed prior to run; toolkit launched it in background for update trigger. | Launch: Bundle ID recorded in `toolkit_launched.txt`.<br>Quit: `internet_app_quit_gracefully` quits app.<br>Failure to quit:<br>`L_INTERNET_APP_STILL_RUNNING_FMT`<br>`"%s was launched for update and did not exit within 60s"` | User-opened apps are untouched. Apps opened by toolkit are recorded in `toolkit_launched.txt` and closed cleanly at end of Step 4. If an open app is outdated, warns `NEEDS_RESTART` without closing it. | `[ ]` |

---

## Detailed Scenario Guides & Log Verification

### 1. App Store Track 2 (GUI Automation for iPad Apps)

- **Condition:** An iOS/iPad app installed via Mac App Store on Apple Silicon has an update on the App Store (`lib/appstore_ios.sh` finds version difference via iTunes Lookup API).
- **Log lines to look for:**
  ```text
  [INFO] iPad app update available: UniFi 10.19.0 -> 10.20.0
  [STEP] ⬇️ TRACK 2: App Store GUI Automation (iPad apps)
  [STEP] Checking Accessibility permission for terminal...
  [OK]   Accessibility permission confirmed.
  [OK]   iPad apps verified after Track 2
  ```
  In non-interactive runs (`MAC_UPDATE_NONINTERACTIVE=1` or no TTY):
  ```text
  [WARN] iPad app updates need an interactive run (Track 2 uses the App Store window)
  ```
- **Valid Result:**
  - Interactive: Terminal drives App Store via AppleScript, clicks update, closes App Store window, and `ios_apps_pending` verifies zero pending items.
  - Non-interactive: Emits soft warning, records bundle ID to `$MAC_UPDATE_SESSION_DIR/appstore_ios_pending.txt`, exits Step 1 with code 10 (soft fail).
- **Triage on Failure:**
  - If Accessibility is denied (`L_AX_PERMISSION_DENIED`): grant Accessibility permissions to Terminal / iTerm in `System Settings → Privacy & Security → Accessibility`.
  - If AppleScript times out or fails: check `$MAC_UPDATE_SESSION_DIR/appstore_diag.txt`. The user can update iPad apps manually via the Mac App Store app.

---

### 2. macOS System Update: No-Restart Labels + Single Restart Batch

- **Condition:** Apple releases updates with mixed requirements (e.g. Safari / Command Line Tools without restart, macOS system delta with restart).
- **Log lines to look for:**
  ```text
  [STEP] Installing: Safari18.3SequoiaAuto-18.3...
  [STEP] Installing (restart required): macOS Sequoia 15.4-24E248...
  [OK]   Update complete. System will restart automatically...
  ```
  And in session directory:
  ```text
  $ cat "$MAC_UPDATE_SESSION_DIR/system_installed_labels.txt"
  Safari18.3SequoiaAuto-18.3
  macOS Sequoia 15.4-24E248
  ```
- **Valid Result:**
  - Non-restart labels install sequentially via `sudo softwareupdate -i "<label>" -R --verbose`.
  - Restart-required labels are grouped and executed in a single command `sudo softwareupdate -i <labels...> -R --verbose`.
  - All installed labels are recorded in `system_installed_labels.txt`.
- **Triage on Failure:**
  - If installation exits non-zero: check AC power connection (macOS blocks OS updates on battery power) and disk space. Inspect `logs/update_all_*.log`.

---

### 3. Major macOS Upgrade Policy Guard (e.g. macOS 28+)

- **Condition:** `softwareupdate -l` returns an upgrade to a new major version (e.g. host is macOS 15, update is macOS 16 / macOS 28).
- **Log lines to look for:**
  ```text
  [WARN] Major macOS upgrade available: macOS Golden Gate (28.0) — skipped (requires MAC_UPDATE_ALLOW_MAJOR_UPGRADE=1)
  ```
- **Valid Result:**
  - The major release is skipped. Only updates for the current major branch (security patches, Safari) are passed to installation.
  - Exit code remains 0.
- **Triage on Failure:**
  - If a major upgrade was installed without consent: verify `lib/python/system_updates.py` classification logic.
  - If the user *wants* the major upgrade: run interactively with `MAC_UPDATE_ALLOW_MAJOR_UPGRADE=1 bash update_all.sh`.

---

### 4. Homebrew Orphan Cask Handling

- **Condition:** An application installed via Homebrew cask was deleted directly from `/Applications` by the user, leaving the cask recorded in Homebrew's metadata.
- **Log lines to look for:**
  ```text
  [INFO] Cask vlc: the app was removed manually (/Applications/VLC.app missing) — skipping. Remove the Homebrew record: brew uninstall --cask --force vlc
  ```
  Session artifact:
  ```text
  $ cat "$MAC_UPDATE_SESSION_DIR/brew_orphan_casks.txt"
  vlc
  ```
- **Valid Result:**
  - The orphan cask is excluded from `brew_cask_targets.txt`. Homebrew does not redownload or reinstall the removed app.
  - In interactive mode, prompts whether to remove the stale Homebrew record (`L_BREW_ORPHAN_CASK_PROMPT_FMT`).
- **Triage on Failure:**
  - If prompt was skipped or declined: manually run `brew uninstall --cask --force <cask>`.

---

### 5. Direct Vendor DMG Install & Atomic Rollback via `copy_verified_app`

- **Condition:** An internet app with a direct DMG download feed (e.g. KeePassXC, LibreOffice) is outdated and closed on the local Mac.
- **Log lines to look for:**
  - Normal successful upgrade:
    ```text
    [STEP] Updating KeePassXC via direct vendor download...
    [OK]   Updated KeePassXC to 2.7.10
    ```
  - Gatekeeper rejection during pre-swap check:
    ```text
    [WARN] Gatekeeper rejected signature: KeePassXC.app
    ```
  - Post-swap signature failure triggering rollback:
    ```text
    [WARN] Post-install signature check failed for KeePassXC.app
    ```
- **Valid Result:**
  - The app is downloaded from an allowlisted HTTPS host, verified with Gatekeeper (`spctl --assess --type execute`), and checked for CFBundleIdentifier and Apple Team ID parity against the existing bundle.
  - If post-swap verification fails, `copy_verified_app` automatically restores the existing bundle from `/Applications/.macupd_backup.*`.
- **Triage on Failure:**
  - If rollback is triggered: verify certificate validity with `codesign -dv --verbose=4 /Applications/<App>.app`.
  - If catastrophic failure leaves backup in place: log will display:
    `CRITICAL: Install failed for <app> and automatic rollback failed! Retained backup is at <backup>. Restore with: mv "<backup>" "<dest>"`

---

### 6. Chrome Staged Rollout Status (K1)

- **Condition:** Google VersionHistory API indicates a newer Chrome release is live, but Google Omaha updater on this Mac returns `noupdate` or no response due to staged rollout cohorts.
- **Log lines to look for:**
  ```text
  [INFO] ℹ️  Vendor rollout: 153.0.8010.53 installed, 154.0.8037.58 public — not offered to this Mac yet
  ```
  Session status:
  ```text
  $ grep "com.google.chrome" "$MAC_UPDATE_SESSION_DIR/internet_status_codes.txt"
  com.google.chrome|rollout_hold
  ```
- **Valid Result:**
  - The updater reports status `rollout_hold` with an informational mark (`⏸` / `ℹ️`).
  - `INTERNET_LAST_VERIFIED=1` prevents treating the application as failing or unverified.
- **Triage on Failure:**
  - If reported as `UNVERIFIED` (⏳): check internet connection to `https://versionhistory.googleapis.com` or review `$MAC_UPDATE_SESSION_DIR/chromium_updater_log.txt`.

---

### 7. User App Preservation & Quitting Toolkit-Launched Apps

- **Condition:**
  - Case A: App was NOT running before update. Toolkit launches it via `silent_launch_app` to trigger auto-update.
  - Case B: App was ALREADY running by user before update.
- **Log lines to look for:**
  - Case A (Toolkit launched):
    App bundle ID is logged to `$MAC_UPDATE_SESSION_DIR/toolkit_launched.txt`.
    At end of Step 4, `quit_toolkit_launched_apps` quits it via AppleScript.
    If app fails to exit within 60s:
    ```text
    [WARN] com.example.app was launched for update and did not exit within 60s
    ```
  - Case B (User already had app open):
    App is NOT logged to `toolkit_launched.txt`. It remains open.
    If an update requires application restart:
    ```text
    [WARN] ⚠️  Update 1.2.0 → 1.3.0 pending — quit the app so its updater can install it
    ```
- **Valid Result:**
  - The user's open applications are never terminated by the toolkit. Only apps launched by the toolkit are gracefully closed.
- **Triage on Failure:**
  - If a toolkit-launched app remains running: inspect running processes (`pgrep -fl <App>`) and verify `toolkit_launched.txt` entries.
