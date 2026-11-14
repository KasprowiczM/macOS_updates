# Recipe evidence contract

As of 2026-11-14, `config/verified_recipes.json` contains an empty schema v2 recipe list. Its metadata covers the 48 catalog product identifiers for research coverage only. It grants no automatic update, installation or application lifecycle permission. DeepSeek remains excluded pending an independently reviewed stable release. The legacy `config/app_recipes.json` remains schema v1 and cannot be promoted automatically.

`app_recipes.load_verified_recipes(path)` reads bounded UTF-8 JSON with unique keys, exact fields and exact scalar types. It rejects unknown keys, executable recipe fields, unsupported schema versions, nonfinite constants, wildcard hosts, unbounded artifact limits and cyclic requirement graphs. `app_recipes.validate_recipe(recipe)` validates one v2 recipe without changing it. A structurally valid recipe still requires separate evidence and consent.

## Recipe fields

| Field | Contract |
| --- | --- |
| `id`, `product`, `edition`, `revision` | Stable recipe identifier, explicit product and edition, positive integer revision. Names never establish installed identity. |
| `bundle_ids`, `team_ids` | Nonempty reviewed identities. A candidate binds one exact bundle and ten-character Apple Team ID; updating another allowed identity is still denied. |
| `installation_source`, `update_mechanism`, `adapter_id` | Declared provenance and a closed implementation selector. No commands, argument strings, scripts or import paths. Supported implementation availability is a separate runtime gate. |
| `channel`, `minimum_os`, `architectures` | Explicit channel and known minimum OS; this project accepts arm64 recipes. Stable candidates require a numeric stable version. RC, beta, nightly and TestFlight require distinct recipes and explicit selection. |
| `allowed_artifacts`, `download_hosts` | Exact artifact types and HTTPS download hosts; no wildcards, URL credentials or fragments. Redirects must be independently checked by acquisition. |
| `candidate` | Exact release binding described below. A version string by itself is insufficient. |
| `requirement_graph` | Exact `nodes` and `edges`; nodes have `id`, `kind` (`permission` or `dependency`), `value` and scoped `operations`. Edges have `from` and `to`, refer to declared nodes and must form a DAG. All applicable nodes are obligations. An update never installs dependencies. Dependency installation is an explicit install effect and must finish before a parent operation can rely on its availability. |
| `effect_scope` | Separate lists for `update`, `install` and `lifecycle`. Update allows `replace_existing_app`, `native_update`, `manager_update`; install allows `install_app`, `install_dependency`; lifecycle allows `launch_app`, `quit_owned_app`. An empty operation scope cannot authorize execution. Source/channel migration and session restart are outside this contract. |
| `observation_contract` | Exact `preflight`, `postflight`, `requires_artifact_hash`. Identity, source, version and build are mandatory on both sides; preflight also covers requirements and postflight signature. Artifact hash verification is mandatory. |
| `limits` | Positive bounded integers: `maximum_bytes`, `maximum_expanded_bytes`, `maximum_entries`, `maximum_evidence_age_days`. |
| `matrix_ids` | Research matrix identifiers, all present in catalog metadata. Coverage is not acceptance. |
| `acceptance_records` | Separate arrays for `update`, `install`, `lifecycle`. No operation inherits another operation's records. |

The candidate has exactly `url`, `sha256`, `version`, `build`, `artifact_type`, `bundle_name`, `minimum_os`, `architecture`, `channel`, `product`, `edition`, `bundle_id`, `team_id`, `installation_source`, `feed_sequence`. All identity fields must fit the enclosing recipe. The SHA-256 is lowercase hexadecimal. Feed sequence is a nonnegative integer. A changed version, build, hash, source, URL, feed sequence or other field changes the binding.

## Acceptance records

Every record has exactly:

```text
id, recorded_at, recipe_revision, recipe_sha256, candidate_sha256,
artifact_sha256, operation, kind, result, os_version, architecture,
permissions, effect_scope, requirements_sha256, limitations, redacted_traces
```

