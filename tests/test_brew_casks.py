"""Tests for Homebrew orphaned casks, sudo detection, and greedy upgrades (T9)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
try:
    from ._env import install_app_state_stubs, shell_env
except ImportError:
    from _env import install_app_state_stubs, shell_env

sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))  # explicit: simulates caller

from brew_casks import (
    app_targets,
    cask_guard_facts,
    cask_primary_app,
    cask_requires_sudo,
    find_orphan_casks,
    pkg_app_hints,
)


class BrewCasksPureTests(unittest.TestCase):
    def test_app_targets_string_and_dict(self) -> None:
        cask_str = {
            "token": "chrome",
            "artifacts": [{"app": ["Google Chrome.app"]}],
        }
        self.assertEqual(app_targets(cask_str), ["Google Chrome.app"])

        cask_dict = {
            "token": "custom",
            "artifacts": [{"app": [{"target": "Custom App.app"}]}],
        }
        self.assertEqual(app_targets(cask_dict), ["Custom App.app"])

        cask_mixed = {
            "token": "mixed",
            "artifacts": [
                {"binary": ["cli"]},
                {"app": ["First.app", {"target": "Second.app"}]},
            ],
        }
        self.assertEqual(app_targets(cask_mixed), ["First.app", "Second.app"])

    def test_cask_guard_facts_parses_and_joins_targets(self) -> None:
        raw = '{"casks": [{"token": "my-app", "version": "2.0", "installed": "1.0", "artifacts": [{"app": ["MyApp.app", "Helper.app"]}]}]}'
        self.assertEqual(cask_guard_facts(raw), "2.0|1.0|MyApp.app;Helper.app")

    def test_cask_guard_facts_pkg_cask_uses_delete_hint(self) -> None:
        raw = json.dumps({
            "casks": [{
                "token": "zoom",
                "version": "6.2.11.43576",
                "installed": "6.2.11.43576",
                "artifacts": [
                    {"pkg": ["zoomus.pkg"]},
                    {
                        "uninstall": [
                            {
                                "delete": [
                                    "/Applications/zoom.us.app",
                                    "/Library/Audio/Plug-Ins/HAL/ZoomAudioDevice.driver",
                                    "~/Library/Application Support/zoom.us",
                                ]
                            }
                        ]
                    }
                ],
            }]
        })
        facts = cask_guard_facts(raw)
        self.assertEqual(facts, "6.2.11.43576|6.2.11.43576|zoom.us.app")

    def test_orphan_detection_ignores_delete_hints(self) -> None:
        info_json = {
            "casks": [{
                "token": "zoom",
                "artifacts": [
                    {"pkg": ["zoomus.pkg"]},
                    {
                        "uninstall": [
                            {"delete": ["/Applications/zoom.us.app"]}
                        ]
                    }
                ]
            }]
        }
        orphans = find_orphan_casks(info_json, ["/Applications"], exists=lambda p: False)
        self.assertEqual(orphans, [], "Orphan detection must ignore delete hints")

    def test_cask_guard_facts_bad_json_is_empty(self) -> None:
        self.assertEqual(cask_guard_facts(""), "")
        self.assertEqual(cask_guard_facts("{bad json"), "")
        self.assertEqual(cask_guard_facts('{"casks": []}'), "")

    def test_cask_primary_app(self) -> None:
        raw = '{"casks": [{"token": "my-app", "artifacts": [{"app": ["Primary.app", "Secondary.app"]}]}]}'
        self.assertEqual(cask_primary_app(raw), "Primary.app")
        self.assertEqual(cask_primary_app('{"casks": [{"artifacts": []}]}'), "")
        self.assertEqual(cask_primary_app("not-json"), "")

    def test_orphan_when_all_targets_missing(self) -> None:
        info_json = {
            "casks": [
                {"token": "missing-app", "artifacts": [{"app": ["Missing.app"]}]},
                {"token": "present-app", "artifacts": [{"app": ["Present.app"]}]},
            ]
        }

        def mock_exists(path: str) -> bool:
            return "Present.app" in path

        orphans = find_orphan_casks(info_json, ["/Applications", "/Users/fake/Applications"], exists=mock_exists)
        self.assertEqual(orphans, ["missing-app"])

    def test_not_orphan_without_app_artifact(self) -> None:
        info_json = {
            "casks": [
                {"token": "cli-only", "artifacts": [{"binary": ["mycli"]}]},
                {"token": "pkg-only", "artifacts": [{"pkg": ["installer.pkg"]}]},
            ]
        }
        orphans = find_orphan_casks(info_json, ["/Applications"], exists=lambda p: False)
        self.assertEqual(orphans, [])

    def test_requires_sudo_pkg_and_launchctl(self) -> None:
        cask_pkg = {"artifacts": [{"pkg": ["tool.pkg"]}]}
        self.assertTrue(cask_requires_sudo(cask_pkg))

        cask_installer = {"artifacts": [{"installer": {"manual": "setup.app"}}]}
        self.assertTrue(cask_requires_sudo(cask_installer))

        cask_launchctl = {
            "artifacts": [
                {"app": ["Service.app"]},
                {"uninstall": [{"launchctl": "com.example.service"}]},
            ]
        }
        self.assertTrue(cask_requires_sudo(cask_launchctl))

        cask_pkgutil = {
            "artifacts": [
                {"uninstall": [{"pkgutil": "com.example.pkg"}]},
            ]
        }
        self.assertTrue(cask_requires_sudo(cask_pkgutil))

        cask_kext = {
            "artifacts": [
                {"uninstall": [{"kext": "com.example.kext"}]},
            ]
        }
        self.assertTrue(cask_requires_sudo(cask_kext))

        cask_normal = {
            "artifacts": [
                {"app": ["Normal.app"]},
                {"zap": [{"trash": "~/Library/Preferences/normal.plist"}]},
            ]
        }
        self.assertFalse(cask_requires_sudo(cask_normal))


class BrewCasksIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.bin_dir = self.tmp / "bin"
        self.bin_dir.mkdir()
        (self.bin_dir / "uname").write_text("#!/bin/sh\necho arm64\n", encoding="utf-8")
        (self.bin_dir / "uname").chmod(0o755)
        (self.bin_dir / "sw_vers").write_text("#!/bin/sh\necho 26.0\n", encoding="utf-8")
        (self.bin_dir / "sw_vers").chmod(0o755)
        install_app_state_stubs(self.bin_dir)
        self.session_dir = self.tmp / "session"
        self.session_dir.mkdir()
        self.fake_apps = self.tmp / "Applications"
        self.fake_apps.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_brew_stub(self, script_content: str) -> None:
        brew = self.bin_dir / "brew"
        brew.write_text(f"#!/bin/bash\n{script_content}\n", encoding="utf-8")
        brew.chmod(0o755)

    def test_update_brew_skips_orphan_cask(self) -> None:
        from tests._policy_fixtures import PolicyFixture
        for orphan in (False,True):
            with self.subTest(orphan=orphan), PolicyFixture() as fixture:
                fixture.cask(orphan=orphan)
                result=fixture.run('update_brew.sh')
                upgrades=[c for c in fixture.calls() if c[0]=='upgrade']
                if orphan:
                    self.assertEqual(result.returncode,10,result.stdout+result.stderr)
                    self.assertEqual(upgrades,[])
                    self.assertFalse(fixture.app.exists())
                    self.assertFalse(fixture.results()[-1]['verified'])
                else:
                    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                    self.assertEqual(upgrades,[['upgrade','--cask','--appdir='+str(fixture.app.parent),'fixture']])
                    self.assertEqual(fixture.results()[-1]['status'],'current_verified')
                self.assertFalse(any(c[0]=='uninstall' for c in fixture.calls()))

    def test_greedy_limited_to_designated_casks(self) -> None:
        log_file = self.tmp / "brew_outdated_calls.log"
        brew_script = f"""
