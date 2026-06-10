#!/usr/bin/env bash
# lib/version.sh — read package version (Bash 3.2+)

mac_update_version() {
    local vf="${SCRIPT_DIR:-}/VERSION"
    if [ -f "$vf" ]; then
        tr -d '[:space:]' < "$vf"
    else
        echo "unknown"
    fi
}
