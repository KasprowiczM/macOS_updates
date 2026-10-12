# Development records (`docs/reviews/`)

Everything in this directory is a **development record**, not product documentation and not part of the shipped toolkit: audit trails, code-review findings, implementation briefs for AI coding agents and the reports written while findings were fixed. Nothing here is loaded at runtime and nothing here is authoritative. When a record disagrees with the code, the code wins.

| Topic | Authoritative source |
|-------|----------------------|
| What shipped in each release | [`CHANGELOG.md`](../../CHANGELOG.md) |
| Current version | [`VERSION`](../../VERSION) |
| End-user documentation | [`../user/`](../user/INDEX.md) |
| Developer / AI-agent reference | [`../agents/`](../agents/scripts.md) |

## Layout

- **This directory** holds the records of the current release line (v1.5.3 to v1.5.5): the ones still cited by the changelog and the acceptance checklist.
- **[`archive/`](archive/)** holds everything superseded, kept for provenance and never edited except for link paths and privacy redaction. Briefs and reports there describe work that has already shipped.
- Record types: **review** (read-only audit of code and/or a run log), **prompt** (task brief handed to an AI agent), **report** (what an agent changed), **run-log** (analysis of a live `update_all.sh` run and the fixes it caused).
- Naming: `ULTRA_REVIEW_*` / `*_ultra_review_*` are reviews, `*_PROMPT_*` / `*_prompt_*` / `GEMINI_TASK_*` are briefs, `IMPLEMENTATION_*` / `FIX_REPORT_*` are reports, `RUN_LOG_FOLLOWUP_*` are run-log follow-ups. Suffixes `vN` are successive passes of one series.

## Current records

| Date | File | Author / model | Type | Version | Summary |
|------|------|----------------|------|---------|---------|
| 2026-10-05 | [`ULTRA_REVIEW_2026-10-05_v153.md`](ULTRA_REVIEW_2026-10-05_v153.md) | not stated | review | v1.5.3 | Update-reliability review and release plan (vendor-truth ChatGPT/Proton, native-CLI-first ordering, bundle-swap protection). |
| 2026-10-05 | [`RUN_LOG_FOLLOWUP_2026-10-05_v154.md`](RUN_LOG_FOLLOWUP_2026-10-05_v154.md) | not stated | run-log | v1.5.4 | Follow-up on the first live v1.5.3 run: stale manufacturer feeds become warnings, summary wording. |
| 2026-10-11 | [`RUN_LOG_FOLLOWUP_2026-10-11_v155.md`](RUN_LOG_FOLLOWUP_2026-10-11_v155.md) | not stated | run-log | v1.5.5 | Follow-up on the 2026-10-11 live run: stale `python3` command hash, non-blocking step 5, honest summaries (F1-F6). |

## Archive (chronological)

