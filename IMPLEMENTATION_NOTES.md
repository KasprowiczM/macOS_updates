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
