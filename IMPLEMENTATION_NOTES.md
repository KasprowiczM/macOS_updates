# Implementation Notes

## Task 1 - Stop treating `brew doctor` advisories and greedy-cask residue as hard failures
Files: update_brew.sh, tests/test_safety_static.py
What changed: Updated update_brew.sh so brew doctor warnings no longer set BREW_EXIT=1 and are logged as health advisories. Post-upgrade remaining greedy casks are now printed as informational without setting BREW_EXIT=1. Added static test test_brew_doctor_and_greedy_cask_no_hard_failure.
Why: Finding C2 - brew doctor advisories and greedy-cask residue were incorrectly causing hard failures and skipping system updates.
Tests: test_brew_doctor_and_greedy_cask_no_hard_failure (run_tests.sh passed 95 tests)
Deviations: none

## Task 2 - Give update_brew.sh, update_appstore.sh and update_npm_cli.sh a soft-exit path
Files: lib/severity.sh, update_brew.sh, update_appstore.sh, update_npm_cli.sh, docs/agents/exit_codes.md, tests/test_safety_static.py
What changed: Created lib/severity.sh defining MAC_UPDATE_SOFT_EXIT=10 and severity helpers mac_update_severity_init and mac_update_severity_exit_code. Updated update_brew.sh, update_appstore.sh, and update_npm_cli.sh to source lib/severity.sh, track HARD_FAIL and SOFT_FAIL accumulators, and exit with code 10 on non-mutating unverifiable conditions while reserving exit code 1 for hard transaction failures. Updated docs/agents/exit_codes.md and added static test test_leaf_scripts_source_severity_and_have_soft_exit_path.
Why: Finding C1 - Leaf orchestrators lacked soft exit paths, causing non-critical unverifiable states (like offline checks, snapshot errors, or background installs) to trigger hard exit code 1 and block system updates.
Tests: test_leaf_scripts_source_severity_and_have_soft_exit_path, test_appstore_success_header_depends_on_final_exit_status (run_tests.sh passed 96 tests)
Deviations: none

## Task 3 - Classify the three unclassified internet-app statuses
Files: update_internet_apps.sh, tests/test_safety_static.py
What changed: Added L_INTERNET_STATUS_UNKNOWN_VERSION and L_INTERNET_STATUS_MAU_OPENED to the SOFT failure case in update_internet_apps.sh. Extended I18nCompletenessTests with test_all_internet_status_constants_are_classified to enforce that every L_INTERNET_STATUS_* constant belongs to hard, soft, or benign allowlist.
Why: Finding H12 - Unclassified status constants previously produced exit code 0, misreporting unverifiable runs as completely clean.
Tests: test_all_internet_status_constants_are_classified (run_tests.sh passed 97 tests)
Deviations: none

## Task 4 - Make the severity tests exercise the real scripts, not stubs
Files: tests/test_safety_static.py
What changed: Added producer-side static test test_producer_side_soft_exit_references verifying each leaf script references soft exit code and has a soft exit path. Added test_leaf_script_behavioural_severity running real leaf orchestrators against mock-PATH binaries to assert exit codes for doctor warnings (0), greedy casks (0/10), formula upgrade failures (1), mas outdated failures (10), and offline curl failures (10).
Why: Finding H3 - Test suite previously stubbed children with exit N, leaving real leaf severity logic untested.
Tests: test_producer_side_soft_exit_references, test_leaf_script_behavioural_severity (run_tests.sh passed 99 tests)
Deviations: none

## Task 5 - Add `--fail` to every internet-app curl invocation
Files: lib/internet_app_updates.sh, lib/github_release.sh, update_internet_apps.sh, tests/test_safety_static.py
What changed: Added -f / -fsSL flags to 11 curl calls across lib/internet_app_updates.sh and lib/github_release.sh. Reclassified L_INTERNET_STATUS_DOWNLOAD_ERROR from hard to soft failure (exit 10) in update_internet_apps.sh since a failed download leaves system state unmutated. Added test_curl_invocations_use_fail_flag_and_download_error_is_soft.
Why: Finding H7 - Missing -f flag caused HTTP 404 responses to exit 0 with HTML error text written into archives, leading to false MOUNT_ERROR hard failures.
Tests: test_curl_invocations_use_fail_flag_and_download_error_is_soft (run_tests.sh passed 100 tests)
Deviations: none

