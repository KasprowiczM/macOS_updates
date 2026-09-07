"""H2: failed swap + failed restore must keep a recoverable backup."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "dev_sync"))

from overlay_import import OverlayRecoveryError, commit_overlay, recover_overlay_transaction  # noqa: E402
from dev_sync_core import RunOptions  # noqa: E402


class _Null:
    def log(self, message: str, always_stdout: bool = True) -> None:
        pass

    def verbose(self, message: str) -> None:
        pass


class SwapAndRestoreFailureKeepsBackup(unittest.TestCase):
    def test_failed_swap_and_restore_leaves_backup_and_recovery_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            dest = root / "dest"
            source.mkdir()
            dest.mkdir()
            (source / "secret.txt").write_text("incoming", encoding="utf-8")
            (dest / "secret.txt").write_text("original", encoding="utf-8")

            real_replace = os.replace

            def fail_swap_and_restore(src, target):
                src_p, tgt_p = Path(src), Path(target)
                if "incoming" in src_p.parts and tgt_p.name == "secret.txt":
                    raise OSError("simulated incoming swap failure")
                if "backup" in src_p.parts and tgt_p.name == "secret.txt":
                    raise OSError("simulated restore failure")
                return real_replace(src, target)

            with mock.patch("overlay_import.os.replace", side_effect=fail_swap_and_restore):
                with self.assertRaises(OverlayRecoveryError) as ctx:
                    commit_overlay(
                        source,
                        dest,
                        ["secret.txt"],
                        _Null(),
                        RunOptions(),
                    )

            recovery = Path(ctx.exception.recovery_path)
            self.assertTrue(recovery.is_dir(), msg=str(ctx.exception))
            backup = recovery / "backup" / "secret.txt"
            self.assertTrue(backup.exists(), f"backup missing under {recovery}")
            self.assertEqual(backup.read_text(encoding="utf-8"), "original")
            self.assertIn(str(recovery), str(ctx.exception))
            leftover_txn = list(dest.glob(".dev-sync-txn-*"))
            self.assertTrue(leftover_txn, "transaction directory was cleaned up")

    def test_successful_rollback_still_restores_original(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            dest = root / "dest"
            source.mkdir()
            dest.mkdir()
            (source / "first.txt").write_text("new-first", encoding="utf-8")
            (source / "second.txt").write_text("new-second", encoding="utf-8")
            (dest / "first.txt").write_text("old-first", encoding="utf-8")
            (dest / "second.txt").write_text("old-second", encoding="utf-8")

            real_replace = os.replace

            def fail_incoming_swap(src, target):
                if Path(target) == dest / "second.txt" and "incoming" in Path(src).parts:
                    raise OSError("simulated swap failure")
                return real_replace(src, target)

            with mock.patch("overlay_import.os.replace", side_effect=fail_incoming_swap):
                with self.assertRaises(OSError):
                    commit_overlay(
                        source,
                        dest,
                        ["first.txt", "second.txt"],
                        _Null(),
                        RunOptions(),
                    )

            self.assertEqual((dest / "first.txt").read_text(encoding="utf-8"), "old-first")
            self.assertEqual((dest / "second.txt").read_text(encoding="utf-8"), "old-second")
            self.assertFalse(list(dest.glob(".dev-sync-txn-*")))

    def test_recover_overlay_restores_missing_original(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest = root / "dest"
            dest.mkdir()
            txn = dest / ".dev-sync-txn-recover"
            backup = txn / "backup"
            backup.mkdir(parents=True)
            (backup / "secret.txt").write_text("original", encoding="utf-8")
            recover_overlay_transaction(txn, dest)
            self.assertEqual((dest / "secret.txt").read_text(encoding="utf-8"), "original")


if __name__ == "__main__":
    unittest.main()
