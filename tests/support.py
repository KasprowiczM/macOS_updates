"""Test-only host command fixtures."""
from pathlib import Path


def mock_defaults(directory: Path) -> None:
    """Read fixture plists, and record every invocation in the fixture directory."""
    tool = directory / 'defaults'
    tool.write_text('''#!/usr/bin/env python3
import pathlib, plistlib, sys
with open(pathlib.Path(__file__).with_name("defaults.log"), "a") as log:
    log.write(repr(sys.argv[1:]) + "\\n")
try:
    if len(sys.argv) != 4 or sys.argv[1] != "read":
        sys.exit(1)
    path = pathlib.Path(sys.argv[2] + ".plist")
    with path.open("rb") as handle:
        value = plistlib.load(handle)[sys.argv[3]]
    print(value)
except (OSError, KeyError, ValueError):
    sys.exit(1)
''')
    tool.chmod(0o755)
