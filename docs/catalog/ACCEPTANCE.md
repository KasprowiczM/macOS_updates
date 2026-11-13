# Catalog acceptance evidence

Evidence date: 2026-11-13. This record covers deterministic fixtures and public metadata. It is not permission to publish, install applications on a real Mac, launch native updaters or migrate an existing installation between sources.

## Public catalog scope

The reviewed channel manifest covers every registry row. The 47 registry rows describe 48 separate products because ChatGPT and Codex are distinct products. Multiple sources for one product do not create extra product coverage.

All public setup entries currently remain manual acquisition entries. No public recipe has a passing first-install acceptance record. The number of researched products, the number of verified update adapters and the number of verified first-install recipes have separate meanings. Public metadata, an existing update handler or a matching version never establishes first-install safety.

The machine-independent catalog view includes public product identities, editions, available source metadata, updater hints and verification state. It starts without selected items. It excludes local application paths, account details and receipt contents. Official URLs must use HTTPS without embedded credentials. See [SOURCE_RESEARCH.md](SOURCE_RESEARCH.md) and [SOURCE_RESEARCH_EVIDENCE.json](SOURCE_RESEARCH_EVIDENCE.json) for the dated research evidence and its limits.

## Fixture acceptance matrix

| Scenario | Required observed behavior | Evidence |
|---|---|---|
| Empty scan | Zero detected applications and no install command | `tests/test_catalog_acceptance.py` |
| Public catalog without selection | All rows unselected; no implicit dependencies or application writes | `tests/test_catalog_acceptance.py` |
| Catalog without a terminal, with automatic yes, or with EOF | No new consent and no installation | `tests/test_catalog_acceptance.py` |
| Empty or cancelled selection | Empty InstallPlan and dependency graph | `tests/test_catalog_acceptance.py` |
| Two selected products share a dependency | One shared required node; no dependency from an unselected product | `tests/test_catalog_acceptance.py` |
| Old InstallPlan presented to updater | Rejected by update-plan loader; updater cannot execute it | `tests/test_catalog_acceptance.py` |
| One consented synthetic install action | Only its absent destination changes; observation precedes snapshot recording | `tests/test_catalog_acceptance.py` |
| An action outside the accepted subset | No application or snapshot write | `tests/test_catalog_acceptance.py` |
| Vendor ahead, manager tie or App Store ahead | Product-specific compatible stable evidence controls a proposal | `tests/test_channel_advisor.py` |
| Missing, incompatible or prerelease-only metadata | No unsupported recommendation and no source migration | `tests/test_channel_advisor.py` |
| Uncertain version numbering or GUI versus CLI | Incomparable, without aliasing different products | `tests/test_channel_advisor.py` |
| Insufficient publication history | No claim that a source is historically fastest | `tests/test_channel_advisor.py` |

The first-install success fixture uses a synthetic recipe, an isolated destination, staged local files and an injected identity observer. It verifies transaction and consent behavior. It does not verify a real vendor signature, downloadable artifact, license, package script or application launch.

Native commands and network access are denied by default in these fixtures. Shell integration uses temporary HOME, application roots, state, checkout and PATH doubles. Only the explicitly declared signed-out App Store observation is permitted. An attempted forbidden command is a failure even when its double refuses to make a change.

## Executed and outstanding checks

The independent catalog acceptance suite passed all 9 tests on 2026-11-13 in 1.318 seconds. This includes actual shell processes, terminal empty input and EOF, no-terminal and automatic-yes paths, an unchanged old InstallPlan, and the selected synthetic filesystem installation. The existing channel advisor suite passed all 31 tests with fixture metadata in 0.081 seconds. Its recommendation and bounded-probe scenarios are reused rather than duplicated here. Full guarded toolkit verification belongs to the final integration gate; these selections are not a full-suite pass.

No disposable-Mac fresh installation, actual App Store acquisition, privileged package installation, native updater launch, reboot, cross-account GUI run or supported-OS matrix was performed for this record. Those checks require separate owner approval and a dated record naming recipe revision, source, version, architecture, OS, requirements and outcome. No public recipe becomes installable from this fixture record alone.

Publication, merge, tagging, release parity and landing synchronization remain separate approved steps. The landing is outside this acceptance change.

## Integrated local gate

The sealed stage-E integration passed 1178 collected cases, 1177 passed and one expected private-inventory skip, in 220.231 seconds. Zero unexpected host-command or network guard hits were reported. Bash syntax, Python compilation, tracked secrets and warning-level ShellCheck passed. Python 3.9.6 passed 102 selected channel/catalog/setup/install cases. This adds fixture evidence only; the live acceptance boundaries above remain open.
