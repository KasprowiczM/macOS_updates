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


def _run_npm_cli(snippet: str, env: dict[str, str] | None = None, timeout: int = 20) -> subprocess.CompletedProcess:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    cmd = (
        f'eval "$(sed -e \'/mac_update_require_supported_platform/d\' -e \'/^print_header "🧰 Native CLI & npm"/,$d\' "{REPO_ROOT}/update_npm_cli.sh")"; '
        f'{snippet}'
    )
    return subprocess.run(
        ["bash", "-c", cmd],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=merged,
        timeout=timeout,
    )


class OnlyInstalledAndSelfUpdateTests(unittest.TestCase):
    def test_missing_native_cli_is_not_reinstalled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            home.mkdir()
            mock_bin = tmp_path / "bin"
            mock_bin.mkdir()
            curl_log = tmp_path / "curl_calls.log"
            curl = mock_bin / "curl"
            curl.write_text(f'#!/bin/sh\necho "$*" >> "{curl_log}"\nexit 0\n', encoding="utf-8")
            curl.chmod(0o755)

            env = {
                "HOME": str(home),
                "PATH": f"{mock_bin}:{os.environ.get('PATH', '')}",
                "MAC_UPDATE_BOOTSTRAP_CLI": "0",
            }
            res = _run_npm_cli('install_native_cli "codex-cli" "codex"', env=env)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertFalse(curl_log.exists(), "curl should not be called when native CLI is missing and not bootstrapping")

    def test_existing_codex_uses_update_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            local_bin = home / ".local" / "bin"
            local_bin.mkdir(parents=True)
            args_log = tmp_path / "codex_args.log"
            codex = local_bin / "codex"
            codex.write_text(
                f'#!/bin/sh\n'
                f'echo "$*" >> "{args_log}"\n'
                f'case "$*" in\n'
                f'  *--version*|-v*) echo "codex-cli 0.154.0"; exit 0 ;;\n'
                f'  *update*) echo "Updated to 0.154.0"; exit 0 ;;\n'
                f'esac\nexit 0\n',
                encoding="utf-8",
            )
            codex.chmod(0o755)

            env = {
                "HOME": str(home),
                "PATH": f"{local_bin}:{os.environ.get('PATH', '')}",
            }
            res = _run_npm_cli('install_native_cli "codex-cli" "codex"', env=env)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue(args_log.exists())
            logged = args_log.read_text(encoding="utf-8")
            self.assertIn("update", logged)

    def test_existing_agent_uses_update_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            local_bin = home / ".local" / "bin"
            local_bin.mkdir(parents=True)
            args_log = tmp_path / "agent_args.log"
            agent = local_bin / "agent"
            agent.write_text(
                f'#!/bin/sh\n'
                f'echo "$*" >> "{args_log}"\n'
                f'case "$*" in\n'
                f'  *--version*|-v*) echo "2026.09.20-abcdef12"; exit 0 ;;\n'
                f'  *update*) echo "Updated to 2026.09.20-abcdef12"; exit 0 ;;\n'
                f'esac\nexit 0\n',
                encoding="utf-8",
            )
            agent.chmod(0o755)

            env = {
                "HOME": str(home),
                "PATH": f"{local_bin}:{os.environ.get('PATH', '')}",
            }
            res = _run_npm_cli('install_native_cli "cursor-agent" "agent"', env=env)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue(args_log.exists())
            logged = args_log.read_text(encoding="utf-8")
            self.assertIn("update", logged)

    def test_bootstrap_flag_installs_missing_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            home.mkdir()
            mock_bin = tmp_path / "bin"
            mock_bin.mkdir()
            local_bin = home / ".local" / "bin"

            installer = tmp_path / "fake_installer.sh"
            installer.write_text(
                f'#!/bin/sh\n'
                f'mkdir -p "{local_bin}"\n'
                f'cat <<\'EOF\' > "{local_bin}/codex"\n'
                f'#!/bin/sh\n'
                f'echo "codex-cli 0.155.0"\n'
                f'exit 0\n'
                f'EOF\n'
                f'chmod 755 "{local_bin}/codex"\n'
                f'exit 0\n',
                encoding="utf-8",
            )

            curl = mock_bin / "curl"
            curl.write_text(
                f'#!/bin/sh\n'
                f'out=""\n'
                f'prev=""\n'
                f'for arg in "$@"; do\n'
                f'  if [ "$prev" = "-o" ]; then out="$arg"; fi\n'
                f'  prev="$arg"\n'
                f'done\n'
                f'if [ -n "$out" ]; then cp "{installer}" "$out"; fi\n'
                f'exit 0\n',
                encoding="utf-8",
            )
            curl.chmod(0o755)

            env = {
                "HOME": str(home),
                "PATH": f"{mock_bin}:{os.environ.get('PATH', '')}",
                "MAC_UPDATE_BOOTSTRAP_CLI": "1",
            }
            res = _run_npm_cli('install_native_cli "codex-cli" "codex"', env=env)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue((local_bin / "codex").exists())

    def test_npm_package_skipped_when_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            home.mkdir()
            mock_bin = tmp_path / "bin"
            mock_bin.mkdir()
            npm_log = tmp_path / "npm_calls.log"

            toolchain = home / ".local" / "share" / "mac-update"
            node_bin = toolchain / "node" / "bin"
            node_bin.mkdir(parents=True)
            (node_bin / "node").write_text("#!/bin/sh\necho v22.0.0\nexit 0\n", encoding="utf-8")
            (node_bin / "node").chmod(0o755)

            npm = node_bin / "npm"
            npm.write_text(f'#!/bin/sh\necho "$*" >> "{npm_log}"\nexit 0\n', encoding="utf-8")
            npm.chmod(0o755)

            manifest = tmp_path / "manifest.txt"
            manifest.write_text("pnpm|pnpm|npm||pnpm\n", encoding="utf-8")

            env = {
                "HOME": str(home),
                "PATH": f"{node_bin}:{mock_bin}:{os.environ.get('PATH', '')}",
                "MANIFEST_PATH": str(manifest),
                "MAC_UPDATE_BOOTSTRAP_CLI": "0",
            }
            res = _run_npm_cli('install_latest_npm_packages', env=env)
            self.assertEqual(res.returncode, 0, res.stderr)
            if npm_log.exists():
                self.assertNotIn("pnpm", npm_log.read_text(encoding="utf-8"), "npm install should not be called for pnpm")
            self.assertIn("pnpm", res.stdout)

    def test_bun_not_installed_when_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            home.mkdir()
            mock_bin = tmp_path / "bin"
            mock_bin.mkdir()
            curl_log = tmp_path / "curl_calls.log"
            curl = mock_bin / "curl"
            curl.write_text(f'#!/bin/sh\necho "$*" >> "{curl_log}"\nexit 0\n', encoding="utf-8")
            curl.chmod(0o755)

            env = {
                "HOME": str(home),
                "BUN_INSTALL": str(home / ".bun"),
                "BUN_BIN": str(home / ".bun" / "bin"),
                "PATH": f"{mock_bin}:{os.environ.get('PATH', '')}",
                "MAC_UPDATE_BOOTSTRAP_CLI": "0",
            }
            res = _run_npm_cli('ensure_latest_bun', env=env)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertFalse(curl_log.exists(), "curl should not be called to install bun when absent")


