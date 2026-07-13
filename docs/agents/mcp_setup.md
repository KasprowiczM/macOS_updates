# MCP Server Setup

## Critical: Always Use Absolute Paths

Prevents `exec: "npx": executable file not found in $PATH` errors.

```json
{
  "command": "/Users/<you>/.local/share/mac-update/node/bin/npx",
  "env": {
    "PATH": "/Users/<you>/.local/share/mac-update/npm-global/bin:/Users/<you>/.local/share/mac-update/node/bin:/Users/<you>/.bun/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
  }
}
```

- Preferred: `~/.local/share/mac-update/node/bin/npx` (managed by `update_npm_cli.sh`)
- Homebrew fallback on the supported platform: `/opt/homebrew/bin/npx` (Apple Silicon)
- Always include `PATH` in `env` block — Claude Code does not inherit shell PATH.
