import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib", "python"))
from source_resolver import resolve_target
from app_recipes import load_recipes, load_legacy_capabilities


def app(evidence=(), path="/fixture/Applications/CapCut.app", **extra):
    return dict(
        {
            "target": {"kind": "app", "id": "a"},
            "instance_id": "a",
            "real_path": path,
            "presence": "present",
            "freshness": "fresh",
            "channel": "stable",
            "evidence": list(evidence),
        },
        **extra,
    )


def ev(kind, **kw):
    return dict(kind=kind, **kw)


class ResolverTests(unittest.TestCase):
    def resolve(self, target, recipes=None, snapshot=None):
        return resolve_target(
            target,
            snapshot or {"instances": [], "packages": [], "os_version": "14"},
            recipes or {"schema_version": 1, "recipes": []},
        )

    def test_receipt_and_stale_brew_conflict(self):
        r = self.resolve(
            app(
                [
                    ev("app_store_receipt"),
                    ev(
                        "homebrew",
                        token="capcut",
                        prefix="/opt/homebrew",
                        artifact_path="/fixture/Applications/CapCut.app",
                        installed_receipt=True,
                        freshness="stale",
                    ),
                ]
            )
        )
        self.assertEqual((r["source"], r["capability"]), ("conflict", "inventory_only"))

    def test_receipt_only_and_catalog_is_not_ownership(self):
        self.assertEqual(
            self.resolve(app([ev("app_store_receipt")]))["source"], "app_store"
        )
        r = self.resolve(
            app(
                [
                    ev(
                        "homebrew",
                        token="capcut",
                        prefix="/opt/homebrew",
                        artifact_path="/fixture/Applications/CapCut.app",
                        installed_receipt=False,
                    )
                ]
            )
        )
        self.assertEqual(r["source"], "unknown")

    def test_brew_requires_matching_artifact_and_receipt(self):
        e = ev(
            "homebrew",
            token="different-token",
            prefix="/opt/homebrew",
            artifact_path="/fixture/Applications/CapCut.app",
            installed_receipt=True,
        )
        self.assertEqual(self.resolve(app([e]))["source"], "homebrew")
        e["artifact_path"] = "/fixture/Applications/Other.app"
        self.assertEqual(self.resolve(app([e]))["source"], "unknown")

    def test_framework_never_claims_vendor(self):
        r = self.resolve(app([ev("framework", name="Sparkle")]))
        self.assertEqual((r["source"], r["capability"]), ("unknown", "check_only"))

    def test_protected_location_and_enterprise(self):
        self.assertEqual(self.resolve(app([ev("protected_root")]))["source"], "unknown")
        self.assertEqual(
            self.resolve(
                app([ev("protected_root")], path="/System/Applications/Mail.app")
            )["source"],
            "apple_system",
        )
        self.assertEqual(
            self.resolve(app([ev("enterprise_managed")]))["source"],
            "enterprise_managed",
        )

    def test_review_requires_signature_and_channel(self):
        recipe = {
            "schema_version": 1,
            "recipes": [
                {
                    "id": "v",
                    "adapter_id": "github_dmg",
                    "bundle_ids": ["org.example.app"],
                    "team_ids": ["TEAM"],
                    "channels": ["stable"],
                    "architectures": ["arm64"],
                    "minimum_os": "13",
                    "download_hosts": ["example.org"],
                    "allowed_artifacts": ["dmg"],
                }
            ],
        }
        target = app(
            [ev("vendor_signature", bundle_id="org.example.app", team_id="TEAM")],
            bundle_id="org.example.app",
            team_id="TEAM",
            architectures=["arm64"],
        )
        self.assertEqual(self.resolve(target, recipe)["capability"], "reviewed_direct")
        target["team_id"] = "OTHER"
        self.assertNotEqual(
            self.resolve(target, recipe)["capability"], "reviewed_direct"
        )
        target["team_id"] = "TEAM"
        target["channel"] = "testflight"
        self.assertNotEqual(
            self.resolve(target, recipe)["capability"], "reviewed_direct"
        )

    def test_package_and_duplicates(self):
        p = {
            "target": {"kind": "package", "id": "p"},
            "package_id": "p",
            "manager": "npm",
            "prefix": "/opt/npm",
            "presence": "present",
            "freshness": "fresh",
            "installed_receipt": True,
            "source_identity": "example",
            "evidence": [
                ev(
                    "npm",
                    name="example",
                    prefix="/opt/npm",
                    manifest_path="/opt/npm/lib/node_modules/example/package.json",
                )
            ],
        }
        self.assertEqual(self.resolve(p)["source"], "npm")
        a = app([ev("app_store_receipt")], bundle_id="org.example")
        b = app(
            [],
            path="/fixture/users/test/Applications/CapCut.app",
            bundle_id="org.example",
        )
        b["instance_id"] = "b"
        self.assertIn(
            "duplicate_bundle_id",
            self.resolve(a, snapshot={"instances": [a, b]})["reason_codes"],
        )


