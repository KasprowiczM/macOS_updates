#!/usr/bin/env bash
# lib/github_release.sh — GitHub release tag lookup (Bash 3.2+)

github_latest_tag() {
    local repo="$1"
    local result=""
    local auth_header=""
    if [ -n "${GITHUB_TOKEN:-}" ]; then
        auth_header="-H"
    fi
    result=$(curl -fsSL --max-time 20 --retry 3 --retry-delay 2 \
        -H "User-Agent: macos-updates-toolkit" \
        ${auth_header:+"$auth_header"} ${auth_header:+"Authorization: Bearer $GITHUB_TOKEN"} \
        "https://api.github.com/repos/${repo}/releases/latest" 2>/dev/null \
        | python3 -c 'import json,sys
try:
    d=json.load(sys.stdin)
    print(d.get("tag_name","").strip() or "?")
except Exception:
    print("?")' 2>/dev/null)

    if [ -z "$result" ] || [ "$result" = "?" ]; then
        # Fallback: parse Location header redirect from github.com/owner/repo/releases/latest
        local loc
        loc=$(curl -fssI --max-time 15 --retry 2 "https://github.com/${repo}/releases/latest" 2>/dev/null \
            | grep -i '^location:' | tr -d '\r' | awk -F'/' '{print $NF}')
        result="${loc:-?}"
    fi

    echo "${result:-?}"
}

# Package revision the toolkit last installed per product+version
# ("KeePassXC|2.8.0|1"). The bundle cannot tell a rebuild apart (same version,
# and ditto keeps the DMG's timestamps), so the install records it.
package_revision_file() {
    printf '%s' "${MAC_UPDATE_PACKAGE_REVISION_FILE:-$HOME/.local/state/mac-update/package_revisions.tsv}"
}

package_revision_recorded() {
    local f
    f="$(package_revision_file)"
    [ -f "$f" ] || return 0
    awk -F'|' -v p="$1" -v v="$2" '$1 == p && $2 == v { r = $3 } END { if (r != "") print r }' "$f" 2>/dev/null
}

package_revision_record() {
    local product="$1" version="$2" revision="$3" f dir tmp
    case "$revision" in ''|*[!0-9]*) return 1 ;; esac
    f="$(package_revision_file)"
    dir="$(dirname "$f")"
    mkdir -p "$dir" 2>/dev/null && chmod 700 "$dir" 2>/dev/null
    tmp="$(mktemp "$dir/.package_revisions.XXXXXX")" || return 1
    if [ -f "$f" ]; then
        awk -F'|' -v p="$product" '$1 != p' "$f" > "$tmp" 2>/dev/null
    fi
    printf '%s|%s|%s\n' "$product" "$version" "$revision" >> "$tmp"
    chmod 600 "$tmp" && mv -f "$tmp" "$f"
}

# github_rebuild_asset REPO TAG PRODUCT VERSION ARCH APP_PATH
# Prints the DMG asset name of a same-version package rebuild (e.g.
# KeePassXC-2.8.0-1-arm64.dmg) newer than what is installed; prints nothing
# otherwise. Installed revision: the recorded one (package_revision_record);
# without a record, a rebuild uploaded after the bundle's creation time counts
# as newer (at worst one redundant reinstall, which then records). Read-only.
github_rebuild_asset() {
    local repo="$1" tag="$2" product="$3" version="$4" arch="$5" app_path="$6"
    local installed_epoch recorded
    recorded="$(package_revision_recorded "$product" "$version")"
    installed_epoch="$(stat -f %B "$app_path" 2>/dev/null)"
    case "$installed_epoch" in ''|*[!0-9]*) return 0 ;; esac
    local auth_header=""
    [ -n "${GITHUB_TOKEN:-}" ] && auth_header="-H"
    curl -fsSL --max-time 20 --retry 2 --retry-delay 2 \
        -H "User-Agent: macos-updates-toolkit" \
        ${auth_header:+"$auth_header"} ${auth_header:+"Authorization: Bearer $GITHUB_TOKEN"} \
        "https://api.github.com/repos/${repo}/releases/tags/${tag}" 2>/dev/null \
        | PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import json, sys
from vendor_feeds import dmg_package_revision
try:
    best = dmg_package_revision(json.load(sys.stdin), sys.argv[1], sys.argv[2], sys.argv[3])
except Exception:
    best = None
recorded = sys.argv[5]
if best and best["revision"] > 0:
    if recorded.isdigit():
        newer = best["revision"] > int(recorded)
    else:
        newer = best["updated_epoch"] > int(sys.argv[4])
    if newer:
        print(best["name"])
' "$product" "$version" "$arch" "$installed_epoch" "$recorded" 2>/dev/null || true
}
