# PR 682 review: more context for the same agent, pre-registered: two full arms, a baseline of 21, no claim (#674, #678)

Reviewed against `.claude/review-rubric.md` and AGENTS.md. A read-only reviewer went over the range
`2b50e94..fd3bc54` (code, tables and prose) without this session's conclusions; each of its findings was then
checked against the code and the tables before anything changed. What it found is below, with what was done.

| Check | Result |
|---|---|
| Branch `feat/674-028-context-run`; `Closes #674` and `Closes #678` (the batch key, found while collecting); spec 028 T026 | ok |
| The three GPU kernels were run by hand on the owner's word; merging starts no run and publishes nothing | ok |
| The plan and its addendum hash to the values recorded on issue 674 (`1b517a…d7c4` at 14:39 UTC, `7121f1…0f29` at 14:56 UTC); both context files hash to the values the plans pin | ok |
| Each arm's rows and resolved count (21 and 0, 93 and 4, 93 and 5), the three Wilson intervals, both paired tables (21 pairs, 72 left out, no discordant pair, p = 1.00) and `graph` against `report` (1, 4, 3, 85) recomputed from the tables | ok |
| The 21 tasks the baseline ran are the first 21 of the seeded order | ok |
| The README says what happened to the baseline arm before it gives a result, and claims nothing for either context | ok |
| Controls on the collecting machine before any patch was scored: reference patch 93 of 93, empty patch 0 of 93; the same verdict as the committed table in 186 of 186 rows, the same exit code in 184 | ok |
| Each arm's patches were verified twice (two collections): no row of any table changed | ok |
| Scans of the whole diff, data files included: no secret, no personal data (ids, counts and hashes), no organisation's plan or partnership, no wording the rules forbid | ok |
| New scripts read paths from `health_transformation_lab_nlp.paths`; the order takes a seed; writes merge on `instance_id`; every row of an arm's table carries `run_ts` (#678), and the development-set table is backfilled | ok |
| `pytest -q tests`: 2,433 passed, 4 skipped before the review's fixes; the 111 tests of every file changed since pass | ok |
| The Kaggle allowance: the three kernels used all of it. The README gives the account's own quota readings and says the rerun is owed (#681) | note |

Nothing blocking.

## What the review found, and what was done

Should fix, all checked and fixed in `91ad05d` unless it says otherwise:

1. **"Not run" was decided from zero model calls alone.** Reproduced with the shape of the hints defect of
   November 10 (a live server, no model call, the submission's own prompt at fault): the row was dropped as "no
   answer from the model server", and the kernel's stop rule fired. A task now also has to have ended at its time
   limit or on a server error. The statement arm's 60 are 33 and 27 of those, so nothing in the tables changes.
2. **The settings held counts where the README said "the reason for each".** They now hold one record per task
   not run: the reason, how it ended, and after how long.
3. **"5 of the 8 had been resolved from the statement alone" is 6.** `htlnlp_144` was resolved by the first run
   of `agent_reruns/gemma-4-e4b-it_graph_tools.csv`. The README now reads every earlier table and says those
   runs were another harness, budget or checkpoint. "9 tasks, 8 of them core" was right.
4. **The rerun (#681) cannot yet be joined to its arm.** Partly done: a rerun's order is now recorded in its
   settings (`sample.order_of`) and a rerun id that was not in the first run is an error. Still open, and written
   into #681: `70_context_pairs.py` reads one `statement` table, so the rerun's rows have to be added to it or
   the script taught to read both.
5. **`--context` without `--label` would have written into the table of November 10.** Refused now.
6. **Overclaiming in the README.** The core-split count is labelled as a description in the short statement; "is
   not a task its context was needed for" became "is not shown to be"; "with the report the agent stopped sooner"
   is gone; the tables that set 21 tasks beside 93 say they are not like for like. Added: when the reading of
   "agent phase did not start" was coded (19:00 UTC, after the `report` arm was collected), and what the other
   reading gives (4 and 5 discordant pairs, p = 0.125 and 0.0625: still no claim).
7. **The allowance's rate was stated as Kaggle's rule.** It is now the account's own three quota readings.

Nits fixed: one of two identical definitions of `build_competition_batch`; the help of `--ids` in script 70; the
paired tables' measure columns are `<arm>_arm_<measure>`, so the graph arm's tool calls are not mistaken for calls
to a graph tool; the batch's settings no longer say each task ran alone in a kernel; the README says the report
lists every public function the test files called, passing tests included, cut to the first 15 by name, and how
`context_run_controls.csv` was made (no single command writes it).

Not fixed, and why:

- `is_import_error` means two things: in `trace_reach.csv` (the 51 edit tasks, one test run) and in
  `failure_report_shape.csv` (all 93, a run that goes on past files it cannot import). They disagree on 6 of
  the 51. The second is the one the report arm's split uses. Worth one name each; not in this change.
- The kernel's call to `server_gone` and the runner's not-run block are tested as functions, not through
  `run_batch`, which needs Kaggle. The first real use is the rerun of #681.
- The paired and shape tables carry no batch key. They are derived from tables that do.
- Tests and code land in the same commits, so the order cannot be read from history. Each test here was run and
  seen to fail before its code was written.

## Notes
- The experiment does not answer its question. Its baseline arm ran 21 of 93 tasks, with one of the core
  split's 17 among them, and every fix of the other two arms is in a task the baseline did not run.
- The kernel had no check for a model server that dies mid-run, only for one that never starts. That cost almost
  four hours of a four-L4 session and, with it, the allowance the rerun needed.
- The estimate given before the run counted a four-L4 session at its wall-clock time. The account's quota
  readings show about twice that.
