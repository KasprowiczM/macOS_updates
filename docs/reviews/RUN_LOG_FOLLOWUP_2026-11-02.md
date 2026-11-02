# Run-log follow-up — 2026-11-02 (macOS 27.2)

Author: Claude Opus 5.5 (orchestrator, implementation and verification). No subagents.
Version: unreleased (stays 1.5.5 under the lockstep policy). The authoritative summary is in [`CHANGELOG.md`](../../CHANGELOG.md).

## Run reviewed

| Run | Duration | Result | Notes |
|-----|----------|--------|-------|
| 2026-11-02 (27.2) | 3 min | clean, exit 0 | NordVPN, svt-av1 and Ledger Live updated. No macOS update pending. Prescan deleted HyperFrames and Superset as "uninstalled" although both were in `/Applications`. KeePassXC was reported current at 2.8.0 while it crashed twice on unlock minutes before the run. |

Evidence is paraphrased below. Raw logs, crash reports and inventory content stay local and are never quoted here.

## Findings and fixes

| ID | Severity | Finding | Fix | Verification |
|----|----------|---------|-----|--------------|
| R1 | high | KeePassXC 2.8.0 bundles Qt 6.11.1, which traps in `QImage::toCGImage` via `setOverrideCursor` on macOS 27.2 when a database is unlocked (upstream keepassxreboot/keepassxc#13822, duplicates #13890/#13896). Upstream published `KeePassXC-2.8.0-1-*.dmg` (Qt 6.11.2) on 2026-10-23 with the same `CFBundleShortVersionString` and an empty `CFBundleVersion`, so the version comparison could never see it. | `vendor_feeds.dmg_package_revision` finds the highest `-N` package revision of the release. `github_rebuild_asset` compares it with the revision the toolkit recorded (`~/.local/state/mac-update/package_revisions.tsv`, mode 0600), or, without a record, with the bundle's creation time. Only that case may install an equal version. The publisher `.DIGEST` sha256 is now verified for every KeePassXC download (closes the old `TODO(H5)`). | Live: 2.8.0-1 installed, `libQt6Gui.6.11.2`, `codesign --verify --deep --strict` passes; the next check finds nothing to do. Tests in `tests/test_run_log_regressions_20261102.py`. |
| R2 | high | Prescan wrote new apps as `Name [arm64]`; the removed-app check passed that raw cell to `app_exists`, so every new app was deleted on the next run. | `inventory.strip_inventory_markers` is applied in `app_exists`. | `InventoryMarkerTests`; a rebuild reports all GROUP 3 apps still installed. |
| R3 | high | Re-adding them failed silently: the 🆕-section regex needed a blank line before the `> **Uwaga:**` note and ran on into the GROUP 4 `4a` formulae table, where `sync_formulae` removed the rows as uninstalled formulae ("Usunięto 2 wpisów … z Homebrew Formulae"). Its dedup also searched the whole file, and the legend line lists every configured internet app. | `inventory.append_rows_to_new_section` is bounded to the section; dedup uses `row_exists`. | `NewSectionInsertTests`; three consecutive `build_inventory.sh` runs keep the rows, no formula removals, no diff. |
| R4 | medium | Open Design, HyperFrames and Superset were not managed. Open Design's `/Applications` bundle is a launcher stuck at 0.21.1 while its native updater runs payload 0.26.1; HyperFrames stays 0.1.0 while its updater ships builds `bNNN`. | Feeds (verify only, artifact `-`): `releases.open-design.ai/stable/latest/metadata.json`, `static.heygen.ai/hyperframes-oss/desktop/latest.json`, Superset's electron-updater `latest-mac.yml`. Method `silent_launch` (vendor truth first, native updater only when behind). Installed version: the launcher's `runtime.json` active payload (only when `install.json` names this bundle) and `HFBuildLabel`, from one implementation (`inventory.vendor_installed_version`) used by `app_version` and the snapshots. Endpoints were confirmed in the apps' own updater code and the vendors' docs (Context7: nexu-io/open-design `tools/pack/AGENTS.md`, heygen-com/hyperframes Studio app docs). | Verify-only: Open Design 0.26.1 current, Superset 2.0.3 current, HyperFrames b637 behind b666. Live: HyperFrames' own updater installed b666 and the toolkit quit the app it had launched. |
| R5 | low | `internet_app_snapshot_version` duplicated the version reader (rule 11) and missed the overrides. | It delegates to `app_version`. | Shell test in `NativeUpdaterVersionTests`. |

## Ruled out

- **keepassxc-browser in Firefox Developer Edition:** 1.10.4.1, equal to the current AMO release; the native-messaging manifest points at the installed `keepassxc-proxy`.
- **keepassxc-cli writes from another project on 2026-11-01:** the database was written at 21:01 and the GUI state (last database and key file paths) is consistent. The first crash with this signature followed the macOS 27.2 upgrade; the stack is in Qt's cursor conversion before any database code runs. An earlier crash on 2026-10-30 (27.0.1) was a different signature (widget teardown).

## Not verified

- Open Design's launcher-payload activation through a toolkit launch (it was already current).
- KeePassXC unlock after the fix: needs the user's password, so it was not attempted.
