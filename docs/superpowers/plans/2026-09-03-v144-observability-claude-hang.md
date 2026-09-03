# v1.4.4 — Hang Claude Code + R1–R6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unblock `update_all.sh` when a vendor native installer TUI hangs, then land Ultra Review R1–R6 as v1.4.4 without regressing the v1.4.3 MAU/App Store/counts fixes.

**Architecture:** Sequential Bash 3.2 orchestrators stay sequential. The hang is fixed at the process-control boundary (`lib/proc.sh`) and the Claude Code update path (prefer `claude update` over re-running `install.sh`'s TUI). Observability (chronic warnings, pending counts, App Store track divergence) is additive: new files and extra diagnostics, no change to decision logic except the Claude path and timeout kill.

**Tech Stack:** Bash 3.2, Python 3 stdlib (`lib/python/`), GNU `timeout` from Homebrew coreutils, `unittest`.

**Spec:** `docs/reviews/GEMINI_TASK_2026-09-02.md` (Z1–Z5) plus live incident `logs/update_all_20260903_101005.log` (Z0, not in the Gemini prompt).

Callers of this document: none at runtime. The next implementing agent and the user read it. Closest existing file `docs/reviews/GEMINI_TASK_2026-09-02.md` is the task prompt, not a checkbox implementation plan.

## Global Constraints

- Evidence is the target system, never the repo. A green regex-on-file test does not prove a call site exists.
- Do not touch the six v1.4.3 invariants (MAU quarantine clock, TEAMS21 pin, single `mau_reconcile_deferrals` call, TOR 1 explicit IDs + one retry, `run_counts.json` → `counts`, IPMIView/DJI as `print_info`).
- Bash 3.2: no `declare -A` / `mapfile` / `readarray`. Empty arrays under `set -u` need `(( ${#ARR[@]} > 0 ))`.
- `update_*.sh`: `set -o pipefail`, never `set -e`.
- Pipeline Python stays in heredocs or `lib/python/`.
- `SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"`.
- New user-visible strings: all seven `i18n/lang_*.sh` keys, or a plain English string.
- `softwareupdate` must keep `-R`. `mas upgrade` keeps `sudo` + explicit IDs + one user-session retry.
- Never `brew outdated` with `2>&1`; never `brew list --cask --versions`; use `lib/brew.sh`.
- `norm_name()` lives only in `lib/python/inventory.py`.
- Vendor installers that prompt on `/dev/tty` need their own non-interactive switch. A longer timeout is not a fix.
- Internet-step baseline to preserve: **0 warnings, exit 0**. Any regression is a failed change.
- Do not implement until the user approves this plan.

## Findings that the Gemini prompt did not contain (measured 2026-09-03)

### Z0 — Claude Code native installer hung the whole run

`logs/update_all_20260903_101005.log` (8015 bytes vs ~48–60 KB for a finished run) stops at:

```
Aktualizuję claude-code przez własny updater (native installer update)...
```

Measured on the machine:

- WhatsApp TOR 1 completed: `26.34.72 → 26.34.74`. TOR 2 GUI said no pending updates. App Store step finished OK.
- Node `26.8.1`, npm `12.0.2`, pnpm `11.25.0` finished. Then Claude.
- `~/.local/bin/claude` symlink and `~/.local/share/claude/versions/2.1.259` mtime **10:15**. Previous binary `2.1.258` from 2026-09-02.
- Log mtime stays **10:10:55**. Parent never printed `print_ok` / `print_warn`. No `run_summary_20260903_*.json`.
- By 10:21 the process was gone. Session dir cleaned up.
- Steps 3–6 (Homebrew, internet, postupdate, `softwareupdate -R`) **never started**. Independent vendor daemons (MAU, Keystone, Sparkle) keep running outside the toolkit; the toolkit itself does not update anything after a hang in step 2.

Root cause, from Anthropic's own `https://claude.ai/install.sh` (fetched 2026-09-03):

```sh
echo "Setting up Claude Code..."
"$binary_path" install ${TARGET:+"$TARGET"} || install_code=$?
```

The installer comments call this **the binary's TUI** and restore `stty sane` after signal death. `update_npm_cli.sh` runs `curl | sh` every run, including when Claude is already installed. `native_installer_env` only sets `CODEX_NON_INTERACTIVE=1` for Codex. Claude gets an empty env. `run_quiet_with_error_log` redirects stdout/stderr to a temp file, so the TUI prompt is invisible.

Second defect, same stack: `lib/proc.sh` prefers Homebrew GNU `timeout` **without `--kill-after`**. GNU timeout then sends SIGTERM and waits forever if the TUI catches/ignores TERM. The bash fallback in the same function already SIGKILLs after 5 s — that path is dead on this machine because `/opt/homebrew/bin/timeout` exists.

Vendor CLI on this Mac (`claude install --help`): `--force` only. Subcommand `update|upgrade` exists: "Check for updates and install if".

### Other apps during the hang

| Layer | What happened 2026-09-03 |
|---|---|
| App Store TOR 1 | Ran and succeeded (WhatsApp). |
| App Store TOR 2 | Ran; GUI reported empty while TOR 1 had just installed. Divergence not written as a three-way comparison (Z4). |
| Native CLI after Claude | Never reached (codex, opencode, agy, cursor-agent, bun). |
| Homebrew / internet / macOS | Never reached. |
| Background vendor updaters | Unrelated to the script; not evidence the toolkit finished its job. |

Fixing timeout kill + switching installed Claude to `claude update` is what lets the rest of the pipeline run. Do not parallelize steps.

### Trusted sources (audit, no drive-by method changes)

Doctrine already in `docs/reviews/Opus5_Max_Ultra_Review_v6.md`: the fastest trusted channel wins; Homebrew cask `claude-code` is ~7 days behind and must not replace the native installer.

| App / CLI | Configured method | Actual fetch | Verdict |
|---|---|---|---|
| Claude Code CLI | `native-installer` → `https://claude.ai/install.sh` | Official Anthropic CDN `downloads.claude.ai` + SHA256 | **Right source, wrong invocation** (TUI every run). Z0 changes invocation only. |
| Codex CLI | native-installer + `CODEX_NON_INTERACTIVE=1` | `https://chatgpt.com/codex/install.sh` | Correct (v1.4.2). |
| Agy / Cursor Agent | native-installer | vendor install URLs | Correct; will run again once Claude cannot stall the loop. |
| OpenCode CLI | npm `@latest` into managed prefix | npm registry | Correct for this product. |
| Firefox Developer Edition | labelled `github_dmg` | Mozilla `product-details` + `download.mozilla.org/?product=firefox-devedition-latest` | **Right bytes, misleading method name.** Do not rename in this release. Z5 only fixes the user-visible version string. |
| Office | `msupdate` / MAU `Current` | Microsoft AutoUpdate | Correct after v1.4.3. Do not touch quarantine. |
| Chrome / Drive | Google Keystone | Keystone agent | Correct. |
| brew_cask apps (Brave, Obsidian, Spotify, …) | Homebrew, **not** internet dispatch (`config/internet_dispatch_order.txt` comments them out) | `brew upgrade --cask` via `lib/brew.sh` | Correct verified channel. Spotify `sudo launchctl` stall is R7 — **out of scope** (Gemini: no code). |
| VS Code, KeePassXC, Ledger, Trezor, CodeEdit | `github_dmg` | GitHub / vendor metadata + DMG verify | Correct. Ledger digest pairing already fixed in v1.4.2. |
| IPMIView, DJI | `manual` | none | Correct; `print_info` in v1.4.3. |

Do not migrate anything to Homebrew to "clean up" Claude Code. That would be a freshness regression documented by the vendor.

### Z2 preview (write the full answers in the audit doc during Task 3)

1. **Cask downgrade guard** (`update_brew.sh` ~239–311): re-reads `brew info --json=v2` and `app_vs_package_version_relation` every run. Skip is per-run. Next newer cask version is observable. **Passes. No code change.**
2. **`vendor_latest`** (`lib/internet_handlers.sh`): feed is fetched every run; on miss it degrades to launch-unverified and tries again next run. Nothing is persisted that hides the feed. **Passes. No code change.**
3. **npm skip filters** (`resolve_command_path`, "nie jest zainstalowany — pomijam", `remove_legacy_brew_formulas`): path preference and absence skips, re-evaluated every run from live `PATH` / `brew list`. **Passes. No TTL.** Document why, then add AGENTS.md rule 10 anyway.

## File map

| File | Role |
|---|---|
| `lib/proc.sh` | GNU/gtimeout `--kill-after=5`; keep bash fallback SIGKILL. |
| `update_npm_cli.sh` | Installed Claude → `claude update`; bootstrap only via `install.sh`. Log native-installer output to the session dir. |
| `lib/python/chronic_warnings.py` | Pure functions: trailing non-OK streak per step. |
| `scripts/report_chronic_warnings.sh` | Thin wrapper; never changes exit code. |
| `update_all.sh` | Call chronic reporter after `write_run_summary`; merge `pending_after_run`. |
| `update_appstore.sh` / `update_brew.sh` / `lib/internet_app_updates.sh` | Write pending-after-run counts; App Store three-way diag. |
| `lib/internet_app_updates.sh` `iu_firefox_developer_edition` | Show bundle + channel. |
| `.mac_update_prefs` (gitignored) | Delete dead `FIREFOX_DEV_CHANNEL_VERSION`. |
| `docs/reviews/GUARD_AUDIT_2026-09.md` | Z2 answers. |
| `AGENTS.md` | Rule 10. |
| `tests/test_run_log_regressions_20260903.py` | Behavioral regressions for every task. |
| `VERSION` / `CHANGELOG.md` | 1.4.4. |

`tests/test_dev_sync_safety.py` **does not exist**. Safety lives in `tests/test_safety_static.py` (`DevSyncPathSafetyTests`). Completion item 2 becomes: run that class separately. `tests/run_all.sh` also does not exist; `run_tests.sh` uses `unittest discover tests`.

Planned data files (synthetic):

```json
{
  "timestamp": "2026-08-15T08:10:00+00:00",
  "steps": {
    "internet": "Ostrzeżenie zakończono z ostrzeżeniami (niezweryfikowane)"
  }
}
```

Session pending files: one integer per file, `pending_appstore`, `pending_brew_formulae`, `pending_brew_casks`, `pending_mau`.

---

### Task 1: Timeout always SIGKILLs (Z0a)

**Files:**
- Modify: `lib/proc.sh`
- Test: `tests/test_run_log_regressions_20260903.py`

**Interfaces:**
- Consumes: existing `run_with_timeout seconds cmd...` (exit 124 on timeout).
- Produces: same signature; GNU path uses `--kill-after=5`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_run_log_regressions_20260903.py`:

```python
"""Regressions for the 2026-09-03 hang and Ultra Review R1–R6 (v1.4.4)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_proc(snippet: str, timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", f'source "{REPO_ROOT}/lib/proc.sh"; {snippet}'],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=timeout,
    )


class TimeoutKillAfterTests(unittest.TestCase):
    def test_term_ignoring_child_still_returns_124(self) -> None:
        """GNU timeout without --kill-after waits forever if the child traps TERM.

        That is the 2026-09-03 hang class: claude install TUI after a successful
        binary swap. The bash fallback already SIGKILLs; the GNU path must too.
        """
        start = time.monotonic()
        out = run_proc(
            'run_with_timeout 1 bash -c \'trap "" TERM; sleep 30\'',
            timeout=15,
        )
        elapsed = time.monotonic() - start
        self.assertEqual(out.returncode, 124, out.stderr)
        self.assertLess(elapsed, 10)
```

- [ ] **Step 2: Run it — expect FAIL** (hangs until unittest timeout, or never returns 124)

```bash
python3 -m unittest tests.test_run_log_regressions_20260903.TimeoutKillAfterTests -v
```

- [ ] **Step 3: Minimal implementation in `lib/proc.sh`**

Replace the GNU/gtimeout branches:

```bash
run_with_timeout() {
    local seconds="$1"
    local command_pid command_exit elapsed grace
    shift
    if command -v timeout >/dev/null 2>&1; then
        timeout --kill-after=5 "$seconds" "$@"
    elif command -v gtimeout >/dev/null 2>&1; then
        gtimeout --kill-after=5 "$seconds" "$@"
    else
        # existing SIGTERM + 5s grace + SIGKILL fallback unchanged
        ...
    fi
}
```

Do **not** add `--foreground`: that disables process-group kill and is how children escape the timeout.

- [ ] **Step 4: Re-run the test — expect PASS**

- [ ] **Step 5: Commit** only after the user has approved the plan and asked to implement. Message: `fix: SIGKILL vendor TUI that ignore SIGTERM (v1.4.4)`

---

### Task 2: Claude Code — `claude update` when already installed (Z0b)

**Files:**
- Modify: `update_npm_cli.sh` (`native_installer_env`, `install_latest_npm_packages` native-installer branch)
- Test: `tests/test_run_log_regressions_20260903.py`

**Interfaces:**
- Consumes: `resolve_command_path claude`, `LOCAL_BIN`, `native_installer_timeout`, `run_quiet_with_error_log`.
- Produces: installed Claude updated via `claude update`; first-time install still `curl | sh -s latest`.

- [ ] **Step 1: Failing tests**

```python
class ClaudeNativeInstallerPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = (REPO_ROOT / "update_npm_cli.sh").read_text(encoding="utf-8")

    def test_installed_claude_uses_self_update_not_install_sh(self) -> None:
        """install.sh always downloads ~200MB then runs a TUI (`claude install`).

        2026-09-03: binary 2.1.259 landed at 10:15; the TUI never returned, so
        brew/internet/system never ran. The vendor's own `claude update` is the
        update path once ~/.local/bin/claude exists.
        """
        self.assertIn('"claude" update', self.source)
        self.assertIn("https://claude.ai/install.sh", self.source)

    def test_claude_update_is_gated_on_existing_binary(self) -> None:
        self.assertRegex(
            self.source,
            r'command_name" = "claude".*-x "\$LOCAL_BIN/claude"',
        )
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implementation**

In the `native-installer` branch, **before** `curl | sh`:

```bash
elif [ "$method" = "native-installer" ]; then
    local install_url="" installer_env=""
    case "$command_name" in
        claude) install_url="https://claude.ai/install.sh" ;;
        codex)  install_url="https://chatgpt.com/codex/install.sh" ;;
        agy)    install_url="https://antigravity.google/cli/install.sh" ;;
        agent)  install_url="https://cursor.com/install" ;;
    esac
    installer_env="$(native_installer_env "$command_name")"
    if [ -z "$install_url" ]; then
        print_warn "${display_name}: native-installer method not implemented for ${command_name}"
        failures=$((failures + 1))
        continue
    fi
    print_info "$(printf "$L_NPM_UPDATING_VIA_SELF_UPDATE" "${display_name}" "native installer")"
    if [ "$command_name" = "claude" ] && [ -x "$LOCAL_BIN/claude" ]; then
        if run_quiet_with_error_log \
            "${command_name} update" \
            run_with_timeout "$(native_installer_timeout)" \
            "$LOCAL_BIN/claude" update </dev/null; then
            print_ok "${display_name}: $(detect_command_version "$display_name" "$LOCAL_BIN/$command_name")"
        else
            print_warn "$(printf "$L_NPM_PACKAGE_UPDATE_FAILED" "${display_name}")"
            failures=$((failures + 1))
        fi
        continue
    fi
    if run_quiet_with_error_log \
        "${command_name} native installer" \
        run_with_timeout "$(native_installer_timeout)" \
        env $installer_env sh -c "curl -fsSL '$install_url' | sh -s latest" </dev/null; then
        print_ok "${display_name}: $(detect_command_version "$display_name" "$LOCAL_BIN/$command_name")"
    else
        print_warn "$(printf "$L_NPM_PACKAGE_UPDATE_FAILED" "${display_name}")"
        failures=$((failures + 1))
    fi
```

Keep Codex on `install.sh` + `CODEX_NON_INTERACTIVE=1` (v1.4.2). Do not invent a Claude env var that the vendor does not document. `claude install --help` (measured) has only `--force`.

Optional observability (same task, still no decision-logic change): for native-installer runs, copy the last 30 lines of the quiet stderr file to `$MAC_UPDATE_SESSION_DIR/native_installer_${command_name}.log` **even on success**, so a future hang that *does* get killed leaves evidence. `run_quiet_with_error_log` currently deletes the file on success.

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Live measure (required)**

```bash
timeout --kill-after=5 60 ~/.local/bin/claude update </dev/null
echo exit=$?
~/.local/bin/claude -v
```

Record exit and version. If `claude update` itself is a TUI, the 60 s + kill-after must still return; then keep the path (timeout is the backstop) and log it as a vendor TUI in CHANGELOG. Do **not** lengthen the timeout to paper over the TUI.

---

### Task 3: Guard audit + AGENTS.md rule 10 (Z2)

**Files:**
- Create: `docs/reviews/GUARD_AUDIT_2026-09.md`
- Modify: `AGENTS.md` (rule 10 after rule 8; there is no rule 9 today)

**Interfaces:** none (documentation). No behavior change if all three pass.

- [ ] **Step 1: Write the audit from the measured code** (answers already previewed above). Required headings per guard: Q1 hide input? Q2 release event observable while armed? Q3 TTL only if no. Explicit "passes because…" for each.

- [ ] **Step 2: Add AGENTS.md rule 10**

```
10. **Every mechanism that hides its own diagnostic input must declare a
    lifetime and a path back to re-evaluation.** A guard whose release
    condition is an observation the guard itself suppresses is a deadlock
    (Office `DeferralDays` 2026-07-14 → 2026-09-01). Pattern: record an
    expiry the guard controls, pass the expired set into the same
    reconcile call, never a second export/import. See
    `mau_quarantine_expired_ids`.
```

- [ ] **Step 3: Test that the rule exists**

```python
class AgentsRuleTenTests(unittest.TestCase):
    def test_rule_10_is_in_agents_md(self) -> None:
        text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("hides its own diagnostic input", text)
        self.assertIn("mau_quarantine_expired_ids", text)
```

Do **not** change cask guard / vendor_latest / npm filters.

---

### Task 4: Chronic warning detector (Z1 / R2)

**Files:**
- Create: `lib/python/chronic_warnings.py`
- Create: `scripts/report_chronic_warnings.sh`
- Modify: `update_all.sh` (after `write_run_summary`, before final exit)
- Test: `tests/test_run_log_regressions_20260903.py`

**Interfaces:**
- Consumes: `logs/run_summary_20*.json` (exclude `run_summary_latest.json`), env `MAC_UPDATE_CHRONIC_WINDOW` default 10, `MAC_UPDATE_CHRONIC_THRESHOLD` default 3, optional `MAC_UPDATE_LOGS_DIR`.
- Produces: stdout report; process exit 0 always.

OK detection: `L_STATUS_OK` is the literal `OK` in all seven language files. A step is OK iff its `steps[name]` value starts with `OK`. `[DRY-RUN] skipped` / `pominięty` are **not** OK (Gemini: "inaczej niż OK"). Trailing streak only.

`run_summary_latest.json` must be excluded or the last timestamp is duplicated.

- [ ] **Step 1: Failing tests against fixtures**

```python
class ChronicWarningsTests(unittest.TestCase):
    def test_trailing_internet_streak(self) -> None:
        sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))
        from chronic_warnings import find_chronic_streaks
        with tempfile.TemporaryDirectory() as tmp:
            steps = [
                {"internet": "OK completed"},
                {"internet": "Ostrzeżenie zakończono z ostrzeżeniami (niezweryfikowane)"},
                {"internet": "Ostrzeżenie zakończono z ostrzeżeniami (niezweryfikowane)"},
                {"internet": "Ostrzeżenie zakończono z ostrzeżeniami (niezweryfikowane)"},
            ]
            for i, st in enumerate(steps):
                p = Path(tmp) / f"run_summary_2026081{i}_101000.json"
                p.write_text(json.dumps({
                    "timestamp": f"2026-08-1{i}T08:00:00+00:00",
                    "steps": st,
                }), encoding="utf-8")
            (Path(tmp) / "run_summary_latest.json").write_text("{}", encoding="utf-8")
            hits = find_chronic_streaks(tmp, window=10, threshold=3)
            self.assertEqual(hits[0]["step"], "internet")
            self.assertEqual(hits[0]["streak"], 3)

    def test_wrapper_never_fails(self) -> None:
        out = subprocess.run(
            ["bash", str(REPO_ROOT / "scripts/report_chronic_warnings.sh")],
            capture_output=True, text=True,
            env={**os.environ, "MAC_UPDATE_LOGS_DIR": "/no/such"},
        )
        self.assertEqual(out.returncode, 0)
```

- [ ] **Step 2: Run — FAIL** (module missing)

- [ ] **Step 3: Implement `lib/python/chronic_warnings.py`**

```python
STEPS = ("prescan", "appstore", "npmcli", "brew", "internet", "postupdate", "system")

def is_ok(status: str) -> bool:
    return (status or "").startswith("OK")

def load_summaries(logs_dir: str, window: int) -> list[dict]:
    files = sorted(
        p for p in Path(logs_dir).glob("run_summary_*.json")
        if p.name != "run_summary_latest.json"
    )
    files = files[-window:]
    ...

def find_chronic_streaks(logs_dir, window=10, threshold=3) -> list[dict]:
    ...
```

`scripts/report_chronic_warnings.sh`:

```bash
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOGS="${MAC_UPDATE_LOGS_DIR:-$SCRIPT_DIR/logs}"
WINDOW="${MAC_UPDATE_CHRONIC_WINDOW:-10}"
THRESHOLD="${MAC_UPDATE_CHRONIC_THRESHOLD:-3}"
python3 - "$SCRIPT_DIR" "$LOGS" "$WINDOW" "$THRESHOLD" <<'PY' || true
...
PY
exit 0
```

The `|| true` plus final `exit 0` is the contract. Wire in `update_all.sh` **after** the `write_run_summary` python block (~line 2001), never as a condition of `OVERALL_EXIT`.

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Live August demonstration (Gemini verification)**

Default last-10 on this Mac **must print nothing** for internet (2026-09-02 is OK). To show the August series, copy `logs/run_summary_202608*.json` into a temp dir **without** 2026-09-02:

```bash
MAC_UPDATE_LOGS_DIR=/tmp/chronic-aug MAC_UPDATE_CHRONIC_WINDOW=20 MAC_UPDATE_CHRONIC_THRESHOLD=3 \
  bash scripts/report_chronic_warnings.sh
```

Paste stdout into the session notes. Also run against real `logs/` and paste that (expected: no chronic internet after v1.4.3).

---

### Task 5: `pending_after_run` in counts (Z3 / R3)

**Files:**
- Modify: `update_appstore.sh` (after `STILL_OUTDATED`)
- Modify: `update_brew.sh` (after `REMAINING_FORMULAE` / `REMAINING_CASKS` — those queries already exist)
- Modify: `lib/internet_app_updates.sh` (after final `mau_parse_pending` / `MAU_REMAINING`)
- Modify: `update_all.sh` postupdate heredoc — merge into `run_counts.json`
- Test: `tests/test_run_log_regressions_20260903.py`

**Interfaces:**
- Each child writes one integer file under `$MAC_UPDATE_SESSION_DIR/`: `pending_appstore`, `pending_brew_formulae`, `pending_brew_casks`, `pending_mau`.
- `update_all.sh` already loads `run_counts.json` with `int` values only — keep values ints.

Do **not** call `brew outdated` or `2>&1`. Reuse `brew_outdated_formulae` / `brew_outdated_casks` already assigned to `REMAINING_*`. App Store: count IDs from `STILL_OUTDATED` via `mas_outdated_ids`. MAU: line count of `MAU_REMAINING` / `mau_parse_pending` of the post-install list. If MAU CLI absent, write `0` and skip.

Helper in postupdate / `lib/python/run_summary.py`:

```python
def merge_pending(counts: dict, session_dir: str) -> dict:
    for key, filename in (
        ("pending_after_run_appstore", "pending_appstore"),
        ("pending_after_run_brew_formulae", "pending_brew_formulae"),
        ("pending_after_run_brew_casks", "pending_brew_casks"),
        ("pending_after_run_mau", "pending_mau"),
    ):
        path = os.path.join(session_dir, filename)
        try:
            counts[key] = int(Path(path).read_text().strip() or "0")
        except (OSError, ValueError):
            counts[key] = 0
    return counts
```

Write files with `printf '%s\n' "$n" > "$MAC_UPDATE_SESSION_DIR/pending_appstore"` guarded by `[ -n "$MAC_UPDATE_SESSION_DIR" ]`.

- [ ] **Step 1: Tests**

```python
def test_brew_pending_uses_lib_helpers_not_raw_outdated(self):
    text = (REPO_ROOT / "update_brew.sh").read_text()
    self.assertIn("pending_brew_formulae", text)
    self.assertIn("brew_outdated_formulae", text)
    self.assertNotRegex(text, r"brew outdated.*2>&1")
```

Plus a subprocess test: fake `STILL_OUTDATED` through `mas_outdated_ids` count.

- [ ] **Step 2–4: FAIL / implement / PASS**

No change to upgrade logic.

---

### Task 6: App Store three-way diag (Z4 / R4)

**Files:**
- Modify: `update_appstore.sh`
- Test: `tests/test_run_log_regressions_20260903.py`

**Fact:** `appstore_diag.txt` already gets TOR 1 retries, TOR 2 *failures*, and leftover `mas outdated`. TOR 2 **success** (`NO_UPDATES_FOUND`) is not written. 2026-09-03: mas listed WhatsApp pending, GUI said empty, after TOR 1 both agreed — that comparison was not recorded as one block.

- [ ] **Step 1: Test**

```python
def test_appstore_diag_records_three_tracks(self):
    text = (REPO_ROOT / "update_appstore.sh").read_text()
    self.assertIn("mas outdated before TRACK 1", text)
    self.assertIn("TRACK 2 AppleScript", text)
    self.assertIn("mas outdated after both tracks", text)
```

Also extract a `appstore_write_diag()` if needed and drive it via bash snippet with a temp `MAC_UPDATE_SESSION_DIR`.

- [ ] **Step 2–4:** After `NATIVE_OUTDATED` is captured, write section 1. After `AS_RESULT` is classified (including `no_updates`), write section 2 **always**, not only on failure. After `STILL_OUTDATED`, write section 3. **Do not change** TOR 1 IDs, retry-once, or TOR 2 branching.

---

### Task 7: Firefox cleanup (Z5 / R5–R6)

**Files:**
- Modify: `lib/internet_app_updates.sh` `iu_firefox_developer_edition` success/current messages
- Modify: gitignored `.mac_update_prefs` on this machine (delete the key)

**R5 decision: delete the key, do not wire as cache.** The stored value is `150.0b10` while installed is `156.0`. Using it as a fallback "latest" would compare against a stale channel. A cache is only safe if written on every successful API read; that is a new feature, not cleanup.

Reuse existing format strings. Pass `"$NEW_VER (kanał $LATEST_FF)"` as the version argument of `L_INTERNET_APP_UPDATED` / `L_INTERNET_APP_CURRENT`. No new i18n key.

- [ ] **Step 1: Tests**

```python
def test_firefox_updated_message_includes_channel_argument(self):
    text = (REPO_ROOT / "lib/internet_app_updates.sh").read_text()
    self.assertIn('"$NEW_VER (kanał $LATEST_FF)"', text)
    self.assertIn('"$VER (kanał $LATEST_FF)"', text)
```

- [ ] **Step 2–4:** Change the two `print_ok` / status lines in `iu_firefox_developer_edition`. Delete the prefs line on the live machine:

```bash
grep -v '^FIREFOX_DEV_CHANNEL_VERSION=' .mac_update_prefs > .mac_update_prefs.tmp && mv .mac_update_prefs.tmp .mac_update_prefs
```

Do not commit `.mac_update_prefs`.

---

### Task 8: Version, changelog, gates, live runs, handoff, git

**Files:** `VERSION`, `CHANGELOG.md`

CHANGELOG shape (copy v1.4.3): symptom → root cause → fix → measured evidence.

Must include Z0 (hang) and Z1–Z5. Mention: internet-step baseline 0 warnings / exit 0 must still hold.

- [ ] **Step 1: `VERSION` → `1.4.4`**
- [ ] **Step 2: CHANGELOG entry dated 2026-09-03**
- [ ] **Step 3: Static gates**

```bash
bash run_tests.sh
python3 -m unittest tests.test_safety_static.DevSyncPathSafetyTests -v
bash -n lib/proc.sh update_npm_cli.sh update_all.sh update_appstore.sh update_brew.sh \
  lib/internet_app_updates.sh scripts/report_chronic_warnings.sh
shellcheck -S error lib/proc.sh update_npm_cli.sh update_all.sh update_appstore.sh \
  update_brew.sh lib/internet_app_updates.sh scripts/report_chronic_warnings.sh
bash scripts/scan_secrets.sh
```

- [ ] **Step 4: Live runs (evidence)**

```bash
MAC_UPDATE_YES=1 bash update_internet_apps.sh
echo internet_exit=$?
bash update_all.sh --dry-run
echo dry_run_exit=$?
```

Paste exit codes and warning counts. Internet must stay **0 warnings, exit 0**. A hang in Claude during `update_all.sh --dry-run` is a bug: dry-run must not invoke `claude update`. Confirm `mac_update_dry_run_msg` still skips `update_npm_cli.sh` entirely.

Optional but strongly recommended after dry-run: one live `update_npm_cli.sh` (or full `update_all.sh` with the user present) to prove Claude no longer stalls past `native_installer_timeout`.

- [ ] **Step 5: Handoff** (vault CLI, not a hand-written file)

```bash
agentic handoff -p macos-updates "<one paragraph: v1.4.4 landed; Claude update path; chronic detector; pending counts; measured internet exit/warnings>"
```

- [ ] **Step 6: Git** — only when the user confirms this plan **and** the Gemini git sequence. Branch `fix/v1.4.4-observability`, commit, push branch, `merge --no-ff` to `main`, push `main`. Do not force-push. Do not skip hooks.

---

## Spec coverage checklist

| Requirement | Task |
|---|---|
| Z0 hang / other apps blocked / trusted source for Claude | 1, 2 |
| Z1 chronic detector + live August demo + no exit-code mutation | 4 |
| Z2 three guards + AGENTS.md rule 10 | 3 |
| Z3 pending_after_run via lib/brew.sh and mas/msupdate | 5 |
| Z4 three-way App Store diag, no decision change | 6 |
| Z5 delete prefs key + Firefox channel in message | 7 |
| tests, shellcheck, secrets, live internet 0/0, VERSION 1.4.4, CHANGELOG, handoff, git | 8 |
| Do not revert v1.4.3 MAU/TOR1/counts/IPMIView | all |
| R7 Spotify sudo stall | **out of scope** |

## Execution notes for the next session

- Work in `/Users/mk/Dev_Env/macOS_updates`, not the vault.
- `logs/` is gitignored; use the real directory for Z1 live proof.
- Today's hung run left Claude at **2.1.259** already. `claude update` should report current unless a newer build shipped.
- If `claude update` prompts on `/dev/tty`, do not add a timeout bump; keep SIGKILL and record `NIE WYKONANO` for a vendor non-interactive flag that does not exist (`claude install --help` has only `--force`).
