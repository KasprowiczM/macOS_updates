"""Real curses sessions against a private fixture repository; no host tools."""
import fcntl
import json
import os
import select
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Session:
    def __init__(self, repo, state, log, pidfile):
        self.master, self.slave = os.openpty()
        self.resize(36, 120, notify=False)
        env = os.environ.copy()
        env.update(TERM='xterm-256color', MAC_UPDATE_STATE_DIR=str(state),
                   MAC_UPDATE_LANG='en', FIXTURE_LOG=str(log), FIXTURE_PID=str(pidfile), PYTHONUNBUFFERED='1')
        env.pop('TMUX', None)
        env.pop('STY', None)
        code = ('import sys; sys.path.insert(0, sys.argv[1]); '
                'from terminal_app import run; sys.exit(run(sys.argv[2]))')
        self.proc = subprocess.Popen([sys.executable, '-c', code, str(ROOT / 'lib/python'), str(repo)],
                                     stdin=self.slave, stdout=self.slave, stderr=self.slave,
                                     env=env, start_new_session=True)
        self.pidfile = pidfile
        self.output = bytearray()
        self.search_from = 0
        self.deadline = time.monotonic() + 15

    def resize(self, rows, columns, notify=True):
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack('HHHH', rows, columns, 0, 0))
        if notify:
            os.kill(self.proc.pid, signal.SIGWINCH)

    def wait_for(self, needle):
        needle = needle.encode() if isinstance(needle, str) else needle
        while time.monotonic() < self.deadline:
            index = self.output.find(needle, self.search_from)
            if index >= 0:
                self.search_from = index + len(needle)
                return
            if self.proc.poll() is not None:
                self.read()
                break
            self.read()
        self.assert_failure('missing ' + repr(needle))

    def read(self):
        ready, _, _ = select.select([self.master], [], [], 0.1)
        if ready:
            try:
                self.output.extend(os.read(self.master, 65536))
            except OSError:
                pass

    def send(self, data):
        os.write(self.master, data if isinstance(data, bytes) else data.encode())

    def assert_failure(self, message):
        raise AssertionError(message + '\nterminal tail: ' + repr(bytes(self.output[-5000:])))

    def finish(self):
        while self.proc.poll() is None and time.monotonic() < self.deadline:
            self.read()
        if self.proc.poll() is None:
            self.assert_failure('terminal did not exit')
        for _ in range(3):
            self.read()
        if self.proc.returncode != 0:
            self.assert_failure('exit code ' + str(self.proc.returncode))
        data = bytes(self.output)
        if b'\x1b[?2004h' not in data or b'\x1b[?2004l' not in data:
            self.assert_failure('bracketed paste was not restored')
        if b'\x1b[?1049h' not in data or b'\x1b[?1049l' not in data:
            self.assert_failure('alternate screen was not restored')

    def close(self):
        if self.proc.poll() is None:
            if self.pidfile.exists():
                try:
                    os.kill(int(self.pidfile.read_text()), signal.SIGTERM)
                except ProcessLookupError:
                    pass
            self.proc.kill()
            self.proc.wait(timeout=3)
        os.close(self.master)
        os.close(self.slave)


class RealTerminalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.repo, self.state, self.log = root / 'repo', root / 'state', root / 'calls'
        self.pidfile = root / 'fixture-pid'
        self.repo.mkdir()
        self.state.mkdir(mode=0o700)
        (self.repo / 'VERSION').write_text('1.8.0\n')
        script = '''#!/bin/bash
printf '%s' "$$" > "$FIXTURE_PID"
printf '%s\\n' "$*" >> "$FIXTURE_LOG"
printf 'FIXTURE_PREVIEW_READY\\n'
IFS= read -r answer
printf 'answer:%s\\n' "$answer" >> "$FIXTURE_LOG"
printf 'FIXTURE_PREVIEW_DONE\\n'
'''
        for name in ('update_all.sh', 'setup.sh', 'build_inventory.sh'):
            (self.repo / name).write_text(script)
        self.session = None

    def tearDown(self):
        if self.session:
            self.session.close()
        self.temp.cleanup()

    def start(self, completed=False):
        if completed:
            (self.state / 'tui-settings.json').write_text(json.dumps({'wizard_complete': True, 'auto_resize': False}))
            (self.state / 'tui-settings.json').chmod(0o600)
        self.session = Session(self.repo, self.state, self.log, self.pidfile)
        return self.session

    def test_wizard_help_resize_and_clean_exit_without_actions(self):
        session = self.start()
        session.wait_for('Welcome')
        session.send('?')
        session.wait_for('Dashboard help')
        session.resize(18, 60)
        session.wait_for('Enlarge the terminal')
        session.resize(36, 120)
        session.wait_for('Dashboard help')
        session.send(b'\x1b')
        session.send('q')
        session.wait_for('Use i to open the answer dialog')
        session.send('q')
        session.finish()
        self.assertFalse(self.log.exists(), 'UI started a fixture action without permission')

    def test_preview_output_and_explicit_answer(self):
        session = self.start(completed=True)
        session.wait_for('Preview update plan')
        session.send('d')
        session.wait_for('FIXTURE_PREVIEW_READY')
        session.send('i')
        session.wait_for('PgUp / PgDn')
        session.send('fixture-answer')
        session.wait_for('fixture-answer')
        session.send('\r')
        session.wait_for('FIXTURE_PREVIEW_DONE')
        session.wait_for('Operation finished')
        session.send('q')
        session.finish()
        self.assertEqual(self.log.read_text().splitlines(), ['--dry-run', 'answer:fixture-answer'])


if __name__ == '__main__':
    unittest.main()
