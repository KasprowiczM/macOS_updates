#!/usr/bin/env bash
# ============================================================
# Backward-compatibility wrapper — calls dev_sync/dev-sync-verify-git.sh
# ============================================================
set -eu
exec bash "$(cd "$(dirname "$0")" && pwd)/dev_sync/dev-sync-verify-git.sh" "$@"
