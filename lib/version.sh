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

# Compare an installed application's bundle version against a package manager's
# version string when the two may use different numbering schemes.
#
# Homebrew casks and the apps they ship do not always agree on the shape of a
# version. Brave's cask is "1.93.138.0" while the bundle reports
# "151.1.93.138" — the Chromium major prefixed to the same Brave version. A
# plain numeric comparison reads 151 > 1 and concludes the installed app is
# newer, which made the cask downgrade guard skip brave-browser on every run,
# permanently. The app was in fact at exactly the cask's version.
#
# Strategy: strip trailing zero segments, then look for the alignment offset at
# which the two segment lists share the longest run of equal leading values. A
# run of two or more is treated as the same scheme with a vendor prefix, and the
# comparison happens on the aligned tails. Without such a run the versions are
# not comparable and "unknown" is printed, so the caller can defer to the
# package manager's own record instead of inventing a downgrade.
#
# Prints "newer" (installed provably ahead of candidate), "current" (equal or
# behind) or "unknown" (not comparable).
app_vs_package_version_relation() {
    python3 - "$1" "$2" <<'PYEOF_AVP'
import re
import sys


def segments(value):
    match = re.search(r"\d+(?:\.\d+)*", value or "")
    if not match:
        return None
    parts = [int(p) for p in match.group(0).split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return parts


def leading_run(a, b, oa, ob):
    run = 0
    while oa + run < len(a) and ob + run < len(b) and a[oa + run] == b[ob + run]:
        run += 1
    return run


def prefix_offset(a, b):
    """Offsets at which one version carries an extra leading vendor segment.

    Only accepted when the shifted alignment agrees on strictly more leading
    segments than the natural offset does, so ordinary same-scheme pairs such
    as 4.15 and 4.17.1 are never realigned.
    """
    natural = leading_run(a, b, 0, 0)
    best = None
    for oa in range(len(a)):
        for ob in range(len(b)):
            if oa == 0 and ob == 0:
                continue
            run = leading_run(a, b, oa, ob)
            if run >= 2 and run > natural:
                candidate = (run, -(oa + ob), oa, ob)
                if best is None or candidate > best:
                    best = candidate
    return (best[2], best[3]) if best else None


def padded(values, width):
    return tuple((values + [0] * width)[:width])


installed = segments(sys.argv[1])
candidate = segments(sys.argv[2])

if installed is None or candidate is None:
    print("unknown")
    sys.exit(0)

if installed == candidate:
    print("current")
    sys.exit(0)

offsets = prefix_offset(installed, candidate)
if offsets is not None:
    installed = installed[offsets[0]:]
    candidate = candidate[offsets[1]:]
elif leading_run(installed, candidate, 0, 0) == 0 and len(installed) != len(candidate):
    # Nothing in common and a different shape: two unrelated schemes. Saying
    # "unknown" lets the caller fall back to the package manager's own record
    # instead of inventing a downgrade out of incomparable numbers.
    print("unknown")
    sys.exit(0)

width = max(len(installed), len(candidate))
print("newer" if padded(installed, width) > padded(candidate, width) else "current")
PYEOF_AVP
}
