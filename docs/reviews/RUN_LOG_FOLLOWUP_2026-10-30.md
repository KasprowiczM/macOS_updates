# Run-log follow-up — 2026-10-29 / 2026-10-30 (macOS 27.2)

Author: Claude Opus 5.5 (orchestrator and verifier). Sonnet and Haiku subagents did read-only research: a macOS_cleanup port survey, macOS 27.2 compatibility checks, and a scan of historical logs.
Version: unreleased (stays 1.5.5 under the lockstep policy). The authoritative summary is in [`CHANGELOG.md`](../../CHANGELOG.md).

## Runs reviewed

| Run | Duration | Result | Notes |
|-----|----------|--------|-------|
| 2026-10-29 (27.0.1) | 70 min | exit 1, step 6 "Error" | macOS 27.2 was offered. The user declined the automatic restart. Node.js moved to `v27.0.0-alpha`. Step 4 took 31 min (VS Code / Antigravity IDE replacements deferred). |
| 2026-10-30 (27.2) | 3 min | clean | OpenCode was unverified (feed 404). The Proton Drive section was empty. No macOS update was pending. |

Evidence is paraphrased below. Raw logs and inventory content stay in `logs/` and are never quoted here.

## Findings and fixes

| ID | Severity | Finding | Fix | Verification |
|----|----------|---------|-----|--------------|
| R1 | high | `detect_latest_node_version` took the head of `nodejs.org/dist/index.json`, and `n latest` installed it. On 2026-10-29 the head was `v27.0.0-alpha.0.0.0`, so the managed Node moved from 26.12.1 to the alpha, and npm 12.2.1 now warns on every call. | `lib/python/node_releases.py:latest_stable_node` selects the newest stable `vX.Y.Z`. The shell fallback is restricted the same way. `n` installs that exact version. | `tests/test_node_releases.py` and the updated static test. A live lookup returns `v26.13.0`. |
| R2 | high | Declining the restart prompt printed "will not be installed" and then "installing with automatic restart". The step exited `1`, so the run was "completed with errors". | Restart-required labels are skipped and never run without `-R`. No-restart labels still install. The step writes `system_skipped_by_user` and exits `10`, with a localized message in 7 languages. | Two new tests in `tests/test_system_step.py`. |
| R3 | medium | OpenCode Desktop is now Electron (Squirrel, `app-update.yml`). The Tauri `latest.json` feed returns 404, so every run did a blind launch and reported "unverified". | The feed is `latest-mac.yml`. The parser prefers the arm64 zip. Relative URLs resolve against the feed URL. The sha512 is verified. | Feed lookup returns 1.19.5, an arm64 zip and `sha512b64`. Tests are in `tests/test_vendor_feeds.py`. |
| R4 | low | The equal, stale, unknown and dry-run branches of `internet_handler_vendor_truth` printed nothing, so Proton Drive showed only its header. | Each branch prints its status. | `test_vendor_truth_terminal_branches_print_their_status`. |
| R5 | low | The docs said the Xcode gate uses `-checkFirstLaunchStatus`. The code uses `-license check`, which is correct: the first-launch status returns 69 on a licensed Xcode 27.2. | Docs corrected. | — |

## Live verification (2026-10-30, after the fixes)

- `update_npm_cli.sh` moved the managed Node from `v27.0.0-alpha.0.0.0` to `v26.13.0` (stable, LTS), and npm 12.2.1 no longer warns.
- Every managed CLI equals its registry's stable `latest` tag: Claude Code 2.1.314, Codex 0.166.0, OpenCode 1.19.5, pnpm 12.16.1, npm 12.2.1, n 11.0.0. Bun 1.4.4 equals GitHub `releases/latest`. None of them is on an alpha, next or beta tag.
- In `scripts/check_vendor_feeds.sh` all 11 vendor-feed apps are `equal`; OpenCode was `unknown` before. The four Omaha apps report `noupdate`.
- Update channels:
  - Sparkle parsing accepts only `stable` or channel-less items.
  - Warp, Cursor and Antigravity IDE feeds use their `stable` channel.
  - Office MAU has no `ChannelName` set, so it uses the default Current channel.
  - No beta, nightly or preview casks and no HEAD formulae are installed.
- Firefox Developer Edition is a beta product by design, and the user chose to install it.
- `update_all.sh --dry-run -y --json-summary` exits 0.

## macOS_cleanup port

| Pattern (cleanup commit) | Status here |
|---|---|
| No test may reach a real native tool (240f0b8) | **Ported.** `run_tests.sh` puts a guard directory of failing host-tool stubs behind each test's own mocks and fails the gate if any stub is reached. The guard found three tests querying the real Homebrew/mas; they now use `tests/_env.py:isolate_host_tools`. |
| stdin closed per test (6b61e8f) | **Ported** (`</dev/null` on the unittest step). Pinning tests to `/bin/bash` 3.2 is not done yet. |
| Installer SHA256SUMS (ad14710) | Not ported. A checksum file inside the same repo only detects a corrupt checkout. Pinning a tag is the stronger control and is left as a decision for the owner. |
| Behavioural keep-alive orphan test (73dd097) | Not ported (follow-up). |

## macOS 27.2 compatibility (evidence, 2026-10-30)

Verified on this Mac:
- Homebrew 7.0.11 with CLT 27.2 (no CLT doctor warning).
- mas 7.0.0. `mas upgrade` still needs root (context7 `/mas-cli/mas`).
- The `softwareupdate` flags `-l`, `-i`, `-R`, `--verbose` and `--install-rosetta` are present.
- Gatekeeper is enabled. Rosetta is not installed.
- All `lib/python` modules import under `/usr/bin/python3` 3.9.6, and the suite passes there. That is the fallback used when Homebrew's `python3` link disappears.

Not exercised: `softwareupdate -l` text on a 27.2 offer, the App Store Track 2 GUI, a live vendor-direct OpenCode install, and the restart decline on real hardware. Acceptance paths 2 and 3 remain open.
