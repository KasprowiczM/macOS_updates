#!/usr/bin/env bash
# ============================================================
# Shared severity and exit code helpers across orchestrator scripts
# ============================================================
# Exit code contracts:
#   0  = success / clean
#   10 = soft/degraded failure (could not verify, offline, cosmetic; non-blocking)
#   1  = hard failure (download/install/package operation broke mid-transaction; blocking)
# ============================================================

export MAC_UPDATE_SOFT_EXIT=10

mac_update_severity_init() {
    HARD_FAIL=0
    SOFT_FAIL=0
}

mac_update_severity_exit_code() {
    if [ "${HARD_FAIL:-0}" -ne 0 ]; then
        echo 1
    elif [ "${SOFT_FAIL:-0}" -ne 0 ]; then
        echo "$MAC_UPDATE_SOFT_EXIT"
    else
        echo 0
    fi
}
