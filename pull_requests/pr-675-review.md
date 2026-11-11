# PR 675 review: the agent on a seeded 40 of the competition's development set (#668)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

| Check | Result |
|---|---|
| Branch `feat/668-028-devset-run`, `Closes #668`; spec 028 T024 | ok |
| The GPU run was made by hand on the owner's word ("Do the 40", November 11, 2026); merging starts no run and publishes nothing | ok |
| Competition data: the kernel attaches the competition and reads each task from its mounted files; the bundle holds the submission and the order only (a test checks it). The committed tables hold ids, counts, verdicts, exit codes and seconds. The host has said on the Paper Track forum that derived data keyed by task id may be published (topics 749803 and 757562) | ok |
| Controls before the agent's verdicts are read: reference patch 24 of 40, empty patch 1, so 23 verifiable; the agent's count is over those 23 only | ok |
| The row of `fastapi_14851` says resolved with an empty patch. The README says it is kept and not counted, and why | ok |
| Resolved 3 of 23, recomputed from the table and the controls; Wilson interval 4.5 to 32.1%; Fisher's exact p = 0.24 against 0 of 20, computed in the README's own text from the hypergeometric counts | ok |
| The README does not claim the two sets differ by resolved tasks | ok |
| Why 16 are not verifiable: the cause is read from the kernel's log for the sandbox and from the output for 7 tasks, and the README says it is inferred for the other 9 | ok |
| `outside_workspace_call_count` is 0 in all 40 rows: with the competition mounted, no tool call named a path outside the workspace | ok |
| Telemetry: spans keep names, counts and seconds; a test checks a span never keeps a request or reply. The rollup is self time, and a test checks a task's sections sum to its whole time | ok |
| GPU: each task has GPU-hours and energy; `estimated_cost_usd` is empty with the reason in `price_basis_text`, since no L4 price is declared | ok |
| Test first: `tests/test_run_telemetry.py` failed before `71_run_telemetry.py` existed; one expectation was loosened afterwards to allow for shares rounded to 0.01 | ok |
| `script_seconds` is empty in the 40 rows: a batch kernel's result has one start and end for the whole kernel, not per task. The kernel's 94 minutes are in the README | note |
| No secrets, no real data, no organisation names; wording and benchmark-order tests pass | ok |

Nothing blocking.

## Notes
- Eight of the 40 runs ended when a prompt passed the model's context window (32,768 tokens, of which 16,384 are
  kept for output). On large repositories that is the agent's commonest hard stop, ahead of the 5-minute limit (2).
  It is a setting of the submission, not of the harness, and worth an issue of its own in gemma-developer-agent.
- The 23 verifiable tasks are 15 rich and 8 fastapi. A sandbox with pip would make the other 16 verifiable; that
  needs the kernel's image to provide `ensurepip`, which this project does not control.
- A dollar estimate for L4 time needs a declared price with its source and date in `ops/cost_settings.yaml`. The
  price page the T4 figure came from could not be reached from the session that made this change.
