# UniFi: recipe dossier

Product identifier: `unifi-gui`. Research wave: 4. Status as of 2026-11-14: **metadata review recorded, product acceptance pending**. No verified recipe is published for this product.

## Existing evidence

This dossier reconciles the existing [source research](../SOURCE_RESEARCH.md#current-channel-matrix), [mechanism research](../RECIPE_VERIFICATION_RESEARCH_2026-11-14.md), [verification matrix](../RECIPE_VERIFICATION_MATRIX_2026-11-14.md) and `config/channel_sources.json`. It makes no new network, native-tool or live-application observation.

Catalog summary: [primary](https://itunes.apple.com/search?term=UniFi&entity=software&country=us&limit=4). Apple publisher Ubiquiti Inc.; com.ubnt.unifiac11.1.0. reviewed/high listed identity. UniFi Network server/controller, UniFi Endpoint and Protect are separate products; no desktop migration from this iPad app.

The existing catalog records edition `gui`, metadata identity status `reviewed_metadata`, comparison policy `incomparable` and license review `unknown`. Metadata identity review does not establish the identity or ownership of an installed bundle. Catalog installation authority is false.

- [vendor](https://itunes.apple.com/search?term=UniFi&entity=software&country=us&limit=4), source metadata observed `2026-11-13T20:44:38.552212+00:00`; parser `unknown`, stable policy `unknown`, evidence key `mas-search:UniFi`.

## Identity and source gates

Production bundle ID, Apple Team ID, signed candidate artifact digest, candidate build and complete candidate minimum OS are **unknown in this dossier**. They must be observed and independently reviewed before a v2 candidate is created. No example signature or version is substituted for these unknowns. Published feed/cask metadata and response hashes are not artifact signature evidence or an offered update for a particular Mac/account.

Preserve the confirmed local installation source and receipt. App Store, Homebrew and vendor distributions require their own ownership proof; source conflict blocks execution. Stable remains the default; a preview release requires a separate identity/channel recipe and explicit consent. arm64 and compatible minimum OS must be established on the actual candidate.

## Candidate contract

Matrix update candidate: App Store zgodnie z receipt.

Matrix first-install candidate: Ręczne pozyskanie App Store.

Specific review gate: Aplikacja iPad kontra kontroler serwera; offered/account/region.

These are candidates for investigation, not accepted adapters. Use only a documented, closed adapter implementation with an exact recipe revision, version/build, artifact/source binding, bounded effects and fresh observations. Generic framework detection cannot invent a trigger or ready signal. A native updater command must prove its full target scope; an artifact path must prove its payload contains only approved effects. Unknown helper, installer, account, license, active-work or lifecycle behavior remains manual.

## Fixture evidence and limits

`tests/fixtures/recipes/unifi-gui/scenarios.json` supplies 19 deterministic synthetic safety cases: absent, current, newer, older, offline, HTTP 429, partial download, bad signature, wrong identity, wrong OS, wrong architecture, running, duplicate, source conflict, permission denial, crash, rerun, unknown minimum OS and prerelease. `tests/test_recipe_fixture_matrix.py` invokes the real acceptance predicate, adapter preparation and source resolver; the running case also exercises transaction preparation against a temporary directory, and version cases invoke the production version comparator.

The bundle `org.example.fixture`, Team ID `EXAMPL1234`, example.org endpoint, numeric versions and repeated hashes belong only to the shared synthetic fixture. They are not identities, releases, signatures or downloads of UniFi. Every acceptance record remains fixture-only, every scenario stays non-executable, and every real product identity stays unresolved. Offline/429 cases model unavailable observations, partial download models a changed digest, and crash/rerun model incomplete observations/stale consent. They do not certify product transport, payload, crash recovery, native trigger or lifecycle behavior.


The product-specific `tests/fixtures/recipes/unifi-gui/contract.json` now pins this actual catalog edition, comparison policy, source IDs, source URLs, parser/stable policies, evidence references and scope blocker. `tests/test_recipe_product_contracts.py` executes those actual source parser configurations against existing captured metadata projections. Parsed captured source metadata projections: none; no reviewed source parser is available. Retained rejection gates: vendor: parser_unreviewed. Cask token mismatches, GitHub prerelease flags, unknown stable policies, Open Design failed-platform state, Firefox Developer Edition preview status and Proton staged rollout are tested where the corresponding product uses that contract. Public metadata never proves an offered release or local ownership; source conflict and unmatched product/edition stay blocked.

No existing historical vendor parser fixture is mapped to this product. Product-specific payload/native protocol evidence remains required.

## Acceptance still required

Live update: missing. Live first install: missing. Live lifecycle: missing. Deterministic vendor-payload/native-protocol acceptance: missing. Successful shared safety tests do not close any of these gates or populate `verified_recipes.json`.

Next actions: resolve the specific review gate above; capture a sanitized immutable candidate and actual identity/source/OS/arch/effects; exercise product-specific artifact/native protocol fixtures; review licenses and dependencies; then seek separately scoped owner consent for any later live update, install or lifecycle test. No app needs to be launched to complete this dossier.
