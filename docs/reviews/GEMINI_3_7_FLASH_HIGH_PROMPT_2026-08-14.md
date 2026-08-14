# Implementation Prompt — macOS_updates (for Gemini 3.7 Flash, high effort)

Paste everything below this line into Gemini 3.7 Flash (high reasoning effort), with the
repository `~/Dev_Env/macOS_updates` as working directory.

---

You are a senior macOS/Bash release engineer. Implement ALL fixes and improvements from
`docs/reviews/ULTRA_REVIEW_2026-08-14.md` in the repository at `~/Dev_Env/macOS_updates`.
Work with 95%+ confidence before each change; read the referenced files first. Do not invent
behavior — every claim in the review is verified against code and the run log
`logs/update_all_20260814_112225.log`.

## Non-negotiable constraints (from AGENTS.md — violating any of these is a failed task)

1. Bash 3.2 only: no `declare -A`, no `mapfile`, no `readarray`, no `${var,,}`.
2. `softwareupdate` must always keep `-R`; `mas upgrade` must always keep `sudo`.
3. All `update_*.sh` orchestrators: `set -o pipefail`, never `set -e`.
4. No hardcoded paths — use `SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"`.
5. Every method in `config/internet_app_methods.txt` must have a handler; the 4-way parity
   (internet_apps.txt ↔ internet_app_methods.txt ↔ dispatch order ↔ STATUS_* init/summary/exit
   loop) is enforced by `tests/test_safety_static.py` — keep it green.
6. Update pipeline Python lives in heredocs or importable pure-function modules under
   `lib/python/` (create this directory as part of task 8). No new standalone entrypoints.
7. Never call interactive `sudo` without a TTY. Severity contract: exit 0 = clean,
   10 = soft (must NOT defer the final macOS step), 1 = hard failure.
8. Public repo: nothing personal in tracked files; user-visible changes require updating all
   7 READMEs (en/pl/de/es/fr/it/pt) and CHANGELOG.md; bump VERSION appropriately (1.4.0).
9. Validate after every task: `bash -n <file>`, and at the end run `bash run_tests.sh`
   (all tests + shellcheck-clean at warning severity per `.shellcheckrc`).
10. Do NOT commit unless explicitly asked. Keep Ascendo removed (done 2026-08-14) — do not
    re-add it anywhere.

## Tasks, in this exact order

### P0-1 — Fix the dead cask downgrade guard (update_brew.sh:276)
Evidence: run log prints `update_brew.sh: line 276: app_version: command not found` (3×),
so `installed_ver` is always empty and the guard never runs.
- Move the canonical `app_version()` implementation (currently in `update_internet_apps.sh:356`,
  reads CFBundleShortVersionString → CFBundleVersion → mdls fallback) into `lib/version.sh`
  as the single shared definition. `lib/version.sh` currently has ~11 lines — extend it.
- Source `lib/version.sh` from `update_brew.sh` and `update_internet_apps.sh`; delete the
  duplicated local definition in `update_internet_apps.sh` (keep the localized
  `$L_INTERNET_VERSION_UNKNOWN` fallback working — pass a default when the i18n var is unset,
  because update_brew.sh loads i18n too, so it is available there).
- Verify `internet_version_relation` and `internet_msg` used at update_brew.sh:278-280 resolve
  in update_brew.sh's context; if not, source the library that defines them.
- Add a static test in `tests/test_safety_static.py`: for `update_brew.sh`, assert that every
  `$(function_name ...)` call it makes resolves to a function defined in the file itself or in
  a file it sources (at minimum, explicitly assert `app_version`, `internet_version_relation`,
  and `internet_msg` are defined in the sourced set). Model it on the existing source-analysis
  tests in that file.

### P1-2 — Fix `installed_apps_after.txt` semantics (update_all.sh:580)
The prescan (step 0) writes `installed_apps_after.txt` BEFORE any updates run (log evidence:
it contains pre-update versions like `Obsidian|1.13.6`). Fix:
- Rename the prescan output to `installed_apps_scan.txt` (update every consumer — grep the
  repo for `installed_apps_after`).
- In step 5 (inventory refresh), capture a fresh snapshot into `installed_apps_after.txt`
  using the same helper logic, AFTER steps 1–4 completed. Keep it in the session dir.
- Keep `--inventory-only` mode working (it copies before→after snapshots today).

### P1-3 — Remove deprecated `datetime.utcnow()` (lib/internet_apps.sh:91,104)
Replace with `datetime.datetime.now(datetime.timezone.utc)`. The TSV timestamps parsed with
`strptime(.., "%Y-%m-%d %H:%M:%S")` are naive — make the comparison consistent (either strip
tzinfo after `now(...)` or attach UTC to parsed values). Zero DeprecationWarnings in a dry run.

