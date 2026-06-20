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
| Sparkle appcast + DMG | ChatGPT, Atlas |
| Mozilla product-details/download + DMG | Firefox Dev |
| GitHub API / Official Metadata + DMG | KeePassXC, CodeEdit, Trezor Suite, Ledger Wallet / Live |
| Google Keystone | Chrome, Google Drive |
| msupdate CLI | Word, Excel, PowerPoint, Outlook, OneNote, Teams |
| Docker CLI | Docker Desktop v4.37+ |
| Native/npm/self-updating CLI | Node.js, npm, pnpm, bun, Claude Code CLI, Codex CLI, OpenCode CLI, Agy CLI |
| Homebrew cask --greedy | Inkscape |
| Built-in auto-updater (silent launch) | Brave, ChatGPT, Claude, Comet, Perplexity, Antigravity, Antigravity IDE, LM Studio, Codex, OpenCode, ProtonVPN, Proton Mail, Proton Drive, MEGAsync, Zoom, Warp, AppCleaner, Spotify, CapCut, Remote Desktop Manager, Cursor, Obsidian, Ascendo |
| Manual only | IPMIView, DJI Assistant 2, Picsart, UniFi (iPad), WiFiman (iPad) |

## 6. Downloaded installers
- Use random temp paths under `$MAC_UPDATE_SESSION_DIR` or `mktemp`.
- Run `hdiutil verify` before mounting downloaded DMGs.
- Copy `.app` bundles with `ditto` (preserves code signature, xattrs, resource forks — `cp -R` does not). Quit the running app first, then `spctl --assess --type execute` **before** copy (reject unsigned downloads) and again **after** the swap (log post-install failures).
- Verify `.pkg` installers with `pkgutil --check-signature` before `sudo installer`.
- Do not report success after a failed copy/install; return a non-zero exit so `update_all.sh` records a failed step.
- **Honest status:** a GUI app that is only launched reports `LAUNCHED_UNVERIFIED` (⏳), not success; a failed launch reports `LAUNCH_FAILED` (⚠️) and fails the step. Only a confirmed version change reports `UPDATED`/`CURRENT`.

## 7. APPLICATIONS.md structure
- GRUPA 1: Apple system apps
- GRUPA 2: App Store (mas IDs)
- GRUPA 3: Internet apps
- GRUPA 4: Tooling (4a key ⭐, 4b deps, 4c casks, 4d native CLI + npm)
