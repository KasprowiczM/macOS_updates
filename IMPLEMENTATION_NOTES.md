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
