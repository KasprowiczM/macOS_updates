# Dry-run fix, source 1.7.7

The plain preview printed the complete internal plan as one escaped JSON line. It now prints a localized, bounded human preview of at most 25 targets, with a complete-plan hint. `--plan` and `--dry-run --json-summary` preserve the JSON interface and the same decisions. No new consent, inventory writes, logs, locks or application operations are introduced by preview.

A closed output pipe was independently reproduced: Python returned 120 and emitted a shutdown BrokenPipeError. Explicit flushing and handling the closed reader now returns zero without that traceback. Unicode names are retained on UTF-8 terminals; explicit ASCII output uses escaped fallback instead of failing. The original reported crash text was unavailable, so this does not establish that every reported failure had this cause.

Focused guarded tests passed: 12 planning, 43 policy-runtime and 183 static safety cases. They cover Bash 3.2, seven languages, Unicode under C locale, explicit ASCII, existing inventory byte preservation, bounded human output versus complete JSON, and a closed pipe. Full release gate is recorded below.

The latest observed public real run ended after 23 seconds with warnings and no confirmed application updates. It was not a dry run. Its 219 partial inventory targets include 12 invalid cask metadata records; these host files were not repaired. macOS reported no available system update.

Live T6 tests are deferred by the owner. User feedback supplies diagnostic evidence, not automatic live acceptance or permission to activate an unverified recipe. DeepSeek remains excluded until stable. No real update, installation or app lifecycle operation was run on the owner's Mac for this change.

The first full release run collected 1334 tests in 387.472 seconds. Its only failure was a missing documentation-index entry for the offline readiness module added during the run. After indexing that module, all 183 static safety tests passed again. Shell and Python syntax checks and the secret scan passed. No host-tool or network guard hits were reported. The additional 16 readiness tests passed separately.
