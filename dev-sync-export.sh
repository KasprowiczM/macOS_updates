#!/usr/bin/env bash
# ============================================================
# Backward-compatibility wrapper — calls dev_sync/dev-sync-export.sh
# ============================================================
set -eu
exec bash "$(cd "$(dirname "$0")" && pwd)/dev_sync/dev-sync-export.sh" "$@"
