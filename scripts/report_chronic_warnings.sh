#!/usr/bin/env bash
# report_chronic_warnings.sh — print trailing non-OK step streaks from run summaries
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOGS="${MAC_UPDATE_LOGS_DIR:-$SCRIPT_DIR/logs}"
WINDOW="${MAC_UPDATE_CHRONIC_WINDOW:-10}"
THRESHOLD="${MAC_UPDATE_CHRONIC_THRESHOLD:-3}"

# Localized labels (silent fallback to English when the loader is unavailable).
if [ -f "$SCRIPT_DIR/i18n/loader.sh" ]; then
    # shellcheck source=i18n/loader.sh
    . "$SCRIPT_DIR/i18n/loader.sh" >/dev/null 2>&1 || true
fi
export CHRONIC_TITLE="${L_ALL_CHRONIC_TITLE:-Chronic warning streaks:}"
export CHRONIC_ITEM_FMT="${L_ALL_CHRONIC_ITEM_FMT:-- %s: %s trailing non-OK runs (first in streak: %s)}"

python3 - "$SCRIPT_DIR" "$LOGS" "$WINDOW" "$THRESHOLD" <<'PY' || true
import os
import sys

script_dir = sys.argv[1]
logs_dir = sys.argv[2]
window = int(sys.argv[3])
threshold = int(sys.argv[4])

sys.path.insert(0, os.path.join(script_dir, "lib", "python"))

from chronic_warnings import find_chronic_streaks

hits = find_chronic_streaks(logs_dir, window=window, threshold=threshold)
if hits:
    print(os.environ.get("CHRONIC_TITLE", "Chronic warning streaks:"))
    fmt = os.environ.get("CHRONIC_ITEM_FMT", "- %s: %s trailing non-OK runs (first in streak: %s)")
    for hit in hits:
        try:
            print(fmt % (hit["step"], hit["streak"], hit["first_timestamp"]))
        except (TypeError, ValueError):
            print(f"- {hit['step']}: {hit['streak']} (first in streak: {hit['first_timestamp']})")
PY

exit 0
