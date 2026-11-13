"""Orchestrators must find Homebrew under launchd's minimal PATH (P0-2)."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MINIMAL_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"


def _run_bash(script: str, root: Path) -> subprocess.CompletedProcess:
    env = {
        "HOME": str(root),
        "PATH": MINIMAL_PATH,
        "MAC_UPDATE_HOMEBREW_PREFIX": str(root / "brewprefix"),
    }
    return subprocess.run(["/bin/bash", "-c", script], env=env, capture_output=True, text=True)


class HomebrewPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bindir = self.root / "brewprefix" / "bin"
        self.bindir.mkdir(parents=True)
        for tool in ("brew", "mas"):
            stub = self.bindir / tool
            stub.write_text("#!/bin/sh\necho stub-" + tool + " 9.9.9\n", encoding="utf-8")
            stub.chmod(0o755)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_platform_source_prepends_homebrew(self) -> None:
        r = _run_bash(
            f'. "{REPO_ROOT}/lib/platform.sh"; command -v brew; command -v mas; echo "$PATH"',
            self.root,
        )
        lines = r.stdout.splitlines()
        self.assertEqual(lines[0], str(self.bindir / "brew"), r.stderr)
        self.assertEqual(lines[1], str(self.bindir / "mas"))
        self.assertTrue(lines[2].startswith(str(self.bindir)))

    def test_does_not_duplicate_or_reorder_existing_path(self) -> None:
        script = (
            f'PATH="/custom/first:{self.bindir}:{MINIMAL_PATH}"; '
            f'. "{REPO_ROOT}/lib/platform.sh"; echo "$PATH"'
        )
        r = _run_bash(script, self.root)
        self.assertEqual(r.stdout.strip(), f"/custom/first:{self.bindir}:{MINIMAL_PATH}")

    def test_missing_prefix_leaves_path_untouched(self) -> None:
        script = f'MAC_UPDATE_HOMEBREW_PREFIX=/nonexistent; . "{REPO_ROOT}/lib/platform.sh"; echo "$PATH"'
        r = _run_bash(script, self.root)
        self.assertEqual(r.stdout.strip(), MINIMAL_PATH)

    def test_update_brew_finds_stub_brew_under_launchd_path(self) -> None:
        from tests._policy_fixtures import PolicyFixture
        import os
        import sys
        with PolicyFixture() as fixture:
            fixture.cask()
            prefix_bin=fixture.prefix/'bin'
            (prefix_bin/'python3').symlink_to(sys.executable)
            (prefix_bin/'ps').write_text('#!/bin/sh\nexit 0\n');(prefix_bin/'ps').chmod(0o755)
            os.environ['PATH']=MINIMAL_PATH
            os.environ['MAC_UPDATE_HOMEBREW_PREFIX']=str(fixture.prefix)
            result=fixture.run('update_brew.sh')
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual([c for c in fixture.calls() if c[0]=='upgrade'],[['upgrade','--cask','--appdir='+str(fixture.app.parent),'fixture']])
            self.assertTrue(fixture.results()[-1]['verified'])

    def test_every_orchestrator_sources_platform_before_first_brew_lookup(self) -> None:
        names = [
            "update_all.sh", "update_appstore.sh", "update_brew.sh", "update_npm_cli.sh",
            "update_internet_apps.sh", "update_system.sh", "build_inventory.sh",
            "migration_setup.sh", "setup.sh",
        ]
        for name in names:
            lines = (REPO_ROOT / name).read_text(encoding="utf-8").splitlines()
            src = next(
                i for i, ln in enumerate(lines) if ln.startswith('. "$SCRIPT_DIR/lib/platform.sh"')
            )
            for i, ln in enumerate(lines[:src]):
                if ln.lstrip().startswith("#"):
                    continue
                self.assertNotIn("command -v brew", ln, f"{name}:{i + 1}")
                self.assertNotIn("command -v mas", ln, f"{name}:{i + 1}")


if __name__ == "__main__":
    unittest.main()
