"""Exercise recipe authority and actual fixture replacement without host tools."""

import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib/python"))
from test_recipe_acceptance import recipe, record, environment

try:
    import recipe_adapters as adapters
except ImportError:
    adapters = None


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(adapters, "recipe executor missing")
        self.r = recipe()
        self.r["acceptance_records"]["update"] = [record(self.r)]
        self.env = environment(self.r)
        self.target = dict(
            self.env["target"],
            real_path="/fixture/apps/Fixture.app",
            version="1.0",
            build="100",
            running=False,
            freshness="fresh",
        )

    def prepare(self, operation="update"):
        return adapters.prepare_recipe_action(self.r, self.target, operation, self.env)

    def test_no_public_recipe_or_fixture_record_promotes(self):
        self.r["acceptance_records"]["update"] = [record(self.r, kind="fixture")]
        self.assertFalse(self.prepare()["allowed"])

    def test_exact_candidate_and_consent_are_bound(self):
        action = self.prepare()
        self.assertTrue(action["allowed"], action)
        self.assertEqual(action["candidate"]["version"], "2.0")
        self.r["candidate"]["build"] = "201"
        self.assertFalse(self.prepare()["allowed"])

    def test_unknown_adapter_and_latest_native_never_fall_back(self):
        self.r["adapter_id"] = "unknown-shell"
        self.assertFalse(self.prepare()["allowed"])

    def test_update_never_installs_and_requires_closed_target(self):
        for change in [dict(presence="absent"), dict(running=True), dict(running=None)]:
            target = copy.deepcopy(self.target)
            target.update(change)
            self.assertFalse(
                adapters.prepare_recipe_action(self.r, target, "update", self.env)[
                    "allowed"
                ]
            )
        self.assertFalse(self.prepare("install")["allowed"])

    def test_downgrade_or_same_version_build_rejected_without_comparator(self):
        for v, b in [("3.0", "300"), ("2.0", "100")]:
            self.target.update(version=v, build=b)
            self.assertFalse(self.prepare()["allowed"])

    def test_guard_rechecked_after_acquisition_and_no_launch(self):
        action = self.prepare()
        action["action_id"] = "action-test"

        class Observer:
            def authorize(self):
                return False

        with tempfile.TemporaryDirectory() as root:
            with patch.object(
                adapters,
                "acquire_candidate",
                side_effect=AssertionError("not authorized"),
            ):
                result = adapters.execute_recipe_action(action, Observer(), root)
        self.assertFalse(result["verified"])
        self.assertEqual(result["reason_code"], "authorization_deferred")


if __name__ == "__main__":
    unittest.main()


class DirectFixtureSwapTests(unittest.TestCase):
    def test_accepted_update_swaps_only_existing_bundle_and_observes_build(self):
        import hashlib, io, plistlib, zipfile
        import update_transaction

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            apps = root / "apps"
            apps.mkdir()
            dest = apps / "Fixture.app"
            (dest / "Contents").mkdir(parents=True)

            def plist(v, b):
                return plistlib.dumps(
                    dict(
                        CFBundleIdentifier="org.example.fixture",
                        CFBundleShortVersionString=v,
                        CFBundleVersion=b,
                    )
                )

            (dest / "Contents/Info.plist").write_bytes(plist("1.0", "100"))
            r = recipe()
            r["candidate"]["build"] = "200"
            payload = io.BytesIO()
            with zipfile.ZipFile(payload, "w") as z:
                z.writestr("Fixture.app/Contents/Info.plist", plist("2.0", "200"))
            raw = payload.getvalue()
            r["candidate"]["sha256"] = hashlib.sha256(raw).hexdigest()
            r["acceptance_records"]["update"] = [record(r)]
            env = environment(r)
            target = dict(
                env["target"],
                real_path=str(dest),
                path=str(dest),
                version="1.0",
                build="100",
                running=False,
                freshness="fresh",
            )
            action = adapters.prepare_recipe_action(r, target, "update", env)
            self.assertTrue(action["allowed"], action)

            class Observer:
                allowed_roots = [str(apps)]
                transaction_action = dict(
                    action_id="fixture",
                    target={"kind": "app", "id": "fixture"},
                    target_path=str(dest),
                    action_scope="direct_update",
                    adapter_id="github_dmg",
                    expected_target=dict(
                        bundle_id=r["candidate"]["bundle_id"],
                        team_id=r["candidate"]["team_id"],
                        channel="stable",
                    ),
                )

                def authorize(self):
                    return True

                def current(self):
                    return dict(target, short_version="1.0")

                def observe_bundle(self, path):
                    info = plistlib.loads(
                        Path(path, "Contents/Info.plist").read_bytes()
                    )
                    return dict(
                        good=True,
                        exists=True,
                        receipt_present=False,
                        running=False,
                        bundle_id=info["CFBundleIdentifier"],
                        team_id=r["candidate"]["team_id"],
                        version=info["CFBundleShortVersionString"],
                        build=info["CFBundleVersion"],
                        architectures=["arm64"],
                        minimum_os="13.0",
                        host_os="15.1",
                    )

            journals = root / "transactions"
            journals.mkdir(mode=0o700)

            def download(url, path, **kwargs):
                Path(path).write_bytes(raw)

            with (
                patch("artifact_acquisition.download", download),
                patch.object(
                    update_transaction, "sys_platform_darwin", return_value=False
                ),
            ):
                result = adapters.execute_recipe_action(
                    action, Observer(), str(journals)
                )
            self.assertTrue(result["verified"], result)
            self.assertEqual(
                plistlib.loads((dest / "Contents/Info.plist").read_bytes())[
                    "CFBundleVersion"
                ],
                "200",
            )
            self.assertTrue(list(apps.glob(".macupd-backup-*/*/Contents/Info.plist")))
