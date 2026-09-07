"""L1: living docs must name the VERSION file, not a stale release number."""

from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

LIVING = [
    "README.md",
    "README.pl.md",
    "README.de.md",
    "README.fr.md",
    "README.es.md",
    "README.it.md",
    "README.pt.md",
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    "CODEX.md",
    "CONTRIBUTING.md",
    "docs/INSTALL.md",
    "docs/PUBLIC_RELEASE.md",
    "docs/user/INDEX.md",
    "docs/user/en/GUIDE.md",
    "docs/user/en/QUICK_START.md",
    "docs/user/pl/GUIDE.md",
    "docs/user/pl/QUICK_START.md",
    "docs/user/de/GUIDE.md",
    "docs/user/de/QUICK_START.md",
    "docs/user/fr/GUIDE.md",
    "docs/user/fr/QUICK_START.md",
    "docs/user/es/GUIDE.md",
    "docs/user/es/QUICK_START.md",
    "docs/user/it/GUIDE.md",
    "docs/user/it/QUICK_START.md",
    "docs/user/pt/GUIDE.md",
    "docs/user/pt/QUICK_START.md",
]


class VersionConsistencyTests(unittest.TestCase):
    def test_living_docs_mention_current_version(self) -> None:
        version = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f"## [{version}]", changelog)
        for rel in LIVING:
            path = REPO_ROOT / rel
            with self.subTest(rel=rel):
                self.assertTrue(path.is_file(), rel)
                text = path.read_text(encoding="utf-8")
                self.assertIn(version, text, f"{rel} does not mention {version}")

    def test_install_help_reads_version_file(self) -> None:
        text = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn("/VERSION", text)
        self.assertIn("MAC_UPDATE_REF", text)
        self.assertNotIn("1.0.21", text)


if __name__ == "__main__":
    unittest.main()
