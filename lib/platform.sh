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

# Check if Rosetta 2 translation environment is installed and active.
mac_update_rosetta_installed() {
    if pgrep -q oahd 2>/dev/null || /usr/bin/pgrep -q oahd 2>/dev/null; then
        return 0
    fi
    if [ -d "/Library/Apple/usr/share/rosetta" ]; then
        return 0
    fi
    return 1
}

# Determine binary architecture of an app bundle using lipo.
# Outputs: arm64 | universal | x86_64-only | unknown
mac_update_app_architecture() {
    local app_path="$1"
    local info_plist="$app_path/Contents/Info.plist"
    local exe_name=""
    local exe_path=""
    local archs=""

    [ -d "$app_path" ] || { echo "unknown"; return 0; }

    if [ -f "$info_plist" ]; then
        exe_name="$(defaults read "$app_path/Contents/Info" CFBundleExecutable 2>/dev/null || true)"
    fi
    if [ -n "$exe_name" ] && [ -f "$app_path/Contents/MacOS/$exe_name" ]; then
        exe_path="$app_path/Contents/MacOS/$exe_name"
    elif [ -d "$app_path/Contents/MacOS" ]; then
        for f in "$app_path/Contents/MacOS"/*; do
            if [ -f "$f" ]; then
                exe_path="$f"
                break
            fi
        done
    fi

    if [ -z "$exe_path" ] || [ ! -f "$exe_path" ]; then
        echo "unknown"
        return 0
    fi

    archs="$(lipo -archs "$exe_path" 2>/dev/null || true)"
    case "$archs" in
        *arm64*x86_64*|*x86_64*arm64*|*arm64*i386*|*i386*arm64*)
            echo "universal"
            ;;
        *arm64*)
            echo "arm64"
            ;;
        *x86_64*|*i386*)
            echo "x86_64-only"
            ;;
        *)
            echo "unknown"
            ;;
    esac
}
