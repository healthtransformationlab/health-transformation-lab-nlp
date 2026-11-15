# PR 823 review: a missing azure exporter turns telemetry off; notebooks install it

Closes #822. Reviewed against `.claude/review-rubric.md` and AGENTS.md "Configuration and secrets".

- Optional settings warn and carry on: the missing package now behaves like a missing secret (warning, stderr line, status reason, SEV3 via the digest), never a raised error.
- No value is logged: the test asserts the connection string is absent from stderr and the log.
- Notebooks: the `azure` extra added to each `%pip install` line, other extras kept.
- Tests first; full suite 2,833 passed. Environments: dev. No rule change: an agent may merge it when green.

Nothing blocking.
