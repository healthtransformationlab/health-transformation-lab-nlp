# Implementation Plan: the study and GPU encoder tables under the gold conventions (spec 031)

**Spec**: [spec.md](spec.md) · **Issue**: #233 (US1)

## Approach

1. **Names.** `gold_names.TABLES` gains `dim_study_note` and `benchmark_metric` (analysis name → gold name);
   `RENAMED` maps `labeled_notes` and `benchmark_results` to them, and `MERGE_KEYS["benchmark_metric"]` keeps
   earlier runs when the migration finds both. AGENTS.md and `test_sql_conventions.py` add `_mm`.
2. **Model and diagrams.** `diagrams/_build/gold_model.py` declares both tables in a new `study` area;
   `gold_erd.py` and `gold_architecture.py` regenerate the ERDs, `data_model.md` and the architecture, and
   `drawio_render.js` the PNGs (diagrams/_build/render.md).
3. **Benchmark job** (`01_run_benchmark.py`): `dim_study_note` through `to_gold`, overwrite; `benchmark_metric`
   through `to_gold` and `delta.replace_batch` keyed by `run_id`, which the job passes as `{{job.run_id}}`. The
   `ai_query` cell reads the new names.
4. **GPU encoder job** (`08_encoder_gpu.py`): each method's CSV through `results_store.prediction_rows`, then
   `to_gold` and `replace_batch` into `fact_prediction` keyed by `(source_code, run_id, method_name)`; the job
   passes `run_id: "{{job.run_id}}"`. `run_rows` uses the same helper for its predictions.
5. **Migration.** `renamed()` in `11_migrate_gold_names.py` turns a string `_ts` column into a timestamp, so
   `benchmark_results.timestamp` (ISO text) lands as `scored_ts`.
6. **Docs.** `docs/gold_tables.md`, `docs/deployment.md`, `r/README.md`, the 08 notebook header.

## Tests first

- `test_gold_names.py`: a benchmark frame (from `eval/score.py`) and a labelled-notes frame (from `build`) become
  their declared gold tables; the old names are copied or merged by `migration_plan`.
- `test_gold_model.py`: the two tables are declared.
- `test_sql_conventions.py`: `_mm` is a `double`.
- `test_results_store.py`: `prediction_rows` keeps the run key and the file's SHA-256.
- Notebook checks: no plain `mode("append")` in 01 and 08; both use `replace_batch`; jobs pass `{{job.run_id}}`.
