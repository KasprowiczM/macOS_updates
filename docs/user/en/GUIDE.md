# User Guide (English)

**Version:** 1.8.2 · **Apple Silicon, macOS 13+**

## Terminal workspace

In an interactive terminal, `bash update_all.sh` opens the workspace and shows the first-use wizard until it is finished. `bash setup.sh` opens the wizard and `bash build_inventory.sh` opens inventory. You can reopen the wizard from its navigation item. Completion and display settings persist; they grant no update permission. Use `--cli` for the existing text interface or `--tui` to request the workspace explicitly. Explicit flags such as `--dry-run` stay in the CLI; do not combine `--tui` with other options. An explicit `--tui` requires a usable terminal and Python. Noninteractive and non-TTY invocations keep CLI behavior.

Choose update groups before a run. Navigation is on the left, actions and live output in the center, and contextual details in the right sidebar on every screen. Only one supervised job runs at a time; each update retains its existing consent checks. Settings include language, theme, ASCII and automatic resizing. Press `?` for help, Ctrl+P for the action palette, and `c` to copy the focused command, output or summary. Ctrl+V pastes only into the answer dialog; Enter submits. Input is masked when the child disables echo.

The interface needs at least 80 columns by 24 rows. By default it requests at least 140 columns by 38 rows on supported terminals and requests the original size on exit; the terminal may ignore either request. Automatic resizing can be disabled in settings.

## Safe setup and application sources

`bash setup.sh --inspect` checks readiness without installing dependencies, changing shell profiles or configuring Touch ID. Missing tools leave the affected feature unavailable. In a terminal, `bash setup.sh --install-dependencies` previews optional dependencies and asks before each installation; `bash setup.sh --configure-shell` separately previews a shell profile change. Declining a dependency leaves independent features usable. If Python is unavailable, install it explicitly before building inventory. Missing or outdated `mas` is reported during updates and is never installed or upgraded automatically.

The optional catalog starts unselected. A separately approved Homebrew installation is available for KeePassXC when fresh source and absence checks pass. Its preview lists the manager command and declared effects; verification is a Homebrew receipt, not vendor recipe acceptance. Other entries retain their reviewed official acquisition paths. Existing apps are never migrated automatically. Source comparison recommends only what current stable-release evidence supports.

If a catalog installation has an uncertain result, reopen the catalog to run a fresh recovery check. Do not delete locks or journals manually. KeePassXC delegation requires reviewed stable evidence within its seven-day validity period; otherwise it falls back to the manual path.

## What this toolkit does

macOS Updates orchestrates updates in seven steps on **Apple Silicon Macs running macOS 13+**. The full pipeline runs in this order:

1. Prescan and per-Mac inventory
2. App Store (`sudo mas upgrade <app-id>` plus a separate GUI Track 2 for iPad apps)
3. Existing native CLIs first, then Node/Bun and npm fallbacks
4. Homebrew formulae and casks (greedy upgrade only for casks registered as `brew_cask`)
5. Installed internet apps through consented scoped manager operations; unaccepted vendor updates remain manual
6. Atomic inventory/history postupdate
7. macOS (`softwareupdate -i <label> -R`) last; deferred after a blocking hard failure or unavailable authorization

Each Mac builds its own inventory first (`build_inventory.sh` or prescan in `update_all.sh`). The public recipes do not automatically install or update vendor apps.

## Languages

Seven UI languages: EN, PL, DE, FR, ES, IT, PT. Set during `setup.sh` / `install.sh`; stored in `.mac_update_prefs`.

## Public vs private data

| Source | Contents |
|--------|----------|
| **GitHub** | Scripts, `config/`, tests, docs |
| **Cloud overlay** | `APPLICATIONS.md`, `UPDATES.md`, `.env`, `.dev_sync_config.json` |

## Coverage report

After install or when adding apps:

```bash
bash scripts/report_update_coverage.sh
```

Shows five evidence-based states:

- **verified direct** — a package/version path or vendor CLI result was confirmed
- **triggered-unverified** — the app launched its built-in updater, but completion is not asserted
- **externally managed** — App Store or vendor lifecycle owns the update
- **manual** — user action is intentionally required
- **unknown** — the installed app has no registered method

### Current recipe status

The optional catalog starts unselected. A separately approved Homebrew installation is available for KeePassXC when fresh source and absence checks pass. Its preview lists the manager command and declared effects; verification is a Homebrew receipt, not vendor recipe acceptance. Other entries retain their reviewed official acquisition paths. Existing apps are never migrated automatically. Source comparison recommends only what current stable-release evidence supports.

## Adding an internet app

1. Install the app on your Mac.
2. `bash build_inventory.sh --cli`
3. `bash scripts/scaffold_internet_app.sh "/path/to/Observed.app" --json`
4. Review the non-executable JSON proposal; any later implementation needs review and `bash run_tests.sh`.

