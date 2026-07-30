#!/usr/bin/env bash
# lib/github_release.sh — GitHub release tag lookup (Bash 3.2+)

github_latest_tag() {
    local repo="$1"
    local result
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
    echo "${result:-?}"
}
