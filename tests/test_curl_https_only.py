"""Static guard: every real network fetch via curl must be https-only.

A redirect to plain http must never be followed (critical_rules.md §7/§15), so
each executed ``curl`` call carries ``--proto '=https'`` on its own line.
"""
from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

SKIP_PREFIXES = ("tests/", "skills/", "scratch/", "graphify-out/", ".claude/", "i18n/", "docs/")

# A curl invocation with options/URL: `curl -fsSL ...`, `curl --proto ...`.
CURL_CALL = re.compile(r"\bcurl\s+(-|https?://)")

# Explicit allowlist of non-fetch or user-run occurrences (substring -> reason).
ALLOW = (
    # Homebrew's official bootstrap one-liner: shown to the user, and run only
    # after interactive consent in setup/migration; it is a documented command.
    "Homebrew/install/HEAD/install.sh",
    # Version probe, performs no network access.
    "curl --version",
)


class CurlHttpsOnlyTests(unittest.TestCase):
    def test_every_real_curl_fetch_is_https_only(self) -> None:
        tracked = subprocess.run(
            ["git", "ls-files", "*.sh"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        ).stdout.split()
        offenders = []
        for rel in tracked:
            if rel.startswith(SKIP_PREFIXES):
                continue
            text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
            for n, line in enumerate(text.splitlines(), 1):
                if line.lstrip().startswith("#") or not CURL_CALL.search(line):
                    continue
                if any(a in line for a in ALLOW):
                    continue
                if "--proto" not in line:
                    offenders.append(f"{rel}:{n}: {line.strip()[:120]}")
        self.assertEqual(offenders, [], "curl without --proto '=https':\n" + "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()
