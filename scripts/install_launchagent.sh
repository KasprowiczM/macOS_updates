#!/usr/bin/env bash
# scripts/install_launchagent.sh — Install/manage the launchd schedule for macOS Updates
# Usage:
#   bash scripts/install_launchagent.sh                       # weekly, Monday 09:00
#   bash scripts/install_launchagent.sh --daily 09:00         # every day
#   bash scripts/install_launchagent.sh --days 1,3,5 --daily 08:30
#   bash scripts/install_launchagent.sh --at-login --delay-min 5
#   bash scripts/install_launchagent.sh --day 1 --hour 9 --minute 30 (1=Mon..7=Sun)
#   bash scripts/install_launchagent.sh --once-in 5           # one-shot test run, own label
#   bash scripts/install_launchagent.sh --check | --status [--json] | --uninstall
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="$(id -un)"
# User-independent labels. The regular schedule and a one-shot test run are
# separate jobs, so --once-in never replaces the regular schedule.
PLIST_LABEL="site.64bit.mac-update.daily"
ONCE_LABEL="site.64bit.mac-update.once"
LEGACY_LABEL="com.${USER_NAME}.macos-updates"
AGENT_DIR="${HOME}/Library/LaunchAgents"
PLIST_PATH="${AGENT_DIR}/${PLIST_LABEL}.plist"
ONCE_PATH="${AGENT_DIR}/${ONCE_LABEL}.plist"
LEGACY_PATH="${AGENT_DIR}/${LEGACY_LABEL}.plist"
[ -f "$SCRIPT_DIR/lib/paths.sh" ] && . "$SCRIPT_DIR/lib/paths.sh"
STATE_DIR="$(mu_state_dir 2>/dev/null || printf '%s' "${MAC_UPDATE_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/mac-update}")"
LOG_DIR="${STATE_DIR}/logs"

# launchd's default PATH lacks Homebrew; cover Apple Silicon and Intel.
LAUNCHD_PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/local/sbin:/usr/bin:/bin:/usr/sbin:/sbin"

WEEKDAY=""      # set by --day
DAYS=""         # set by --days
HOUR=9
MINUTE=0
DAILY=0
AT_LOGIN=0
DELAY_MIN=0
SYSTEM_UPDATES=0
NOTIFY_MODE="needs_you"   # --silent (default): notify only when something needs you
ONCE_IN=""
TIME_SET=0
ASSUME_YES=0
JSON=0

show_help() {
    cat <<EOF
Usage: bash scripts/install_launchagent.sh [OPTIONS]

Schedule:
  --day N          Day of week (1=Monday .. 7=Sunday, default: 1)
  --days N,N,...   Several weekdays, e.g. 1,3,5
  --hour N         Hour of day (0..23, default: 9)
  --minute N       Minute of hour (0..59, default: 0)
  --daily HH:MM    Run every day at HH:MM (combine with --days to limit days)
  --at-login       Also run when you log in (RunAtLoad)
  --delay-min N    After login wait until N minutes of session time (0..240)
  --once-in N      One-shot test run N minutes from now (1..1440), own label;
                   the regular schedule stays. Exclusive with the schedule flags
Behaviour:
  --silent         Notify only when something needs you or failed (default)
  --no-silent      Notify after every run that did something
  --notify MODE    always | needs_you | never
  --system-updates Let scheduled runs install macOS updates too (default: off;
                   sets MAC_UPDATE_AUTOMATION_SYSTEM_UPDATES=1 in the job)
  -y, --yes        Replace a legacy schedule without asking
Management:
  --check          Status report
  --status [--json] Status; --json is machine-readable
  --uninstall      Remove every mac-update LaunchAgent (regular, one-shot, legacy)
  -h, --help       Show this help
EOF
}

die() { echo "Error: $1" >&2; exit 2; }

