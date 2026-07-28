# macOS Updates — Codex Agent Context

Codex is a cloud-based coding agent for this repo — read shared rules before modifying any script.

**Version:** 1.0.21 · **Platform:** Apple Silicon (arm64), macOS 13+

## Shared Rules & Architecture

@CLAUDE.md

## Reference Docs

Load only when relevant:

- @docs/agents/scripts.md — install.sh, build_inventory.sh, pipeline, dev_sync, new Mac setup
- @docs/agents/architecture.md — Bash 3.2, session dir, Python heredocs, i18n
- @docs/agents/critical_rules.md — softwareupdate -R, sudo mas, update methods
- @docs/agents/troubleshooting.md — common failures
- @docs/agents/codex_notes.md — adding internet apps, download URLs
- @docs/INSTALL.md · @docs/UNINSTALL.md — user install/remove

## Production notes

- New users: `install.sh` → `build_inventory.sh` (no cloud import)
- `APPLICATIONS.md` is per-machine; never ship another user's catalog
- `scripts/report_update_coverage.sh` lists apps by update-method category
