# Offline readiness and user feedback

Live T6 testing is deferred. T7 activation remains pending. The importable `lib/python/recipe_readiness.py` module helps review what is missing and compare reported timings. It does not install, update, launch, quit, change the catalog or grant consent. DeepSeek remains excluded until stable.

## Readiness API

`assess_catalog_readiness(catalog, environment)` accepts an in-memory schema-v2 catalog and the same observation/consent environment used by `validate_recipe_evidence`. Use the existing strict `app_recipes.load_verified_recipes` reader for a catalog file. No new file loader or pipeline entrypoint is introduced.

The report lists matrix IDs without recipes and separates update, install and lifecycle gates for each existing recipe. It applies the existing schema and acceptance predicates, checks the available adapter/driver and, when evidence matches, evaluates pure runtime preparation. Unknown observations, missing immutable candidates, missing live evidence and unsupported payload formats remain blocked. The environment applies to every recipe in that call; use separate calls for different target environments. The function does not create observations or approval bindings.

`evidence_allowed` describes whether the supplied evidence matches. `runtime_prepare_allowed` describes the pure preparation predicate, not authorization to run. `activation_allowed` is always false. Lifecycle is not a standalone dispatch operation; native updates require their own lifecycle evidence and consent. Manager support in the older updater does not imply an executable schema-v2 manager adapter. A valid readiness report is not an acceptance record.

## Minimal redacted feedback

The report below is a template for a person to fill in. Use the actual source version/commit, executed command and flags, OS/architecture, locale, terminal state and exact error. Preserve meaningful error codes and wording while replacing usernames, paths, account identifiers and credential values. Do not include full inventory, raw logs, receipt contents, keychain data, tokens or a private home directory. Unknown commit information stays `unknown`; it does not prove a tagged release.

```json
{
  "schema_version": 1,
  "toolkit_version": "1.7.7",
  "commit": "unknown",
  "command": "bash update_all.sh",
  "flags": ["--dry-run", "-y"],
  "os_version": "15.1",
  "architecture": "arm64",
  "locale": "pl_PL.UTF-8",
  "terminal": {"is_tty": true, "name": "Terminal"},
  "exact_error": "Paste the exact error here with private values replaced by REDACTED.",
  "redacted": true
}
```

`validate_feedback_report(report)` accepts the parsed in-memory object and returns structural validity, missing/invalid context and warnings. It accepts bounded script names and simple flag tokens, not shell command text or private paths. If a command included a sensitive argument, describe it separately after manual redaction instead of adding that argument to the structured flags. The redaction declaration is supplied by the reporter; the validator is not a secret scanner. Review the original manually before sharing it.

Every report is classified `unverified_user_feedback`, even when it says that an update succeeded or requests that guards be ignored. The returned report never echoes error prose, commands or private diagnostics. `trusted`, `verified` and `acceptance_eligible` are always false. Unknown fields, including attempted acceptance records, are rejected. There is no automatic conversion into live evidence, a recipe or an execution permission.

## Comparable timing API

`summarize_phase_timings(receipts)` accepts at most 20,000 in-memory phase events. Each event retains the ordinary receipt fields: `run_id`, `action_id`, `recipe_revision`, `phase`, timezone-aware `start` and `end`, integer nonnegative `elapsed_ms`, `outcome` and `evidence_type`. Add these explicit comparison fields to a copy of the event for this analysis:

- `recipe_id`: the exact recipe identifier.
- `operation`: `update`, `install` or `lifecycle`.
- `evidence_kind`: declared `fixture`, `live`, `user_feedback` or `unknown` provenance.
- `comparison_id`: a SHA256 of a canonical redacted comparison manifest binding the exact N/N+1 versions, builds and payload hashes; source/channel; recipe revision; OS/architecture and machine class; toolkit revision; effective wait budgets; sequential/parallel mode; network/fault conditions and observation method.

Use the same comparison ID only for repeated comparable trials. Use different IDs for baseline/candidate implementations, sequential/parallel modes or changed conditions, then compare their separate summaries. Ordinary receipts do not contain this complete comparison context; missing fields are rejected rather than guessed. A digest binds the caller's manifest but does not prove its accuracy. Retain that manifest privately for review.

Grouping separates recipe ID/revision, phase, comparison ID, operation, declared provenance, evidence type and outcome. Five distinct run IDs are required within each group before percentiles are emitted. Repeated identical events count once; conflicting events for the same run exclude that run. Different actions in one run cannot create independent trials. Callers must assign real independent run IDs; the summarizer cannot attest that two declared IDs came from distinct executions.

The p50 and p95 use nearest rank. With five trials, p95 is the largest measured sample and remains a coarse estimate. Below five trials both values are null and the group reports `insufficient_independent_runs`. Rejected-event, duplicate-event and conflicting-run counts remain visible. Declaring `live` does not validate live provenance: `verified_live_evidence` is always false. Fixture timings and user feedback cannot establish production performance gains or close T6/T7 gates.

## Deferred acceptance

A later disposable experiment still needs the separately selected Mac/VM, clean snapshots, immutable signed pilot artifacts, complete effects, operation-specific approval and trusted observations from the approved plan. User feedback can identify a reproducible bug and motivate guarded fixtures now. Live update, first-install, lifecycle and parallel acceptance remain separate requirements before activation. Public release claims must continue to distinguish researched products from accepted recipes.
