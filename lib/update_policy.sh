#!/usr/bin/env bash
# Source-aware policy bridge. Arguments carry plan/action identity, never eval.
_MAC_UPDATE_POLICY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mac_update_authorize_action() {
    [ "$#" -eq 2 ] && [ -n "$1" ] && [ -n "$2" ] || return 10
    PYTHONPATH="$_MAC_UPDATE_POLICY_DIR/python${PYTHONPATH:+:$PYTHONPATH}" \
        python3 -c 'import sys; from policy_runtime import main; sys.exit(main(sys.argv[1:]))' guard "$1" "$2"
}
mac_update_policy_run_adapter() {
    [ "$#" -eq 1 ] || return 1
    if [ -z "${MAC_UPDATE_PLAN_PATH:-}" ]; then
        printf '%s\n' 'deferred_by_user: a reviewed action plan is required.'
        return 10
    fi
    PYTHONPATH="$_MAC_UPDATE_POLICY_DIR/python${PYTHONPATH:+:$PYTHONPATH}" \
        python3 -c 'import sys; from policy_runtime import main; sys.exit(main(sys.argv[1:]))' adapter "${MAC_UPDATE_PLAN_PATH:-}" "$1"
}
mac_update_target_lock_run() {
    [ "$#" -ge 2 ] || return 1
    PYTHONPATH="$_MAC_UPDATE_POLICY_DIR/python${PYTHONPATH:+:$PYTHONPATH}" \
        python3 -c 'import sys; from policy_runtime import main; sys.exit(main(sys.argv[1:]))' target-lock "$@"
}
