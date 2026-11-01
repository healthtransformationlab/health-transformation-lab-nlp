---
pr: 415
branch: feat/233-026-gold-names-idempotent
title: "Name the Benchmark and GPU encoder tables by the gold conventions, written idempotently (spec 031)"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-01
reviewer: agent self-review against the rubric (no reviewer subagent run)
verdict: approve
---

# PR Review: Name the Benchmark and GPU encoder tables by the gold conventions, written idempotently (spec 031)

## Summary
This finishes #233 (spec 031 US1). It supersedes #238: that PR's commits are merged onto current main, and the
spec is renumbered from 027 to 031 because 027 to 030 were taken in the meantime.

The changes:
- `labeled_notes` becomes `dim_study_note`. It is overwritten each run, and every row carries `run_id`, `run_ts`
  and `git_commit_sha`.
- `benchmark_results` becomes `benchmark_metric`, written with `replace_batch` keyed by the job run (`run_id`).
- The GPU encoders write `fact_prediction` (`source_code = databricks`), replaced per (`source_code`, `run_id`,
  `method_name`) with `replace_batch`. `encoder_gpu_predictions` goes.

Both new tables are declared in `gold_names.py` and `gold_model.py`, and the migration carries the old dev tables.
The pipeline doctor's config and lineage (spec 027), which named the retired tables, are updated. Approve.

## Tests
- A new test checks that no pipeline output or lineage edge names a retired gold table. It failed first, on
  `benchmark_result` and `encoder_gpu_predictions`.
- New `legacy_plan` tests cover the study tables. A new test checks that `benchmark_metric`'s merge key is unique
  in a `score()` frame and that `metric_ratio` stays between 0 and 1. All of these pass.
- #238's tests are carried over: gold names and model, `_mm`, `run_prediction_rows`, and the notebook and job
  checks.
- Full suite: 1258 passed, 15 skipped. `ruff check` on the changed modules: clean.

## Secrets, PHI and Claims Scan
Clean.
- **Data:** the data stays synthetic. No metric, label rule or result values change. The rows are the same, under
  convention names.
- **Secrets:** no settings or secrets change.
- **Wording:** checked by `test_wording.py`, `test_bench_order.py` and `test_no_org_references.py`, which all pass.

## Findings
None blocking.
- **Only a Databricks run can confirm:**
  - the migration on dev's real tables: the text-to-timestamp cast and the merge on `model_run_id, metric_code,
    class_status_code`;
  - `replace_batch` on a retried run;
  - that `{{job.run_id}}` resolves in the notebook widgets.
- **`study_benchmark` lists `fact_prediction` as an output:** this was already in `ops/pipeline_config.yaml` and is
  kept so the doctor's impact numbers don't move. Recheck it when the doctor's config is next touched.
- **`llm_reader_run` in the doctor's config:** it is not a gold name (that is `fact_llm_call`). This was already
  there and is outside this issue.
- **PR #238:** it should be closed as superseded once this merges. Its review record
  (`pull_requests/pr-238-review.md`) comes in with the merge, as written.

## Rubric
- Spec: `specs/031-study-gold-names/` (spec, plan, tasks). `Closes #233`. The branch name follows
  `feat/<issue>-<slug>`.
- Every write is idempotent and every row carries its batch key.
- Generated files were regenerated, not edited by hand: `gold_erd.py`, `gold_architecture.py`, and
  `drawio_render.js` for the PNGs.
- The new public function `results_store.run_prediction_rows` is `@traced`.
- Python/R parity is unaffected. The metrics themselves don't change, only the table and column names.
