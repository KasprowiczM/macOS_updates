"""WP3: running-app cask deferral, bounded prompts, brew doctor advisories.

Covers: P1-4 (a cask whose app is open or of unknown state is deferred, never
upgraded), P1-5 (mid-run prompts have a lifetime and a safe default; a parent
confirmation is not asked twice; the system step stays mandatory but bounded),
P1-6 (brew doctor advisories reach advisories.txt and the on-screen verdict).
"""
from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib" / "python"))
from _env import install_app_state_stubs, isolate_host_tools, shell_env  # noqa: E402
from brew_casks import doctor_advisories  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
LANGS = ("en", "pl", "es", "it", "pt", "de", "fr")

DOCTOR_SAMPLE = """Please note that these warnings are just used to help the Homebrew maintainers
with debugging if you file an issue.

Warning: Some installed formulae are deprecated or disabled.
You should find replacements for the following formulae:

  icu4c@78

Warning: Root certificates in /etc/ssl/cert.pem can trust compromised CAs.
Command-line tools using this file may accept forged TLS certificates:
  AAA Certificate Services
  emSign ECC Root CA - G3

Run this script to create a backup and remove these roots:
  sudo /opt/homebrew/Library/Homebrew/vendor/portable-ruby/bin/ruby fix.rb

For details and software update plans, see:
  https://support.apple.com/en-us/149555
"""


