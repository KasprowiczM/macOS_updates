# Source-aware inventory and catalog, 1.7.0

Local implementation report for the approved A-E plan. This source version is unpublished. No release tag, push, merge, deployment, real application update, host inventory migration or landing change is part of this work.

## Result

- Inventory is built from the current Mac's observations. Catalog membership and an old Markdown list cannot create an installed target or authorize installation.
- Source conflicts, missing receipts, absent managers and incomplete scans are explicit states. Unknown apps stay visible and usable through manual handling. Ordinary missing catalog casks do not become update failures.
- Updates require an existing, fresh target, confirmed source, scoped consent and revalidation immediately before execution. Related cask artifacts and dependency effects are checked. Deleted apps are not recreated; source and destination changes require a new decision.
- Markdown migration preserves original bytes and notes with private backups, generation checks and recovery. Update transactions retain a recoverable good copy and use shared resource locks across checkouts.
- Product-specific advice compares confirmed compatible stable releases. It distinguishes public versions from versions actually offered to a user and does not assume App Store is slower.
- The optional setup catalog starts unselected and uses a separate InstallPlan. Requirements and permissions appear before fresh digest-bound approval. Manual acquisition can be followed by an optional new scan; opening a page never means installed.

## Scope of automatic execution

The public catalog contains 47 registry rows describing 48 products. All first-install entries currently remain manual or pending review. There are **zero approved public automatic first-install recipes**. Generic native/direct update recipes also remain disabled until their identity and execution contract are reviewed. The older method list describes capabilities and historical adapters, not new execution authority.

Scoped manager updates are available only when their observed receipt, target, related artifacts, metadata effects and saved permission satisfy the guard. Opaque packages, additional cask dependencies, npm scripts or new command links defer to manual handling. Existing application sources are never migrated automatically. The staged vendor-bundle installation adapter is validated with synthetic fixtures, not real vendor acceptance.

## Verification

| Checkpoint | Result |
|---|---|
| C, source 1.6.3 | 1101 collected, 1100 passed, one intentional skip; 232.233 seconds |
| D, source 1.6.4 | 1103 collected, 1102 passed, one intentional skip; 222.774 seconds |
| E, source 1.6.5 | 1178 collected, 1177 passed, one intentional skip; 220.231 seconds |
| Python 3.9.6 | 188 C critical cases, two D profile methods and 102 E/channel/setup/installation cases passed |
| New-user fixtures | 29 profiles plus a 100-bundle offline scan under a five-second budget |
| Languages | All seven locale key sets match; no duplicate keys |
| Final 1.7.0 closure | Two version checks passed; static safety collected 183 cases, 182 passed and one expected private-inventory skip |

Sealed C and D exports prevent parallel E edits from changing those checkpoints. Their full runners include Bash syntax, Python compilation and tracked secret scanning, with zero unexpected command/network guard hits. The one skip requires a private APPLICATIONS.md and is expected in a clean export. It is not a skipped safety scenario. The full E runner also passed with zero guard hits. All tracked shell files passed warning-level ShellCheck; new modules and tests passed Ruff F checks. The only runtime-file edit after the sealed export changes CLI help text and has 28 passing guarded CLI cases. The 1.7.0 closure changes version and documentation only. Version consistency, static safety and locale parity passed again against the final working tree. Local documentation links and staged secrets also passed.

One independent C/D security review closed related-artifact identity, hidden cask dependency, npm effect-scope and transport deadline findings. One independent E review closed the install-journal crash window. Parent integration checks covered exact custom cask destinations, truncated downloads, real collector-to-catalog matching, fresh per-action observations and manual rescan behavior.

## Remaining acceptance boundaries

Linux execution was not run because the local container engine was unavailable; it was not started and CI was not triggered. No supported-macOS matrix, disposable-Mac fresh install, other-account/region GUI acquisition, privileged package, reboot or live updater was exercised. Historical live receipts do not certify the new executor or a first-install recipe. See [catalog acceptance](../catalog/ACCEPTANCE.md).

Future public automatic recipes require a separate dated first-install record with exact identity, source, revision, version, architecture, OS, requirements and observed result. Publication, Ascendo parity and landing synchronization remain separate authorized operations. The implementation changes no workflow schedule or runner budget.

## Local entrypoints

```bash
bash setup.sh --inspect
bash build_inventory.sh
bash update_all.sh --plan
bash setup.sh --catalog
```

For an existing Markdown report, first use `bash build_inventory.sh --migration --preview`, inspect the proposal and accept its displayed ID explicitly. Preview and ordinary updates grant no new first-install permission. Review or reset update choices through `bash update_all.sh --preferences` in an interactive run.

Details: [approved plan](../superpowers/plans/2026-11-13-source-aware-inventory.md), [stage C](STAGE_C_1.6.3.md), [stage D](STAGE_D_1.6.4.md), [stage E](STAGE_E_1.6.5.md), [source research](../catalog/SOURCE_RESEARCH.md).
