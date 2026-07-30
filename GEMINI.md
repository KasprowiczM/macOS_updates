# macOS Updates

Automated macOS update system — Bash 3.2+ scripts + Python 3 backend, **Apple Silicon (arm64) only**, macOS 13–26, **v1.0.21**, 7 languages, multi-cloud private overlay via `dev_sync/`.

## Quick Commands

```bash
bash install.sh                         # One-line new-user install
bash build_inventory.sh                 # Build APPLICATIONS.md from this Mac
bash update_all.sh                      # Full update (all steps)
bash scripts/report_update_coverage.sh  # Supported vs missing apps
bash dev_sync/dev-sync-import.sh        # Restore private overlay (owners)
bash run_tests.sh                       # Full test suite
bash -n update_all.sh                   # Syntax check
```

## Model Hierarchy (Gemini CLI / Antigravity)

| Role | Profile / Model | Purpose |
|------|-----------------|---------|
| **Default Worker** | `low-Pro` | Routine tasks without deep reasoning |
| **Orchestrator** | `orchestrator` (Pro 3.1 High) | Planning, delegating |
| **Advisor** | `advisor` (Pro 3.1 High) | Architecture, ADRs — NO implementation |
| **Subagent** | `flash-worker` (Gemini 3 Flash) | Fast boilerplate, test snippets |

## Reference Docs

- @docs/agents/scripts.md — pipeline, install, dev_sync, adding apps
- @docs/agents/architecture.md — Bash 3.2, session dir, i18n
- @docs/agents/critical_rules.md — softwareupdate -R, sudo mas
- @docs/agents/troubleshooting.md — common failures
- @docs/agents/security.md — secrets, .geminiignore

## Non-Negotiable Rules

1. **`softwareupdate` MUST have `-R`**
2. **`mas upgrade` MUST have `sudo`** (macOS 15.7.2+/14.8.2+/26.1+ entitlement change, see https://github.com/orgs/Homebrew/discussions/6550)
3. **Bash 3.2 only** — no `declare -A`, `mapfile`, `readarray`
4. **No new standalone pipeline entrypoints** — update pipeline Python stays in heredocs or importable pure-function modules under `lib/python/` (which `run_tests.sh` compiles and tests); `dev_sync/` and `scripts/fix_mcp_configs.py` are the existing Python backend/tools.
5. **No hardcoded paths** — use `SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"`
6. **Never install apps for users** — update only what is already installed; build inventory per Mac
