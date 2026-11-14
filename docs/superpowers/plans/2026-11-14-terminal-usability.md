# Terminal usability implementation plan

**Goal:** Make the terminal workspace understandable through visible controls and complete inventory and toolkit-maintenance flows.

**Architecture:** Curses control model over scoped consent/execution with a separately authorized concurrent Internet batch, private inventory policy adapter and guarded toolkit-update service.

**Tech Stack:** Python 3.9 standard library, Bash 3.2, existing localized catalogs.

**Spec:** ../specs/2026-11-14-terminal-usability-design.md

- [x] Audit latest real logs and reproduce keyboard/prompt failures.
- [x] Implement saved-inventory table adapter and explicit exclusion/reset policy changes; test stale snapshot and policy races.
- [x] Implement visible controls, stable action bars, contextual help, automatic prompt editor and truthful phase progress; cover actual PTY flows.
- [x] Implement official-source self-update check/preview/apply, dirty-checkout protection and separation of user state; validate only on fixture repositories.
- [x] Integrate About, action explanations and seven-language copy; update current documentation and patch version.
- [x] Run full guarded tests, inspect rendered flows, record limitations and handoff. Host updates were outside this stage. Publication is tracked by the subsequent 1.8.2 plan.

- [x] Expand automatic Internet mode after the owner requested restoration: separate native and replacement scopes, fresh batch consent, shared manager groups and source ownership.
- [x] Implement concurrent native launches, common observation deadline, group recovery and explicit DeepSeek/unsupported-method distinctions.
- [x] Complete the final regression gate for the expanded batch scope and record the result.
