#!/usr/bin/env bash
# Compatibility boundary: one admitted installed target, never the full dispatcher.

scoped_legacy_mau_binary() {
    printf '%s\n' "/Library/Application Support/Microsoft/MAU2.0/Microsoft AutoUpdate.app/Contents/MacOS/msupdate"
}

scoped_legacy_prepare() {
    [ "${MAC_UPDATE_DRY_RUN:-0}" != 1 ] || return 10
    [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -d "$MAC_UPDATE_SESSION_DIR" ] || return 10
    local metadata
    metadata="$(PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" python3 - "$MAC_UPDATE_PLAN_PATH" "$MAC_UPDATE_ACTION_ID" "$MAC_UPDATE_BATCH_OWNER" <<'PY_LEGACY_CONTEXT'
import os, re, sys
from inventory_store import _root
from policy_runtime import load_plan, guard_action
from installed_native_updaters import (legacy_handler_for, legacy_registry_name, legacy_group_members,
                                        verify_installed_updater_executable)
try:
    plan_path, action_id, owner = sys.argv[1:]
    if _root(os.environ.get("MAC_UPDATE_SESSION_DIR"), False) is None:
        raise ValueError("missing_session")
    plan = load_plan(plan_path)
    rows = [a for a in plan['actions'] if a['action_id'] == action_id]
    if len(rows) != 1 or not owner:
        raise ValueError('invalid_scope')
    action = rows[0]
    handler = legacy_handler_for(action)
    if not isinstance(handler, str) or not re.fullmatch(r'iu_[a-z0-9_]+', handler):
        raise ValueError('unsupported_handler')
    if guard_action(plan_path, action_id, owner_action_id=owner).get('allowed') is not True:
        raise ValueError('scope_not_authorized')
    members = legacy_group_members(plan_path, action_id, owner)
    if handler in ('iu_google_chrome', 'iu_google_drive', 'iu_gemini'):
        if action.get('whole_registered_manager_scope') != 'google':
            raise ValueError('google_broad_scope_required')
        team = action['expected_target'].get('team_id')
        if any(member['expected_target'].get('team_id') != team for member in members):
            raise ValueError('google_signer_scope_conflict')
        binaries = [
            os.path.expanduser('~/Library/Application Support/Google/GoogleUpdater/Current/GoogleUpdater.app/Contents/MacOS/GoogleUpdater'),
            '/Library/Application Support/Google/GoogleUpdater/Current/GoogleUpdater.app/Contents/MacOS/GoogleUpdater',
            '/Library/Google/GoogleSoftwareUpdate/GoogleSoftwareUpdate.bundle/Contents/Resources/GoogleSoftwareUpdateAgent.app/Contents/MacOS/GoogleSoftwareUpdateAgent',
        ]
        for binary in binaries:
            if os.path.lexists(binary) and not verify_installed_updater_executable(binary, team):
                raise ValueError('google_helper_signature_mismatch')
    office = {'Microsoft Word': 'MSWD2019', 'Microsoft Excel': 'XCEL2019',
              'Microsoft PowerPoint': 'PPT32019', 'Microsoft Outlook': 'OPIM2019',
              'Microsoft OneNote': 'ONMC2019'}
    ids = []
    if handler == 'iu_microsoft_365':
        ids = [office[legacy_registry_name(member)] for member in members]
        if len(ids) != len(set(ids)) or not ids:
            raise ValueError('invalid_office_scope')
        team = action['expected_target'].get('team_id')
        if any(member['expected_target'].get('team_id') != team for member in members):
            raise ValueError('office_signer_scope_conflict')
        binary = '/Library/Application Support/Microsoft/MAU2.0/Microsoft AutoUpdate.app/Contents/MacOS/msupdate'
        if os.path.lexists(binary) and not verify_installed_updater_executable(binary, team):
            raise ValueError('office_helper_signature_mismatch')
    target = action['expected_target']
    values = [handler, action['target_path'], target.get('name') or '', target.get('bundle_id') or '', legacy_registry_name(action), ' '.join(ids)]
    if any(not isinstance(v, str) or any(ord(c) < 32 or ord(c) == 127 for c in v) for v in values):
        raise ValueError('invalid_scope_text')
    print('\n'.join(values))
except Exception:
    sys.exit(10)
PY_LEGACY_CONTEXT
)" || return 10
    {
        IFS= read -r SCOPED_LEGACY_HANDLER
        IFS= read -r SCOPED_LEGACY_TARGET
        IFS= read -r SCOPED_LEGACY_NAME
        IFS= read -r SCOPED_LEGACY_BUNDLE
        IFS= read -r SCOPED_LEGACY_REGISTRY
        IFS= read -r SCOPED_LEGACY_MAU_IDS
    } <<EOF_LEGACY_CONTEXT
