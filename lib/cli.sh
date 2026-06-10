#!/usr/bin/env bash
# lib/cli.sh — shared CLI flags for update orchestrators (Bash 3.2+)

mac_update_cli_usage() {
    cat <<'EOF'
Usage: bash update_all.sh [OPTIONS]

Options:
  -y, --yes                      Skip confirmation prompt
  -h, --help                     Show this help
      --dry-run                  Preview steps without mutating the system
      --json-summary             Emit JSON summary on exit (stdout, after run)
      --skip-prescan             Skip step 0 (APPLICATIONS.md prescan)
      --skip-system              Skip step 1 (macOS system update)
      --skip-appstore            Skip step 2 (App Store)
      --skip-npm                 Skip step 3 (Native CLI + npm)
      --skip-brew                Skip step 4 (Homebrew)
      --skip-internet            Skip step 5 (internet apps)
      --skip-postupdate          Skip step 6 (APPLICATIONS.md / UPDATES.md)
      --skip-doctor              Skip brew doctor in update_brew.sh
      --treat-appstore-ax-as-warning
                                 Treat App Store exit 2 (Accessibility) as warning

Environment (also set by flags):
  MAC_UPDATE_DRY_RUN=1
  MAC_UPDATE_SKIP_*=1
EOF
}

mac_update_parse_cli() {
    while [ $# -gt 0 ]; do
        case "$1" in
            -y|--yes) export MAC_UPDATE_YES=1 ;;
            -h|--help) mac_update_cli_usage; exit 0 ;;
            --dry-run) export MAC_UPDATE_DRY_RUN=1 ;;
            --json-summary) export MAC_UPDATE_JSON_SUMMARY=1 ;;
            --skip-prescan) export MAC_UPDATE_SKIP_PRESCAN=1 ;;
            --skip-system) export MAC_UPDATE_SKIP_SYSTEM=1 ;;
            --skip-appstore) export MAC_UPDATE_SKIP_APPSTORE=1 ;;
            --skip-npm) export MAC_UPDATE_SKIP_NPM=1 ;;
            --skip-brew) export MAC_UPDATE_SKIP_BREW=1 ;;
            --skip-internet) export MAC_UPDATE_SKIP_INTERNET=1 ;;
            --skip-postupdate) export MAC_UPDATE_SKIP_POSTUPDATE=1 ;;
            --skip-doctor) export MAC_UPDATE_SKIP_DOCTOR=1 ;;
            --treat-appstore-ax-as-warning) export MAC_UPDATE_TREAT_APPSTORE_AX_AS_WARNING=1 ;;
            --) shift; break ;;
            -*) echo "Unknown option: $1" >&2; mac_update_cli_usage >&2; exit 2 ;;
            *) break ;;
        esac
        shift
    done
}

mac_update_dry_run_msg() {
    local action="$1"
    if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
        if type ui_is_tty >/dev/null 2>&1 && ui_is_tty; then
            echo -e "  \033[1;33m[DRY-RUN]\033[0m Would run: $action"
        else
            echo "  [DRY-RUN] Would run: $action"
        fi
        return 0
    fi
    return 1
}

mac_update_run_child() {
    local script_name="$1"
    local dry_label="$2"
    if mac_update_dry_run_msg "$dry_label"; then
        return 0
    fi
    if [ ! -f "$SCRIPT_DIR/$script_name" ]; then
        return 127
    fi
    chmod +x "$SCRIPT_DIR/$script_name"
    bash "$SCRIPT_DIR/$script_name"
}
