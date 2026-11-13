import os
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib", "python"))
from inventory_collect import Providers, collect_snapshot
from inventory_store import load_snapshot, save_snapshot, StoreError


class StoreTests(unittest.TestCase):
    def test_deep_invalid_json_returns_store_error(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "inventory.json")
            with open(path, "w") as stream:
                stream.write("[" * 2000 + "0" + "]" * 2000)
            os.chmod(path, 0o600)
            with self.assertRaises(StoreError):
                load_snapshot(root)

    def test_atomic_cas_and_modes(self):
        with tempfile.TemporaryDirectory() as root:
            state = os.path.join(root, "state")
            snap = collect_snapshot([], Providers(), None)
            saved = save_snapshot(state, snap, 0)
            self.assertEqual(saved["generation"], 1)
            self.assertEqual(load_snapshot(state), saved)
            self.assertEqual(stat.S_IMODE(os.stat(state).st_mode), 0o700)
            self.assertEqual(
                stat.S_IMODE(os.stat(os.path.join(state, "inventory.json")).st_mode),
                0o600,
            )
            with self.assertRaises(StoreError):
                save_snapshot(state, snap, 0)
            self.assertEqual(load_snapshot(state), saved)

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            os.symlink(root, os.path.join(root, "link"))
            with self.assertRaises(StoreError):
                load_snapshot(os.path.join(root, "link"))

    def test_foreign_profile_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as parent:
            root = os.path.join(parent, "state")
            first = save_snapshot(root, collect_snapshot([], Providers(), None), 0)
            foreign = collect_snapshot([], Providers(), None)
            foreign["generation"] = 1
            foreign["previous_snapshot_id"] = first["snapshot_id"]
            with self.assertRaises(StoreError):
                save_snapshot(root, foreign, 1)
            self.assertEqual(load_snapshot(root), first)

    def test_failed_replace_keeps_previous(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as parent:
            root = os.path.join(parent, "state")
            first = save_snapshot(root, collect_snapshot([], Providers(), None), 0)
            second = collect_snapshot([], Providers(), first)
            with patch("inventory_store.os.replace", side_effect=OSError("failure")):
                with self.assertRaises(StoreError):
                    save_snapshot(root, second, 1)
            self.assertEqual(load_snapshot(root), first)

    def test_stale_writer_and_symlink_parent(self):
        with tempfile.TemporaryDirectory() as parent:
            root = os.path.join(parent, "state")
            first = save_snapshot(root, collect_snapshot([], Providers(), None), 0)
            one = collect_snapshot([], Providers(), first)
            two = collect_snapshot([], Providers(), first)
            saved = save_snapshot(root, one, 1)
            with self.assertRaises(StoreError):
                save_snapshot(root, two, 1)
            self.assertEqual(load_snapshot(root), saved)
            os.symlink(parent, os.path.join(parent, "alias"))
            with self.assertRaises(StoreError):
                load_snapshot(os.path.join(parent, "alias", "state"))

    def test_fifo_and_oversized_snapshot_rejected(self):
        with tempfile.TemporaryDirectory() as parent:
            root = os.path.join(parent, "state")
            os.mkdir(root, 0o700)
            path = os.path.join(root, "inventory.json")
            os.mkfifo(path, 0o600)
            with self.assertRaises(StoreError):
                load_snapshot(root)
            os.unlink(path)
            with open(path, "wb") as f:
                f.write(b" " * (16 * 1024 * 1024 + 1))
            os.chmod(path, 0o600)
            with self.assertRaises(StoreError):
                load_snapshot(root)

    def test_oversized_write_keeps_old_snapshot(self):
        with tempfile.TemporaryDirectory() as parent:
            root = os.path.join(parent, "state")
            first = save_snapshot(root, collect_snapshot([], Providers(), None), 0)
            second = collect_snapshot([], Providers(), first)
            second["sources"]["mas"]["items"] = [{"padding": "x" * (16 * 1024 * 1024)}]
            with self.assertRaises(StoreError):
                save_snapshot(root, second, 1)
            self.assertEqual(load_snapshot(root), first)

    def test_lock_timeout_and_open_directory_mode(self):
        import fcntl
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as parent:
            root = os.path.join(parent, "state")
            first = save_snapshot(root, collect_snapshot([], Providers(), None), 0)
            lock = os.open(os.path.join(root, ".inventory.lock"), os.O_RDWR)
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with patch("inventory_store.LOCK_TIMEOUT_SECONDS", 0):
                    with self.assertRaisesRegex(StoreError, "lock timeout"):
                        save_snapshot(root, collect_snapshot([], Providers(), first), 1)
            finally:
                os.close(lock)
            self.assertEqual(load_snapshot(root), first)
            os.chmod(root, 0o755)
            with self.assertRaises(StoreError):
                save_snapshot(root, collect_snapshot([], Providers(), first), 1)