### P1-4 — Inventory exclusion mechanism (the Ascendo case)
`SKIP_DISCOVERY_APPS` is hardcoded (`update_all.sh:495`), so an installed app removed from
APPLICATIONS.md gets re-added by the prescan as "🆕 do skategoryzowania".
- Add `config/inventory_exclusions.txt` (one app name per line, `#` comments), loaded by the
  prescan heredoc into `SKIP_DISCOVERY_APPS` (and by `migration_setup.sh`'s copy — grep for
  the second SKIP_DISCOVERY_APPS occurrence).
- Seed it with `Ascendo` and a comment header explaining semantics (excluded from discovery
  AND from the update pipeline; the app may still appear in APPLICATIONS.md as documentation).
- Document in `docs/agents/scripts.md` (adding/removing apps section) and README(s).
- Add a static test: every non-comment line in the exclusions file is non-empty and unique.

### P1-5 — `--verify-only` mode
Add a flag to `update_all.sh` (wire through `lib/cli.sh` like existing `--skip-*`/`--dry-run`
flags) that: skips all mutations, captures current internet-app + brew + mas versions, compares
against the most recent `logs/version_history.tsv` entries, and prints a verification table
(updated / unchanged / still-outdated). Purpose: run 10–15 min after a normal run to confirm
the `silent_launch` "launched (unverified)" apps actually landed. Exit 0/10 per contract.
Reuse `internet_capture_versions`; no new Python entrypoints.

### P2-6 — Optional gated MAU remediation
The run log shows Office 16.112 blocked by `DeferralDays.*=7` and MAU channel `Preview`.
In the msupdate handler (lib/internet_app_updates.sh, `iu_microsoft_365`): when deferrals are
detected AND `MAC_UPDATE_MAU_CLEAR_DEFERRALS=1` is set, delete the deferral keys via
`defaults delete com.microsoft.autoupdate2 <key>` (loop over detected keys only), re-run
`msupdate --list`, and report before/after. Default remains report-only. Never touch the
channel automatically — keep the existing advisory message. Document the env var in
docs/agents/critical_rules.md and READMEs.

### P2-7 — Machine-readable run report + notification
- At the end of `update_all.sh`, write `logs/run_summary_<timestamp>.json` (via a heredoc or
  a new `lib/python/run_summary.py` pure function): step names, result strings, exit class,
  duration, counts (formulae/casks/CLI/version changes). Compose the JSON with Python
  (`json.dumps`), never string concatenation in bash.
- After writing it, if `MAC_UPDATE_NOTIFY=1`, send a macOS notification via
  `osascript -e 'display notification ...'` summarizing the run (guard with `command -v osascript`).

### P2-8 — Extract prescan Python to `lib/python/`
Create `lib/python/` with importable, pure-function modules (e.g. `inventory.py` holding the
prescan parsing/merging logic currently inlined in update_all.sh's giant heredoc). The heredoc
becomes a thin driver that imports from `lib/python/` (invoke as
`python3 - "$SCRIPT_DIR" ... <<'PYEOF'` with `sys.path.insert(0, script_dir + '/lib/python')`).
Extend `run_tests.sh` so it py_compiles `lib/python/*.py` (its README says it already compiles
tested modules — verify and adjust the glob) and add unit tests for at least: `norm_name`,
`row_exists`, alias handling, and the exclusions loading from P1-4. Do this incrementally and
re-run the full suite after each extraction. Do NOT change behavior — pure refactor.

### P2-9 — Repo hygiene
- Move `git_history_archive.md` (7.5 MB) out of the repo root: `git rm --cached` if tracked,
  add to `.gitignore`, and relocate the file into `scratch/` (gitignored) — verify with
  `git ls-files` first.
- Ensure `.DS_Store` is gitignored and untracked.
- Do not touch `dev_sync_logs/` or `graphify-out/` contents beyond confirming they are ignored.

### P3-10 — Snapshot source consistency
Make the prescan's `installed_app_version()` (update_all.sh:556) use the same read order as
`app_version()` in lib/version.sh (defaults CFBundleShortVersionString → CFBundleVersion →
mdls). After P0-1 the logic exists in one place — reuse it via the P2-8 module or mirror the
order exactly and add a comment cross-referencing lib/version.sh.

## Acceptance checklist (run and paste results)

1. `bash -n` on every modified script — clean.
2. `bash run_tests.sh` — all green (including the new tests).
3. `bash update_all.sh --dry-run` — no `app_version: command not found`, no
   DeprecationWarnings, exclusions honored, run summary JSON written.
4. `bash update_all.sh --verify-only` — produces the verification table and exits 0 or 10.
5. `shellcheck --severity=warning` clean on modified files.
6. All 7 READMEs + CHANGELOG.md updated; VERSION bumped to 1.4.0.
7. `git status` shows only intended changes; nothing committed.

Report at the end: files changed, tests added, and any deviation from this plan with
justification. If a task cannot be completed safely under the constraints, stop that task,
leave the code untouched, and explain why — do not ship a partial mutation.