## Task 6 - Handle exit 10 soft failures gracefully in update_all.sh
Files: update_all.sh, tests/test_safety_static.py
What changed: Updated update_all.sh to track soft failures (DEGRADED), continue through all steps including step 6 (macOS system update), and exit with code 10 at top level when soft warnings occurred without hard failures. Updated tests to assert top-level exit code 10 on degraded execution.
Why: Finding M1 - update_all.sh previously exited 0 on soft warnings, failing to convey degraded status to callers while correctly keeping step 6 unblocked.
Tests: test_soft_internet_failure_still_runs_macos_system_step, test_soft_failure_in_every_layer_never_blocks_macos_system_step (run_tests.sh passed 100 tests)
Deviations: none

## Task 7 - Wrap Track 2 App Store AppleScript GUI automation in a timeout
Files: update_appstore.sh, tests/test_safety_static.py
What changed: Wrapped Track 2 osascript execution in run_with_timeout using MAC_UPDATE_APPSTORE_GUI_TIMEOUT (default 180s). On timeout or error, set SOFT_FAIL=1 and log warning without setting hard exit 1 or blocking execution. Added static test test_appstore_track2_gui_wrapped_in_timeout.
Why: Finding H6 - AppleScript GUI automation could hang indefinitely on custom themes or high contrast settings.
Tests: test_appstore_track2_gui_wrapped_in_timeout (run_tests.sh passed 101 tests)
Deviations: none

## Task 8 - Fix edge cases in Firefox Dev, ChatGPT Atlas, and KeePassXC handlers
Files: lib/internet_app_updates.sh, tests/test_safety_static.py
What changed: Set STATUS_FIREFOX to UNKNOWN_VERSION when application.ini returns ? in iu_firefox_developer_edition. Updated iu_chatgpt_atlas to use silent_launch_app because OpenAI retired public Sparkle feeds. Added safe default for KPX_ARCH in iu_keepassxc when uname -m returns non-standard values. Added test_task_8_edge_cases_handling to test_safety_static.py.
Why: Findings H13, H14, H15 - Edge-case version parsing and retired appcast URLs caused unhandled errors or broken download URLs.
Tests: test_task_8_edge_cases_handling (run_tests.sh passed 102 tests)
Deviations: none

## Task 9 - Add awk fallback to Node version detection in update_npm_cli.sh
Files: update_npm_cli.sh, tests/test_safety_static.py
What changed: Added an awk-based fallback JSON parser in detect_latest_node_version if python3 parsing returns empty. Ensured SOFT_FAIL=1 is set if both fail. Added test_detect_latest_node_version_contains_python_and_awk_fallback to test_safety_static.py.
Why: Finding H5 - Lack of a fallback parser in Node version detection caused false failures in environments where python3 inline execution failed.
Tests: test_detect_latest_node_version_contains_python_and_awk_fallback (run_tests.sh passed 103 tests)
Deviations: none

## Task 10 - Make Bun SHA-256 matching resilient in update_npm_cli.sh
Files: update_npm_cli.sh, tests/test_safety_static.py
What changed: Updated grep in install_bun_tarball to use extended regex grep -E "[[:space:]]+(\./)?${archive_name}\$", allowing flexible spacing and optional ./ prefixes in SHASUMS256.txt. Set SOFT_FAIL=1 on checksum lookup or verification failures. Added test_bun_shasum_pattern_is_resilient to test_safety_static.py.
Why: Finding H16 - Rigid double-space grep pattern caused Bun tarball installation to fail if upstream SHASUMS256 formatting changed.
Tests: test_bun_shasum_pattern_is_resilient (run_tests.sh passed 104 tests)
Deviations: none

