import copy
import datetime
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib/python"))
from channel_advisor import recommend_channel, compare_channel_releases
from channel_probes import (
    collect_channel_observations,
    load_channel_sources,
    compare_selected_channels,
)

NOW = "2026-11-13T21:00:00Z"


def recipe():
    return {
        "product_id": "example-desktop",
        "edition": "gui",
        "version_comparison_policy": "numeric",
        "sources": [],
        "compatible_updaters": [],
    }


def observation(source, version, **changes):
    result = {
        "product_id": "example-desktop",
        "edition": "gui",
        "source_id": source,
        "updater_id": source,
        "release_channel": "stable",
        "stable_confirmed": True,
        "version": version,
        "build": None,
        "release_identity": version,
        "published_at": None,
        "observed_at": NOW,
        "availability": "listed",
        "compatibility": {
            "status": "compatible",
            "minimum_os": "13",
            "architectures": ["arm64"],
        },
        "region": None,
        "evidence_url": "https://vendor.example/metadata",
        "fetch_status": "ok",
        "cached": False,
    }
    result.update(changes)
    return result


class ChannelAdvisorTests(unittest.TestCase):
    def test_vendor_ahead_is_proposal_not_migration(self):
        result = recommend_channel(
            recipe(),
            [observation("vendor", "2"), observation("homebrew", "1")],
            {
                "product_id": "example-desktop",
                "edition": "gui",
                "source_id": "homebrew",
            },
            {},
        )
        self.assertEqual(result["recommended_source_id"], "vendor")
        self.assertTrue(result["migration_required"])
        self.assertEqual(result["historical_sample_size"], 0)
        self.assertNotIn("fastest", json.dumps(result))

    def test_brew_tie_preserves_current_source_and_payload(self):
        for current in ["homebrew", "vendor"]:
            result = recommend_channel(
                recipe(),
                [observation("vendor", "2"), observation("homebrew", "2")],
                {
                    "product_id": "example-desktop",
                    "edition": "gui",
                    "source_id": current,
                },
                {},
            )
            self.assertEqual(result["recommended_source_id"], current)
            self.assertFalse(result["migration_required"])

    def test_mas_can_be_ahead_but_listed_never_offered(self):
        result = recommend_channel(
            recipe(),
            [observation("vendor", "1"), observation("app_store", "2", region="us")],
            None,
            {},
        )
        self.assertEqual(result["recommended_source_id"], "app_store")
        self.assertIsNone(result["actually_offered"])

    def test_late_mas_not_permanently_demoted(self):
        result = recommend_channel(
            recipe(),
            [observation("vendor", "2"), observation("app_store", "1", region="us")],
            {
                "product_id": "example-desktop",
                "edition": "gui",
                "source_id": "app_store",
            },
            {},
        )
        self.assertEqual(result["recommended_source_id"], "vendor")

    def test_prerelease_or_latest_word_is_never_stable_proof(self):
        for changed in [
            {"release_channel": "beta"},
            {"version": "3.0rc1"},
            {"stable_confirmed": False},
            {"release_channel": "nightly"},
        ]:
            row = observation("npm", "3")
            row.update(changed)
            result = recommend_channel(recipe(), [row], None, {})
            self.assertIsNone(result["recommended_source_id"])
            self.assertIsNone(result["latest_global_stable"])

    def test_product_and_edition_are_hard_boundaries(self):
        wrong = [
            observation("npm", "999", edition="cli"),
            observation("vendor", "999", product_id="other"),
        ]
        result = recommend_channel(
            recipe(), wrong + [observation("vendor", "1")], None, {}
        )
        self.assertEqual(result["latest_global_stable"]["version"], "1")
        self.assertEqual(
            compare_channel_releases(recipe(), wrong[0], observation("vendor", "1")),
            "incomparable",
        )

    def test_incompatible_latest_and_staged_rollout(self):
        rows = [
            observation("vendor", "3", compatibility={"status": "incompatible"}),
            observation("vendor", "2", availability="staged"),
            observation("homebrew", "1"),
        ]
        result = recommend_channel(recipe(), rows, None, {})
        self.assertEqual(result["latest_global_stable"]["version"], "3")
        self.assertEqual(result["latest_compatible_stable"]["version"], "2")
        self.assertEqual(result["recommended_source_id"], "homebrew")

    def test_unknown_compatibility_and_missing_source_cannot_win(self):
        result = recommend_channel(
            recipe(),
            [
                observation("vendor", "3", compatibility={"status": "unknown"}),
                observation("homebrew", None, fetch_status="unavailable"),
            ],
            None,
            {},
        )
        self.assertIsNone(result["recommended_source_id"])
        self.assertIn("source_unavailable", result["reason_codes"])

    def test_region_unknown_has_explicit_uncertainty(self):
        result = recommend_channel(recipe(), [observation("app_store", "2")], None, {})
        self.assertIn("storefront_or_offer_unknown", result["uncertainty"])

    def test_unreviewed_numbering_is_incomparable(self):
        r = recipe()
        r["version_comparison_policy"] = "incomparable"
        self.assertEqual(
            compare_channel_releases(
                r, observation("vendor", "2"), observation("homebrew", "1")
            ),
            "incomparable",
        )
        self.assertIsNone(
            recommend_channel(
                r, [observation("vendor", "2"), observation("homebrew", "1")], None, {}
            )["recommended_source_id"]
        )

    def test_native_updater_ownership_requires_explicit_review(self):
        r = recipe()
        rows = [
            observation("homebrew", "2", updater_id="homebrew"),
            observation("vendor", "2", updater_id="native"),
        ]
        installed = {
            "product_id": "example-desktop",
            "edition": "gui",
            "source_id": "homebrew",
            "updater_id": "homebrew",
        }
        result = recommend_channel(
            r, rows, installed, {"preferred_updater_id": "native"}
        )
        self.assertEqual(result["recommended_updater_id"], "homebrew")
        r["compatible_updaters"] = [
            {
                "installation_source": "homebrew",
                "updater_id": "native",
                "reviewed": True,
            }
        ]
        self.assertEqual(
            recommend_channel(r, rows, installed, {"preferred_updater_id": "native"})[
                "recommended_updater_id"
            ],
            "native",
        )


