# Stage A implementation record for 1.6.1

Date: 2026-11-13. Prepared locally from public source commit `10dc0e4` on `codex/v1.6.1-new-user-safety`. Version 1.6.1 is a source change, not a published release or tag. The landing repository was not edited.

Scope: [approved plan](../superpowers/plans/2026-11-13-source-aware-inventory.md), T01-T03, plus the research part of T12. The [original audit](NEW_USER_AUDIT_2026-11-13.md) describes the earlier baseline and remains historical evidence.

## Implemented behavior

- Internet dispatch checks local presence before entering app handlers. Stale checks and status aggregation ignore absent targets. The Microsoft AutoUpdate location remains supported.
- Cask catalog entries check local presence and App Store receipts even when their handler is not dispatched. MAS CapCut without a cask stays App Store managed. A manual copy produces `source_unmanaged`; a failed Homebrew query produces `source_unavailable`. Neither causes installation or adoption.
- Coverage normally lists local installations, with a catalog count. `--show-supported` explicitly lists absent supported recipes. Catalog method alone no longer proves Homebrew ownership. Empty installed-name sets no longer populate the inventory legend with the whole catalog.
- Default setup and `--inspect` check readiness without installing tools, writing profiles/PAM, opening applications or rewriting documentation. Python must run and be at least 3.9; mas must be at least 4.1. Apple developer-tool shims require provisioned tools before invocation.
- `--install-dependencies` previews optional mas/Python actions and asks separately. `--configure-shell` separately previews a bash/zsh profile change. No terminal means no mutation. Declining one dependency does not prevent independent choices.
- The installer reports incomplete readiness with exit 10. It skips inventory and coverage when Python is unavailable. The App Store updater reports unavailable mas with exit 10 and never installs or upgrades the dependency.
- Touch ID remains a standalone, explicit action. It rejects foreign files, symbolic links and nonregular paths. Consent binds the operation to the previewed state; the privileged helper rechecks it, makes a mandatory unique backup and creates new PAM content exclusively. Shell profile writes reject changed targets and use a descriptor that cannot follow symlinks.
- Tests run through the same guarded runner on Ubuntu and macOS. Network/native-tool denials fail the gate even when a test swallows an exit status. Fixture mocks are installed after library sourcing, use temporary paths and identify originating tests in guard diagnostics.

## Decisions and deviations

1. Reused the clean public checkout after verifying the parallel privacy migration. No private history was merged and no landing files were changed.
2. Homebrew itself remains a manual acquisition from its official site. This avoids executing a downloaded bootstrap script inside setup and makes the remaining prerequisite explicit. mas/Python installation stays available after Homebrew is present.
3. Automatic PAM modification is limited to macOS 14+ `sudo_local`. The shared macOS 13 sudo file needs manual administration. This deliberately trades convenience for preserving administrator configuration.
4. Optional profile/PAM mutations now require Python 3.9+ for regular-file validation, preview fingerprints, exclusive creation and backups. Missing Python cannot silently weaken these checks.
5. Stage A changes are retained as one local integration change after the final gate, instead of per-task commits while shared integration work was still running. There is no push, PR, merge, tag or release.
6. The old real-curl capability test was removed from the unit suite. Mocked request-contract tests still verify required flags; unit tests no longer depend on the installed curl build.

## Verification

Final verification results are recorded below. Earlier failed runs were used to correct source-order fixture leaks, previously unmocked native tools, a heredoc marker and old static expectations. They are not release evidence.

- Regression tests first demonstrated catalog dispatch/legend/cask failures, automatic installer/mas behavior, missing tool-shim guards and unsafe or changed setup file targets.
- Mocked `update_all.sh` scenarios cover an empty Mac, MAS CapCut, manual CapCut and unavailable Homebrew. They execute the real internet stage in a disposable repository with other update stages explicitly skipped and preflight mocked. No install/adopt calls are allowed.
- Setup fixtures cover no TTY, read-only HOME, missing/old/unrunnable tools, refusal and per-dependency consent, repeat runs, bash/zsh profiles, symlinks/FIFOs, prompt-time changes, privilege/backup failure and exclusive PAM creation. Positive PAM file operations run only on temporary fixture files without sudo.
- There was no live app update, package installation, updater launch, host profile/PAM write, restart, Linux CI execution or new-user physical-Mac acceptance run.

- Full runner: shell syntax, Python modules/inline blocks and 900 unittest cases completed; 899 passed and one skipped in 268.731 seconds. No unmocked native-tool or network guard hits were reported.
- The skip is the existing private-inventory overlap check (`APPLICATIONS.md` absent in the public checkout). No host inventory was generated to satisfy it.
- The final runner initially failed only its tracked-ignored-file rule: the historical audit had been staged under the private `docs/reviews/` directory. Its public-safe copy was moved unchanged to `docs/implementation/`; ignore rules were preserved. The entire secret/privacy phase was then rerun separately.
- Python 3.9.6 compatibility: 65 targeted setup, file-safety, reporting, inventory and developer-tool-shim cases passed. The full 900-case suite was not rerun under Python 3.9.
- Warning-level ShellCheck passed for all tracked shell scripts. Staged-secret scanning passed (413.71 KB checked, no leaks); the complete repository secret/privacy phase passed after the documentation move (206 existing commits checked, no leaks or tracked ignored files).

Verification status: all required local checks passed. The final full invocation passed phases 1-3; phase 4 passed on its separate rerun after the documentation-only relocation. No product or test code changed between these checks.

## Research and remaining work

[SOURCE_RESEARCH.md](../catalog/SOURCE_RESEARCH.md) covers all 47 registry rows, with 146 dated public observations, 138 successful HTTP responses and 8 bounded errors. It distinguishes versions listed publicly from releases actually offered to a specific Mac. The parent independently re-read the Cursor stable endpoint and Homebrew metadata and confirmed the recorded vendor-ahead observation. A single observation does not prove a historically fastest channel.

This version does not enable the source advisor, stable-channel policy engine, app installation menu or automatic discovery of trusted updater adapters. The combined ChatGPT/Codex identity, full MAS-plus-stale-brew conflicts, duplicate installations, successful-empty versus failed inventory source reconciliation, consent migration and revalidation of every mutation target remain stages B-E. Existing nightly/developer catalog feeds are identified in research; their runtime stable-policy migration is not part of stage A.

The test guards are layered regression safeguards, not an operating-system sandbox. Deliberate dynamic absolute-path execution, isolated Python startup or environment-stripping exec paths require disposable-system testing. Tests do not certify live installation success, supported minimum macOS behavior or all privileged administrator races. The PAM directory is administrator-owned; checks cannot constrain another process with root authority.

## CI budget

No trigger, schedule or runner platform was added. Ubuntu uses the guarded unit runner. Its timeout is 10 minutes to allow diagnostics near the former 5-minute boundary; macOS remains manual/tag-only. A conservative planning envelope of 6 Ubuntu minutes per qualifying event including ShellCheck yields 360 minutes for 60 events/month. Actual Ubuntu runtime and the delta from the previous runner remain unmeasured until separately authorized publication triggers CI.

## Orchestration

Four agents completed seven assignments: two GPT-6.1 Terra agents implemented test isolation and setup changes; two GPT-6.1 Sol agents researched sources and independently reviewed security-sensitive changes. The coordinator inspected diffs, reproduced regressions, addressed review findings, ran the final verification and independently checked a source-version observation. One security review was performed for this stage. Procedures applied: orkiestra, test-driven-development and verification-before-completion; the approved ultra-review and implementation plan supplied the scope.
