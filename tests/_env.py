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