MODE="install"
while [ $# -gt 0 ]; do
    case "$1" in
        --check)       MODE="check"; shift ;;
        --status)      MODE="status"; shift ;;
        --json)        JSON=1; shift ;;
        --uninstall)   MODE="uninstall"; shift ;;
        --day)         WEEKDAY="${2:-1}"; TIME_SET=1; shift 2 ;;
        --days)        DAYS="${2:-}"; TIME_SET=1; shift 2 ;;
        --hour)        HOUR="${2:-9}"; TIME_SET=1; shift 2 ;;
        --minute)      MINUTE="${2:-0}"; TIME_SET=1; shift 2 ;;
        --daily)
            case "${2:-}" in
                [0-9]:[0-5][0-9]|[0-1][0-9]:[0-5][0-9]|2[0-3]:[0-5][0-9]) ;;
                *) die "--daily needs HH:MM (00:00..23:59), got ${2:-}" ;;
            esac
            HOUR="$((10#${2%%:*}))"; MINUTE="$((10#${2##*:}))"; DAILY=1; TIME_SET=1; shift 2 ;;
        --at-login)    AT_LOGIN=1; shift ;;
        --delay-min)   DELAY_MIN="${2:-}"; shift 2 ;;
        --system-updates) SYSTEM_UPDATES=1; shift ;;
        --silent)      NOTIFY_MODE="needs_you"; shift ;;
        --no-silent)   NOTIFY_MODE="always"; shift ;;
        --notify)      NOTIFY_MODE="${2:-}"; shift 2 ;;
        -y|--yes)      ASSUME_YES=1; shift ;;
        --once-in)     ONCE_IN="${2:-}"; shift 2 ;;
        -h|--help)     show_help; exit 0 ;;
        *)             echo "Error: Unknown option $1" >&2; show_help >&2; exit 2 ;;
    esac
done

CURRENT_UID="$(id -u)"

xml_escape() {
    local s="$1"
    s="${s//&/&amp;}"; s="${s//</&lt;}"; s="${s//>/&gt;}"
    printf '%s' "$s"
}

# Stop one job. Only touches jobs that have a plist or are listed.
unload_job() { # <label> <plist>
    if [ -f "$2" ] || launchctl list 2>/dev/null | grep -q "$1"; then
        launchctl bootout "gui/${CURRENT_UID}/$1" >/dev/null 2>&1 \
            || launchctl bootout "gui/${CURRENT_UID}" "$2" >/dev/null 2>&1 \
            || true
    fi
}

