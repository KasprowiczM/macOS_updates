#!/usr/bin/env bash
# scripts/install_launchagent.sh — Install/manage launchd schedule for macOS Updates
# Usage:
#   bash scripts/install_launchagent.sh            # install / update
#   bash scripts/install_launchagent.sh --check    # status report
#   bash scripts/install_launchagent.sh --uninstall
#   bash scripts/install_launchagent.sh --day 1 --hour 9 (1=Mon..7=Sun, hour=0..23)
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="$(id -un)"
PLIST_LABEL="com.${USER_NAME}.macos-updates"
PLIST_PATH="${HOME}/Library/LaunchAgents/${PLIST_LABEL}.plist"

WEEKDAY=1  # 1 = Monday
HOUR=9     # 09:00 AM

show_help() {
    cat <<EOF
Usage: bash scripts/install_launchagent.sh [OPTIONS]

Options:
  --check          Check status of installed LaunchAgent
  --uninstall      Remove LaunchAgent schedule
  --day N          Day of week (1=Monday .. 7=Sunday, default: 1)
  --hour N         Hour of day (0..23, default: 9)
  -h, --help       Show this help
EOF
}

MODE="install"
while [ $# -gt 0 ]; do
    case "$1" in
        --check)       MODE="check"; shift ;;
        --uninstall)   MODE="uninstall"; shift ;;
        --day)         WEEKDAY="${2:-1}"; shift 2 ;;
        --hour)        HOUR="${2:-9}"; shift 2 ;;
        -h|--help)     show_help; exit 0 ;;
        *)             echo "Error: Unknown option $1" >&2; show_help >&2; exit 2 ;;
    esac
done

if [ "$MODE" = "check" ]; then
    if launchctl list | grep -q "$PLIST_LABEL"; then
        echo "✅ LaunchAgent is active: $PLIST_LABEL"
        echo "   Plist: $PLIST_PATH"
        if [ -f "$PLIST_PATH" ]; then
            sch_day=$(grep -A1 '<key>Weekday</key>' "$PLIST_PATH" | grep -o '[0-9]*' || echo "?")
            sch_hr=$(grep -A1 '<key>Hour</key>' "$PLIST_PATH" | grep -o '[0-9]*' || echo "?")
            echo "   StartCalendarInterval: Weekday $sch_day at ${sch_hr}:00"
        fi
        exit 0
    elif [ -f "$PLIST_PATH" ]; then
        echo "⚠️  LaunchAgent plist exists but is not loaded: $PLIST_PATH"
        exit 1
    else
        echo "ℹ️  LaunchAgent is not installed"
        exit 0
    fi
fi

if [ "$MODE" = "uninstall" ]; then
    if launchctl list | grep -q "$PLIST_LABEL"; then
        launchctl unload -w "$PLIST_PATH" 2>/dev/null || true
    fi
    rm -f "$PLIST_PATH"
    echo "✅ LaunchAgent uninstalled: $PLIST_LABEL"
    exit 0
fi

# Validation
if ! [[ "$WEEKDAY" =~ ^[1-7]$ ]]; then
    echo "Error: --day must be between 1 (Monday) and 7 (Sunday), got $WEEKDAY" >&2
    exit 2
fi

if ! [[ "$HOUR" =~ ^([0-9]|1[0-9]|2[0-3])$ ]]; then
    echo "Error: --hour must be between 0 and 23, got $HOUR" >&2
    exit 2
fi

# Install mode
mkdir -p "${HOME}/Library/LaunchAgents"
mkdir -p "$SCRIPT_DIR/logs"

cat <<PLISTEOF > "$PLIST_PATH"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DOCTYPE/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${SCRIPT_DIR}/update_all.sh</string>
        <string>-y</string>
        <string>--skip-system</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>MAC_UPDATE_NONINTERACTIVE</key>
        <string>1</string>
        <key>MAC_UPDATE_NOTIFY</key>
        <string>1</string>
    </dict>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>${WEEKDAY}</integer>
        <key>Hour</key>
        <integer>${HOUR}</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>${SCRIPT_DIR}/logs/launchd.out</string>
    <key>StandardErrorPath</key>
    <string>${SCRIPT_DIR}/logs/launchd.err</string>
</dict>
</plist>
PLISTEOF

chmod 644 "$PLIST_PATH"
launchctl unload -w "$PLIST_PATH" 2>/dev/null || true
launchctl load -w "$PLIST_PATH"

echo "✅ Installed and loaded LaunchAgent: $PLIST_LABEL"
echo "   Schedule: Weekday $WEEKDAY at $HOUR:00"
echo "   Plist: $PLIST_PATH"