class RecipeTests(unittest.TestCase):
    def load(self, obj):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "recipes.json")
            with open(path, "w") as f:
                json.dump(obj, f)
            return load_recipes(path)

    def test_strict_nested_fields_and_types(self):
        self.assertEqual(self.load({"schema_version": 1, "recipes": []})["recipes"], [])
        for obj in (
            {"schema_version": 1, "recipes": [], "command": "x"},
            {"schema_version": 1, "recipes": [{"id": "x", "command": "evil"}]},
            {"schema_version": True, "recipes": []},
        ):
            with self.subTest(obj=obj), self.assertRaises(ValueError):
                self.load(obj)

    def test_legacy_catalog_only_declares_capability(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "methods.txt")
            with open(path, "w") as f:
                f.write("Example|silent_launch|STATUS_EXAMPLE\n")
            self.assertEqual(
                load_legacy_capabilities(path),
                [{"name": "Example", "adapter_id": "silent_launch"}],
            )


class AcceptanceTests(unittest.TestCase):
    def resolve(self, target, snapshot=None, recipes=None):
        return resolve_target(
            target,
            snapshot or {"instances": [], "packages": [], "os_version": "14"},
            recipes or {"schema_version": 1, "recipes": []},
        )

    def recipe(self):
        return {
            "schema_version": 1,
            "recipes": [
                {
                    "id": "vendor",
                    "adapter_id": "github_dmg",
                    "bundle_ids": ["org.example.app"],
                    "team_ids": ["TEAM"],
                    "channels": ["stable"],
                    "architectures": ["arm64"],
                    "minimum_os": "13",
                    "download_hosts": ["example.org"],
                    "allowed_artifacts": ["dmg"],
                }
            ],
        }

    def test_current_target_and_batch(self):
        from source_resolver import resolve_snapshot

        a = app([ev("app_store_receipt")])
        del a["target"]
        results = resolve_snapshot({"instances": [a], "packages": []}, {"recipes": []})
        self.assertEqual(results[0]["target"], {"kind": "app", "id": "a"})
        self.assertEqual(results[0]["source"], "app_store")

    def test_vendor_only_and_invalid_team(self):
        a = app(
            [ev("vendor_signature", team_id="TEAM", bundle_id="org.example.app")],
            bundle_id="org.example.app",
            team_id="TEAM",
            architectures=["arm64"],
        )
        r = self.resolve(a, recipes=self.recipe())
        self.assertEqual(
            (r["source"], r["evidence_grade"], r["capability"]),
            ("vendor", "probable", "reviewed_direct"),
        )
        a["team_id"] = "CHANGED"
        r = self.resolve(a, recipes=self.recipe())
        self.assertEqual((r["source"], r["capability"]), ("conflict", "inventory_only"))
        self.assertIn("recipe_identity_mismatch", r["reason_codes"])

    def test_unknown_feed_and_fake_apple_identity(self):
        a = app(
            [ev("info_plist", SUFeedURL="https://example.org/feed")],
            bundle_id="com.apple.fake",
        )
        self.assertEqual(
            (self.resolve(a)["source"], self.resolve(a)["capability"]),
            ("unknown", "check_only"),
        )
        a["evidence"].append(ev("framework", name="Sparkle"))
        self.assertEqual(self.resolve(a)["capability"], "check_only")
        a["evidence"].append(ev("protected_root"))
        a["path"] = "/System/Applications/Fake.app"
        self.assertEqual(self.resolve(a)["source"], "unknown")

    def test_mas_brew_stale_and_multiartifact(self):
        claims = [
            ev("app_store_receipt"),
            ev(
                "homebrew",
                token="renamed-cask",
                prefix="/opt/homebrew",
                artifact_path="/fixture/Applications/CapCut.app",
                installed_receipt=True,
                freshness="stale",
            ),
        ]
        r = self.resolve(app(claims))
        self.assertEqual((r["source"], r["capability"]), ("conflict", "inventory_only"))
        a = app(
            [
                ev(
                    "homebrew",
                    token="suite",
                    prefix="/opt/homebrew",
                    artifact_path="/fixture/Applications/Other.app",
                    installed_receipt=True,
                )
            ]
        )
        self.assertEqual(self.resolve(a)["source"], "unknown")
        a["evidence"].append(
            ev(
                "homebrew",
                token="suite",
                prefix="/opt/homebrew",
                artifact_path=a["real_path"],
                installed_receipt=True,
            )
        )
        self.assertEqual(self.resolve(a)["source"], "homebrew")
        a["evidence"].append(
            ev(
                "homebrew",
                token="other",
                prefix="/opt/homebrew",
                artifact_path=a["real_path"],
                installed_receipt=True,
            )
        )
        self.assertEqual(self.resolve(a)["source"], "conflict")

    def test_duplicates_testflight_and_mdm(self):
        a = app([ev("app_store_receipt")], bundle_id="same")
        b = app(
            [], path="/fixture/users/test/Applications/Example.app", bundle_id="same"
        )
        b["instance_id"] = "b"
        self.assertIn(
            "duplicate_bundle_id",
            self.resolve(a, {"instances": [a, b]})["reason_codes"],
        )
        a["channel"] = "testflight"
        self.assertEqual(self.resolve(a)["capability"], "inventory_only")
        self.assertEqual(
            self.resolve(app([ev("enterprise_managed")]))["source"],
            "enterprise_managed",
        )

    def test_package_prefix_and_weak_evidence(self):
        base = {
            "package_id": "p",
            "manager": "homebrew",
            "prefix": "/opt/homebrew",
            "source_identity": "tool",
            "installed_receipt": "/opt/homebrew/receipt",
            "presence": "present",
            "freshness": "fresh",
            "evidence": [
                ev(
                    "homebrew",
                    token="tool",
                    prefix="/opt/homebrew",
                    artifact_path=None,
                    installed_receipt="/opt/homebrew/receipt",
                )
            ],
        }
        self.assertEqual(
            (self.resolve(base)["source"], self.resolve(base)["capability"]),
            ("homebrew", "native_managed"),
        )
        base["related_instance_ids"] = ["app-one", "app-two"]
        self.assertNotEqual(self.resolve(base)["capability"], "reviewed_direct")
        base["prefix"] = "/usr/local"
        self.assertEqual(self.resolve(base)["source"], "unknown")
        base["prefix"] = "/opt/homebrew"
        base["installed_receipt"] = None
        self.assertEqual(self.resolve(base)["source"], "unknown")
        base["installed_receipt"] = "/opt/homebrew/receipt"
        for field, value in [
            ("freshness", "stale"),
            ("presence", "absent"),
            ("presence", "unobserved"),
        ]:
            trial = dict(base, **{field: value})
            self.assertEqual(self.resolve(trial)["capability"], "inventory_only")
        trial = dict(base, evidence=[dict(base["evidence"][0], status="partial")])
        self.assertEqual(self.resolve(trial)["capability"], "inventory_only")

    def test_real_legacy_catalog_is_capability_only(self):
        path = os.path.join(
            os.path.dirname(__file__), "..", "config", "internet_app_methods.txt"
        )
        entries = load_legacy_capabilities(path)
        self.assertEqual(len(entries), 47)
        self.assertTrue(all(set(row) == {"name", "adapter_id"} for row in entries))
        self.assertEqual(self.resolve(app())["source"], "unknown")

    def test_recipe_rejections_and_bound(self):
        recipe = self.recipe()["recipes"][0]
        invalid = [
            dict(recipe, command="touch evil"),
            dict(recipe, download_hosts=[{"command": "evil"}]),
            dict(recipe, adapter_id="arbitrary"),
            dict(recipe, adapter_id=[]),
        ]
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(ValueError):
                RecipeTests().load({"schema_version": 1, "recipes": [item]})
        with self.assertRaises(ValueError):
            RecipeTests().load({"schema_version": 2, "recipes": []})
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "large.json")
            with open(p, "w") as f:
                f.write(" " * (1024 * 1024 + 1))
            with self.assertRaises(ValueError):
                load_recipes(p)


