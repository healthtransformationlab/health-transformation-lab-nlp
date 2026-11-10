# PR 640 review: 028 AI1: record the competition's own verifier on the task set (#636)

Reviewed against `.claude/review-rubric.md` and AGENTS.md by the authoring session (no reviewer subagent run).

| Check | Result |
|---|---|
| Branch `data/636-028-official-evaluator-check`, `Refs #636` | ok |
| The table's counts (93 of 113, 0 of 113, 2 of 25) match the README beside it | ok |
| The 20 unresolved reference patches each carry a reason | ok: 12 withheld files, 6 `PYTHONSAFEPATH`, 2 skipped required tests |
| Nothing from the competition is committed (no wheel, no guide text) | ok: the scripts import the evaluator; the README names its source |
| No data, metric, label or published file changes | ok: three scripts, one table, one README |
| Column names follow the typed suffixes (`_code`, `_text`, `_seconds`, `_name`, `_ts`, `is_`) | ok |
| Secrets, PHI, organisation claims | clean |
| `ruff check` on the new scripts; five guard tests | clean; 39 passed |
| Full suite and R parity | not run here; CI runs them |

## Should fix (non-blocking)
- **The scripts have no tests and are not wired into the builders.** They exist so the table can be reproduced. When
  #636 adds the `conftest.py` to the snapshots, the adapter belongs in `task_graph.snapshot` with a test, and these
  two helper scripts can go.
- **`run_ts` is one rounded time for every row** (2026-11-10T03:00:00Z), not each row's own. The runs took about
  twenty minutes in all.
- **"As published" was checked on three tasks**, with the evaluator's own command line. The cause is the same for
  every task, but only three were run that way.

## Notes
- This is a record of a measurement, kept before the task set is changed. It also shows two things about our own
  earlier claims: `calib:oracle`'s 111 of 113 was measured from this repository's history, not from the published
  snapshots, and twelve published tasks cannot pass from their snapshot at all.
- The environment had this repository's test dependencies but not the package itself, so the tests imported the
  code from each snapshot.

## Blocking
None. Nothing is published and no limited compute is used, so this can merge when CI is green.
