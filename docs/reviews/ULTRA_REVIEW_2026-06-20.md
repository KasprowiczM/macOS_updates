# 🍎 Ultra Review & Diagnostic Report — macOS Updates

**Date:** 2026-06-20 · **Reviewer:** Claude (Opus) + 2 audit subagents · **Project:** v1.0.19
**Environment (verified live):** macOS **26.5.1** (Tahoe), **arm64**, run log `logs/update_all_20260620_095258.log` (duration 3 min 7 s, `OVERALL_EXIT = OK`).
**Scope:** diagnose the last run + 6 problem apps, audit installed-app coverage, wire CapCut (done), and produce a prioritized fix backlog with ready-to-run prompts for cheaper models. **No source code was changed by this report** — the only code change applied is the approved CapCut wiring (section 6).

---

## 1. Executive summary

The run "succeeded" — but **the green ✅ is the headline bug, not a clean bill of health.** The last run reported every internet app as `✅ Aktualny`/`✅ Sprawdzony`, yet you observe several apps that never actually update. Both are true at once, because **~26 of 36 internet handlers print success without verifying that anything happened** (`silent_launch_app … || true` → unconditional `STATUS=CHECKED`). That single design flaw is the root cause behind most of your "it says OK but nothing changed" experiences.

Live inspection of your Mac resolved each of the 6 apps you flagged:

| App | Installed (live) | Latest (verified) | Script verdict | What's actually going on |
|---|---|---|---|---|
| **Firefox Dev Edition** | `153.0` | DevEd channel `152.0b10` (Mozilla product‑details) | "current 153.0" | **Real bug.** Beta‑suffix stripping collapses the whole beta cycle into one number → intra‑cycle updates are invisible. Channel numbering can also sit *ahead* of the feed → nonsensical compares / downgrade attempts. |
| **VS Code** | `1.125.1` (now) — was `1.125.0` in the log | `1.125.x` | "current 1.125.0" | **Self‑updated on its own** between runs (+0.0.1). The script's own path is risky: no offline guard → re‑downloads & replaces the *running* app via `cp -R` when the GitHub check fails → corrupted bundle that "won't launch". |
| **Docker Desktop** | `4.78.0` | n/a | "checked" (then hidden‑launch) | **Real bug.** `docker desktop update` is called **with no flags**; in a non‑interactive shell it returns non‑zero → falls back to launching Docker **hidden** (`open -gjF`), which is why it "doesn't launch" for you. The CLI *is* available (confirmed: flags `--check-only`, `--quiet`). |
| **Ledger Wallet** | `4.8.0` (bundle id `com.ledger.live`) | ~`4.x` (Jun 2026) | "current 4.8.0" | **Genuinely ~current.** "Ledger Wallet" is the renamed "Ledger Live". Complaint stems from §1 (script never visibly does anything) + fragile DMG asset‑name after the rebrand. |
| **Trezor Suite** | `26.6.1` | **`26.6.1`** (Jun 2026, confirmed) | "current 26.6.1" | **Genuinely current.** But the version source (`github_latest_tag trezor/trezor-suite`) reads a **monorepo** that tags many non‑desktop packages — it's luck that it matched this cycle. |
| **ChatGPT Atlas** | `1.2026.126.0` | (Sparkle appcast) | "current" | **Likely current.** Appcast parse is fragile (`grep -m1` first match; breaks if the feed is gzip‑encoded → false "offline"). Atlas self‑updates via Sparkle anyway. |

**Bottom line:** Trezor, Ledger, Atlas, and VS Code are essentially up to date — your machine is fine. The *toolkit* is what's misleading you. Firefox and Docker have genuine functional bugs. And one macOS‑specific issue (`cp -R` instead of `ditto` when replacing `.app` bundles) is the most plausible cause of the "won't launch" symptom for any DMG/zip‑installed app.

**CapCut:** ✅ now wired into the updater (silent‑launch method) — see §6. Verified: `bash -n` clean, dispatch/registry parity holds, all 62 static tests pass.

