#!/usr/bin/env bash
# Explicit first-install bridge. A prior UI consent file is required per action.
_SETUP_INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
setup_execute_install_action() {
    [ "$#" -eq 2 ] && [ -n "${MAC_UPDATE_INSTALL_CONSENT_PATH:-}" ] || return 10
    PYTHONPATH="$_SETUP_INSTALL_DIR/python${PYTHONPATH:+:$PYTHONPATH}" \
        python3 -c 'import sys; from install_execution import shell_execute; sys.exit(shell_execute(sys.argv[1:]))' "$1" "$2" "$MAC_UPDATE_INSTALL_CONSENT_PATH"
}
install_verified_app() {
    [ "$#" -eq 3 ] && [ -n "${MAC_UPDATE_INSTALL_PLAN_PATH:-}" ] && [ -n "${MAC_UPDATE_INSTALL_CONSENT_PATH:-}" ] || return 10
    PYTHONPATH="$_SETUP_INSTALL_DIR/python${PYTHONPATH:+:$PYTHONPATH}" \
        python3 -c 'import sys; from install_execution import shell_execute; sys.exit(shell_execute(sys.argv[1:]))' "$MAC_UPDATE_INSTALL_PLAN_PATH" "$3" "$MAC_UPDATE_INSTALL_CONSENT_PATH" "$1" "$2"
}