# ── status / check ──────────────────────────────────────────────────────────
# One python helper reads the plists (plistlib) for both --check and --status.
status_py() { # <json|text>
    local fmt="$1" d="" o="" g="" ld=0 lo=0 lg=0
    if d="$(launchctl print "gui/${CURRENT_UID}/${PLIST_LABEL}" 2>/dev/null)"; then ld=1; fi
    if o="$(launchctl print "gui/${CURRENT_UID}/${ONCE_LABEL}" 2>/dev/null)"; then lo=1; fi
    if g="$(launchctl print "gui/${CURRENT_UID}/${LEGACY_LABEL}" 2>/dev/null)"; then lg=1; fi
    MU_FMT="$fmt" MU_DAILY="$PLIST_PATH|$PLIST_LABEL" MU_ONCE="$ONCE_PATH|$ONCE_LABEL" \
        MU_LEGACY="$LEGACY_PATH|$LEGACY_LABEL" MU_L_DAILY="$ld" MU_L_ONCE="$lo" MU_L_LEGACY="$lg" \
        MU_P_DAILY="$d" MU_P_ONCE="$o" MU_P_LEGACY="$g" \
        python3 - <<'PY'
import datetime, json, os, plistlib, re, time

fmt = os.environ["MU_FMT"]
now = float(os.environ.get("MAC_UPDATE_LAUNCHAGENT_NOW_EPOCH") or time.time())


def triggers_of(data):
    out = []
    if data.get("RunAtLoad"):
        out.append({"type": "login"})
    cal = data.get("StartCalendarInterval")
    if isinstance(cal, dict):
        cal = [cal]
    for c in cal or []:
        if "Month" in c and "Day" in c:
            out.append({"type": "once", "month": c["Month"], "day": c["Day"],
                        "hour": c.get("Hour", 0), "minute": c.get("Minute", 0)})
        else:
            out.append({"type": "calendar", "weekday": c.get("Weekday"),
                        "hour": c.get("Hour", 0), "minute": c.get("Minute", 0)})
    return out


def next_run(triggers):
    base = datetime.datetime.fromtimestamp(now)
    best = None
    for t in triggers:
        cands = []
        if t["type"] == "calendar":
            for off in range(0, 9):
                day = base.date() + datetime.timedelta(days=off)
                w = t["weekday"]
                if w is not None and day.isoweekday() != (7 if w in (0, 7) else w):
                    continue
                cands.append(datetime.datetime(day.year, day.month, day.day, t["hour"], t["minute"]))
        elif t["type"] == "once":
            for yr in (base.year, base.year + 1):
                try:
                    cands.append(datetime.datetime(yr, t["month"], t["day"], t["hour"], t["minute"]))
                except ValueError:
                    pass
        for c in cands:
            if c > base:
                if best is None or c < best:
                    best = c
                break
    return best.strftime("%Y-%m-%dT%H:%M") if best else None


def last_exit(text):
    m = re.search(r"last exit code = (-?\d+)", text or "")
    return int(m.group(1)) if m else None


def load(env_key, print_key, loaded_key):
    path, label = os.environ[env_key].split("|", 1)
    info = {"label": label, "plist": path, "installed": os.path.isfile(path),
            "loaded": os.environ.get(loaded_key) == "1", "triggers": [], "next_run": None,
            "last_exit_code": last_exit(os.environ.get(print_key)),
            "delay_min": 0, "notify": None}
    if info["installed"]:
        try:
            with open(path, "rb") as fh:
                data = plistlib.load(fh)
            info["triggers"] = triggers_of(data)
            env = data.get("EnvironmentVariables") or {}
            info["delay_min"] = int(env.get("MAC_UPDATE_DELAY_MIN") or 0)
            info["notify"] = env.get("MAC_UPDATE_NOTIFY")
            info["system_updates"] = env.get("MAC_UPDATE_AUTOMATION_SYSTEM_UPDATES") == "1"
            info["path_ok"] = "/opt/homebrew/bin" in (env.get("PATH") or "")
            info["next_run"] = next_run(info["triggers"])
        except Exception:
            info["unreadable"] = True
    return info


daily = load("MU_DAILY", "MU_P_DAILY", "MU_L_DAILY")
once = load("MU_ONCE", "MU_P_ONCE", "MU_L_ONCE")
legacy = load("MU_LEGACY", "MU_P_LEGACY", "MU_L_LEGACY")

if fmt == "json":
    out = dict(daily)
    out.pop("path_ok", None)
    once.pop("path_ok", None)
    out["once"] = once
    out["legacy"] = {k: legacy[k] for k in ("installed", "label", "plist", "loaded")}
    print(json.dumps(out, indent=2, sort_keys=True))
    raise SystemExit(0)


def describe(t):
    if t["type"] == "once":
        return "one-shot on %02d-%02d at %02d:%02d" % (t["month"], t["day"], t["hour"], t["minute"])
    if t["weekday"] is None:
        return "daily at %02d:%02d" % (t["hour"], t["minute"])
    return "Weekday %s at %02d:%02d" % (t["weekday"], t["hour"], t["minute"])


rc = 0
shown = False
for info in (daily, once, legacy):
    if not info["installed"] and not info["loaded"]:
        continue
    shown = True
    tag = " (legacy, replaced on next install)" if info is legacy else ""
    if info["loaded"]:
        print("✅ LaunchAgent is active: %s%s" % (info["label"], tag))
    else:
        print("⚠️  LaunchAgent plist exists but is not loaded: %s" % info["plist"])
        rc = 1
        continue
    print("   Plist: %s" % info["plist"])
    for t in info["triggers"]:
        if t["type"] == "login":
            print("   Trigger: at login")
        else:
            print("   StartCalendarInterval: %s" % describe(t))
    if info["delay_min"]:
        print("   Login delay: %d min" % info["delay_min"])
    if info["next_run"]:
        print("   Next run: %s" % info["next_run"])
    if info.get("installed") and info.get("path_ok") is False:
        print("⚠️  Plist has no EnvironmentVariables.PATH with Homebrew; scheduled runs cannot "
              "find brew/mas. Re-run: bash scripts/install_launchagent.sh")
if not shown:
    print("ℹ️  LaunchAgent is not installed")
raise SystemExit(rc)
PY
}

