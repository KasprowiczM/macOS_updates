#!/usr/bin/env bash
# report_chronic_warnings.sh — print trailing non-OK step streaks from run summaries
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOGS="${MAC_UPDATE_LOGS_DIR:-$SCRIPT_DIR/logs}"
WINDOW="${MAC_UPDATE_CHRONIC_WINDOW:-10}"
THRESHOLD="${MAC_UPDATE_CHRONIC_THRESHOLD:-3}"

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
    print("Chronic warning streaks:")
    for hit in hits:
        print(
            f"- {hit['step']}: {hit['streak']} trailing non-OK runs "
            f"(first in streak: {hit['first_timestamp']})"
        )
PY

exit 0
