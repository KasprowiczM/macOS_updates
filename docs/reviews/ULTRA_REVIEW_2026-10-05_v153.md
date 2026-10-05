# v1.5.3 update reliability review and release plan

Review date: 2026-10-05. Base: `e5b39a2` (v1.5.2). This document describes the public implementation scope; private run logs and machine inventory remain outside Git.

## Verified baseline

- Shell and Python syntax checks passed; secret scan passed.
- Full baseline: 496 tests, 495 passed; one failure in the App Store account-version fixture (expected clean, received degraded). Its missing application-directory override scanned the host's actual iPad apps. The fixture now uses a sandbox; the targeted suite passes.
- Existing main CI and secret scan passed. Existing workflow triggers and runner scope remain unchanged; no new schedule or macOS CI run is required.

## Implementation plan

1. Use verified vendor downloads before launching ChatGPT when an installable update is known. Parse Proton release data correctly, respect system requirements and staged rollout information, and preserve honest stale/unknown-feed status.
2. Avoid launching applications whose current version is already proven. Preserve background update fallback when vendor evidence is unavailable. Never close applications already running in the user's session.
3. Make native CLI updates precede npm/toolchain work. Detect duplicate installations and remove redundant copies only after validating the supported replacement. Suppress absent inventory applications, including uninstalled DJI software.
4. Guard every bundle swap against running applications; remove unconditional quit from the common copy helper. Avoid settle delays when no applications were launched.
5. Defer privileged system work softly without a terminal or cached authorization; preserve `softwareupdate -R`. Propagate system warnings into the run summary. Never call bare `mas upgrade` after an unparseable queue.
6. Update v1.5.3 documentation, perform independent review and regression checks, commit scoped files, push and merge to main, then verify remote state and CI.

## Acceptance

- Full `bash run_tests.sh`, warning-level ShellCheck and secret scan pass.
- Behavioral tests cover native-first ownership, vendor-feed parsing, no unnecessary GUI launch, running-app preservation, absent apps, no interactive sudo without a terminal, explicit App Store IDs, and warning propagation.
- Vendor probes compare installed and available versions without installing system updates or causing a reboot.
- All seven READMEs and affected operating instructions describe the implemented behavior and evidence limits.
- Merge and remote main are verified; private inventory and historical untracked reviews are not committed. No release tag is created by this change.

## Evidence limits

Mock tests establish control flow and failure handling. They do not certify a live macOS upgrade, vendor rollout completion, or every third-party updater. A full reboot-capable Update All run is intentionally outside this review's automated validation.

## Findings and disposition

| Priority | Evidence in base revision | Effect and resolution |
|---|---|---|
| P1 | `update_internet_apps.sh:278` common copy unconditionally requested quit, then slept one second | Could close a user's application or replace a still-running bundle. Common copy now checks idle state twice and defers ambiguous/running state. |
| P1 | `update_system.sh:235` sudo preauthorization and subsequent installs used interactive sudo without terminal guards | Unattended system step could prompt/fail as a hard error. Explicit no-sudo policy and unavailable authorization defer softly; install commands use `sudo -n`. |
| P1 | `update_appstore.sh:310` unparseable IDs fell through to bare `mas upgrade` | Root enumeration could differ from the measured queue. Missing IDs now defer, with no upgrade call. |
| P2 | `update_all.sh:1999` soft system result did not set degraded | Final summary could claim clean despite a system warning. Warning now propagates; deliberate cancellation keeps its separate status. |
| P2 | `update_internet_apps.sh:630` no-launch runs still slept for the configured settle time | Settle is retained only for actual toolkit launches. |
| P2 | `tests/test_appstore_mas.py:26` account-version fixture lacked app-directory isolation | Host apps affected the test result. The fixture now uses an empty sandbox directory. |
| P2 | Vendor-truth GUI path staged a launch before direct fallback; Proton's release map was not parsed | Direct-first ChatGPT avoids the former 90-second stage plus 60-second post-quit poll. This 150-second saving is a code-path estimate, not a new live benchmark. Proton feed parsing and rollout handling are covered by regressions. |

## Scope reviewed

