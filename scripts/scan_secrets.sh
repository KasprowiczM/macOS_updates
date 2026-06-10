#!/usr/bin/env bash
# scan_secrets.sh — lightweight secret scan for CI and pre-push (Bash 3.2+)
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SCRIPT_DIR" || exit 1

FAIL=0

if command -v gitleaks >/dev/null 2>&1; then
    echo "── gitleaks detect (tracked git content) ──"
    if gitleaks detect --source . -v --redact; then
        echo "  OK gitleaks"
    else
        echo "  FAIL gitleaks"
        FAIL=1
    fi
else
    echo "── pattern scan (gitleaks not installed) ──"
    PATTERNS=(
        'github_pat_[A-Za-z0-9_]+'
        'ghp_[A-Za-z0-9]{20,}'
        'sk-[A-Za-z0-9]{20,}'
        'AKIA[0-9A-Z]{16}'
    )
    for pat in "${PATTERNS[@]}"; do
        if git grep -E "$pat" -- ':!*.md' ':!.env.example' ':!scripts/scan_secrets.sh' ':!.github/workflows/gitleaks.yml' 2>/dev/null; then
            echo "  FAIL pattern match: $pat"
            FAIL=1
        fi
    done
    if [ "$FAIL" -eq 0 ]; then
        echo "  OK pattern scan"
    fi
fi

# Tracked files that must never be committed
FORBIDDEN_TRACKED=(
    .env
    .dev_sync_config.json
    APPLICATIONS.md
    UPDATES.md
)
for f in "${FORBIDDEN_TRACKED[@]}"; do
    if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
        echo "  FAIL tracked forbidden file: $f"
        FAIL=1
    fi
done

if [ "$FAIL" -ne 0 ]; then
    exit 1
fi
echo "Secret scan passed"
exit 0
