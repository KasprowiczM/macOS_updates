"""Synthetic ZIP first-install bridge. Native tools and network stay guarded."""

import datetime
import hashlib
import io
from pathlib import Path
import plistlib
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib" / "python"))
import setup_catalog
import install_execution as execution
from install_plan import build_install_plan
from policy_runtime import utc_now
from recipe_acceptance import (
    recipe_fingerprint,
    candidate_binding,
    requirements_fingerprint,
)
from update_scheduler import claim_action_resources, pending_sessions
from test_recipe_acceptance import recipe, record


class VerifiedInstallFixture:
    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.apps = self.root / "Applications"
        self.apps.mkdir()
        self.state = self.root / "state"
        self.state.mkdir(mode=0o700)
        self.destination = self.apps / "Fixture.app"
        self.environment = dict(os_version="15.1", architecture="arm64")
        self.snapshot = dict(environment=self.environment, instances=[], packages=[])
        self.r = recipe()
        self.r.update(edition="gui", matrix_ids=["fixture-gui"])
        self.r["candidate"].update(edition="gui", bundle_name="Fixture.app")
        self.r["requirement_graph"] = dict(nodes=[], edges=[])
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w") as archive:
            archive.writestr(
                "Fixture.app/Contents/Info.plist",
                plistlib.dumps(
                    dict(
                        CFBundleIdentifier="org.example.fixture",
                        CFBundleShortVersionString="2.0",
                        CFBundleVersion="200",
                        LSMinimumSystemVersion="13.0",
                    )
                ),
            )
        self.payload = payload.getvalue()
        self.r["candidate"]["sha256"] = hashlib.sha256(self.payload).hexdigest()
        self.recorded_at = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.r["acceptance_records"]["install"] = [
            record(
                self.r,
                operation="install",
                permissions=[],
                recorded_at=self.recorded_at,
            )
        ]
        self.catalog = dict(
            recipes=[
                dict(
                    id="fixture-gui",
                    product_id="fixture-gui",
                    name="Fixture Editor",
                    edition="gui",
                    sources=[
                        dict(
                            source_id="vendor",
                            official_url="https://downloads.example.org/",
                            architectures=["arm64"],
                        )
                    ],
                    architectures=[],
                    minimum_os=None,
                    channel="unknown",
                    install_adapter=None,
                    first_install_acceptance=None,
                    requirements_known=False,
                    requirements=[],
                )
            ],
            requirements={},
        )
        return self

    def __exit__(self, *args):
        self.temp.cleanup()

    def attach(self):
        self.catalog = setup_catalog.attach_verified_install_recipes(
            self.catalog,
            dict(
                schema_version=2,
                metadata=dict(
                    status="evidence_required",
                    matrix_ids=["fixture-gui"],
                    excluded_products=["DeepSeek"],
                ),
                recipes=[self.r],
            ),
            applications_root=str(self.apps),
        )
        return self.catalog

    def plan(self):
        self.plan_value = build_install_plan(
            [dict(product_id="fixture-gui", source_id="vendor", edition="gui")],
            self.snapshot,
            self.catalog,
            utc_now(),
        )
        self.action = self.plan_value["actions"][0]
        self.consent = execution.make_install_consent(
            self.plan_value, [self.action["action_id"]], utc_now()
        )
        return self.plan_value

    def observe(self, path):
        path = Path(path)
        info = plistlib.loads((path / "Contents/Info.plist").read_bytes())
        return dict(
            exists=True,
            good=True,
            receipt_present=False,
            running=False,
            bundle_id=info["CFBundleIdentifier"],
            team_id="EXAMPL1234",
            version=info["CFBundleShortVersionString"],
            build=info["CFBundleVersion"],
            architectures=["arm64"],
            minimum_os=info["LSMinimumSystemVersion"],
            host_os="15.1",
        )

    def download(self, url, destination, **kwargs):
        Path(destination).write_bytes(self.payload)

    def run(self, **extra):
        with patch("artifact_acquisition.download", self.download):
            return execution.execute_install_action(
                self.plan_value,
                self.action["action_id"],
                self.consent,
                self.catalog,
                self.environment,
                snapshot=self.snapshot,
                observe=self.observe,
                state_dir=str(self.state),
                allowed_roots=[str(self.apps)],
                snapshot_writer=lambda a, o: dict(
                    snapshot_id="synthetic-snapshot",
                    verified_path=str(self.destination),
                ),
                **extra,
            )


class VerifiedInstallTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(
            callable(getattr(setup_catalog, "attach_verified_install_recipes", None)),
            "verified first-install catalog bridge is missing",
        )

    def test_only_live_install_record_can_make_plan_executable(self):
        for variant in ("live_install", "fixture_install", "live_update", "missing"):
            with self.subTest(variant=variant), VerifiedInstallFixture() as f:
                if variant == "fixture_install":
                    f.r["acceptance_records"]["install"][0]["kind"] = "fixture"
                elif variant == "live_update":
                    f.r["acceptance_records"]["install"] = []
                    f.r["acceptance_records"]["update"] = [record(f.r)]
                elif variant == "missing":
                    f.r["acceptance_records"]["install"] = []
                f.attach()
                f.plan()
                self.assertEqual(
                    f.action["kind"],
                    "install" if variant == "live_install" else "manual_acquisition",
                )

    def test_consent_explicitly_binds_all_three_fingerprints(self):
        with VerifiedInstallFixture() as f:
            f.attach()
            f.plan()
            binding = f.consent["verified_recipe_bindings"][f.action["action_id"]]
            self.assertEqual(
                binding,
                dict(
                    recipe_sha256=recipe_fingerprint(f.r),
                    candidate_sha256=candidate_binding(f.r["candidate"]),
                    requirements_sha256=requirements_fingerprint(f.r),
                ),
            )

    def test_real_zip_acquisition_exclusive_install_and_exact_build(self):
        with VerifiedInstallFixture() as f:
            f.attach()
            f.plan()
            result = f.run()
            self.assertEqual(result["status"], "installed_verified", result)
            self.assertEqual(f.observe(f.destination)["build"], "200")
            self.assertEqual(pending_sessions(str(f.state)), [])
            self.assertFalse(list(f.apps.glob(".recipe-*")))

    def test_without_consent_no_download_or_staging(self):
        with VerifiedInstallFixture() as f:
            f.attach()
            f.plan()
            f.consent["action_ids"] = []
            with patch(
                "artifact_acquisition.download",
                side_effect=AssertionError("download before consent"),
            ):
                result = execution.execute_install_action(
                    f.plan_value,
                    f.action["action_id"],
                    f.consent,
                    f.catalog,
                    f.environment,
                    snapshot=f.snapshot,
                    allowed_roots=[str(f.apps)],
                    state_dir=str(f.state),
                )
            self.assertEqual(result["status"], "deferred")
            self.assertFalse(f.destination.exists())
            self.assertEqual(pending_sessions(str(f.state)), [])

    def test_changed_consent_binding_or_recipe_blocks_before_acquisition(self):
        for field in ("recipe_sha256", "candidate_sha256", "requirements_sha256"):
            with self.subTest(field=field), VerifiedInstallFixture() as f:
                f.attach()
                f.plan()
                f.consent["verified_recipe_bindings"][f.action["action_id"]][field] = (
                    "b" * 64
                )
                f.download = lambda *a, **kw: self.fail(
                    "download after changed consent"
                )
                result = f.run()
                self.assertFalse(result["verified"])
                self.assertFalse(f.destination.exists())

    def test_changed_build_after_copy_or_commit_is_not_verified(self):
        for point in ("copy", "commit"):
            with self.subTest(point=point), VerifiedInstallFixture() as f:
                f.attach()
                f.plan()
                base = f.observe

                def observed(path):
                    value = base(path)
                    if (point == "copy" and ".macupd-install-" in str(path)) or (
                        point == "commit" and Path(path) == f.destination
                    ):
                        value["build"] = "201"
                    return value

                f.observe = observed
                result = f.run()
                self.assertFalse(result["verified"], result)
                if point == "commit":
                    self.assertEqual(result["status"], "recovery_required")
                    self.assertEqual(len(pending_sessions(str(f.state))), 1)
                    self.assertTrue(f.destination.exists())
                else:
                    self.assertFalse(f.destination.exists())
                    self.assertEqual(pending_sessions(str(f.state)), [])

    def test_appeared_destination_never_overwritten_or_adopted(self):
        with VerifiedInstallFixture() as f:
            f.attach()
            f.plan()
            f.destination.mkdir()
            (f.destination / "keep").write_text("foreign")
            result = f.run()
            self.assertFalse(result["verified"])
            self.assertEqual((f.destination / "keep").read_text(), "foreign")
            self.assertEqual(pending_sessions(str(f.state)), [])

    def test_pending_scheduler_resource_blocks_download(self):
        with VerifiedInstallFixture() as f:
            f.attach()
            f.plan()
            blocker = claim_action_resources(
                dict(
                    action_id="other",
                    resources=["path:" + str(f.destination)],
                    scope_complete=True,
                    parallel_safe=False,
                ),
                str(f.state),
            )
            blocker.pending("synthetic helper unresolved")
            f.download = lambda *a, **kw: self.fail("download while pending")
            result = f.run()
            self.assertFalse(result["verified"])
            self.assertFalse(f.destination.exists())
            self.assertEqual(len(pending_sessions(str(f.state))), 1)

    def test_install_claim_exists_before_download_and_released_on_transport_error(self):
        with VerifiedInstallFixture() as f:
            f.attach()
            f.plan()

            def unavailable(*args, **kwargs):
                rows = pending_sessions(str(f.state))
                self.assertEqual(rows[0]["action_id"], f.action["action_id"])
                raise OSError("offline")

            f.download = unavailable
            result = f.run()
            self.assertFalse(result["verified"])
            self.assertFalse(f.destination.exists())
            self.assertEqual(pending_sessions(str(f.state)), [])

    def test_foreign_duplicate_other_path_and_missing_os_are_manual(self):
        with VerifiedInstallFixture() as f:
            f.attach()
            f.snapshot["environment"] = {}
            f.plan()
            self.assertEqual(f.action["kind"], "manual_acquisition")
        with VerifiedInstallFixture() as f:
            f.attach()
            f.snapshot["instances"] = [
                dict(
                    product_id="fixture-gui",
                    edition="gui",
                    presence="present",
                    source_id="homebrew",
                )
            ]
            f.plan()
            self.assertEqual(f.action["kind"], "manual_migration")

    def test_legacy_staged_install_also_claims_scheduler_before_copy(self):
        from test_install_execution import InstallFixture

        with InstallFixture() as f:
            original = execution._copy_bundle

            def copied(source, destination):
                rows = pending_sessions(str(f.state))
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["action_id"], f.action["action_id"])
                return original(source, destination)

            with patch("install_execution._copy_bundle", copied):
                result = f.run()
            self.assertTrue(result["verified"], result)
            self.assertEqual(pending_sessions(str(f.state)), [])

    def test_recovery_verifies_exact_installed_build_and_releases_own_claim(self):
        with VerifiedInstallFixture() as f:
            f.attach()
            f.plan()

            def crashed(phase, journal):
                if phase == "after_commit":
                    raise OSError("interrupted")

            result = f.run(fault=crashed)
            self.assertEqual(result["status"], "recovery_required")
            self.assertEqual(len(pending_sessions(str(f.state))), 1)
            recovered = execution.recover_installations(
                state_dir=str(f.state),
                observe=f.observe,
                allowed_roots=[str(f.apps)],
                snapshot_writer=lambda a, o: dict(
                    snapshot_id="recovered", verified_path=str(f.destination)
                ),
            )
            self.assertTrue(recovered[0]["verified"], recovered)
            self.assertEqual(pending_sessions(str(f.state)), [])

    def test_uncertain_rename_result_preserves_claim_until_observed_recovery(self):
        with VerifiedInstallFixture() as f:
            f.attach()
            f.plan()
            rename = execution._rename_exclusive

            def uncertain(source, destination):
                rename(source, destination)
                raise OSError("rename_result_lost")

            with patch("install_execution._rename_exclusive", uncertain):
                result = f.run()
            self.assertEqual(result["status"], "recovery_required")
            self.assertTrue(f.destination.exists())
            self.assertEqual(len(pending_sessions(str(f.state))), 1)

    def test_post_copy_payload_is_reobserved_immediately_before_commit(self):
        with VerifiedInstallFixture() as f:
            f.attach()
            f.plan()

            def replaced(phase, journal):
                if phase == "before_commit":
                    stage = (
                        Path(journal["created_paths"][0])
                        / "Fixture.app"
                        / "Contents/Info.plist"
                    )
                    value = plistlib.loads(stage.read_bytes())
                    value["CFBundleVersion"] = "201"
                    stage.write_bytes(plistlib.dumps(value))

            result = f.run(fault=replaced)
            self.assertFalse(result["verified"], result)
            self.assertFalse(f.destination.exists())
            self.assertEqual(pending_sessions(str(f.state)), [])

    def test_normalized_catalog_cannot_override_verified_candidate_facts(self):
        for field, bad in [
            ("version", "3.0"),
            ("build", "201"),
            ("bundle_id", "org.other"),
            ("team_id", "OTHER12345"),
            ("minimum_os", "14.0"),
            ("channel", "beta"),
            ("destination", "/fixture/apps/Other.app"),
            ("requires_administrator", True),
        ]:
            with self.subTest(field=field), VerifiedInstallFixture() as f:
                f.attach()
                row = f.catalog["recipes"][0]
                row[field] = bad
                if field == "destination":
                    row["artifact_effects"] = [bad]
                f.plan()
                self.assertEqual(f.action["kind"], "manual_acquisition")

    def test_runtime_os_change_blocks_before_download(self):
        with VerifiedInstallFixture() as f:
            f.attach()
            f.plan()
            f.environment = dict(os_version="15.2", architecture="arm64")
            f.download = lambda *a, **kw: self.fail("download on unaccepted OS")
            result = f.run()
            self.assertFalse(result["verified"])
            self.assertFalse(f.destination.exists())

    def test_wrong_build_recovery_never_releases_pending_claim(self):
        with VerifiedInstallFixture() as f:
            f.attach()
            f.plan()

            def interrupted(phase, journal):
                if phase == "after_commit":
                    raise OSError("interrupted")

            f.run(fault=interrupted)
            observe = f.observe

            def wrong(path):
                return dict(observe(path), build="201")

            results = execution.recover_installations(
                state_dir=str(f.state),
                observe=wrong,
                allowed_roots=[str(f.apps)],
                snapshot_writer=lambda a, o: dict(
                    snapshot_id="wrong", verified_path=str(f.destination)
                ),
            )
            self.assertFalse(results[0]["verified"])
            self.assertEqual(len(pending_sessions(str(f.state))), 1)
            self.assertTrue(f.destination.exists())

    def test_nonzip_or_dependency_scope_never_enters_automatic_installer(self):
        for variant in ("dmg", "dependencies", "native"):
            with self.subTest(variant=variant), VerifiedInstallFixture() as f:
                if variant == "dmg":
                    f.r["allowed_artifacts"] = ["dmg"]
                    f.r["candidate"]["artifact_type"] = "dmg"
                elif variant == "dependencies":
                    f.r["effect_scope"]["install"].append("install_dependency")
                    f.r["requirement_graph"]["nodes"] = [
                        dict(
                            id="tool",
                            kind="dependency",
                            value="extra-tool",
                            operations=["install"],
                        )
                    ]
                else:
                    f.r["update_mechanism"] = "native_updater"
                f.r["acceptance_records"]["install"] = [
                    record(
                        f.r,
                        operation="install",
                        permissions=[],
                        recorded_at=f.recorded_at,
                    )
                ]
                f.attach()
                f.plan()
                self.assertEqual(f.action["kind"], "manual_acquisition")


if __name__ == "__main__":
    unittest.main()
