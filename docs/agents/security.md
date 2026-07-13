# Security Rules

## Secrets — Never in Repo

Private files are `.gitignore`d and managed by `dev_sync`:

| File | Storage |
|------|---------|
| `.env` | Proton/cloud only |
| `.dev_sync_config.json` | Proton/cloud only |
| `APPLICATIONS.md`, `UPDATES.md` | Proton/cloud only |

`dev_sync` exports only the private overlay and writes a provider-side `.dev_sync_manifest.json`. Generated directories, dependency installs, caches, logs, and external skill repos are excluded from Proton sync and should be recreated from their original source.

**Claude must never read these files** even if they exist locally. The `settings.local.json` deny rules enforce this:

```json
"deny": [
  "Read(.env)",
  "Read(.env.*)",
  "Read(.dev_sync_config.json)",
  "Read(**/.git/objects/**)",
  "Read(**/dev_sync_logs/**)"
]
```

## .claudeignore Policy

`.claudeignore` excludes from Claude's context:
- All secret/config files (`.env`, `*.pem`, `*.key`, `*.p12`)
- Logs (`dev_sync_logs/`, `*.log`)
- Binaries/archives (`.dmg`, `.pkg`, `.zip`, etc.)
- macOS junk (`.DS_Store`)
- Build artefacts (`__pycache__`, `dist/`, `build/`)

## Bash Safety Rules

- Never run `cat .env` or read sensitive files via Bash tool
- All scripts must use `SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"` — no hardcoded `/Users/<name>/`
- Use `mktemp` for executable temp files and downloads; do not use predictable `/tmp/name_$$` paths.
- Downloaded DMGs must pass `hdiutil verify`; copied `.app` bundles must pass Gatekeeper assessment; PKGs must pass `pkgutil --check-signature`.
- Mount DMGs at unique paths inside the private session directory. Validate incoming bundle identifier and signing team, retain the installed app during the staged swap, and roll back on any copy or post-install validation failure.
- `dev_sync` manifest and cleanup-plan relpaths must pass safe relative-path validation. Reject absolute paths, `..`, empty paths, newlines, NUL/control characters, and resolved paths outside the intended root.
- Private files/configs must use atomic same-directory replacement and restrictive permissions. Cloud imports must stage an allowlisted file set and roll back the transaction after any partial commit failure.
- Enforce the platform boundary (Apple Silicon arm64 and macOS 13+) before setup or update mutations.
- Avoid commands that dump gigantic logs without redirect; pipe to file and read selectively
- Output limits: ~200 lines per tool call; redirect long builds to file

## MCP Server Policy

Only enable MCP servers that this repo actively uses. Disabled servers (Gmail, Google Calendar, Google Drive, memory) are listed in `.claude/settings.json → disabledMcpServers`. Do not re-enable without explicit user decision.
