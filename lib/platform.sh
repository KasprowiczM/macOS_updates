#!/usr/bin/env bash
# lib/platform.sh — Apple Silicon (arm64) platform guard (Bash 3.2+)

# Require Apple Silicon. Exits 1 with a clear message on Intel or unknown arch.
mac_update_require_apple_silicon() {
    local arch
    arch="$(uname -m 2>/dev/null || echo unknown)"
    case "$arch" in
        arm64)
            return 0
            ;;
        x86_64|i386)
            echo "ERROR: macOS Updates requires Apple Silicon (arm64)." >&2
            echo "       Detected architecture: $arch" >&2
            echo "       This toolkit is not supported on Intel Macs." >&2
            return 1
            ;;
        *)
            echo "ERROR: Unsupported CPU architecture: $arch (Apple Silicon arm64 required)." >&2
            return 1
            ;;
    esac
}

# Human-readable platform label for APPLICATIONS.md templates.
mac_update_platform_label() {
    echo "Apple Silicon (arm64)"
}
