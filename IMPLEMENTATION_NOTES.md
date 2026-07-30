# Implementation Notes

## Task 1 - Stop treating `brew doctor` advisories and greedy-cask residue as hard failures
Files: update_brew.sh, tests/test_safety_static.py
What changed: Updated update_brew.sh so brew doctor warnings no longer set BREW_EXIT=1 and are logged as health advisories. Post-upgrade remaining greedy casks are now printed as informational without setting BREW_EXIT=1. Added static test test_brew_doctor_and_greedy_cask_no_hard_failure.
Why: Finding C2 - brew doctor advisories and greedy-cask residue were incorrectly causing hard failures and skipping system updates.
Tests: test_brew_doctor_and_greedy_cask_no_hard_failure (run_tests.sh passed 95 tests)
Deviations: none
