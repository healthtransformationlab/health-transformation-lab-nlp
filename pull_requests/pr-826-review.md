# PR 826 review: raise Modal's auto-start limits

Closes #825. Reviewed against AGENTS.md (settings change by pull request) and ADR 0008.

- One setting file; values carry their source and date. Tests read the file, so the next change touches one place.
- Spending rule: this raises what can start without a reviewer. **It waits for the owner's explicit "merge"**; not merged by the agent.
- Tests: 71 passed, 2 skipped.

Nothing blocking; owner decision required.
