# Exit codes — update orchestrators

| Script | Code | Meaning |
|--------|------|---------|
| `update_all.sh` | `0` | All selected steps completed without critical failure |
| `update_all.sh` | `1` | One or more steps failed (see step summary / run log) |
| `update_all.sh` | `0` | User cancelled at confirmation prompt |
| `update_appstore.sh` | `0` | TRACK 1 and/or TRACK 2 succeeded |
| `update_appstore.sh` | `1` | mas upgrade hard failure |
| `update_appstore.sh` | `2` | Accessibility permission missing (TRACK 2 blocked) |
| `update_appstore.sh` | `10` | Soft/degraded warning (snapshots, non-TTY sudo skipped, background GUI install) |
| Leaf `update_*.sh` | `0` | Step completed cleanly (or dry-run preview) |
| Leaf `update_*.sh` | `10` | Soft/degraded failure (query failed, network unreachable, cosmetic; non-blocking) |
| Leaf `update_*.sh` | `1` | Hard failure (package/install operation broke mid-transaction; blocking) |

Only a **hard** failure (exit `1` / `127`) in steps 1–4 sets `BLOCKING_EXIT` and defers the
final macOS step. This prevents `softwareupdate -R` from restarting a Mac that may be
mid-transaction. Three deliberate exceptions:

- **Step 0 (prescan) never blocks.** It is a read-only scan and mutates nothing.
- **Step 5 (inventory/postupdate) never blocks (v1.5.5).** It is a reporting step; a failure still sets `OVERALL_EXIT=1` (non-zero exit, "completed with errors") but must not defer macOS security updates.
- **Soft results (exit `10`) never block.** A vendor updater that could not be verified,
  an offline feed, or a GUI automation that returned an ambiguous result surfaces as a
  warning and still allows macOS security updates to install. Suppressing security
  updates because an app updater could not be verified was the 2026-07-26 regression;
  see `docs/agents/critical_rules.md` §13.

`update_all.sh` itself exits `0` when the run was clean **or** merely degraded — a run
where self-updating apps report `LAUNCHED_UNVERIFIED` is the normal healthy outcome and
must not look like a failure to cron, CI, or `dev_sync`. Use `MAC_UPDATE_DEGRADED` or the
`degraded` field of `--json-summary` to detect warnings programmatically.

## Doctor, pre-flight and prompt timeouts (2026-11-09)

| Situation | Exit | Notes |
|-----------|------|-------|
| `update_all.sh --doctor`, all checks ok | `0` | Read-only: no sudo prompt, no run log, no summary |
| `--doctor`, warnings only | `10` | Low disk, battery, missing optional tool, plist without `PATH`, ... |
| `--doctor`, hard problem | `1` | For example unsupported platform or no network |
| Pre-flight: low free disk (`MAC_UPDATE_MIN_FREE_GB`) | run continues, degraded | Reported as a warning |
| Pre-flight: on battery below `MAC_UPDATE_MIN_BATTERY` | macOS step recorded as `skipped` (never started), run marked degraded, `update_all.sh` still exits `0` | Other steps run |
| Pre-flight: no reachable host (`MAC_UPDATE_PREFLIGHT_HOSTS`) | `1` before any step | Dry runs and inventory-only runs skip pre-flight |
| Prompt times out (`MAC_UPDATE_PROMPT_TIMEOUT`) | `10` where the step declines | Safe answer is "no"; the macOS step lands in its existing declined branch |
| Cask deferred because its app is open | `10` | Homebrew step; session file `brew_deferred_running.txt` |
| `feed_unreachable` | `10` | Internet step; `current_cached` and `current_feed_regressed` are informational |


## Stale vendor feeds (v1.5.4)

v1.5.4 changes report presentation only: a stale vendor feed remains degraded (`10` at the leaf, `0` plus `degraded=true` at the master). Manufacturer warnings are separate from pending installations and unconfirmed operations. A warning does not imply that an updater was launched.

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

Since v1.5.3, the system leaf honors `MAC_UPDATE_NO_SUDO=1`. With no terminal or in noninteractive mode and no cached authorization, it exits `10` before installation. Authorized installs use `sudo -n` so timestamp expiry fails explicitly instead of prompting. The orchestrator records a soft system deferral as degraded; a deliberate user cancellation remains `skipped_by_user`.

For unattended runs, use `--skip-system` (`bash update_all.sh --skip-system`) and apply macOS system updates interactively later. Existing cached authorization does not replace Apple Silicon volume-owner credentials.

## Typed per-target results

Summary format 4 adds `action_results` and per-item `action_status`. Manual and ignored outcomes are neutral; source conflicts, unavailable observations and unverified updates remain visible. A failed mutation is hard and can defer the final system step; a reporting conflict or declined action is soft. `current_verified` requires fresh observed identity, source and version; an installer exit code alone is insufficient.