echo "$@" >> "{log_file}"
if [ "$1" = "outdated" ] && [ "$2" = "--cask" ]; then
    if [ "$3" = "--greedy-auto-updates" ]; then
        echo "greedy-app (1.0) < 1.1"
    else
        echo "normal-app (2.0) < 2.1"
    fi
fi
exit 0
"""
        self._make_brew_stub(brew_script)

        env = os.environ.copy()
        env["PATH"] = f"{self.bin_dir}:{env.get('PATH', '')}"

        script = f"""
. "{REPO_ROOT}/lib/brew.sh"
brew_outdated_casks "greedy-app"
"""
        proc = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = proc.stdout.strip()
        self.assertIn("normal-app", out)
        self.assertIn("greedy-app", out)

        calls = log_file.read_text(encoding="utf-8")
        self.assertIn("outdated --cask --greedy-auto-updates greedy-app", calls)

    def test_no_sudo_defers_pkg_casks(self) -> None:
        from tests._policy_fixtures import PolicyFixture
        with PolicyFixture() as fixture:
            fixture.cask(extra_artifacts=[{'pkg':['installer.pkg']}])
            result=fixture.run('update_brew.sh')
            self.assertEqual(result.returncode,10,result.stdout+result.stderr)
            self.assertFalse(any(c[0]=='upgrade' for c in fixture.calls()))
            guards=[json.loads(line) for line in (fixture.session/'guard_results.jsonl').read_text().splitlines()]
            self.assertTrue(guards)
            self.assertTrue(all(not guard['allowed'] for guard in guards))
            self.assertEqual(fixture.results()[-1]['status'],'scan_partial')

    def test_update_brew_downgrade_guard_blocks_upgrade(self) -> None:
        from tests._policy_fixtures import PolicyFixture
        for latest,allowed in [('0.5.0',False),('2.0.0',True)]:
            with self.subTest(latest=latest), PolicyFixture() as fixture:
                fixture.cask(latest=latest)
                result=fixture.run('update_brew.sh')
                upgrades=[c for c in fixture.calls() if c[0]=='upgrade']
                self.assertEqual(bool(upgrades),allowed,result.stdout+result.stderr)
                self.assertEqual(result.returncode,0 if allowed else 10)
                outcome=fixture.results()[-1]
                if allowed:
                    self.assertEqual(outcome['after'],'2.0.0')
                    self.assertTrue(outcome['verified'])
                else:
                    self.assertEqual(outcome['reason_code'],'downgrade_or_version_unknown')
                    self.assertFalse(outcome['verified'])

    def test_brew_outdated_casks_rc1_empty_stderr_success(self) -> None:
        brew_script = """#!/usr/bin/env bash
