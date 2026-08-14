#!/usr/bin/env bash
# lib/version.sh — read package and application versions (Bash 3.2+)

mac_update_version() {
    local vf="${SCRIPT_DIR:-}/VERSION"
    if [ -f "$vf" ]; then
        tr -d '[:space:]' < "$vf"
    else
        echo "unknown"
    fi
}

# ── Canonical Application Version Reader ─────────────────────
# Read order: CFBundleShortVersionString → CFBundleVersion → mdls Spotlight metadata
# Cross-reference: lib/python/inventory.py installed_app_version()
app_version() {
    local app_path="$1" v=""
    v=$(defaults read "$app_path/Contents/Info" CFBundleShortVersionString 2>/dev/null \
        || defaults read "$app_path/Contents/Info" CFBundleVersion 2>/dev/null)
    if [ -z "$v" ]; then
        # Fallback for iOS/iPadOS apps on Apple Silicon (wrapped bundles, no
        # Contents/Info plist) and any odd bundle — read Spotlight metadata.
        v=$(mdls -name kMDItemVersion -raw "$app_path" 2>/dev/null)
        [ "$v" = "(null)" ] && v=""
    fi
    [ -n "$v" ] && echo "$v" || echo "${L_INTERNET_VERSION_UNKNOWN:-unknown}"
}

# Print "newer" only when the remote version is provably greater than the
# installed version. "current" includes equality and a local version ahead of
# the feed; "unknown" prevents replacement when either version is unparseable.
internet_version_relation() {
    python3 - "$1" "$2" <<'PYEOF'
import re
import sys


def version_key(value):
    match = re.search(r"\d+(?:\.\d+)*", value or "")
    if not match:
        return None
    numbers = [int(part) for part in match.group(0).split(".")]
    numbers = (numbers + [0] * 12)[:12]
    suffix = (value[match.end():] or "").lower().split("+", 1)[0]
    prerelease = suffix.lstrip("-._")
    prerelease_rank = 4
    for marker, rank in (("dev", 0), ("alpha", 1), ("a", 1), ("beta", 2), ("b", 2), ("rc", 3)):
        if prerelease.startswith(marker):
            prerelease_rank = rank
            break
    suffix_numbers = [int(part) for part in re.findall(r"\d+", suffix)]
    suffix_numbers = (suffix_numbers + [0] * 4)[:4]
    return tuple(numbers + [prerelease_rank] + suffix_numbers)


remote = version_key(sys.argv[1])
local = version_key(sys.argv[2])
if remote is None or local is None:
    print("unknown")
elif remote > local:
    print("newer")
else:
    print("current")
PYEOF
}
