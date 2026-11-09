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

# launchd's default PATH lacks Homebrew; set one explicitly.
LAUNCHD_PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/bin:/bin:/usr/sbin:/sbin"

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
    CURRENT_UID="$(id -u)"
    if launchctl print "gui/${CURRENT_UID}/${PLIST_LABEL}" >/dev/null 2>&1 || launchctl list | grep -q "$PLIST_LABEL"; then
        echo "✅ LaunchAgent is active: $PLIST_LABEL"
        echo "   Plist: $PLIST_PATH"
        if [ -f "$PLIST_PATH" ]; then
            sch_day=$(grep -A1 '<key>Weekday</key>' "$PLIST_PATH" | grep -o '[0-9]*' || echo "?")
            sch_hr=$(grep -A1 '<key>Hour</key>' "$PLIST_PATH" | grep -o '[0-9]*' || echo "?")
            echo "   StartCalendarInterval: Weekday $sch_day at ${sch_hr}:00"
            if ! grep -A1 '<key>PATH</key>' "$PLIST_PATH" | grep -q '/opt/homebrew/bin'; then
                echo "⚠️  Plist has no EnvironmentVariables.PATH with Homebrew; scheduled runs cannot find brew/mas. Re-run: bash scripts/install_launchagent.sh"
            fi
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
    CURRENT_UID="$(id -u)"
    launchctl bootout "gui/${CURRENT_UID}/${PLIST_LABEL}" 2>/dev/null \
        || launchctl bootout "gui/${CURRENT_UID}" "$PLIST_PATH" 2>/dev/null \
        || launchctl unload -w "$PLIST_PATH" 2>/dev/null \
        || true
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
        <key>PATH</key>
        <string>${LAUNCHD_PATH}</string>
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
xattr -d com.apple.quarantine "$PLIST_PATH" 2>/dev/null || true

CURRENT_UID="$(id -u)"
# Remove a previous instance. bootout only: `unload -w` would persist a
# "disabled" override that can survive into the new install.
launchctl bootout "gui/${CURRENT_UID}/${PLIST_LABEL}" >/dev/null 2>&1 \
    || launchctl bootout "gui/${CURRENT_UID}" "$PLIST_PATH" >/dev/null 2>&1 \
    || true

# Clear any stale "disabled" override first, then bootstrap with a fallback to
# legacy load; keep stderr for diagnostics.
launchctl enable "gui/${CURRENT_UID}/${PLIST_LABEL}" >/dev/null 2>&1 || true
BOOT_ERR="$(launchctl bootstrap "gui/${CURRENT_UID}" "$PLIST_PATH" 2>&1)"
if [ $? -ne 0 ]; then
    BOOT_ERR_LEGACY="$(launchctl load -w "$PLIST_PATH" 2>&1)"
    BOOT_ERR="${BOOT_ERR}${BOOT_ERR_LEGACY:+
$BOOT_ERR_LEGACY}"
fi
launchctl enable "gui/${CURRENT_UID}/${PLIST_LABEL}" >/dev/null 2>&1 || true

# Never claim success without proof that the service is loaded.
if ! PRINT_OUT="$(launchctl print "gui/${CURRENT_UID}/${PLIST_LABEL}" 2>&1)"; then
    echo "❌ LaunchAgent was NOT loaded: $PLIST_LABEL" >&2
    [ -n "$BOOT_ERR" ] && echo "$BOOT_ERR" >&2
    [ -n "$PRINT_OUT" ] && echo "$PRINT_OUT" >&2
    echo "   Plist: $PLIST_PATH" >&2
    exit 1
fi

echo "✅ Installed and loaded LaunchAgent: $PLIST_LABEL"
echo "   Schedule: Weekday $WEEKDAY at $HOUR:00"
echo "   Plist: $PLIST_PATH"
