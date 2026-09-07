#!/usr/bin/env bash
# Fast checks on staged files. Full suite remains the integration gate.
set -o pipefail
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT" || exit 1
fail=0
tmp="$(mktemp "${TMPDIR:-/tmp}/mac-update-precommit.XXXXXX")" || exit 1
trap 'rm -f "$tmp"' EXIT
git diff --cached --name-only --diff-filter=ACMR > "$tmp" || exit 1
while IFS= read -r f; do
    [ -n "$f" ] || continue
    [ -f "$f" ] || continue
    case "$f" in
        *.sh)
            if ! bash -n "$f"; then
                echo "bash -n failed: $f" >&2
                fail=1
            fi
            ;;
        *.py)
            if ! python3 -m py_compile "$f"; then
                echo "py_compile failed: $f" >&2
                fail=1
            fi
            ;;
    esac
done < "$tmp"
exit "$fail"
