#!/usr/bin/env bash
# lib/notify_summary.sh — one localized notification after a scheduled run.
# mu_notify_run_summary <event-file> [exit-code] [extra-line]
# Mode comes from MAC_UPDATE_NOTIFY (always | needs_you | never; legacy 0/1).
# Never prints to the terminal, never changes an exit status.

_MU_NOTIFY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mu_notify_run_summary() {
    local lang=""
    command -v python3 >/dev/null 2>&1 || return 0
    # Language: environment, then <config>/lang (lib/paths.sh), then the old
    # developer-checkout .mac_update_prefs (read by run_notification.py).
    if [ -z "${MAC_UPDATE_LANG:-}${MAC_LANG:-}" ]; then
        type mu_data_resolve >/dev/null 2>&1 || . "$_MU_NOTIFY_DIR/paths.sh"
        if mu_data_resolve 2>/dev/null && [ -f "$MU_LANG_FILE" ]; then
            IFS= read -r lang < "$MU_LANG_FILE" || true
        fi
    fi
    python3 "$_MU_NOTIFY_DIR/python/run_notification.py" notify \
        --events "${1:-}" --exit-code "${2:-0}" --extra "${3:-}" --lang "$lang" \
        --prefs "$_MU_NOTIFY_DIR/../.mac_update_prefs" </dev/null >/dev/null 2>&1 || true
    return 0
}
