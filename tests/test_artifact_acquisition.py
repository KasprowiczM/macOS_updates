"""Bounded acquisition tests: no network, mount or native tools."""

import hashlib
import io
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib/python"))
from artifact_acquisition import acquire_candidate


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.data = self.archive({"Fixture.app/Contents/Info.plist": b"fixture"})

    def archive(self, entries):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as z:
            for name, value in entries.items():
                z.writestr(name, value)
        return data.getvalue()

    def action(self):
        return dict(
            candidate=dict(
                url="https://example.org/fixture.zip",
                sha256=hashlib.sha256(self.data).hexdigest(),
                artifact_type="zip",
                bundle_name="Fixture.app",
                version="2.0",
                build="20",
                bundle_id="org.example.fixture",
                team_id="FIXTURE123",
            ),
            download_hosts=["example.org"],
            limits=dict(
                maximum_bytes=1048576,
                maximum_expanded_bytes=1048576,
                maximum_entries=100,
            ),
        )

    def download(self, url, dest, **kwargs):
        Path(dest).write_bytes(self.data)

    def observe(self, path):
        self.assertTrue(Path(path, "Contents/Info.plist").is_file())
        return dict(
            good=True,
            receipt_present=False,
            bundle_id="org.example.fixture",
            team_id="FIXTURE123",
            version="2.0",
            build="20",
            architectures=["arm64"],
            minimum_os="13.0",
            host_os="13.0",
        )

    def acquire(self, action=None, observer=None):
        with patch("artifact_acquisition.download", self.download):
            return acquire_candidate(
                action or self.action(), self.root, observer=observer or self.observe
            )

    def test_exact_archive_is_verified_without_launch(self):
        result = self.acquire()
        self.assertEqual(result["observed"]["version"], "2.0")
        self.assertTrue(Path(result["bundle_path"]).is_dir())
        self.assertEqual(stat.S_IMODE(os.stat(result["staging_path"]).st_mode), 0o700)

    def test_changed_archive_rejected_before_observation(self):
        action = self.action()
        self.data += b"changed"
        with self.assertRaisesRegex(ValueError, "artifact_hash_changed"):
            self.acquire(
                action, lambda _: self.fail("must not inspect changed payload")
            )
        self.assertEqual(list(Path(self.root).iterdir()), [])

    def test_traversal_extra_payload_duplicate_and_symlink_escape_rejected(self):
        cases = [
            {"../outside": b"x"},
            {"Fixture.app/../../outside": b"x"},
            {"Fixture.app/Contents/Info.plist": b"x", "helper.pkg": b"x"},
            {"Fixture.app/x": b"x", "Fixture.app/X": b"y"},
            {"Fixture.app/\u00e9": b"x", "Fixture.app/e\u0301": b"y"},
        ]
        for entries in cases:
            with self.subTest(entries=entries):
                self.data = self.archive(entries)
                with self.assertRaises(ValueError):
                    self.acquire()
                self.assertEqual(list(Path(self.root).iterdir()), [])
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as z:
            i = zipfile.ZipInfo("Fixture.app/link")
            i.create_system = 3
            i.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(i, "../../outside")
        self.data = data.getvalue()
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.acquire()

    def test_internal_framework_symlink_allowed(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as z:
            z.writestr("Fixture.app/Contents/Info.plist", "fixture")
            z.writestr("Fixture.app/Contents/Frameworks/F/Versions/A/lib", "fixture")
            i = zipfile.ZipInfo("Fixture.app/Contents/Frameworks/F/Versions/Current")
            i.create_system = 3
            i.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(i, "A")
        self.data = data.getvalue()
        r = self.acquire()
        self.assertTrue(
            Path(
                r["bundle_path"], "Contents/Frameworks/F/Versions/Current/lib"
            ).is_file()
        )

    def test_expansion_bound_and_identity_fail_closed(self):
        action = self.action()
        action["limits"]["maximum_expanded_bytes"] = 1
        with self.assertRaisesRegex(ValueError, "expansion_limit"):
            self.acquire(action)
        with self.assertRaisesRegex(ValueError, "candidate_identity_changed"):
            self.acquire(observer=lambda _: dict(self.observe(_), team_id="OTHER"))
        self.assertEqual(list(Path(self.root).iterdir()), [])

    def test_native_formats_never_mount_or_execute(self):
        for kind in ("dmg", "pkg", "app"):
            action = self.action()
            action["candidate"]["artifact_type"] = kind
            with self.assertRaisesRegex(ValueError, "artifact_format_requires_review"):
                self.acquire(action)

    def test_symlink_stage_root_rejected(self):
        link = Path(self.root, "link")
        link.symlink_to(self.root)
        with self.assertRaises(ValueError):
            acquire_candidate(self.action(), str(link))


if __name__ == "__main__":
    unittest.main()
