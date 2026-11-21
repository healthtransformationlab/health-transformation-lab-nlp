# Feature Specification: How each model ranks, and what drives its score

**Feature Branch**: `feat/863-042-model-drivers` (US1), `feat/864-042-model-drivers-uc` (US2)

**Created**: 2026-11-17

**Status**: draft

**Input**: The owner asked on November 17, 2026: "take the evaluation format for multiple models that we used in the
agent competition and apply in the readme and drilldown to nlp - how we rank each model the features of each models
that are driving the score and loading the traces score and as much information to databricks as possible with
explanations".

> Personal learning project, not affiliated. Synthetic charts, scored against the generator's answer key: agreement
> with it, not clinical accuracy. No patient data.

## Why

The PerioBench leaderboard (`docs/results.md`) ranks 53 methods with a 95% rank range, but it doesn't say which
differences between two models are more than chance, or why one model scores more than another. The agent
competition (gemma-developer-agent `docs/findings.md`) compared its agents in a format that answers both:

1. a ranked table with an exact McNemar test on the same tasks against the leader;
2. pairs that change one thing, tested the same way, with reruns of the same thing as the noise floor;
3. which task facts decide outcomes, as an AUC with and without the agent's own features.

Applied to the 43 methods that read the chart note, the same format gives (`docs/model_drivers.md`, from the
committed predictions):

- the leader, modernbert-large+rules4 (203 of 223), is not distinguishable from 9 of the other 42;
- chart facts predict a correct reading with AUC 0.80 (0.73 to 0.86), model features 0.52; how the note states the
  diagnosis (L1, L2, L3) is the biggest driver;
- a second training seed moves a count by up to 6 charts, as much as the median effect of the stage 4 rule or of a
  larger model.

On Databricks the predictions are already in `fact_prediction` and `fact_llm_call` (spec 016), but none of the
ranking, the tests or the drivers are, and the LLM reader calls aren't traces the MLflow UI can show or score.

## User stories

### US1 - Each note-reading model ranked, paired against the leader and its neighbours, with what drives its score (P1) #863

- `docs/model_drivers.md` (drill-down) and a block in `docs/edr/README.md` (the study page), generated from committed
  results; the landing README links to the drill-down.
- Seven tables in `data/datasets/model_drivers/`: `model_rank`, `model_feature`, `model_contrast`,
  `model_feature_effect`, `chart_feature_effect`, `driver_fit`, `driver_drop`.
- **Independent test:** `python/tests/test_model_drivers.py`: the counts reproduce the leaderboard, every contrast
  differs in exactly one feature, the committed outputs exist; `scripts/74_model_drivers.py --check` exits 1 when one
  is stale.

### US2 - The ranking, its drivers and the LLM readers' traces and scores load into Databricks, with comments that explain them (P1) #864

- The seven tables load into `health_transformation_lab.gold_perio_bench` with table and column comments, plus the
  batch key (`run_id`, `run_ts`, `git_commit_sha`); a load overwrites them (idempotent).
- The MLflow experiment `/Shared/perio-bench-model-ranking` holds one run per method (features as params, scores as
  metrics) and one trace per LLM reader call (input, output, tokens, latency), with code-scorer assessments
  (`is_correct`, `is_unsafe_error`, `is_wrong_stage`). A trace already present (tag `trace_key`) is skipped.
- **Independent test:** with a fake client the loader writes each table with its comments and each trace once; a
  second load writes no trace. On the dev workspace the row counts and the leader's 203 match the CSVs.

### US4 - Should the tooth-loss model use another kind of model? (P2) #867

- The tooth-loss model (spec 029) in the same format, on the plan's held-out teeth, for both label sets and both
  predictor sets: each model's AUC, Brier score and calibration slope, with patient-bootstrap 95% CIs. Paired AUC
  and Brier differences against the best pre-specified model on the same resamples. Drivers by SHAP, by permutation
  and by the AUC lost when refitting without each one. Stability over 5 generator seeds.
- Post-hoc candidates (elastic-net and spline logistic, random forest, histogram gradient boosting, EBM) carry
  `is_prespecified = false` and sit outside the analysis plan; adding one to it needs a dated plan amendment.
- `docs/tooth_loss_drivers.md`, four `tooth_loss_*` tables in `data/datasets/model_drivers/`, loaded into
  `health_transformation_lab.gold_opendental_perio` with comments, and the MLflow experiment
  `/Shared/tooth-loss-model-comparison` (one run per model; a second load of the same commit skips them).
- **Independent test:** `python/tests/test_tooth_loss_drivers.py`: the plan's two models reproduce
  `tooth_loss_model.run` exactly; `scripts/78_tooth_loss_drivers.py --check` exits 1 when an output is stale.

## Requirements

- **FR-001** Every number on the pages comes from the committed predictions; nothing is rerun.
- **FR-002** Counts read after the runs are labelled described, not tested; each pair has its own exact McNemar p,
  and pooled counts over pairs are never tested (the pairs share charts).
- **FR-003** A contrast is a pair that differs in exactly one model feature; seed pairs are shown as the noise floor.
- **FR-004** Names follow "Data names": typed suffixes, `is_` booleans, never a bare `name`, `type` or `value`.
- **FR-005** No trace holds a secret: text goes through `telemetry.scrub_value` (ADR 0010). The notes are synthetic.
- **FR-006** Writes are idempotent: tables overwrite; traces skip a `trace_key` already in the experiment; runs skip
  a method already logged for the same `git_commit_sha`.

## Success criteria

- **SC-001** A reader finds in one page which models are distinguishable from the leader and which features matter
  beyond rerun noise.
- **SC-002** On Databricks, `select * from gold_perio_bench.model_rank` returns 43 rows whose comments explain every
  column, and the experiment shows the LLM calls as traces with their assessments.

## Risks

- **The experiment is made by the loader, not the bundle.** An experiment's trace location can't be changed once it
  is made (spec 041), and the loader makes `/Shared/perio-bench-model-ranking` with its traces in
  `ops_agent_trace` under the prefix `perio_reader` the first time it runs. Declaring it in
  `databricks/resources/agent_traces.yml` afterwards would clash with the existing name, so the bundle declaration
  waits for a decision (an ADR) on whether to adopt or rebuild it.
- **Trace writes are one call per assessment.** 669 traces with five assessments each take minutes on Free Edition;
  a rerun skips what is there.

## Out of scope

- New model runs (a GPU run follows AGENTS.md's Kaggle GPU rules and is not part of this spec).
- Interactions in the driver fit (a model feature that helps only stage 4); the leader-only columns show where.
- A Genie space over the tables.
