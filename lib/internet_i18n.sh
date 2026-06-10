#!/usr/bin/env bash
# lib/internet_i18n.sh — printf helpers for update_internet_apps.sh (Bash 3.2+)

internet_msg() {
  # Usage: internet_msg "$L_INTERNET_NOT_INSTALLED" "Google Chrome"
  local fmt="$1"
  shift
  # shellcheck disable=SC2059
  printf "$fmt" "$@"
}

internet_diag_log() {
  local line="$1"
  if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ]; then
    echo "$line" >> "$MAC_UPDATE_SESSION_DIR/internet_diag.txt"
  fi
}

internet_diag_section() {
  local title="$1"
  if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ]; then
    {
      echo ""
      echo "=== $title ==="
      echo "$(date '+%Y-%m-%d %H:%M:%S')"
    } >> "$MAC_UPDATE_SESSION_DIR/internet_diag.txt"
  fi
}
