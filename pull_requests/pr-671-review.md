# PR 671 review: does the failing test's trace lead to the fix? (#670)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

| Check | Result |
|---|---|
| Branch `data/670-028-trace-reach`, `Closes #670`; spec 028 T023 | ok |
| Test first: six tests in `test_trace_reach.py` failed before the plugin and the script (one end to end, a tiny package and a failing test under pytest with the plugin), then pass | ok |
| The plugin records names only: the package's functions called during each test, the package's frames on each failure's traceback, and a collection error's type, missing name and module; no arguments, values or output | ok |
| "What the spans record": only public functions count, since every public function in the package is `@traced` (spec 014) | ok |
| Each of the 51 tasks runs from its published snapshot plus its test patch, with the snapshot's own package first on the path (44 are from before the package was renamed) | ok |
| Results: an edited node in the trace in 23 of 51 (median trace 7 functions), on a traceback in 7; 15 tests cannot be imported, 9 of them import a name the fix adds and 13 name a module it changes; with the statement's 42, the two reach 48 | ok |
| The trace uses the hidden test, and every place it is reported says so: the context a test-first workflow has, not a fair benchmark condition | ok |
| `data/tasks/trace_reach.csv` holds ids, exit codes, counts and booleans, no text | ok |
| No GPU, no secrets, no real data; merging starts no run and publishes nothing | ok |

## Notes
- What this says for the owner's question (would telemetry context help the agent?): the trace adds the fix's
  location in 6 tasks the statement misses, and the import errors give the exact missing name in 9. The second is
  the screen's finding (tests need names the statement never gives) seen from the failure report. A GPU run with and
  without that context should start with those tasks.
