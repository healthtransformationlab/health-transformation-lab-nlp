# PR 673 review: what the trace and the import errors each add to the statement (#672)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

| Check | Result |
|---|---|
| Branch `fix/672-028-trace-credit`, `Closes #672`; a fix with a regression test, so no spec of its own (spec 028 T023 is updated) | ok |
| Test first: `test_the_summary_says_what_the_trace_and_the_import_errors_each_add_to_the_statement` failed before the change (no such keys) and passes now; the six earlier tests still pass | ok |
| The split on the committed table, run with the new summary: statement 42; the trace adds 1; import errors add 5; the report reaches 36, 6 of them beyond the statement; statement or report 48 | ok |
| `trace_not_statement_count` now counts a traceback as part of the trace. On the table it is still 1: every task with an edited function on a traceback also has it among the functions called | ok |
| A task with several test files can be reached by both the trace and an import error, so the two parts need not sum to the whole; the docstring says so. On the table they do (1 + 5 = 6) | ok |
| The review of pull request 671 is a record and stays as written; the correction is added under it with its date and this issue's number | ok |
| No data changes: `data/tasks/trace_reach.csv` is untouched | ok |
| No GPU, no secrets, no real data; merging starts no run and publishes nothing | ok |

## Notes
- Where the wrong sentence went: only into that review's note. Spec 028 T023 and the description of pull request
  671 both say "the trace or the import error", which is right. The paper had not been updated with it.
- What it means for the owner's question (would telemetry context help the agent?): spans of the functions a
  failing test calls would point to the fix in one more task than the statement does. The larger gain is the plain
  import error, which names the module to change in five. A run with and without that context should send the
  error text first, not the spans.
- Not checked here: whether a model uses either. These are counts from the files, not agent runs.