class ChannelProbeTests(unittest.TestCase):
    def setUp(self):
        self.cache_tmp = tempfile.TemporaryDirectory()
        self.cache_root = pathlib.Path(self.cache_tmp.name).resolve() / "state"
        self.cache_root.mkdir(mode=0o700)
        self.cache_patch = patch(
            "inventory_store.default_root", return_value=str(self.cache_root)
        )
        self.cache_patch.start()
        self.system_patch = patch(
            "channel_probes._system_environment",
            return_value={"os_version": "14", "architecture": "arm64"},
        )
        self.system_patch.start()

    def tearDown(self):
        self.system_patch.stop()
        self.cache_patch.stop()
        self.cache_tmp.cleanup()

    def fixture_recipe(self):
        r = recipe()
        r["sources"] = [
            {
                "source_id": "vendor",
                "updater_id": "native",
                "url": "https://api.github.com/repos/example/desktop/releases/latest",
                "allowed_hosts": ["api.github.com"],
                "parser": "github_release",
                "stable_policy": "github_flags",
                "architectures": ["arm64"],
                "minimum_os": "13",
                "identity_reviewed": True,
            }
        ]
        return r

    def test_github_flags_and_compatibility(self):
        r = self.fixture_recipe()
        rows = collect_channel_observations(
            r,
            {"os_version": "14", "architecture": "arm64"},
            lambda *a, **k: {
                "status": 200,
                "body": json.dumps(
                    {"tag_name": "v2.0", "prerelease": False, "draft": False}
                ),
            },
            {},
            NOW,
        )
        self.assertTrue(rows[0]["stable_confirmed"])
        self.assertEqual(rows[0]["compatibility"]["status"], "compatible")
        rows = collect_channel_observations(
            r,
            {"os_version": "12", "architecture": "arm64"},
            lambda *a, **k: {
                "status": 200,
                "body": json.dumps(
                    {"tag_name": "v2.0", "prerelease": False, "draft": False}
                ),
            },
            {},
            NOW,
        )
        self.assertEqual(rows[0]["compatibility"]["status"], "incompatible")

    def test_cache_24h_refresh_and_429_no_loop(self):
        r = self.fixture_recipe()
        cache = {}
        calls = []

        def fetch(*args, **kwargs):
            calls.append(1)
            return {
                "status": 200,
                "body": json.dumps(
                    {"tag_name": "v2.0", "prerelease": False, "draft": False}
                ),
            }

        collect_channel_observations(
            r, {"os_version": "14", "architecture": "arm64"}, fetch, cache, NOW
        )
        rows = collect_channel_observations(
            r,
            {"os_version": "14", "architecture": "arm64"},
            fetch,
            cache,
            "2026-11-14T20:59:59Z",
        )
        self.assertTrue(rows[0]["cached"])
        self.assertEqual(len(calls), 1)
        collect_channel_observations(
            r,
            {"os_version": "14", "architecture": "arm64", "refresh": True},
            fetch,
            cache,
            NOW,
        )
        self.assertEqual(len(calls), 2)
        rows = collect_channel_observations(
            r,
            {"refresh": True},
            lambda *a, **k: {"status": 429, "retry_after": "120", "body": ""},
            cache,
            NOW,
        )
        self.assertEqual(rows[0]["fetch_status"], "rate_limited")
        self.assertEqual(rows[0]["retry_after"], 120)

    def test_arbitrary_feed_never_fetched(self):
        r = self.fixture_recipe()
        r["sources"][0]["url"] = "https://attacker.example/feed"
        calls = []
        rows = collect_channel_observations(
            r, {}, lambda *args, **kwargs: calls.append(args), {}, NOW
        )
        self.assertEqual(calls, [])
        self.assertEqual(rows[0]["fetch_status"], "unreviewed_source")

    def test_manifest_keeps_47_rows_and_splits_products(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        manifest = load_channel_sources(str(root / "config/channel_sources.json"))
        registry = [
            s.strip()
            for s in (root / "config/internet_apps.txt").read_text().splitlines()
            if s.strip() and not s.startswith("#")
        ]
        self.assertEqual([r["name"] for r in manifest["registry_rows"]], registry)
        split = next(
            r for r in manifest["registry_rows"] if r["name"] == "ChatGPT / Codex"
        )
        self.assertEqual(len(split["product_ids"]), 2)

    def test_only_selected_or_trusted_installed_products_are_probed(self):
        calls = []
        result = compare_selected_channels(
            {"instances": [{"name": "Google Chrome", "presence": "present"}]},
            environment={"os_version": "14", "architecture": "arm64"},
            fetch=lambda *a, **k: calls.append(a),
            now=NOW,
        )
        self.assertEqual(calls, [])
        self.assertEqual(result["recommendations"], [])

    def test_parallel_and_host_limits_with_real_fixture_scheduler(self):
        import threading, time

        r = self.fixture_recipe()
        products = []
        for index in range(6):
            item = copy.deepcopy(r)
            item["product_id"] = "example-" + str(index)
            item["name"] = item["product_id"]
            products.append(item)
        manifest = {"schema_version": 1, "registry_rows": [], "products": products}
        active = 0
        maximum = 0
        mutex = threading.Lock()

        def fetch(*args, **kwargs):
            nonlocal active, maximum
            with mutex:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.005)
            with mutex:
                active -= 1
            return {
                "status": 200,
                "body": json.dumps(
                    {"tag_name": "v2", "prerelease": False, "draft": False}
                ),
            }

        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root) / "manifest.json"
            path.write_text(json.dumps(manifest))
            compare_selected_channels(
                {},
                [p["product_id"] for p in products],
                manifest_path=str(path),
                fetch=fetch,
                now=NOW,
            )
        self.assertEqual(maximum, 1)
        for index, item in enumerate(products):
            item["sources"][0]["url"] = (
                "https://host" + str(index) + ".example/metadata"
            )
            item["sources"][0]["allowed_hosts"] = ["host" + str(index) + ".example"]
        maximum = 0
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root) / "manifest.json"
            path.write_text(json.dumps(manifest))
            compare_selected_channels(
                {},
                [p["product_id"] for p in products],
                manifest_path=str(path),
                fetch=fetch,
                now=NOW,
            )
        self.assertGreater(maximum, 1)
        self.assertLessEqual(maximum, 3)

    def test_exhausted_budget_marks_pending_without_fetch(self):
        from channel_probes import ProbeBudget

        budget = ProbeBudget(seconds=0)
        calls = []
        result = collect_channel_observations(
            self.fixture_recipe(),
            {"_budget": budget},
            lambda *a, **k: calls.append(a),
            {},
            NOW,
        )
        self.assertEqual(calls, [])
        self.assertEqual(result[0]["fetch_status"], "pending")

    def test_expired_cache_is_fetched_and_clock_reversal_not_trusted(self):
        cache = {}
        calls = []

        def fetch(*args, **kwargs):
            calls.append(1)
            return {
                "status": 200,
                "body": json.dumps(
                    {"tag_name": "v2", "prerelease": False, "draft": False}
                ),
            }

        for now in [NOW, "2026-11-14T21:00:00Z", "2026-11-12T21:00:00Z"]:
            collect_channel_observations(self.fixture_recipe(), {}, fetch, cache, now)
        self.assertEqual(len(calls), 3)

    def test_public_store_requires_exact_mac_identity_and_never_offered(self):
        r = self.fixture_recipe()
        source = r["sources"][0]
        source.update(
            source_id="app_store",
            url="https://itunes.apple.com/lookup?id=1",
            allowed_hosts=["itunes.apple.com"],
            parser="app_store_mac",
            stable_policy="public_store_listing",
            store_id=1,
            bundle_id="org.example",
            region="us",
        )
        data = {
            "results": [
                {
                    "trackId": 1,
                    "bundleId": "org.example",
                    "kind": "software",
                    "version": "999",
                    "minimumOsVersion": "13",
                }
            ]
        }
        rows = collect_channel_observations(
            r, {}, lambda *a, **k: {"status": 200, "body": json.dumps(data)}, {}, NOW
        )
        self.assertEqual(rows[0]["fetch_status"], "unavailable")
        data["results"][0]["kind"] = "mac-software"
        rows = collect_channel_observations(
            r, {}, lambda *a, **k: {"status": 200, "body": json.dumps(data)}, {}, NOW
        )
        self.assertEqual(rows[0]["availability"], "listed")
        self.assertTrue(rows[0]["stable_confirmed"])

    def test_cached_history_preserves_first_observation_not_publication(self):
        from channel_probes import _record_history

        row = observation("vendor", "2", published_at="2026-01-01T00:00:00Z")
        history = _record_history([], [row])
        self.assertEqual(history[0]["first_observed_at"], NOW)
        row["observed_at"] = "2026-11-14T21:00:00Z"
        self.assertEqual(_record_history(history, [row])[0]["first_observed_at"], NOW)

    def test_history_needs_five_matched_releases_over_thirty_days(self):
        from channel_advisor import historical_evidence

        rows = []
        for index in range(5):
            day = (
                datetime.datetime(2026, 10, 1, tzinfo=datetime.timezone.utc)
                + datetime.timedelta(days=index * 8)
            ).isoformat()
            for source in ["homebrew", "vendor"]:
                rows.append(
                    {
                        "product_id": "example-desktop",
                        "edition": "gui",
                        "source_id": source,
                        "release_identity": str(index),
                        "stable_confirmed": True,
                        "first_observed_at": day,
                    }
                )
        self.assertTrue(historical_evidence(rows, "example-desktop")["qualified"])
        self.assertFalse(historical_evidence(rows[:8], "example-desktop")["qualified"])

    def test_retry_after_blocks_refresh_until_deadline(self):
        r = self.fixture_recipe()
        cache = {}
        calls = []

        def fetch(*args, **kwargs):
            calls.append(1)
            return {"status": 429, "retry_after": "120", "body": ""}

        first = collect_channel_observations(r, {"refresh": True}, fetch, cache, NOW)
        self.assertEqual(first[0]["fetch_status"], "rate_limited")
        second = collect_channel_observations(
            r, {"refresh": True}, fetch, cache, "2026-11-13T21:01:00Z"
        )
        self.assertEqual(len(calls), 1)
        self.assertTrue(second[0]["cached"])
        self.assertEqual(second[0]["fetch_status"], "rate_limited")
        collect_channel_observations(
            r, {"refresh": True}, fetch, cache, "2026-11-13T21:02:00Z"
        )
        self.assertEqual(len(calls), 2)

    def test_sanitized_acceptance_matrix_fixture(self):
        cases = json.loads(
            (
                pathlib.Path(__file__).parent / "fixtures/channels/recommendations.json"
            ).read_text()
        )["cases"]
        for case in cases:
            with self.subTest(case=case["name"]):
                r = recipe()
                r["version_comparison_policy"] = case.get("policy", "numeric")
                rows = []
                for source, version in case["versions"]:
                    row = observation(source, version)
                    if source in case.get("incompatible", []):
                        row["compatibility"] = {"status": "incompatible"}
                    if source in case.get("staged", []):
                        row["availability"] = "staged"
                    if source in case.get("cli", []):
                        row["edition"] = "cli"
                    rows.append(row)
                installed = (
                    {
                        "product_id": r["product_id"],
                        "edition": "gui",
                        "source_id": case["current"],
                    }
                    if case.get("current")
                    else None
                )
                self.assertEqual(
                    recommend_channel(r, rows, installed, {})["recommended_source_id"],
                    case["expected"],
                )

    def test_proton_fixture_preserves_stable_history_and_rollout(self):
        r = self.fixture_recipe()
        r["sources"][0].update(
            parser="proton_releases", stable_policy="category_stable"
        )
        body = (
            pathlib.Path(__file__).parent
            / "fixtures/channels/proton_stable_rollout.json"
        ).read_text()
        rows = collect_channel_observations(
            r,
            {"os_version": "14", "architecture": "arm64"},
            lambda *a, **k: {"status": 200, "body": body},
            {},
            NOW,
        )
        self.assertEqual([r["version"] for r in rows], ["3.0", "2.0"])
        self.assertEqual(rows[0]["availability"], "staged")
        self.assertEqual(rows[0]["compatibility"]["status"], "incompatible")
        self.assertEqual(
            recommend_channel(r, rows, None, {})["latest_compatible_stable"]["version"],
            "2.0",
        )

    def test_private_cache_persists_dates_and_avoids_second_network_probe(self):
        r = self.fixture_recipe()
        calls = []

        def fetch(*a, **k):
            calls.append(1)
            return {
                "status": 200,
                "body": (
                    pathlib.Path(__file__).parent
                    / "fixtures/channels/github_stable.json"
                ).read_text(),
            }

        with tempfile.TemporaryDirectory() as root:
            root = pathlib.Path(root).resolve()
            state = root / "state"
            state.mkdir(mode=0o700)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps({"schema_version": 1, "products": [r], "registry_rows": []})
            )
            for now in [NOW, "2026-11-14T20:00:00Z"]:
                result = compare_selected_channels(
                    {},
                    [r["product_id"]],
                    {"os_version": "14", "architecture": "arm64"},
                    state_dir=str(state),
                    manifest_path=str(manifest),
                    fetch=fetch,
                    now=now,
                )
            self.assertEqual(len(calls), 1)
            self.assertTrue(result["observations"][0]["cached"])
            persisted = state / "channel-observations.json"
            self.assertEqual(persisted.stat().st_mode & 0o777, 0o600)
            value = json.loads(persisted.read_text())
            self.assertEqual(value["history"][0]["first_observed_at"], NOW)

    def test_collector_shaped_cask_receipt_matches_product_without_name_guess(self):
        import channel_probes

        snapshot = {
            "instances": [
                {
                    "instance_id": "app1",
                    "path": "/fixture/apps/Unrelated Label.app",
                    "real_path": "/fixture/apps/Unrelated Label.app",
                    "presence": "present",
                    "freshness": "fresh",
                    "bundle_id": "untrusted.name",
                }
            ],
            "packages": [
                {
                    "package_id": "pkg1",
                    "manager": "homebrew",
                    "prefix": "/fixture/brew",
                    "source_identity": "cask:google-chrome",
                    "installed_receipt": "/fixture/brew/receipt",
                    "presence": "present",
                    "freshness": "fresh",
                    "related_instance_ids": ["app1"],
                    "evidence": [
                        {
                            "kind": "homebrew",
                            "token": "google-chrome",
                            "prefix": "/fixture/brew",
                            "installed_receipt": "/fixture/brew/receipt",
                        }
                    ],
                }
            ],
        }
        manifest = load_channel_sources()
        matched = channel_probes.match_installed_products(snapshot, manifest)
        self.assertEqual(set(matched), {"google-chrome-gui"})
        self.assertEqual(matched["google-chrome-gui"]["source_id"], "homebrew")
        snapshot["packages"][0]["evidence"] = []
        self.assertEqual(
            channel_probes.match_installed_products(snapshot, manifest), {}
        )

    def test_exact_reviewed_bundle_identity_can_match_without_product_id(self):
        import channel_probes

        snapshot = {
            "instances": [
                {
                    "instance_id": "app1",
                    "path": "/fixture/apps/Word.app",
                    "real_path": "/fixture/apps/Word.app",
                    "bundle_id": "com.microsoft.Word",
                    "presence": "present",
                    "freshness": "fresh",
                    "evidence": [{"kind": "app_store_receipt"}],
                }
            ]
        }
        matched = channel_probes.match_installed_products(
            snapshot, load_channel_sources()
        )
        self.assertEqual(set(matched), {"microsoft-word-gui"})
        self.assertEqual(matched["microsoft-word-gui"]["source_id"], "app_store")

    def test_default_cache_and_system_environment_use_controlled_fixture_values(self):
        import channel_probes

        with patch.object(
            channel_probes,
            "_system_environment",
            return_value={"os_version": "14", "architecture": "arm64"},
        ):
            r = self.fixture_recipe()
            with tempfile.TemporaryDirectory() as root:
                path = pathlib.Path(root) / "manifest.json"
                path.write_text(
                    json.dumps(
                        {"schema_version": 1, "products": [r], "registry_rows": []}
                    )
                )
                result = compare_selected_channels(
                    {},
                    [r["product_id"]],
                    manifest_path=str(path),
                    fetch=lambda *a, **k: {
                        "status": 200,
                        "body": json.dumps(
                            {"tag_name": "v2", "prerelease": False, "draft": False}
                        ),
                    },
                    now=NOW,
                )
            self.assertEqual(
                result["observations"][0]["compatibility"]["status"], "compatible"
            )

    def test_mixed_store_and_cask_ownership_is_not_a_silent_preference(self):
        import channel_probes

        snapshot = {
            "instances": [
                {
                    "instance_id": "app1",
                    "path": "/fixture/apps/Word.app",
                    "real_path": "/fixture/apps/Word.app",
                    "bundle_id": "com.microsoft.Word",
                    "presence": "present",
                    "freshness": "fresh",
                    "evidence": [{"kind": "app_store_receipt"}],
                }
            ],
            "packages": [
                {
                    "package_id": "pkg1",
                    "manager": "homebrew",
                    "prefix": "/fixture/brew",
                    "source_identity": "cask:microsoft-word",
                    "installed_receipt": "/fixture/brew/receipt",
                    "presence": "present",
                    "freshness": "fresh",
                    "related_instance_ids": ["app1"],
                    "evidence": [
                        {
                            "kind": "homebrew",
                            "token": "microsoft-word",
                            "prefix": "/fixture/brew",
                            "installed_receipt": "/fixture/brew/receipt",
                        }
                    ],
                }
            ],
        }
        matched = channel_probes.match_installed_products(
            snapshot, load_channel_sources()
        )
        self.assertEqual(matched["microsoft-word-gui"]["source_id"], "conflict")
        current = dict(
            product_id="example-desktop", edition="gui", source_id="conflict"
        )
        result = recommend_channel(recipe(), [observation("vendor", "2")], current, {})
        self.assertIsNone(result["recommended_source_id"])
        self.assertIn("source_conflict", result["reason_codes"])

    def test_same_host_429_stops_other_selected_product_requests(self):
        r = self.fixture_recipe()
        products = []
        for index in range(6):
            item = copy.deepcopy(r)
            item["product_id"] = "example-" + str(index)
            products.append(item)
        calls = []
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root) / "manifest.json"
            path.write_text(
                json.dumps(
                    {"schema_version": 1, "products": products, "registry_rows": []}
                )
            )
            result = compare_selected_channels(
                {},
                [p["product_id"] for p in products],
                manifest_path=str(path),
                fetch=lambda *a, **k: (
                    calls.append(1) or {"status": 429, "retry_after": "120", "body": ""}
                ),
                now=NOW,
            )
        self.assertEqual(len(calls), 1)
        self.assertTrue(
            all(r["fetch_status"] == "rate_limited" for r in result["observations"])
        )
