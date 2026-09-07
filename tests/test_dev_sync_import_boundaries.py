"""H1/H3: overlay import must not clobber Git or read outside the provider root."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "dev_sync"))

from dev_sync_core import (  # noqa: E402
    DevSyncConfig,
    DevSyncError,
    ImportResult,
    RunOptions,
    import_overlay,
    write_manifest,
)
from overlay_import import plan_overlay_import, validate_source  # noqa: E402


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(repo: Path) -> None:
    _git(repo, "init")
    _git(repo, "config", "user.email", "devsync-test@example.test")
    _git(repo, "config", "user.name", "DevSync Test")
    _git(repo, "config", "commit.gpgsign", "false")


class DirectoryManifestDoesNotClobberGit(unittest.TestCase):
    def test_directory_manifest_keeps_tracked_and_unlisted_local_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            cloud = root / "cloud"
            project = cloud / "proj"
            repo.mkdir()
            project.mkdir(parents=True)

            (repo / "docs").mkdir()
            (repo / "docs" / "tracked.txt").write_text("ORIGINAL", encoding="utf-8")
            (repo / "docs" / "local_only.txt").write_text("LOCAL", encoding="utf-8")
            (repo / "README.md").write_text("readme", encoding="utf-8")
            _init_repo(repo)
            _git(repo, "add", "docs/tracked.txt", "README.md")
            _git(repo, "commit", "-m", "seed")

            (project / "docs").mkdir()
            (project / "docs" / "tracked.txt").write_text("CLOUD_OVERWRITE", encoding="utf-8")
            (project / "docs" / "from_cloud.txt").write_text("cloud-new", encoding="utf-8")
            write_manifest(project, ["docs"], logger=_Null(), options=RunOptions())

            config = DevSyncConfig(
                project_name="proj",
                provider="local",
                provider_path=str(cloud),
            )
            result = import_overlay(repo, config)
            self.assertIsInstance(result, ImportResult)
            self.assertEqual(
                (repo / "docs" / "tracked.txt").read_text(encoding="utf-8"),
                "ORIGINAL",
            )
            self.assertEqual(
                (repo / "docs" / "local_only.txt").read_text(encoding="utf-8"),
                "LOCAL",
            )
            self.assertEqual(
                (repo / "docs" / "from_cloud.txt").read_text(encoding="utf-8"),
                "cloud-new",
            )
            self.assertIn("docs/tracked.txt", result.skipped_tracked_files)

    def test_plan_expands_directory_and_drops_tracked_leaves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            source = root / "source"
            repo.mkdir()
            source.mkdir()
            (repo / "docs").mkdir()
            (repo / "docs" / "tracked.txt").write_text("ORIGINAL", encoding="utf-8")
            _init_repo(repo)
            _git(repo, "add", "docs/tracked.txt")
            _git(repo, "commit", "-m", "seed")
            (source / "docs").mkdir()
            (source / "docs" / "tracked.txt").write_text("CLOUD", encoding="utf-8")
            (source / "docs" / "private.env").write_text("secret", encoding="utf-8")
            config = DevSyncConfig(project_name="proj", provider="local", provider_path=str(root))
            plan = plan_overlay_import(repo, source, config, ["docs"])
            self.assertNotIn("docs", plan.files_to_copy)
            self.assertNotIn("docs/tracked.txt", plan.files_to_copy)
            self.assertIn("docs/private.env", plan.files_to_copy)
            self.assertIn("docs/tracked.txt", plan.skipped_tracked)


class SourceSymlinkEscapeTests(unittest.TestCase):
    def test_symlink_ancestor_outside_root_is_rejected_before_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside"
            source = root / "provider"
            dest = root / "dest"
            outside.mkdir()
            source.mkdir()
            dest.mkdir()
            (outside / "marker.txt").write_text("OUTSIDE", encoding="utf-8")
            os.symlink(outside, source / "link")

            with self.assertRaises(DevSyncError) as ctx:
                validate_source(source, "link/marker.txt")
            self.assertIn("escape", str(ctx.exception).lower())
            self.assertFalse((dest / "marker.txt").exists())

    def test_import_refuses_symlink_escape_and_does_not_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            cloud = root / "cloud"
            project = cloud / "proj"
            outside = root / "outside"
            repo.mkdir()
            project.mkdir(parents=True)
            outside.mkdir()
            (outside / "marker.txt").write_text("OUTSIDE", encoding="utf-8")
            os.symlink(outside, project / "link")
            write_manifest(
                project,
                ["link/marker.txt"],
                logger=_Null(),
                options=RunOptions(),
            )
            (repo / "keep.txt").write_text("keep", encoding="utf-8")
            _init_repo(repo)
            _git(repo, "add", "keep.txt")
            _git(repo, "commit", "-m", "seed")

            config = DevSyncConfig(
                project_name="proj",
                provider="local",
                provider_path=str(cloud),
            )
            with self.assertRaises(DevSyncError):
                import_overlay(repo, config)
            self.assertFalse((repo / "marker.txt").exists())
            self.assertFalse((repo / "link" / "marker.txt").exists())
            self.assertEqual((repo / "keep.txt").read_text(encoding="utf-8"), "keep")


class DestSymlinkEscapeTests(unittest.TestCase):
    def test_relative_symlink_escaping_dest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            dest = root / "dest"
            source.mkdir()
            dest.mkdir()
            (source / "ok.txt").write_text("ok", encoding="utf-8")
            # Resolves inside source (/.../source/ok.txt) but at dest becomes
            # /.../source/ok.txt, which is outside dest_base.
            os.symlink("../source/ok.txt", source / "link")
            from overlay_import import commit_overlay
            from dev_sync_core import DevSyncError, RunOptions
            with self.assertRaises(DevSyncError) as ctx:
                commit_overlay(source, dest, ["link"], _Null(), RunOptions())
            self.assertIn("escape", str(ctx.exception).lower())
            self.assertFalse((dest / "link").exists())


class _Null:
    def log(self, message: str, always_stdout: bool = True) -> None:
        pass

    def verbose(self, message: str) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
