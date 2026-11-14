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

## T5b, source 1.7.6

Complete two-slot durable scheduling, per-action receipts, cancellation and shared recovery barriers; protect standalone and final system updates with an authenticated exclusive lease.

The queue admits at most two independent actions globally across cooperating checkouts using the same OS-user state directory. The production runtime keeps `parallel_safe=False` until product effect contracts pass live acceptance. Tests prove overlap only for disjoint resources, deterministic results, cancellation without killing an active worker, and durable slots across observer failure. System updates remain the last, exclusive mutation. The standalone system script uses the same authenticated supervisor and lease.

## Recovery and operational limits

An unresolved helper is not an expired lock. Do not delete scheduler or session journals to make a later run proceed. A timeout, crash or CLI exit without completion proof preserves the resource claim. Direct and first-install recovery reobserve retained bundles and installation ownership before reconciling their own claims; neither path installs a missing catalog application.

Native recovery uses `recover_native_sessions` for local inspection and `reconcile_native_session` with fresh trusted driver observations. System recovery uses `pending_system_sessions` and `reconcile_system_session` from `system_update_guard.py`. These are code APIs, not user-facing reset commands. A system reconciliation requires a successful fresh update listing with every selected label absent and verified target OS. A restart case additionally requires a known boot identity different from the recorded identity. Time elapsed, PID disappearance or CLI exit zero alone is insufficient. Automatic startup reconciliation is not implemented in this checkpoint. A pending system restart or failed/unconfirmed system operation therefore blocks subsequent mutations until reviewed completion proof is supplied; read-only plans remain available.

For a synchronous non-restart system operation, the supervisor releases its lease only after the child returns successfully and a fresh valid listing proves the selected labels are absent. It never kills a running system installer to meet a deadline. The test runner now also blocks unmocked `sysctl` reads so boot-identity tests cannot silently inspect the host.

## Activation boundary and next work

There are zero public schema-v2 executable recipes and zero production native drivers. T5 records real source/parser contracts and manual blockers for 48 products; it does not certify 48 signed payloads or native protocols. Before T6, each pilot needs its real immutable artifact, signed identity, source, channel, architecture, minimum OS, version/build and full effect scope. Native pilots additionally need a documented trigger, readiness/completion observations, helper lifetime and user-engagement protection. Separate live update, first-install and lifecycle evidence must then be collected on a disposable Mac under the separately approved T6 scope. Only T7 activates accepted recipes. DeepSeek Harness remains excluded until stable.

The latest run's empty local cask metadata was not repaired on the host. Missing or malformed metadata remains a blocked target/source, now accompanied by grouped diagnostics. This change does not claim that the previous run updated applications or that existing host inventory is healthy.

## Final local gate

On 2026-11-14, `bash run_tests.sh` passed all 1329 unittest cases in 228.299 seconds on Python 3.15.2, with zero host-command or network guard hits. Bash syntax, Python modules, inline Python and secret scan passed. The warning-level ShellCheck gate passed for all project shell scripts, and Ruff F checks passed for production Python and the new focused test surface. Selected critical modules passed 132 guarded test cases on Python 3.9.6, including the product source contracts.

The first full run exposed two static-gate failures: seven new modules were missing from the script index, and five test data lines used real application-root literals. The script index and fixture paths were corrected without weakening those gates; the final full run above passed.

Local source version is 1.7.6. T1-T5b checkpoints are recorded in the changelog; no tag, push, merge or release was created for this implementation. Public main was observed unchanged at `cb56dda5ce9b13a01f9ca0b8305d713bd4a602b0`. Landing files and workflow schedules were not changed. No real update, installation, application launch or quit was performed on the host.
