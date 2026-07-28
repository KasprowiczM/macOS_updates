# Troubleshooting

| Problem | Fix |
|---------|-----|
| New Mac — where to start? | `bash install.sh` or `setup.sh` + `build_inventory.sh` |
| Wrong app catalog / another user's apps | `bash build_inventory.sh` — never copy someone else's `APPLICATIONS.md` |
| App not auto-updating | `bash scripts/report_update_coverage.sh` — add handler per GUIDE |
| macOS update not applied after reboot | `softwareupdate -ia -R` — never `sudo reboot` |
| macOS step was skipped | An earlier step failed; inspect the summary/log, fix it, then rerun. macOS runs last to avoid rebooting a partial session. |
| macOS update step exits after declining restart | Rerun and accept the framework-managed restart (`-R`) or use System Settings; never replace it with a plain reboot. |
| `mas upgrade` fails | `sudo mas upgrade` (CVE-2025-43411) |
| iPad apps "not allowed" error | System Settings → Privacy → Accessibility → add terminal |
| Wrong language | Edit `.mac_update_prefs` → `MAC_LANG=en` |
| APPLICATIONS.md missing | `bash build_inventory.sh` or `dev_sync/dev-sync-import.sh` (owner) |
| `mas` Spotlight warning walls | `export MAS_NO_AUTO_INDEX=1` before calling `mas` |
| Script won't execute | `chmod +x *.sh dev_sync/*.sh` or re-run `setup.sh` |
| `brew: command not found` | `eval "$(/opt/homebrew/bin/brew shellenv)"` |
| `npx` / `node` not found in MCP config | Run `bash update_npm_cli.sh`; fix paths with `scripts/fix_mcp_configs.py` |
| No disk space during update | `brew cleanup --prune=all` |
| Proton mirror has generated files | `bash dev_sync/dev-sync-prune-excluded.sh --plan-out dev_sync_cleanup_plan.json` |
| Free Proton local cache safely | `bash dev_sync/dev-sync-proton-status.sh --full` |
| `mas` login error | Log into App Store manually first |
| Firefox / KeePassXC / Trezor not updating | Check connectivity, `hdiutil verify`, `spctl --assess` |
| Dev sync import rejects manifest path | Regenerate with `dev_sync/dev-sync-export.sh` |
| Microsoft Office not updating | `msupdate` CLI required (ships with Office); inspect `msupdate --list`, then use the MAU package-regression procedure below before reinstalling anything |
| Office reported "Held back — upstream package regression" | Expected: Microsoft is offering a package older than what is installed. Nothing to do — it clears itself. See the section below |
| Office re-downloads the same failing update every run | Fixed in v1.0.21. If it recurs, confirm `mau_deferral_preflight` is not clearing `DeferralDays` (see `critical_rules.md` §9a) |
| Microsoft Teams not updating | Launch Teams for its normal self-update; if MAU surfaces fallback product `TEAMS21`, the shared handler installs it and verifies a clean final `msupdate --list` |
| Internet-apps step feels slow | ~18% of it is a fixed settle that lets launched vendor updaters rewrite `Info.plist`. Lower with `MAC_UPDATE_INTERNET_SETTLE_SECONDS=5` (0 disables, clamped to 120) |
| `mas outdated` or `mas upgrade` hangs | The script stops checks after 120s and upgrades after 1800s; override with `MAC_UPDATE_MAS_CHECK_TIMEOUT` / `MAC_UPDATE_MAS_UPGRADE_TIMEOUT` only for unusually large downloads |
| Docker not updating | Docker Desktop v4.37+ for `docker desktop update` |
| App is only “triggered-unverified” | The toolkit launched the vendor updater but cannot prove completion; reopen the app and verify its About/version screen |
| Intel Mac or macOS 12 and older | **Not supported** — Apple Silicon with macOS 13+ only |
| Homebrew "untrusted taps" warning | `brew trust --formula <user>/<tap>/<formula>` or `brew untap` |
| CI shellcheck fails | See `.shellcheckrc`; run same `find \| xargs shellcheck` as `.github/workflows/ci.yml` |

## Microsoft AutoUpdate: the toolkit says "Held back — upstream package regression"

