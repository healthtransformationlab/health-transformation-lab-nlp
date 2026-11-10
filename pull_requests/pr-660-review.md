# PR 660 review: count the tasks whose fix the code graph does not reach (#659)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

| Check | Result |
|---|---|
| Branch `data/659-...`, `Closes #659` | ok |
| Test first: `test_graph_coverage.py` failed without the script (5 errors), passes with it | ok |
| The rule cannot take a class for a module (a module is the parent of a node whose parent is not a node); tested | ok |
| A module the patch adds counts as outside the base commit's graph; tested, and stated in the script and the PR | ok |
| Counts reproduced a second way (every dotted prefix of a node id as a module): 62 and 31 both times | ok |
| Script number 63 is free on `main`; `test_script_numbers.py` passes | ok |
| Written whole on each run (idempotent); a missing graph file fails naming it | ok |
| No secrets, no real data, no organisation names; wording and conventions tests pass | ok |
| Not a published file: `kaggle/publish_tasks.py` does not include it, so the dataset's documentation is unchanged | ok |

## Notes
- The count is of files, and a reference patch carries documents and data too, so 155 of 1,173 files understates how
  much code the graph covers. The per-task figure (62 of 93) is the one to quote.
- A task whose fix is "in the graph" may still change other things the graph does not reach.

## Blocking
None.
