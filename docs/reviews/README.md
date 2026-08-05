# Development review artefacts

Everything in this directory is a **development artefact**, not product
documentation and not part of the shipped toolkit. It is kept for provenance:
audit trails, code-review findings, implementation plans and the notes written
while the findings were being fixed.

Nothing here is loaded at runtime and nothing here is authoritative. When an
artefact disagrees with the code, the code wins. The authoritative documents are:

| Topic | Authoritative source |
|-------|----------------------|
| What shipped in each release | [`../../CHANGELOG.md`](../../CHANGELOG.md) |
| Current version | [`../../VERSION`](../../VERSION) |
| End-user documentation | [`../user/`](../user/) |
| Developer / AI-agent reference | [`../agents/`](../agents/) |

## Naming

| Prefix | Contents |
|--------|----------|
| `ULTRA_REVIEW_*` / `ultra_review_*` / `sonnet5_ultra_review_*` / `FABLE5_*` | Full-repository code reviews, newest suffix = newest pass |
| `IMPLEMENTATION_PROMPT_*` / `PRODUCTION_PROMPT_*` / `COMPLETION_PROMPT_*` / `FINAL_PROMPT_*` | Task briefs handed to an agent for a review round |
| `IMPLEMENTATION_REPORT_*` / `IMPLEMENTATION_LOG_*` / `IMPLEMENTATION_NOTES.md` | What was actually changed in response, per task |

## Git status

Tracking status is deliberately mixed and is preserved from before these files
were collected here:

- Some review documents are tracked in git.
- The private-overlay ones (`FABLE5_Project_Review_Report.md`,
  `IMPLEMENTATION_REPORT_20260609.md`, `ultra_review_opus5_v*.md`) are
  `.gitignore`d and travel through `dev_sync/` only. **Do not `git add` them.**
- The rest are untracked working documents.

Before publishing the repository, review anything here that is still untracked —
prompt and report files can quote local paths and machine-specific detail.
