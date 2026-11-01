# Feature Specification: the study and GPU encoder tables under the gold conventions

**Feature Branch**: `feat/233-026-gold-names-idempotent` (first opened as `spec/233-026-study-gold-names`, PR #238; renumbered 031, the next free spec number, since 026 to 030 were taken meanwhile)

**Created**: 2026-10-28

**Status**: implemented

**Input**: the owner asked to bring the gold tables that don't yet follow AGENTS.md "SQL and data names" into
line: `encoder_gpu_predictions` (also written by plain append with no batch key, against "Failures, retries and
reruns"), `labeled_notes`, `benchmark_results`, and any dq_* / grader_* table not yet in
`diagrams/_build/gold_model.py`. Spec 018 left the first three for "when they're next touched".

> Personal learning project; synthetic data only. No metric, label rule or result changes: the same rows under
> convention names, with each write made idempotent.

## User stories

### US1 - Every gold table the jobs write follows the conventions and is written idempotently (P1) #233

| Was (`gold_perio_bench`) | Now | Writer and write |
|---|---|---|
| `labeled_notes` | `dim_study_note`: one row per synthetic study note, its generator label and split | Benchmark: overwrite, rows carry `run_id`, `run_ts`, `git_commit_sha` |
| `benchmark_results` (plain append) | `benchmark_metric`: one row per job run, model run, metric and class | Benchmark: replace by `run_id` (the job run), so a retry or rerun of the same run adds nothing |
| `encoder_gpu_predictions` (plain append, no key) | rows in `fact_prediction`, `source_code = databricks` | Encoders on GPU: replace by `(source_code, run_id, method_name)`, as the MedGemma reader does |

- Columns follow the suffix table. `label` is `truth_status_code`, `split` is `split_code`, `class` is
  `class_status_code`, `value` is `metric_ratio` (every metric `score` writes is 0 to 1), and `timestamp` is
  `scored_ts`. `score`'s own `run_id` (one per model fit) is `model_run_id`; `run_id` is the Databricks job run.
- AGENTS.md gains one suffix, `_mm`: a length in millimetres (`double`), for `max_probing_depth_mm` and
  `max_cal_mm`. `teeth_lost_perio` is `perio_lost_tooth_count`.
- Both tables are declared in `gold_model.py` and `gold_names.py`; the ERDs, `data_model.md` and the architecture
  diagram are regenerated.
- The tables that exist in dev (`labeled_notes`, `benchmark_results`) are carried by the gold-name migration
  (`RENAMED`). `benchmark_metric` keeps every earlier run (merge key `model_run_id, metric_code,
  class_status_code`); `dim_study_note` is rebuilt every run. `encoder_gpu_predictions` was never written in any
  workspace (dev's `information_schema` has no such table), so it has no migration.
- The GPU encoder job's predictions are already the CSVs Load results would load: as source `databricks`,
  Load results treats their versions as loaded and doesn't add them again as `repo`.

The dq_* and grader tables (spec 019) are already declared in `gold_model.py` and `gold_names.py`: no change.

## Out of scope

- The OMOP tables (`person`, `visit_occurrence`, `measurement`, `note`) keep their official names.
- The Postgres `perio_chart` view and the CSV files (`data/labels/labeled_notes.csv`): pandas frames and files keep
  their analysis names (AGENTS.md).
- Running the Benchmark or GPU encoder jobs; this changes what they write, not when they run.
