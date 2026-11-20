"""Read-only Background Task Management (Login Items) state of an app from `sfltool dumpbtm` text.

macOS can keep an app's launcher "disallowed" in System Settings > General >
Login Items & Extensions; the app then closes right after opening. This module
only parses text: it never runs sfltool, never needs root and never changes BTM.
The result is "disallowed", "allowed" or "unknown" (anything unparsable).
"""

import re
import sys

_ITEM_START = re.compile(r"^\s*#\d+:\s*$")
_FIELD = re.compile(r"^\s*([A-Za-z ]+?):\s*(.*?)\s*$")


def _blocks(text):
    block = None
    for line in (text or "").splitlines():
        if _ITEM_START.match(line):
            if block is not None:
                yield block
            block = {}
            continue
        if block is None:
            continue
        m = _FIELD.match(line)
        if m and m.group(1) not in block:
            block[m.group(1)] = m.group(2)
    if block is not None:
        yield block


def _matches(identifier, bundle_id):
    ident = re.sub(r"^\d+\.", "", (identifier or "").strip())
    return ident == bundle_id or ident.startswith(bundle_id + ".")


def btm_state(dump_text, bundle_id):
    """"disallowed" when any item of the bundle id is disallowed, "allowed" when every
    matching item says allowed, otherwise "unknown"."""
    if not dump_text or not bundle_id or not re.match(r"^[A-Za-z0-9._-]+$", bundle_id):
        return "unknown"
    states = []
    for block in _blocks(dump_text):
        if not (_matches(block.get("Identifier"), bundle_id) or _matches(block.get("Bundle Identifier"), bundle_id)):
            continue
        disposition = block.get("Disposition", "").lower()
        tokens = {t.strip() for t in re.sub(r"[\[\]]|\(0x[0-9a-f]+\)", " ", disposition).replace(",", " ").split()}
        if "disallowed" in tokens:
            states.append("disallowed")
        elif "allowed" in tokens:
            states.append("allowed")
    if "disallowed" in states:
        return "disallowed"
    if states and all(s == "allowed" for s in states):
        return "allowed"
    return "unknown"


if __name__ == "__main__":
    print(btm_state(sys.stdin.read(), sys.argv[1] if len(sys.argv) > 1 else ""))
