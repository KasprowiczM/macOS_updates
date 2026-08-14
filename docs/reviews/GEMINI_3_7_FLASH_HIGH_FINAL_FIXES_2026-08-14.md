# Final Fixes Prompt — macOS_updates post-Gemini verification (2026-08-14)

Paste this into Gemini 3.7 Flash high effort with working directory `~/Dev_Env/macOS_updates`.

---

You are finishing the Gemini implementation from `docs/reviews/GEMINI_3_7_FLASH_HIGH_PROMPT_2026-08-14.md`.
Most requested features appear implemented: `VERSION=1.4.0`, `lib/version.sh` now owns
`app_version()` and `internet_version_relation()`, `lib/python/inventory.py` and
`run_summary.py` exist, `config/inventory_exclusions.txt` exists with `Ascendo`, `--verify-only`
is wired, `datetime.utcnow()` is gone from production code, MAU remediation is gated, and
`git_history_archive.md` moved to `scratch/`.

However, verification found final regressions. Fix ONLY these issues, then stop.

## Non-negotiable rules

- Bash 3.2 only; no `declare -A`, `mapfile`, `readarray`.
- Keep `softwareupdate -ia -R` and `sudo mas upgrade`.
- `update_*.sh` scripts must keep `set -o pipefail` and must not use `set -e`.
- Do not re-add Ascendo to the update pipeline.
- Do not commit.
- Run `bash run_tests.sh` at the end; it must pass.

## 1. P0 — Fix `run_tests.sh` timeout regression in `update_all.sh`

Current result of `bash run_tests.sh`:

- exit code 1
- `157 tests ran, 11 errors`
- all 11 are `subprocess.TimeoutExpired` in `tests/test_safety_static.py`
- failing helper: `run_update_all_with_layer_exit(...)`
- repeated symptom: sandboxed `update_all.sh --yes --skip-prescan --skip-postupdate ...`
  times out after 20 seconds.

Root cause from `bash -x` reproduction:

- `update_all.sh` starts the sudo keepalive loop:
  `( while true; do sudo -n true 2>/dev/null || exit 0; sleep 50; done ) &`
- `cleanup_session_dir()` runs `kill "$SUDO_KEEPALIVE_PID"; wait "$SUDO_KEEPALIVE_PID"`
- if the keepalive subshell is inside `sleep 50`, cleanup can block until the sleep exits,
  causing the 20s unit-test timeout.

Fix the keepalive so cleanup exits immediately and leaves no orphaned `sleep`.
Use a Bash 3.2-safe pattern like:

```bash
(
    _macupd_sleep_pid=""
    trap '[ -n "$_macupd_sleep_pid" ] && kill "$_macupd_sleep_pid" 2>/dev/null; exit 0' INT TERM
    while true; do
        sudo -n true 2>/dev/null || exit 0
        sleep 50 &
        _macupd_sleep_pid=$!
        wait "$_macupd_sleep_pid" 2>/dev/null || exit 0
    done
) &
SUDO_KEEPALIVE_PID=$!
```

Also add/adjust a static test proving the keepalive trap kills its child sleep, or add a
targeted regression test that the layer-exit helper completes under the existing 20s timeout.
Do not simply increase the timeout. Do not disable the keepalive globally.

## 2. P1 — Notification behavior is too broad

The original prompt requested a notification only when `MAC_UPDATE_NOTIFY=1`.
Current code sends one when either `MAC_UPDATE_NOTIFY=1` OR `MAC_UPDATE_NONINTERACTIVE=1`:

```bash
if [ "${MAC_UPDATE_NOTIFY:-0}" = "1" ] || [ "${MAC_UPDATE_NONINTERACTIVE:-0}" = "1" ]; then
```

Fix it to notify only when explicitly requested:

```bash
if [ "${MAC_UPDATE_NOTIFY:-0}" = "1" ]; then
```

Scheduled/noninteractive runs should not show GUI notifications unless the user opted in.
Add or update a static test for this exact condition.

## 3. P1 — Make run summary filenames readable and deterministic

`update_all.sh` uses:

```python
ts_str = os.environ.get("RUN_TIMESTAMP") or str(start_time)
```

but spot-checking found no `RUN_TIMESTAMP` definition. This makes JSON filenames fall back to
epoch seconds, while logs use `LOG_TS=YYYYMMDD_HHMMSS`.

Fix by exporting:

```bash
export RUN_TIMESTAMP="$LOG_TS"
```

before the final summary writer runs. Keep `run_summary_latest.json`.
Add a static test that `RUN_TIMESTAMP="$LOG_TS"` exists and is used by the JSON summary writer.

## 4. P2 — Triage unrelated/untracked review files before final handoff

`git status --porcelain` showed untracked old review files:

- `docs/reviews/Opus5_Max_Implementation_Prompt_v6.md`
- `docs/reviews/Opus5_Max_Ultra_Review_v6.md`

Do not silently include them in the final change set unless they are intentionally part of the
release. Either:

- leave them explicitly untracked and mention them in the final report, or
- move/archive them only if they are generated artifacts and that is already the repo convention.

Do not delete them without explicit user approval.

## Acceptance commands

Run these and paste exact results:

```bash
bash -n update_all.sh update_brew.sh update_internet_apps.sh lib/version.sh
python3 -m pytest tests/test_safety_static.py -q
bash run_tests.sh
MAC_UPDATE_NO_SUDO_KEEPALIVE=1 bash update_all.sh --dry-run
MAC_UPDATE_NO_SUDO_KEEPALIVE=1 bash update_all.sh --verify-only
```

Expected:

- no `TimeoutExpired`
- `bash run_tests.sh` passes
- no `app_version: command not found`
- no `datetime.utcnow()` deprecation warnings
- no notification unless `MAC_UPDATE_NOTIFY=1`
- `logs/run_summary_latest.json` exists and the timestamped JSON filename uses `YYYYMMDD_HHMMSS`

Final response: list files changed, tests added/updated, command outputs, and remaining untracked
files. Do not commit.
