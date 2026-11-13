"""Contract checks for the guarded unittest runner."""
import os
import subprocess
import sys
import unittest
from pathlib import Path


class TestIsolation(unittest.TestCase):
    def test_unmocked_curl_is_blocked(self):
        with __import__('tempfile').TemporaryDirectory() as temp:
            env = dict(os.environ, MAC_UPDATE_TEST_GUARD_LOG=os.path.join(temp, 'blocked.log'))
            result = subprocess.run(['curl', '--version'], capture_output=True, text=True, env=env)
            self.assertIn('curl --version', Path(temp, 'blocked.log').read_text())
        self.assertEqual(result.returncode, 97)
        self.assertIn('guard', result.stderr)

    def test_runner_fails_on_unmocked_tool_even_if_test_ignores_exit(self):
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copy(Path(__file__).resolve().parents[1] / 'run_tests.sh', root)
            (root / 'tests').mkdir()
            (root / 'tests' / 'test_probe.py').write_text(
                "import subprocess, unittest\n"
                "class Probe(unittest.TestCase):\n"
                " def test_guard(self): subprocess.run(['curl', '--version'], capture_output=True)\n"
                " def test_network(self):\n"
                "  import socket\n"
                "  try: socket.socket().connect(('127.0.0.1', 9))\n"
                "  except OSError: pass\n")
            result = subprocess.run(['bash', str(root / 'run_tests.sh'), '--unit-only',
                                     '--pattern', 'test_probe.py'], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('unmocked host tools', result.stdout)
            self.assertIn('python network blocked', result.stdout)

    def test_all_protected_tools_fail_closed(self):
        import tempfile
        tools = ('wget', 'open', 'osascript', 'defaults', 'hdiutil', 'ditto',
                 'codesign', 'spctl', 'brew', 'mas', 'softwareupdate')
        with tempfile.TemporaryDirectory() as temp:
            env = dict(os.environ, MAC_UPDATE_TEST_GUARD_LOG=os.path.join(temp, 'blocked.log'))
            for tool in tools:
                result = subprocess.run([tool], capture_output=True, env=env)
                self.assertEqual(result.returncode, 97, tool)
            log = Path(temp, 'blocked.log').read_text()
            for tool in tools:
                self.assertIn(tool + ' ', log)

    def test_python_subprocess_network_is_blocked(self):
        code = "import socket; socket.create_connection(('example.com', 443), timeout=1)"
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            env = dict(os.environ, MAC_UPDATE_TEST_GUARD_LOG=os.path.join(temp, 'blocked.log'))
            result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('network blocked', result.stderr)

    def test_child_python_remains_guarded_after_environment_replacement(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            env = {'PATH': os.environ['PATH'], 'PYTHONPATH': temp,
                   'MAC_UPDATE_TEST_GUARD_LOG': os.path.join(temp, 'blocked.log')}
            code = "import socket; socket.socket().connect(('127.0.0.1', 9))"
            for args in ([sys.executable, '-c', code], ['bash', '-c', 'PYTHONPATH="$1" python3 -c "$2"', '_', temp, code]):
                result = subprocess.run(args, env=env, capture_output=True, text=True)
                self.assertIn('network blocked', result.stderr)
            self.assertIn('network', Path(temp, 'blocked.log').read_text())

    def test_absolute_host_tool_paths_are_not_used(self):
        import re
        pattern = re.compile(r'/(?:usr/(?:local/)?bin|bin|opt/homebrew/bin)/(?:curl|wget|open|osascript|defaults|hdiutil|ditto|codesign|spctl|sudo|brew|mas|softwareupdate)(?:\b|$)')
        self.assertIsNotNone(pattern.search('/usr/bin/' + 'curl --version'))
        self.assertIsNotNone(pattern.search('/opt/homebrew/bin/' + 'brew install x'))
        violations = []
        for path in Path(__file__).parent.rglob('*.py'):
            if path == Path(__file__):
                continue
            for number, line in enumerate(path.read_text().splitlines(), 1):
                if pattern.search(line):
                    violations.append(f'{path.name}:{number}')
        self.assertEqual(violations, [])
