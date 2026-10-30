"""Helper for subprocess environments in tests: strips PYTHONPATH so child shell processes do not inherit it."""
from __future__ import annotations

import os
from typing import Any


def shell_env(**extra: Any) -> dict[str, str]:
    """Return a copy of os.environ without PYTHONPATH, plus extra environment variables."""
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    for k, v in extra.items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = str(v)
    return env


_HOST_STUB_DIR: str | None = None
# Read-only on the host today, but a test must not depend on the real Homebrew/mas
# (its answer differs per Mac) or reach it at all. Exit 1 = "brew unavailable".
_HOST_STUBS = ("brew", "mas")


def host_stub_dir() -> str:
    """A per-process directory of failing stubs for host tools tests must not reach."""
    global _HOST_STUB_DIR
    if _HOST_STUB_DIR is None:
        import atexit
        import shutil
        import tempfile

        _HOST_STUB_DIR = tempfile.mkdtemp(prefix="mac_update_hoststub_")
        atexit.register(shutil.rmtree, _HOST_STUB_DIR, True)
        for tool in _HOST_STUBS:
            p = os.path.join(_HOST_STUB_DIR, tool)
            with open(p, "w", encoding="utf-8") as f:
                f.write("#!/bin/sh\nexit 1\n")
            os.chmod(p, 0o755)
    return _HOST_STUB_DIR


def isolate_host_tools(env: dict[str, str]) -> dict[str, str]:
    """Insert the stub dir between a test's own mock dirs and the inherited PATH.

    Test mocks prepended to os.environ["PATH"] still win; anything they do not
    mock resolves to a failing stub instead of the real host tool."""
    inherited = os.environ.get("PATH", "")
    path = env.get("PATH", inherited)
    stub = host_stub_dir()
    if inherited and path.endswith(inherited):
        env["PATH"] = path[: len(path) - len(inherited)] + stub + ":" + inherited
    else:
        env["PATH"] = stub + ":" + path
    return env
