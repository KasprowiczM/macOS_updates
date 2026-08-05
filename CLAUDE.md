# macOS Updates

Automated macOS update system — Bash 3.2+ scripts + Python 3 backend, **Apple Silicon (arm64) only**, macOS 13–26, 7 languages, v**1.3.1**, multi-cloud private overlay via `dev_sync/`.

## Quick Commands

```bash
bash install.sh                       # One-line new-user install (see docs/INSTALL.md)
bash build_inventory.sh               # Build APPLICATIONS.md from this Mac only
bash update_all.sh                    # Full update (all 7 steps)
bash update_all.sh --dry-run          # Preview without mutations
bash scripts/report_update_coverage.sh # Supported vs missing apps (by category)
bash dev_sync/dev-sync-import.sh      # Restore private overlay (owners only)
bash run_tests.sh                     # bash -n + py_compile + unittest
bash -n update_all.sh                 # Syntax check
```

## Run logs & diagnostics

- Every `update_all.sh` invocation writes `logs/update_all_<YYYYMMDD_HHMMSS>.log`
  (gitignored). Rotation keeps the last `MAC_UPDATE_MAX_LOGS` files (default 30).
- On non-zero `OVERALL_EXIT`, the EXIT trap appends every `*.txt` snapshot from
  the session dir into the run log before wiping the dir. Capped at 200 lines
  per snapshot.
- `update_appstore.sh` writes `$MAC_UPDATE_SESSION_DIR/appstore_diag.txt` on
  TRACK 1 (`sudo mas upgrade`) failure, on TRACK 2 (AppleScript) non-success
  branches, and on a final `mas outdated` non-empty result. This file is
  picked up by `update_all.sh`'s failure-path logger.

## Model Hierarchy

| Role | Model | Purpose |
|------|-------|---------|
| **Orchestrator** | `claude-sonnet-4-6` | Default — daily coding, planning, coordinating subagents |
| **Advisor** | `claude-opus-4-7` | Architecture analysis, code review, ADRs — NO implementation code |
| **Worker** | `claude-haiku-4-5-20251001` | Fast/cheap tasks: boilerplate, refactors, log summaries, test snippets |

- Switch to Advisor: `/agent:advisor` or `claude --model claude-opus-4-7`
- Delegate to Worker: Sonnet orchestrator calls `Task()` → `worker-haiku` agent handles it

## Reference Docs

Load only when relevant to your task:

- @docs/agents/scripts.md — script list, update_all.sh step order, migration_setup.sh phases 0a-16, dev sync, adding internet apps
- @docs/agents/architecture.md — Bash 3.2 constraints, session dir, Python inline heredocs, i18n, Homebrew prefix detection, cloud sync
- @docs/agents/critical_rules.md — softwareupdate -R, sudo mas (macOS 15.7.2+/14.8.2+/26.1+ entitlement change), App Store two-track, version detection, update methods per app
- @docs/agents/troubleshooting.md — common failures + fixes, skills directory
- @docs/agents/handoff.md — how to create handoff files between sessions and preserve context
- @docs/agents/security.md — secret handling, deny rules, .claudeignore policy

## Non-Negotiable Rules

1. **`softwareupdate` MUST have `-R`** — without it, macOS updates download but never apply.
2. **`mas upgrade` MUST have `sudo`** — macOS 15.7.2+/14.8.2+/26.1+ entitlement change (https://github.com/orgs/Homebrew/discussions/6550).
3. **Bash 3.2 only** — no `declare -A`, `mapfile`, `readarray`.
4. **No new standalone pipeline entrypoints** — update pipeline Python stays in heredocs or importable pure-function modules under `lib/python/` (which `run_tests.sh` compiles and tests); `dev_sync/` and `scripts/fix_mcp_configs.py` are the existing Python backend/tools.
5. **No hardcoded paths** — use `SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"`.
   For temp files: `mktemp -d "${TMPDIR:-/tmp}/mac_update_*.XXXXXX"` (never bare `/tmp/`).
6. **All `update_*.sh` orchestrators must `set -o pipefail`** — without it, a
   piped command's upstream failure is silently lost. Do **not** add `set -e` —
   the orchestrator is expected to run every step even on partial failure.

---

## PLANNING RULE

Do not make any changes or write code until you have thoroughly explored the codebase and have **95% confidence** in what you need to build. Stop and ask follow-up questions until you reach that confidence level. Verify your assumptions 5× before exiting Plan Mode.
