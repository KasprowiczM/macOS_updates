# Run-log follow-up — 2026-11-10 (Open Design, HyperFrames, Superset)

Author: Claude Opus 5.5 (implementation subagent). Version: unreleased (stays 1.5.5 under the lockstep policy). The authoritative summary is in [`CHANGELOG.md`](../../CHANGELOG.md).

Evidence is paraphrased. Raw logs, inventory content and machine paths stay local and are never quoted here.

## Scope

In the 2026-11-10 interactive run three apps registered as "vendor feed decides, the app's own updater installs" were behind and were launched hidden by the toolkit:

- **Open Design** (feed 0.27.1, active launcher payload 0.27.0): still behind after the run. The owner saw the app start and close by itself.
- **HyperFrames** (feed b891, build label b879): launched, sat idle, still behind. A manual launch afterwards did not update it either.
- **Superset** (feed 2.0.8; upstream project renamed "paradev"): reported "updated to 2.0.8", but the owner saw nothing happen after the launch.

## Findings

| ID | Severity | Finding | Fix |
|----|----------|---------|-----|
| R1 | high | A hidden launch does not reliably make these apps update; the status depended on whether their updater happened to act in the 90 s window. | HyperFrames and Superset install direct-only from their verified arm64 zip; Open Design is verify-only and never launched (`config/vendor_launch_policy.txt`). |
| R2 | medium | Apps that must not be launched still had two hidden launch paths: the native-updater fallback after a failed direct download and the fallback after an unreachable feed. | Both are skipped for `direct-only` / `never-launch` apps; the unreachable-feed case has its own status ("version not checked (app not launched)", code `feed_unreachable`). |
| R3 | medium | Nothing guaranteed a minimum time between a toolkit launch and its quit: an app launched shortly before the end-of-step settle could be asked to quit a few seconds after launch. | `toolkit_launched_at.txt` + `MAC_UPDATE_QUIT_MIN_AGE` (default 30 s) before the first graceful `quit`; never a force-kill, user-opened apps untouched as before. |
| R4 | low | The "updated to 2.0.8" claim for Superset needed checking. | It was real: the handler reports `updated` only when `app_version` of the installed bundle reaches the feed version, and the run's before/after snapshots show 2.0.7 → 2.0.8. Most likely the electron updater installed on the toolkit's quit (the handler polls 10 s after the quit). No change needed. |

## Artifact verification (read-only, nothing installed)

Both feed artifacts were downloaded to a scratch directory and inspected:

- **HyperFrames** `latest.json` → `arm64.url` (zip, `static.heygen.ai`) and `arm64.sha256`: the download matched the sha256. The bundle is `dev.hyperframes.desktop`, `HFBuildLabel` b891, arm64 only, `codesign --verify --deep --strict` passes, `spctl` reports a notarized Developer ID, and its Team ID equals the installed bundle's.
- **Superset** `latest-mac.yml` → `Superset-2.0.8-arm64-mac.zip` (relative URL resolved against the GitHub `releases/latest/download/` feed URL) and base64 sha512: the download matched. Bundle `com.superset.desktop`, 2.0.8, arm64, notarized, same Team ID as the installed one.
- The feed's top-level HyperFrames `url` is a universal archive and `x64` is Intel; the selector takes only `arm64` and stays verify-only without a well-formed https zip and 64-hex sha256.
- HyperFrames' bundle version is always 0.1.0; `vendor_direct_install`'s pre-copy check and the post-install verification both use `app_version` (which reads `HFBuildLabel` through `lib/python/inventory.py:vendor_installed_version`), and build labels compare numerically (b879 < b891 < b1000).

## Open Design launcher (code reading of the shipped launcher, no state written)

