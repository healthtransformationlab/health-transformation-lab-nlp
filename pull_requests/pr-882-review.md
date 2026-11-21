# PR 882 review: the trace loader takes the official verifier's verdicts (#881)

Reviewed against `AGENTS.md`, `CLAUDE.md` and `.claude/review-rubric.md`.

| Check | Result |
|---|---|
| One issue with its four parts, branch `chore/881-041-loader-verdicts`, `Closes #881` | yes |
| Test first | the four new tests and the changed root-span test failed on main, then passed: `test_load_agent_traces.py` 20 passed |
| Contract | `--verdicts`, `read_verdicts`, the `verdicts` argument of `task_trace` and `load_run`, the tag `verdict_source_code` and the message, all as the issue names them |
| Data names | `verdict_source_code` has the `_code` suffix for a value from a fixed set (`kernel`, `official_verify`) |
| Telemetry | no row data in logs; the message names only the task id |
| Writes | unchanged: a trace_key already in the experiment is still skipped |
| Docs | one bullet in `docs/telemetry.md`; wording, organisation-name and benchmark-order tests pass |

## Findings

- **Not blocking:** traces loaded before this PR have no `verdict_source_code`. A null means the kernel's verdict.
- **Not blocking:** a run graded by the verifier and loaded earlier without `--verdicts` would keep its kernel verdict, because its trace keys are already there. None of the five runs this is for has been loaded yet.

Nothing blocking.