if [ "$1" = "outdated" ] && [ "$2" = "--cask" ]; then
    echo "brave-browser"
    exit 1
fi
exit 0
"""
        self._make_brew_stub(brew_script)
        env = os.environ.copy()
        env["PATH"] = f"{self.bin_dir}:{env.get('PATH', '')}"

        script = f"""
. "{REPO_ROOT}/lib/brew.sh"
brew_outdated_casks "brave-browser"
"""
        proc = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, msg=f"Expected 0, got {proc.returncode}. stderr: {proc.stderr}")
        self.assertIn("brave-browser", proc.stdout)

    def test_brew_outdated_casks_rc1_progress_chatter_stderr_success(self) -> None:
        brew_script = """#!/usr/bin/env bash
if [ "$1" = "outdated" ] && [ "$2" = "--cask" ]; then
    echo "==> Downloading Homebrew API data" >&2
    echo "✔︎ JSON API packages.jws.json" >&2
    echo "brave-browser"
    exit 1
fi
exit 0
"""
        self._make_brew_stub(brew_script)
        env = os.environ.copy()
        env["PATH"] = f"{self.bin_dir}:{env.get('PATH', '')}"

        script = f"""
. "{REPO_ROOT}/lib/brew.sh"
brew_outdated_casks "brave-browser"
"""
        proc = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, msg=f"Expected 0, got {proc.returncode}. stderr: {proc.stderr}")
        self.assertIn("brave-browser", proc.stdout)

    def test_brew_outdated_casks_rc1_with_stderr_fails(self) -> None:
        brew_script = """#!/usr/bin/env bash
if [ "$1" = "outdated" ] && [ "$2" = "--cask" ]; then
    echo "Error: Cask 'x' is unavailable" >&2
    exit 1
fi
exit 0
"""
        self._make_brew_stub(brew_script)
        env = os.environ.copy()
        env["PATH"] = f"{self.bin_dir}:{env.get('PATH', '')}"

        script = f"""
. "{REPO_ROOT}/lib/brew.sh"
brew_outdated_casks "x"
"""
        proc = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Error: Cask 'x' is unavailable", proc.stderr)

    def test_brew_outdated_formulae_rc1_empty_stderr_success(self) -> None:
        log_file = self.tmp / "brew_formula_calls.log"
        brew_script = f"""#!/usr/bin/env bash
