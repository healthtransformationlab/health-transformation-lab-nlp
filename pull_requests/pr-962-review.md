# PR 962 review: AccessBench in Databricks' MLflow evaluation view (045 US6, #961)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Verdict

Nothing blocking. Merge once CI is green (the owner asked for agent PRs to merge when green, 2026-11-25).

## Checked

- **Test first:** `test_access_mlflow.py` failed at import before `access_mlflow.py` existed; 6 tests now pass
  against a local SQLite MLflow store.
- **No model calls:** the scorers only report the batch's stored grades, so logging costs nothing and can be redone
  for a past run. A judge parse failure shows as an error, never as a grade.
- **Optional, never blocking:** the notebook logs after the gold write and only warns if MLflow fails; an empty
  `experiment_id` skips it.
- **Verified live:** `82_access_mlflow_backfill.py --run-id 608662392694095` logged 98 answers into experiment
  2752130492804746, one evaluation run per model plus one for the controls.
- **Telemetry:** public functions are `@traced`; the script calls `telemetry.setup()` and `start_script`.
- **Settings:** the job's new `experiment_id` parameter is the bundle's existing experiment; no new setting or secret.

## Not blocking

- The judge's free-text rationale isn't stored in gold, so MLflow shows per-point verdicts and spans, not the
  judge's paragraph. Storing it would be a new gold column.
