#!/usr/bin/env bash
# lib/fetch.sh — Bounded HTTPS downloads for vendor scripts and feeds.
# Bash 3.2 compatible. Not an orchestrator; sourced by callers.

fetch_to_file() {
    local url="$1"
    local dest="$2"
    local timeout_s="${3:-60}"
    local max_bytes="${4:-10485760}"
    local tmp=""

    if [ -z "$url" ] || [ -z "$dest" ]; then
        return 1
    fi
    case "$url" in
        https://*) ;;
        *) return 1 ;;
    esac
    tmp="${dest}.part"
    rm -f "$tmp" "$dest"
    if ! curl -fsSL --proto =https --proto-redir =https --max-filesize "$max_bytes" --max-time "$timeout_s" --retry 2 --retry-delay 1 \
        -o "$tmp" "$url"; then
        rm -f "$tmp"
        return 1
    fi
    if [ ! -s "$tmp" ]; then
        rm -f "$tmp"
        return 1
    fi
    if [ "$(wc -c < "$tmp" | tr -d ' ')" -gt "$max_bytes" ]; then
        rm -f "$tmp"
        return 1
    fi
    mv "$tmp" "$dest"
    return 0
}