---

## 2. Why "it says updated but isn't" — the three cross‑cutting causes

These explain the majority of symptoms and should be fixed **before** the per‑app tweaks, because they fix many apps at once.

### C1 — Unconditional success reporting (the big one)
`lib/internet_app_updates.sh` — ~26 handlers (Chrome, Brave, ChatGPT, Claude, Comet, Antigravity×2, Gemini, LM Studio, Perplexity, Codex, OpenCode, ProtonVPN, Zoom, Google Drive, MEGAsync, Proton Drive, Docker fallback, Warp, Cursor, AppCleaner, Obsidian, Spotify, RDM, …) do:

```bash
silent_launch_app "X" || true          # fire-and-forget; exit code discarded
STATUS_X="$L_INTERNET_STATUS_CHECKED"   # success, unconditionally
```

A launch that silently fails (app already running, updater broken, no network) is reported identically to a real update. There is **no code path** by which these apps can ever report anything but "checked". This is the user‑facing root cause #1.

### C2 — `cp -R` corrupts `.app` bundles on modern macOS (the "won't launch" cause)
`update_internet_apps.sh:123` (`copy_verified_app`) replaces app bundles with `cp -R`. On macOS 13→26, **`ditto` is the correct tool** for copying application bundles — it preserves extended attributes, ACLs, symlinks and the code signature; `cp -R` can subtly break the signature/structure, after which Gatekeeper refuses to launch the app ("damaged / can't be opened"). Combined with C3 (needless re‑downloads), this is the most likely reason VS Code / a DMG app "won't launch" after a run. The function also `rm -rf`s and replaces apps **while they may be running**, with no "quit first" step.

### C3 — Unauthenticated GitHub API → false "offline" / needless reinstalls
`lib/github_release.sh` calls `api.github.com` with **no `User-Agent` and no token** (60 req/hr per IP, shared). When it returns the `"?"` sentinel, well‑built handlers (KeePassXC, CodeEdit, Trezor) degrade to "offline" — but **VS Code has no offline guard** and instead re‑downloads + reinstalls every time the check fails (feeding C2).

---

## 3. Per‑app diagnosis (detail + file:line)

**Firefox Developer Edition** — `lib/internet_app_updates.sh:30‑93`
Installed `153.0` (from `application.ini` `Version=153.0`; `CFBundleShortVersionString=153.0`). Mozilla `FIREFOX_DEVEDITION` currently `152.0b10`. Line 45 strips the beta suffix (`152.0b10`→`152.0`) before comparing. Because the installed string **never** carries a beta suffix and the feed **always** does, the only way they ever compare equal is via that base‑strip — which is exactly what makes a `…b9 → …b10` update within the same base invisible. Net effect: reports "current" for most of a beta cycle and **never updates**. Secondary: DevEdition's base can run ahead of the published `FIREFOX_DEVEDITION` (you're on `153.0`, feed says `152.0b10`), so on other runs the compare can be nonsensical or attempt a *downgrade* fetch of `firefox-devedition-latest`.

