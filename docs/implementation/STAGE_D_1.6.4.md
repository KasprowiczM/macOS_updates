# Stage D implementation, 1.6.4

Local source checkpoint dated 2026-11-13, unpublished. Tasks T10-T11 close static adaptation and fixture acceptance. The common capability detector and coverage resolver were integrated with stage C so all views use the same source decisions.

Unknown apps remain visible in the local inventory. Sparkle, Electron, Squirrel, Keystone and receipt signals describe possible capabilities; they do not execute an updater, fetch an arbitrary local feed or grant installation authority. An optional proposal export requires review of its redacted preview. It remains local and never changes executable recipes.

Two profile test methods exercise 29 synthetic new-user profiles and a separate 100-bundle offline scan. The profiles include missing managers, MAS-only CapCut, stale cask conflicts, custom roots, duplicates, partial scans, changed identities, removed/running targets, MDM signals and unknown updaters. Command and network calls are forbidden. The scan has a five-second budget; the Python 3.9 targeted run, including all profiles, completed in 0.147 seconds.

Verification: the sealed full integration gate passed 1103 cases (1102 passed and one explicitly skipped), with zero unexpected host-command or network guard hits. Shell syntax, Python compilation and tracked secret scanning passed. The two profile tests also passed on Python 3.9.6. These fixtures establish deterministic safety behavior, not live compatibility with every macOS version. Linux execution, a disposable Mac, signed-out/other-account GUI acquisition and actual updates were not run. No public direct/native recipe was promoted from metadata alone. Landing and Ascendo parity remain separate work.
