# Automatic workflow repair, 1.8.2

The owner requests a complete installed-app workflow, readable CLI output and contextual help in every terminal screen. Publishing the resulting release is authorized. Host updates are not necessary for regression tests; ChatGPT Desktop must remain running and untouched.

## Design

Keep the current Bash and Python engine and repair its observation and consent boundaries. Replacing it with an independent updater would duplicate source detection and installation authority. Removing all guards would allow source changes and unsolicited installations. Instead, persist one clearly disclosed agreement for installed-app updates from their current sources, while preserving per-app exclusions and conflict checks.

The first-run flow covers language, missing requirements, optional author catalog with nothing selected, personal inventory, source explanations and saved update preferences. Existing sources remain unchanged. Source comparisons are recommendations based on available stable-release evidence, not an assumption that one distribution channel always wins. Additional installations and migrations require separate selection and approval.

## Work and acceptance

- [x] Diagnose the latest real run and retain a concise, anonymized explanation.
- [x] Fix missing CLI group and target progress, with bounded output and waiting status.
- [x] Show contextual help in the right sidebar on every supported screen size, including wizard and prompts.
- [x] Persist installed-source update preferences; honor exclusions, protected apps, source conflicts and DeepSeek manual mode.
- [x] Resolve overly broad partial-scan blocking without treating unknown ownership as proven absence.
- [x] Show actionable post-run suggestions and explicit source-comparison entry points.
- [x] Verify setup, optional catalog, inventory, preview and execution with isolated fixtures and terminal rendering.
- [x] Run guarded full tests and sync current documentation and version to 1.8.2.
- [ ] Review and publish source changes.
- [x] Record remaining real-world validation limits and a resume prompt.

Progress must distinguish running, waiting, verified updated, current, skipped and unconfirmed. Indeterminate vendor operations must not display fabricated percentages or claim latest stable merely because an app window opened.
