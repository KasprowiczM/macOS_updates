import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class SetupConsentTests(unittest.TestCase):
    def test_installer_does_not_launch_touchid_or_clt(self):
        text = (ROOT / 'install.sh').read_text()
        self.assertNotIn('bash "$MAC_UPDATE_DIR/scripts/setup_touchid_sudo.sh"', text)
        self.assertNotIn('xcode-select --install 2>', text)

    def test_appstore_never_installs_mas(self):
        text = (ROOT / 'update_appstore.sh').read_text()
        self.assertNotIn('if brew install mas', text)
        self.assertNotIn('brew upgrade mas 2>', text)

class IsolatedSetupTests(unittest.TestCase):
    def setUp(self):
        import tempfile, shutil, os
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = pathlib.Path(self.tmp.name)
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        shutil.copy(ROOT / 'setup.sh', self.repo / 'setup.sh')
        shutil.copytree(ROOT / 'i18n', self.repo / 'i18n')
        shutil.copytree(ROOT / 'lib', self.repo / 'lib')
        self.home = self.base / 'home'
        self.home.mkdir()
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        for name in ('dirname', 'grep'):
            (self.bin / name).symlink_to(shutil.which(name))
        for name, value in [('uname', 'arm64'), ('sw_vers', '14.0')]:
            tool = self.bin / name
            tool.write_text('#!/bin/bash\necho ' + value + '\n')
            tool.chmod(0o755)
        self.log = self.base / 'commands'
        brew = self.bin / 'brew'
        brew.write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> "$TEST_LOG"\n')
        brew.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.bin), HOME=str(self.home), SHELL="/bin/zsh",
                        TEST_LOG=str(self.log), MAC_UPDATE_LANG='en',
                        MAC_UPDATE_HOMEBREW_PREFIX=str(self.base / 'prefix'))

    def run_setup(self, *args, terminal=False, answers=''):
        import subprocess, pty, os
        cmd = ['/bin/bash', str(self.repo / 'setup.sh'), *args]
        if not terminal:
            return subprocess.run(cmd, env=self.env, capture_output=True, text=True)
        master, slave = pty.openpty()
        proc = subprocess.Popen(cmd, env=self.env, stdin=slave, stdout=slave, stderr=slave)
        os.close(slave)
        os.write(master, answers.encode())
        proc.wait(timeout=5)
        os.close(master)
        return proc

    def test_unsupported_platform_refuses_changes(self):
        (self.bin / 'uname').write_text('#!/bin/bash\necho x86_64\n')
        result = self.run_setup('--configure-shell', terminal=True, answers='y\n')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_old_mas_and_unrunnable_python_are_unavailable(self):
        for name, content in [('mas', 'echo 3.0'), ('python3', 'exit 1')]:
            path = self.bin / name
            path.write_text('#!/bin/bash\n' + content + '\n')
            path.chmod(0o755)
        result = self.run_setup('--inspect')
        self.assertEqual(result.returncode, 10)
        self.assertIn('mas: unavailable', result.stdout)
        self.assertIn('python3: unavailable', result.stdout)

    def test_repeated_inspection_is_read_only_and_reports_missing_python(self):
        before = set(self.repo.rglob('*'))
        for _ in range(2):
            result = self.run_setup('--inspect')
            self.assertEqual(result.returncode, 10)
            self.assertIn('Inventory and coverage cannot run', result.stdout)
        self.assertEqual(before, set(self.repo.rglob('*')))
        self.assertEqual(list(self.home.iterdir()), [])
        self.assertFalse(self.log.exists())

    def test_unattended_explicit_mutations_are_refused(self):
        result = self.run_setup('--install-dependencies', '--configure-shell')
        self.assertEqual(result.returncode, 10)
        self.assertFalse(self.log.exists())
        self.assertEqual(list(self.home.iterdir()), [])

    def test_declining_one_dependency_does_not_block_another(self):
        result = self.run_setup('--install-dependencies', terminal=True, answers='n\ny\n')
        self.assertEqual(result.returncode, 10)
        self.assertEqual(self.log.read_text().splitlines(), ['install python'])
        self.assertEqual(list(self.home.iterdir()), [])

    def test_successful_dependency_setup_rechecks_readiness(self):
        import shutil
        (self.bin / 'chmod').symlink_to(shutil.which('chmod'))
        git = self.bin / 'git'
        git.write_text('#!/bin/bash\nexit 0\n')
        git.chmod(0o755)
        self.env['TEST_BIN'] = str(self.bin)
        (self.bin / 'brew').write_text("""#!/bin/bash
printf '%s\\n' "$*" >> "$TEST_LOG"
case "$*" in
  'install mas') printf '#!/bin/bash\\necho 4.1\\n' > "$TEST_BIN/mas"; chmod +x "$TEST_BIN/mas" ;;
  'install python') printf '#!/bin/bash\\nexit 0\\n' > "$TEST_BIN/python3"; chmod +x "$TEST_BIN/python3" ;;
  *) exit 1 ;;
esac
""")
        result = self.run_setup('--install-dependencies', terminal=True, answers='y\ny\n')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.log.read_text().splitlines(), ['install mas', 'install python'])

    def test_missing_brew_read_only_home_remains_unchanged(self):
        (self.bin / 'brew').unlink()
        self.home.chmod(0o555)
        result = self.run_setup('--inspect')
        self.assertEqual(result.returncode, 10)
        self.assertIn('brew: unavailable', result.stdout)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_symlink_and_unsafe_prefix_cannot_change_profile(self):
        (self.bin / 'python3').symlink_to(sys.executable)
        prefix_bin = self.base / 'prefix' / 'bin'
        prefix_bin.mkdir(parents=True)
        (prefix_bin / 'brew').symlink_to(self.bin / 'brew')
        target = self.base / 'foreign'
        target.write_text('untouched\n')
        (self.home / '.zprofile').symlink_to(target)
        self.run_setup('--configure-shell', terminal=True, answers='y\n')
        self.assertEqual(target.read_text(), 'untouched\n')
        (self.home / '.zprofile').unlink()
        self.env['MAC_UPDATE_HOMEBREW_PREFIX'] = str(self.base / 'unsafe"prefix')
        self.run_setup('--configure-shell', terminal=True, answers='y\n')
        self.assertFalse((self.home / '.zprofile').exists())

    def test_bash_profile_is_configured_for_bash_user(self):
        self.env['SHELL'] = '/bin/bash'
        (self.bin / 'python3').symlink_to(sys.executable)
        prefix_bin = self.base / 'prefix' / 'bin'
        prefix_bin.mkdir(parents=True)
        (prefix_bin / 'brew').symlink_to(self.bin / 'brew')
        self.run_setup('--configure-shell', terminal=True, answers='y\n')
        self.assertTrue((self.home / '.bash_profile').is_file())
        self.assertFalse((self.home / '.zprofile').exists())

    def test_shell_change_requires_separate_consent(self):
        (self.bin / 'python3').symlink_to(sys.executable)
        prefix_bin = self.base / 'prefix' / 'bin'
        prefix_bin.mkdir(parents=True)
        (prefix_bin / 'brew').symlink_to(self.bin / 'brew')
        self.run_setup('--configure-shell', terminal=True, answers='n\n')
        self.assertFalse((self.home / '.zprofile').exists())
        self.run_setup('--configure-shell', terminal=True, answers='y\n')
        content = (self.home / '.zprofile').read_text()
        self.assertIn('shellenv', content)
        self.run_setup('--configure-shell', terminal=True, answers='y\n')
        self.assertEqual((self.home / '.zprofile').read_text(), content)

