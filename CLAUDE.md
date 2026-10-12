# macOS Updates (v1.5.5)

Claude Code entry point. The shared project contract (quick commands, reference docs, non-negotiable rules) lives in `AGENTS.md` and is imported here so there is exactly one copy to maintain:

@AGENTS.md

## Claude Code specifics

- Switch to the Advisor model with `/agent:advisor` or `claude --model claude-opus-4-7`; delegate cheap work to the `worker-haiku` agent (`.claude/agents/`).
- Slash commands for common operations live in `.claude/commands/` (`/mac-update`, `/mac-status`, `/mac-update-brew`, ...).
- Local deny rules for secrets are described in `docs/agents/security.md` (`.claude/settings.local.json` is gitignored).
- Planning rule: explore the codebase thoroughly and reach 95% confidence before changing anything; ask follow-up questions otherwise.
