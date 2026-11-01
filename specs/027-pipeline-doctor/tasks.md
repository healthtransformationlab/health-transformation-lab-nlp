# Tasks: the pipeline doctor

**Tests**: required (test-first): each implementation task follows its failing test.

## US1 - Every failure is classified from the tables, rules first
- [x] T001 Failing tests in `python/tests/test_doctor.py`: `signals()` gives freshness, volume ratio, schema change, quality ratio and duration ratio for a run against the pipeline's last ok runs; `classify()` returns each of the seven classes on the incident rows, and the signals it used
- [x] T002 Implement `signals` and `classify` in `python/health_transformation_lab_nlp/doctor.py` (`@traced`)
- [x] T003 `ops/pipeline_config.yaml` with one entry per job in `jobs.yml`; `load_config()` test and implementation

## US2 - Every recommendation comes from the runbook's allow-list with its impact
- [x] T004 Failing tests: `recommend()` returns the first allowed action, moves to the next one when retries are exhausted, never returns an action off the list, lists downstream names one hop away, carries severity and owner, and drafts a notification without note text
- [x] T005 `ops/runbook.yaml` (seven classes) and `recommend` implementation

## US3 - A failure class earns automation and can lose it
- [x] T006 Failing tests: `graduation()` says `automatic` after N matches on a reversible class, `recommend_only` after two misses, `recommend_only` with fewer than N decisions, never `automatic` for a non-reversible class
- [x] T007 Implement `graduation`

## US4 - The doctor is measured against the repo's own incidents
- [x] T008 `data/ops/incident.csv`: the nine incidents from the spec as run rows with the action taken
- [x] T009 Failing test: `evaluate()` reports per-class classification accuracy, recommendation agreement and share resolved without the LLM, with 95% intervals; then implement

## The ablation
- [x] T016 Failing test: `ablation()` reports the overall metrics per condition (full, no_config, no_conventions, no_lineage, no_metrics, no_history); switching a piece off costs accuracy, impact or LLM load; then implement
- [x] T017 `data/ops/lineage_edge.csv` and `load_lineage()`, covering every pipeline with an incident

## US7 - A separate, reusable package adopted by two projects
- [ ] T018 Extract `doctor.py`, `ops/*.yaml` schemas and the eval into its own repo, `healthtransformationlab/pipeline-doctor`; this repo installs it
- [ ] T019 Second project adopts it: its config, runbook, lineage and incident set; run `evaluate` and `ablation` there
- [ ] T020 Paper draft: the four tables as a contract, the ladder, the ablation on both projects, limits

## US8 - Forecasting and alert batching (in the shared package)
- [x] T021 `pipeline-doctor` `forecast.py`: credential expiry, deprecation (dated or marked deprecated), cost and duration trends, volume drift, schema-change frequency; `digest.py`: route now/daily/weekly, dedupe, repeats, level review, render (46 tests there)
- [x] T022 `ops/dependency_inventory.csv` with no invented dates; first forecast on the real register recorded in spec.md
- [ ] T023 This repo installs `pipeline-doctor` and drops its own `doctor.py` copy (US7 T018); a `pipeline_forecast` job runs the forecaster and writes the digests

## US5 - The doctor runs as a job and writes its decisions
- [x] T010 Failing bundle tests: job `pipeline_doctor` runs `13_pipeline_doctor.py` (12 was taken by `12_load_open_dental.py`) with catalog, schema, judge endpoint and `max_usd`; writes are delete-then-append by `run_id` (`test_bundle.py`, `test_delta.py`)
- [x] T011 Notebook: read `system.lakeflow.job_run_timeline` and the span export into `fact_pipeline_run`; call the module; write `fact_remediation_decision`; notification at the runbook severity. The decisions live in `doctor_job.py` (`test_doctor_job.py`); the notebook only reads and writes. Also writes `fact_pipeline_signal` for the dashboard
- [x] T012 Grader dashboard: the signals per pipeline (spec 019 pattern; six since cost was added): `dashboards.doctor_dashboard`, `databricks/dashboards/pipeline_doctor.lvdash.json`

## US6 - The LLM rung is evaluated like any other model here
- [ ] T013 Root-cause prompt (run row + last N runs + lineage one hop + runbook; never note text); `make_judge` Guidelines scorer on the runbook rules; no-PHI scorer on every trace
- [ ] T014 Score the incident set; add the result to `docs/dataops.md` with intervals

## Polish
- [ ] T015 `docs/dataops.md`; link from `docs/telemetry.md` ("next: the pipeline doctor"); full Python suite
