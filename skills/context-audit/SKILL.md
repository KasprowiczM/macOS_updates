---
name: context-audit
description: >
  Audit Claude Code setup for token waste and context bloat. Triggers:
  "audit my context", "check my settings", "token optimization",
  "context audit", "why is Claude slow", or /context-audit.
  Reads settings files, CLAUDE.md, plugins, MCP, permissions, and
  .claudeignore. Returns health score with actionable fixes.
user-invocable: true
---

# Context Audit

Bloated context wastes tokens and degrades output quality. This skill
finds waste and produces a fix list.

## Step 1: Gather Data

Read these files in parallel to build the audit picture:

```
~/.claude/settings.json          # global settings + plugins + env + deny rules
.claude/settings.json            # project team settings
.claude/settings.local.json      # project local settings
~/.claude.json                   # MCP servers (global)
.mcp.json                        # MCP servers (project)
CLAUDE.md                        # project root instructions
.claude/CLAUDE.md                # scoped project instructions
~/.claude/CLAUDE.md              # global user instructions
CLAUDE.local.md                  # personal overrides
.claudeignore                    # file exclusion (like .gitignore)
```

Also check for:
- `.claude/rules/*.md` — path-scoped rules (count files and total lines)
- `.claude/skills/*/SKILL.md` — project skills
- `~/.claude/projects/*/memory/` — auto-memory entries

If the user already ran `/context` in this session, use that output
as the primary data source. If not, proceed with file-based analysis
(do NOT block on /context — file inspection is sufficient).

## Step 2: Audit Categories

Audit each category. Run checks in parallel where possible.

### 2a. Plugins (enabledPlugins)

Read `enabledPlugins` from `~/.claude/settings.json`. Each enabled
plugin injects its full tool schema into context **every turn**.

- Count total enabled plugins
- Flag plugins irrelevant to current project type:
  - `stripe` — only Stripe projects
  - `supabase` — only Supabase projects
  - `vercel` — only Vercel deployments
  - `playwright` — only E2E testing projects
  - `typescript-lsp` — only TypeScript projects
  - `frontend-design` — only web UI projects
  - `Notion` — only Notion-integrated projects
  - `plugin-dev` — only when building plugins
  - `claude-code-setup` / `claude-md-management` — one-time use tools
- Recommend: keep `github`, `superpowers`, `context7`, `skill-creator` as general-purpose

### 2b. MCP Servers

Read `mcpServers` from `~/.claude.json` (global) and `.mcp.json` (project).
Each server loads tool definitions into context every turn (~15-20K tokens).

- Count total servers
- Flag global servers that should be project-scoped
- Flag servers with CLI alternatives (GitHub → `gh`, Playwright → `npx playwright`)
- Flag HTTP MCP servers with exposed API keys in config

### 2c. CLAUDE.md Files

Read all CLAUDE.md files (all locations listed in Step 1).
Count total lines across all files. Test each rule/section against:

| Filter | Flag when... |
|--------|-------------|
| Default | Claude does this without instruction ("write clean code", "handle errors") |
| Contradiction | Conflicts with another rule in same or different file |
| Redundancy | Repeats info Claude gets from reading actual files (directory trees, command lists) |
| Bandaid | Fix for one past bug, not a general improvement |
| Vague | No clear action ("be natural", "use good patterns") |
| Stale | References outdated versions, removed features, or old paths |

If total lines > 200: recommend moving task-specific rules to
`.claude/rules/*.md` with path scoping (frontmatter `paths:` field).

If total lines > 500: flag as CRITICAL — this actively degrades quality.

Check for `@import` directives that pull in large reference files
unnecessarily.

### 2d. .claude/rules/

Count files in `.claude/rules/`. For each:
- Check if `paths:` frontmatter is set (mandatory for scoped rules)
- Count lines (flag > 100)
- Run same filters as CLAUDE.md

### 2e. Settings & Environment

Check all settings.json files for:

