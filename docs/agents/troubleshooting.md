# Troubleshooting

| Problem | Fix |
|---------|-----|
| New Mac — where to start? | `bash install.sh` or `setup.sh` + `build_inventory.sh` |
| Wrong app catalog / another user's apps | `bash build_inventory.sh` — never copy someone else's `APPLICATIONS.md` |
| App not auto-updating | `bash scripts/report_update_coverage.sh` — add handler per GUIDE |
| macOS update not applied after reboot | `softwareupdate -ia -R` — never `sudo reboot` |
| macOS update step exits after declining restart | Expected without `-R`; rerun and accept restart or use System Settings |
| `mas upgrade` fails | `sudo mas upgrade` (CVE-2025-43411) |
| iPad apps "not allowed" error | System Settings → Privacy → Accessibility → add terminal |
| Wrong language | Edit `.mac_update_prefs` → `MAC_LANG=en` |
| APPLICATIONS.md missing | `bash build_inventory.sh` or `dev_sync/dev-sync-import.sh` (owner) |
| `mas` Spotlight warning walls | `export MAS_NO_AUTO_INDEX=1` before calling `mas` |
| Script won't execute | `chmod +x *.sh dev_sync/*.sh` or re-run `setup.sh` |
| `brew: command not found` | `eval "$(/opt/homebrew/bin/brew shellenv)"` |
| `npx` / `node` not found in MCP config | Run `bash update_npm_cli.sh`; fix paths with `scripts/fix_mcp_configs.py` |
| No disk space during update | `brew cleanup --prune=all` |
| Proton mirror has generated files | `bash dev_sync/dev-sync-prune-excluded.sh --plan-out dev_sync_cleanup_plan.json` |
| Free Proton local cache safely | `bash dev_sync/dev-sync-proton-status.sh --full` |
| `mas` login error | Log into App Store manually first |
| Firefox / KeePassXC / Trezor not updating | Check connectivity, `hdiutil verify`, `spctl --assess` |
| Dev sync import rejects manifest path | Regenerate with `dev_sync/dev-sync-export.sh` |
| Microsoft 365 not updating | `msupdate` CLI required (ships with any MS365 app) |
| Docker not updating | Docker Desktop v4.37+ for `docker desktop update` |
| Intel Mac | **Not supported** — Apple Silicon only |
| Homebrew "untrusted taps" warning | `brew trust --formula <user>/<tap>/<formula>` or `brew untap` |
| CI shellcheck fails | See `.shellcheckrc`; run same `find \| xargs shellcheck` as `.github/workflows/ci.yml` |

## Skills (in `skills/` directory)

- `computer-use-agents` — GUI automation
- `os-scripting` — system admin
- `bash-pro` — defensive bash patterns
- `context-audit` — token optimization
