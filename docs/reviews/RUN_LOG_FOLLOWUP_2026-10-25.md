# Run-log follow-up — 2026-10-25 (unreleased, version stays 1.5.5)

Base revision: `main` at `efeeebd` (v1.5.5 plus documentation commits). Earlier reviews remain historical evidence. Machine-specific logs, session directories and inventory remain private; this document paraphrases the evidence and records public application versions only. The version number is unchanged because `macOS_updates` and Ascendo release in lockstep (see `CONTRIBUTING.md`).

## Observed live result

The user ran Update All interactively (Polish locale, macOS 27.0.1, Homebrew 7.0.10) in 9 min 56 s. The run exited `0` with `exit_class: warnings`. Steps 0–3, 5 and 6 were OK and step 4 (internet apps) reported a soft warning. Observed changes: 8 Homebrew formulae, Claude Code CLI 2.1.309 → 2.1.310, agy CLI 1.4.6 → 1.4.7 and KeePassXC 2.7.12 → 2.8.0 (verified vendor DMG). macOS offered no update, so the system/reboot path was again not exercised.

## Findings, root causes and fixes

### R1 (high) — App Store Track 2 reported "nothing pending" while an iPad update was pending

- *Evidence:* the iTunes lookup reported UniFi 11.0.1 → 11.0.2. The Track 2 AppleScript returned `NO_UPDATES_FOUND`, the step printed "App Store shows no pending updates" and the closing summary said Track 2 had no pending iPad updates, with exit `0`. UniFi was still 11.0.1 after the run. Across the private run logs, Track 2 took the `no_updates` branch while the lookup reported a pending iPad update on 2026-10-05, 10-06, 10-18 (twice), 10-21, 10-23 and 10-25. The bulk button was found only on 10-08 and 10-11.
- *Root cause:* the `no_updates` branch never compared the GUI result with the lookup's pending list, so the run reported success. The GUI miss itself has three plausible causes; none was isolated, because this agent session has no Accessibility permission:
  - a fixed 6 s wait after opening the Updates page;
  - matching only the `name` attribute, whereas SwiftUI buttons often expose their label as `description`/`title`;
  - matching only the English bulk label.
- *Fix:*
  - The AppleScript polls the Updates page for up to ~30 s, reads `name`, `description` and `title`, and matches localized bulk and per-app labels.
  - If nothing is found it sends one refresh (Cmd+R) and polls again for up to ~20 s.
  - As a fallback it opens each pending app's product page and presses its Update button. The ids come from `ios_pending_ids`, are digits only and are passed as `osascript` arguments, never interpolated into the script.
  - It keeps its own deadline below `MAC_UPDATE_APPSTORE_GUI_TIMEOUT`.
  - If the store still offers nothing while the lookup reports an update, the new `not_offered` branch prints a per-app soft warning (exit `10`, never blocking), writes `appstore_ios_pending.txt` and counts the app in `pending_after_run_appstore`.
  - A Track-2-only run asks a Track-2-specific question instead of "run both updates?".
  - An undefined `mac_update_severity_register` call on the GUI-timeout path was removed; `SOFT_FAIL` already records the failure.

### R2 (high) — Proton Drive's permanent "stale feed" warning

- *Evidence:* Proton Drive 3.1.0 (build 12778.3) was installed while `version.json` listed only stable 3.0.3. The internet step therefore stayed non-OK for 10 consecutive runs since 2026-10-12. The app's own Sparkle feed (`SUFeedURL`, `appcast.xml`) publishes 3.1.0 in the `gradual-rollout` channel and 3.0.3 in `stable`.
- *Root cause:* the toolkit compared against the stable JSON feed only, so a build the vendor rolled out gradually through the app's own updater looked "newer than the vendor".
- *Fix:*
  - When the primary feed is older than the installed app, `internet_handler_vendor_truth` checks the appcast listed in the new `config/vendor_appcasts.txt`.
  - That URL is an explicit config value, not read from the plist. It must be https and its host must equal the app's allowed host in `vendor_feeds.txt`.
  - If the installed short version or build is published there in any channel, the app is reported current with the channel named.
  - This only proves "current". A gradual-rollout item is never used as an install target (critical rules §16).
  - `scripts/check_vendor_feeds.sh` shows the relation `rollout_ok`.

### R3 (medium) — misleading final banner

- *Evidence:* the final banner said some updates could not be verified, although nothing was unverified or pending; the only cause was a manufacturer feed warning.
- *Fix:* `degraded_is_warnings_only` (`lib/python/run_summary.py`) is deliberately conservative. Any unknown or actionable state keeps the generic wording. When it returns true, `update_all.sh` prints `L_ALL_WARNINGS_ONLY`.

### R4 (medium) — untranslated and tautological strings

- *Evidence:* a Polish run printed English or mixed lines:
  - the "Checking mas tool" header and the Track 1 "sudo mas upgrade skipped" suffix;
  - "reported warnings (soft)";
  - "OK completed" and the tautological "Ostrzeżenie zakończono z ostrzeżeniami" ("warning — completed with warnings");
  - the final summary labels, "Run summary" and "Chronic warning streaks";
  - the App Store banners.
- *Fix:* all of these use i18n keys in the seven languages. Comparisons use `STATUS_CODE_*` instead of display text. Legacy texts in old run summaries still classify.

### R5 (low) — a profile backup on every run

- *Evidence:* every run created `~/.zshrc` and `~/.npmrc` backups. Rotation kept them bounded.
- *Root cause:*
  - The `.npmrc` prefix removal ran unconditionally.
  - The profile block is normalised by removing every known variant and re-appending the canonical lines in place. That rewrites the file even when the result is identical.
- *Fix:*
  - The `.npmrc` removal returns early when no `prefix`/`globalconfig` line exists.
  - The profile edits are applied to a staging copy (`sync_profile_block`). The real profile is backed up and replaced only when the result differs. Repeated runs on an already-correct profile create no backup.

## Tests and verification

- New `tests/test_run_log_regressions_20261025.py` covers:
  - appcast parsing and the host allowlist;
  - the shell cross-check with a stubbed `curl`;
  - the warnings-only banner and step-text classification, including legacy texts;
  - the `not_offered` branch and the AppleScript (`osacompile`);
  - id validation and i18n parity;
  - backups only on change, including an idempotency test for the remove-and-re-append profile flow.
- Four assertions in older regression tests now check i18n keys instead of hardcoded strings.
- Full `bash run_tests.sh` passes, and warning-level ShellCheck on the changed shell files is clean.
- A read-only `scripts/check_vendor_feeds.sh` shows Proton Drive as `rollout_ok`.
- The pre-existing intermittent failure of `test_system_step.SystemStepBehavioralTests.test_batch_restart_labels_two_invocations_restart_last` (`softwareupdate -l` mock exiting 139) also occurs on the unchanged baseline (1 in 10 runs) and is not caused by these changes.

## Remaining acceptance work

- The new Track 2 AppleScript was compiled but not run against the real App Store; this session has no Accessibility permission. The next interactive run shows one of two outcomes. Either the polling or product-page fallback installs the pending iPad update, or the run reports `not_offered` honestly.
- The macOS system update/reboot path is still unaccepted.