echo "$@" >> "{log_file}"
if [ "$1" = "outdated" ] && [ "$2" = "--formula" ]; then
    echo "wget"
    exit 1
fi
exit 0
"""
        self._make_brew_stub(brew_script)
        env = os.environ.copy()
        env["PATH"] = f"{self.bin_dir}:{env.get('PATH', '')}"

        script = f"""
. "{REPO_ROOT}/lib/brew.sh"
brew_outdated_formulae "wget"
"""
        proc = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, msg=f"Expected 0, got {proc.returncode}. stderr: {proc.stderr}")
        self.assertIn("wget", proc.stdout)
        self.assertIn("outdated --formula wget", log_file.read_text(encoding="utf-8"))

    def test_brew_outdated_formulae_rc1_progress_chatter_stderr_success(self) -> None:
        brew_script = """#!/usr/bin/env bash
if [ "$1" = "outdated" ] && [ "$2" = "--formula" ]; then
    echo "==> Downloading Homebrew API data" >&2
    echo "✔︎ JSON API packages.jws.json" >&2
    echo "wget"
    exit 1
fi
exit 0
"""
        self._make_brew_stub(brew_script)
        env = os.environ.copy()
        env["PATH"] = f"{self.bin_dir}:{env.get('PATH', '')}"

        script = f"""
. "{REPO_ROOT}/lib/brew.sh"
brew_outdated_formulae "wget"
"""
        proc = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, msg=f"Expected 0, got {proc.returncode}. stderr: {proc.stderr}")
        self.assertIn("wget", proc.stdout)

    def test_brew_outdated_formulae_rc1_with_stderr_fails(self) -> None:
        brew_script = """#!/usr/bin/env bash
if [ "$1" = "outdated" ] && [ "$2" = "--formula" ]; then
    echo "Error: Formula 'x' is unavailable" >&2
    exit 1
fi
exit 0
"""
        self._make_brew_stub(brew_script)
        env = os.environ.copy()
        env["PATH"] = f"{self.bin_dir}:{env.get('PATH', '')}"

        script = f"""
. "{REPO_ROOT}/lib/brew.sh"
brew_outdated_formulae "x"
"""
        proc = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Error: Formula 'x' is unavailable", proc.stderr)

    def test_update_brew_upgrades_greedy_cask_on_rc1_empty_stderr(self) -> None:
        # Eligibility now comes from the exact installed receipt and info row;
        # a broad outdated exit code cannot remove a concrete approved action.
        from tests._policy_fixtures import PolicyFixture
        with PolicyFixture() as fixture:
            fixture.cask()
            result=fixture.run('update_brew.sh')
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual([c for c in fixture.calls() if c[0]=='upgrade'],[['upgrade','--cask','--appdir='+str(fixture.app.parent),'fixture']])
            self.assertTrue(any(c[0]=='info' for c in fixture.calls()))
            self.assertFalse(any(c[0]=='outdated' for c in fixture.calls()))
            self.assertTrue(fixture.results()[-1]['verified'])

    def test_quit_and_signal_ids(self) -> None:
        from brew_casks import cask_quit_ids_facts, quit_bundle_ids
        cask = {"artifacts": [
            {"pkg": ["x.pkg"]},
            {"uninstall": [{"quit": ["com.a", "com.b"],
                            "signal": [["TERM", "com.c"], ["KILL", "com.a"]]}]},
        ]}
        self.assertEqual(quit_bundle_ids(cask), ["com.a", "com.b", "com.c"])
        self.assertEqual(quit_bundle_ids({"artifacts": [
            {"uninstall": [{"quit": "com.s"}]}]}), ["com.s"])
        self.assertEqual(quit_bundle_ids({"artifacts": [
            {"uninstall": [{"signal": ["TERM", "com.p"]}]}]}), ["com.p"])
        self.assertEqual(quit_bundle_ids({"artifacts": [{"font": ["F.ttf"]}]}), [])
        import json
        self.assertEqual(cask_quit_ids_facts(json.dumps({"casks": [cask]})), "com.a;com.b;com.c")
        self.assertEqual(cask_quit_ids_facts(json.dumps({"casks": [{"artifacts": []}]})), "")
        self.assertEqual(cask_quit_ids_facts("not json"), "UNREADABLE")
        self.assertEqual(cask_quit_ids_facts('{"casks": []}'), "UNREADABLE")
