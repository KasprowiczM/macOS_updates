#!/usr/bin/env bash
# scaffold_internet_app.sh — generate boilerplate for a new internet app handler
# Usage: bash scripts/scaffold_internet_app.sh "My App" silent_launch
# Methods: silent_launch | github_dmg | keystone | manual | msupdate
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

APP_NAME="${1:-}"
METHOD="${2:-silent_launch}"

if [ -z "$APP_NAME" ]; then
    echo "Usage: bash scripts/scaffold_internet_app.sh \"App Name\" [method]" >&2
    echo "Methods: silent_launch | github_dmg | keystone | manual | msupdate" >&2
    exit 1
fi

# Bash 3.2 safe: derive STATUS var from app name
STATUS_VAR="STATUS_$(echo "$APP_NAME" | tr '[:lower:]' '[:upper:]' | tr -cd 'A-Z0-9_')"

cat <<EOF

# ── Scaffold for: $APP_NAME (method: $METHOD) ─────────────────
# 1. Add to config/internet_apps.txt:
#    $APP_NAME
#
# 2. Add to config/internet_app_methods.txt:
#    $APP_NAME|$METHOD|${STATUS_VAR}
#
# 3. Add STATUS init in update_internet_apps.sh:
#    ${STATUS_VAR}="\$L_INTERNET_STATUS_SKIPPED"
#
# 4. Implement iu_* handler in lib/internet_app_updates.sh and add to
#    config/internet_dispatch_order.txt
#
# 5. Handler block (edit paths/URLs as needed):

print_header "$APP_NAME"
APP_PATH="\$(capture_app_path "$APP_NAME")"
if [ -n "\$APP_PATH" ] && [ -d "\$APP_PATH" ]; then
    VER=\$(app_version "\$APP_PATH")
    print_info "\$(internet_msg "\$L_INTERNET_INSTALLED_VERSION" "\$VER")"
EOF

case "$METHOD" in
    silent_launch)
        cat <<'EOF'
    print_step "$(internet_msg "$L_INTERNET_LAUNCHING_HIDDEN" "APP_NAME")"
    if silent_launch_app "APP_NAME"; then
        STATUS_VAR="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
    else
        STATUS_VAR="$L_INTERNET_STATUS_LAUNCH_FAILED"
    fi
EOF
        ;;
    manual)
        cat <<'EOF'
    print_warn "$(internet_msg "$L_INTERNET_NO_AUTO_UPDATER" "APP_NAME")"
    STATUS_VAR="$L_INTERNET_STATUS_MANUAL_UPDATE"
EOF
        ;;
    github_dmg)
        cat <<'EOF'
    # TODO: github_latest_tag owner/repo, DMG download, verify_dmg, copy_verified_app
    STATUS_VAR="$L_INTERNET_STATUS_SKIPPED"
EOF
        ;;
    keystone)
        cat <<'EOF'
    # TODO: Keystone / Google Omaha updater launch
    STATUS_VAR="$L_INTERNET_STATUS_SKIPPED"
EOF
        ;;
    msupdate)
        cat <<'EOF'
    # Handled in Microsoft 365 block — do not add a separate handler
EOF
        ;;
    *)
        echo "# Unknown method: $METHOD" ;;
esac

cat <<EOF
else
    print_info "\$(internet_msg "\$L_INTERNET_NOT_INSTALLED" "$APP_NAME")"
fi

# 6. Add summary printf line in PODSUMOWANIE section
# 7. Add "\$${STATUS_VAR}" to failure-scan for loop
# 8. Run: bash run_tests.sh

EOF
