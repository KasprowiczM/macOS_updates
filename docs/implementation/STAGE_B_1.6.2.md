# Stage B implementation record for 1.6.2

Date: 2026-11-13. Local changes on `codex/v1.6.1-new-user-safety`, based on stage A commit `5daf24d`. Source version 1.6.2 is not a release or tag. No landing files were edited.

## Scope and activation boundary

The [approved plan](../superpowers/plans/2026-11-13-source-aware-inventory.md) assigns T04-T05 to stage B. The previous handoff incorrectly included T06-T07; the plan's stage table governs. Stage C remains T06-T09.

`bash build_inventory.sh --shadow` observes local installations and saves a private schema-1 snapshot. It does not invoke `update_all.sh`, rewrite Markdown, change update routing, launch apps or fetch vendor feeds. `--dry-run` prevents state writes; `--json` returns source diagnostics and resolutions; repeated `--root PATH` replaces the default scan roots. The normal inventory/update commands retain stage A behavior until a coordinated stage C activation.

The owner requested a patch increment after each stage and version 1.7.0 after completion of the whole plan. Stage B therefore changes 1.6.1 to 1.6.2. No publication is authorized by this version change.

## Delivered behavior

- Separate app instances and package targets, with local UUIDs, paths/prefixes, identity evidence, observation time, presence and freshness. Names never merge ChatGPT/Codex, beta editions or duplicate installations in the new model.
- Explicit source results distinguish complete empty scans from unavailable tools, failures and partial coverage. A failed or truncated scan does not establish absence. Manager observations cannot erase independent filesystem receipts. Stale contradictory ownership survives until the relevant source completely disproves it.
- Static app metadata collection stops at bundles, limits organizational depth, directory entries, records and metadata size, and preserves unusual names. Directory symlinks are conservatively skipped and coverage becomes partial; canonical copies are not marked absent because an alias was visited first. No name-based Agent exclusion is used.
- Homebrew collection reads installed JSON metadata and Cellar receipts without invoking brew or Ruby. Actual cask staging symlinks identify artifact destinations, including renamed bundles and custom application directories. Unsupported or missing metadata remains partial. npm scopes and manifests are read without running package scripts. Unmanaged Node executables are inventory-only observations, never version probes.
- The optional known `mas list --json` query has a ten-second timeout and supports array/NDJSON responses. Missing/failed mas is not an empty successful source. Store IDs attach only by exact path or a unique bundle identity, never by display name.
- The resolver handles App Store, Homebrew, npm, protected Apple roots, enterprise signals, unknown sources and conflicts. Framework markers indicate capability only. Team mismatches, incomplete evidence and TestFlight restrict capability. Related cask bundles are linked by observed paths; a bundle conflict also blocks the package's capability classification, preventing an alternative target from appearing eligible.
- The JSON recipe loader rejects unknown fields, commands, duplicate keys, unsupported adapters and oversized catalogs. All 47 legacy TXT entries remain capability-only. No current catalog entry supplies the complete reviewed identity/compatibility evidence for a new direct-update recipe, so `app_recipes.json` intentionally starts with an empty reviewed list.
- Private state uses a 0700 directory and 0600 files, regular-file and symlink checks, generation/profile/ancestry checks, bounded reads and writes, an exclusive lock with a two-second deadline, and atomic replacement through the opened directory. A stale writer, oversized snapshot or failed replacement preserves the previous snapshot. Unsafe existing directory permissions are refused rather than changed automatically.

## Review and verification

One independent security/correctness review reproduced three findings: loss of old MAS/brew conflicts after a provider error; false absence caused by an organizational directory alias; and a writer accepting data larger than its reader could load. All three were corrected with red-to-green regression tests.

The coordinator also exercised the real shadow entrypoint in a disposable repository with a failing `update_all.sh` sentinel, verified the manager-to-bundle relation and conflict propagation, added aggregate scan budgets, and reproduced/corrected the Python 3.9 deep-JSON exception path. No real host inventory was collected.

Final verification:

- `bash run_tests.sh`: all four phases passed; 971 unittest cases in 263.704 seconds, 970 passed and one skipped. The skip is the private-inventory overlap check because `APPLICATIONS.md` is absent in the public checkout. No native-tool or network guard hits were reported.
- Actual Python 3.9.6: 87 targeted cases passed (68 inventory/provider/store/shadow/legacy-sync cases and 19 resolver cases). This is not a claim that the whole 971-case suite ran on 3.9.
- Warning-level ShellCheck passed for all tracked shell scripts; Ruff F checks passed for the new Python modules/tests. Staged gitleaks and the repository privacy/secret phase passed, with no private workspace or vault pointers in staged additions. Documentation links passed.
- An earlier full run had two static failures: missing full module filenames in documentation and synthetic test paths rejected by the existing host-path guard. Both were fixed without weakening that guard. A French shell literal was corrected after ShellCheck. These earlier runs are not the final gate evidence.
- No real host inventory, application update, installation, updater launch, migration of user data or publication occurred.

## Decisions, limitations and remaining work

1. Stage B adds an opt-in shadow command rather than enabling a half-migrated executor. The production resolver/guard activation, user choices, Markdown migration and journal belong to C.
2. Static Homebrew JSON is deliberately preferred to commands that could refresh external metadata or evaluate casks. Ruby-only casks, missing artifact links, pkg effects and inaccessible prefixes remain partial. No directory guess authorizes a destination.
3. The new resolver never uses legacy display-name aliases. Legacy active aliases remain until C; removing them independently would violate the agreed activation boundary.
4. Runtime signing identity and binary architecture remain unknown where static metadata does not establish them. Wrapped iPad apps or unusual layouts may be recorded with incomplete metadata. Framework detection does not open an arbitrary feed URL. Native launch, direct installation and latest-stable selection are not enabled.
5. User/system duplicates remain separate. A random local profile ID supports store consistency, not hardware attestation; copying a whole state directory is not an authorization mechanism. No policies or mutation consents are generated in this stage.
6. Limits protect ordinary failures and malformed inputs; these are not an operating-system sandbox or a guarantee against another process with the same user/root authority. Existing directory permissions may require deliberate administrator/user repair before opting into persistence.
7. No physical new-Mac acceptance, Linux CI run, actual app/package update, privileged operation or release was performed. No Actions triggers, schedules, runners or timeouts changed in this stage.

## Orchestration

Two GPT-6.1 Terra agents implemented collection/storage and resolution/recipes; one GPT-6.1 Sol agent performed the single independent review. There were eight assignments including follow-ups. The coordinator implemented provider/CLI integration, inspected the result, fixed integration regressions and verified the final gates. Applied procedures: orkiestra, subagent-driven-development and test-driven-development, with verification-before-completion at closure.
