# PR 642 review: 028 US6: publish only tasks the competition's evaluator verifies (#641)

Reviewed against `.claude/review-rubric.md` and AGENTS.md by the authoring session (no reviewer subagent run).

| Check | Result |
|---|---|
| Branch `feat/641-028-official-verified-set`, `Closes #641`, `Refs #636` | ok |
| Spec first: US6 in `specs/028-dataops-task-set/spec.md`, tasks T013 to T017, issue number beside the story | ok |
| Tests first | ok: 17 failed and 8 errored before the code; all pass after |
| The snapshot still differs from its base only by redacted files, withheld files and the one added file | ok: checked in `snapshot`, and by a test that compares every path's mode and blob |
| A base that already has a root `conftest.py` is refused, with no archive left behind | ok |
| Nothing unverified can be published | ok: `57_gate_tasks.py` filters on the table, and `publish_tasks.check` refuses an unverified task or a missing table |
| Every published file and column is described (`test_kaggle_dataset_docs.py`) | ok: one file, seven columns, one file-specific meaning for `reason_text` |
| `@traced` on the new public functions (`evaluator_verified`, `evaluator_exclusions`) | ok |
| Column names follow the typed suffixes | ok |
| Secrets, PHI, organisation claims; nothing of the competition's is committed | clean |
| Wider test run here (477 passed, 2 skipped) | ok |
| Full suite and R parity | not run here; CI runs them |

## Should fix (non-blocking)
- **The verification table was made on copies of the version 3 snapshots with the file added**, not on snapshots built by this code. T016 runs the evaluator again on the new version's files as published. Until then "verified" rests on the copies.
- **`data/tasks/snapshot_index.csv` is stale after the next build**: every snapshot head changes with the added file. It is refreshed after the publish (T016); nothing reads it at build time.
- **A task the evaluator has not been run on is left out silently unless someone reads `tasks_excluded.csv`.** That is the safe side, and the script prints the count, but a newly mined task will not be published until the table has its two rows.
- **`57_gate_tasks.py` skips the filter when the table is missing.** `publish_tasks.check` then refuses to publish, so nothing unverified can go out, but the two behaviours are worth knowing together.

## Notes
- Our own gate is unchanged: it still runs in a worktree of this repository, where the withheld files exist. The evaluator's table is what removes the twelve tasks that cannot pass from a snapshot.
- The conftest also sets `PYTHONPATH` for processes a test starts. It does not undo the evaluator's `PYTHONSAFEPATH=1`, so the six tasks whose test starts a script importing a module beside it stay out.
- This supersedes pull request 640, whose commits it carries; that one is closed unmerged, and its review file stays as a record.

## Blocking
None. Merging publishes nothing. The publish is a separate workflow run, which the owner asked for on November 10, 2026.
