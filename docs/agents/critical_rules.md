# Critical Rules — Do NOT Violate

## 1. softwareupdate MUST use `-R`
```bash
sudo softwareupdate -ia -R --verbose   # CORRECT — writes boot metadata
# Without -R: update downloads but NEVER applies after reboot
```
`-R` only restarts or shuts down when required, so it is safe to keep on every install path. If the user declines a restart-required update, do not install it without `-R`; exit non-zero with manual instructions.

## 2. mas MUST use `sudo` (CVE-2025-43411)
```bash
export MAS_NO_AUTO_INDEX=1   # suppress Spotlight warnings
sudo env MAS_NO_AUTO_INDEX=1 mas upgrade
```

## 3. App Store — Two tracks
- **Track 1:** `sudo mas upgrade` — native macOS apps
- **Track 2:** AppleScript GUI (`osascript`) — iPad apps (UniFi, WiFiman, myCANAL, Picsart)
  - Requires Accessibility permission in System Settings
  - This is a separate track, not a fallback for Track 1; unexpected GUI states fail honestly
  - `mas outdated` cannot prove the state of iPad apps, so Track 2 keeps its own result

## 4. Version detection
```bash
defaults read "/Applications/App.app/Contents/Info" CFBundleShortVersionString
```
- **Firefox Dev Edition:** `application.ini` → `grep "^Version=" | cut -d= -f2` gives the **base** version (no beta suffix). Compare with `sort -V` against Mozilla product-details and never downgrade (local may legitimately be ahead of the published beta).
- **GitHub tags:** strip the leading `v` with `sed 's/^v//'` (never `tr -d 'v'`, which deletes every `v`) before comparing with `app_version()`.
- **iOS/iPadOS apps on Apple Silicon** (UniFi, WiFiman, …): no `Contents/Info` plist — `app_version()` falls back to `mdls -name kMDItemVersion`.

## 5. Internet app update methods

| Method | Apps |
|--------|------|
| Sparkle appcast + DMG | ChatGPT Atlas |
| Mozilla product-details/download + DMG | Firefox Dev |
| GitHub API / Official Metadata + DMG | KeePassXC, CodeEdit, Trezor Suite, Ledger Wallet / Live |
| Google Keystone | Chrome, Google Drive |
| msupdate CLI | Word, Excel, PowerPoint, Outlook, OneNote; observed `TEAMS21` fallback when MAU offers it |
| Vendor self-updater + MAU fallback | Microsoft Teams normally owns its cadence; MAU may recover a failed Teams updater |
| Docker CLI | Docker Desktop v4.37+ |
| Native/npm/self-updating CLI | Node.js, npm, pnpm, bun, Claude Code CLI, Codex CLI, OpenCode CLI, Agy CLI |
| Homebrew cask --greedy | Inkscape |
| Built-in auto-updater (silent launch) | Brave, ChatGPT/Codex desktop, Claude, Comet, Perplexity, Antigravity, Antigravity IDE, LM Studio, OpenCode, ProtonVPN, Proton Mail, Proton Drive, MEGAsync, Zoom, Warp, AppCleaner, Spotify, CapCut, Remote Desktop Manager, Cursor, Obsidian, Ascendo |
| Hybrid self-update + MAU fallback | Teams (`TEAMS21` is accepted only when surfaced by MAU and is verified by a final `msupdate --list`) |
| App Store GUI Track 2 | UniFi, WiFiman, Picsart |
| Manual only | IPMIView, DJI Assistant 2 |

These methods are not equivalent proof levels:

- **verified direct** — the script verifies a version/package path or a vendor CLI reports completion.
- **triggered-unverified** — the app was launched to trigger its built-in updater; completion is not asserted.
- **externally managed** — the App Store or vendor owns the update lifecycle outside a directly verifiable handler.
- **manual** — the registry intentionally requires user action.
- **unknown** — no supported registry method matches the installed app.

## 6. Downloaded installers
- Use random temp paths under `$MAC_UPDATE_SESSION_DIR` or `mktemp`.
- Run `hdiutil verify` before mounting downloaded DMGs.
- Mount each DMG at a unique mountpoint inside `$MAC_UPDATE_SESSION_DIR`; never discover an installer by scanning shared `/Volumes` names.
- Copy `.app` bundles with `ditto` (preserves code signature, xattrs, resource forks — `cp -R` does not). Quit the running app first, verify the incoming bundle's identifier and signing team against the installed target, run `spctl --assess --type execute`, stage the replacement, then swap it in with a retained backup. If the copy or post-swap validation fails, restore the original app before returning non-zero.
- Verify `.pkg` installers with `pkgutil --check-signature` before `sudo installer`.
- Do not report success after a failed copy/install; return a non-zero exit so `update_all.sh` records a failed step.
- **Honest status:** a GUI app that is only launched reports `LAUNCHED_UNVERIFIED` (⏳), not success; a failed launch reports `LAUNCH_FAILED` (⚠️) and fails the step. Only a confirmed version change reports `UPDATED`/`CURRENT`.

## 7. Private state and imports

- Write `APPLICATIONS.md`, `UPDATES.md`, provider config and logs through a same-directory temporary file, flush/fsync where implemented, then `os.replace()`.
- Private config is mode `0600`; log/config directories are private to the user.
- Cloud imports stage only allowlisted, safe relative paths. Commit the staged set transactionally and roll back already replaced targets if any later file fails.
- Rclone listing/copy failures are fatal; never turn an incomplete remote listing into a successful empty import.

## 8. APPLICATIONS.md structure
- GRUPA 1: Apple system apps
- GRUPA 2: App Store (mas IDs)
- GRUPA 3: Internet apps
- GRUPA 4: Tooling (4a key ⭐, 4b deps, 4c casks, 4d native CLI + npm)

## 9. Microsoft AutoUpdate version regressions

- Treat `Installer succeeded with no version change`, PackageKit `Skipping component`, or delta `postinstall` code 112 as a package-version investigation, not proof that MAU itself is broken.
- Compare both `CFBundleShortVersionString` and `CFBundleVersion` for the installed Office app and offered package. PackageKit can reject a package with a newer build number when its short version is lower.
- Never bypass that protection by editing a signed Office bundle, deleting it, or forcing a lower short-version component into place.
- If Microsoft has published a malformed `Recommended` Preview update, use its documented per-app `OptionalUpdatesDeferrals` mechanism as a temporary quarantine. Preserve existing nested deferrals; critical updates must remain eligible.
- Deferral-day preferences persist across releases. Remove only the incident-specific app IDs after Microsoft corrects the feed, then require a clean `msupdate --list`.
- The evidence and reversible commands for the 2026-07-14 Preview incident are in `docs/agents/troubleshooting.md`.
