# Recipe verification implementation, 2026-11-14

Owner approved T1-T5 and T5b from the [plan](../superpowers/plans/2026-11-14-recipe-verification-and-native-updaters.md). T6 live acceptance and T7 activation remain separate. DeepSeek RC is deferred until stable. No real updates, installs or application launches are part of this implementation.

## T1, source 1.7.1

The latest public-checkout run lasted 103 seconds and reported no mutations. Its 219 partial-scan items were inventory uncertainty, not failed updates. Later read-only inspection found empty cask metadata and incomplete CLI metadata; exact at-run bytes were not archived. The implementation retains these safety blocks, records source-level diagnostics and groups terminal scan advisories without dropping JSON details. A normal npm hidden lockfile no longer counts as a broken package.

Duration formatting no longer reuses the last step's seconds. Additive summary v4 fields record toolkit provenance, observation types and per-phase monotonic receipts. These distinguish historical updater claims, requested lifecycle actions and fresh observations. A timer ending never proves an update succeeded.

Focused guarded tests passed: receipts9, summary23, providers19, collector23. Bash syntax and module compilation passed. Full integrated gate will be recorded after the remaining stages.

## T2, source 1.7.2

Add strict schema v2 and exact release, identity, source, requirements and evidence bindings. Update, first-install and lifecycle acceptance are separate; the public executable recipe catalog remains empty. Thirty-seven focused guarded evidence tests passed.

## T3, source 1.7.3

Add exact-candidate ZIP acquisition and separate consent-bound update and first-install execution, with shared resource admission foundations.

## T4, source 1.7.4

Add observable native sessions, separate accepted lifecycle effects and consent, owned-process checks, durable helper barriers and recovery regression coverage.

The T3/T4 integration shares the scheduler admission layer so direct, manager, installation and native writers use the same state directory across cooperating checkouts of one OS user. This is not coordination with unrelated third-party updaters or other OS users. The concrete direct and first-install executor accepts a bounded ZIP containing one signed bundle; DMG, PKG, bootstrap and unknown effects remain manual. Lifecycle consent never follows ordinary update consent. Restart has its own accepted lifecycle effect and explicit permission. Production native drivers and the public schema-v2 recipe list remain empty.

An independent review found and closed retry-timeout lease release, prejournal phantom recovery, original-lease recovery and external-install adoption gaps. Five dedicated regressions exercise these cases. Install recovery checks the committed bundle inode as well as signature, version and build; it cannot adopt an independently created matching app.

## T5, source 1.7.5

Add 48 product dossiers, real source/parser contracts and synthetic safety scenarios; preserve unknown identity and unaccepted native/payload behavior as manual.

T5 includes 48 manifest-bound product contracts, 50 captured source metadata parser cases, 33 unreviewed parser denials, five App Store projection denials and 12 historical product parser fixtures. Shared synthetic scenarios cover absence, versions, source conflicts, permissions and incomplete evidence. Exact signed production payloads and native trigger/readiness/helper contracts remain product-specific gates before T6; metadata or passing synthetic tests cannot close them. DeepSeek is exclusion-only.
