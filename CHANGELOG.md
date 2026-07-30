# Changelog

All notable changes to **macOS Updates** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
semantic-ish versioning tracked in [`VERSION`](VERSION).

---

## [1.0.21] — 2026-07-30

Hardening release. No new user-facing features; the focus was correctness of the
**step-severity contract**, integrity of downloaded payloads, and closing gaps between
what the documentation promised and what the code did.

The headline fix: several ordinary, non-mutating conditions were being reported as hard
failures, which silently deferred `softwareupdate -ia -R` — the macOS security update.
On a typical developer Mac this could suppress security updates indefinitely.

### Fixed — release blockers

- **macOS security updates are no longer deferred by non-failures.** The soft-exit code
  (`10`) contract described in `docs/agents/critical_rules.md` §10 was only implemented by
  `update_internet_apps.sh`; `update_appstore.sh`, `update_brew.sh` and `update_npm_cli.sh`
  had no soft path, so every unverifiable condition became a blocking hard failure. All four
  leaf orchestrators now share `lib/severity.sh` and classify correctly.
- **`brew doctor` warnings and `--greedy` cask residue no longer fail the run.** `brew doctor`
  is advisory, and casks with `auto_updates true` / `version :latest` can never stop being
  listed by `brew outdated --greedy`. Both previously produced a permanent hard failure.
- **`update_all.sh` no longer hangs on exit.** A `wait` on the `tee` process ran while the
  shell's descriptors were still attached to it, deadlocking the EXIT trap. Descriptors are
  now saved and restored before the wait, so failure diagnostics still reach the run log.
- **App Store Track 2 restored.** The AppleScript payload is written to a file instead of
  being piped as a heredoc through `run_with_timeout`, which silently lost the script on
  stock macOS and stopped iPad-app updates (UniFi, WiFiman, Picsart).
- **Shell profile edits are non-destructive.** `~/.zshrc` and `~/.npmrc` were replaced via
  `mv`, destroying symlinks into dotfiles repositories and resetting file modes. Edits now
  resolve symlinks, write in place, and take a timestamped backup.
- **`update_npm_cli.sh` reports mid-transaction failures as hard.** Node and Bun toolchain
  installs move the live toolchain aside before swapping; those failures are no longer
  silently discarded.

### Fixed — integrity and correctness

- Ledger Live downloads are verified against the publisher `sha512` from `latest-mac.yml`.
- Visual Studio Code uses the official update API for version, URL **and** `sha256hash`,
  and extracts with `ditto` instead of `unzip` (which does not preserve code signatures).
- Every `curl` download in `lib/internet_app_updates.sh` uses `--fail`, so HTTP errors are
  no longer written into `.dmg`/`.zip` files and misreported as mount failures.
- ChatGPT Atlas is registered as `silent_launch` to match its handler, so the coverage
  report no longer overstates its proof level; it also no longer claims the ChatGPT/Codex
  bundle.
- The Microsoft AutoUpdate quarantine no longer oscillates for products hidden by their own
  active deferral, which caused repeated multi-hundred-megabyte re-downloads.
- `softwareupdate -l` is parsed under `LANG=C LC_ALL=C`, and the Accessibility probe matches
  AppleScript error `-1743` instead of localised English text.
- `strip_ansi` uses ANSI-C quoting so it works under BSD `sed`.

### Added

- `lib/severity.sh` — shared soft/hard exit-code helpers.
- `lib/proc.sh` — single `run_with_timeout` implementation (was duplicated three times).
- Secret redaction in the `dev_sync` Python error paths and logger.
- `sudo` pre-authentication before the tee redirect, so long unattended runs do not stall
  on a password prompt at step 6.
- Inline heredoc Python is now extracted and `py_compile`d by `run_tests.sh` and CI.
- Behavioural test scenarios that execute the real leaf orchestrators against a mocked
  `PATH` and a sandboxed `HOME`.

### Changed

- Console output for steps 0, 2 and 5 is fully localised; all seven language files carry
  identical key sets (653 keys each).
- 19 silent-launch handlers migrated to the shared `internet_dispatch_silent_launch`.
- Bun resolves its latest release tag at runtime; `config/bun_version.txt` is now a
  documented minimum floor rather than a hard pin.
- `mas` gate raised to ≥ 4.1. The `sudo` requirement is now attributed to the macOS
  `installd` entitlement change rather than to an unrelated CVE.

### Security

- `.claude/settings.local.json` and two `.DS_Store` files were tracked despite `.gitignore`;
  they are untracked, and the Claude `deny` rules now ship in the tracked settings file.
- `scripts/scan_secrets.sh` and the CI workflow now fail on **any** tracked-but-gitignored
  file, not just four hardcoded names.

### Known limitations

- ~1,100 lines of Python remain embedded in `update_all.sh` heredocs. They are syntax- and
  lint-checked by CI, but not unit-tested; extracting the pure functions into `lib/python/`
  is the next planned change.
- `internet_version_relation` still spawns a Python interpreter per comparison. This is an
  accepted trade-off — an `awk` port risked altering the version-ordering semantics that the
  Microsoft AutoUpdate regression guard depends on.
- `setup.sh` and `migration_setup.sh` retain local `print_*` definitions because their
  output padding differs from `lib/ui.sh`.

---

## [1.0.20] and earlier

See `git log` and the review documents in the repository root for the history preceding this
release.

[1.0.21]: https://github.com/KasprowiczM/macOS_updates/releases/tag/v1.0.21
