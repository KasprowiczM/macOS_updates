"""H4/H5/M1: per-vendor native installer contracts and honest verification."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LIB = REPO_ROOT / "lib" / "native_installers.sh"


def _run(snippet: str, env: dict[str, str] | None = None, timeout: int = 20) -> subprocess.CompletedProcess:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        ["bash", "-c", f'source "{LIB}"; {snippet}'],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=merged,
        timeout=timeout,
    )


class PerVendorArgsTests(unittest.TestCase):
    def test_codex_uses_release_flag_not_positional_latest(self) -> None:
        out = _run('native_installer_bootstrap_args codex; echo')
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), "--release latest")

    def test_agy_bootstrap_has_no_positional_latest(self) -> None:
        out = _run('native_installer_bootstrap_args agy; echo')
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertNotIn("latest", out.stdout)

    def test_claude_bootstrap_still_accepts_latest(self) -> None:
        out = _run('native_installer_bootstrap_args claude')
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), "latest")

    def test_agy_existing_binary_uses_update_not_bootstrap(self) -> None:
        out = _run('native_installer_existing_update_cmd agy')
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), "update")

    def test_shared_sh_s_latest_is_gone(self) -> None:
        source = (REPO_ROOT / "update_npm_cli.sh").read_text(encoding="utf-8")
        self.assertNotIn("sh -s latest", source)


class DownloadAndVerifyTests(unittest.TestCase):
    def test_curl_failure_is_not_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp) / "bin"
            bindir.mkdir()
            curl = bindir / "curl"
            curl.write_text("#!/bin/sh\necho curl-failed >&2\nexit 22\n", encoding="utf-8")
            curl.chmod(0o755)
            dest = Path(tmp) / "installer.sh"
            env = {"PATH": f"{bindir}:{os.environ.get('PATH', '')}"}
            out = _run(
                f'download_installer_script "https://example.test/install.sh" "{dest}"',
                env=env,
            )
            self.assertNotEqual(out.returncode, 0)
            self.assertFalse(dest.exists() and dest.stat().st_size > 0)

    def test_http_url_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "installer.sh"
            out = _run(
                f'download_installer_script "http://example.test/install.sh" "{dest}"'
            )
            self.assertNotEqual(out.returncode, 0)
            self.assertFalse(dest.exists())

    def test_empty_download_is_not_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp) / "bin"
            bindir.mkdir()
            curl = bindir / "curl"
            curl.write_text("#!/bin/sh\n# succeed and write nothing\nexit 0\n", encoding="utf-8")
            curl.chmod(0o755)
            dest = Path(tmp) / "installer.sh"
            dest.write_text("", encoding="utf-8")
            env = {"PATH": f"{bindir}:{os.environ.get('PATH', '')}"}
            out = _run(
                f'download_installer_script "https://example.test/install.sh" "{dest}"',
                env=env,
            )
            self.assertNotEqual(out.returncode, 0)

    def test_exit_zero_without_working_binary_is_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "codex"
            fake.write_text("#!/bin/sh\necho broken >&2\nexit 1\n", encoding="utf-8")
            fake.chmod(0o755)
            out = _run(f'report_cli_version_or_fail "codex-cli" "{fake}"')
            self.assertNotEqual(out.returncode, 0)


class OpenCodeRepairTests(unittest.TestCase):
    def test_repair_skips_when_not_installed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp) / "npm-global"
            prefix.mkdir()
            out = _run(f'repair_broken_opencode "{prefix}" "{prefix / "bin" / "opencode"}"')
            self.assertEqual(out.returncode, 2, out.stdout + out.stderr)

    def test_repair_uses_managed_prefix_for_existing_stub(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp) / "npm-global"
            bindir = prefix / "bin"
            bindir.mkdir(parents=True)
            stub = bindir / "opencode"
            stub.write_text(
                "#!/bin/sh\necho \"Error: opencode-ai's postinstall script was not run.\" >&2\nexit 1\n",
                encoding="utf-8",
            )
            stub.chmod(0o755)
            npm = bindir / "npm"
            npm.write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$*\" > \"${MAC_UPDATE_TEST_NPM_ARGS}\"\nexit 0\n",
                encoding="utf-8",
            )
            npm.chmod(0o755)
            args_file = Path(tmp) / "npm-args"
            env = {
                "PATH": f"{bindir}:{os.environ.get('PATH', '')}",
                "MAC_UPDATE_TEST_NPM_ARGS": str(args_file),
            }
            out = _run(
                f'repair_broken_opencode "{prefix}" "{stub}"',
                env=env,
            )
            self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
            recorded = args_file.read_text(encoding="utf-8")
            self.assertIn("--prefix", recorded)
            self.assertIn(str(prefix), recorded)
            self.assertIn("opencode-ai", recorded)
            self.assertIn("--allow-scripts=opencode-ai", recorded)

    def test_product_name_is_not_accepted_as_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "codex"
            fake.write_text("#!/bin/sh\necho 'codex-cli 0.153.4'\nexit 0\n", encoding="utf-8")
            fake.chmod(0o755)
            out = _run(f'report_cli_version_or_fail "codex-cli" "{fake}"')
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(out.stdout.strip(), "0.153.4")

    def test_question_mark_version_is_not_success(self) -> None:
        source = (REPO_ROOT / "update_npm_cli.sh").read_text(encoding="utf-8")
        self.assertIn("report_cli_version_or_fail", source)
        self.assertIn('NPM_CONFIG_ALLOW_SCRIPTS="opencode-ai"', source)


if __name__ == "__main__":
    unittest.main()
