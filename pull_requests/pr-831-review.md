# PR 831 review: forward a development run's results to Application Insights

Closes #830. Reviewed against `.claude/review-rubric.md` and AGENTS.md (secrets, telemetry).

- Secrets stay in the dev environment; the session never sees them. The register names the new user of both credentials.
- Span attributes are numbers and short labels; a test asserts task text and patch content are absent.
- Telemetry stays optional: off without the setting; the export result is printed, as the watcher does (#801).
- Tests first; related suites 380 passed. No compute or rule change: an agent may merge it when green.

Nothing blocking.
