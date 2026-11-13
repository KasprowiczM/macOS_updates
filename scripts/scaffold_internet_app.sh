#!/usr/bin/env bash
# Review-only proposal for one exact observed app path. No executable scaffolds.
# Preview: bash scripts/scaffold_internet_app.sh /path/Observed.app --json
# Export: repeat with --export --accept PREVIEW_ID after reviewing that preview.
set -o pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
. "$SCRIPT_DIR/i18n/loader.sh"
export MAC_LANG
PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" python3 - "$SCRIPT_DIR" "$@" <<'PYEOF'
import sys
from coverage_report import main
sys.exit(main(sys.argv[1], sys.argv[2:], mode='scaffold'))
PYEOF
