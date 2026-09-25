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
    from ._env import shell_env
except ImportError:
    from _env import shell_env

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
        # present-cask has its app installed, orphan-cask does not
        (self.fake_apps / "Present.app").mkdir()

        # Log calls to a file
        log_file = self.tmp / "brew_calls.log"

        brew_script = f"""
echo "$@" >> "{log_file}"
case "$1" in
    update) exit 0 ;;
    list)
        if [ "$2" = "--cask" ]; then
            echo "present-cask"
            echo "orphan-cask"
            exit 0
        fi
        ;;
    outdated)
        if [ "$2" = "--formula" ]; then exit 0; fi
        if [ "$2" = "--cask" ]; then
            echo "present-cask (1.0) < 1.1"
            echo "orphan-cask (2.0) < 2.1"
            exit 0
        fi
        ;;
    info)
        # return json for casks
        cat <<'EOF'
{{"casks":[
    {{"token":"present-cask","version":"1.1","installed":"1.0","artifacts":[{{"app":["Present.app"]}}]}},
    {{"token":"orphan-cask","version":"2.1","installed":"2.0","artifacts":[{{"app":["Orphan.app"]}}]}}
]}}
EOF
        exit 0
        ;;
    upgrade)
        exit 0
        ;;
esac
exit 0
"""
        self._make_brew_stub(brew_script)

        env = os.environ.copy()
        env["PATH"] = f"{self.bin_dir}:{env.get('PATH', '')}"
        env["MAC_UPDATE_SESSION_DIR"] = str(self.session_dir)
        env["MAC_UPDATE_YES"] = "1"
        env["HOME"] = str(self.tmp)

        proc = subprocess.run(
            ["bash", str(REPO_ROOT / "update_brew.sh")],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 1, msg=proc.stdout + proc.stderr)

        calls = log_file.read_text(encoding="utf-8") if log_file.is_file() else ""
        # Find upgrade --cask calls
        upgrade_lines = [l for l in calls.splitlines() if "upgrade --cask" in l]
        self.assertTrue(len(upgrade_lines) > 0, msg=f"No upgrade --cask found in: {calls}")
        for l in upgrade_lines:
            self.assertNotIn("orphan-cask", l)

        # brew_orphan_casks.txt should record orphan-cask
        orphan_file = self.session_dir / "brew_orphan_casks.txt"
        self.assertTrue(orphan_file.is_file())
        self.assertIn("orphan-cask", orphan_file.read_text(encoding="utf-8"))

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
        (self.fake_apps / "PkgApp.app").mkdir()
        log_file = self.tmp / "brew_upgrade_calls.log"

        brew_script = f"""
echo "$@" >> "{self.tmp / 'calls.log'}"
case "$1" in
    update) exit 0 ;;
    list)
        if [ "$2" = "--cask" ]; then
            echo "pkg-cask"
            exit 0
        fi
        ;;
    outdated)
        if [ "$2" = "--cask" ]; then
            echo "pkg-cask (1.0) < 1.1"
            exit 0
        fi
        exit 0
        ;;
    info)
        cat <<'EOF'
{{"casks":[
    {{"token":"pkg-cask","version":"1.1","installed":"1.0","artifacts":[{{"app":["PkgApp.app"]}},{{"pkg":["installer.pkg"]}}]}}
]}}
EOF
        exit 0
        ;;
    upgrade)
        echo "$@" >> "{log_file}"
        exit 0
        ;;
esac
exit 0
"""
        self._make_brew_stub(brew_script)

        env = os.environ.copy()
        env["PATH"] = f"{self.bin_dir}:{env.get('PATH', '')}"
        env["MAC_UPDATE_SESSION_DIR"] = str(self.session_dir)
        env["MAC_UPDATE_NO_SUDO"] = "1"
        env["MAC_UPDATE_YES"] = "1"
        env["HOME"] = str(self.tmp)

        proc = subprocess.run(
            ["bash", str(REPO_ROOT / "update_brew.sh")],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 10, msg=f"Expected exit 10 (soft fail), got {proc.returncode}. Output:\n{proc.stdout}\n{proc.stderr}")

        # verify pkg-cask was deferred
        sudo_file = self.session_dir / "brew_needs_interactive.txt"
        self.assertTrue(sudo_file.is_file())
        self.assertIn("pkg-cask", sudo_file.read_text(encoding="utf-8"))

        if log_file.is_file():
            self.assertNotIn("pkg-cask", log_file.read_text(encoding="utf-8"))

    def test_update_brew_downgrade_guard_blocks_upgrade(self) -> None:
        log_file = self.session_dir / "brew_calls.log"
        brew_script = f"""#!/usr/bin/env bash
case "$1" in
    outdated)
        echo "foo (2.0) < 1.0"
        exit 0
        ;;
    info)
        cat <<'EOF'
{{"casks":[
    {{"token":"foo","version":"1.0","installed":"2.0","artifacts":[{{"app":["Foo.app"]}}]}}
]}}
EOF
        exit 0
        ;;
    upgrade)
        echo "$@" >> "{log_file}"
        exit 0
        ;;
esac
exit 0
"""
        self._make_brew_stub(brew_script)
        env = shell_env(
            PATH=f"{self.bin_dir}:{os.environ.get('PATH', '')}",
            MAC_UPDATE_SESSION_DIR=str(self.session_dir),
            MAC_UPDATE_YES="1",
            MAC_UPDATE_LANG="en",
            HOME=str(self.tmp),
        )
        proc = subprocess.run(
            ["bash", str(REPO_ROOT / "update_brew.sh")],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertIn("downgrade", proc.stdout.lower() + proc.stderr.lower())
        if log_file.is_file():
            self.assertNotIn("upgrade --cask foo", log_file.read_text(encoding="utf-8"))

        # Case 2: installed < version -> upgrade --cask bar is in log
        if log_file.is_file():
            log_file.unlink()
        brew_script_up = f"""#!/usr/bin/env bash
case "$1" in
    outdated)
        echo "bar (1.0) < 2.0"
        exit 0
        ;;
    info)
        cat <<'EOF'
{{"casks":[
    {{"token":"bar","version":"2.0","installed":"1.0","artifacts":[{{"app":["Bar.app"]}}]}}
]}}
EOF
        exit 0
        ;;
    upgrade)
        echo "$@" >> "{log_file}"
        exit 0
        ;;
esac
exit 0
"""
        self._make_brew_stub(brew_script_up)
        (self.tmp / "Applications" / "Bar.app").mkdir(parents=True, exist_ok=True)
        proc2 = subprocess.run(
            ["bash", str(REPO_ROOT / "update_brew.sh")],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertTrue(log_file.is_file())
        self.assertIn("upgrade --cask bar", log_file.read_text(encoding="utf-8"))

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
        (self.tmp / "Applications" / "Brave Browser.app").mkdir(parents=True, exist_ok=True)
        log_file = self.session_dir / "brew_upgrade_calls.log"

        brew_script = f"""#!/usr/bin/env bash
case "$1" in
    update)
        exit 0
        ;;
    list)
        if [ "$2" = "--cask" ]; then
            echo "brave-browser"
            exit 0
        fi
        ;;
    outdated)
        if [ "$2" = "--formula" ]; then
            exit 0
        fi
        if [ "$2" = "--cask" ]; then
            for arg in "$@"; do
                if [ "$arg" = "--greedy-auto-updates" ]; then
                    echo "brave-browser (1.0) < 2.0"
                    exit 1
                fi
            done
            exit 0
        fi
        ;;
    info)
        cat <<'EOF'
{{"casks":[
    {{"token":"brave-browser","version":"2.0","installed":"1.0","artifacts":[{{"app":["Brave Browser.app"]}}]}}
]}}
EOF
        exit 0
        ;;
    upgrade)
        echo "$@" >> "{log_file}"
        exit 0
        ;;
esac
exit 0
"""
        self._make_brew_stub(brew_script)
        env = shell_env(
            PATH=f"{self.bin_dir}:{os.environ.get('PATH', '')}",
            MAC_UPDATE_SESSION_DIR=str(self.session_dir),
            MAC_UPDATE_YES="1",
            MAC_UPDATE_LANG="en",
            HOME=str(self.tmp),
        )
        proc = subprocess.run(
            ["bash", str(REPO_ROOT / "update_brew.sh")],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertTrue(log_file.is_file(), msg=f"Upgrade log file not found. stdout: {proc.stdout}\nstderr: {proc.stderr}")
        calls = log_file.read_text(encoding="utf-8")
        self.assertIn("upgrade --cask brave-browser", calls)


if __name__ == "__main__":
    unittest.main()