## Task 11 - Sanitize inventory table formatting in report_update_coverage.sh
Files: scripts/report_update_coverage.sh, tests/test_safety_static.py
What changed: Added clean_app_name to strip markdown links ([App](url)), bold/italic formatting (**App**), and emojis before name normalization in scripts/report_update_coverage.sh. Added test_report_update_coverage_sanitizes_formatted_rows to test_safety_static.py.
Why: Finding H18 - Markdown formatting and links in APPLICATIONS.md caused formatted inventory rows to fail matching against update categories and fall through to unknown.
Tests: test_report_update_coverage_sanitizes_formatted_rows (run_tests.sh passed 105 tests)
Deviations: none

## Task 12 - Prioritize bundle IDs over name matching for ChatGPT Codex
Files: scripts/report_update_coverage.sh, tests/test_safety_static.py
What changed: Confirmed bundle ID prioritization in target_for and bundle-ID-only alias for ChatGPT / Codex in scripts/report_update_coverage.sh. Added test_chatgpt_codex_target_alias_is_bundle_id_only to test_safety_static.py.
Why: Finding H19 - Target matching by string equality without checking bundle ID could misidentify legacy com.openai.chat as com.openai.codex.
Tests: test_chatgpt_codex_target_alias_is_bundle_id_only (run_tests.sh passed 106 tests)
Deviations: none

## Task 13 - Add robust fallback anchors for section insertions in build_inventory.sh
Files: update_all.sh, tests/test_safety_static.py
What changed: Added fallback anchors and warning logs for 4a formulae, 4c casks, GRUPA 2 App Store, and GRUPA 3 new app section insertions in update_all.sh prescan block. Added test_inventory_insertion_has_fallback_anchors to test_safety_static.py.
Why: Finding M3 - Fragile regex section matching could silently fail or misplace inventory entries if section header formatting changed.
Tests: test_inventory_insertion_has_fallback_anchors (run_tests.sh passed 107 tests)
Deviations: none

## Task 14 - Add ANSI escape sequence stripping to update_brew.sh
Files: update_brew.sh, tests/test_safety_static.py
What changed: Added strip_ansi helper to update_brew.sh and piped brew list, brew outdated, and brew doctor outputs through it to strip ANSI control sequences. Added test_brew_outputs_use_ansi_stripping to test_safety_static.py.
Why: Finding M4 - Unstripped ANSI escape codes in Homebrew command outputs could corrupt package names and version tracking.
Tests: test_brew_outputs_use_ansi_stripping (run_tests.sh passed 108 tests)
Deviations: none

## Task 15 - Expand PATH for Node manager locations in update_npm_cli.sh
Files: update_npm_cli.sh, tests/test_safety_static.py
What changed: Added expand_node_manager_paths function to update_npm_cli.sh to include ~/.n/bin, ~/.nvm/versions/node/v*/bin, /usr/local/bin, and /opt/homebrew/bin in PATH before running toolchain checks. Added test_update_npm_cli_expands_node_manager_paths to test_safety_static.py.
Why: Finding M5 - Custom or non-standard Node manager paths caused command -v npm to fail in non-interactive shells.
Tests: test_update_npm_cli_expands_node_manager_paths (run_tests.sh passed 109 tests)
Deviations: none

## Task 16 - Add Location header fallback to github_latest_tag in lib/github_release.sh
Files: lib/github_release.sh, tests/test_safety_static.py
What changed: Updated github_latest_tag in lib/github_release.sh to fall back to parsing the Location header redirect from https://github.com/owner/repo/releases/latest if the API endpoint returns empty or rate-limit error. Added test_github_latest_tag_contains_location_fallback to test_safety_static.py.
Why: Finding M9 - GitHub API rate limits or JSON format changes could cause version resolution to fail without a secondary fallback.
Tests: test_github_latest_tag_contains_location_fallback (run_tests.sh passed 110 tests)
Deviations: none

