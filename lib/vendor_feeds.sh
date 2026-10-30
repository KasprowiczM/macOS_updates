#!/usr/bin/env bash
# lib/vendor_feeds.sh — vendor feeds lookup and config (Bash 3.2+)

_VENDOR_FEEDS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # = lib/

vendor_feed_config_path() {
    echo "$_VENDOR_FEEDS_DIR/../config/vendor_feeds.txt"
}

vendor_feed_row() {
    local app="$1" cfg row
    cfg="$(vendor_feed_config_path)"
    [ -f "$cfg" ] || return 1
    row=$(awk -F'|' -v a="$app" '
        /^[[:space:]]*#/ { next }
        { n = $1; gsub(/^[[:space:]]+|[[:space:]]+$/, "", n); if (n == a) { print; exit } }
    ' "$cfg" 2>/dev/null)
    [ -n "$row" ] || return 1
    printf "%s\n" "$row"
}

vendor_feed_lookup() {
    local app="$1" row
    row=$(vendor_feed_row "$app") || return 1
    local _app kind url arg artifact host
    IFS='|' read -r _app kind url arg artifact host <<EOF
$row
EOF
    [ -n "$url" ] || return 1

    local py_res
    py_res=$(curl -fsSL --max-time 15 --retry 2 "$url" 2>/dev/null | head -c 5242880 | \
        PYTHONPATH="$_VENDOR_FEEDS_DIR/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import sys
from vendor_feeds import evaluate_feed

kind = sys.argv[1]
arg = sys.argv[2]
os_ver = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else None
base_url = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] else None
body = sys.stdin.read()

res = evaluate_feed(kind, body, arg, os_version=os_ver, base_url=base_url)
if not res or not res.get("version"):
    sys.exit(1)

v = res.get("version") or "-"
u = res.get("url") or "-"
ck = res.get("checksum_kind") or "-"
cs = res.get("checksum") or "-"
policy = "rollout_hold" if res.get("rollout_hold") else "eligible"
print(f"{v}|{u}|{ck}|{cs}|{policy}")
' "$kind" "$arg" "$(sw_vers -productVersion 2>/dev/null)" "$url"
    )
    local rc=$?
    [ $rc -eq 0 ] && [ -n "$py_res" ] || return 1

    local v u ck cs policy
    IFS='|' read -r v u ck cs policy <<EOF_RESULT
$py_res
EOF_RESULT
    printf "%s|%s|%s|%s|%s|%s|%s\n" "$v" "$u" "$ck" "$cs" "${artifact:--}" "${host:--}" "$policy"
}

# Explicit appcast URL for an app (config/vendor_appcasts.txt); empty when none.
vendor_appcast_url() {
    local app="$1" cfg
    cfg="$_VENDOR_FEEDS_DIR/../config/vendor_appcasts.txt"
    [ -f "$cfg" ] || return 1
    awk -F'|' -v a="$app" '
        /^[[:space:]]*#/ { next }
        { n = $1; gsub(/^[[:space:]]+|[[:space:]]+$/, "", n);
          if (n == a) { u = $2; gsub(/^[[:space:]]+|[[:space:]]+$/, "", u); print u; exit } }
    ' "$cfg" 2>/dev/null
}

# Cross-check used when the primary vendor feed is OLDER than the installed app.
# Prints the channel in which the app's own Sparkle appcast publishes the installed
# version ("stable", "gradual-rollout", ... or "default") and returns 0; returns 1
# when it is not published there, the appcast is missing/unreachable, or its host is
# not the app's allowed host. Proof of "current" only: never an install target.
vendor_appcast_published_channel() {
    local app="$1" app_path="$2" row url host
    url="$(vendor_appcast_url "$app")" || return 1
    [ -n "$url" ] || return 1
    row="$(vendor_feed_row "$app")" || return 1
    host="$(printf '%s' "$row" | awk -F'|' '{ h = $6; gsub(/^[[:space:]]+|[[:space:]]+$/, "", h); print h }')"

    local short build
    short="$(defaults read "$app_path/Contents/Info" CFBundleShortVersionString 2>/dev/null || true)"
    build="$(defaults read "$app_path/Contents/Info" CFBundleVersion 2>/dev/null || true)"
    [ -n "$short" ] || return 1

    PYTHONPATH="$_VENDOR_FEEDS_DIR/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import sys
from vendor_feeds import appcast_url_allowed
sys.exit(0 if appcast_url_allowed(sys.argv[1], sys.argv[2]) else 1)
' "$url" "$host" || return 1

    local out
    out="$(curl -fsSL --max-time 15 --retry 2 "$url" 2>/dev/null | head -c 5242880 | \
        PYTHONPATH="$_VENDOR_FEEDS_DIR/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import sys
from vendor_feeds import appcast_publishes_installed
ch = appcast_publishes_installed(sys.stdin.read(), sys.argv[1], sys.argv[2] or None)
if ch is None:
    sys.exit(1)
print(ch or "default")
' "$short" "$build")" || return 1
    [ -n "$out" ] || return 1
    printf '%s\n' "$out"
}
