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

## Second commit: does the graph lead from the statement to the fix?

| Check | Result |
|---|---|
| Test first: the eleven new tests failed before the code (11 failed, 5 passed), pass with it (16) | ok |
| Node names come from `task_graph._Defs` and `module_name`, the graph builder's own, so a def here is the graph's node | ok |
| Reproduced a second way: a separate implementation (its own diff parser and AST walk, written first) gives the same edited nodes, named nodes and distance on all 93 tasks | ok |
| That implementation's checks: all 1,926 defs in the 159 modified package files are graph nodes whose `text` equals the snapshot's source; no file missing, none unparsed | ok |
| Read by hand: the seven tasks matched only by a backticked name (`runlog.run`, `telemetry.setup()`, `track()`, `fit`, ...) each refer to the edited function; three tasks' hunks read against their rows | ok |
| How much the reading matters, from the first implementation: inserted lines credited to the def above give 54 tasks with an edit and 21 named; without the backtick rule 13 are named; a plain capitalised word (`Status`, `Verdict`) excluded leaves 20 named, 2 joined and 29 not | noted |
| A file the snapshot lacks fails naming it; the table is still written whole | ok |
| Column names follow the suffix rules (`_count`, `_text`, `is_`) | ok |

## Notes
- "Names" is a rule over the text, not a judgement: a statement that describes a function without its name counts as
  naming nothing. The counts are lower bounds on what a reader could work out, and the paper says "names".
- Call edges are followed in either direction. Followed only from caller to callee the two joined tasks could differ;
  the table gives the nodes, so either can be recomputed.
- The count is of files, and a reference patch carries documents and data too, so 155 of 1,173 files understates how
  much code the graph covers. The per-task figure (62 of 93) is the one to quote.
- A task whose fix is "in the graph" may still change other things the graph does not reach.

## Blocking
None.