## Task 17 - Ensure schema_version 2 and classification_counts in coverage report JSON
Files: scripts/report_update_coverage.sh, tests/test_safety_static.py
What changed: Confirmed schema_version: 2 and top-level classification_counts summary dictionary in scripts/report_update_coverage.sh JSON payload. Added test_report_update_coverage_json_schema_v2 to test_safety_static.py.
Why: Finding M10 - JSON consumers require explicit schema versioning and structured classification counts for stability across updates.
Tests: test_report_update_coverage_json_schema_v2 (run_tests.sh passed 111 tests)
Deviations: none

## Task 18 - Expand TARGET_ALIASES for multi-name apps in report_update_coverage.sh
Files: scripts/report_update_coverage.sh, tests/test_safety_static.py
What changed: Expanded TARGET_ALIASES dictionary in scripts/report_update_coverage.sh to cover name and bundle_id variants for Visual Studio Code, Brave Browser, DJI Assistant 2, OpenCode, and zoom.us. Added test_target_aliases_contains_all_multi_name_apps to test_safety_static.py.
Why: Finding M14 - Missing name/bundle_id aliases caused multi-name apps to fall back to unknown classification on systems with variant bundle names.
Tests: test_target_aliases_contains_all_multi_name_apps (run_tests.sh passed 112 tests)
Deviations: none

## Task 19 - Full End-to-End Verification across all 7 steps
Files: IMPLEMENTATION_NOTES.md
What changed: Conducted full repository verification. Ran complete test suite (112 tests passed), syntax checks on all shell scripts (bash -n passed), shellcheck warning scan (0 warnings), and verified honest update coverage report generation.
Why: Ensure all 19 reviewed findings and tasks are fully implemented, verified, and documented without regressions.
Tests: run_tests.sh (112 tests passed), bash -n, shellcheck, report_update_coverage.sh
Deviations: none

## Task R1 - Revert the update_all.sh exit-code change and restore the two tests
Files: update_all.sh, tests/test_safety_static.py
What changed: Restored `exit "$OVERALL_EXIT"` as the final statement in update_all.sh and removed the `FINAL_EXIT` block so soft/degraded runs exit 0. Restored returncode 0 assertions in test_soft_internet_failure_still_runs_macos_system_step and test_soft_failure_in_every_layer_never_blocks_macos_system_step. Added unit test test_degraded_only_exits_zero asserting exit code 0 when only DEGRADED is set.
Why: Finding N1
ACCEPTANCE CHECK command: grep -c 'FINAL_EXIT' update_all.sh ; grep -n 'result.returncode, 0' tests/test_safety_static.py | head -3
ACCEPTANCE CHECK output:
```
0
458:                    result.returncode, 0, msg=result.stdout + result.stderr
479:        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
495:                    result.returncode, 0, msg=result.stdout + result.stderr
```
Tests: test_soft_internet_failure_still_runs_macos_system_step, test_soft_failure_in_every_layer_never_blocks_macos_system_step, test_degraded_only_exits_zero — run_tests.sh: 113 passed
Deviations: none

## Task R2 - Fix App Store Track 2, which is silently broken on stock macOS
Files: update_appstore.sh, tests/test_safety_static.py
What changed: Updated update_appstore.sh to write the Track 2 AppleScript payload to a session or temp script file before invoking `run_with_timeout "$GUI_TIMEOUT" osascript "$AS_SCRIPT_FILE"`. Removed the piped heredoc from the run_with_timeout invocation to prevent stdin loss when running background fallback tasks. Added unit test `test_no_run_with_timeout_uses_piped_heredoc` asserting no run_with_timeout call uses piped heredocs.
Why: Finding N2
ACCEPTANCE CHECK command: grep -n -A2 'run_with_timeout .*osascript' update_appstore.sh
ACCEPTANCE CHECK output:
```
426:if ! AS_RESULT=$(run_with_timeout "$GUI_TIMEOUT" osascript "$AS_SCRIPT_FILE" 2>&1); then
427-    print_warn "Track 2 (App Store GUI) timed out or failed; review window manually"
428-    SOFT_FAIL=1
```
Tests: test_appstore_track2_gui_wrapped_in_timeout, test_no_run_with_timeout_uses_piped_heredoc — run_tests.sh: 114 passed
Deviations: none

