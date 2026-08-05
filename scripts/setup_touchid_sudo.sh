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
#      or patches /etc/pam.d/sudo    (macOS 13; wiped by OS updates)
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
    warn "macOS 13 has no sudo_local; /etc/pam.d/sudo is patched instead."
    warn "That file is REWRITTEN by every macOS update — re-run this script after upgrades."
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

# ── 5. UNINSTALL mode ───────────────────────────────────────
if [ "$MODE" = "uninstall" ]; then
    if [ "$PERSISTENT" -eq 1 ]; then
        if [ -f "$TARGET" ]; then
            step "Removing $TARGET"
            sudo rm -f "$TARGET" || { err "Failed to remove $TARGET"; exit 1; }
            ok "Touch ID for sudo disabled."
        else
            info "Nothing to remove."
        fi
    else
        err "Automatic uninstall from /etc/pam.d/sudo is not performed (too risky)."
        info "Edit it manually: sudo visudo is NOT the tool — use: sudo nano $PAM_SUDO"
        exit 1
    fi
    exit 0
fi

# ── 6. INSTALL ──────────────────────────────────────────────
if current_state; then
    if [ -n "$REATTACH_LINE" ] && ! grep -q "pam_reattach" "$TARGET" 2>/dev/null; then
        info "pam_tid already present; adding pam_reattach for tmux support."
    else
        ok "Already configured — nothing to do."
        echo ""
        info "Verify with: sudo -k && sudo true"
        exit 0
    fi
fi

echo ""
step "Writing PAM configuration (sudo password required once)"

if [ "$PERSISTENT" -eq 1 ]; then
    # sudo_local is ours to own entirely. Back up anything pre-existing.
    if [ -f "$TARGET" ]; then
        BACKUP="${TARGET}.backup-$(date +%Y%m%d%H%M%S)"
        sudo cp -p "$TARGET" "$BACKUP" 2>/dev/null && info "Backup: $BACKUP"
    fi
    if ! build_desired | sudo tee "$TARGET" >/dev/null; then
        err "Failed to write $TARGET"
        exit 1
    fi
    sudo chown root:wheel "$TARGET" 2>/dev/null || true
    sudo chmod 444 "$TARGET" 2>/dev/null || true
else
    # macOS 13: prepend into /etc/pam.d/sudo, never overwrite it.
    BACKUP="${TARGET}.backup-$(date +%Y%m%d%H%M%S)"
    sudo cp -p "$TARGET" "$BACKUP" || { err "Backup failed — aborting."; exit 1; }
    info "Backup: $BACKUP"
    TMP_PAM="$(mktemp "${TMPDIR:-/tmp}/mac_update_pam.XXXXXX")" || exit 1
    build_desired > "$TMP_PAM"
    grep -v '^# Managed by macOS_updates' "$TARGET" >> "$TMP_PAM"
    if ! sudo cp "$TMP_PAM" "$TARGET"; then
        err "Write failed — restoring backup."
        sudo cp -p "$BACKUP" "$TARGET"
        rm -f "$TMP_PAM"
        exit 1
    fi
    rm -f "$TMP_PAM"
    sudo chown root:wheel "$TARGET" 2>/dev/null || true
    sudo chmod 444 "$TARGET" 2>/dev/null || true
fi

ok "PAM configuration written."
echo ""
info "Result:"
sed 's/^/      /' "$TARGET"
echo ""

# ── 7. Verify ───────────────────────────────────────────────
if current_state; then
    ok "Touch ID for sudo is now ACTIVE."
    [ "$PERSISTENT" -eq 1 ] && ok "This survives macOS updates (sudo_local)."
    echo ""
    info "Test it in a NEW terminal window:"
    echo "      sudo -k && sudo true      # should show the Touch ID prompt"
    echo ""
    info "Then run the updater without typing a password:"
    echo "      bash update_all.sh -y"
    exit 0
fi

err "Verification failed — pam_tid line not found after write."
exit 1
