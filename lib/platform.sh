#!/usr/bin/env bash
# lib/platform.sh — supported macOS platform guards (Bash 3.2+)

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

# Require a supported macOS release. The optional argument is the minimum
# major version; project entrypoints use the supported baseline of macOS 13.
mac_update_require_macos_minimum() {
    local minimum_major="${1:-13}"
    local product_version
    local major_version

    case "$minimum_major" in
        ''|*[!0-9]*)
            echo "ERROR: Invalid minimum macOS major version: $minimum_major" >&2
            return 1
            ;;
    esac

    if ! command -v sw_vers >/dev/null 2>&1; then
        echo "ERROR: macOS Updates must run on macOS (sw_vers not found)." >&2
        return 1
    fi

    product_version="$(sw_vers -productVersion 2>/dev/null)"
    major_version="${product_version%%.*}"
    case "$major_version" in
        ''|*[!0-9]*)
            echo "ERROR: Unable to determine the macOS version (reported: ${product_version:-unknown})." >&2
            return 1
            ;;
    esac

    if [ "$major_version" -lt "$minimum_major" ]; then
        echo "ERROR: macOS Updates requires macOS $minimum_major or newer." >&2
        echo "       Detected macOS version: $product_version" >&2
        return 1
    fi

    return 0
}

# Canonical guard for public entrypoints.
mac_update_require_supported_platform() {
    mac_update_require_apple_silicon || return 1
    mac_update_require_macos_minimum 13 || return 1
}

# Human-readable platform label for APPLICATIONS.md templates.
mac_update_platform_label() {
    echo "Apple Silicon (arm64)"
}