$metadata
EOF_LEGACY_CONTEXT
    case "$SCOPED_LEGACY_TARGET" in /*.app) ;; *) return 10 ;; esac
    [ -d "$SCOPED_LEGACY_TARGET" ] || return 10
    SCOPED_LEGACY_BASENAME="${SCOPED_LEGACY_TARGET##*/}"
    SCOPED_LEGACY_BASENAME="${SCOPED_LEGACY_BASENAME%.app}"
    unset MAC_UPDATE_GOOGLE_USER_UPDATER MAC_UPDATE_GOOGLE_SYS_UPDATER
    export MAC_UPDATE_STAGE_WAIT=0 MAC_UPDATE_INTERNET_SETTLE_SECONDS=0
}

scoped_legacy_execute() {
    declare -F "$SCOPED_LEGACY_HANDLER" >/dev/null || return 10
    # Bind discovery to the exact admitted installation. A handler cannot discover
    # another copy or use a catalog name as authority for first installation.
    internet_app_path() {
        case "$1" in
            "$SCOPED_LEGACY_NAME"|"$SCOPED_LEGACY_TARGET"|"${SCOPED_LEGACY_TARGET##*/}"|"$SCOPED_LEGACY_BASENAME"|"$SCOPED_LEGACY_REGISTRY")
                printf '%s\n' "$SCOPED_LEGACY_TARGET" ;;
            *) return 1 ;;
        esac
    }
    capture_app_path() { internet_app_path "$1"; }
    # The supervising Python callback owns the launch journal and batch lease.
    # Request its handoff, never start an untracked app from a shell fallback.
    silent_launch_app() {
        case "${1:-}" in
            "$SCOPED_LEGACY_TARGET"|"$SCOPED_LEGACY_NAME"|"${SCOPED_LEGACY_TARGET##*/}"|"$SCOPED_LEGACY_BASENAME"|"$SCOPED_LEGACY_REGISTRY") ;;
            *) return 1 ;;
        esac
        printf '%s\n' "$MAC_UPDATE_ACTION_ID" > "$MAC_UPDATE_SESSION_DIR/native_launch_requested"
    }
    internet_app_quit_gracefully() { return 1; }
    quit_toolkit_launched_apps() { return 0; }
    internet_wait_launch_min_age() { return 0; }
    copy_verified_app() {
        local source="${1:-}" destination="${2:-}" rc
        INTERNET_COPY_DEFERRED=0
        [ "$destination" = "$SCOPED_LEGACY_TARGET" ] || { INTERNET_COPY_DEFERRED=1; return 2; }
        PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" python3 - "$MAC_UPDATE_PLAN_PATH" "$MAC_UPDATE_ACTION_ID" "$source" "$destination" "$MAC_UPDATE_BATCH_OWNER" <<'PY_LEGACY_REPLACEMENT'
import sys
from installed_native_updaters import execute_legacy_replacement
sys.exit(execute_legacy_replacement(*sys.argv[1:]))
PY_LEGACY_REPLACEMENT
        rc=$?
        if [ "$rc" -eq 10 ]; then INTERNET_COPY_DEFERRED=1; return 2; fi
        return "$rc"
    }
    # Office updates must not run the legacy preferences/quarantine rewrites or
    # terminate an app. MAU receives only freshly consented selected product IDs.
    iu_microsoft_365() {
        [ -n "$SCOPED_LEGACY_MAU_IDS" ] || return 10
        PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" python3 - "$MAC_UPDATE_PLAN_PATH" "$MAC_UPDATE_ACTION_ID" "$MAC_UPDATE_BATCH_OWNER" <<'PY_LEGACY_MAU_GUARD'
import sys
from installed_native_updaters import legacy_group_members
try:
    legacy_group_members(*sys.argv[1:])
except Exception:
    sys.exit(10)
PY_LEGACY_MAU_GUARD
        [ "$?" -eq 0 ] || return 10
        local cli
        cli="$(scoped_legacy_mau_binary)"
        [ -x "$cli" ] || return 10
        # Closed product IDs emitted by the guarded Python metadata reader.
        # shellcheck disable=SC2086
        run_with_timeout 1800 "$cli" --install --wait 1740 --apps $SCOPED_LEGACY_MAU_IDS
    }
    local rc=0
    "$SCOPED_LEGACY_HANDLER" || rc=$?
    [ "${INTERNET_HARD_FAIL:-0}" -eq 0 ] || return 1
    [ "$rc" -eq 0 ] || return 10
    [ "${INTERNET_SOFT_FAIL:-0}" -eq 0 ] || return 10
    return 0
}
