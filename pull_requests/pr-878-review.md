# PR 878 review: tell the owner times in 12-hour form, UTC with Central beside it

Closes #877. Files: `CLAUDE.md` (a "Times" section).

| Check | Result |
|---|---|
| The owner asked for it, in their words, quoted with the date ("give all utc times in am pm all chats", November 17, 2026) | ok |
| Scope: only what agents tell the owner; files, logs, tables, commit messages and code keep ISO 8601 UTC, so nothing machine-read changes | ok |
| The same section is in all four repositories' `CLAUDE.md` (health-transformation-lab-nlp, gemma-developer-agent, gemma-developer-agent-private, pipeline-doctor) | ok |
| Central is the owner's zone (the status sheet already gives Central beside UTC); in November it is UTC-6 | ok |
| No secrets, no task text | ok |

## Verdict

Ready to merge once CI is green. It changes a rule at the owner's own request.