**Visual Studio Code** — `lib/internet_app_updates.sh:664‑712`
`LATEST_VSCODE=$(github_latest_tag "microsoft/vscode" | tr -d 'v')` — `tr -d 'v'` deletes **every** `v` (latent landmine; harmless for today's numeric tags). No `"?"` offline guard: when the GitHub call fails, `VER != "?"` falls into the **download‑and‑replace** branch and reinstalls from `update.code.visualstudio.com/latest` every run — replacing the **running** app via `cp -R` (C2). That is the "won't launch" mechanism. On this run the check happened to match, so nothing was touched; VS Code then self‑updated to `1.125.1`.

**Docker Desktop** — `lib/internet_app_updates.sh:778‑804`
`docker desktop update 2>/dev/null` with **no flags** and **no timeout**. Live check confirms the subcommand exists with `-k/--check-only` and `-q/--quiet`. With no flags in a non‑TTY run it returns non‑zero → fallback `silent_launch_app "Docker"` = `open -gjF -a Docker` (background+hidden), so Docker never visibly comes up. Should be: `docker desktop update --check-only` (detect) → `--quiet` (apply), wrapped in `run_with_timeout`, status derived from the real exit code; drop the hidden‑launch‑as‑success path.

**Ledger Wallet / Live** — `lib/internet_app_updates.sh:908‑977`
Installed `4.8.0` (`com.ledger.live`). "Ledger Wallet" is the renamed "Ledger Live"; `4.x` is the current line (Jun 2026 rollout). The handler already tolerates both names. Likely genuinely current. Risks: the DMG asset URL `ledger-live-desktop-${VER}-mac.dmg` may 404 after the rebrand; the `latest-mac.yml` feed is the right electron‑updater source but should be sanity‑checked post‑rename.

**Trezor Suite** — `lib/internet_app_updates.sh:982‑1037`
Installed `26.6.1` = **confirmed latest** (Trezor "June 2026" desktop release). `github_latest_tag "trezor/trezor-suite"` reads a **monorepo** that also tags `@trezor/connect`, suite‑web, etc.; a non‑desktop tag would silently break the compare. The DMG URL pattern `Trezor-Suite-${VER}-mac-arm64.dmg` is a guess. Prefer the official desktop feed `https://data.trezor.io/suite/releases/desktop/latest/`.

**ChatGPT Atlas** — `lib/internet_app_updates.sh:111‑190`
Installed `1.2026.126.0`. Parses OpenAI's Sparkle appcast with `grep -m1 'sparkle:shortVersionString'`. Risks: if the appcast is served gzip‑encoded, `curl` (without `--compressed`) yields binary → empty parse → false "offline"; `grep -m1` assumes newest‑first ordering; exact string compare assumes the appcast `shortVersionString` format equals `CFBundleShortVersionString`. Atlas ships Sparkle and self‑updates; the manual DMG path is largely redundant.

---

## 4. Installed‑app coverage audit (verified via `mas list`, `brew list --cask`, `_MASReceipt`)

**Covered today:** 14 App Store apps via `update_appstore.sh` (WhatsApp, Telegram, OneDrive, Xcode, NordVPN, Amphetamine, KeePassium, Copilot, iMovie, Keynote/Numbers/Pages incl. "Creator Studio", Notion Web Clipper, Whisper Transcription); 2 Homebrew casks (`blackhole-2ch`, `inkscape`); ~36 internet handlers; Apple system apps via `softwareupdate`.

**❌ Installed but with NO update path** (NON‑MAS, no Sparkle, not in any registry):

| App | Vendor | Suggested method |
|---|---|---|
| DJI Assistant 2 (Consumer Drones) | DJI | `manual` (DJI has no auto‑feed) — already flagged "🆕" in APPLICATIONS.md |
| UniFi | Ubiquiti | `manual` or Ubiquiti download page |
| WiFiman | Ubiquiti | `manual` |
| Picsart | Picsart | `manual` / App Store re‑install |

**No action needed:** Google Docs/Sheets/Slides are Chrome **PWA wrappers** (update with the browser). `Microsoft Defender Shim` and `Proton Mail Uninstaller` are helpers.

**CapCut:** was the only app the Step‑0 prescan flagged as new; now wired (§6).

---

## 5. Ultra‑review findings (deduped from both audit subagents)

Two subagents independently audited the **shell pipeline** and the **Python/infra**. The project's non‑negotiables (`softwareupdate -R`, `sudo mas`, Bash 3.2, `pipefail`/no `set -e`, no hardcoded paths, mktemp) were **all confirmed satisfied** in the core `update_*.sh` pipeline — good baseline hygiene. Findings below are the gaps.

**Shell (S‑series)**

| ID | Sev | file:line | Problem |
|---|---|---|---|
| S1 | 🔴 Crit | `lib/internet_app_updates.sh` (~26 handlers) | Success reported without verification (see C1). |
| S5 | 🟠 High | all `silent_launch_app` call sites | `\|\| true` swallows every launch failure (the mechanism behind S1). |
| C2 | 🟠 High | `update_internet_apps.sh:105‑135` | `cp -R` (not `ditto`) replaces bundles; replaces running apps → broken/"won't launch". |
| S2 | 🔴 Crit | `lib/internet_app_updates.sh:478‑500` | Proton Mail computes a real version diff then **discards** it; status hard‑coded "checked". |
| S3 | 🟠 High | `:670` | `tr -d 'v'` deletes all `v`s; use `sed 's/^v//'` (latent). |
| S4 | 🟠 High | `:664‑712` | VS Code lacks the `"?"` offline guard its siblings have → needless reinstall (see C3). |
| S6 | 🟠 High | `lib/github_release.sh:7` | No `User-Agent`/token → 60 req/hr → false "offline". |
| S10 | 🟡 Med | `:778‑804` | `docker desktop update` no flags/timeout; collapses "no‑op" vs "updated". |
| S7 | 🟡 Med | 6× `hdiutil attach` | Missing `-nobrowse` → Finder windows pop mid‑run. |
| S8 | 🟡 Med | `lib/internet_registry.sh` | Dead method‑registry can drift from real handler behavior. |
| S12 | 🟡 Med | `lib/internet_handlers.sh:38‑50` | Guarded `eval` for dynamic `STATUS_*` — allowlist protects the var name but not the value. |

**Python / infra (P‑series)**

| ID | Sev | file:line | Problem |
|---|---|---|---|
| P1 | 🔴 Crit | `scratch/add_mcp.py:54` | Actual `SyntaxError` (raw newline in string) — file can't run. |
| P3 | 🟠 High | `run_tests.sh` | py_compile glob omits `scratch/*.py` → P1 went undetected. |
| P2 | 🟠 High | `dev_sync/dev_sync_core.py:352`; `dev_sync/dev_sync_prune_excluded.py:244`; `scripts/fix_mcp_configs.py:85` | Non‑atomic JSON writes → corruption risk on your real sync config and `~/.claude.json`. |
| P4 | 🟠 High | `setup.sh`, `fix_mcp_all.sh` | Missing `set -o pipefail` (rest of family has it). |
| P7 | 🟡 Med | `.github/workflows/*.yml` | Actions pinned to mutable tags (`@v5`) not SHAs — supply‑chain risk. |
| P5 | 🟡 Med | `dev_sync/provider_setup.sh` | JSON built by string‑interpolating `read` input (unescaped quotes/backslashes). |
| P8 | 🟡 Med | `.shellcheckrc` | `SC2086` disabled **globally** — hides real word‑splitting bugs. |
| P6 | 🟡 Med | `uninstall.sh` | `rm -rf "$PARENT"` with no empty/`/`/`$HOME` guard. |

**Confirmed clean:** path‑traversal guards in `dev_sync_core.py`, quarantine/prune two‑step safety gates, gitleaks + `.gitignore`/`.claudeignore` secret hygiene, no `eval`/`exec`/`os.system`/`shell=True` in Python, 62/62 static tests pass.

---

## 6. ✅ CapCut — change already applied

CapCut is a **non‑App‑Store, non‑Sparkle** direct download (`com.lemon.lvoverseas`, v8.7.0) with its own in‑app updater → method **`silent_launch`** (consistent with Spotify/AppCleaner/etc.). Wired across all 7 required touchpoints:

1. `config/internet_apps.txt` → `CapCut`
2. `config/internet_app_methods.txt` → `CapCut|silent_launch|STATUS_CAPCUT`
3. `config/internet_dispatch_order.txt` → `iu_capcut`
4. `lib/internet_app_updates.sh` → `iu_capcut()` handler (🎬, Multimedia)
5. `update_internet_apps.sh` → `STATUS_CAPCUT` init + summary `printf` + failure‑scan loop
6. `APPLICATIONS.md` → moved CapCut out of "🆕 do skategoryzowania" into **🎨 Multimedia** + added to the auto‑coverage list

**Verification:** `bash -n` clean; dispatch↔handler parity OK; `python3 -m unittest tests.test_safety_static` → 62 passed.

> Note: CapCut inherits the C1/S1 "checked = unverified" caveat shared by all silent‑launch apps. Fixing WI‑1 below upgrades CapCut's honesty automatically.

---

## 7. Fix backlog — prioritized, with ready‑to‑run prompts

Each work item is a **self‑contained prompt** you can paste to a cheaper model (Haiku/Sonnet worker). Every prompt assumes this header:

> **Global constraints (obey exactly):** Bash 3.2 only (no `declare -A`, `mapfile`, `readarray`, `${v^^}`). All `update_*.sh` keep `set -o pipefail` and must NOT add `set -e`. No hardcoded paths (`SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"`); temp via `mktemp`. Don't touch i18n keys without adding the key to all 7 `i18n/lang_*.sh`. After changes run `bash -n` on every edited script and `bash run_tests.sh`; both must pass. Make the **smallest** change that fixes the issue. Work on `/Users/mk/Dev_Env/macOS_updates`.

---

### 🔴 P0 — correctness & user‑visible (do first)

#### WI‑1 — Make silent‑launch handlers report the truth (fixes C1/S1/S5)
> **Role:** Bash 3.2 engineer. **Files:** `lib/internet_app_updates.sh`, `lib/internet_handlers.sh`, `update_internet_apps.sh`, all 7 `i18n/lang_*.sh`.
> **Problem:** ~26 handlers do `silent_launch_app "X" || true` then unconditionally set `STATUS_X="$L_INTERNET_STATUS_CHECKED"`, so a failed launch looks identical to a success. **Task:** (1) In `internet_handler_silent_launch` (and every inline silent‑launch handler), capture the launch exit code: `silent_launch_app "$t"; rc=$?`. (2) Capture `app_version` (or bundle mtime via `mdls -name kMDItemContentModificationDate -raw`) before and after, with a bounded `sleep`. (3) Set status to a new honest constant `L_INTERNET_STATUS_LAUNCHED_UNVERIFIED` ("launch attempted — verify manually") when `rc=0` but no version/mtime change can be confirmed, and to `L_INTERNET_STATUS_LAUNCH_FAILED` when `rc!=0`. Reserve `…_CHECKED`/`…_CURRENT` for confirmed cases only. (4) Add both new keys to all 7 `i18n/lang_*.sh` (English text first, mirror existing style). (5) Add `L_INTERNET_STATUS_LAUNCH_FAILED` to the failure‑scan `case` in `update_internet_apps.sh:369` so it counts toward `INTERNET_EXIT`. **Acceptance:** `bash -n` + `bash run_tests.sh` pass; a forced‑fail launch shows a non‑green status in the summary. Keep changes mechanical and uniform across handlers.

#### WI‑2 — Replace `cp -R` with `ditto` + quit‑running‑app (fixes C2, the "won't launch")
> **Role:** macOS/Bash engineer. **File:** `update_internet_apps.sh` (`copy_verified_app`, ~line 105‑135). **Problem:** App bundles are copied with `cp -R`, which can break code signatures / xattrs on macOS 13‑26 → Gatekeeper refuses to launch; bundles are also replaced while running. **Task:** (1) Replace the `cp -R "$app_path" "$staging"` with `ditto "$app_path" "$staging"` (ditto preserves signature/xattrs/ACLs; it's the Apple‑sanctioned bundle copy). (2) Before swapping, if the destination app is running, quit it first: `osascript -e 'quit app "<name>"'` best‑effort with a short wait, OR detect via `pgrep -f` and skip‑with‑warning if still running. (3) Keep the existing staging‑then‑atomic‑`mv` swap. (4) After `mv`, re‑verify with `spctl --assess --type execute "$dest"` and, on failure, restore is not needed (old app already gone) but set an INSTALL_ERROR status and log to `$MAC_UPDATE_SESSION_DIR/internet_diag.txt`. **Acceptance:** `bash -n` passes; a dry‑run (`MAC_UPDATE_DRY_RUN=1`) still short‑circuits; updating a DMG app leaves a launchable, validly‑signed bundle. Bash 3.2 only.

#### WI‑3 — Fix the Docker Desktop handler (fixes Docker "won't launch")
> **Role:** Bash engineer. **File:** `lib/internet_app_updates.sh:778‑804` (`iu_docker_desktop`). **Problem:** `docker desktop update` is run with no flags and no timeout; in a non‑interactive shell it returns non‑zero and the script falls back to launching Docker **hidden**. The CLI supports `--check-only` and `--quiet` (verified). **Task:** rewrite the update branch as: if `command -v docker`, run `run_with_timeout 60 docker desktop update --check-only` to detect; if an update is available, run `run_with_timeout 600 docker desktop update --quiet` to apply and set `STATUS_DOCKER` to UPDATED/CURRENT based on the real exit code; capture stdout into `$MAC_UPDATE_SESSION_DIR/docker_diag.txt` instead of discarding it; only fall back to a **visible** `open -a Docker` (not `-gjF`) if the CLI is genuinely absent. Distinguish "no update available" (CURRENT) from "applied" (UPDATED) from "unsupported" (CHECKED). **Acceptance:** `bash -n` + `run_tests.sh` pass; no hidden‑launch on the success path.

#### WI‑4 — Fix VS Code handler: offline guard + correct version strip (fixes S3/S4)
> **Role:** Bash engineer. **File:** `lib/internet_app_updates.sh:664‑712` (`iu_visual_studio_code`). **Task:** (1) Change `tr -d 'v'` to `sed 's/^v//'`. (2) Add the `"?"` offline guard used by the sibling github_dmg handlers (KeePassXC `:422`, CodeEdit `:727`, Trezor `:991`): `if [ "$LATEST_VSCODE" = "?" ]; then silent_launch_app "Visual Studio Code" || true; STATUS_VSCODE="$L_INTERNET_STATUS_OFFLINE"; else … existing logic … fi` — so a failed GitHub lookup never triggers a download. (3) Only enter the download branch when `LATEST_VSCODE != VER` AND `LATEST_VSCODE != "?"`. (4) Pair with WI‑2 so the replace is `ditto`‑based and quits a running VS Code first. **Acceptance:** with the network blocked, the handler reports offline and does NOT reinstall; `bash -n` + `run_tests.sh` pass.

#### WI‑5 — Fix Firefox Developer Edition version comparison (fixes "Firefox never updates")
> **Role:** Bash engineer + Firefox release model. **File:** `lib/internet_app_updates.sh:30‑93` + `lib/internet_apps.sh:49‑58`. **Problem:** Installed version (`application.ini Version=153.0`, no beta suffix) is compared against Mozilla `FIREFOX_DEVEDITION` (`152.0b10`, beta suffix) after **stripping the suffix to the base** — so beta‑to‑beta updates within one base are invisible, and the channel numbers can even invert (installed `153.0` > feed `152.0b10`). **Task:** stop relying on base‑equality. Read a full, comparable build identity: prefer `CFBundleVersion` (DevEdition encodes the build) or the `application.ini` `BuildID`, and compare against the corresponding Mozilla field; if only the marketing version is available, treat **any difference** (including different beta number) as "update available" and let the existing download path run — but guard against downgrades by only updating when the feed version sorts **higher** (use a Bash‑3.2 `sort -V` comparison helper, not arithmetic). Document the chosen channel (DevEdition = beta). **Acceptance:** when feed beta > installed beta the handler downloads; when equal it reports current; it never attempts a downgrade. `bash -n` + `run_tests.sh` pass.

#### WI‑6 — Harden version sources: GitHub auth + Trezor/Ledger/Atlas feeds (fixes C3/S6)
> **Role:** Bash engineer. **Files:** `lib/github_release.sh`; `lib/internet_app_updates.sh` (Trezor `:982`, Ledger `:908`, Atlas `:111`). **Task:** (1) In `github_latest_tag`, add `-H "User-Agent: macos-updates-toolkit"` and, when `$GITHUB_TOKEN` is set, `-H "Authorization: Bearer $GITHUB_TOKEN"` (build the header array conditionally so an unset token adds nothing). Document the optional `GITHUB_TOKEN` in README. (2) Trezor: switch the version/asset source from the monorepo `releases/latest` to the official desktop channel `https://data.trezor.io/suite/releases/desktop/latest/` (parse its version + arm64 dmg name) — or at minimum filter monorepo tags to those matching `^v?[0-9]{2}\.[0-9]+\.[0-9]+$`. (3) Atlas: add `--compressed` to the appcast `curl` and parse the **highest** `sparkle:shortVersionString` rather than the first match. (4) Ledger: verify the `latest-mac.yml` `path:`/asset name and use it for the DMG URL instead of hardcoding `ledger-live-desktop-${VER}-mac.dmg`. **Acceptance:** each handler still reports correctly with the network up; `bash -n` + `run_tests.sh` pass.

---

### 🟠 P1 — robustness & safety

#### WI‑7 — Fix `scratch/add_mcp.py` syntax + widen test coverage (fixes P1/P3)
> **Role:** Python engineer. **Files:** `scratch/add_mcp.py:54`, `run_tests.sh`. **Task:** (1) Repair the unterminated string at line 54 — the intended `f.write("\n")` has a literal raw newline inside the quotes; put the proper `\n` escape on one line. Run `python3 -m py_compile scratch/add_mcp.py` to confirm. (2) In `run_tests.sh` step 2, extend the py_compile glob to include `scratch/*.py` only when the dir exists, e.g. `python3 -m py_compile dev_sync/*.py scripts/*.py tests/*.py $([ -d scratch ] && echo scratch/*.py)`. **Acceptance:** `bash run_tests.sh` compiles all `.py` and still passes.

#### WI‑8 — Atomic JSON writes for config files (fixes P2)
> **Role:** Python engineer. **Files:** `dev_sync/dev_sync_core.py:352`, `dev_sync/dev_sync_prune_excluded.py:244`, `scripts/fix_mcp_configs.py:85`. **Task:** add one shared helper and route writes through it:
> ```python
> def atomic_write_text(path, content, encoding="utf-8"):
>     tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
>     tmp.write_text(content, encoding=encoding)
>     os.replace(tmp, path)  # atomic on same filesystem
> ```
> For `fix_mcp_configs.py` (touches the user's live `~/.claude.json`/MCP configs) also copy the existing file to `<path>.bak` before writing. **Acceptance:** `python3 -m py_compile` clean; a `KeyboardInterrupt` mid‑write can't truncate the target. No behavior change on the happy path.

#### WI‑9 — pipefail in setup scripts + `-nobrowse` on hdiutil (fixes P4/S7)
> **Role:** Bash engineer. **Files:** `setup.sh`, `fix_mcp_all.sh`; `lib/internet_app_updates.sh` (6× `hdiutil attach`). **Task:** (1) Add `set -o pipefail` near the top of `setup.sh` and `fix_mcp_all.sh` (do NOT add `set -e`). (2) Add `-nobrowse` to every `hdiutil attach … -quiet` call so DMG mounts don't pop Finder windows during unattended runs. **Acceptance:** `bash -n` on all three; `run_tests.sh` passes.

#### WI‑10 — Pin CI actions to SHAs + un‑hide SC2086 (fixes P7/P8)
> **Role:** DevOps. **Files:** `.github/workflows/*.yml`, `.shellcheckrc`. **Task:** (1) Replace mutable action tags (`actions/checkout@v5`, `gitleaks/gitleaks-action@v2`) with full commit SHAs plus a `# vX.Y.Z` comment. (2) Remove `SC2086` from the global `disable=` in `.shellcheckrc`; instead add per‑line `# shellcheck disable=SC2086` only where word‑splitting is intentional. Report (don't auto‑fix) any new SC2086 warnings the codebase surfaces. **Acceptance:** CI still green; shellcheck job runs with SC2086 active.

---

### 🟡 P2 — cleanups & hardening

#### WI‑11 — Input‑escaping + destructive‑path guard (fixes P5/P6)
> **Role:** Bash engineer. **Files:** `dev_sync/provider_setup.sh` (`create_config_json`), `uninstall.sh`. **Task:** (1) In `create_config_json`, stop interpolating raw `read` input into the JSON heredoc — either escape `\` and `"` for each of the 5 values, or (preferred) emit the JSON via a `python3 - <<'PY'` heredoc using `json.dumps()`. (2) In `uninstall.sh`, before `rm -rf "$PARENT"`, add: `case "$PARENT" in ""|"/"|"$HOME") echo "Refusing unsafe path: $PARENT" >&2; exit 1;; esac`. **Acceptance:** a folder name containing `"` produces valid JSON; uninstall refuses degenerate paths. `bash -n` passes.

#### WI‑12 — Reconciliation logging + dead‑code + Proton Mail status (fixes S2/S8/S14)
> **Role:** Bash engineer. **Files:** `update_all.sh` (postupdate step), `lib/internet_app_updates.sh:478‑500`, `lib/internet_registry.sh`, `lib/internet_handlers.sh`. **Task:** (1) Proton Mail: use the version diff it already computes — set `STATUS_PROTONMAIL` to CURRENT/UPDATED/OFFLINE instead of hard‑coded "checked". (2) Add a reconciliation check in the postupdate Python: if the before/after snapshot (`internet_before.txt`/`internet_after.txt`) shows a version change for an app whose `STATUS_*` was never "updated" (or vice‑versa), log a warning to the run log — this makes S1‑class drift self‑diagnosing. (3) Either delete the unused `internet_registry_load`/`internet_registry_method_for` + `internet_handler_fail_scan`, or add header comments marking the method registry as documentation‑only. **Acceptance:** `bash -n` + `run_tests.sh` pass; the run log prints a reconciliation note when status and snapshot disagree.

#### WI‑13 — Add update paths for the 4 uncovered apps (optional)
> **Role:** Bash engineer. **Files:** the 3 `config/*.txt`, `lib/internet_app_updates.sh`, `update_internet_apps.sh`, `APPLICATIONS.md`. **Task:** using `scripts/scaffold_internet_app.sh "<App>" manual` as the template, add `manual` handlers (print version + vendor download URL, status = MANUAL_UPDATE) for **DJI Assistant 2**, **UniFi**, **WiFiman**, **Picsart**, following the same 7‑touchpoint pattern used for CapCut in §6. Move DJI out of the "🆕 do skategoryzowania" table in `APPLICATIONS.md`. **Acceptance:** dispatch↔handler parity holds; `bash run_tests.sh` passes.

---

## 8. Suggested execution order

1. **WI‑1 + WI‑2** together (they fix the most symptoms: honest status + launchable bundles).
2. **WI‑3, WI‑4, WI‑5** (Docker, VS Code, Firefox — the three with real functional bugs).
3. **WI‑6** (version sources) — unblocks reliable detection for the github_dmg apps.
4. **WI‑7 → WI‑10** (P1 safety/CI).
5. **WI‑11 → WI‑13** (P2 polish + coverage).

Re‑run `bash update_all.sh --dry-run` after each P0 item, then a real `bash update_all.sh`, and confirm the summary now shows honest, per‑app outcomes.

---
*Generated 2026-06-20. Diagnoses verified against live system state (read‑only) and official version feeds. The only code change applied is the CapCut wiring (§6); all other fixes are specified as prompts for implementation by worker models.*