if [ "$MODE" = "status" ] && [ "$JSON" -eq 1 ]; then
    status_py json
    exit $?
fi
if [ "$MODE" = "check" ] || [ "$MODE" = "status" ]; then
    status_py text
    exit $?
fi

if [ "$MODE" = "uninstall" ]; then
    for pair in "${PLIST_LABEL}|${PLIST_PATH}" "${ONCE_LABEL}|${ONCE_PATH}" "${LEGACY_LABEL}|${LEGACY_PATH}"; do
        unload_job "${pair%%|*}" "${pair#*|}"
        # No `unload -w` fallback: it leaves a persistent disabled override behind.
        rm -f "${pair#*|}"
    done
    echo "✅ LaunchAgent uninstalled: $PLIST_LABEL"
    exit 0
fi

# ── validation ──────────────────────────────────────────────────────────────
if [ -n "$WEEKDAY" ] && [ -n "$DAYS" ]; then
    die "--day and --days cannot be combined"
fi
[ -n "$WEEKDAY" ] && DAYS="$WEEKDAY"
if [ -n "$DAYS" ]; then
    NORM_DAYS=""
    OLD_IFS="$IFS"; IFS=','
    for d in $DAYS; do
        case "$d" in
            [1-7]) ;;
            *) IFS="$OLD_IFS"; die "--day/--days must be between 1 (Monday) and 7 (Sunday), got $DAYS" ;;
        esac
        case ",${NORM_DAYS}," in *",$d,"*) ;; *) NORM_DAYS="${NORM_DAYS:+$NORM_DAYS,}$d" ;; esac
    done
    IFS="$OLD_IFS"
    DAYS="$(printf '%s' "$NORM_DAYS" | tr ',' '\n' | sort -n | tr '\n' ',' | sed 's/,$//')"
fi

if ! [[ "$HOUR" =~ ^([0-9]|1[0-9]|2[0-3])$ ]]; then
    die "--hour must be between 0 and 23, got $HOUR"
fi
if ! [[ "$MINUTE" =~ ^([0-9]|[1-5][0-9])$ ]]; then
    die "--minute must be between 0 and 59, got $MINUTE"
fi
if ! [[ "$DELAY_MIN" =~ ^[0-9]+$ ]] || [ "$((10#$DELAY_MIN))" -gt 240 ]; then
    die "--delay-min must be between 0 and 240, got $DELAY_MIN"
fi
DELAY_MIN=$((10#$DELAY_MIN))
case "$NOTIFY_MODE" in
    always|needs_you|never) ;;
    1) NOTIFY_MODE="always" ;;
    0) NOTIFY_MODE="never" ;;
    *) die "--notify must be always, needs_you or never, got $NOTIFY_MODE" ;;
esac

# ── build the trigger block ─────────────────────────────────────────────────
CALENDAR_BLOCK=""
RUN_AT_LOAD=0
SCHEDULE_DESC=""
JOB_LABEL="$PLIST_LABEL"
JOB_PATH="$PLIST_PATH"
EXTRA_ENV=""

cal_dict() { # <indent> [weekday]  (hour/minute from globals)
    local ind="$1"
    printf '%s<dict>\n' "$ind"
    if [ -n "${2:-}" ]; then
        printf '%s    <key>Weekday</key>\n%s    <integer>%s</integer>\n' "$ind" "$ind" "$2"
    fi
    printf '%s    <key>Hour</key>\n%s    <integer>%s</integer>\n' "$ind" "$ind" "$HOUR"
    printf '%s    <key>Minute</key>\n%s    <integer>%s</integer>\n' "$ind" "$ind" "$MINUTE"
    printf '%s</dict>' "$ind"
}