This is the expected, correct outcome when Microsoft's Preview feed offers an
Office package whose short version is **lower** than what is installed. It is not
a bug in the toolkit and needs no action — the quarantine lifts automatically.

Observed twice so far:

| Date | Installed | Offered | Result |
|------|-----------|---------|--------|
| 2026-07-14 | `16.111.5` (`16.111.26071215`) | `16.111` → normalized `16.111.0` | PackageKit skip + code 112 |
| 2026-07-28 | `16.111.5` (`16.111.26071215`) | `16.111.1` (`26071913`) | PackageKit skip + code 112 |

Since v1.0.21 `update_internet_apps.sh` detects this before installing:

1. `msupdate --list` runs first; the DeferralDays quarantine is left untouched.
2. Each pending product's offered short version is compared to the installed
   `CFBundleShortVersionString`.
3. Strictly-older offers are quarantined via `OptionalUpdatesDeferrals` and
   **excluded from `msupdate --install`** — the packages are never downloaded.
4. Products whose offer has been corrected are released from the quarantine and
   installed normally, in the same run.

To confirm the diagnosis by hand:

```bash
MAU_CLI="/Library/Application Support/Microsoft/MAU2.0/Microsoft AutoUpdate.app/Contents/MacOS/msupdate"
"$MAU_CLI" --list                       # what the feed offers
defaults read "/Applications/Microsoft Word.app/Contents/Info" CFBundleShortVersionString
defaults read com.microsoft.autoupdate2 OptionalUpdatesDeferrals
grep -E 'Skipping component|Code=112' /var/log/install.log | tail -n 10
```

Escape hatches:

| Need | Command |
|------|---------|
| Never touch deferrals | `MAC_UPDATE_MAU_KEEP_DEFERRALS=1 bash update_all.sh` |
| Shorten the quarantine window | `MAC_UPDATE_MAU_DEFERRAL_DAYS=14 bash update_all.sh` (default 7, clamped to 1–28) |
| Preview the change only | `bash update_all.sh --dry-run` |
| Undo everything by hand | `defaults import com.microsoft.autoupdate2 "$MAC_UPDATE_SESSION_DIR/mau_prefs_reconcile_backup.plist"` |

Do **not** work around it by editing a signed Office bundle, deleting the app, or
forcing the lower component into place.

## Microsoft AutoUpdate: installer succeeded with no version change

First distinguish a broken Microsoft AutoUpdate installation from a broken Office update payload. MAU is healthy when its app and CLI are present, its signature is valid, and `msupdate --config` completes. The official MAU path is:

```bash
MAU_APP="/Library/Application Support/Microsoft/MAU2.0/Microsoft AutoUpdate.app"
MAU_CLI="$MAU_APP/Contents/MacOS/msupdate"

defaults read "$MAU_APP/Contents/Info" CFBundleShortVersionString
defaults read "$MAU_APP/Contents/Info" CFBundleVersion
codesign --verify --deep --strict "$MAU_APP"
"$MAU_CLI" --config
"$MAU_CLI" --list
```

The 2026-07-14 Preview-channel incident was an upstream Microsoft package regression, not a missing or corrupt updater:

- MAU `4.83.26040910` was the latest published release and passed code-signature validation.
- The five installed Office apps were valid Microsoft-signed `16.111.5` bundles with build `16.111.26071215`.
- The Preview check feed offered build `16.111.26071325`, but its packages declared the top-level app as `16.111` (normalized by PackageKit to `16.111.0`).
- PackageKit correctly skipped the lower `16.111.0` component because `16.111.5` was installed. The delta package then had no patch files to apply and failed its `postinstall` with `PKInstallErrorDomain Code=112`; the full fallback reported `Installer succeeded with no version change.`
- The Preview history feed still listed `16.111.26071215` as its newest completed release. Reinstalling MAU or manually rerunning the same Office package could not fix the malformed payload.

Confirm this exact failure before applying a workaround:

