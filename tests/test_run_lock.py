"""Per-repo lock: exclusive create, same-PID reentry, stale PID release."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class PythonRunLockTests(unittest.TestCase):
    def test_acquire_release_and_reentrant_same_pid(self) -> None:
        import sys

        sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))
        import run_lock

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            first = run_lock.acquire(repo)
            self.assertTrue(first.is_file())
            self.assertEqual(first.stat().st_mode & 0o777, 0o600)
            second = run_lock.acquire(repo)
            self.assertEqual(first, second)
            run_lock.release(repo)
            self.assertFalse(first.exists())

    def test_live_foreign_pid_is_rejected(self) -> None:
        import sys

        sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))
        import run_lock

        holder = subprocess.Popen(["sleep", "30"])
        try:
            with tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp)
                lock = repo / ".mac-update.lock"
                lock.write_text(
                    f"pid={holder.pid}\nstarted=2026-01-01T00:00:00Z\nstarted_unix=0\n",
                    encoding="utf-8",
                )
                with self.assertRaises(run_lock.LockError):
                    run_lock.acquire(repo)
        finally:
            holder.kill()
            holder.wait()

    def test_dead_pid_is_stolen(self) -> None:
        import sys

        sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))
        import run_lock

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            lock = repo / ".mac-update.lock"
            lock.write_text(
                "pid=999999\nstarted=2026-01-01T00:00:00Z\nstarted_unix=0\n",
                encoding="utf-8",
            )
            acquired = run_lock.acquire(repo)
            self.assertTrue(acquired.is_file())
            payload = acquired.read_text(encoding="utf-8")
            self.assertIn(f"pid={os.getpid()}", payload)
            run_lock.release(repo)


class BashRunLockTests(unittest.TestCase):
    def test_bash_lock_is_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = f"""
. "{REPO_ROOT}/lib/run_lock.sh"
mac_update_lock_acquire "{tmp}" || exit 10
mac_update_lock_acquire "{tmp}" || exit 11
if bash -c '. "{REPO_ROOT}/lib/run_lock.sh"; mac_update_lock_acquire "{tmp}"'; then
  mac_update_lock_release "{tmp}"
  exit 12
fi
mac_update_lock_release "{tmp}"
exit 0
"""
            out = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stdout + out.stderr)


if __name__ == "__main__":
    unittest.main()
