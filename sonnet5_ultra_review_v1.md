# 🍎 Ultra Review & Diagnostic Report — macOS Updates (Sonnet 5)

**Date:** 2026-07-06 · **Reviewer:** Claude (Sonnet 5, xhigh effort) + a 25-agent review workflow (find → adversarially verify) · **Project:** v1.0.19
**Scope:** diagnose the last run + a 5-day recurring failure, run a 9-dimension review of the entire codebase with adversarial verification, fix everything confirmed real, re-run the full test suite + shellcheck, and assess production readiness.
**Branch:** `review/sonnet5-ultra-review-2026-07-06` (merged to `main` at the end of this session).

---

## 1. Executive summary

The project is in good shape. The June 20, 2026 ultra-review's entire backlog (S1–S12, P1–P8 — unconditional success reporting, `cp -R` vs `ditto`, the `tr -d 'v'` bug, missing `User-Agent`, Docker flags, `hdiutil -nobrowse`, non-atomic JSON writes, missing `pipefail`, unpinned GitHub Actions, the global `SC2086` shellcheck disable, `uninstall.sh` path safety) has been fixed in the two commits since then. That is confirmed by direct reading of the current code, not by trusting the old report.

This review found and fixed **one currently-live production bug** (Ledger Wallet has failed to update every single day for 5 days running), **one silent status-reporting bug** (Docker Desktop misreports itself as "current" when it simply isn't running), **two non-atomic config writes**, and **five stale documentation facts**. It also found and fixed a **harness configuration bug** that was breaking every subagent spawned in this project — discovered the hard way, when it broke this review's own first attempt.

Three additional findings raised by the automated review pipeline turned out to be **false positives** on manual re-verification against live data — reported honestly below, because a review that only reports what it found and not what it disproved isn't trustworthy.

**Bottom line: production-ready**, with one governance item that needs your attention (see §5) because the harness blocked me from fixing it myself.

---

## 2. Today's failure, and why it's been happening for 5 days

`update_all.sh` has ended with **"UPDATE COMPLETED WITH ERRORS"** at Step 5 (Internet apps) in *every run since 2026-07-02* (07-02, 07-03, 07-04, 07-05, 07-06 — 5 for 5). Before that, 06-27 through 06-30 were clean. Something changed around July 1–2.

**Root cause:** Ledger released Wallet 4.10.0 around that date. `iu_ledger()` in `lib/internet_app_updates.sh` fetches `https://download.live.ledger.com/latest-mac.yml`, which lists **two** downloadable assets per release:

```yaml
files:
  - url: ledger-live-desktop-4.10.0-mac.zip
  - url: ledger-live-desktop-4.10.0-mac.dmg
path: ledger-live-desktop-4.10.0-mac.zip   # electron-builder's default "path" is the .zip
```

The old parser (`grep "^  *- url:" | head -1`) matched **both** `url:` lines and took the first — the **.zip**, not the **.dmg**. The script downloaded the zip, then ran `hdiutil verify` on it (a DMG-only check), which correctly fails on a zip. Hence, every day: *"Pobieranie lub weryfikacja DMG nie powiodła się"* ("DMG download or verification failed").

**Fix applied** (`lib/internet_app_updates.sh:1076`): the grep now filters to `.dmg` URLs specifically:

```diff
- LEDGER_DMG_FILE=$(echo "$LEDGER_YML" | grep "^  *- url:" | head -1 | sed 's|.*url: *||' | tr -d '[:space:]')
+ LEDGER_DMG_FILE=$(echo "$LEDGER_YML" | grep "^  *- url:.*\.dmg" | head -1 | sed 's|.*url: *||' | tr -d '[:space:]')
```

**Verified against live production data**, not just logic:
```
$ curl -s https://download.live.ledger.com/latest-mac.yml | grep 'url:'
  - url: ledger-live-desktop-4.10.0-mac.zip
  - url: ledger-live-desktop-4.10.0-mac.dmg

Old parser  → ledger-live-desktop-4.10.0-mac.zip   (wrong asset)
New parser  → ledger-live-desktop-4.10.0-mac.dmg    (correct asset)
HEAD https://download.live.ledger.com/ledger-live-desktop-4.10.0-mac.dmg
  → HTTP/2 200, content-type: application/x-apple-diskimage   ✅
```
Ledger Wallet will update cleanly on the next run.

---

## 3. Harness bug: every subagent in this project was broken

While standing up the review workflow for this report, all 10 of its first-attempt subagents failed identically:

> *"There's an issue with the selected model (claude-haiku-4-6). It may not exist or you may not have access to it."*

**Root cause:** `.claude/settings.json` sets `CLAUDE_CODE_SUBAGENT_MODEL=claude-haiku-4-6` — not a real model ID (the actual Haiku 4.5 ID is `claude-haiku-4-5-20251001`). Every `Task`/subagent spawned in this project — the review workflow, `/mac-update-*` skills, anything using the documented "Worker" tier — was silently broken by this. The same wrong ID was written into `CLAUDE.md`, `AGENTS.md`, and `.claude/agents/worker-haiku.md`.

**Fixed:**
- `.claude/settings.json` → `CLAUDE_CODE_SUBAGENT_MODEL=claude-haiku-4-5-20251001`
- `CLAUDE.md`, `AGENTS.md` → Model Hierarchy table corrected

**Not fixed — needs your action:** `.claude/agents/worker-haiku.md` (`model: claude-haiku-4-6`) and `.claude/agents/advisor.md` (a separate, stale "16 phases" doc reference — see §4) are under Claude Code's own self-modification protection: editing `.claude/agents/*` without an explicit user request is blocked by the auto-mode classifier, on purpose. I did not attempt to work around this. **Please update `model: claude-haiku-4-6` to `model: claude-haiku-4-5-20251001` in `.claude/agents/worker-haiku.md` yourself** (one line) — until then, directly invoking the `worker-haiku` agent by name will still fail, even though the `CLAUDE_CODE_SUBAGENT_MODEL` env var fix resolves the default-subagent path.

---

## 4. Full findings table

Nine review dimensions ran in parallel (browsers/AI/VPN/mail/cloud handlers; MS365/dev-tools/multimedia handlers; crypto/IT-infra/iOS handlers + registry/dispatch; core orchestrators; npm/brew/setup/migration scripts; Python `dev_sync` backend; i18n/tests/CI; docs consistency; security/supply-chain). Every finding was then re-verified by an independent adversarial agent instructed to try to refute it — and for anything load-bearing, I re-verified a third time myself by reading the code or testing live.

### Fixed this session

| # | Severity | File:line | Problem | Status |
|---|----------|-----------|---------|--------|
| 1 | 🔴 Critical | `lib/internet_app_updates.sh:1076` | Ledger handler downloads `.zip` instead of `.dmg`, fails `hdiutil verify` every run since 2026-07-02 | ✅ Fixed, verified live |
| 2 | 🟠 High | `.claude/settings.json`, `CLAUDE.md`, `AGENTS.md` | `CLAUDE_CODE_SUBAGENT_MODEL`/docs pointed at invalid model `claude-haiku-4-6`, breaking all subagent spawns | ✅ Fixed (partially — see §3) |
| 3 | 🟠 High | `lib/internet_app_updates.sh:876` | Docker Desktop: `--check-only` fails for *any* reason (not running, daemon down, no network) but the handler reports `STATUS_DOCKER=CURRENT` regardless — empirically confirmed: Docker Desktop wasn't running on this Mac during the review, and the unpatched code would have reported "current" | ✅ Fixed — now checks `docker desktop status` first; treats "not running" like the no-CLI case (launches the app) instead of misreporting current |
| 4 | 🟠 High | `scratch/add_mcp.py:52` | Non-atomic write to `~/.claude.json` (no backup, no atomic swap) — violates the project's own documented config-write standard | ✅ Fixed — atomic tmp+`os.replace()` + `.bak`, matching `scripts/fix_mcp_configs.py` |
| 5 | 🟡 Medium | `dev_sync/dev_sync_prune_excluded.py:244` | Cleanup-plan JSON written directly via `write_text()`, no atomic guarantee — a crash mid-write corrupts the plan `--apply-plan` later reads | ✅ Fixed — atomic tmp+`os.replace()`, matching `dev_sync_core.py`'s `write_json()` |
| 6 | 🟡 Low (doc) | `CONTRIBUTING.md:14`, `docs/PUBLIC_RELEASE.md:18` | Both say "56 unittest"; actual count is 62 | ✅ Fixed |
| 7 | 🟡 Low (doc) | `CLAUDE.md:10`, `AGENTS.md:10` | Both say "all 6 steps"; `update_all.sh` runs 7 (steps 0–6, matching `README.md`'s correct "seven steps") | ✅ Fixed |
| 8 | 🟡 Low (doc) | `docs/agents/scripts.md`, `CLAUDE.md`, `AGENTS.md` | "16 phases" for `migration_setup.sh` omits Phase 0a (language) and 0b (cloud provider) which the script actually runs first — 18 phases total | ✅ Fixed in the two editable files; `.claude/agents/advisor.md` still says "16 phases" — blocked by self-modification protection, same as §3 |

### Confirmed but left as a backlog decision, not a same-session fix

| # | Severity | File | Problem | Why not fixed now |
|---|----------|------|---------|---------------------|
| 9 | 🟡 Med (architecture) | `lib/internet_registry.sh`, `lib/internet_handlers.sh` (`internet_dispatch_silent_launch`, `internet_handler_set_status`) | The method-registry / generic-dispatch-helper infrastructure is not consulted by the live dispatch path (`config/internet_dispatch_order.txt` + direct handler calls in `lib/internet_app_updates.sh` is the real path). `config/internet_app_methods.txt` is used only by `scripts/report_update_coverage.sh` for the coverage report, not at update time. | This is real architectural drift, but it's covered by dedicated unit tests (`tests/test_safety_static.py`) and referenced in the documented "Adding a New Internet App" 8-step process (`docs/agents/scripts.md`) — it looks like scaffolding kept for a future handler-generalization pass, not accidental dead code. Removing it is a real decision (rewrite the onboarding doc + `scaffold_internet_app.sh`, or finish wiring it in) that deserves your sign-off, not a same-session deletion. **Recommendation:** pick one — either wire `internet_registry_method_for()` into `iu_dispatch_run_all()` so the method column is enforced, or drop the registry/config file and simplify the onboarding doc to match what's actually used today. |

### False positives — found by the automated pipeline, disproven by manual re-verification

Reporting these because a review that hides its own pipeline's mistakes isn't one you can trust:

| Claim | Automated verdict | My manual verdict | Evidence |
|---|---|---|---|
| "Ledger URL is double-prefixed with the base URL, producing a malformed `https://.../https://...` download link" | ✅ Confirmed real (high confidence) | ❌ **False** | Fetched the live `latest-mac.yml`: the `url:` fields are bare filenames (`ledger-live-desktop-4.10.0-mac.dmg`), never full URLs. No double-prefixing is possible. The verifier agent traced the *logic* correctly but never fetched the real YAML to check its premise. |
| "`internet_handler_set_status()`'s `eval` is exploitable via the VALUE argument (backticks/`$()`)" | ✅ Confirmed real (high confidence, verifier claimed to have tested it) | ❌ **False** | Ran the actual function in bash with `value='$(whoami)'`, `` value='`id`' ``, and `value='; echo INJECTED'` — in all three cases the literal string was assigned, nothing executed. The double-quoted `eval "${var_name}=\"\${value}\""` pattern is a well-known *safe* idiom for exactly this reason (parameter expansion runs once, and the expanded value is never re-parsed as source). The var-name allowlist was already sufficient; there was no second gap to close. |
| Docker Desktop should explicitly set `STATUS_DOCKER` when the app isn't installed (like it does in every other branch) | ❌ Correctly rejected | (agrees) | 28+ other handlers rely on the same pre-initialized `SKIPPED` default; this is the established, correct pattern, not an inconsistency. |
| `update_brew.sh`/`setup.sh`/`migration_setup.sh` use `&>/dev/null`, which is "bash 4.0+ only" and violates the bash 3.2 requirement | ❌ Correctly rejected | (agrees) | Tested directly: `bash -c 'echo &>/dev/null'` on this Mac's bash 3.2.57 works fine. `&>` has been supported since early bash 3.x; the claim was simply wrong. |
| `dev_sync/provider_setup.sh`'s heredoc allows command injection via `$(id)` in a user-typed path | ❌ Correctly rejected | (agrees) | The sanitizer already strips backslashes/quotes and the heredoc is never re-evaluated by `eval`; a literal `$(id)` lands in the JSON as text, unexecuted. |

Two dimensions came back completely clean: **core orchestrators** (`update_all.sh`, `update_internet_apps.sh`, `update_system.sh`, `update_appstore.sh` — all non-negotiables re-verified: `-R`, `sudo mas`, `pipefail`, mktemp, cleanup traps) and **security/supply-chain** (no unpinned actions, no stray `sudo`, no unverified installs). **i18n/tests/CI** also came back clean — key parity across all 7 language packs holds, and `run_tests.sh` matches its own header claims.

---

## 5. What you need to do

1. **Edit `.claude/agents/worker-haiku.md`** — change `model: claude-haiku-4-6` to `model: claude-haiku-4-5-20251001`. I couldn't do this myself; Claude Code's self-modification guard blocks edits to `.claude/agents/*` without your explicit say-so, by design.
2. **Optionally fix `.claude/agents/advisor.md`** — "Migration setup (16 phases)" → "phases 0a–16" (cosmetic, same file-protection reason).
3. **Decide on the dead-registry question (finding #9 above)** — wire it in or retire it; either is fine, but it's a call for you, not me.

---

## 6. Verification performed

```
bash run_tests.sh
  1/4  bash -n on all .sh                → all bash scripts parse       ✅
  2/4  python3 -m py_compile on all .py  → all python modules compile   ✅
  3/4  python3 -m unittest discover      → Ran 62 tests — OK            ✅
  4/4  scripts/scan_secrets.sh (gitleaks)→ no leaks found               ✅

shellcheck --severity=warning (49 scripts, matches .github/workflows/ci.yml exactly)
  → 0 warnings                                                          ✅
```

All fixes were re-tested after the change, not just before. The Ledger and Docker Desktop fixes were additionally validated against live external state (Ledger's real `latest-mac.yml`, this Mac's actual Docker Desktop process state), not just static reasoning.

## 7. Review process notes (for whoever runs the next one)

- The review workflow's first attempt spawned 10 subagents that all failed instantly (§3) — worth checking `.claude/settings.json`'s `CLAUDE_CODE_SUBAGENT_MODEL` before assuming a workflow's agents are broken.
- One workflow agent (briefed for diagnosis only) went ahead and edited `lib/internet_app_updates.sh` directly instead of just returning a proposed fix — caught via `git status` before trusting anything, and the edit itself turned out to be correct on manual verification, but subagents should not be assumed read-only just because their brief says so. Check tool access explicitly if research-only behavior is required.
- Three "confirmed" findings out of 15 were wrong despite passing independent adversarial verification (§4's false-positive table) — a 20% miss rate for this pipeline on this run. Spot-checking high-confidence claims against live/executable ground truth (not just re-reading the same static code) is what caught all three; a purely textual re-verification would have missed them too.