class IntegrationContractTests(unittest.TestCase):
    def test_brew_package_subtypes_receipt_and_source_quality(self):
        for subtype in ("cask", "formula"):
            receipt = "/opt/homebrew/receipt.json"
            p = {
                "package_id": subtype,
                "manager": "homebrew",
                "prefix": "/opt/homebrew",
                "source_identity": subtype + ":token",
                "installed_receipt": receipt,
                "presence": "present",
                "freshness": "fresh",
                "source_status": "ok",
                "complete": True,
                "evidence": [
                    ev(
                        "homebrew",
                        token="token",
                        prefix="/opt/homebrew",
                        artifact_path=None,
                        installed_receipt=receipt,
                        source_status="ok",
                        complete=True,
                    )
                ],
            }
            r = resolve_target(p, {}, {"recipes": []})
            self.assertEqual(
                (r["source"], r["evidence_grade"]), ("homebrew", "confirmed")
            )
            p["evidence"][0]["installed_receipt"] = "/other/receipt"
            self.assertEqual(
                resolve_target(p, {}, {"recipes": []})["source"], "unknown"
            )
            p["evidence"][0]["installed_receipt"] = receipt
            p["evidence"][0]["source_status"] = "partial"
            r = resolve_target(p, {}, {"recipes": []})
            self.assertNotEqual(r["evidence_grade"], "confirmed")
            self.assertEqual(r["capability"], "inventory_only")
            p["evidence"][0]["source_status"] = "ok"
            p["evidence"][0]["source_complete"] = False
            r = resolve_target(p, {}, {"recipes": []})
            self.assertEqual(
                (r["evidence_grade"], r["capability"]), ("probable", "inventory_only")
            )

    def test_recipe_identity_mismatch_blocks_brew(self):
        recipe = AcceptanceTests().recipe()
        a = app(
            [
                ev(
                    "homebrew",
                    token="example",
                    prefix="/opt/homebrew",
                    artifact_path="/fixture/Applications/CapCut.app",
                    installed_receipt="/receipt",
                ),
                ev("vendor_signature", bundle_id="org.example.app", team_id="CHANGED"),
            ],
            bundle_id="org.example.app",
            team_id="CHANGED",
            architectures=["arm64"],
        )
        r = resolve_target(a, {"os_version": "14"}, recipe)
        self.assertEqual(
            (r["source"], r["capability"], r["evidence_grade"]),
            ("conflict", "inventory_only", "conflicting"),
        )