class InstallerReadinessTests(unittest.TestCase):
    def test_missing_python_does_not_end_with_ready_or_create_inventory(self):
        import tempfile, shutil, subprocess, os
        with tempfile.TemporaryDirectory() as temp:
            base = pathlib.Path(temp)
            repo = base / 'repo'
            repo.mkdir()
            (repo / '.git').mkdir()
            for directory in ('lib', 'i18n'):
                shutil.copytree(ROOT / directory, repo / directory)
            for name in ('install.sh', 'setup.sh', 'VERSION'):
                shutil.copy(ROOT / name, repo / name)
            (repo / 'build_inventory.sh').write_text('echo unexpected > "$HOME/inventory-called"\n')
            (repo / 'scripts').mkdir()
            (repo / 'scripts/report_update_coverage.sh').write_text('echo unexpected > "$HOME/coverage-called"\n')
            bindir = base / 'bin'
            bindir.mkdir()
            for name in ('dirname', 'mkdir', 'grep', 'tr', 'cut', 'head', 'cat'):
                (bindir / name).symlink_to(shutil.which(name))
            (bindir / 'bash').symlink_to('/bin/bash')
            for name, body in [('uname', 'echo arm64'), ('sw_vers', 'echo 27.0'),
                               ('git', 'echo git-called >> "$HOME/git-calls"; exit 97'), ('python3', 'exit 1')]:
                p = bindir / name
                p.write_text('#!/bin/bash\n' + body + '\n')
                p.chmod(0o755)
            env = dict(os.environ, HOME=temp, PATH=str(bindir), MAC_UPDATE_DIR=str(repo),
                       MAC_UPDATE_LANG='en', MAC_LANG='en', MAC_UPDATE_HOMEBREW_PREFIX=str(base / 'no-brew'))
            result = subprocess.run(['/bin/bash', str(repo / 'install.sh')], env=env,
                                    stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 10, result.stdout + result.stderr)
            self.assertNotIn('is ready', result.stdout)
            self.assertFalse((base / 'inventory-called').exists())
            self.assertFalse((base / 'coverage-called').exists())
            self.assertFalse((base / 'git-calls').exists())

