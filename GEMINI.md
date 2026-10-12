# macOS Updates (v1.5.5)

Gemini CLI / Antigravity entry point. The shared project contract (quick commands, reference docs, non-negotiable rules) lives in `AGENTS.md`:

@AGENTS.md

## Model hierarchy (Gemini CLI / Antigravity)

| Role | Profile / Model | Purpose |
|------|-----------------|---------|
| **Default Worker** | `low-Pro` | Routine tasks without deep reasoning |
| **Orchestrator** | `orchestrator` (Pro 3.1 High) | Planning, delegating |
| **Advisor** | `advisor` (Pro 3.1 High) | Architecture, ADRs — NO implementation |
| **Subagent** | `flash-worker` (Gemini 3 Flash) | Fast boilerplate, test snippets |

## Gemini specifics

- Secrets and noise are excluded from context via `.geminiignore`; see `docs/agents/security.md`.
- Never install apps for the user — update only what is already installed; build inventory per Mac.
