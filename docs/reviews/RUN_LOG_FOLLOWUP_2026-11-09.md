# Review follow-up — 2026-11-09

Author: Claude (orchestrator with implementation subagents). Version: unreleased (stays 1.5.5 under the lockstep policy). The authoritative summary is in [`CHANGELOG.md`](../../CHANGELOG.md).

Evidence is paraphrased. Raw logs, inventory content and machine paths stay local and are never quoted here.

## Scope

A review of the scheduled (launchd) path and the interactive path, prompted by recent run logs: a scheduled run that found no Homebrew, a Homebrew prompt that waited about 51 minutes, a Google Drive check that never had fresh proof, a Proton Mail feed that moved backwards, an inflated chronic-warning streak and inventory counts that read zero.

## Findings and fixes

| ID | Severity | Finding and root cause | Fix |
|----|----------|------------------------|-----|
| P1 | high | Scheduled runs reported "Homebrew is not installed". launchd starts jobs with a minimal `PATH`; the plist set none. | `mac_update_ensure_homebrew_path` in `lib/platform.sh` (runs when sourced) and an explicit `EnvironmentVariables.PATH` in the generated plist. `install_launchagent.sh --check` warns about old plists. |
| P2 | high | The LaunchAgent installer could print success although the service was not loaded; cleanup used `unload -w`, which persists a disabled state. | `launchctl print` verification; failure prints the launchctl error and exits non-zero; re-install cleanup uses `bootout`. |
| P3 | high | A mid-run prompt had no lifetime (about 51 minutes waiting on 2026-11-04) and anything not starting with N counted as yes. | `mac_update_prompt_yn` with `MAC_UPDATE_PROMPT_TIMEOUT`; timeout and unrecognised input mean "no"; children skip their own question after `MAC_UPDATE_PARENT_CONFIRMED=1`, except the macOS step. |
| P4 | high | `brew upgrade --cask` could replace an app that was open. | Cask with an open or unknown-state app is deferred (`brew_deferred_running.txt`), step ends soft. |
| P5 | medium | Google Drive is registered only with the system-scope GoogleUpdater; the run's wake reached only the user scope, so the newest proof was always older than the 6 h window. | Also `--wake-all --system`; refused proofs are logged with a reason. Window and "different build is not proof" unchanged. |
| P6 | medium | Feed failures left no trace and a failed fetch forced a blind updater launch. The Proton Mail feed dropped from 1.16.1 to 1.16.0 and was reported stale. | Fetch diagnostics, distinct fetch/parse failures, persistent feed state with cached proof (`current_cached`), high-water mark (`current_feed_regressed`) and `feed_unreachable`. |
| P7 | medium | Chronic-warning streak counted `skipped` steps and dry runs (reported 10, real 4). | `skipped` is neutral; dry-run and inventory-only runs excluded. |
| P8 | low | `build_inventory.sh` printed zero changes: the counts file was written after an early exit in inventory-only mode. | Counts written before the exit; own banner; added/removed entries reported. |
| P9 | low | History labelled feed-driven apps with their config method, Firefox and IPMIView inaccurately; doubled status emoji. | `internet_effective_method`, `mozilla_dmg` label, IPMIView as App Store iPad app, text fixes. |
| P10 | low | `brew doctor` warnings were mixed with a "good condition" line and could suggest running a sudo fix script. | Advisories (`advisories.txt`), security advisories flagged, fix script never run. |

## Added

`update_all.sh --doctor` (read-only readiness report, exit 0/10/1), cheap pre-flight (disk, battery, network) with `caffeinate`, sudo keep-alive limit, additive run-summary fields (`advisories`, per-step `duration_seconds`, inventory counts), log rotation for `run_summary_*.json`, and a follow-up hardening making every curl fetch https-only.

## Independent review round

1. Localized yes letters (`j`, `s`, `o`, plus `y`, `t`) are accepted by `mac_update_prompt_yn`; `n` is no, anything else no.
2. Casks without an `app` artifact are deferred when a declared `uninstall` quit/signal bundle ID is running or unknown, or the cask JSON is unreadable; none declared means upgrade.
3. Deferred casks count in `pending_brew_casks` and appear as pending `brew_cask` run-summary items (no duplicate "still outdated" report, still soft).
4. The sudo keep-alive stops when the parent shell is gone; `MAC_UPDATE_SUDO_KEEPALIVE_MAX` now defaults to 14400.
5. The network pre-flight retries the whole probe pass (`MAC_UPDATE_PREFLIGHT_NET_RETRIES`, `MAC_UPDATE_PREFLIGHT_NET_RETRY_WAIT`) before aborting; `--doctor` stays single-pass.
6. `--doctor` "last run" ignores dry-run and inventory-only summaries and says so when no real run exists.
7. A timed-out macOS prompt prints "no answer within N s", writes `system_prompt_timeout` and the banner reads "skipped: no answer" (exit `10`, status codes unchanged).
8. `docs/agents/exit_codes.md` battery row corrected: the system step is `skipped`, the run degraded, the master exits `0`.
9. `install_launchagent.sh --uninstall` no longer falls back to `launchctl unload -w`.
10. The run-log filter keeps passing output to the terminal when the log cannot be opened.

## DeepSeek Harness, Grok Bot, DJI Assistant 2

- **DeepSeek Harness** (`com.deepseek.dsh`, 0.2.2-rc.1): `app-update.yml` is a generic electron-updater provider on channel `nightly`. `nightly-mac.yml` returned HTTP 200 with version `0.2.2-rc.1` (folded `>-` url/checksum); `latest-mac.yml` and `nightly.yml` return an HTML page with 404. Registered verify-only; today's status is "Up to date (0.2.2-rc.1, vendor feed)". Limit: the feed URL is fixed to the nightly channel; an unknown pre-release label such as `nightly` ranks as a final release in `version_key`.
- **Grok Bot** (`com.anysphere.sand`, 0.79.3): no `app-update.yml`, but the bundle's own code builds `https://api2.cursor.sh/updates` with product `sand` for the stable channel. `.../darwin-arm64/sand/0.0.0/stable` returned HTTP 200 `{"url":...,"name":"0.79.3"}` (the same call with the installed version returns 204). Registered verify-only with the existing `cursor_update` selector; today's status is "Up to date (0.79.3, vendor feed)". Assumes the app tracks the stable channel.
- Neither app uses the `brew_cask` method (not adopted, rule 5a); the casks were not consulted as oracle because a real vendor feed exists.
- **Inventory:** the prescan puts a newly installed app that is missing from `APPLICATIONS.md` into the "🆕 do skategoryzowania" table; nothing moves it to GROUP 3 afterwards (`config/internet_apps.txt` only feeds the legend and the update-method summary), so the owner moves the rows by hand once.
- **DJI Assistant 2** removed from the product. Its handler was the only test of the Intel-only path; the generic helpers now carry it and the tests use a fake x86_64 bundle.
- Not verified live: no real update run, no launch of either app.

## Not verified live

- No real scheduled launchd run was observed; the plist `PATH`, the load check and the bootout flow are covered by tests with stubbed `launchctl`.
- The system-scope Google updater wake was not observed on a real Google Drive install.
- No live full `update_all.sh` run on the merged branch.
- The interactive prompt timeout and the real `caffeinate` process were not exercised live.
- Acceptance paths 2 (system update with restart batch) and 3 (major upgrade guard) remain open.