class IsolatedTouchIDTests(unittest.TestCase):
    def test_foreign_pam_file_is_preserved(self):
        import tempfile, shutil, subprocess, os
        with tempfile.TemporaryDirectory() as temp:
            base = pathlib.Path(temp)
            pam = base / 'pam'
            pam.mkdir()
            (pam / 'sudo_local').write_text('auth required foreign.so\n')
            (pam / 'sudo').write_text('auth required original.so\n')
            (pam / 'pam_tid.so.2').touch()
            bindir = base / 'bin'
            bindir.mkdir()
            for name, output in [('uname', 'Darwin'), ('sw_vers', '14.0')]:
                f = bindir / name
                f.write_text('#!/bin/bash\necho ' + output + '\n')
                f.chmod(0o755)
            for name in ('dirname', 'cut', 'grep', 'diff'):
                (bindir / name).symlink_to(shutil.which(name))
            script = (ROOT / 'scripts/setup_touchid_sudo.sh').read_text()
            script = script.replace('/etc/pam.d/sudo_local', str(pam / 'sudo_local'))
            script = script.replace('/etc/pam.d/sudo', str(pam / 'sudo'))
            script = script.replace('/usr/lib/pam/pam_tid.so.2', str(pam / 'pam_tid.so.2'))
            (base / 'scripts').mkdir()
            shutil.copytree(ROOT / 'lib', base / 'lib')
            shutil.copytree(ROOT / 'i18n', base / 'i18n')
            path = base / 'scripts/touchid.sh'
            path.write_text(script)
            env = dict(os.environ, PATH=str(bindir), HOME=temp)
            for args in ([], ['--uninstall']):
                result = subprocess.run(['/bin/bash', str(path), *args], env=env, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual((pam / 'sudo_local').read_text(), 'auth required foreign.so\n')

    def test_privilege_failure_after_consent_never_writes_pam(self):
        import tempfile, shutil, subprocess, os, pty
        with tempfile.TemporaryDirectory() as temp:
            base = pathlib.Path(temp)
            pam = base / 'pam'
            pam.mkdir()
            (pam / 'sudo').write_text('auth required original.so\n')
            (pam / 'pam_tid.so.2').touch()
            bindir = base / 'bin'
            bindir.mkdir()
            for name, body in [('uname', 'echo Darwin'), ('sw_vers', 'echo 14.0'),
                               ('sudo', 'echo "CALL:$*" >> "$TEST_LOG"; exit 1')]:
                tool = bindir / name
                tool.write_text('#!/bin/bash\n' + body + '\n')
                tool.chmod(0o755)
            for name in ('dirname', 'cut', 'grep', 'diff', 'date'):
                (bindir / name).symlink_to(shutil.which(name))
            script = (ROOT / 'scripts/setup_touchid_sudo.sh').read_text()
            script = script.replace('/etc/pam.d/sudo_local', str(pam / 'sudo_local'))
            script = script.replace('/etc/pam.d/sudo', str(pam / 'sudo'))
            script = script.replace('/usr/lib/pam/pam_tid.so.2', str(pam / 'pam_tid.so.2'))
            (base / 'scripts').mkdir()
            shutil.copytree(ROOT / 'lib', base / 'lib')
            shutil.copytree(ROOT / 'i18n', base / 'i18n')
            path = base / 'scripts/touchid.sh'
            path.write_text(script)
            (bindir / 'python3').symlink_to(sys.executable)
            log = base / 'log'
            env = dict(os.environ, PATH=str(bindir), HOME=temp, TEST_LOG=str(log))
            master, slave = pty.openpty()
            proc = subprocess.Popen(['/bin/bash', str(path)], env=env, stdin=slave, stdout=slave, stderr=slave)
            os.close(slave)
            os.write(master, b'y\n')
            proc.wait(timeout=5)
            os.close(master)
            self.assertEqual(proc.returncode, 1)
            self.assertEqual((pam / 'sudo').read_text(), 'auth required original.so\n')
            self.assertFalse((pam / 'sudo_local').exists())
            self.assertEqual(sum(line.startswith('CALL:') for line in log.read_text().splitlines()), 1)
            self.assertIn(' - ', log.read_text())
