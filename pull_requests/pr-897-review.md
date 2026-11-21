# PR 897 review: record the decision to retire the old trace experiment (#896)

Reviewed against `AGENTS.md`, `CLAUDE.md` and `.claude/review-rubric.md`.

| Check | Result |
|---|---|
| One issue with its four parts, branch `docs/896-041-retire-old-trace-experiment`, `Closes #896` | yes |
| A decision is an ADR, not an issue thread | yes: `docs/adr/0012-retire-the-old-trace-experiment.md`, listed in `docs/adr/README.md`, linked from spec 041 FR-005 |
| The count behind it | repeated on November 21: 14 of 14 old run labels matched in the new experiment, each with at least as many traces |
| The owner's approval | given in the session on November 21 ("Delete it") |
| Tests | wording, organisation-name and benchmark-order tests: 37 passed |

## Findings

- **Not blocking:** the deletion happens after merge and is not part of the diff. The experiment can be restored from the Databricks trash for 30 days.

Nothing blocking.