- The `/Applications` bundle (0.21.1, never updated by the vendor updater) is a launcher. It reads `runtime.json` (`active`, `lastSuccessful`) in its channel/namespace directory, writes `state/attempt.json` when it hands off to the active payload, and spawns the versioned payload with "wait for my exit" arguments, then exits.
- The payload clears `attempt.json` and rewrites `runtime.json` (`active = lastSuccessful`) only when its desktop window reports ready.
- If an `attempt.json` for the active generation is still present on the next start, the launcher selects `lastSuccessful`; here both pointers are the same generation and version, so it starts the same payload. The stale file is therefore harmless and does not explain an exit. An updated payload is activated by writing a new generation to `runtime.json` plus a fresh `attempt.json`, so the next update replaces the leftover.
- The updater runs inside the running app: about 5 s after the window is ready it checks the channel metadata, downloads the payload zip (about 440 MB) and installs it only when the user confirms the restart, or silently at the next start if the app's "silent updates" setting is on. A hidden launch that is quit after a fixed wait cannot complete that.
- Its own desktop log shows, for the toolkit launch and two later LaunchServices launches, the payload starting and exiting with code 0 about 0.5-0.8 s later, without the shutdown sequence. The only silent exit-0 point after that log line is the Electron single-instance lock (`requestSingleInstanceLock` fails → `app.quit()`). Why the lock is refused for LaunchServices-started chains but not for a launcher started directly from a shell (which came up normally the same morning, with the stale `attempt.json` untouched) could not be established from the code alone. The same pattern occurred on 2026-11-06, where two quick exits preceded a successful start.
- Timing: the toolkit's quit phase for Open Design came about 110 s after its launch, when no Open Design process was running, so the quit was not sent and did not cause the exit.

Decision: no safe, verifiable automated path exists, so Open Design is `never-launch`: a behind version is reported as "open the app to update" (soft `behind`), the toolkit never launches or quits it, and never writes the vendor's launcher state. No repair was made on the machine (the stale `attempt.json` was shown not to be the cause).

## Rename note

The Superset feed lives in the renamed `paradevai/paradev` repository and its DMG is named "Paradev", but the bundle still reports `CFBundleName` / `CFBundleDisplayName` "Superset" and id `com.superset.desktop`, so user-facing names were left unchanged; only comments and agent docs mention the upstream name.

## Not verified live

No `update_all.sh` run. No real direct install of HyperFrames or Superset (only the artifact inspection above and tests with fake bundles). Open Design's exit cause on LaunchServices launches is not established.

Observed in passing (not changed here): the step headers in that run log print durations that do not fit their steps (the internet step header said about one minute, the inventory step about seven), which looks like an off-by-one in the per-step duration labels.

## Live verification after the fixes (2026-11-10)

A one-shot LaunchAgent (`scripts/install_launchagent.sh --once-in 2`) was installed, verified as loaded, and fired at the scheduled minute. The launchd-started run was non-interactive with `--skip-system` and finished with exit 0 (degraded).

Observed:

- Homebrew and `mas` were found under launchd; no "Homebrew is not installed"; no sudo prompt; pre-flight and `caffeinate` ran.
- HyperFrames was installed direct-only from the vendor zip (checksum, bundle ID, Team ID, Gatekeeper) with no launch; the installed bundle passes `codesign --verify --deep --strict` and is a notarized Developer ID app.
- Superset was reported current from the vendor feed without a launch.
- Open Design was not launched; it was reported as "open the app to update".
- A GitHub API rate limit was reported as a rate limit with its reset time, not as a connection failure.
- The LaunchAgent was removed afterwards with `--uninstall`; the service and the plist are gone.

Still open:

- Why Open Design's packaged app exits right after start when launched through LaunchServices on this machine while a direct start of its executable works. This is the vendor app's behaviour, not caused by the toolkit; the toolkit no longer launches it.
- Two text nits seen in that run: a never-launch app still prints the generic "updates automatically" line, and one run-summary detail ("behind vendor version") is not localized.
- A prompt timeout, an open-cask deferral, and acceptance paths 2 and 3.
