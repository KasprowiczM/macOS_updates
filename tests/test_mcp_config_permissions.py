"""M5: MCP config rewrites must keep private file modes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXER = REPO_ROOT / "scripts" / "fix_mcp_configs.py"


class McpConfigPermissionTests(unittest.TestCase):
    def test_umask_022_preserves_0600(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mcp.json"
            path.write_text(
                json.dumps({"mcpServers": {"demo": {"command": "npx"}}}) + "\n",
                encoding="utf-8",
            )
            os.chmod(path, 0o600)
            env = os.environ.copy()
            env["MAC_UPDATE_TOOLCHAIN_HOME"] = str(Path(tmp) / "toolchain")
            env["MAC_UPDATE_NPX_PATH"] = str(Path(tmp) / "toolchain" / "npx")
            (Path(tmp) / "toolchain").mkdir()
            (Path(tmp) / "toolchain" / "npx").write_text("#!/bin/sh\n", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(FIXER), str(path)],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
                env=env,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            mode = path.stat().st_mode & 0o777
            self.assertEqual(mode, 0o600, f"mode became {oct(mode)}")

    def test_failure_keeps_original(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mcp.json"
            original = json.dumps({"mcpServers": {"demo": {"command": "npx"}}}) + "\n"
            path.write_text(original, encoding="utf-8")
            os.chmod(path, 0o600)
            sys.path.insert(0, str(REPO_ROOT / "scripts"))
            import fix_mcp_configs as fixer  # noqa: E402

            def boom(*_args, **_kwargs):
                raise OSError("disk full")

            original_dump = fixer.json.dump
            try:
                fixer.json.dump = boom  # type: ignore[method-assign]
                ok = fixer.fix_mcp_config(str(path))
            finally:
                fixer.json.dump = original_dump  # type: ignore[method-assign]
            self.assertFalse(ok)
            self.assertEqual(path.read_text(encoding="utf-8"), original)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
