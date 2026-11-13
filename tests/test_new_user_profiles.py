"""Deny-by-default fixture profiles; none observe native host apps or execute tools."""

import copy
import json
import plistlib
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib/python"))
from inventory_collect import Providers, collect_snapshot, source_result
from inventory_model import validate_snapshot
from coverage_report import build_coverage_report
from source_resolver import resolve_snapshot
from update_plan import build_plan, authorize_action

FIXTURES = Path(__file__).parent / "fixtures/new_user/profiles"
RECIPES = dict(schema_version=1, recipes=[])


class NewUserProfileTests(unittest.TestCase):
    def exercise(self, profile):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            apps = root / "Applications"
            apps.mkdir()
            prefix = str(root / "brew")
            brew_items = []
            info_overrides = {}
            for spec in profile["apps"]:
                app = apps / spec.get("folder", "") / (spec["name"] + ".app")
                contents = app / "Contents"
                contents.mkdir(parents=True)
                info = dict(
                    CFBundleIdentifier=spec["bundle"],
                    CFBundleName=spec["name"],
                    CFBundleShortVersionString="1.0",
                )
                if spec.get("framework") == "sparkle":
                    info["SUFeedURL"] = (
                        "https://account:password@private.example/feed?token=SECRET"
                    )
                (contents / "Info.plist").write_bytes(
                    b"not plist" if spec.get("bad_plist") else plistlib.dumps(info)
                )
                if spec.get("receipt"):
                    (contents / "_MASReceipt").mkdir()
                    (contents / "_MASReceipt/receipt").write_bytes(
                        b"private fixture receipt"
                    )
                if spec.get("framework") == "electron":
                    (contents / "Resources").mkdir()
                    (contents / "Resources/app-update.yml").write_text(
                        "provider: generic\nurl: https://user:secret@private.example/?token=SECRET\n"
                    )
                for signal, framework in [
                    ("squirrel", "Squirrel"),
                    ("sparkle_no_feed", "Sparkle"),
                ]:
                    if spec.get("framework") == signal:
                        (contents / "Frameworks" / (framework + ".framework")).mkdir(
                            parents=True
                        )
                info_overrides[str(app)] = spec
                if spec.get("brew"):
                    receipt = prefix + "/Cellar/tool/1/INSTALL_RECEIPT.json"
                    evidence = [
                        dict(
                            kind="homebrew",
                            token="tool",
                            prefix=prefix,
                            installed_receipt=receipt,
                            artifact_path=str(app),
                        )
                    ]
                    if profile.get("missing_artifact"):
                        evidence.append(
                            dict(
                                kind="homebrew",
                                token="tool",
                                prefix=prefix,
                                installed_receipt=receipt,
                                artifact_path=str(apps / "Absent.app"),
                            )
                        )
                    brew_items.append(
                        dict(
                            manager="homebrew",
                            source_identity="formula:tool",
                            installed_receipt=receipt,
                            version="1",
                            evidence=evidence,
                        )
                    )
            if profile.get("opaque_package"):
                brew_items.append(
                    dict(
                        manager="homebrew",
                        source_identity="formula:driver",
                        installed_receipt=prefix
                        + "/Cellar/driver/1/INSTALL_RECEIPT.json",
                        evidence=[],
                    )
                )
            if profile.get("symlink_escape"):
                outside = root / "Outside.app"
                outside.mkdir()
                (apps / "Escape.app").symlink_to(outside)
            from inventory_collect import read_bundle_static

            def read_bundle(path):
                result = read_bundle_static(path)
                spec = info_overrides[path]
                if result["items"]:
                    result["items"][0]["channel"] = spec.get("channel", "unknown")
                    if spec.get("enterprise"):
                        result["items"][0]["evidence"].append(
                            dict(kind="enterprise_managed")
                        )
                return result

            providers = Providers(
                read_bundle=read_bundle,
                list_mas=lambda: source_result(
                    profile.get("mas_status", "unavailable")
                ),
                list_brew=lambda p: source_result("ok", brew_items),
                brew_prefixes=[prefix],
            )
            with (
                patch(
                    "subprocess.run", side_effect=AssertionError("unexpected command")
                ) as commands,
                patch(
                    "socket.create_connection",
                    side_effect=AssertionError("network denied"),
                ),
                patch(
                    "urllib.request.urlopen",
                    side_effect=AssertionError("network denied"),
                ),
            ):
                snapshot = validate_snapshot(
                    collect_snapshot([str(apps)], providers, None)
                )
                if profile.get("empty_manager") or profile.get("partial_manager"):
                    old = collect_snapshot(
                        [str(apps)],
                        Providers(
                            list_brew=lambda p: source_result(
                                "ok",
                                [
                                    dict(
                                        manager="homebrew",
                                        source_identity="formula:tool",
                                        installed_receipt=prefix + "/receipt",
                                        evidence=[],
                                    )
                                ],
                            ),
                            brew_prefixes=[prefix],
                        ),
                        None,
                    )
                    providers.list_brew = lambda p: source_result(
                        "partial" if profile.get("partial_manager") else "ok"
                    )
                    snapshot = collect_snapshot([str(apps)], providers, old)
                    package = snapshot["packages"][0]
                    self.assertEqual(
                        package["presence"],
                        "unobserved" if profile.get("partial_manager") else "absent",
                    )
                resolutions = resolve_snapshot(snapshot, RECIPES)
                report = build_coverage_report(snapshot, RECIPES, [])
                policies = dict(
                    schema_version=1,
                    profile_id=snapshot["profile_id"],
                    revision=0,
                    decisions=[],
                )
                plan = build_plan(
                    snapshot, resolutions, policies, snapshot["created_at"]
                )
                self.assertEqual(
                    report["installed_unique_count"],
                    profile.get("expected_instances", len(profile["apps"])),
                )
                self.assertEqual(
                    sorted(
                        r["source"] for r in resolutions if r["target"]["kind"] == "app"
                    ),
                    sorted(profile["expected_sources"]),
                )
                self.assertEqual(report["errors"], [])
                self.assertNotIn("SECRET", json.dumps(report))
                if "expected_possible" in profile:
                    self.assertEqual(
                        report["possible_updater_count"], profile["expected_possible"]
                    )
                targets = {
                    r.get("instance_id") or r.get("package_id"): r
                    for r in snapshot["instances"] + snapshot["packages"]
                }
                resolution_map = {r["target"]["id"]: r for r in resolutions}
                for action in plan["actions"]:
                    current = dict(
                        copy.deepcopy(targets[action["target"]["id"]]),
                        resolution=resolution_map[action["target"]["id"]],
                        running=profile.get("running", False),
                    )
                    if profile.get("removed_after_plan"):
                        current["presence"] = "absent"
                    if profile.get("changed_team"):
                        current["team_id"] = "CHANGED123"
                    self.assertFalse(
                        authorize_action(
                            action, current, policies, snapshot["created_at"]
                        )["allowed"]
                    )
                self.assertEqual(
                    commands.call_count, profile["expected_unexpected_commands"]
                )
                self.assertEqual(profile["allowed_commands"], [])
                self.assertEqual(profile["expected_effects"], [])

    def test_profile_fixture_contracts(self):
        profiles = sorted(FIXTURES.glob("*.json"))
        self.assertGreaterEqual(len(profiles), 25)
        for path in profiles:
            with self.subTest(profile=path.stem):
                profile = json.loads(path.read_text())
                self.assertEqual(profile["schema_version"], 1)
                self.exercise(profile)

    def test_one_hundred_offline_bundles_within_five_seconds(self):
        profile = dict(
            apps=[
                dict(
                    name="Offline Agent " + str(n), bundle="org.example.agent" + str(n)
                )
                for n in range(100)
            ],
            expected_sources=["unknown"] * 100,
            allowed_commands=[],
            expected_effects=[],
            expected_unexpected_commands=0,
        )
        started = time.monotonic()
        self.exercise(profile)
        self.assertLess(time.monotonic() - started, 5.0)
