#!/usr/bin/env bash
# Static updater signals only. Never contact arbitrary bundle feed URLs.
set -o pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
. "$SCRIPT_DIR/i18n/loader.sh"
export MAC_LANG
PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" python3 - "$SCRIPT_DIR" "$@" <<'PYEOF'
import sys
from coverage_report import main
sys.exit(main(sys.argv[1], sys.argv[2:], mode='feeds'))
PYEOF
