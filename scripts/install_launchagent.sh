#!/usr/bin/env bash
# scripts/install_launchagent.sh — Install/manage launchd schedule for macOS Updates
# Usage:
#   bash scripts/install_launchagent.sh            # install / update
#   bash scripts/install_launchagent.sh --check    # status report
#   bash scripts/install_launchagent.sh --uninstall
#   bash scripts/install_launchagent.sh --day 1 --hour 9 --minute 30 (1=Mon..7=Sun)
#   bash scripts/install_launchagent.sh --once-in 5   # one-shot test run in 5 min
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="$(id -un)"
PLIST_LABEL="com.${USER_NAME}.macos-updates"
PLIST_PATH="${HOME}/Library/LaunchAgents/${PLIST_LABEL}.plist"

# launchd's default PATH lacks Homebrew; set one explicitly.
LAUNCHD_PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/bin:/bin:/usr/sbin:/sbin"

WEEKDAY=1  # 1 = Monday
HOUR=9     # 09:00 AM
MINUTE=0
ONCE_IN=""
RECURRING_SET=0

show_help() {
    cat <<EOF
Usage: bash scripts/install_launchagent.sh [OPTIONS]

Options:
  --check          Check status of installed LaunchAgent
  --uninstall      Remove LaunchAgent schedule
  --day N          Day of week (1=Monday .. 7=Sunday, default: 1)
  --hour N         Hour of day (0..23, default: 9)
  --minute N       Minute of hour (0..59, default: 0)
  --once-in N      One-shot test run N minutes from now (1..1440); fires once
                   at that wall-clock time. Exclusive with --day/--hour/--minute
  -h, --help       Show this help
EOF
}

MODE="install"
while [ $# -gt 0 ]; do
    case "$1" in
        --check)       MODE="check"; shift ;;
        --uninstall)   MODE="uninstall"; shift ;;
        --day)         WEEKDAY="${2:-1}"; RECURRING_SET=1; shift 2 ;;
        --hour)        HOUR="${2:-9}"; RECURRING_SET=1; shift 2 ;;
        --minute)      MINUTE="${2:-0}"; RECURRING_SET=1; shift 2 ;;
        --once-in)     ONCE_IN="${2:-}"; shift 2 ;;
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
            sch_hr=$(grep -A1 '<key>Hour</key>' "$PLIST_PATH" | grep -o '[0-9]*' | head -n 1)
            sch_min=$(grep -A1 '<key>Minute</key>' "$PLIST_PATH" | grep -o '[0-9]*' | head -n 1)
            sch_hr="${sch_hr:-0}"; sch_min="${sch_min:-0}"
            if grep -q '<key>Month</key>' "$PLIST_PATH"; then
                sch_mon=$(grep -A1 '<key>Month</key>' "$PLIST_PATH" | grep -o '[0-9]*' | head -n 1)
                sch_dom=$(grep -A1 '<key>Day</key>' "$PLIST_PATH" | grep -o '[0-9]*' | head -n 1)
                printf '   StartCalendarInterval: one-shot on %02d-%02d at %02d:%02d\n' \
                    "$((10#${sch_mon:-0}))" "$((10#${sch_dom:-0}))" "$((10#$sch_hr))" "$((10#$sch_min))"
            else
                sch_day=$(grep -A1 '<key>Weekday</key>' "$PLIST_PATH" | grep -o '[0-9]*' | head -n 1)
                printf '   StartCalendarInterval: Weekday %s at %02d:%02d\n' \
                    "${sch_day:-?}" "$((10#$sch_hr))" "$((10#$sch_min))"
            fi
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
        || true
    # No `unload -w` fallback: it leaves a persistent disabled override behind.
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

if ! [[ "$MINUTE" =~ ^([0-9]|[1-5][0-9])$ ]]; then
    echo "Error: --minute must be between 0 and 59, got $MINUTE" >&2
    exit 2
fi

CALENDAR_XML=""
SCHEDULE_DESC=""
if [ -n "$ONCE_IN" ]; then
    if [ "$RECURRING_SET" -eq 1 ]; then
        echo "Error: --once-in cannot be combined with --day/--hour/--minute" >&2
        exit 2
    fi
    if ! [[ "$ONCE_IN" =~ ^[0-9]+$ ]] || [ "$((10#$ONCE_IN))" -lt 1 ] || [ "$((10#$ONCE_IN))" -gt 1440 ]; then
        echo "Error: --once-in must be between 1 and 1440 minutes, got $ONCE_IN" >&2
        exit 2
    fi
    # "Now" is injectable for tests only. BSD date: -r <epoch> formats an epoch
    # in local time, so DST and month/year rollover are handled by the system.
    NOW_EPOCH="${MAC_UPDATE_LAUNCHAGENT_NOW_EPOCH:-$(date +%s)}"
    TARGET_EPOCH=$((NOW_EPOCH + 10#$ONCE_IN * 60))
    T_PARTS="$(date -r "$TARGET_EPOCH" "+%m %d %H %M")"
    # shellcheck disable=SC2086
    set -- $T_PARTS
    T_MON=$((10#$1)); T_DAY=$((10#$2)); T_HOUR=$((10#$3)); T_MIN=$((10#$4))
    CALENDAR_XML="        <key>Month</key>
        <integer>${T_MON}</integer>
        <key>Day</key>
        <integer>${T_DAY}</integer>
        <key>Hour</key>
        <integer>${T_HOUR}</integer>
        <key>Minute</key>
        <integer>${T_MIN}</integer>"
    SCHEDULE_DESC="$(printf 'one-shot, fires once on %02d-%02d at %02d:%02d (local time)' "$T_MON" "$T_DAY" "$T_HOUR" "$T_MIN")"
else
    CALENDAR_XML="        <key>Weekday</key>
        <integer>${WEEKDAY}</integer>
        <key>Hour</key>
        <integer>${HOUR}</integer>
        <key>Minute</key>
        <integer>${MINUTE}</integer>"
    SCHEDULE_DESC="$(printf 'Weekday %s at %02d:%02d' "$WEEKDAY" "$((10#$HOUR))" "$((10#$MINUTE))")"
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
${CALENDAR_XML}
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
echo "   Schedule: $SCHEDULE_DESC"
echo "   Plist: $PLIST_PATH"
