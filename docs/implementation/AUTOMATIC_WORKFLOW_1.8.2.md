# Automatic workflow verification, 1.8.2

Date: 2026-11-14. Status: integration verified; publication pending.

## Reported failures and evidence

The latest reviewed real run finished in 96 seconds with warnings and zero observed package changes. It reported 248 targets with partial inventory evidence, 93 manual targets and 23 deferred targets. This was not evidence of successful updates.

Three independent problems explained the experience:

1. The mixed queue emitted its live progress only to the terminal workspace protocol. Text-mode users saw almost no activity before the final summary.
2. The contextual sidebar was hidden below 120 columns. Supported smaller windows therefore lost instructions and status.
3. An unrelated incomplete Homebrew prefix could invalidate fresh checks for native applications. Declined or missing consent also prevented launches; the logs do not show a native launch failure.

## Intended release behavior

Setup separates optional author-catalog acquisition from installed-app maintenance. No catalog product is preselected. A saved, explicitly confirmed agreement covers supported updates from existing sources. Per-target exclusions and actual source conflicts continue to block changes. Additional installations and source migrations are separate decisions.

The text interface reports group activity, bounded per-target outcomes and waiting status. The windowed interface keeps instructions visible in a right sidebar. Vendor observation remains indeterminate until there is evidence; launching a window never counts as a verified latest-stable update. DeepSeek Harness remains manual. Unsupported mechanisms remain identified as unavailable.

After a run, the summary gives outcome-specific next steps: inventory repair, saved preferences, running applications, source conflicts, native recovery and optional source comparison. It never treats a recommendation as installation consent.

## Verification record

- The preceding local 1.8.1 checkpoint passed 1,566 guarded Python tests and the complete shell, compilation and secret-scan gates.
- A real read-only CLI dry-run completed successfully on the host during 1.8.2 diagnosis. It displayed 364 local targets and 29 eligible Internet applications. This was a preview, not an execution test.
- The final guarded 1.8.2 gate passed 1,624 Python tests with no skips in 326.261 seconds. Shell syntax, Python compilation and secret checks passed; no host-tool or network guard hits occurred.
- The read-only host preview after integration returned 364 planned targets: 269 needing consent, 65 with no blocking reason and 30 manual or unsupported. No targets were blocked by partial scans. This did not execute updates.
- Focused Python 3.9 checks passed 55 terminal tests and five package-observation tests. Landing lint and prerender passed.

## Limits

Fixture tests validate orchestration, consent and reporting. They do not certify every vendor's real updater, App Store offering, download, restart or installation. Stable-release comparisons depend on available evidence and can remain unknown. Native updater channels follow the installed application's settings. Source migration is never inferred from a recommendation. The KeePassXC manager-delegation review evidence has a seven-day validity period; a live cask query does not renew it, and expired evidence returns the catalog entry to manual metadata-only handling.
