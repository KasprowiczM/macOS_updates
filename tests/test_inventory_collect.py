import os
import plistlib
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib", "python"))
from inventory_collect import Providers, collect_snapshot, source_result
from inventory_model import validate_snapshot


class CollectorTests(unittest.TestCase):
    def test_total_directory_budget_marks_coverage_partial(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as root:
            for parent in ("one", "two"):
                for child in ("a", "b"):
                    os.makedirs(os.path.join(root, parent, child))
            with patch("inventory_collect.MAX_ENTRIES", 3):
                result = collect_snapshot([root], Providers(), None)
            source = result["sources"]["filesystem:" + os.path.realpath(root)]
            self.assertEqual(source["status"], "partial")
            self.assertFalse(source["complete"])

    def test_reconcile_and_partial(self):
        with tempfile.TemporaryDirectory() as root:
            app = os.path.join(root, "Agent", "Thing.app")
            os.makedirs(os.path.join(app, "Contents", "_MASReceipt"))
            with open(os.path.join(app, "Contents", "Info.plist"), "wb") as f:
                plistlib.dump(
                    {
                        "CFBundleIdentifier": "org.example.thing",
                        "CFBundleName": "Thing",
                    },
                    f,
                )
            open(os.path.join(app, "Contents", "_MASReceipt", "receipt"), "wb").close()
            p = Providers(
                list_mas=lambda: source_result("unavailable", reason_code="missing")
            )
            first = collect_snapshot([root], p, None)
            validate_snapshot(first)
            self.assertEqual(first["instances"][0]["presence"], "present")
            self.assertIn(
                "app_store_receipt",
                [e["kind"] for e in first["instances"][0]["evidence"]],
            )
            second = collect_snapshot([root], p, first)
            self.assertEqual(
                first["instances"][0]["instance_id"],
                second["instances"][0]["instance_id"],
            )
            os.rename(app, app + ".gone")
            third = collect_snapshot([root], p, second)
            self.assertEqual(third["instances"][0]["presence"], "absent")

    def test_packages_scoped_and_partial_preserves(self):
        with tempfile.TemporaryDirectory() as root:

            def listing(prefix):
                return source_result(
                    "ok",
                    [
                        {
                            "name": "tool",
                            "version": "1",
                            "installed_receipt": prefix + "/receipt",
                        }
                    ],
                )

            p = Providers(list_cli=listing, cli_prefixes=[root + "/a", root + "/b"])
            first = collect_snapshot([], p, None)
            self.assertEqual(len(first["packages"]), 2)
            p.list_cli = lambda prefix: source_result("partial", reason_code="timeout")
            second = collect_snapshot([], p, first)
            self.assertTrue(
                all(
                    x["presence"] == "unobserved" and x["freshness"] == "stale"
                    for x in second["packages"]
                )
            )

    def test_invalid_plist_retains_receipt_and_blocks_absence(self):
        with tempfile.TemporaryDirectory() as root:
            app = os.path.join(root, "A.app")
            os.makedirs(os.path.join(app, "Contents", "_MASReceipt"))
            with open(os.path.join(app, "Contents", "Info.plist"), "wb") as f:
                f.write(b"bad plist")
            open(os.path.join(app, "Contents", "_MASReceipt", "receipt"), "wb").close()
            snapshot = collect_snapshot([root], Providers(), None)
            self.assertEqual(
                snapshot["sources"]["filesystem:" + os.path.realpath(root)]["status"],
                "partial",
            )
            self.assertEqual(
                snapshot["instances"][0]["evidence"][0]["kind"], "app_store_receipt"
            )

    def test_symlink_escape_makes_coverage_partial(self):
        with (
            tempfile.TemporaryDirectory() as root,
            tempfile.TemporaryDirectory() as outside,
        ):
            os.symlink(outside, os.path.join(root, "Link.app"))
            snap = collect_snapshot([root], Providers(), None)
            self.assertEqual(snap["instances"], [])
            self.assertEqual(
                snap["sources"]["filesystem:" + os.path.realpath(root)]["status"],
                "partial",
            )

    def test_distinct_copies_and_identity_change(self):
        with tempfile.TemporaryDirectory() as root:

            def app(name, bundle):
                path = os.path.join(root, name + ".app", "Contents")
                os.makedirs(path)
                with open(os.path.join(path, "Info.plist"), "wb") as f:
                    plistlib.dump(
                        {"CFBundleIdentifier": bundle, "CFBundleName": name}, f
                    )
                return path

            paths = [
                app("ChatGPT", "com.example.chat"),
                app("Copy", "com.example.chat"),
                app("Codex", "com.example.codex"),
                app("Beta", "com.example.beta"),
            ]
            first = collect_snapshot([root], Providers(), None)
            self.assertEqual(len({x["instance_id"] for x in first["instances"]}), 4)
            ids = {x["path"]: x["instance_id"] for x in first["instances"]}
            with open(os.path.join(paths[0], "Info.plist"), "wb") as f:
                plistlib.dump({"CFBundleIdentifier": "new.identity"}, f)
            second = collect_snapshot([root], Providers(), first)
            new = {x["path"]: x["instance_id"] for x in second["instances"]}
            for path in new:
                if path.endswith("ChatGPT.app"):
                    self.assertNotEqual(ids[path], new[path])
                else:
                    self.assertEqual(ids[path], new[path])

    def test_fifo_and_metadata_bound(self):
        with tempfile.TemporaryDirectory() as root:
            for name in ("fifo", "large"):
                os.makedirs(os.path.join(root, name + ".app", "Contents"))
            os.mkfifo(os.path.join(root, "fifo.app", "Contents", "Info.plist"))
            with open(
                os.path.join(root, "large.app", "Contents", "Info.plist"), "wb"
            ) as f:
                f.write(b"x" * (1024 * 1024 + 1))
            result = collect_snapshot([root], Providers(), None)
            self.assertEqual(len(result["instances"]), 2)
            self.assertEqual(
                result["sources"]["filesystem:" + os.path.realpath(root)]["status"],
                "partial",
            )

    def test_source_scoped_absence(self):
        with tempfile.TemporaryDirectory() as root:
            a, b = root + "/a", root + "/b"
            p = Providers(
                list_cli=lambda prefix: source_result(
                    "ok",
                    [
                        {
                            "name": "tool",
                            "manager": "npm",
                            "installed_receipt": prefix + "/receipt",
                        }
                    ],
                ),
                cli_prefixes=[a, b],
            )
            first = collect_snapshot([], p, None)
            p.list_cli = lambda prefix: (
                source_result("ok")
                if prefix == os.path.realpath(a)
                else source_result("error", reason_code="timeout")
            )
            second = collect_snapshot([], p, first)
            result = {
                x["prefix"]: (x["presence"], x["freshness"]) for x in second["packages"]
            }
            self.assertEqual(result[os.path.realpath(a)], ("absent", "fresh"))
            self.assertEqual(result[os.path.realpath(b)], ("unobserved", "stale"))

    def test_validate_rejects_bad_source_and_duplicate_id(self):
        import copy

        with tempfile.TemporaryDirectory() as root:
            p = Providers(
                list_cli=lambda prefix: source_result(
                    "ok", [{"name": "one"}, {"name": "two"}]
                ),
                cli_prefixes=[root],
            )
            snap = collect_snapshot([], p, None)
            for mutate in (
                lambda x: x["sources"]["mas"].update(status="error", complete=True),
                lambda x: x["sources"]["mas"].update(items=["bad"]),
                lambda x: x["packages"][1].update(
                    package_id=x["packages"][0]["package_id"]
                ),
            ):
                bad = copy.deepcopy(snap)
                mutate(bad)
                with self.assertRaises(ValueError):
                    validate_snapshot(bad)

    def test_depth_unknown_names_and_permission(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as root:
            for sub in ("a/b/c/Unicode | Ω.app", "a/b/c/d/TooDeep.app", "NoID.app"):
                contents = os.path.join(root, sub, "Contents")
                os.makedirs(contents)
                with open(os.path.join(contents, "Info.plist"), "wb") as f:
                    plistlib.dump({"CFBundleName": sub}, f)
            snapshot = collect_snapshot([root], Providers(), None)
            self.assertEqual(len(snapshot["instances"]), 2)
            self.assertTrue(all(x["bundle_id"] is None for x in snapshot["instances"]))
            with patch("inventory_collect.os.scandir", side_effect=PermissionError()):
                second = collect_snapshot([root], Providers(), snapshot)
            self.assertTrue(
                all(x["presence"] == "unobserved" for x in second["instances"])
            )

    def test_record_limit_and_loop(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as root:
            for name in ("one", "two"):
                contents = os.path.join(root, name + ".app", "Contents")
                os.makedirs(contents)
                with open(os.path.join(contents, "Info.plist"), "wb") as f:
                    plistlib.dump({}, f)
            os.symlink(root, os.path.join(root, "loop"))
            with patch("inventory_collect.MAX_RECORDS", 1):
                snapshot = collect_snapshot([root], Providers(), None)
            self.assertEqual(len(snapshot["instances"]), 1)
            self.assertEqual(
                snapshot["sources"]["filesystem:" + os.path.realpath(root)]["status"],
                "partial",
            )

    def test_bad_provider_results_are_errors(self):
        for result in (
            {"status": "ok"},
            source_result("error", complete=True),
            source_result("ok", ["invalid"]),
        ):
            with self.subTest(result=result):
                snap = collect_snapshot([], Providers(list_mas=lambda: result), None)
                self.assertEqual(snap["sources"]["mas"]["status"], "error")
                validate_snapshot(snap)

    def test_overlapping_roots_depth_and_partial_metadata(self):
        with tempfile.TemporaryDirectory() as root:
            contents = os.path.join(root, "sub", "A.app", "Contents")
            os.makedirs(contents)
            with open(os.path.join(contents, "Info.plist"), "wb") as f:
                plistlib.dump({"CFBundleIdentifier": "a"}, f)
            first = collect_snapshot(
                [root, os.path.join(root, "sub")], Providers(), None
            )
            self.assertEqual(len(first["instances"]), 1)
            with open(os.path.join(contents, "Info.plist"), "wb") as f:
                f.write(b"broken")
            second = collect_snapshot([root], Providers(), first)
            self.assertEqual(second["instances"][0]["freshness"], "stale")
            self.assertNotIn(
                "homebrew", [e["kind"] for e in second["instances"][0]["evidence"]]
            )

    def test_partial_package_and_unambiguous_mas(self):
        with tempfile.TemporaryDirectory() as root:
            contents = os.path.join(root, "A.app", "Contents")
            os.makedirs(contents)
            with open(os.path.join(contents, "Info.plist"), "wb") as f:
                plistlib.dump({"CFBundleIdentifier": "org.example.a"}, f)
            p = Providers(
                list_mas=lambda: source_result(
                    "ok", [{"store_id": "123", "bundle_id": "org.example.a"}]
                ),
                list_cli=lambda prefix: source_result(
                    "partial",
                    [
                        {
                            "name": "a",
                            "manager": "npm",
                            "installed_receipt": "/receipt",
                            "evidence": [{"kind": "npm"}],
                        }
                    ],
                ),
                cli_prefixes=[root],
            )
            snap = collect_snapshot([root], p, None)
            self.assertEqual(snap["packages"][0]["freshness"], "stale")
            self.assertFalse(snap["packages"][0]["evidence"][0]["source_complete"])
            self.assertEqual(
                [x["kind"] for x in snap["instances"][0]["evidence"]].count("mas"), 1
            )

    def test_invalid_schema_types(self):
        import copy

        snap = collect_snapshot([], Providers(), None)
        for key, value in [("schema_version", True), ("created_at", "yesterday")]:
            bad = copy.deepcopy(snap)
            bad[key] = value
            with self.assertRaises(ValueError):
                validate_snapshot(bad)

    def test_framework_markers_do_not_expose_feed_url(self):
        with tempfile.TemporaryDirectory() as root:
            for name in ("Agent", "Copy"):
                contents = os.path.join(root, name + ".app", "Contents")
                os.makedirs(contents)
                with open(os.path.join(contents, "Info.plist"), "wb") as f:
                    plistlib.dump(
                        {
                            "CFBundleIdentifier": "org.example.same",
                            "SUFeedURL": "https://user:secret@example.invalid/feed",
                        },
                        f,
                    )
            snap = collect_snapshot([root], Providers(), None)
            self.assertEqual(len(snap["instances"]), 2)
            self.assertTrue(
                all(
                    any(e.get("name") == "sparkle" for e in x["evidence"])
                    for x in snap["instances"]
                )
            )
            self.assertNotIn("secret", repr(snap))
            self.assertNotIn("example.invalid", repr(snap))

    def test_unreceipted_file_observation_keeps_identity(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "node")
            with open(path, "w") as f:
                f.write("synthetic")
            p = Providers(
                list_cli=lambda prefix: source_result(
                    "ok",
                    [
                        {
                            "name": "node",
                            "manager": "unknown",
                            "source_identity": "node",
                            "evidence": [{"kind": "file_metadata", "path": path}],
                        }
                    ],
                ),
                cli_prefixes=[root],
            )
            first = collect_snapshot([], p, None)
            second = collect_snapshot([], p, first)
            self.assertEqual(len(second["packages"]), 1)
            self.assertEqual(
                first["packages"][0]["package_id"], second["packages"][0]["package_id"]
            )
            p.list_cli = lambda prefix: source_result(
                "partial", reason_code="permission_denied"
            )
            third = collect_snapshot([], p, second)
            self.assertEqual(third["packages"][0]["presence"], "unobserved")
            self.assertEqual(third["packages"][0]["freshness"], "stale")

    def test_incomplete_brew_preserves_conflicting_evidence(self):
        from source_resolver import resolve_target

        with tempfile.TemporaryDirectory() as root:
            app = os.path.realpath(os.path.join(root, "A.app"))
            contents = os.path.join(app, "Contents")
            os.makedirs(os.path.join(contents, "_MASReceipt"))
            with open(os.path.join(contents, "Info.plist"), "wb") as f:
                plistlib.dump({"CFBundleIdentifier": "org.test.a"}, f)
            open(os.path.join(contents, "_MASReceipt", "receipt"), "wb").close()
            p = Providers(
                brew_prefixes=[root],
                list_brew=lambda prefix: source_result(
                    "ok",
                    [
                        {
                            "name": "a",
                            "manager": "homebrew",
                            "installed_receipt": "/receipt",
                            "evidence": [
                                {
                                    "kind": "homebrew",
                                    "token": "a",
                                    "prefix": prefix,
                                    "artifact_path": app,
                                    "installed_receipt": "/receipt",
                                }
                            ],
                        }
                    ],
                ),
            )
            first = collect_snapshot([root], p, None)
            p.list_brew = lambda prefix: source_result("error", reason_code="timeout")
            second = collect_snapshot([root], p, first)
            result = resolve_target(second["instances"][0], second, {"recipes": []})
            self.assertEqual(result["source"], "conflict")
            self.assertIn("target_or_evidence_incomplete", result["reason_codes"])

    def test_alias_cannot_make_canonical_app_absent(self):
        with tempfile.TemporaryDirectory() as root:
            contents = os.path.join(root, "z", "A.app", "Contents")
            os.makedirs(contents)
            with open(os.path.join(contents, "Info.plist"), "wb") as f:
                plistlib.dump({}, f)
            first = collect_snapshot([root], Providers(), None)
            os.symlink(os.path.join(root, "z"), os.path.join(root, "a"))
            second = collect_snapshot([root], Providers(), first)
            old = next(
                x
                for x in second["instances"]
                if x["instance_id"] == first["instances"][0]["instance_id"]
            )
            self.assertEqual(old["presence"], "present")

    def test_stale_ownership_clears_after_complete_source(self):
        with tempfile.TemporaryDirectory() as root:
            app = os.path.realpath(os.path.join(root, "A.app"))
            contents = os.path.join(app, "Contents")
            os.makedirs(contents)
            with open(os.path.join(contents, "Info.plist"), "wb") as f:
                plistlib.dump({"CFBundleIdentifier": "a"}, f)
            p = Providers(
                brew_prefixes=[root],
                list_brew=lambda prefix: source_result(
                    "ok",
                    [
                        {
                            "name": "a",
                            "installed_receipt": "/r",
                            "evidence": [
                                {
                                    "kind": "homebrew",
                                    "token": "a",
                                    "prefix": prefix,
                                    "artifact_path": app,
                                    "installed_receipt": "/r",
                                }
                            ],
                        }
                    ],
                ),
                list_mas=lambda: source_result(
                    "ok", [{"bundle_id": "a", "store_id": "1"}]
                ),
            )
            first = collect_snapshot([root], p, None)
            p.list_brew = lambda prefix: source_result("partial")
            p.list_mas = lambda: source_result("unavailable", reason_code="missing")
            second = collect_snapshot([root], p, first)
            self.assertEqual(
                {e["kind"] for e in second["instances"][0]["evidence"]}
                & {"mas", "homebrew"},
                {"mas", "homebrew"},
            )
            self.assertTrue(
                all(
                    e.get("freshness") == "stale"
                    for e in second["instances"][0]["evidence"]
                    if e["kind"] in ("mas", "homebrew")
                )
            )
            p.list_brew = lambda prefix: source_result("ok")
            p.list_mas = lambda: source_result("ok")
            third = collect_snapshot([root], p, second)
            self.assertFalse(
                any(
                    e["kind"] in ("mas", "homebrew")
                    for e in third["instances"][0]["evidence"]
                )
            )

    def test_large_metadata_is_not_retained(self):
        with tempfile.TemporaryDirectory() as root:
            contents = os.path.join(root, "A.app", "Contents")
            os.makedirs(contents)
            with open(os.path.join(contents, "Info.plist"), "wb") as f:
                plistlib.dump({"CFBundleName": "x" * 10000}, f)
            snap = collect_snapshot([root], Providers(), None)
            self.assertIsNone(snap["instances"][0]["name"])
            self.assertEqual(snap["instances"][0]["freshness"], "stale")

class PackageVersionIdentityTests(unittest.TestCase):
    def test_verified_versioned_receipt_keeps_uuid_but_ambiguous_replacement_does_not(self):
        with tempfile.TemporaryDirectory() as root:
            root = os.path.realpath(root)
            def record(version, token='tool'):
                receipt = root + '/Cellar/' + token + '/' + version + '/INSTALL_RECEIPT.json'
                return dict(manager='homebrew', name='same display name', source_identity='formula:' + token,
                            version=version, installed_receipt=receipt, channel='stable',
                            evidence=[dict(kind='homebrew', prefix=root, token=token, installed_receipt=receipt)])
            items = [record('1')]
            p = Providers(list_brew=lambda prefix: source_result('ok', items), brew_prefixes=[root])
            first = collect_snapshot([], p, None)
            items[:] = [record('2')]
            second = collect_snapshot([], p, first)
            self.assertEqual(len(second['packages']), 1)
            self.assertEqual(first['packages'][0]['package_id'], second['packages'][0]['package_id'])
            items[:] = [record('3'), record('4')]
            ambiguous = collect_snapshot([], p, second)
            self.assertNotIn(second['packages'][0]['package_id'], [x['package_id'] for x in ambiguous['packages'] if x['presence'] == 'present'])
            items[:] = [record('2', 'other')]
            other = collect_snapshot([], p, second)
            self.assertNotEqual(second['packages'][0]['package_id'], other['packages'][0]['package_id'])

    def test_pure_reconcile_distinguishes_empty_and_unknown(self):
        from inventory_collect import reconcile_inventory
        with tempfile.TemporaryDirectory() as root:
            root = os.path.realpath(root)
            receipt = root + '/Cellar/tool/1/INSTALL_RECEIPT.json'
            item = dict(manager='homebrew', source_identity='formula:tool', installed_receipt=receipt,
                        evidence=[dict(kind='homebrew', prefix=root, token='tool', installed_receipt=receipt)])
            first = collect_snapshot([], Providers(list_brew=lambda p: source_result('ok', [item]), brew_prefixes=[root]), None)
            for status, presence in [('partial', 'unobserved'), ('ok', 'absent')]:
                fresh = collect_snapshot([], Providers(list_brew=lambda p: source_result(status), brew_prefixes=[root]), None)
                fresh.update(profile_id=first['profile_id'], generation=first['generation'], previous_snapshot_id=first['snapshot_id'])
                reconciled = reconcile_inventory(first, fresh)
                self.assertEqual(reconciled['packages'][0]['presence'], presence)
                self.assertEqual(reconciled['packages'][0]['package_id'], first['packages'][0]['package_id'])
