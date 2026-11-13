#!/usr/bin/env bash
# ============================================================
# setup_touchid_sudo.sh — enable Touch ID for sudo (per-machine)
# ============================================================
# WHY THIS EXISTS
#   Touch ID for sudo lives in /etc/pam.d — a machine-local, root-owned
#   directory that is NOT part of this git repository. Cloning or pulling
#   this repo on a second Mac therefore never enables Touch ID there.
#   This script is the missing "per-machine bootstrap" step.
#
# WHAT IT DOES
#   1. Writes /etc/pam.d/sudo_local  (macOS 14+; survives OS updates)
#      macOS 13 shared sudo configuration requires manual administration
#   2. Optionally wires pam_reattach so Touch ID also works in tmux/screen
#   3. Never touches /etc/sudoers and never grants passwordless sudo
#
# USAGE
#   bash scripts/setup_touchid_sudo.sh            # install / repair
#   bash scripts/setup_touchid_sudo.sh --check    # report only, no writes
#   bash scripts/setup_touchid_sudo.sh --uninstall
#
# EXIT CODES
#   0 — Touch ID configured (or already correct)
#   1 — hard failure
#   2 — unsupported hardware/OS (no Touch ID sensor)
# ============================================================
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
[ ! -f "$SCRIPT_DIR/i18n/loader.sh" ] || . "$SCRIPT_DIR/i18n/loader.sh"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[0;33m'
RED='\033[0;31m'; MAGENTA='\033[0;35m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✅ $1${NC}"; }
info() { echo -e "  ${CYAN}ℹ️  $1${NC}"; }
warn() { echo -e "  ${YELLOW}⚠️  $1${NC}"; }
err()  { echo -e "  ${RED}❌ $1${NC}"; }
step() { echo -e "  ${MAGENTA}▶  $1${NC}"; }

MODE="install"
case "${1:-}" in
    --check)     MODE="check" ;;
    --uninstall) MODE="uninstall" ;;
    -h|--help)
        sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'
        exit 0
        ;;
    "") ;;
    *) err "Unknown option: $1"; exit 1 ;;
esac

PAM_SUDO_LOCAL="/etc/pam.d/sudo_local"
PAM_SUDO="/etc/pam.d/sudo"
PAM_TID="/usr/lib/pam/pam_tid.so.2"

echo ""
echo -e "${CYAN}══ Touch ID for sudo — per-machine setup ══${NC}"
echo ""

# ── 1. Hardware / OS capability ─────────────────────────────
if [ "$(uname -s)" != "Darwin" ]; then
    err "macOS only."
    exit 2
fi

MACOS_MAJOR="$(sw_vers -productVersion | cut -d. -f1)"
info "macOS $(sw_vers -productVersion) (major: $MACOS_MAJOR)"

if [ ! -f "$PAM_TID" ]; then
    err "pam_tid.so not found at $PAM_TID — this Mac has no Touch ID support."
    exit 2
fi
ok "pam_tid module present"

# bioutil reports whether a fingerprint is actually enrolled for this user.
if command -v bioutil >/dev/null 2>&1; then
    if bioutil -r -s 2>/dev/null | grep -qi "biometrics functionality: *1"; then
        ok "Touch ID biometrics enabled for this user"
    else
        warn "No enrolled fingerprint detected for this user."
        warn "Enroll one first: System Settings → Touch ID & Password."
    fi
fi

# macOS 14+ (Sonoma) introduced sudo_local, which OS updates do not overwrite.
if [ "$MACOS_MAJOR" -ge 14 ] 2>/dev/null; then
    TARGET="$PAM_SUDO_LOCAL"
    PERSISTENT=1
else
    TARGET="$PAM_SUDO"
    PERSISTENT=0
    warn "$L_TOUCHID_SHARED_UNAVAILABLE"

fi
info "Target PAM file: $TARGET"

# ── 2. pam_reattach (Touch ID inside tmux / screen) ─────────
# Touch ID is bound to the GUI login session. Anything running detached from
# it (tmux, screen) cannot reach the sensor until pam_reattach re-attaches the
# process. Optional — plain Terminal/iTerm/VS Code do not need it.
REATTACH_LINE=""
for candidate in \
    /opt/homebrew/lib/pam/pam_reattach.so \
    /usr/local/lib/pam/pam_reattach.so
do
    if [ -f "$candidate" ]; then
        REATTACH_LINE="auth       optional       ${candidate} ignore_ssh"
        ok "pam_reattach found: $candidate"
        break
    fi
done
if [ -z "$REATTACH_LINE" ]; then
    info "pam_reattach not installed (optional)."
    info "Only needed for Touch ID inside tmux/screen: brew install pam-reattach"
fi

