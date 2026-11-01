# Tasks: the study and GPU encoder tables under the gold conventions (spec 031)

- [x] T001 [US1] Failing tests: gold names and model for `dim_study_note` and `benchmark_metric`, `_mm`, `prediction_rows`, notebook and job checks
- [x] T002 [US1] AGENTS.md `_mm` suffix; `gold_names.py` tables, `RENAMED`, `MERGE_KEYS`
- [x] T003 [US1] `gold_model.py`: both tables, `study` area
- [x] T004 [US1] Benchmark notebook writes `dim_study_note` (overwrite) and `benchmark_metric` (replace by `run_id`)
- [x] T005 [US1] GPU encoder notebook writes `fact_prediction` by `replace_batch`; `results_store.prediction_rows`
- [x] T006 [US1] Migration turns string `_ts` columns into timestamps
- [x] T007 Regenerate the gold diagrams; update docs; full test suite
