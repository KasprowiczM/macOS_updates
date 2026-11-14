#!/usr/bin/env bash
# lib/github_release.sh — GitHub release tag lookup (Bash 3.2+)

_gh_diag() {
    command -v internet_diag_log >/dev/null 2>&1 && internet_diag_log "$@"
    return 0
}

# Outcome of the most recent api.github.com lookup, readable from a parent shell
# even when the lookup ran inside $(...): "cause|http|remaining|reset_epoch".
# cause: ok | ratelimit | http | network. Only kept when a session dir exists.
github_outcome_file() {
    [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && printf '%s' "$MAC_UPDATE_SESSION_DIR/github_last_outcome"
    return 0
}

github_last_outcome() {
    local f
    f="$(github_outcome_file)"
    [ -n "$f" ] && [ -f "$f" ] && cat "$f" 2>/dev/null
    return 0
}

# github_reset_time <epoch> -> local HH:MM ("?" when unusable)
github_reset_time() {
    case "$1" in ''|*[!0-9]*) printf '?'; return 0 ;; esac
    python3 -c 'import sys,time; print(time.strftime("%H:%M", time.localtime(int(sys.argv[1]))))' "$1" 2>/dev/null || printf '?'
}

# github_api_fetch <label> <url> <out_file>
# https-only GitHub API GET. Records HTTP status and the x-ratelimit-* headers in
# the internet diagnostics ("curl=... http=... remaining=...", the vendor-feed style)
# and in github_outcome_file, so a rate limit (403/429 with remaining 0 - 60/h
# without GITHUB_TOKEN) is told apart from a missing connection. 0 on a 2xx, 1 otherwise.
github_api_fetch() {
    local label="$1" url="$2" out="$3"
    local hdr="$out.hdr" rc http rem reset cause t0 t1 of
    t0=$(date +%s 2>/dev/null || echo 0)
    if [ -n "${GITHUB_TOKEN:-}" ]; then
        http="$(curl -sSL --proto '=https' --proto-redir '=https' --tlsv1.2 --max-time 20 --retry 2 --retry-delay 2 \
            -H "User-Agent: macos-updates-toolkit" -H "Authorization: Bearer $GITHUB_TOKEN" \
            -D "$hdr" -o "$out" -w '%{http_code}' "$url" 2>/dev/null)"
    else
        http="$(curl -sSL --proto '=https' --proto-redir '=https' --tlsv1.2 --max-time 20 --retry 2 --retry-delay 2 \
            -H "User-Agent: macos-updates-toolkit" \
            -D "$hdr" -o "$out" -w '%{http_code}' "$url" 2>/dev/null)"
    fi
    rc=$?
    t1=$(date +%s 2>/dev/null || echo 0)
    # -L may leave several header blocks; the last value is the final response's.
    rem="$(tr -d '\r' < "$hdr" 2>/dev/null | awk -F': *' 'tolower($1)=="x-ratelimit-remaining" {v=$2} END {print v}')"
    reset="$(tr -d '\r' < "$hdr" 2>/dev/null | awk -F': *' 'tolower($1)=="x-ratelimit-reset" {v=$2} END {print v}')"
    rm -f "$hdr"
    case "$http" in
        2??) cause=ok ;;
        429) cause=ratelimit ;;
        403) if [ "$rem" = "0" ]; then cause=ratelimit; else cause=http; fi ;;
        ''|000) cause=network ;;
        *) cause=http ;;
    esac
    of="$(github_outcome_file)"
    [ -n "$of" ] && printf '%s|%s|%s|%s\n' "$cause" "${http:-000}" "${rem:--}" "${reset:--}" > "$of" 2>/dev/null
    if [ "$cause" = "ok" ]; then
        _gh_diag "GitHub $label: lookup ok (curl=$rc http=$http remaining=${rem:--} reset=${reset:--} time=$((t1 - t0))s)"
        return 0
    fi
    _gh_diag "GitHub $label: lookup FAILED (curl=$rc http=${http:-000} remaining=${rem:--} reset=${reset:--} time=$((t1 - t0))s cause=$cause)"
    return 1
}

github_latest_tag() {
    local repo="$1"
    local result="" body
    body="$(mktemp "${TMPDIR:-/tmp}/ghapi.XXXXXX")" || { echo "?"; return 0; }
    if github_api_fetch "$repo" "https://api.github.com/repos/${repo}/releases/latest" "$body"; then
        result=$(python3 -c 'import json,sys
try:
    d=json.load(open(sys.argv[1]))
    print(d.get("tag_name","").strip() or "?")
except Exception:
    print("?")' "$body" 2>/dev/null)
    fi
    rm -f "$body"

    if [ -z "$result" ] || [ "$result" = "?" ]; then
        # Fallback: parse Location header redirect from github.com/owner/repo/releases/latest
        # (not the API, so it still works while the API rate limit is exhausted).
        local loc
        loc=$(curl -fssI --proto '=https' --proto-redir '=https' --tlsv1.2 --max-time 15 --retry 2 "https://github.com/${repo}/releases/latest" 2>/dev/null \
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
    local body
    body="$(mktemp "${TMPDIR:-/tmp}/ghapi.XXXXXX")" || return 0
    if github_api_fetch "$repo releases/tags/$tag" "https://api.github.com/repos/${repo}/releases/tags/${tag}" "$body"; then
        PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import json, sys
from vendor_feeds import dmg_package_revision
try:
    with open(sys.argv[6]) as fh:
        best = dmg_package_revision(json.load(fh), sys.argv[1], sys.argv[2], sys.argv[3])
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
' "$product" "$version" "$arch" "$installed_epoch" "$recorded" "$body" 2>/dev/null || true
    fi
    rm -f "$body"
}
