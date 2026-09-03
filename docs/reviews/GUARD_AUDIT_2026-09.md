# Guard audit — self-suppressing diagnostic input (Z2)

**Date:** 2026-09-03  
**Scope:** v1.4.4 observability / Ultra Review R1  
**Reference:** `docs/reviews/GEMINI_TASK_2026-09-02.md` (Z2), Office `DeferralDays` deadlock 2026-07-14 → 2026-09-01

Three guards reviewed for the defect class where a mechanism hides the evidence it needs to release itself. For each guard the three Gemini questions are answered from measured code.

---

## 1. Cask downgrade guard (`update_brew.sh`)

**Location:** ```239:311:update_brew.sh```

Before upgrading outdated casks, the script re-fetches `brew info --json=v2 --cask` per cask, reads Homebrew's recorded install version and the bundle via `app_version`, and compares with `internet_version_relation` / `app_vs_package_version_relation`. Casks that would downgrade are skipped for this run only (`continue`); survivors accumulate in `UPGRADEABLE_CASKS` for `brew upgrade --cask`.

### Q1. Does this guard hide the data on which it decides?

**No.** The skip is in-memory for the current run. Nothing is written to prefs, quarantine files, or logs that would suppress a future `brew info` or bundle read. Warnings are printed (`print_warn` / `print_info`); diagnostic input remains available on the next invocation.

### Q2. If yes — what would have to happen to release it, and is that event observable while the guard is active?

**N/A (Q1 is no).** Release is re-decision on the next run: when Homebrew publishes a cask version that is not a downgrade relative to the installed app, `app_vs_package_version_relation` returns something other than `newer` and the cask enters `UPGRADEABLE_CASKS`. That newer cask version is observable every run via fresh `brew info --json=v2`.

### Q3. If not observable — add a lifetime and path to re-evaluation?

**N/A.** No TTL required.

**Verdict:** **Passes.** No code change. Passes because downgrade detection re-reads live Homebrew JSON and bundle versions every run; skip is per-run only; the release event (a newer cask formula) remains observable while the guard is armed.

---

## 2. `vendor_latest` (`lib/internet_handlers.sh`)

**Location:** `internet_handler_vendor_latest` at ```286:366:lib/internet_handlers.sh```

Each invocation reads the local bundle (`app_version`), discovers a feed (Sparkle `SUFeedURL`, electron-updater `latest-mac.yml` / `latest.yml`, or `feed_url_override`), fetches it with `curl`, and compares via `internet_version_relation`. On unreadable feed it logs and sets `INTERNET_LAST_STATUS`; it still launches the app hidden for the vendor's own updater. No feed body, remote version, or "already checked" flag is persisted across runs.

### Q1. Does this guard hide the data on which it decides?

**No.** Feed URLs come from the app bundle or config override; remote content is fetched anew each run. A miss degrades to launch-unverified (`INTERNET_LAST_VERIFIED=0`, status unknown) — it does not cache "no update" in a way that blocks the next fetch.

### Q2. If yes — what would have to happen to release it, and is that event observable while the guard is active?

**N/A (Q1 is no).** Release is a successful fetch returning a `remote_ver` that compares as `newer` than `local_ver`. That feed response is requested on every run regardless of prior outcome.

### Q3. If not observable — add a lifetime and path to re-evaluation?

**N/A.** No TTL required.

**Verdict:** **Passes.** No code change. Passes because the vendor feed is fetched every run, failures do not persist hidden state, and the next run retries discovery and curl from scratch.

---

## 3. npm skip filters (`update_npm_cli.sh`)

Three related mechanisms, all re-evaluated from live system state each run.

### 3a. `resolve_command_path` — ```362:408:update_npm_cli.sh```

Resolves CLI binaries from known install prefixes (`N_PREFIX`, `LOCAL_BIN`, `NPM_GLOBAL_BIN`, `BUN_BIN`) then falls back to `command -v`. No cached path survives the process.

### 3b. Skip-if-not-installed — ```912:914:update_npm_cli.sh```

When `resolve_command_path` fails, the manifest entry is skipped with `print_info` (`"${display_name} nie jest zainstalowany — pomijam"`). No "removed from manifest" or persistent skip list.

### 3c. `remove_legacy_brew_formulas` — ```932:967:update_npm_cli.sh```

For `opencode`, `bun`, `node`: checks `brew list --formula` and live `command -v` against `brew --prefix` every run before uninstalling a legacy Homebrew formula. Skip path prints a warn when the active command still points at Homebrew.

### Q1. Does this guard hide the data on which it decides?

**No.** PATH preference, presence, and brew-vs-native resolution use live `command -v`, `-x` checks, and `brew list` each run. Skipping an absent CLI does not record "never check again."

### Q2. If yes — what would have to happen to release it, and is that event observable while the guard is active?

**N/A (Q1 is no).** Release is installation of the binary (or relocation off Homebrew prefix): the next run's `resolve_command_path` / `command -v` sees it immediately.

### Q3. If not observable — add a lifetime and path to re-evaluation?

**N/A.** No TTL required — re-evaluation is implicit every run from live PATH and brew list.

**Verdict:** **Passes.** No code change. Passes because all three filters consult live filesystem and PATH every invocation; nothing persisted hides future diagnostic input.

---

## Summary

| Guard | Hides input? | Release observable? | TTL needed? | Action |
|-------|--------------|---------------------|-------------|--------|
| Cask downgrade | No | Yes (next `brew info`) | No | None |
| `vendor_latest` | No | Yes (next feed fetch) | No | None |
| npm skip filters | No | Yes (next PATH/brew check) | No | None |

All three pass. **AGENTS.md rule 10** is added anyway as a non-negotiable guardrail for future mechanisms (pattern: `mau_quarantine_expired_ids`).
