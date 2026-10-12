# v1.5.5 run-log follow-up — 2026-10-11

Base revision: v1.5.4 (PR #4). Earlier reviews remain historical evidence. Machine-specific logs, session directories and inventory remain private; this document paraphrases the evidence and records public application versions only.

## Observed live result

The user ran Update All interactively (Polish locale) on a Mac with Homebrew 7.0.9. Steps 0–4 completed. Step 5 (inventory/postupdate) failed, the final macOS step was skipped with the message that a blocking step had failed and "the machine may be mid-transaction", the summary still claimed that `APPLICATIONS.md` and `UPDATES.md` had been updated, and the machine summary could not be written.

Positive live observations from the same run: App Store Track 2 updated UniFi **10.38.1 → 11.0.0** and verified it; OpenCode Desktop **1.18.35 → 1.19.0** installed from the verified vendor feed; Claude Desktop (**2.31226.1**) and Warp (**0.2026.10.07.08.29.00**) updated through their own updaters after the toolkit launched them. The only per-app warning was Proton Drive's manufacturer feed (3.0.3) being older than the installed app (3.1.0).

## Findings, root causes and fixes

### F1 (critical) — stale command hash after a Homebrew upgrade

- *Evidence:* step 3 upgraded `python@3.14` to 3.14.8_2. The unversioned `/opt/homebrew/bin/python3` link disappeared (only versioned links remained) while `/usr/bin/python3` stayed on `PATH`. Step 5 then failed with `/opt/homebrew/bin/python3: No such file or directory`, and the run-summary write failed the same way.
- *Root cause:* the long-lived master process had hashed `python3` to the Homebrew path in step 0. Without `shopt -s checkhash` bash does not re-search `PATH` when a hashed binary vanishes. Child scripts were unaffected because each is a fresh process. Reproduced in isolation: with `checkhash` off a removed hashed binary yields "No such file or directory"; with it on bash falls through to the next `PATH` entry.
- *Fix:* `shopt -s checkhash` immediately after `set -o pipefail` in `update_all.sh`, all five `update_*.sh` orchestrators and `migration_setup.sh`; `update_all.sh` also runs `hash -r` before steps 2–5.

### F2 — a reporting failure deferred security updates

- *Evidence:* step 5 was classified blocking, so the final macOS step was skipped although step 5 mutates nothing.
- *Fix:* step 5 failure still records an error and `OVERALL_EXIT=1` (non-zero exit) but no longer sets `BLOCKING_EXIT`; the blocking matrix and `critical_rules.md` §13 document it. This is the 2026-07-26 regression class (see exit-code guidance).

### F3 — false "files updated" claim

- *Evidence:* the closing "Zaktualizowane pliki: APPLICATIONS.md, UPDATES.md" line was printed after step 5 failed.
- *Fix:* the line (and the inventory-only equivalent) is printed only when step 5 succeeded.

### F4 — stale `started` summary

- *Evidence:* when the final summary write fails, the file written at the start of the run (`run_status: "started"`) remained as the apparent result.
- *Fix:* the write function names its cause (`python3` missing from `PATH`, or its exit status) and, if the final write fails, the stale `started` summary files are relabelled `failed`. No new standalone Python entrypoint was added.

### F5 — toolkit-launched app that does not quit

- *Evidence:* Claude Desktop was launched by the toolkit and updated itself to 2.31226.1 during the run; it was still running when the 60 s wait expired. `internet_app_quit_gracefully` sends a single `quit`. The most likely cause (not directly observed) is that the updater relaunched the app after that quit, so the new instance never received one; a quit arriving while the app is busy installing is the other plausible cause. Re-sending the graceful quit covers both.
- *Fix:* the graceful AppleScript `quit` is re-sent every 10 s inside the wait window (`MAC_UPDATE_QUIT_RESEND`, 1–60) and the window is configurable (`MAC_UPDATE_QUIT_WAIT`, default 60, 0–300). Only toolkit-launched apps are ever passed to this function; nothing is force-killed and a still-running app is left alone and reported as a warning. `L_INTERNET_APP_STILL_RUNNING_FMT` takes the wait as a parameter in all seven languages.

### F6 — misleading soft-warning wording

- *Evidence:* with every app green except one stale manufacturer feed and one app that did not quit, the step printed "At least one internet application was not verified or updated" and the master printed "reported unverified updates (soft)".
- *Fix:* separate flags track warning-only causes (`feed_stale`, quit timeout). The generic line is printed only for a real unverified, behind, restart-pending or error-class cause; otherwise the new `L_INTERNET_WARNINGS_ONLY` line is printed in all seven languages. The exit code stays `10` (soft, never blocking). The four master messages now read "reported warnings (soft)".

## Tests and verification

- New `tests/test_run_log_regressions_20261011.py` (28 tests): checkhash behaviour with a vanishing `python3` (including a negative control reproducing the failure, and extraction of the exact `shopt` line from `update_all.sh`), non-blocking step 5 executed from the real branch text, conditional "files updated" message, summary-failure cause and stale-file relabelling, repeated graceful quit against a stubbed `osascript` (more than one `quit`, returns 0 once the app exits, no `kill`-style commands, clamped settings), warning classification and the internet closing block across feed-stale-only, quit-timeout-only, unverified, real soft failure, clean and hard-failure cases, and i18n key presence in seven languages.
- New static guard `test_orchestrators_enable_checkhash_after_pipefail` in `tests/test_safety_static.py`; `tests/test_vendor_truth_handlers.py` updated for the separate quit-timeout flag.
- Full `bash run_tests.sh`: **561 tests pass** under both the system Python 3.9.6 (what `python3` resolves to once Homebrew's link is gone; about 97 s) and Homebrew Python 3.14 (about 91 s), plus syntax, inline-heredoc compile and clean secret scanning. Warning-level ShellCheck across the shell entry points reports no findings.
- `tests/test_architecture_rosetta.py` used `X | None` annotations without `from __future__ import annotations` and could not be imported by Python 3.9; the import was added so the suite no longer depends on which `python3` is on `PATH`.

## Remaining acceptance work

- The macOS system update/reboot path was **not** exercised in the observed run (it was skipped by F1/F2) and stays unaccepted; a future interactive run must exercise it.
- Not observed live: the Gatekeeper-rejection/rollback branches of the vendor DMG install, a user-open application protected during a real update, and a fresh isolated install with overlay restore.
- A live confirmation that the repeated `quit` closes an updater-relaunched Claude Desktop is pending the next run.

## Documentation reconciliation

Version headers, seven READMEs, user guide headers, agent overlays, architecture, critical rules (new §6e, §13), exit codes, scripts reference (new environment variables), troubleshooting and acceptance notes are synchronized. Historical reviews and earlier changelog entries are unchanged. Actions workflows and runner scope are unchanged.
