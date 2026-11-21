# PR 900 review: loader leaves no_test_spec traces without a solved assessment and duplicates them on reload

Closes #899. Reviewed by the author's session; no second reviewer.

## Findings

Nothing blocking.

- **Solved assessment:** with `--verdicts`, `task_trace` returns `assessments=[{"name": "solved", "value": ...}]` and `MlflowTraceClient.write` logs each via `log_feedback`, so org-repo / `no_test_spec` loads are not empty in scorer tables.
- **Idempotency:** `load_run` deletes existing traces for the same `trace_key` then appends (`existing_trace_ids` + `delete_keys`). A second load leaves one trace per key and reports `replaced`.
- **Batch key:** every written trace carries `file_sha256` (of that task's `result.json`), `loaded_ts`, and `git_commit_sha`.
- **Already on main (#894):** `ended_code` ignores the harness "Missing test specification" note; `kernel_grade_code` is `no_test_spec` or `graded`. Not re-scored and not written to Databricks in this PR.

## Compliance

| Check | Result |
|---|---|
| Issue #899 has Problem, Done when, Contract, Read first; branch `fix/899-loader-no-test-spec`; `Closes #899` | ok |
| Failing fixture tests before the fix | ok (`test_no_test_spec_with_verdict_attaches_a_solved_assessment`, replace-by-key, load assessment) |
| No loader run against Databricks; no table writes | ok |
| No push to `claude/*` | ok |

## Checks

- `pytest -q tests/test_load_agent_traces.py`: 25 passed.

## Verdict

Ready to merge when the owner says so.
