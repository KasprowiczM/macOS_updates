# DeepSeek Harness: deferred

Product identifier: `deepseek-harness-gui`. Status as of 2026-11-14: **deferred pending stable**, excluded from research execution and runtime acceptance in this stage.

Prior [research](../RECIPE_VERIFICATION_RESEARCH_2026-11-14.md) reports a nightly feed offering an RC. This is historical context only; no new product query, launch, updater invocation or installation was performed. No stable recipe, production bundle/Team ID, artifact digest or live acceptance record is supplied here.

The [matrix](../RECIPE_VERIFICATION_MATRIX_2026-11-14.md) records: Feed nightly oferuje RC; brak udokumentowanego zewnętrznego trigger/ready.

The sanitized fixture in `tests/fixtures/recipes/deepseek-harness-gui/scenarios.json` exercises only the real acceptance guard's exclusion of this matrix identifier. It does not test a DeepSeek updater, feed or application. The shared example identity is reserved test data.

The separate `contract.json` records the existing manifest contract and tests only the production exclusion guard. No DeepSeek source metadata or historical parser fixture is consumed, and no new research was performed.

Next gate: the owner must identify a published stable release and authorize a separate review before this exclusion can be reconsidered. Update, first install and lifecycle acceptance remain missing. Stable consent never selects nightly or RC.