| Area | Review evidence and scope |
|---|---|
| Orchestrator and reporting | Child exit handling, blocking/degraded separation, last-step system installation, dry-run and JSON output reviewed; warning propagation repaired. |
| Downloads and bundle integrity | DMG verification, Gatekeeper, bundle identifier/signing-team comparison, staging and rollback reviewed. Running-state guard repaired. Manufacturer checksums remain unavailable in several existing legacy handlers; signature/identity checks remain required. |
| Homebrew | Shared query wrappers, orphan casks, downgrade prevention, sudo-requiring cask gate and post-upgrade queue checks reviewed. Existing regression suite covers these paths. Direct leaf runs requiring privileged cask work should remain interactive. |
| App Store | Explicit-ID upgrade, user-session retry, no-terminal gate, lookup-before-GUI and final queue verification reviewed. Unparseable queue repaired; accessibility limitations remain explicit. |
| System updates | Major-upgrade policy, label classification and restart batching reviewed. `-R` remains mandatory; no live system installation was performed. |
| Inventory and CLI ownership | All-group inventory synchronization, exclusions, absent apps, native/npm prefix ownership and version/process checks reviewed. Targeted live native CLI migration and duplicate cleanup complement mock regressions. |
| Private overlay | `dev_sync_core.py` path boundaries, `overlay_import.py` staged transaction, symlink rejection and rollback reviewed; transaction/import tests run in sandboxes. No private cloud export/import was initiated for this review. |
| Installation and migration | `install.sh` platform checks, pinned-ref checkout and setup dispatch; `migration_setup.sh` existing setup paths reviewed. Fresh isolated macOS install/restore remains pending live acceptance. |
| Localization and documentation | Seven READMEs refreshed; existing localization/status guards validate referenced keys. Current operating docs updated; historical receipts are preserved. |
| CI | Branch/path filters, concurrency cancellation, timeouts and manual/tag-only macOS scope reviewed. No workflow changes or additional schedule; existing Ubuntu release gates verify pushed code. |

## Measured read-only verification

- Final release gate: `bash run_tests.sh` passed **527 tests** in 83.879 seconds; Bash syntax, Python/module/heredoc compilation and secret scan passed. Whole-repository warning-level ShellCheck and `git diff --check` passed. The original baseline was 495/496 before fixture isolation and 31 additional regression cases.
- `scripts/check_vendor_feeds.sh --json` queried 15 installed-app entries: ChatGPT `26.930.51102` equals its vendor offer; Proton Mail `1.15.1` equals its offer; Proton Drive `3.1.0` exceeds the official `3.0.3` feed and correctly reports `feed_stale`.
- `update_all.sh --dry-run -y --json-summary` exited `0`, all seven steps skipped, `degraded=false`, `blocked_system=false`; no update or reboot was requested.
- Shared regression suite: 13 tests passed, including running/unknown-app preservation, a launch during staging, no-terminal sudo, no-sudo policy, malformed App Store IDs and system-warning propagation. Warning-level ShellCheck passed for the shared modified orchestrators.
- Targeted live OpenCode migration verified the supported native `1.18.34` executable and selected PATH alias. Two redundant npm packages were removed; other Node/nvm packages and the desktop application's bundled CLI were retained. Existing Claude/Codex had no redundant npm package to remove. Process and version guards are tested independently.

## Review assessment

Scores are qualitative assessments of the inspected code and evidence, not a percentage of applications guaranteed to update.

| Dimension | Score / 10 | Justification |
|---|---|---|
| Update integrity | 8 | Signed identity and rollback with new running-state guards; several vendor checksums unavailable. |
| Secrets/privacy | 9 | Private inventory excluded; clean secret scan; sanitized public evidence. |
| Automation honesty | 8 | Warnings and deferred work remain explicit; vendor-only failures cannot be repaired locally. |
| Tests and CI | 8 | Broad behavioral/static suite and inexpensive gated CI; fresh isolated macOS install not verified. |
| Documentation currency | 8 | Current instructions synchronized; historical acceptance dates preserved. |
| Recovery readiness | 8 | Bundle/overlay rollback is covered by tests; live restore drill remains pending. |

## Vendor references and remaining work

- [Proton Drive release JSON](https://proton.me/download/drive/macos/version.json) and [appcast](https://proton.me/download/drive/macos/appcast.xml) remain behind the installed release. The toolkit must not invent an endpoint, downgrade or claim a completed update.
- [Proton Mail release JSON](https://proton.me/download/mail/macos/version.json) publishes rollout proportions. [Vendor updater source](https://github.com/ProtonMail/WebClients/blob/main/applications/inbox-desktop/src/update/update.ts) compares a local cohort against the offer; partial rollouts retain the native updater and never authorize direct rollout bypass.
- Context7-assisted review of [Sparkle CLI documentation](https://sparkle-project.org/documentation/sparkle-cli/) confirms quit/relaunch behavior and custom-delegate limits. Adding a separate updater dependency was unnecessary for the verified direct path.
- Future interactive full-run acceptance and isolated fresh installation/private-overlay restore remain explicit work. No universal success claim is made for third-party native updaters.

## Documentation reconciliation

Updated: VERSION, seven READMEs, CHANGELOG, AGENTS/CLAUDE/CODEX/GEMINI, CONTRIBUTING, user guides, operations runbooks and quick-start release headers, architecture, scripts, critical rules, exit codes, security, troubleshooting, acceptance checklist, INSTALL and PUBLIC_RELEASE. Reviewed without behavior changes: dev_sync README/QUICK_START/INDEX and MCP setup instructions. Historical untracked review files are retained locally and excluded from this release.
