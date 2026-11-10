# PR 663 review: does embedding search find the fix where names and call edges do not? (#662)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

| Check | Result |
|---|---|
| Branch `data/662-...`, `Closes #662` | ok |
| Test first: `test_statement_search.py` failed without the script (5 errors), passes with it (5 tests); the model is not loaded in tests | ok |
| The query is embedded as the nodes were: the same model and pinned revision (`task_graph.EMBED_MODEL`, `EMBED_REVISION`), the query prompt against the nodes' document prompt, cut to 256 dimensions and renormalised | ok |
| Run twice from separate code (a first script in a scratch folder, then this one): the same best rank on all 93 tasks | ok |
| The edited nodes come from `graph_coverage.csv` (#659); an edited node with no vector stops the run naming it; none did | ok |
| Labelled as a count from the published files, not an agent run, in the script, its output and the spec | ok |
| A missing `HF_TOKEN` fails at once, naming it; the token is read from the environment and never printed | ok |
| Script number 64 is free on `main`; `test_script_numbers.py` passes | ok |
| Written whole on each run (idempotent); column names follow the suffix rules (`_count`, `_num`, `is_`) | ok |
| No secrets, no real data, no organisation names; merging starts no run and publishes nothing | ok |

## Second commit: what the baseline's time bought, by graph reach

| Check | Result |
|---|---|
| Test first: `test_cost_by_graph_reach.py` failed without the script, passes with it (3 tests) | ok |
| Every published task gets exactly one kind; the five counts add to 93 (31 + 11 + 22 + 20 + 9) | ok |
| Cost is the agent's own time, which all 48 runs record. A first version used the session's GPU-hours and silently dropped the three earliest runs, two of them resolved; the counts came out as 45 run and 3 resolved, which is how it was caught. A run with no recorded time now stops the script | ok |
| 48 run and 5 resolved match the paper's baseline; the shares add to 100% within rounding | ok |
| Labelled as a description of one run under the tight limits, cheapest tasks first, not an estimate | ok |
| No model, no GPU; merging starts no run and publishes nothing | ok |

## Notes
- The split is of 48 runs with 5 resolved. "3 of 5 where a name or call edge leads to the fix" is a count, not a
  rate to generalise from.
- "In the first ten" is of a median 398 nodes. It says the edited code is near the top of what a similarity search
  returns for the statement; it does not say a model asks for that search or acts on it. In the paired rerun the
  model called a graph tool in 4 of 23 runs.
- The query is the statement and hints as published. A model would search with its own query, which may do better
  or worse.
- One embedding model, the one the nodes were made with. The competition does not name its own.

## Blocking
None.