## Task R3 - Stop the test suite from mutating the developer's home directory
Files: tests/test_safety_static.py
What changed: Updated test environment builders (`run_update_all_with_layer_exit` and `test_leaf_script_behavioural_severity`) in `tests/test_safety_static.py` to set `"HOME": str(tmp_path / "fake-home")` and create the fake home directory before launching subprocesses. Added unit test `test_subprocess_runs_targeting_update_scripts_set_sandboxed_home` asserting that every subprocess invocation executing an `update_*.sh` script sets a sandboxed `HOME` in its environment.
Why: Finding N4
ACCEPTANCE CHECK command: ls -la "$HOME/.zshrc" > /tmp/before.txt 2>&1; bash run_tests.sh > /dev/null 2>&1; ls -la "$HOME/.zshrc" > /tmp/after.txt 2>&1; diff /tmp/before.txt /tmp/after.txt && echo "HOME UNTOUCHED"
ACCEPTANCE CHECK output:
```
HOME UNTOUCHED
```
Tests: test_leaf_script_behavioural_severity, test_subprocess_runs_targeting_update_scripts_set_sandboxed_home — run_tests.sh: 115 passed
Deviations: none

## Task R4 - Restore hard-failure classification in update_npm_cli.sh
Files: update_npm_cli.sh, tests/test_safety_static.py
What changed: Updated update_npm_cli.sh to assign `HARD_FAIL=1` when Node.js (`ensure_latest_node`) or Bun (`ensure_latest_bun`) tarball installation/verification fails mid-mutation. Retained `SOFT_FAIL=1` for offline feed lookup failures. Added a new test scenario to `test_leaf_script_behavioural_severity` asserting Bun tarball extraction failure produces exit 1 while offline curl failures produce exit 10.
Why: Finding N3
ACCEPTANCE CHECK command: grep -c 'HARD_FAIL=1' update_npm_cli.sh
ACCEPTANCE CHECK output:
```
10
```
Tests: test_leaf_script_behavioural_severity — run_tests.sh: 115 passed
Deviations: none

## Task R5 - Make shell-profile edits non-destructive
Files: update_npm_cli.sh, tests/test_safety_static.py
What changed: Updated `update_npm_cli.sh` profile helpers (`ensure_line_in_file`, `remove_line_from_file`, `remove_npmrc_prefix`) to resolve target symlinks via `resolve_target_file` before editing, write in-place via `cat "$tmpfile" > "$target"`, and record one timestamped backup per target path per run. Added unit test `test_remove_line_from_file_preserves_symlink` asserting symlink preservation and in-place editing of target contents.
Why: Finding H11
ACCEPTANCE CHECK command: grep -n 'mv "$tmpfile"' update_npm_cli.sh || echo "NO MV ONTO PROFILE"
ACCEPTANCE CHECK output:
```
NO MV ONTO PROFILE
```
Tests: test_remove_line_from_file_preserves_symlink — run_tests.sh: 116 passed
Deviations: none

## Task R6 - Fix VS Code handler: official API, checksum, and ditto
Files: lib/internet_app_updates.sh
What changed: Refactored `iu_visual_studio_code` to query the official Microsoft VS Code update API endpoint (`https://update.code.visualstudio.com/api/update/darwin-arm64/stable/latest`) for `productVersion`, `url`, and `sha256hash`. Added sha256 checksum validation prior to archive extraction, and replaced `unzip -q` with `ditto -x -k` to preserve code signature attributes.
Why: Finding H6
ACCEPTANCE CHECK command: awk '/^iu_visual_studio_code\(\)/,/^}/' lib/internet_app_updates.sh | grep -cE 'api/update/darwin-arm64|sha256hash|ditto -x -k'
ACCEPTANCE CHECK output:
```
3
```
Tests: run_tests.sh: 116 passed
Deviations: none

