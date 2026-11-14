# Recipe verification implementation, 2026-11-14

Owner approved T1-T5 and T5b from the [plan](../superpowers/plans/2026-11-14-recipe-verification-and-native-updaters.md). T6 live acceptance and T7 activation remain separate. DeepSeek RC is deferred until stable. No real updates, installs or application launches are part of this implementation.

## T1, source 1.7.1

The latest public-checkout run lasted 103 seconds and reported no mutations. Its 219 partial-scan items were inventory uncertainty, not failed updates. Later read-only inspection found empty cask metadata and incomplete CLI metadata; exact at-run bytes were not archived. The implementation retains these safety blocks, records source-level diagnostics and groups terminal scan advisories without dropping JSON details. A normal npm hidden lockfile no longer counts as a broken package.

Duration formatting no longer reuses the last step's seconds. Additive summary v4 fields record toolkit provenance, observation types and per-phase monotonic receipts. These distinguish historical updater claims, requested lifecycle actions and fresh observations. A timer ending never proves an update succeeded.

Focused guarded tests passed: receipts9, summary23, providers19, collector23. Bash syntax and module compilation passed. Full integrated gate will be recorded after the remaining stages.
