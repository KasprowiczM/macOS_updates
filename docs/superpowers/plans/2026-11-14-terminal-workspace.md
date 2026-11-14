# Terminal Workspace Implementation Plan

> For agentic workers: use subagent-driven-development or executing-plans for the assigned task boundaries.

**Goal:** Deliver and publish a localized terminal workspace and first-run wizard in source 1.8.0.

**Architecture:** Curses rendering and pure UI state sit above a whitelisted PTY supervisor. Existing update/setup/inventory code remains authoritative for consent and execution. UI settings never store grants.

**Tech Stack:** Python 3.9+ standard library, curses, PTY, Bash 3.2; existing React landing.

**Spec:** ../specs/2026-11-14-terminal-workspace-design.md

## Global constraints

- Seven languages, no automatic host dependency installation, no arbitrary shell commands.
- Existing target/source/receipt/consent checks and durable recovery remain in force.
- One active mutation process; no unverified recipe activation or fabricated parallel acceptance.
- No real updates are required by tests; use guarded fixtures and explicit terminal interaction.
- Preserve non-TTY/JSON/CLI behavior and restore terminal state on every exit.

## Review focus

- EOF, hidden prompts and stale confirmation must never grant permission.
- Resize and Unicode must not crash or make active controls unreachable.
- Child output, settings and historical logs are untrusted; strip terminal controls and validate bounds.
- Child process ownership and password input must remain private; cancellation must not erase evidence.
- First-run state must persist only after finish, without overwriting existing policies.

## Tasks

- [x] Finish 1.7.8 consent/readiness fixes and isolate any full-suite regressions.
- [x] Implement lib/python/tui_backend.py: settings, command whitelist, group flags, PTY supervision and safe history; test fixture lifecycle, secrets and invalid inputs.
- [x] Implement lib/python/tui_i18n.py: complete seven-language UI/help/wizard catalog with placeholder parity.
- [x] Implement lib/python/terminal_app.py: pure navigation/layout model, three panels, task/log views, palette, input/confirm overlays, settings and wizard.
- [x] Add --tui/--cli routes to existing entry scripts and a nonexecuting preferences-only mode. Test routing and recursion prevention.
- [x] Add guarded PTY interaction tests, deterministic screen/layout checks and visual review. Iterate on verified defects.
- [x] Update version1.8.0, seven-language instructions, script index, changelog and landing facts.
- [x] Run complete local source gates: 1441 guarded tests, syntax and secret checks.
- Publication: push source and landing, verify CI/deployment and record the resulting commits in the private handoff. Live recipe acceptance remains deferred.