if [ -n "$ONCE_IN" ]; then
    if [ "$TIME_SET" -eq 1 ] || [ "$AT_LOGIN" -eq 1 ]; then
        die "--once-in cannot be combined with --day/--days/--daily/--hour/--minute/--at-login"
    fi
    if ! [[ "$ONCE_IN" =~ ^[0-9]+$ ]] || [ "$((10#$ONCE_IN))" -lt 1 ] || [ "$((10#$ONCE_IN))" -gt 1440 ]; then
        die "--once-in must be between 1 and 1440 minutes, got $ONCE_IN"
    fi
    JOB_LABEL="$ONCE_LABEL"
    JOB_PATH="$ONCE_PATH"
    # "Now" is injectable for tests only. BSD date: -r <epoch> formats an epoch
    # in local time, so DST and month/year rollover are handled by the system.
    NOW_EPOCH="${MAC_UPDATE_LAUNCHAGENT_NOW_EPOCH:-$(date +%s)}"
    TARGET_EPOCH=$((NOW_EPOCH + 10#$ONCE_IN * 60))
    T_PARTS="$(date -r "$TARGET_EPOCH" "+%m %d %H %M")"
    # shellcheck disable=SC2086
    set -- $T_PARTS
    T_MON=$((10#$1)); T_DAY=$((10#$2)); T_HOUR=$((10#$3)); T_MIN=$((10#$4))
    CALENDAR_BLOCK="    <dict>
        <key>Month</key>
        <integer>${T_MON}</integer>
        <key>Day</key>
        <integer>${T_DAY}</integer>
        <key>Hour</key>
        <integer>${T_HOUR}</integer>
        <key>Minute</key>
        <integer>${T_MIN}</integer>
    </dict>"
    SCHEDULE_DESC="$(printf 'one-shot, fires once on %02d-%02d at %02d:%02d (local time)' "$T_MON" "$T_DAY" "$T_HOUR" "$T_MIN")"
    EXTRA_ENV="        <key>MAC_UPDATE_SCHEDULED_FORCE</key>
        <string>1</string>
"
else
    SCHEDULE_DESC=""
    if [ "$AT_LOGIN" -eq 1 ]; then
        RUN_AT_LOAD=1
        SCHEDULE_DESC="at login"
        [ "$DELAY_MIN" -gt 0 ] && SCHEDULE_DESC="$SCHEDULE_DESC (after ${DELAY_MIN} min)"
    fi
    if [ "$AT_LOGIN" -eq 0 ] || [ "$TIME_SET" -eq 1 ]; then
        if [ -z "$DAYS" ] && [ "$DAILY" -eq 1 ]; then
            CALENDAR_BLOCK="$(cal_dict '    ')"
            CAL_DESC="$(printf 'daily at %02d:%02d' "$HOUR" "$MINUTE")"
        else
            [ -z "$DAYS" ] && DAYS=1
            case "$DAYS" in
                *,*)
                    CALENDAR_BLOCK="    <array>"
                    OLD_IFS="$IFS"; IFS=','
                    for d in $DAYS; do
                        CALENDAR_BLOCK="${CALENDAR_BLOCK}
$(cal_dict '        ' "$d")"
                    done
                    IFS="$OLD_IFS"
                    CALENDAR_BLOCK="${CALENDAR_BLOCK}
    </array>"
                    CAL_DESC="$(printf 'Weekdays %s at %02d:%02d' "$DAYS" "$HOUR" "$MINUTE")"
                    ;;
                *)
                    CALENDAR_BLOCK="$(cal_dict '    ' "$DAYS")"
                    CAL_DESC="$(printf 'Weekday %s at %02d:%02d' "$DAYS" "$HOUR" "$MINUTE")"
                    ;;
            esac
        fi
        SCHEDULE_DESC="${SCHEDULE_DESC:+$SCHEDULE_DESC + }$CAL_DESC"
    fi
fi

# ── legacy schedule: never two active schedules ─────────────────────────────
if [ -z "$ONCE_IN" ]; then
    if [ -f "$LEGACY_PATH" ] || launchctl list 2>/dev/null | grep -q "$LEGACY_LABEL"; then
        if [ "$ASSUME_YES" -eq 0 ] && [ -t 0 ] && [ -t 1 ]; then
            printf 'A legacy schedule (%s) exists. Replace it with %s? [Y/n] ' "$LEGACY_LABEL" "$PLIST_LABEL"
            read -r reply
            case "$reply" in
                n|N|no|NO) echo "Left unchanged; the legacy schedule stays the only one." >&2; exit 3 ;;
            esac
        fi
        unload_job "$LEGACY_LABEL" "$LEGACY_PATH"
        rm -f "$LEGACY_PATH"
        echo "ℹ️  Replaced legacy schedule: $LEGACY_LABEL"
    fi
fi

# ── write the plist ─────────────────────────────────────────────────────────
mkdir -p "$AGENT_DIR" "$LOG_DIR"

ENV_EXTRA="$EXTRA_ENV"
[ "$DELAY_MIN" -gt 0 ] && ENV_EXTRA="${ENV_EXTRA}        <key>MAC_UPDATE_DELAY_MIN</key>
        <string>${DELAY_MIN}</string>
"
[ "$SYSTEM_UPDATES" -eq 1 ] && ENV_EXTRA="${ENV_EXTRA}        <key>MAC_UPDATE_AUTOMATION_SYSTEM_UPDATES</key>
        <string>1</string>
"
[ -n "${MAC_UPDATE_STATE_DIR:-}" ] && ENV_EXTRA="${ENV_EXTRA}        <key>MAC_UPDATE_STATE_DIR</key>
        <string>$(xml_escape "$MAC_UPDATE_STATE_DIR")</string>
"
CAL_XML=""
[ -n "$CALENDAR_BLOCK" ] && CAL_XML="    <key>StartCalendarInterval</key>
${CALENDAR_BLOCK}
"
LOAD_XML=""
[ "$RUN_AT_LOAD" -eq 1 ] && LOAD_XML="    <key>RunAtLoad</key>
    <true/>
"

cat <<PLISTEOF > "$JOB_PATH"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DOCTYPE/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${JOB_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$(xml_escape "$SCRIPT_DIR")/scripts/scheduled_run.sh</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>${LAUNCHD_PATH}</string>
        <key>MAC_UPDATE_NONINTERACTIVE</key>
        <string>1</string>
        <key>MAC_UPDATE_NOTIFY</key>
        <string>${NOTIFY_MODE}</string>
${ENV_EXTRA}    </dict>
${CAL_XML}${LOAD_XML}    <key>ProcessType</key>
    <string>Background</string>
    <key>LowPriorityIO</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$(xml_escape "$LOG_DIR")/launchd.out</string>
    <key>StandardErrorPath</key>
    <string>$(xml_escape "$LOG_DIR")/launchd.err</string>
</dict>
</plist>
PLISTEOF

chmod 644 "$JOB_PATH"
xattr -d com.apple.quarantine "$JOB_PATH" 2>/dev/null || true

# Remove a previous instance of this job. bootout only: `unload -w` would
# persist a "disabled" override that can survive into the new install.
launchctl bootout "gui/${CURRENT_UID}/${JOB_LABEL}" >/dev/null 2>&1 \
    || launchctl bootout "gui/${CURRENT_UID}" "$JOB_PATH" >/dev/null 2>&1 \
    || true

# Clear any stale "disabled" override first, then bootstrap with a fallback to
# legacy load; keep stderr for diagnostics.
launchctl enable "gui/${CURRENT_UID}/${JOB_LABEL}" >/dev/null 2>&1 || true
BOOT_ERR="$(launchctl bootstrap "gui/${CURRENT_UID}" "$JOB_PATH" 2>&1)"
if [ $? -ne 0 ]; then
    BOOT_ERR_LEGACY="$(launchctl load -w "$JOB_PATH" 2>&1)"
    BOOT_ERR="${BOOT_ERR}${BOOT_ERR_LEGACY:+
$BOOT_ERR_LEGACY}"
fi
launchctl enable "gui/${CURRENT_UID}/${JOB_LABEL}" >/dev/null 2>&1 || true

# Never claim success without proof that the service is loaded.
if ! PRINT_OUT="$(launchctl print "gui/${CURRENT_UID}/${JOB_LABEL}" 2>&1)"; then
    echo "❌ LaunchAgent was NOT loaded: $JOB_LABEL" >&2
    [ -n "$BOOT_ERR" ] && echo "$BOOT_ERR" >&2
    [ -n "$PRINT_OUT" ] && echo "$PRINT_OUT" >&2
    echo "   Plist: $JOB_PATH" >&2
    exit 1
fi

echo "✅ Installed and loaded LaunchAgent: $JOB_LABEL"
echo "   Schedule: $SCHEDULE_DESC"
echo "   Plist: $JOB_PATH"