```bash
for app in "Microsoft Word" "Microsoft Excel" "Microsoft PowerPoint" \
           "Microsoft Outlook" "Microsoft OneNote"; do
    info="/Applications/$app.app/Contents/Info"
    printf '%s: %s (%s)\n' \
        "$app" \
        "$(defaults read "$info" CFBundleShortVersionString)" \
        "$(defaults read "$info" CFBundleVersion)"
done

grep -E 'Skipping component|PKInstallErrorDomain Code=112' \
    /var/log/install.log | tail -n 40
grep 'Installer succeeded with no version change' \
    /Library/Logs/Microsoft/autoupdate.log | tail -n 20
```

Do not force the lower component over the installed signed apps and do not edit their `Info.plist` files. For a `Recommended` update, Microsoft documents a temporary per-app deferral as the safe quarantine. Critical updates bypass deferrals. The following preserves other keys inside `OptionalUpdatesDeferrals`, including an existing Teams deferral:

```bash
mau_prefs_tmp="$(mktemp /tmp/mau-prefs.XXXXXX)" || exit 1
defaults export com.microsoft.autoupdate2 "$mau_prefs_tmp" >/dev/null || exit 1

if ! plutil -extract OptionalUpdatesDeferrals.DeferralDays raw \
    "$mau_prefs_tmp" >/dev/null 2>&1; then
    plutil -insert OptionalUpdatesDeferrals.DeferralDays -json '{}' "$mau_prefs_tmp"
fi

for app_id in MSWD2019 XCEL2019 PPT32019 OPIM2019 ONMC2019; do
    key="OptionalUpdatesDeferrals.DeferralDays.$app_id"
    if plutil -extract "$key" raw "$mau_prefs_tmp" >/dev/null 2>&1; then
        plutil -replace "$key" -integer 7 "$mau_prefs_tmp"
    else
        plutil -insert "$key" -integer 7 "$mau_prefs_tmp"
    fi
done

defaults import com.microsoft.autoupdate2 "$mau_prefs_tmp" >/dev/null
rm -f "$mau_prefs_tmp"
killall "Microsoft AutoUpdate" "Microsoft Update Assistant" 2>/dev/null || true
killall cfprefsd 2>/dev/null || true
MAU_CLI="/Library/Application Support/Microsoft/MAU2.0/Microsoft AutoUpdate.app/Contents/MacOS/msupdate"
"$MAU_CLI" --list
```

The expected verification is `No updates available` with exit code 0. A deferral-day preference is persistent: it delays later recommended Preview builds too. Once Microsoft publishes a corrected package, remove only these five entries, preserve unrelated deferrals, restart MAU, and rerun `msupdate --list`:

```bash
mau_prefs_tmp="$(mktemp /tmp/mau-prefs.XXXXXX)" || exit 1
defaults export com.microsoft.autoupdate2 "$mau_prefs_tmp" >/dev/null || exit 1

for app_id in MSWD2019 XCEL2019 PPT32019 OPIM2019 ONMC2019; do
    plutil -remove "OptionalUpdatesDeferrals.DeferralDays.$app_id" \
        "$mau_prefs_tmp" 2>/dev/null || true
done

defaults import com.microsoft.autoupdate2 "$mau_prefs_tmp" >/dev/null
rm -f "$mau_prefs_tmp"
killall "Microsoft AutoUpdate" "Microsoft Update Assistant" 2>/dev/null || true
killall cfprefsd 2>/dev/null || true
MAU_CLI="/Library/Application Support/Microsoft/MAU2.0/Microsoft AutoUpdate.app/Contents/MacOS/msupdate"
"$MAU_CLI" --list
```

Official references:

- [Update Microsoft applications for Mac by using msupdate](https://learn.microsoft.com/en-us/microsoft-365-apps/mac/update-office-for-mac-using-msupdate)
- [Release history for Microsoft AutoUpdate](https://learn.microsoft.com/en-us/officeupdates/release-history-microsoft-autoupdate)
- [Microsoft AutoUpdate and Deferred Updates](https://learn.microsoft.com/en-us/microsoft-365-apps/mac/mau-deferred-updates)
- [Update history for Office for Mac](https://learn.microsoft.com/en-us/officeupdates/update-history-office-for-mac)

## Skills (in `skills/` directory)

- `computer-use-agents` — GUI automation
- `os-scripting` — system admin
- `bash-pro` — defensive bash patterns
- `context-audit` — token optimization
