# Exit codes — update orchestrators

| Script | Code | Meaning |
|--------|------|---------|
| `update_all.sh` | `0` | All selected steps completed without critical failure |
| `update_all.sh` | `1` | One or more steps failed (see step summary / run log) |
| `update_all.sh` | `0` | User cancelled at confirmation prompt |
| `update_appstore.sh` | `0` | TRACK 1 and/or TRACK 2 succeeded |
| `update_appstore.sh` | `1` | mas upgrade hard failure |
| `update_appstore.sh` | `2` | Accessibility permission missing (TRACK 2 blocked) |
| `update_appstore.sh` | `10` | Soft/degraded warning (snapshots, query failed, background GUI install) |
| Leaf `update_*.sh` | `0` | Step completed cleanly (or dry-run preview) |
| Leaf `update_*.sh` | `10` | Soft/degraded failure (query failed, network unreachable, cosmetic; non-blocking) |
| Leaf `update_*.sh` | `1` | Hard failure (package/install operation broke mid-transaction; blocking) |

Only a **hard** failure (exit `1` / `127`) in steps 1–5 sets `BLOCKING_EXIT` and defers the
final macOS step. This prevents `softwareupdate -R` from restarting a Mac that may be
mid-transaction. Two deliberate exceptions:

- **Step 0 (prescan) never blocks.** It is a read-only scan and mutates nothing.
- **Soft results (exit `10`) never block.** A vendor updater that could not be verified,
  an offline feed, or a GUI automation that returned an ambiguous result surfaces as a
  warning and still allows macOS security updates to install. Suppressing security
  updates because an app updater could not be verified was the 2026-07-26 regression;
  see `docs/agents/critical_rules.md` §10.

`update_all.sh` itself exits `0` when the run was clean **or** merely degraded — a run
where self-updating apps report `LAUNCHED_UNVERIFIED` is the normal healthy outcome and
must not look like a failure to cron, CI, or `dev_sync`. Use `MAC_UPDATE_DEGRADED` or the
`degraded` field of `--json-summary` to detect warnings programmatically.

## App Store exit 2 (Accessibility)

`update_appstore.sh` exits **2** when Terminal lacks Accessibility for AppleScript TRACK 2.

Options:

- Grant Accessibility in **System Settings → Privacy & Security → Accessibility**, then re-run.
- Skip App Store: `bash update_all.sh --skip-appstore`
- Treat as non-fatal: `bash update_all.sh --treat-appstore-ax-as-warning`

## Dry-run

With `MAC_UPDATE_DRY_RUN=1` or `bash update_all.sh --dry-run`, leaf scripts print `[DRY-RUN]` and exit **0** without mutating the system. A dry-run does not prove that an external or built-in GUI updater would complete.

## Sudo Pre-authentication and Unattended / Cron Runs

`update_all.sh` attempts a single `sudo -v` pre-authentication before starting execution to ensure credentials are cached for step 6 (`softwareupdate`).

For unattended runs or cron jobs:
- Either the user stays present for step 6 to enter credentials if the `sudo` timestamp expires during long runs,
- Or run with `--skip-system` (`bash update_all.sh --skip-system`) and apply macOS system updates interactively at a later time.
