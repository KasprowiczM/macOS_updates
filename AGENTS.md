# macOS Updates

Automated macOS update system — Bash 3.2+ scripts + Python 3 backend, **Apple Silicon (arm64) only**, macOS 13–26, 7 languages, v**1.3.1**, multi-cloud private overlay via `dev_sync/`.

## Quick Commands

```bash
bash install.sh                         # One-line new-user install
bash build_inventory.sh                 # Build APPLICATIONS.md from this Mac
bash update_all.sh                      # Full update (all 7 steps)
bash scripts/report_update_coverage.sh  # Coverage by update method category
bash dev_sync/dev-sync-import.sh        # Restore private overlay (owners)
bash run_tests.sh                       # Full test suite
bash -n update_all.sh                   # Syntax check
```

## Model Hierarchy

| Role | Model | Purpose |
|------|-------|---------|
| **Orchestrator** | `claude-sonnet-4-6` | Default — daily work, planning, coordinating subagents |
| **Advisor** | `claude-opus-4-7` | Architecture, code review, ADRs — NO implementation code |
| **Worker** | `claude-haiku-4-5-20251001` | Fast tasks: boilerplate, refactors, log summaries |

## Reference Docs

Load only when relevant to your task:

- @docs/agents/scripts.md — script list, update_all.sh step order, migration_setup.sh phases 0a-16, dev sync commands, new Mac setup, adding internet apps
- @docs/agents/architecture.md — Bash 3.2 constraints, session dir, Python inline heredocs, i18n, Homebrew prefix detection, cloud sync
- @docs/agents/critical_rules.md — softwareupdate -R, sudo mas (CVE-2025-43411), App Store two-track, version detection, update methods per app, APPLICATIONS.md structure
- @docs/agents/troubleshooting.md — common failures + fixes, skills directory
- @docs/agents/mcp_setup.md — MCP server absolute path requirement, PATH env fix
- @docs/agents/handoff.md — how to create handoff files between sessions
- @docs/agents/security.md — secret handling and deny rules

## Subagents

- **Advisor** — Principal Architect: architectural analysis and execution planning only, no implementation code.
- **Worker** — Fast, cheap execution tasks delegated by the orchestrator.

## Non-Negotiable Rules

1. **`softwareupdate` MUST have `-R`** — without it, macOS updates download but never apply.
2. **`mas upgrade` MUST have `sudo`** — CVE-2025-43411 (Sequoia).
3. **Bash 3.2 only** — no `declare -A`, `mapfile`, `readarray`.
4. **No new standalone pipeline entrypoints** — update pipeline Python stays in heredocs or importable pure-function modules under `lib/python/` (which `run_tests.sh` compiles and tests); `dev_sync/` and `scripts/fix_mcp_configs.py` are the existing Python backend/tools.
5. **No hardcoded paths** — use `SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"`.

---

## PLANNING RULE

Do not make any changes until you have 95% confidence in what you need to build. Ask me follow-up questions until you reach that confidence level.
