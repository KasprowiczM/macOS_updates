#!/usr/bin/env bash
# lib/github_release.sh — GitHub release tag lookup (Bash 3.2+)

github_latest_tag() {
    local repo="$1"
    local result
    result=$(curl -s --max-time 20 --retry 3 --retry-delay 2 \
        "https://api.github.com/repos/${repo}/releases/latest" 2>/dev/null \
        | python3 -c 'import json,sys
try:
    d=json.load(sys.stdin)
    print(d.get("tag_name","").strip() or "?")
except Exception:
    print("?")' 2>/dev/null)
    echo "${result:-?}"
}