# ── 3. Desired content ──────────────────────────────────────
build_desired() {
    echo "# Managed by macOS_updates/scripts/setup_touchid_sudo.sh"
    echo "# Touch ID for sudo. Order matters: reattach BEFORE pam_tid."
    [ -n "$REATTACH_LINE" ] && echo "$REATTACH_LINE"
    echo "auth       sufficient     pam_tid.so"
}

# ── 4. CHECK mode ───────────────────────────────────────────
current_state() {
    if [ -f "$TARGET" ] && grep -qE '^[[:space:]]*auth[[:space:]]+sufficient[[:space:]]+pam_tid\.so' "$TARGET"; then
        return 0
    fi
    return 1
}

if [ "$MODE" = "check" ]; then
    echo ""
    if current_state; then
        ok "Touch ID for sudo is ACTIVE ($TARGET)"
        [ "$PERSISTENT" -eq 1 ] && ok "Configuration survives macOS updates"
        if [ -n "$REATTACH_LINE" ] && ! grep -q "pam_reattach" "$TARGET" 2>/dev/null; then
            warn "pam_reattach is installed but not wired in — tmux sessions will still ask for a password."
        fi
        echo ""
        info "Current file:"
        sed 's/^/      /' "$TARGET"
        exit 0
    fi
    err "Touch ID for sudo is NOT configured on this Mac."
    info "Fix it with: bash scripts/setup_touchid_sudo.sh"
    exit 1
fi

# Refuse to alter any existing file whose entire content is not ours.
# The macOS 13 sudo file is shared, so it is never modified automatically.
if [ "$PERSISTENT" -ne 1 ]; then
    err "${L_TOUCHID_SHARED_UNAVAILABLE:-Automatic changes to the shared sudo file are unavailable.}"
    exit 1
fi
if [ -L "$TARGET" ] || { [ -e "$TARGET" ] && [ ! -f "$TARGET" ]; }; then
    err "$L_TOUCHID_FOREIGN_FILE"
    exit 1
fi
if [ -e "$TARGET" ]; then
    if ! diff -q "$TARGET" <(build_desired) >/dev/null 2>&1; then
        err "${L_TOUCHID_FOREIGN_FILE:-Existing sudo_local contains foreign or unrecognized content; left unchanged.}"
        exit 1
    fi
fi
if [ "$MODE" = "install" ] && [ -e "$TARGET" ]; then
    ok "${L_TOUCHID_ALREADY_CONFIGURED:-Already configured; no changes needed.}"
    exit 0
fi
if [ "$MODE" = "uninstall" ] && [ ! -e "$TARGET" ]; then
    info "Nothing to remove."
    exit 0
fi
if [ ! -t 0 ] || [ ! -t 1 ] || [ "${MAC_UPDATE_NONINTERACTIVE:-0}" = 1 ]; then
    err "${L_TOUCHID_TTY_REQUIRED:-A terminal is required for PAM changes; no changes made.}"
    exit 1
fi
if ! command -v sudo >/dev/null 2>&1; then
    err "${L_TOUCHID_SUDO_UNAVAILABLE:-sudo is unavailable; no changes made.}"
    exit 1
fi
. "$SCRIPT_DIR/lib/platform.sh"
if ! mac_update_tool_usable python3 || ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
    err "$L_SETUP_PYTHON_UNAVAILABLE"
    exit 1
fi
python_path="$(command -v python3)"
# Bind consent to absence or the exact file observed before the prompt. The
# privileged helper checks it again and creates new files without overwriting.
preview_token="$(PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import sys
from setup_safety import fingerprint
print(fingerprint(sys.argv[1]))
' "$TARGET" 2>/dev/null)" || { err "$L_TOUCHID_FOREIGN_FILE"; exit 1; }
if [ "$MODE" = "uninstall" ]; then
    info "$(printf "$L_TOUCHID_UNINSTALL_PREVIEW" "$TARGET")"
else
    info "$(printf "$L_TOUCHID_INSTALL_PREVIEW" "$TARGET")"
    build_desired
fi
printf '%s [y/N] ' "$L_TOUCHID_CONFIRM"
IFS= read -r answer || exit 1
case "$answer" in y|Y|yes|YES) ;; *) info "$L_TOUCHID_NO_CHANGES"; exit 0 ;; esac
if ! sudo "$python_path" - "$SCRIPT_DIR/lib/python" "$TARGET" "$PAM_SUDO" "$MODE" "$preview_token" "$(build_desired)" <<'PY_SETUP_PAM'
import sys
sys.path.insert(0, sys.argv[1])
from setup_safety import apply_pam
try:
    backup = apply_pam(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6] + "\n")
    print(backup)
except (OSError, ValueError) as exc:
    print(str(exc), file=sys.stderr)
    sys.exit(1)
PY_SETUP_PAM
then
    err "$L_TOUCHID_OPERATION_FAILED"
    exit 1
fi
ok "$L_TOUCHID_COMPLETE"
