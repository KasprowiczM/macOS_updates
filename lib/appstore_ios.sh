#!/usr/bin/env bash
# lib/appstore_ios.sh — iOS / iPad apps detection and App Store lookup (Bash 3.2+)

_APPSTORE_IOS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

app_store_managed() {
    local app_path="$1"
    [ -n "$app_path" ] || return 1
    [ -f "$app_path/Wrapper/iTunesMetadata.plist" ] && return 0
    [ -d "$app_path/Contents/_MASReceipt" ] && return 0
    return 1
}

ios_apps_scan() {
    PYTHONPATH="$_APPSTORE_IOS_DIR/python${PYTHONPATH:+:$PYTHONPATH}" python3 - <<'PYEOF_IAS'
import os
import plistlib
from appstore_lookup import read_itunes_metadata

override = os.environ.get("MAC_UPDATE_APP_DIRS", "").strip()
if override:
    roots = [p for p in override.split(":") if p]
else:
    roots = ["/Applications", os.path.expanduser("~/Applications")]
seen = set()
for root in roots:
    if not os.path.isdir(root):
        continue
    try:
        entries = sorted(os.listdir(root), key=lambda x: x.casefold())
    except OSError:
        continue
    for e in entries:
        if not e.endswith(".app"):
            continue
        app_path = os.path.join(root, e)
        meta_path = os.path.join(app_path, "Wrapper", "iTunesMetadata.plist")
        if not os.path.isfile(meta_path):
            continue
        try:
            with open(meta_path, "rb") as f:
                data = read_itunes_metadata(f.read())
            if data:
                name = data.get("itemName") or e[:-4]
                item_id = data.get("itemId", "")
                ver = data.get("bundleShortVersionString", "")
                if item_id and item_id not in seen:
                    seen.add(item_id)
                    print(f"{name}|{item_id}|{ver}|{app_path}")
        except Exception:
            pass
PYEOF_IAS
}

ios_store_country() {
    if command -v mas >/dev/null 2>&1; then
        mas config --json 2>/dev/null | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    st = data.get("store", "")
    if st:
        print(st.lower().strip())
except Exception:
    pass
' 2>/dev/null || true
    fi
}

ios_apps_pending() {
    local scan
    scan="$(ios_apps_scan)"
    [ -n "$scan" ] || return 0

    local ids=""
    while IFS='|' read -r name item_id ver path; do
        [ -n "$item_id" ] || continue
        if [ -z "$ids" ]; then
            ids="$item_id"
        else
            ids="${ids},${item_id}"
        fi
    done <<EOF
$scan
EOF

    [ -n "$ids" ] || return 0

    local country
    country="$(ios_store_country)"
    local url="https://itunes.apple.com/lookup?id=${ids}"
    if [ -n "$country" ]; then
        url="${url}&country=${country}"
    fi

    local resp
    if ! resp="$(curl -fsS --max-time 20 "$url" 2>/dev/null)"; then
        return 2
    fi

    PYTHONPATH="$_APPSTORE_IOS_DIR/python${PYTHONPATH:+:$PYTHONPATH}" python3 - "$scan" "$resp" <<'PYEOF_IAP'
import sys
from appstore_lookup import parse_lookup, pending_ios

scan_text = sys.argv[1]
resp_text = sys.argv[2]

installed = []
for line in scan_text.splitlines():
    parts = line.strip().split("|")
    if len(parts) >= 4:
        installed.append({
            "name": parts[0],
            "itemId": parts[1],
            "version": parts[2],
            "path": parts[3],
        })

store = parse_lookup(resp_text)
pending = pending_ios(installed, store)
for p in pending:
    print(f"{p['name']}|{p['itemId']}|{p['installed']}|{p['store']}")
PYEOF_IAP
}