## Task R7 - Verify Ledger Live sha512 checksum before mounting DMG
Files: lib/internet_app_updates.sh
What changed: Updated `iu_ledger` to extract `sha512` hash from `latest-mac.yml` and verify the downloaded DMG via `shasum -a 512` before mounting. Implemented base64/hex normalization comparison logic. Aborts DMG mounting with `L_INTERNET_STATUS_DOWNLOAD_ERROR` on checksum mismatch.
Why: Finding H7
ACCEPTANCE CHECK command: awk '/^iu_ledger\(\)/,/^}/' lib/internet_app_updates.sh | grep -cE 'shasum -a 512|sha512'
ACCEPTANCE CHECK output:
```
2
```
Tests: run_tests.sh: 116 passed
Deviations: none

## Task R8 - Make the ChatGPT Atlas registry row match its handler
Files: config/internet_app_methods.txt, docs/agents/critical_rules.md, tests/test_safety_static.py
What changed: Updated `config/internet_app_methods.txt` to register ChatGPT Atlas as `silent_launch`. Updated `docs/agents/critical_rules.md` Section 5 to categorize ChatGPT Atlas under `Built-in auto-updater (silent launch, triggered-unverified)`. Added `test_handler_registry_dmg_consistency` in `tests/test_safety_static.py` asserting registry method consistency with `mount_verified_dmg` usage.
Why: Finding N5
ACCEPTANCE CHECK command: grep -n 'ChatGPT Atlas' config/internet_app_methods.txt
ACCEPTANCE CHECK output:
```
7:ChatGPT Atlas|silent_launch|STATUS_ATLAS
```
Tests: test_handler_registry_dmg_consistency — run_tests.sh: 117 passed
Deviations: none

## Task R9 - Stop the Atlas handler claiming the ChatGPT/Codex bundle
Files: lib/internet_app_updates.sh, tests/test_safety_static.py
What changed: Added a `com.openai.codex` bundle ID exclusion check in `iu_chatgpt_atlas` candidate loop so `/Applications/ChatGPT.app` is skipped if it belongs to ChatGPT / Codex. Added unit test `test_chatgpt_atlas_ignores_codex_bundle` asserting that `com.openai.codex` bundle ID candidates are excluded.
Why: Finding N6
ACCEPTANCE CHECK command: awk '/^iu_chatgpt_atlas\(\)/,/^}/' lib/internet_app_updates.sh | grep -c 'com.openai.codex\|/Applications/ChatGPT.app'
ACCEPTANCE CHECK output:
```
2
```
Tests: test_chatgpt_atlas_ignores_codex_bundle — run_tests.sh: 118 passed
Deviations: none

## Task R10 - Make strip_ansi actually work on macOS
Files: update_brew.sh, tests/test_safety_static.py
What changed: Investigated BSD sed escape sequence behavior (`printf 'A\033[0;31mR\033[0mB\n' | sed -e 's/\x1b\[[0-9;]*[a-zA-Z]//g' | cat -v` returned `ARB`). Refactored `strip_ansi` in `update_brew.sh` to use bash ANSI-C quoting `sed $'s/\033\\[[0-9;]*[a-zA-Z]//g'`. Updated `test_brew_outputs_use_ansi_stripping` in `tests/test_safety_static.py` to pipe literal ESC sequences through `strip_ansi` and assert removal.
Why: Finding N7
ACCEPTANCE CHECK command: printf 'A\033[0;31mR\033[0mB\n' | sed $'s/\033\\[[0-9;]*[a-zA-Z]//g' | cat -v
ACCEPTANCE CHECK output:
```
ARB
```
Tests: test_brew_outputs_use_ansi_stripping — run_tests.sh: 118 passed
Deviations: none

## Task R11 - Stop gating the macOS update decision on untranslated English strings
Files: update_system.sh, update_appstore.sh
What changed: Updated `update_system.sh` to execute `softwareupdate -l` with `LANG=C LC_ALL=C` so output is deterministically formatted in C locale. Updated `update_appstore.sh` Accessibility probe to check for AppleScript error code `-1743` (`errAEEventNotPermitted`) and removed the overly broad bare token `access`.
Why: Finding H8
ACCEPTANCE CHECK command: grep -c 'LC_ALL=C softwareupdate' update_system.sh ; grep -c '1743' update_appstore.sh
ACCEPTANCE CHECK output:
```
1
1
```
Tests: run_tests.sh: 118 passed
Deviations: none

