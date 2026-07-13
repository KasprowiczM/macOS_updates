# Exit codes — update orchestrators

| Script | Code | Meaning |
|--------|------|---------|
| `update_all.sh` | `0` | All selected steps completed without critical failure |
| `update_all.sh` | `1` | One or more steps failed (see step summary / run log) |
| `update_all.sh` | `0` | User cancelled at confirmation prompt |
| `update_appstore.sh` | `0` | TRACK 1 and/or TRACK 2 succeeded |
| `update_appstore.sh` | `1` | mas upgrade or AppleScript update failed |
| `update_appstore.sh` | `2` | Accessibility permission missing (TRACK 2 blocked) |
| Leaf `update_*.sh` | `0` | Step completed (or dry-run preview) |
| Leaf `update_*.sh` | `1` | Critical update operation failed |

When any of steps 0–5 fails, `update_all.sh` records the failure and skips the final macOS step. This prevents `softwareupdate -R` from restarting a Mac before diagnostics and the rest of the update state are safely recorded.

## App Store exit 2 (Accessibility)

`update_appstore.sh` exits **2** when Terminal lacks Accessibility for AppleScript TRACK 2.

Options:

- Grant Accessibility in **System Settings → Privacy & Security → Accessibility**, then re-run.
- Skip App Store: `bash update_all.sh --skip-appstore`
- Treat as non-fatal: `bash update_all.sh --treat-appstore-ax-as-warning`

## Dry-run

With `MAC_UPDATE_DRY_RUN=1` or `bash update_all.sh --dry-run`, leaf scripts print `[DRY-RUN]` and exit **0** without mutating the system. A dry-run does not prove that an external or built-in GUI updater would complete.