def _script(path: Path, body: str) -> None:
    path.write_text("#!/bin/bash\n" + body + "\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class DoctorAdvisoryParserTests(unittest.TestCase):
    def test_format_and_severity(self) -> None:
        lines = doctor_advisories(DOCTOR_SAMPLE)
        self.assertEqual(len(lines), 2)
        for line in lines:
            parts = line.split("|")
            self.assertEqual(len(parts), 3, line)  # no '|' inside the text
            self.assertEqual(parts[0], "brew_doctor")
            self.assertNotIn("\n", line)
            self.assertLessEqual(len(parts[2]), 240)
        self.assertEqual(lines[0].split("|")[1], "info")
        self.assertIn("deprecated", lines[0])
        self.assertIn("icu4c@78", lines[0])
        self.assertEqual(lines[1].split("|")[1], "security")
        self.assertIn("Root certificates", lines[1])
        self.assertIn("AAA Certificate Services", lines[1])
        self.assertNotIn("sudo", lines[1])
        self.assertNotIn("https://", lines[1])

    def test_pipe_stripped_and_length_capped(self) -> None:
        text = "Warning: " + "x|y " * 200 + "\n"
        (line,) = doctor_advisories(text)
        self.assertEqual(len(line.split("|")), 3)
        self.assertLessEqual(len(line.split("|", 2)[2]), 240)

    def test_no_warnings_no_advisories(self) -> None:
        self.assertEqual(doctor_advisories("Your system is ready to brew.\n"), [])
        self.assertEqual(doctor_advisories("Error: boom\n"), [])


class PromptHelperTests(unittest.TestCase):
    def _bash(self, script: str, stdin: str | None = "", env=None, timeout: int = 40):
        return subprocess.run(
            ["/bin/bash", "-c", f'. "{REPO_ROOT}/lib/ui.sh"\n{script}'],
            input=stdin, capture_output=True, text=True,
            env=env or shell_env(), timeout=timeout,
        )

    def test_timeout_value_is_clamped(self) -> None:
        cases = {"": "120", "abc": "120", "0": "0", "3": "10", "10": "10",
                 "300": "300", "5000": "900"}
        for raw, want in cases.items():
            res = self._bash("mac_update_prompt_timeout", env=shell_env(MAC_UPDATE_PROMPT_TIMEOUT=raw))
            self.assertEqual(res.stdout.strip(), want, raw)

    def test_typed_answers_and_enter_default(self) -> None:
        def rc(stdin, tdef, edef):
            res = self._bash(f"mac_update_prompt_yn 'q? ' {tdef} {edef}; echo rc=$?", stdin=stdin)
            return int(re.search(r"rc=(\d+)", res.stdout).group(1))
        self.assertEqual(rc("n\n", "y", "y"), 1)
        self.assertEqual(rc("y\n", "n", "n"), 0)
        self.assertEqual(rc("T\n", "n", "n"), 0)
        self.assertEqual(rc("\n", "n", "y"), 0)      # Enter -> enter default
        self.assertEqual(rc("", "n", "y"), 1)        # EOF never grants consent.
        self.assertEqual(rc("\n", "y", "n"), 1)
        self.assertEqual(rc("maybe\n", "y", "y"), 1)  # unrecognised is never yes

    def test_localized_yes_letters(self) -> None:
        def rc(stdin):
            res = self._bash(f"mac_update_prompt_yn 'q? ' n n; echo rc=$?", stdin=stdin)
            return int(re.search(r"rc=(\d+)", res.stdout).group(1))
        for letter in "yYtTjJsSoO":
            self.assertEqual(rc(letter + "\n"), 0, letter)
        for letter in "nN":
            self.assertEqual(rc(letter + "\n"), 1, letter)
        self.assertEqual(rc("x\n"), 1)

    def test_timeout_uses_default_and_says_so(self) -> None:
        # stdin stays open and silent for longer than the (minimum) 10 s limit.
        env = shell_env(MAC_UPDATE_PROMPT_TIMEOUT="10")
        res = subprocess.run(
            ["/bin/bash", "-c",
             f'. "{REPO_ROOT}/lib/ui.sh"\n'
             "sleep 14 | { mac_update_prompt_yn 'q? ' n y; echo rc=$? timed=$MAC_UPDATE_PROMPT_TIMED_OUT; }"],
            capture_output=True, text=True, env=env, timeout=40,
        )
        self.assertIn("rc=1 timed=1", res.stdout)
        self.assertIn("No answer within 10s", res.stdout)


class _BrewHarness(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        _script(self.bin / "uname", "echo arm64")
        _script(self.bin / "sw_vers", "echo 26.0")
        install_app_state_stubs(self.bin)
        self.session = self.tmp / "session"
        self.session.mkdir()
        self.apps = self.tmp / "Applications"
        self.apps.mkdir()
        self.log = self.tmp / "brew_calls.log"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def brew(self, casks: dict, doctor: str = "") -> None:
        """casks: token -> app name or None (no app target). All are outdated 1.0 < 2.0."""
        tokens = list(casks)
        docs = []
        for tok, app in casks.items():
            if app and app.startswith("["):
                art = app  # raw artifacts JSON
            else:
                art = f'[{{"app":["{app}"]}}]' if app else '[{"font":["F.ttf"]}]'
            docs.append(f'{{"token":"{tok}","version":"2.0","installed":"1.0","artifacts":{art}}}')
        (self.tmp / "info.txt").write_text(",".join(docs), encoding="utf-8")
        (self.tmp / "doctor.txt").write_text(doctor, encoding="utf-8")
        outdated = "\\n".join(f"{t} (1.0) < 2.0" for t in tokens)
        listing = "\\n".join(tokens)
        _script(self.bin / "brew", f'''
echo "$@" >> "{self.log}"
for last; do :; done
case "$1" in
  update) exit 0 ;;
  list) [ "$2" = "--cask" ] && printf "{listing}\\n"; exit 0 ;;
  outdated) [ "$2" = "--cask" ] && printf "{outdated}\\n"; exit 0 ;;
  info)
    one=""
    for a in "$@"; do case "$a" in --*|info) ;; *) one="$a" ;; esac; done
    if [ "$#" -gt 4 ]; then printf '{{"casks":[%s]}}' "$(cat "{self.tmp}/info.txt")"; exit 0; fi
    printf '{{"casks":[%s]}}' "$(cat "{self.tmp}/info.txt" | python3 -c "
import sys, json
tok = '$one'
d = json.loads('[' + sys.stdin.read() + ']')
print(json.dumps([c for c in d if c['token'] == tok][0]))")"
    exit 0 ;;
  doctor) cat "{self.tmp}/doctor.txt"; exit 0 ;;
  --prefix) echo "{self.tmp}/prefix"; exit 0 ;;
  --cache) echo "{self.tmp}/cache"; exit 0 ;;
esac
exit 0
''')

    def run_brew(self, stdin: str | None = "", **extra):
        env = isolate_host_tools(shell_env(
            PATH=f"{self.bin}:{os.environ.get('PATH', '')}",
            MAC_UPDATE_SESSION_DIR=str(self.session),
            MAC_LANG="en", HOME=str(self.tmp), **extra))
        return subprocess.run(["bash", str(REPO_ROOT / "update_brew.sh")], input=stdin,
                              env=env, capture_output=True, text=True, timeout=120)

    def upgraded(self) -> str:
        calls = self.log.read_text(encoding="utf-8") if self.log.exists() else ""
        return " ".join(l for l in calls.splitlines() if l.startswith("upgrade --cask"))


class CaskRunningDeferralTests(_BrewHarness):
    def test_running_unknown_idle_and_no_target(self) -> None:
        from tests._policy_fixtures import PolicyFixture
        for state in ('running','unknown','idle','opaque'):
            with self.subTest(state=state), PolicyFixture() as fixture:
                fixture.cask(extra_artifacts=[{'font':['F.ttf']}] if state=='opaque' else None)
                fixture.shell('ps','echo "'+str(fixture.app)+'/Contents/MacOS/Fixture"' if state=='running' else 'exit 1' if state=='unknown' else 'exit 0')
                result=fixture.run('update_brew.sh')
                upgrades=[c for c in fixture.calls() if c[0]=='upgrade']
                self.assertEqual(bool(upgrades),state=='idle',result.stdout+result.stderr)
                self.assertEqual(result.returncode,0 if state=='idle' else 10)
                self.assertEqual(fixture.results()[-1]['verified'],state=='idle')

    def test_pkg_cask_with_quit_ids(self) -> None:
        from tests._policy_fixtures import PolicyFixture
        for quit_id in ('fixture.running','fixture.unknown','fixture.idle'):
            with self.subTest(quit_id=quit_id), PolicyFixture() as fixture:
                fixture.cask(extra_artifacts=[{'pkg':['x.pkg']},{'uninstall':[{'quit':[quit_id],'pkgutil':'fixture.pkg'}]}])
                result=fixture.run('update_brew.sh')
                self.assertEqual(result.returncode,10,result.stdout+result.stderr)
                self.assertFalse(any(c[0]=='upgrade' for c in fixture.calls()))
                self.assertFalse(fixture.results()[-1]['verified'])

    def test_unreadable_cask_json_defers_no_target_cask(self) -> None:
        from tests._policy_fixtures import PolicyFixture
        with PolicyFixture() as fixture:
            fixture.cask()
            fixture.python(fixture.prefix/'bin/brew','import json,sys\n'+fixture._log_source()+"print('{invalid')\n")
            result=fixture.run('update_brew.sh')
            self.assertEqual(result.returncode,10,result.stdout+result.stderr)
            self.assertTrue(any(c[0]=='info' for c in fixture.calls()))
            self.assertFalse(any(c[0]=='upgrade' for c in fixture.calls()))
            self.assertFalse(fixture.results()[-1]['verified'])

    def test_deferred_casks_reach_run_summary(self) -> None:
        from run_summary import collect_run_items
        (self.session / "pending_brew_casks").write_text("3\n")
        (self.session / "brew_deferred_running.txt").write_text(
            "run-cask|Run.app\npkg-run|com.test.PkgRun\n")
        items = collect_run_items(self.session)
        by_id = {i["id"]: i for i in items if i["category"] == "brew_cask"}
        self.assertEqual(by_id["run-cask"]["status"], "pending")
        self.assertIn("Run.app", by_id["run-cask"]["details"])
        self.assertEqual(by_id["pkg-run"]["status"], "pending")
        self.assertEqual(by_id["brew_casks"]["details"], "1 updates pending")

    def test_only_running_cask_is_deferred_softly(self) -> None:
        from tests._policy_fixtures import PolicyFixture
        with PolicyFixture() as fixture:
            fixture.cask();fixture.shell('ps','echo "'+str(fixture.app)+'/Contents/MacOS/Fixture"')
            result=fixture.run('update_brew.sh')
            self.assertEqual(result.returncode,10,result.stdout+result.stderr)
            self.assertFalse(any(c[0]=='upgrade' for c in fixture.calls()))
            self.assertEqual(fixture.results()[-1]['reason_code'],'target_running')

    def test_not_running_is_upgraded(self) -> None:
        from tests._policy_fixtures import PolicyFixture
        with PolicyFixture() as fixture:
            fixture.cask();result=fixture.run('update_brew.sh')
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual([c for c in fixture.calls() if c[0]=='upgrade'],[['upgrade','--cask','--appdir='+str(fixture.app.parent),'fixture']])
            self.assertTrue(fixture.results()[-1]['verified'])


class BrewPromptTests(_BrewHarness):
    def test_parent_confirmed_skips_the_question(self) -> None:
        from tests._policy_fixtures import PolicyFixture
        for has_plan in (False,True):
            with self.subTest(has_plan=has_plan), PolicyFixture() as fixture:
                fixture.cask();os.environ['MAC_UPDATE_PARENT_CONFIRMED']='1'
                if not has_plan: os.environ.pop('MAC_UPDATE_PLAN_PATH',None)
                result=fixture.run('update_brew.sh')
                upgrades=[c for c in fixture.calls() if c[0]=='upgrade']
                self.assertEqual(bool(upgrades),has_plan,result.stdout+result.stderr)
                self.assertEqual(result.returncode,0 if has_plan else 10)

    def test_standalone_timeout_skips_upgrades_softly(self) -> None:
        from tests._policy_fixtures import PolicyFixture
        import time
        with PolicyFixture() as fixture:
            fixture.cask();os.environ.pop('MAC_UPDATE_PLAN_PATH',None)
            os.environ['MAC_UPDATE_PROMPT_TIMEOUT']='10'
            start=time.monotonic();result=fixture.run('update_brew.sh')
            self.assertEqual(result.returncode,10,result.stdout+result.stderr)
            self.assertLess(time.monotonic()-start,5,'missing authority must not wait for a leaf prompt')
            self.assertEqual(fixture.calls(),[])


class DoctorVerdictTests(_BrewHarness):
    def test_advisories_written_and_no_good_condition_line(self) -> None:
        # Health inspection is a separate read-only flow. Test the real shared
        # parser and persisted advisory contract without granting update scope.
        advisory_file=self.session/'advisories.txt'
        result=subprocess.run(['/bin/bash','-c','. "$1/lib/brew.sh"; brew_doctor_advisories > "$2"','doctor',str(REPO_ROOT),str(advisory_file)],input=DOCTOR_SAMPLE,capture_output=True,text=True,env=shell_env())
        self.assertEqual(result.returncode,0,result.stderr)
        lines=advisory_file.read_text().splitlines()
        self.assertEqual(len(lines),2)
        self.assertEqual([line.split('|')[1] for line in lines],['info','security'])
        from run_summary import read_advisories
        advisories=read_advisories(self.session)
        self.assertEqual(len(advisories),2)

    def test_clean_doctor_still_reports_good_condition(self) -> None:
        result=subprocess.run(['/bin/bash','-c','. "$1/lib/brew.sh"; brew_doctor_advisories','doctor',str(REPO_ROOT)],input='Your system is ready to brew.\n',capture_output=True,text=True,env=shell_env())
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout,'')
        self.assertFalse((self.session/'advisories.txt').exists())


class SystemPromptTests(unittest.TestCase):
    LISTING = ("Software Update Tool\n\nFinding available software\n"
               "Software Update found the following new or updated software:\n"
               "* Label: macOS Tahoe 26.7-25G229\n"
               "\tTitle: macOS Tahoe 26.7, Version: 26.7, Size: 1KiB, Recommended: YES, Action: restart, \n")

    def test_unanswered_prompt_lands_in_declined_branch(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        bindir = tmp / "bin"
        bindir.mkdir()
        sess = tmp / "session"
        sess.mkdir()
        log = tmp / "calls.log"
        _script(bindir / "uname", "echo arm64")
        _script(bindir / "sw_vers", 'if [ "$1" = "-productVersion" ]; then echo 26.6.2; else echo ProductVersion: 26.6.2; fi')
        _script(bindir / "sudo", f'echo "sudo $@" >> "{log}"; exit 0')
        _script(bindir / "softwareupdate", f'''echo "softwareupdate $@" >> "{log}"
if [ "$1" = "-l" ]; then cat <<'EOF'
{self.LISTING}
EOF
fi
exit 0''')
        env = shell_env(PATH=f"{bindir}:{os.environ['PATH']}", MAC_UPDATE_SESSION_DIR=str(sess),
                        MAC_UPDATE_YES="0", MAC_UPDATE_PARENT_CONFIRMED="1",
                        MAC_UPDATE_PROMPT_TIMEOUT="10", MAC_LANG="en")
        res = subprocess.run(
            ["/bin/bash", "-c", f'sleep 14 | bash "{REPO_ROOT}/update_system.sh"'],
            env=env, capture_output=True, text=True, timeout=90)
        out = res.stdout + res.stderr
        # The parent confirmation does not waive the (mandatory) system prompt.
        self.assertIn("Continue?", out)
        self.assertIn("No answer within 10s", out)
        self.assertEqual(res.returncode, 10, out)
        self.assertTrue((sess / "system_skipped_by_user").exists())
        self.assertNotIn("softwareupdate -i", log.read_text())


class AppStoreParentConfirmedTests(unittest.TestCase):
    def _run(self, stdin: str, **extra):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        bindir = tmp / "bin"
        bindir.mkdir()
        sess = tmp / "session"
        sess.mkdir()
        apps = tmp / "Applications"
        apps.mkdir()
        log = tmp / "mas.log"
        _script(bindir / "uname", "echo arm64")
        _script(bindir / "sw_vers", "echo 26.0")
        _script(bindir / "brew", "exit 0")
        _script(bindir / "osascript", "exit 0")
        _script(bindir / "sleep", "exit 0")
        _script(bindir / "sudo", 'if [ "$1" = "-v" ]; then exit 0; fi\n[ "$1" = "-n" ] && shift\nexec "$@"')
        _script(bindir / "mas", f'''echo "mas $@" >> "{log}"
case "$1" in
  version) echo 7.0.0 ;;
  list) echo "6446904124 Whisper Transcription (15.1.1)" ;;
  outdated) echo "6446904124 Whisper Transcription (15.1.1 -> 15.2.1)" ;;
esac
exit 0''')
        env = shell_env(PATH=f"{bindir}:{os.environ['PATH']}", MAC_UPDATE_SESSION_DIR=str(sess),
                        MAC_UPDATE_NONINTERACTIVE="1", MAC_UPDATE_APP_DIRS=str(apps),
                        MAC_LANG="en", **extra)
        env.pop("MAC_UPDATE_YES", None)
        env.pop("MAC_UPDATE_NO_SUDO", None)
        res = subprocess.run(["bash", str(REPO_ROOT / "update_appstore.sh")], input=stdin,
                             env=env, capture_output=True, text=True, timeout=120)
        return res, (log.read_text() if log.exists() else "")

    def test_standalone_prompt_cancels_but_parent_confirmed_skips_it(self) -> None:
        from tests._policy_fixtures import PolicyFixture
        for has_plan in (False,True):
            with self.subTest(has_plan=has_plan), PolicyFixture() as fixture:
                fixture.mas();os.environ['MAC_UPDATE_PARENT_CONFIRMED']='1'
                if not has_plan: os.environ.pop('MAC_UPDATE_PLAN_PATH',None)
                result=fixture.run('update_appstore.sh')
                self.assertEqual(result.returncode,0 if has_plan else 10,result.stdout+result.stderr)
                self.assertEqual(any(c[0]=='upgrade' for c in fixture.calls()),has_plan)
                self.assertFalse(any(c[0] in ('install','get','search') for c in fixture.calls()))


class StaticContractTests(unittest.TestCase):
    def read(self, rel: str) -> str:
        return (REPO_ROOT / rel).read_text(encoding="utf-8")

    def test_no_bare_read_prompts_left_in_the_three_scripts(self) -> None:
        for rel in ("update_brew.sh", "update_appstore.sh", "update_system.sh"):
            self.assertNotRegex(self.read(rel), r"read -r -p|read -r _resp", rel)

    def test_new_keys_exist_in_every_language(self) -> None:
        keys = ("L_PROMPT_TIMEOUT_FMT", "L_BREW_DRYRUN_MODE", "L_BREW_DRYRUN_WOULD_RUN_FULL",
                "L_BREW_DRYRUN_WOULD_RUN_UPGRADE", "L_BREW_UPDATE_TIMEOUT_SKIPPED",
                "L_BREW_DOCTOR_ADVISORIES_FMT", "L_BREW_DOCTOR_SECURITY_FMT",
                "L_BREW_DOCTOR_SKIPPED", "L_BREW_CASK_RUNNING_FMT")
        for lang in LANGS:
            text = self.read(f"i18n/lang_{lang}.sh")
            for key in keys:
                self.assertRegex(text, rf'(?m)^{key}="', f"{lang}:{key}")

    def test_system_step_keeps_softwareupdate_rules(self) -> None:
        text = self.read("update_system.sh")
        self.assertIn("-R", text)
        self.assertNotIn("softwareupdate -ia", text)


if __name__ == "__main__":
    unittest.main()