## Task R12 - Stop Microsoft AutoUpdate quarantine oscillating for hidden products
Files: lib/internet_app_updates.sh, tests/test_safety_static.py
What changed: Updated `mau_reconcile_deferrals` in `lib/internet_app_updates.sh` to receive the offered products list as a second argument (`$offered`) and restricted release targets to IDs that are BOTH offered in the list and non-regressed. Preserved read-only contract of `mau_deferral_preflight`. Added `test_reconcile_does_not_release_hidden_unoffered_deferral` to `MauRegressionGuardTests` asserting unoffered products remain deferred.
Why: Finding H10
ACCEPTANCE CHECK command: awk '/^mau_reconcile_deferrals\(\)/,/^}/' lib/internet_app_updates.sh | grep -c 'msupdate_list\|RAW_LIST\|LIST_OUTPUT\|OFFERED\|offered'
ACCEPTANCE CHECK output:
```
2
```
Tests: test_reconcile_does_not_release_hidden_unoffered_deferral — run_tests.sh: 119 passed
Deviations: none

## Task R13 - Untrack gitignored files and ship the deny rules
Files: .claude/settings.json, .claude/settings.local.json, scripts/scan_secrets.sh, .github/workflows/gitleaks.yml
What changed: Untracked gitignored files `.claude/settings.local.json`, `.claude/.DS_Store`, and `skills/.DS_Store` via `git rm --cached`. Moved the `permissions.deny` security rules array into tracked `.claude/settings.json`. Updated `scripts/scan_secrets.sh` and `.github/workflows/gitleaks.yml` with general `git check-ignore --no-index` validation across all tracked files.
Why: Finding M14
ACCEPTANCE CHECK command: git ls-files -z | xargs -0 git check-ignore --no-index -v ; echo "exit=$?"
ACCEPTANCE CHECK output:
```
exit=1
```
Tests: run_tests.sh: 119 passed
Deviations: none

## Task R14 - Bring inline Python under quality gate
Files: run_tests.sh, CLAUDE.md, AGENTS.md, GEMINI.md, CONTRIBUTING.md, update_all.sh
What changed: Added step 2 heredoc Python extraction and `py_compile` quality gate in `run_tests.sh` (with non-fatal `ruff check` pass if present). Updated non-negotiable rule 4 across `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, and `CONTRIBUTING.md` to permit importable pure-function modules under `lib/python/`. Added `# TODO(H4):` comments above prescan and postupdate heredocs in `update_all.sh`.
Why: Finding H4
ACCEPTANCE CHECK command: bash run_tests.sh 2>&1 | grep -i 'heredoc\|py_compile'
ACCEPTANCE CHECK output:
```
── 2/4  python3 -m py_compile on all .py and inline heredocs
  ✅ all inline heredoc python blocks compile
```
Tests: run_tests.sh: 119 passed
Deviations: none

## Task R15 - Deduplicate helpers
Files: lib/proc.sh, update_appstore.sh, update_internet_apps.sh, update_npm_cli.sh, lib/internet_app_updates.sh
What changed: Created `lib/proc.sh` containing shared `run_with_timeout`. Sourced `lib/proc.sh` in `update_appstore.sh`, `update_internet_apps.sh`, and `update_npm_cli.sh`, removing local duplicates. Migrated 19 pure silent-launch handlers in `lib/internet_app_updates.sh` to one-line `internet_dispatch_silent_launch` calls.
Why: Finding M15
ACCEPTANCE CHECK command: grep -rn 'run_with_timeout()' update_*.sh lib/*.sh | wc -l ; [ -f lib/proc.sh ] && echo "PROC_SH_EXISTS"
ACCEPTANCE CHECK output:
```
1
PROC_SH_EXISTS
```
Tests: run_tests.sh: 119 passed
Deviations: none
















