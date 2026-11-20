#!/usr/bin/env bash
# Explicit, pinned toolkit self-update. Never runs from automatic startup.
set -o pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
. "$SCRIPT_DIR/lib/platform.sh"
mac_update_tool_usable python3 || { echo 'Python 3 is unavailable.' >&2; exit 2; }
PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" exec python3 -c '
import sys
from toolkit_update import main
sys.exit(main(sys.argv[1], sys.argv[2:]))
' "$SCRIPT_DIR" "$@"
