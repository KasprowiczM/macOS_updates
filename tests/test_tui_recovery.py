"""A failed UI must not close an active fixture worker's terminal."""

import io
import os
from pathlib import Path
import tempfile
import termios
import threading
import time
import unittest

from tui_backend import DEFAULT_SETTINGS, GROUPS, TerminalJob
from tui_recovery import handoff


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name).resolve()

    def job(self, body):
        (self.repo / "update_all.sh").write_text("#!/bin/bash\n" + body + "\n")
        return TerminalJob(self.repo, "update", GROUPS, DEFAULT_SETTINGS).start()

    def wait_for(self, predicate):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.005)
        self.fail("fixture recovery did not reach expected state")

    def outer_terminal(self):
        master, slave = os.openpty()
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        stream = os.fdopen(os.dup(slave), "r", encoding="utf-8")
        self.addCleanup(stream.close)
        return master, slave, stream

    def threaded_handoff(self, job, stream, output):
        result, errors = [], []

        def run():
            try:
                result.append(handoff(job, "UI failed; continue here.", stream, output))
            except BaseException as error:
                errors.append(error)

        thread = threading.Thread(target=run)
        thread.start()
        return thread, result, errors

    def assert_restored(self, terminal, expected):
        actual = termios.tcgetattr(terminal)
        expected = list(expected)
        # Darwin sets the kernel PENDIN status bit when canonical mode returns.
        # Clearing it by reading/flushing would consume the user's queued input.
        pending = getattr(termios, "PENDIN", 0)
        actual[3] &= ~pending
        expected[3] &= ~pending
        self.assertEqual(actual, expected)

    def test_ui_failure_drains_worker_and_never_replays_non_tty_answers(self):
        job = self.job('trap "exit 129" HUP\nprintf READY\\n\n'
                       'if IFS= read -r -t 0.15 answer; then printf "UNEXPECTED:%s" "$answer"; else printf NO_INPUT; fi\nprintf DONE')
        output = io.StringIO()
        code = handoff(job, "UI failed.", io.StringIO("yes\n"), output)
        self.assertEqual(code, 0)
        self.assertFalse(job.running)
        self.assertIn("NO_INPUT", output.getvalue())
        self.assertIn("DONE", output.getvalue())
        self.assertNotIn("UNEXPECTED", output.getvalue())

    def test_raw_parent_terminal_hides_input_and_restores_exact_attributes(self):
        master, slave, stream = self.outer_terminal()
        previous = termios.tcgetattr(slave)
        job = self.job('printf "SECRET\\n"\nIFS= read -r -s -t 3 answer\nprintf "\\nLENGTH:%s\\n" "${#answer}"')
        output = io.StringIO()
        thread, result, errors = self.threaded_handoff(job, stream, output)
        self.wait_for(lambda: "SECRET" in output.getvalue() and job.secret_input)
        raw = termios.tcgetattr(slave)
        self.assertFalse(raw[3] & termios.ECHO)
        self.assertFalse(raw[3] & termios.ICANON)
        self.assertFalse(raw[3] & termios.ISIG)
        os.write(master, b"fixture-secret\n")
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(result, [0])
        self.assertIn("LENGTH:14", output.getvalue())
        self.assertNotIn("fixture-secret", output.getvalue())
        self.assert_restored(slave, previous)
        os.set_blocking(master, False)
        with self.assertRaises(BlockingIOError):
            os.read(master, 1024)  # Parent terminal did not echo the secret.

    def test_incremental_utf8_and_ctrl_c_reach_only_the_owned_worker(self):
        master, slave, stream = self.outer_terminal()
        previous = termios.tcgetattr(slave)
        job = self.job('trap "printf INTERRUPTED; exit 130" INT\nprintf "READY\\n"\n'
                       'IFS= read -r -t 3 answer\nprintf "GOT:%s\\n" "$answer"\nIFS= read -r -t 3 answer')
        output = io.StringIO()
        thread, result, errors = self.threaded_handoff(job, stream, output)
        self.wait_for(lambda: "READY" in output.getvalue())
        raw = "Żółw\n".encode("utf-8")
        os.write(master, raw[:1])
        time.sleep(0.02)
        os.write(master, raw[1:])
        self.wait_for(lambda: "GOT:Żółw" in output.getvalue())
        os.write(master, b"\x03")
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(result, [130])
        self.assertIn("INTERRUPTED", output.getvalue())
        self.assert_restored(slave, previous)

    def test_parent_tty_eof_does_not_hang_up_the_worker(self):
        master, slave = os.openpty()
        self.addCleanup(os.close, slave)
        stream = os.fdopen(os.dup(slave), "r", encoding="utf-8")
        self.addCleanup(stream.close)
        job = self.job('trap "exit 129" HUP\nprintf READY\\n\nsleep 0.15\nprintf DONE')
        output = io.StringIO()
        thread, result, errors = self.threaded_handoff(job, stream, output)
        self.wait_for(lambda: "READY" in output.getvalue())
        os.close(master)
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(result, [0])
        self.assertIn("DONE", output.getvalue())

    def test_control_sequences_cannot_execute_during_plain_output_handoff(self):
        job = self.job("printf 'safe\\033[2J\\033Ppayload'; sleep 0.02; printf '\\033\\\\after\\033]52;c;hidden\\adone'")
        output = io.StringIO()
        self.assertEqual(handoff(job, "Failure", io.StringIO(), output), 0)
        self.assertIn("safeafterdone", output.getvalue())
        self.assertNotIn("\033", output.getvalue())
        self.assertNotIn("payload", output.getvalue())
        self.assertNotIn("hidden", output.getvalue())

    def test_output_failure_keeps_monitoring_instead_of_closing_the_worker(self):
        class ClosedOutput:
            def write(self, text):
                raise BrokenPipeError("fixture closed output")

        job = self.job('trap "exit 129" HUP\nsleep 0.1\nexit 10')
        self.assertEqual(handoff(job, "Failure", io.StringIO(), ClosedOutput()), 10)
        self.assertFalse(job.running)


if __name__ == "__main__":
    unittest.main()
