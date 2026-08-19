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
IGNORED_TRACKED="$(git ls-files -z | xargs -0 git check-ignore --no-index 2>/dev/null || true)"
if [ -n "$IGNORED_TRACKED" ]; then
    echo "  FAIL tracked gitignored file(s):"
    printf '%s\n' "$IGNORED_TRACKED"
    FAIL=1
fi

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

# ── Local-only advisory: shell profiles are outside git, so gitleaks never
# sees them. On 2026-08-19 a live GitHub PAT was found sitting in plaintext in
# ~/.zshrc AND ~/.zshenv, plus 36 un-rotated ~/.zshrc.macupd-backup-* copies.
# Advisory, never fatal: this machine's dotfiles are not the repo's contract,
# and CI has no profiles to scan. Set MAC_UPDATE_SKIP_PROFILE_SCAN=1 to skip.
if [ "${MAC_UPDATE_SKIP_PROFILE_SCAN:-0}" != "1" ]; then
    PROFILE_HITS=""
    for prof in "$HOME/.zshrc" "$HOME/.zshenv" "$HOME/.zprofile" "$HOME/.bash_profile" "$HOME/.bashrc"; do
        [ -f "$prof" ] || continue
        if grep -Eq '(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}' "$prof" 2>/dev/null; then
            PROFILE_HITS="$PROFILE_HITS $prof"
        fi
    done
    # Un-rotated profile backups keep old secrets alive long after the live
    # file is cleaned.
    STALE_BACKUPS="$(ls -1 "$HOME"/.zshrc.macupd-backup-* 2>/dev/null | wc -l | tr -d ' ')"
    if [ -n "$PROFILE_HITS" ]; then
        echo "  ⚠️  ADVISORY: credential-shaped strings in shell profile(s):$PROFILE_HITS"
        echo "      Move the secret to ~/.config/secrets/<name>.env (chmod 600) and source it."
    fi
    if [ -n "$STALE_BACKUPS" ] && [ "$STALE_BACKUPS" -gt 10 ]; then
        echo "  ⚠️  ADVISORY: $STALE_BACKUPS ~/.zshrc.macupd-backup-* files — each is a frozen copy of your profile."
    fi
fi

if [ "$FAIL" -ne 0 ]; then
    exit 1
fi
echo "Secret scan passed"
exit 0
