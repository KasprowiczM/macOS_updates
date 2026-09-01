# macOS Updates

## GitHub Actions budget guardrail

This repository is owned by the `KasprowiczM` GitHub Free account. Private repositories share a hard allowance of 2,000 GitHub Actions minutes per month.

- Do not add, enable, or broaden scheduled workflows without the user's explicit approval.
- Default to `ubuntu-latest`; use macOS, Windows, or larger runners only when technically required and explicitly approved.
- Expensive platform-specific jobs should be manual or release-only, not triggered by every branch push.
- Restrict push/PR triggers by branch and path, add `concurrency` with cancellation, and set `timeout-minutes` on every job.
- Before changing Actions, estimate the monthly run count and minute impact. Do not change billing or spending limits without explicit approval.
- Public-repository standard runners may be free, but the same anti-waste rules still apply.


Automated macOS update system — Bash 3.2+ scripts + Python 3 backend, **Apple Silicon (arm64) only**, macOS 13–26, 7 languages, v**1.4.3**, multi-cloud private overlay via `dev_sync/`.

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
- @docs/agents/critical_rules.md — softwareupdate -R, sudo mas (macOS 15.7.2+/14.8.2+/26.1+ entitlement change), App Store two-track, version detection, update methods per app, APPLICATIONS.md structure
- @docs/agents/exit_codes.md — the 0 / 10 / 1 severity contract and which failures defer the macOS system update
- @docs/agents/troubleshooting.md — common failures + fixes, skills directory
- @docs/agents/mcp_setup.md — MCP server absolute path requirement, PATH env fix
- @docs/agents/handoff.md — how to create handoff files between sessions
- @docs/agents/security.md — secret handling and deny rules

## Subagents

- **Advisor** — Principal Architect: architectural analysis and execution planning only, no implementation code.
- **Worker** — Fast, cheap execution tasks delegated by the orchestrator.

## Non-Negotiable Rules

1. **`softwareupdate` MUST have `-R`** — without it, macOS updates download but never apply.
2. **`mas upgrade` MUST have `sudo` AND explicit app IDs** — the entitlement change on macOS
   15.7.2+/14.8.2+/26.1+ (https://github.com/orgs/Homebrew/discussions/6550) still applies, but a
   bare `mas upgrade` makes `mas` re-enumerate the outdated set in *root's* context rather than the
   one the run measured. On 2026-09-01 that silently skipped WhatsApp while upgrading Copilot.
   Pass the IDs from the pre-scan, then retry anything still outdated once in the invoking user's
   session — App Store receipts belong to the user, not to root.
3. **Bash 3.2 only** — no `declare -A`, `mapfile`, `readarray`.
4. **No new standalone pipeline entrypoints** — update pipeline Python stays in heredocs or importable pure-function modules under `lib/python/` (which `run_tests.sh` compiles and tests); `dev_sync/` and `scripts/fix_mcp_configs.py` are the existing Python backend/tools.
5. **No hardcoded paths** — use `SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"`.
6. **All `update_*.sh` orchestrators must `set -o pipefail`** — and must **not** `set -e`; the orchestrator has to run every step even on partial failure.
7. **A config method name is only valid if a handler exists** — every method in `config/internet_app_methods.txt` needs an `internet_handler_*` / `iu_*` implementation. `tests/test_safety_static.py` enforces this.
8. **Never call interactive `sudo` without a TTY** — see `docs/agents/critical_rules.md`.

---

## PLANNING RULE

Do not make any changes until you have 95% confidence in what you need to build. Ask me follow-up questions until you reach that confidence level.