class PruneVendorCliVersionsTests(unittest.TestCase):
    def test_prune_keeps_current_and_one_previous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            releases = home / ".codex" / "packages" / "standalone" / "releases"
            releases.mkdir(parents=True)

            v1 = releases / "0.153.4-arm64-apple-darwin"
            v2 = releases / "0.154.0-arm64-apple-darwin"
            v3 = releases / "0.155.0-arm64-apple-darwin"
            v1.mkdir()
            (v1 / "dummy").write_text("hello", encoding="utf-8")
            os.utime(v1, (100, 100))

            v2.mkdir()
            (v2 / "dummy").write_text("world", encoding="utf-8")
            os.utime(v2, (200, 200))

            v3.mkdir()
            (v3 / "dummy").write_text("latest", encoding="utf-8")
            os.utime(v3, (300, 300))

            current = home / ".codex" / "packages" / "standalone" / "current"
            current.symlink_to(v3)

            env = {"HOME": str(home)}
            res = _run_npm_cli("prune_vendor_cli_versions", env=env)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue(v3.exists(), "current version must be kept")
            self.assertTrue(v2.exists(), "1 newest previous version must be kept")
            self.assertFalse(v1.exists(), "oldest version should be pruned")

    def test_prune_never_deletes_symlink_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            versions = home / ".local" / "share" / "cursor-agent" / "versions"
            versions.mkdir(parents=True)
            local_bin = home / ".local" / "bin"
            local_bin.mkdir(parents=True)

            v_old = versions / "2026.07.01-aaa111"
            v_mid = versions / "2026.08.01-bbb222"
            v_new = versions / "2026.09.01-ccc333"
            v_latest = versions / "2026.09.20-ddd444"

            for i, v in enumerate((v_old, v_mid, v_new, v_latest), start=1):
                v.mkdir()
                (v / "f").write_text("x", encoding="utf-8")
                os.utime(v, (i * 100, i * 100))

            (local_bin / "agent").symlink_to(v_old)
            (local_bin / "cursor-agent").symlink_to(v_latest)

            env = {"HOME": str(home)}
            res = _run_npm_cli("prune_vendor_cli_versions", env=env)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue(v_old.exists(), "symlink target v_old must NEVER be deleted")
            self.assertTrue(v_latest.exists(), "symlink target v_latest must NEVER be deleted")
            self.assertTrue(v_new.exists(), "1 newest non-protected version (v_new) must be kept")
            self.assertFalse(v_mid.exists(), "unprotected older version v_mid should be deleted")

    def test_prune_ignores_unexpected_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            releases = home / ".codex" / "packages" / "standalone" / "releases"
            releases.mkdir(parents=True)

            bad_dir = releases / "invalid-release-name"
            bad_dir.mkdir()
            bad_file = releases / "some_note.txt"
            bad_file.write_text("do not delete", encoding="utf-8")

            v1 = releases / "0.153.0-arm64-apple-darwin"
            v2 = releases / "0.154.0-arm64-apple-darwin"
            v3 = releases / "0.155.0-arm64-apple-darwin"
            for i, v in enumerate((v1, v2, v3), start=1):
                v.mkdir()
                os.utime(v, (i * 100, i * 100))

            current = home / ".codex" / "packages" / "standalone" / "current"
            current.symlink_to(v3)

            env = {"HOME": str(home)}
            res = _run_npm_cli("prune_vendor_cli_versions", env=env)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue(bad_dir.exists(), "unexpected directory must not be deleted")
            self.assertTrue(bad_file.exists(), "unexpected file must not be deleted")

    def test_prune_agy_old_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            local_bin = home / ".local" / "bin"
            local_bin.mkdir(parents=True)

            agy = local_bin / "agy"
            agy.write_text("#!/bin/sh\necho agy 1.0.0\nexit 0\n", encoding="utf-8")
            agy.chmod(0o755)

            old1 = local_bin / "agy.100.old"
            old2 = local_bin / "agy.200.old"
            other = local_bin / "other.100.old"
            old1.write_text("old binary 1", encoding="utf-8")
            old2.write_text("old binary 2", encoding="utf-8")
            other.write_text("other binary", encoding="utf-8")

            env = {"HOME": str(home)}
            res = _run_npm_cli("prune_vendor_cli_versions", env=env)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertFalse(old1.exists(), "agy.100.old should be pruned")
            self.assertFalse(old2.exists(), "agy.200.old should be pruned")
            self.assertTrue(other.exists(), "other.100.old must NOT be pruned")

            # Now test when agy is failing
            old3 = local_bin / "agy.300.old"
            old3.write_text("old binary 3", encoding="utf-8")
            agy.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")

            res2 = _run_npm_cli("prune_vendor_cli_versions", env=env)
            self.assertEqual(res2.returncode, 0, res2.stderr)
            self.assertTrue(old3.exists(), "agy old files must not be pruned when agy --version fails")

    def test_prune_cursor_agent_file_symlink_preserves_active_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            versions = home / ".local" / "share" / "cursor-agent" / "versions"
            versions.mkdir(parents=True)
            local_bin = home / ".local" / "bin"
            local_bin.mkdir(parents=True)

            v_a = versions / "2026.07.01-aaa111"
            v_b = versions / "2026.08.01-bbb222"
            v_c = versions / "2026.09.01-ccc333"

            for i, v in enumerate((v_a, v_b, v_c), start=1):
                v.mkdir()
                binary = v / "cursor-agent"
                binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                binary.chmod(0o755)
                os.utime(v, (i * 100, i * 100))

            # Active is oldest A (symlink points to executable file inside A)
            (local_bin / "agent").symlink_to(v_a / "cursor-agent")
            (local_bin / "cursor-agent").symlink_to(v_a / "cursor-agent")

            env = {"HOME": str(home)}
            res = _run_npm_cli("prune_vendor_cli_versions", env=env)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue(v_a.exists(), "active version A must be preserved")
            self.assertTrue(v_c.exists(), "newest version C must be preserved")
            self.assertFalse(v_b.exists(), "middle version B must be pruned")

    def test_prune_cursor_agent_active_newest_keeps_previous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            versions = home / ".local" / "share" / "cursor-agent" / "versions"
            versions.mkdir(parents=True)
            local_bin = home / ".local" / "bin"
            local_bin.mkdir(parents=True)

            v_a = versions / "2026.07.01-aaa111"
            v_b = versions / "2026.08.01-bbb222"
            v_c = versions / "2026.09.01-ccc333"

            for i, v in enumerate((v_a, v_b, v_c), start=1):
                v.mkdir()
                binary = v / "cursor-agent"
                binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                binary.chmod(0o755)
                os.utime(v, (i * 100, i * 100))

            # Active is newest C
            (local_bin / "agent").symlink_to(v_c / "cursor-agent")
            (local_bin / "cursor-agent").symlink_to(v_c / "cursor-agent")

            env = {"HOME": str(home)}
            res = _run_npm_cli("prune_vendor_cli_versions", env=env)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue(v_c.exists(), "active newest C must be preserved")
            self.assertTrue(v_b.exists(), "previous newest B must be preserved")
            self.assertFalse(v_a.exists(), "oldest A must be pruned")

    def test_prune_link_outside_root_aborts_pruning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            versions = home / ".local" / "share" / "cursor-agent" / "versions"
            versions.mkdir(parents=True)
            local_bin = home / ".local" / "bin"
            local_bin.mkdir(parents=True)

            v_a = versions / "2026.07.01-aaa111"
            v_b = versions / "2026.08.01-bbb222"
            v_a.mkdir()
            v_b.mkdir()

            outside = tmp_path / "outside-agent"
            outside.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            (local_bin / "cursor-agent").symlink_to(outside)

            env = {"HOME": str(home)}
            res = _run_npm_cli("prune_vendor_cli_versions", env=env)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue(v_a.exists(), "v_a must not be pruned when link points outside root")
            self.assertTrue(v_b.exists(), "v_b must not be pruned when link points outside root")

    def test_prune_codex_supports_dir_and_file_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            releases = home / ".codex" / "packages" / "standalone" / "releases"
            releases.mkdir(parents=True)
            pkg_root = home / ".codex" / "packages" / "standalone"

            v1 = releases / "0.153.0-arm64-apple-darwin"
            v2 = releases / "0.154.0-arm64-apple-darwin"
            v3 = releases / "0.155.0-arm64-apple-darwin"
            for i, v in enumerate((v1, v2, v3), start=1):
                (v / "bin").mkdir(parents=True)
                (v / "bin" / "codex").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                os.utime(v, (i * 100, i * 100))

            # current pointing to bin/codex inside oldest v1
            current = pkg_root / "current"
            current.symlink_to(v1 / "bin" / "codex")

            env = {"HOME": str(home)}
            res = _run_npm_cli("prune_vendor_cli_versions", env=env)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue(v1.exists(), "v1 active via file symlink must be preserved")
            self.assertTrue(v3.exists(), "v3 newest must be preserved")
            self.assertFalse(v2.exists(), "v2 must be pruned")

    def test_native_clis_update_when_node_is_absent(self) -> None:
        """When managed Node is absent (NODE_READY=0), native CLIs like claude still update."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            home = tmp_path / "home"
            local_bin = home / ".local" / "bin"
            local_bin.mkdir(parents=True)
            claude_log = tmp_path / "claude_calls.log"
            claude = local_bin / "claude"
            claude.write_text(
                f'#!/bin/sh\n'
                f'echo "$*" >> "{claude_log}"\n'
                f'case "$*" in\n'
                f'  *--version*|-v*) echo "1.2.3"; exit 0 ;;\n'
                f'  *update*) echo "updated"; exit 0 ;;\n'
                f'esac\nexit 0\n',
                encoding="utf-8",
            )
            claude.chmod(0o755)

            mock_bin = tmp_path / "bin"
            mock_bin.mkdir()
            (mock_bin / "uname").write_text("#!/bin/sh\necho arm64\n", encoding="utf-8")
            (mock_bin / "uname").chmod(0o755)
            (mock_bin / "sw_vers").write_text("#!/bin/sh\necho 26.0\n", encoding="utf-8")
            (mock_bin / "sw_vers").chmod(0o755)
            npm_log = tmp_path / "npm_calls.log"
            npm = mock_bin / "npm"
            npm.write_text(f'#!/bin/sh\necho "$*" >> "{npm_log}"\nexit 0\n', encoding="utf-8")
            npm.chmod(0o755)

            manifest = tmp_path / "manifest.txt"
            manifest.write_text("Claude Code||native-installer||claude\npnpm|pnpm|npm||pnpm\n", encoding="utf-8")

            from tests._env import shell_env
            env = shell_env(
                HOME=str(home),
                PATH=f"{local_bin}:{mock_bin}:{os.environ.get('PATH', '')}",
                MANIFEST_PATH=str(manifest),
                MAC_UPDATE_BOOTSTRAP_CLI="0",
                MAC_UPDATE_DRY_RUN="0",
            )
            res = subprocess.run(
                ["bash", str(REPO_ROOT / "update_npm_cli.sh")],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
                env=env,
                timeout=20,
            )
            self.assertTrue(claude_log.exists(), f"claude was not called. Output: {res.stdout}\nStderr: {res.stderr}")
            self.assertIn("update", claude_log.read_text(encoding="utf-8"))
            self.assertFalse(npm_log.exists(), "npm should not be called when Node is absent")


if __name__ == "__main__":
    unittest.main()

