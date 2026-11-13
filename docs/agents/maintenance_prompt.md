# Universal maintenance prompt

A harness-agnostic prompt for a fresh agent session (any model, any harness). Paste the block below as the first message in a new session opened in this repository. It makes the agent verify the last update run against the live system, review the toolkit, fix what it finds and record the evidence.

Keep this file current when the workflow changes. It must stay free of private data and of tool names that exist in only one harness.

```text
You are maintaining "macOS Updates", a Bash 3.2 + Python 3 update orchestrator for Apple Silicon Macs.
Work in this repository. Follow its contract exactly: read AGENTS.md first, then docs/agents/critical_rules.md,
docs/agents/exit_codes.md and docs/agents/architecture.md. If you have a private project memory or handoff
system available, load the latest handoff for this project before anything else and treat it as a hint, not a fact.

Goal: verify how the last real update run went, review the toolkit, fix what is wrong, and leave evidence.

Phase 1 - ground truth (read-only, no assumptions)
1. git status, current branch, last commits, whether main matches the remote, state of CI on main.
2. bash run_tests.sh (full suite, ShellCheck-relevant checks and secret scan). Record the exact result.
3. bash update_all.sh --doctor (read-only readiness report). Record its exit code and every warning.
4. Find the newest real run: the newest logs/update_all_*.log whose run summary (logs/run_summary_*.json)
   has flags.dry_run = false and flags.inventory_only = false. Read the whole log and the summary.
   Also skim the previous three real runs so you can tell a one-off from a recurring problem.
5. bash scripts/check_vendor_feeds.sh, bash scripts/report_update_coverage.sh and
   bash scripts/report_chronic_warnings.sh.
6. Compare what the run claimed with the live machine: for every item reported as updated, pending,
   unverified or warned, check the installed version and the vendor's current version yourself.
   A claim in a log, a document or a handoff is not evidence until you have checked it.

Phase 2 - review
7. List every defect with evidence (file and line, log line, command output). Separate: confirmed by a
   command you ran / follows from the code / hypothesis. Rank: blocks or mis-reports an update / wastes time
   or misleads / cosmetic. Pay particular attention to: statuses that claim more than was verified; apps
   that were launched, quit, or replaced while the user had them open; warnings that repeat across runs;
   steps that waited on input; English text in a localized run; anything the previous handoff listed as
   "not verified live".
8. Check that the macOS and third-party behaviour the toolkit relies on is still current: look up the
   release notes of the installed macOS version and of Homebrew and mas, and the documentation of any
   update framework involved, instead of relying on memory.
9. Tell the owner what you found before changing anything large. Small, clearly correct fixes may proceed.

Phase 3 - fix
10. Work on a new branch, never directly on main. Keep changes scoped to the defects found.
11. Every fix needs a regression test that fails without it. Tests must be hermetic (no real brew, mas,
    sudo, launchctl, softwareupdate; no dependence on this Mac's apps) and must also pass on the Linux CI job.
12. Never run a real update, install, quit or relaunch of the owner's apps, or anything needing sudo,
    as part of testing. Use --dry-run, --doctor and the test suite. A real bash update_all.sh run is the
    owner's to start; ask for it when live confirmation is needed.
13. New user-facing strings go into all seven language files. No private data, home paths, machine
    inventory or raw log excerpts in tracked files.
14. If you can delegate, split independent work into file-disjoint packages, give each its own isolated
    working copy, use the cheapest model that can do each package well, and have one independent review
    of the merged diff followed by a single fix round. Re-run the full suite yourself on the merged result
    in the owner's main checkout, not only in a clean copy.

Phase 4 - close
15. Update the documentation that describes current behaviour: CHANGELOG.md ([Unreleased], dated section),
    the affected files under docs/agents/, the acceptance checklist status, README files in all languages
    when something user-visible changed.
    Leave dated historical sections unchanged.
16. Do not push, open a pull request, merge, tag or delete anything unless the owner asks. When asked to
    merge: require green CI first, then verify that local main equals the remote.
17. Finish with a short report: what the last run really did; what you fixed (with test results);
    what is still unverified live and how to verify it; decisions that are the owner's. If a handoff or
    memory system is available, store a handoff with the same content. End your final message with this
    prompt again, updated if the workflow changed.

Rules that override convenience: softwareupdate always with -R and per label; mas upgrade with sudo and
explicit IDs; apps the user has open are never quit or replaced; only installed software is updated;
"verified" means a remote version was actually compared in this run; soft warnings never block the macOS step.
```
