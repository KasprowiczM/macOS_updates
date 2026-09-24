#!/usr/bin/env bash
# lib/vendor_feeds.sh — vendor feeds lookup and config (Bash 3.2+)

_VENDOR_FEEDS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # = lib/

vendor_feed_config_path() {
    echo "$_VENDOR_FEEDS_DIR/../config/vendor_feeds.txt"
}

vendor_feed_row() {
    local app="$1" cfg
    cfg="$(vendor_feed_config_path)"
    [ -f "$cfg" ] || return 1
    local escaped row
    escaped=$(printf '%s' "$app" | sed 's/[][\/.^$*]/\\&/g')
    row=$(grep -E "^[[:space:]]*${escaped}[[:space:]]*\\|" "$cfg" 2>/dev/null | head -n 1)
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
body = sys.stdin.read()

res = evaluate_feed(kind, body, arg, os_version=os_ver)
if not res or not res.get("version"):
    sys.exit(1)

v = res.get("version") or "-"
u = res.get("url") or "-"
ck = res.get("checksum_kind") or "-"
cs = res.get("checksum") or "-"
print(f"{v}|{u}|{ck}|{cs}")
' "$kind" "$arg" "$(sw_vers -productVersion 2>/dev/null)"
    )
    local rc=$?
    [ $rc -eq 0 ] && [ -n "$py_res" ] || return 1

    printf "%s|%s|%s\n" "$py_res" "${artifact:--}" "${host:--}"
}