Replace the example with the exact installed application path. The command previews a redacted, non-executable review proposal. Optional export requires repeating it with `--export --accept PREVIEW_ID` after reviewing the displayed preview ID. Enabling updates requires a reviewed implementation and separate acceptance evidence.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Intel Mac / macOS 12 or older | Not supported — Apple Silicon and macOS 13+ only |
| Wrong app catalog | `bash build_inventory.sh --cli` — do not use another user's `APPLICATIONS.md` |
| App not updating | `bash scripts/report_update_coverage.sh` |
| `mas` fails | Sign in to App Store; use `sudo mas upgrade <app-id>` |
| iPad apps not updating | Grant Accessibility to Terminal |
| Missing `APPLICATIONS.md` | `bash build_inventory.sh --cli` or `dev_sync/dev-sync-import.sh` (owner) |

Full troubleshooting: [../../agents/troubleshooting.md](../../agents/troubleshooting.md)

Stage C activates local JSON inventory and scoped update plans. `bash update_all.sh --plan` and `--dry-run` show the same read-only decisions. A normal interactive run asks once for the displayed scopes; `-y`, EOF and unattended runs grant no new permission. Use `--preferences` to review or reset choices. Updates keep the observed source and exact destination; conflicts, missing targets and uncertain evidence defer that target. `build_inventory.sh --migration --preview` preserves old Markdown bytes and notes; accept the displayed proposal ID explicitly. Generic vendor updates remain manual until a reviewed identity and adapter are available. An old catalog entry is neither proof of installation nor consent.


## Optional catalog and first installation

New app signals are review proposals, not executable recipes. `bash scripts/scan_update_feeds.sh` prints an aggregated summary. Proposal export supports preview and explicit acceptance; it is redacted, stays local, and is never uploaded. `bash setup.sh --catalog` opens the optional catalog with no selection. `-y`, noninteractive runs, and EOF install nothing. In the menu, `check <number>` compares only selected sources. Results show the latest confirmed compatible stable version and date, cached for 24 hours. Unknown stays unknown. A public Mac App Store listing does not prove availability to your account, and no channel is always fastest.

The optional catalog starts unselected. A separately approved Homebrew installation is available for KeePassXC when fresh source and absence checks pass. Its preview lists the manager command and declared effects; verification is a Homebrew receipt, not vendor recipe acceptance. Other entries retain their reviewed official acquisition paths. Existing apps are never migrated automatically. Source comparison recommends only what current stable-release evidence supports.

## Local recipe update verification

Update checks include a receipt phase recording evidence and provenance. An incomplete provider group scan is advisory, but unsafe targets are blocked; inspect JSON source issues. The scheduler supports at most two independent mutations across cooperating checkouts for the same OS user. Eligible native windows and supervised legacy handlers can run as a group with explicit consent and shared reservations. The system updater takes the exclusive global lease last. A pending restart or unknown helper can block later mutations until fresh reviewed reconciliation proof; there is no automatic lease expiry or startup reconciliation yet. See [the central implementation receipt](../../implementation/RECIPE_VERIFICATION_2026-11-14.md) for the documented API. Fixture tests do not establish live product acceptance. Existing open apps are protected. DeepSeek Harness is excluded until stable.

Plain `--dry-run` shows a readable preview of up to 10 targets. Use `--dry-run --json-summary` or `--plan` for the complete JSON plan. A preview grants no permission and performs no updates.

The consent screen shows ten eligible items per page. Enter numbers such as `1,3` to approve only their displayed actions; `n` and `p` change pages. Enter or `q` continues without new consent. The screen explains its 120-second answer limit; a timeout does not grant consent. Blocked items are summarized separately. Use `--preferences` for manual, ignored or deferred choices. Diagnostics begin before this review.

## Controls and application list

Tab moves between navigation, work area, output and bottom buttons. Arrows select an item, Space toggles a checkbox, and Enter activates the highlighted button. Questions open an answer field automatically. Use Send to submit; Cancel closes the field without answering.

Inventory shows saved applications grouped by source, with search, filtering and sorting. Save selection writes exclusions; it neither installs nor uninstalls an application. Re-enabling an application requires separate update consent. The preview list remains visible after dry-run. Detailed output is separate from application status.

About contains the author and project links, plus explicit toolkit update checks. Preview prepares a pinned update. Apply exits the interface and asks for confirmation in the terminal. Modified code, an unexpected branch or conflicting local files block the update. No user changes are pushed upstream.

Automatic Internet mode uses the saved agreement when it covers the eligible group; otherwise it offers a separate AUTO review. Authorized native windows open concurrently and scoped download handlers share the supervised batch; Microsoft and Google tasks are grouped. App Store and Homebrew ownership remain separate. DeepSeek Harness stays manual; Open Design currently reports an unavailable automatic method rather than pretending to update. Vendor-selected versions follow existing channel settings. A changed version is reported separately from verified completion. Unconfirmed vendor work retains the batch reservation and defers the system update; Diagnostics offers an explicit, freshly checked recovery review. Google approval explicitly covers all products registered with its updater, including products outside the catalog whose complete list is unknown. This is separate from exact-candidate catalog recipe acceptance. Use `bash update_all.sh --cli --automatic-internet-batch` for the same group review without the terminal workspace; add `--dry-run` for an observational preview.