| Date | File | Author / model | Type | Version | Summary |
|------|------|----------------|------|---------|---------|
| 2026-06-20 | [`ULTRA_REVIEW_2026-06-20.md`](archive/ULTRA_REVIEW_2026-06-20.md) | Claude (Opus) + 2 audit subagents | review | v1.0.19 | Full review plus diagnosis of a live macOS 26.5.1 run log. |
| 2026-07-06 | [`sonnet5_ultra_review_v1.md`](archive/sonnet5_ultra_review_v1.md) | Claude Sonnet 5 (xhigh), 25-agent find/verify workflow | review | v1.0.19 | Recurring-failure diagnosis, 9-dimension review with adversarial verification, fixes applied. |
| 2026-07-13 | [`ULTRA_REVIEW_2026-07-13.md`](archive/ULTRA_REVIEW_2026-07-13.md) | not stated | review | pre-v1.0.21 | Production review of the orchestrator, update layers, registry, first-run setup, `dev_sync` and tests. |
| 2026-08-05 | [`ULTRA_REVIEW_2026-08-05.md`](archive/ULTRA_REVIEW_2026-08-05.md) | Claude (Opus) | review | v1.0.21 | Baseline review that opened the v1.1.0 hardening round. |
| 2026-08-05 | [`IMPLEMENTATION_PROMPT_2026-08-05.md`](archive/IMPLEMENTATION_PROMPT_2026-08-05.md) | for Claude Opus 4.6 | prompt | v1.0.21 to v1.1.0 | Task brief derived from the 2026-08-05 review. |
| 2026-08-05 | [`IMPLEMENTATION_LOG_2026-08-05.md`](archive/IMPLEMENTATION_LOG_2026-08-05.md) | not stated | run-log | v1.1.0 | Phase-by-phase commit log of the v1.1.0 implementation. |
| 2026-08-05 | [`IMPLEMENTATION_NOTES.md`](archive/IMPLEMENTATION_NOTES.md) | not stated | report | v1.1.0 | Per-task implementation notes (brew doctor advisories, greedy-cask residue, and later tasks). |
| 2026-08-05 | [`IMPLEMENTATION_REPORT_2026-08-05.md`](archive/IMPLEMENTATION_REPORT_2026-08-05.md) | not stated | report | v1.1.0 | What the v1.1.0 implementation changed. |
| 2026-08-05 | [`ULTRA_REVIEW_2026-08-05_v2.md`](archive/ULTRA_REVIEW_2026-08-05_v2.md) | not stated | review | v1.1.0 | Verification of the v1.1.0 implementation (executed by Gemini). |
| 2026-08-05 | [`COMPLETION_PROMPT_2026-08-05_v2.md`](archive/COMPLETION_PROMPT_2026-08-05_v2.md) | for Gemini | prompt | v1.1.0 to v1.1.1 | Fix brief after the v2 verification (one critical regression). |
| 2026-08-05 | [`IMPLEMENTATION_REPORT_v2.md`](archive/IMPLEMENTATION_REPORT_v2.md) | not stated | report | v1.1.1 | Result of the v1.1.1 round. |
| 2026-08-05 | [`ULTRA_REVIEW_2026-08-05_v3.md`](archive/ULTRA_REVIEW_2026-08-05_v3.md) | not stated | review | v1.1.1 | Verification of v1.1.1. |
| 2026-08-05 | [`PRODUCTION_PROMPT_2026-08-05_v3.md`](archive/PRODUCTION_PROMPT_2026-08-05_v3.md) | for Gemini | prompt | v1.1.1 to v1.2.0 | Release brief. |
| 2026-08-05 | [`IMPLEMENTATION_REPORT_v3.md`](archive/IMPLEMENTATION_REPORT_v3.md) | not stated | report | v1.2.0 | Result of the v1.2.0 release round. |
| 2026-08-05 | [`ULTRA_REVIEW_2026-08-05_v4.md`](archive/ULTRA_REVIEW_2026-08-05_v4.md) | not stated | review | v1.2.0 | Verification plus a study of Homebrew cask versions versus native updaters. |
| 2026-08-05 | [`FINAL_PROMPT_2026-08-05_v4.md`](archive/FINAL_PROMPT_2026-08-05_v4.md) | for Gemini | prompt | v1.2.0 to v1.3.0 | Production-release brief. |
| 2026-08-05 | [`IMPLEMENTATION_REPORT_v4.md`](archive/IMPLEMENTATION_REPORT_v4.md) | not stated | report | v1.3.0 | Result of the v1.3.0 round. |
| 2026-08-05 | [`ULTRA_REVIEW_2026-08-05_v5.md`](archive/ULTRA_REVIEW_2026-08-05_v5.md) | not stated | review | v1.3.0 | Verification plus the sudo / Touch ID prompt fix. |
| 2026-08-05 | [`PRODUCTION_PROMPT_2026-08-05_v5.md`](archive/PRODUCTION_PROMPT_2026-08-05_v5.md) | for Gemini | prompt | v1.3.0 to v1.3.1 | Release brief. |
| 2026-08-05 | [`ULTRA_REVIEW_FINAL_v1.3.1.md`](archive/ULTRA_REVIEW_FINAL_v1.3.1.md) | not stated | review | v1.3.1 | Final review after six iterations (v1.0.21 to v1.3.1). |
| 2026-08-12 | [`Opus5_Max_Ultra_Review_v6.md`](archive/Opus5_Max_Ultra_Review_v6.md) | Claude Opus 5 (Max) | review | v1.3.1 | Full review at HEAD `dd3c7d5`; successor of the local-only Opus 5 v1-v5 series. |
| 2026-08-12 | [`Opus5_Max_Implementation_Prompt_v6.md`](archive/Opus5_Max_Implementation_Prompt_v6.md) | for Gemini 3 Flash (high) | prompt | v1.3.1 to v1.4.0 | Implementation brief from the v6 review. |
| 2026-08-14 | [`ULTRA_REVIEW_2026-08-14.md`](archive/ULTRA_REVIEW_2026-08-14.md) | Oz (Warp agent) | review | pre-v1.4.1 | Code analysis, last run log, full suite and competitor research. |
| 2026-08-14 | [`GEMINI_3_7_FLASH_HIGH_PROMPT_2026-08-14.md`](archive/GEMINI_3_7_FLASH_HIGH_PROMPT_2026-08-14.md) | for Gemini 3.7 Flash (high) | prompt | pre-v1.4.1 | Implementation brief. |
| 2026-08-14 | [`GEMINI_3_7_FLASH_HIGH_FINAL_FIXES_2026-08-14.md`](archive/GEMINI_3_7_FLASH_HIGH_FINAL_FIXES_2026-08-14.md) | for Gemini 3.7 Flash (high) | prompt | pre-v1.4.1 | Final fixes after verification of that implementation. |
| 2026-08-19 | [`ULTRA_REVIEW_2026-08-19.md`](archive/ULTRA_REVIEW_2026-08-19.md) | not stated | run-log | v1.4.1 | New-Mac run where the macOS step was skipped; root-cause review. |
| 2026-08-26 | [`ULTRA_REVIEW_2026-08-26.md`](archive/ULTRA_REVIEW_2026-08-26.md) | not stated | run-log | v1.4.1 to v1.4.2 | Review of the latest run log with fixes and regression tests. |
| 2026-09-02 | [`ULTRA_REVIEW_2026-09-02.md`](archive/ULTRA_REVIEW_2026-09-02.md) | not stated | review | v1.4.3 | Microsoft AutoUpdate path, App Store Track 1, machine summary; recommendations R1-R7. |
| 2026-09-02 | [`GEMINI_TASK_2026-09-02.md`](archive/GEMINI_TASK_2026-09-02.md) | for Gemini Flash 3.7 (high) | prompt | v1.4.3 to v1.4.4 | Execution brief for the R1-R7 recommendations. |
| 2026-09-03 | [`GUARD_AUDIT_2026-09.md`](archive/GUARD_AUDIT_2026-09.md) | not stated | report | v1.4.4 | Audit of guards that suppress their own diagnostic input (related to the self-suppressing-guard rule in AGENTS.md). |
| 2026-09-05 | [`fable5.1_ultra_review_v1.md`](archive/fable5.1_ultra_review_v1.md) | Fable 5.1 | review | v1.4.4 | Whole repository, live system and 26 run logs. |
| 2026-09-16 | [`fable5.1_ultra_review_macos27_v1.md`](archive/fable5.1_ultra_review_macos27_v1.md) | Fable 5.1 | review | v1.4.5 | Review after upgrading the reference Mac to macOS 27. |
| 2026-09-16 | [`gemini_3.8_flash_macos27_prompt_v1.md`](archive/gemini_3.8_flash_macos27_prompt_v1.md) | for Gemini 3.8 Flash | prompt | v1.4.6 | macOS 27 adaptation brief. |
| 2026-09-23 | [`opus_5.5_ultra_review_v1.md`](archive/opus_5.5_ultra_review_v1.md) | Claude Opus 5.5 | review | v1.4.6 | Review on macOS 27: vendor truth, install-only-what-is-present, inventory drift. |
| 2026-09-23 | [`gemini_3.8_flash_opus55_impl_prompt_v1.md`](archive/gemini_3.8_flash_opus55_impl_prompt_v1.md) | for Gemini 3.8 Flash | prompt | v1.4.6 to v1.5.0 | Implementation brief T0-T15 from the Opus 5.5 review. |
| 2026-09-24 | [`IMPLEMENTATION_REPORT_opus55_v1.md`](archive/IMPLEMENTATION_REPORT_opus55_v1.md) | Gemini 3.8 Flash | report | v1.5.0 | Per-task result of T0-T15 (vendor truth). |
| 2026-09-24 | [`gemini_3.8_flash_opus55_fix_prompt_v2.md`](archive/gemini_3.8_flash_opus55_fix_prompt_v2.md) | for Gemini 3.8 Flash | prompt | v1.5.0 | Fix brief F0-F12 after line-by-line verification. |
| 2026-09-24 | [`FIX_REPORT_opus55_v2.md`](archive/FIX_REPORT_opus55_v2.md) | Gemini 3.8 Flash (Antigravity) | report | v1.5.0 | Result of F0-F12. |
| 2026-09-24 | [`gemini_3.8_flash_opus55_fix_prompt_v3.md`](archive/gemini_3.8_flash_opus55_fix_prompt_v3.md) | for Gemini 3.8 Flash | prompt | v1.5.0 | Fix brief G0-G5 (privacy redaction and minor bugs). |
| 2026-09-24 | [`gemini_3.8_flash_opus55_fix_prompt_v4.md`](archive/gemini_3.8_flash_opus55_fix_prompt_v4.md) | for Gemini 3.8 Flash | prompt | v1.5.0 | Fixes from the first real run of the branch. |
| 2026-09-25 | [`gemini_3.8_flash_opus55_docs_landing_prompt_v6.md`](archive/gemini_3.8_flash_opus55_docs_landing_prompt_v6.md) | for Gemini 3.8 Flash | prompt | v1.5.0 | Documentation, landing-page and Agentic OS sync brief. |
| 2026-09-25 | [`gemini_3.8_flash_opus55_release_prompt_v7.md`](archive/gemini_3.8_flash_opus55_release_prompt_v7.md) | for Gemini 3.8 Flash | prompt | v1.5.1 | Release brief and production acceptance checklist. |
| 2026-09-25 | [`gemini_3.8_flash_opus55_ci_prompt_v8.md`](archive/gemini_3.8_flash_opus55_ci_prompt_v8.md) | for Gemini 3.8 Flash | prompt | v1.5.1 | Brief for green, hermetic GitHub CI. |

## Local-only records (not published)

Some records exist only on the maintainer's machine and travel through the `dev_sync` private overlay. They are listed in `.gitignore`, are not part of the published repository and must not be `git add`ed: an early project review (2026-06-09), the Opus 5 review series v1-v5 (2026-07-30, v1.0.21), the 2026-06-09 release report, and one 2026-09-06 review (v1.4.4) that quotes machine-specific absolute paths. Session handoffs under `docs/agents/handoffs/` are local-only as well.

## Privacy rules for new records

Public records must not contain absolute home-directory paths, account names, e-mail addresses, hostnames, machine inventory or tokens; paraphrase run-log evidence instead (see the v1.5.5 follow-up for the pattern). Put anything that cannot be sanitized under a path that `.gitignore` excludes.