`recorded_at` is UTC `YYYY-MM-DDTHH:MM:SSZ`. `kind` is `fixture` or `live`; `result` is `passed`, `failed` or `blocked`. `permissions`, `effect_scope`, `limitations` and nonempty `redacted_traces` are bounded string lists. Traces are sanitized descriptions or evidence identifiers, never real inventory, account details, receipt contents, user paths or raw local logs. Reviewers must perform redaction before adding public evidence; schema validation cannot prove that arbitrary text is anonymous.

`recipe_acceptance.recipe_fingerprint(recipe)` hashes canonical JSON of every recipe field except `acceptance_records`, avoiding circular evidence hashes. `candidate_binding(candidate)` hashes every candidate field. `requirements_fingerprint(recipe)` hashes the requirement graph. Canonical JSON uses sorted keys, compact separators, ASCII escapes and SHA-256 of UTF-8 bytes.

A matching record must be genuinely live and passed, have no unresolved limitations, be within the recipe's evidence-age limit and not in the future, and match the exact recipe revision and hash, candidate and artifact hashes, requirement graph, OS version, architecture, permissions and operation effects. Merely adding or relabeling a fixture record is not evidence of a live run. The catalog and record review process are the trust boundary; these hashes bind facts and do not authenticate an author.

## Runtime environment

`validate_recipe_evidence(recipe, operation, environment)` returns:

```json
{"allowed": false, "reasons": ["live_acceptance_required"], "evidence_ids": []}
```

It performs no process execution, filesystem discovery or network access. A runtime caller supplies trustworthy, fresh observations and consent. The environment contains:

- `target`: for update/lifecycle, actual `product`, `edition`, `bundle_id`, `team_id`, `installation_source`, `channel`, `presence`, `signature_valid` and boolean `app_store_receipt`. The existing bundle and signer must match the candidate exactly. Unknown receipt or signature state blocks external routes. App Store receipts cannot be updated by an external recipe.
- `candidate`: the exact bound candidate, plus optional `previous_candidate` for previously observed feed state. Older versions, regressed sequences, replacements at the same sequence, same-version changed builds/hashes and cross-product/source/channel baselines are denied. Unknown prerelease ordering requires separate review.
- `os_version`, `architecture`, `now`: known runtime environment and UTC clock. Live records match the exact tested OS version and architecture.
- `granted_permissions`, `granted_effects`, `available_requirements`: explicit lists. All applicable requirements and operation effects must be satisfied.
- `approved_recipe_sha256`, `approved_candidate_sha256`, `approved_requirements_sha256`: fingerprints bound into the caller's recorded consent. Recompute and compare at every authorization boundary.

For installation, `target` proves observed absence only. An absent application cannot provide an installed signature or receipt. After acquisition, `candidate_observation` must contain verified `signature_valid`, `app_store_receipt`, `artifact_sha256`, `bundle_id`, `team_id`, `version`, `build`, `architecture`, `minimum_os`. These must match the exact staged candidate; a copied flag from an absent target is insufficient. Planning before this observation remains pending.

The caller must refresh source ownership, identity, presence, running-state policy and consent immediately before mutation, then verify the postflight contract. An evidence decision does not waive transaction locks, rollback handling or lifecycle permission. Launching and quitting need their own acceptance and user authorization; a previously open application remains open. Installation never follows from update consent.

## Verification

`tests/fixtures/recipes/valid_v2.json` is synthetic, uses reserved example identities/hosts, and contains no live records. Unit tests construct synthetic records in memory to verify both acceptance and rejection branches. They are not product acceptance evidence.

Run the guarded tests with `bash run_tests.sh --unit-only --pattern 'test_recipe_acceptance.py'`. Product-specific dossiers record unknown facts and fixture scope explicitly; no dossier, matrix membership or passing mock can populate the live catalog by itself.
