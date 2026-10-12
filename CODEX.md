# macOS Updates — Codex Agent Context

**Version:** 1.5.5 · **Platform:** Apple Silicon (arm64), macOS 13–27

Codex works on this repo with the same rules as every other agent. The shared contract (quick commands, reference docs, non-negotiable rules) lives in `AGENTS.md`:

@AGENTS.md

## Codex-specific notes

- Docs worth loading for typical Codex tasks: `docs/agents/scripts.md` (install, pipeline, `dev_sync`, adding apps), `docs/agents/critical_rules.md` (`softwareupdate -R`, `sudo mas`, update methods), `docs/user/en/GUIDE.md` (adding internet apps).
- New users: `install.sh`, then `build_inventory.sh` (no cloud import).
- `APPLICATIONS.md` is per-machine; never ship or commit another user's catalog.
- `scripts/report_update_coverage.sh` lists apps by update-method category.
- Install and removal: `docs/INSTALL.md`, `docs/UNINSTALL.md`.
