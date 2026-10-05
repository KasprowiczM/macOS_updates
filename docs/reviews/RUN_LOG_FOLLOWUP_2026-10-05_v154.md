# v1.5.4 run-log follow-up — 2026-10-05

Base production revision: `a504f9d` (v1.5.3, PR #3). The earlier [v1.5.3 review](ULTRA_REVIEW_2026-10-05_v153.md) remains historical evidence. Machine-specific logs and inventory remain private.

## Observed live result

The user completed Update All at 13:39–13:41 Europe/Warsaw. Its machine summary reports **108 seconds**, exit `0`, `degraded=true`, no blocking failure. App Store, native CLI, Homebrew, inventory and system steps completed cleanly. Internet counts: **25 verified**, **0 behind**, **0 unverified**; no observed package or application updates. macOS **27.0.1** had no offered update. No GUI launch was recorded. Proton Drive's installed **3.1.0** versus official-feed **3.0.3** was the sole warning.

The earlier run took 363 seconds with a different workload. These observations confirm removal of unnecessary launch cycles when software is current; they do not establish an installation-speed benchmark or certify every native updater.

## Evidence and scoped fix

- `lib/python/run_summary.py` treated `feed_stale` as pending, with installed version in `old_version` and older feed in `new_version`. This suggested a downgrade target despite no installation being requested.
- The same warning generated an extra generic unconfirmed Internet item, displayed under a title claiming an updater was launched, even though the run recorded zero unverified updaters.
- v1.5.4 represents manufacturer data as `status="warning"`, with separate optional `installed_version` and `vendor_version` fields and null old/new installation versions. Summary format remains **4**; the item status vocabulary gains `warning`. Existing update counters still use `status="updated"`.
- Recognized per-app warnings suppress duplicate generic **warning** steps. Hard errors, unconfirmed steps and unknown/malformed app statuses retain generic diagnostics. Degraded flags and exit codes remain unchanged.
- Seven languages use separate manufacturer-warning and neutral unconfirmed-operation sections. Stale data does not assert that no newer release exists.
- Proton Mail's informational label now identifies its native updater generically; its update path is unchanged.

## Acceptance and verification

- Behavioral regressions cover stale-only, mixed actual-unverified, hard-error/unconfirmed steps, unknown/malformed status input, unparseable version evidence and all seven summary languages.
- Independent agents replayed warning/mixed/unknown/error cases and confirmed backward compatibility for existing update consumers and v4 migration.
- Targeted summary/status tests: **33 passed**. Full `bash run_tests.sh`: **532 passed** in 84.124 seconds, including syntax/static checks and clean history secret scanning. Warning-level ShellCheck across all shell entry points completed with no findings.
- Read-only replay of the completed run's original status input produced a separate manufacturer warning with installed **3.1.0**, vendor **3.0.3**, null update target, and no pending or unconfirmed update. Original logs and summaries were not overwritten.
- Publication gates are staged secret scanning, scoped commit/push/merge and green remote-main CI; the source review does not manufacture a future merge revision.
- No new full Update All run, OS installation/reboot, GUI updater launch or private-overlay import is initiated by this follow-up.

## Documentation reconciliation

Current release headers, seven READMEs, user guides/runbooks, agent instruction overlays, architecture, exit-code guidance, troubleshooting and acceptance notes are synchronized. Historical reviews are preserved. Actions workflows and runner scope are unchanged.