| Setting | Where | Flag if | Recommended |
|---------|-------|---------|-------------|
| `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` | env | Missing or > 80 | `75` |
| `BASH_MAX_OUTPUT_LENGTH` | env | At default (30K) | `150000` |
| `permissions.deny` | permissions | Missing | Add deny rules for build artifacts |
| `effortLevel` | root | Not set when could help | `medium` for routine, `high` for complex |
| `cleanupPeriodDays` | root | Missing | `20` (cleanup orphaned worktrees) |

### 2f. File Permissions (deny rules)

Check for `permissions.deny` in all settings files. If missing,
detect project type and recommend:

| Detected by... | Deny these paths |
|-----------------|-----------------|
| `package.json` | `node_modules/**`, `dist/**`, `build/**`, `.next/**`, `coverage/**` |
| `Cargo.toml` | `target/**` |
| `go.mod` | `vendor/**` |
| `pyproject.toml` / `requirements.txt` | `__pycache__/**`, `.venv/**`, `*.egg-info/**` |
| `.git/` (always) | `.git/objects/**` |
| `.env` (always) | `.env`, `.env.*` |

### 2g. .claudeignore

Check if `.claudeignore` exists. If missing AND bloat directories
exist (node_modules, dist, build, .git/objects, logs/):

Recommend creating `.claudeignore` to prevent Claude from indexing
these in file searches. Example:

```
node_modules/
dist/
build/
.next/
coverage/
*.log
.git/objects/
__pycache__/
.venv/
```

### 2h. Auto Memory

Check `~/.claude/projects/*/memory/` for stale or bloated entries.
Flag if total auto-memory exceeds 50 entries across projects.
Note: users can audit with `/memory` command.

### 2i. Hooks (Bonus)

Check if `hooks` key exists in settings. If not, recommend:
- `PreCompact` hook to preserve critical state before compaction
- Compaction instructions in CLAUDE.md: "When compacting, preserve
  the list of modified files and pending tasks"

## Step 3: Score and Report

Start at 100. Deductions:

| Issue | Points |
|-------|--------|
| Per plugin enabled | -2 |
| Per irrelevant plugin for project | -3 |
| Per MCP server (global) | -3 |
| Per MCP server (project-scoped) | -1 |
| CLAUDE.md > 200 lines total | -10 |
| CLAUDE.md > 500 lines total | -20 |
| Per 5 rules flagged by filters | -5 |
| Contradictions between files | -10 |
| Missing autocompact override | -10 |
| Missing bash output override | -5 |
| No deny rules + bloat dirs exist | -10 |
| No .claudeignore + bloat dirs | -5 |
| Skill > 200 lines | -5 each |
| Skill > 500 lines | -10 each |
| Stale auto-memory (> 50 entries) | -5 |

Floor at 0.

Output format:

```
# Context Audit

Score: {N}/100 [{CLEAN|NEEDS WORK|BLOATED|CRITICAL}]

## Summary
{1-2 sentence overview}

## Issues Found

### [{CRITICAL|WARNING|INFO}] {Category}
{What's wrong}
Fix: {One-line actionable fix}

### Rules to Cut
{Each flagged rule: the text, which filter, why}

### Conflicts
{Contradictions between files, with paths}

## Top 3 Fixes (by token savings)
1. {Highest-impact fix with estimated savings}
2. {Second}
3. {Third}

## Session Tips
- Use /compact at logical breakpoints (after finishing a task)
- Use /clear when switching to unrelated tasks
- Use /btw for quick questions that don't need to stay in context
- Start new sessions every 15-20 messages for complex work
- Use Sonnet for routine work, Opus for architecture decisions
```

Score labels: 90-100 CLEAN, 70-89 NEEDS WORK, 50-69 BLOATED, 0-49 CRITICAL.
Severity: CRITICAL > 10pts, WARNING 5-10pts, INFO < 5pts.

## Step 4: Fix

After the report, auto-apply safe changes (settings.json env/deny
rules, .claudeignore). Show diffs for CLAUDE.md — let user confirm
before modifying instruction files.

Offer:
- Cleaned CLAUDE.md with flagged rules removed
- settings.json with missing env vars and deny rules added
- .claudeignore created if missing
- List of plugins to disable via `/config`
- List of MCP servers to move to project-scoped `.mcp.json`
- Compaction instructions to add to CLAUDE.md
