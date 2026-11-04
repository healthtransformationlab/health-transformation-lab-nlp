# Tasks: tooth lost to periodontitis (spec 029)

Implementation starts after this spec, plan and tasks are reviewed.

## US1 #369: synthetic extract in Open Dental's table format, own bronze schema

- [x] T001 [US1] Check each table and column in plan.md against Open Dental's source schema ([research.md](research.md));
  `TABLES` is written from it in T003
- [x] T001a #377 Spec, plan and research follow how Open Dental records diagnoses (the practice's own lists,
  changing over time) and treatment plans (one planned procedure, many editable copies)
- [x] T002 [US1] Failing tests: `test_open_dental.py` (seed, unchanged datasets, sources, no truth in the
  extract, rates recovered)
- [x] T003 [US1] `open_dental.py` generator, own random stream; writes the extract and `tooth_loss_truth.csv`;
  two diagnosis lists with an adoption date and lag; planned extractions with their plan copies
- [x] T004 [US1] `<layer>_opendental_perio` schemas and the landing volume in `schemas.py` and
  `unity_catalog.yml`; failing schema and bundle tests first (`fact_tooth_loss_prediction` goes in `gold_model.py`
  with the model, T010)

## US2 #370: one silver row per patient and tooth

- [x] T005 [US2] Failing tests: statuses on hand-built extracts, nothing dated after the loss
- [x] T006 [US2] `tooth_loss.tooth_table` and `planned_extraction` (plan copies counted once); base-R twin and
  parity inputs
- [x] T006a [US2] Failing tests, then the bronze-to-silver data-quality checks after Kookal et al. 2024
  (completeness, accuracy, consistency; FR-009), with planted faults (`open_dental.plant_faults`), plus consistency
  by group (`tooth_loss_dq.group_consistency`); the load job writes `tooth_loss_dq_check` and `tooth_loss_dq_group`
- [x] T007 [US2] Load job `open_dental_load` (`12_load_open_dental.py`): generates the extract into the landing
  volume, bronze as generated, silver cleaned (`open_dental.clean`) plus the answer key; overwrite per run, batch
  keys; deploy starts it when bronze is empty. The silver tooth table joins it with T006

## US3 #371: the model, checked against the hidden truth

- [x] T007a [US3] Pre-specified analysis plan, TRIPOD+AI order ([analysis_plan.md](analysis_plan.md), #395); T008–T010
  follow it, and any change is logged there
- [x] T008 [US3] Failing tests: feature sets, grouped stratified split, metrics, expected-count stage rule
- [x] T009 [US3] Logistic regression and XGBoost on both label sets (completed; completed and planned); scores,
  calibration and stage recount; R twins for metrics and the stage rule. Built as `tooth_loss_model.py` (kept apart
  from the tooth table) and `scripts/51_tooth_loss_model.py` (45 was taken); the Load Open Dental job writes gold
- [x] T010 [US3] `docs/tooth_loss.md`, results labelled synthetic; gold `fact_tooth_loss_prediction`
- [x] T011 Full test suite, `ruff`, R parity; review file for each implementation PR

## US4 #379: ERDs of the Open Dental silver tables and an OMOP alternative

- [x] T012 [US4] Failing tests (`test_silver_erd.py`), then `opendental_silver_model.py`, `omop_silver_model.py` and
  `silver_erd.py`, using `gold_erd.py`'s writer (gold output unchanged); entity and full `.drawio`, `.mmd`, PNGs and
  `diagrams/silver/data_model.md`
- [x] T013 [US4] A third format, the data dictionary (`dictionary_erd.py`, `table_profile.py`): subject areas, fact
  and dimension tables, row counts, each column's nulls, distinct and top values, PHI and open questions marked;
  it fills in once T003 writes the extract

## US5 #381: the rest of a typical research extract

- [x] T014 [US5] The 16 further Open Dental tables in research.md (checked in the source), the silver model and the
  three ERDs, in the reference's subject areas; free text marked PHI
- [x] T015 [US5] The generator (T003) and the load job (T007) write them too

## US6 #385: the synthetic extract is as messy as real practice records

- [x] T016 [US6] Failing tests (`test_open_dental.py`), then the generator's mess rates (charts not done, partial,
  copied, uniform, out of range, charted after loss), radiograph procedures and `document` rows, and the simulated
  `radiograph_bone_level` reading; `realism_profile`; research.md, the silver model and the ERDs
- [x] T017 [US6] Failing tests (`test_tooth_loss.py`), then `last_rbl_pct` and the last chart's quality in the tooth
  table; the load job writes `radiograph_bone_level`

## US7 #429: teeth missing at the first visit have a realistic mix of reasons

- [x] T018 [US7] Sources: published shares of reasons for extraction by age band, verified against each paper, in
  [research.md](research.md) and `docs/references.md`
- [x] T019 [US7] Failing tests (`test_open_dental.py`, `test_tooth_loss_model.py`): the share by age band, no link to
  worst CAL, own stream, both classes in the missing-at-entry evaluation
- [x] T020 [US7] `open_dental.py`: `ENTRY_PERIO_SHARE_BY_AGE`, `Params.entry_other_teeth_by_age` and
  `entry_other_tooth_weights`, the draw on its own stream
- [x] T021 [US7] Regenerate with the scripts (tooth table, model results, ERD dictionary, website JSON);
  `docs/tooth_loss.md` with AUC and specificity on teeth missing at entry and the stage recount, labelled synthetic;
  the analysis plan's change log; R parity and the full suite

## US8 #433: teeth lost for other reasons share risk factors with periodontal loss

- [x] T022 [US8] Sources: published effects of smoking and diabetes (and attendance or socioeconomic status, if a
  source gives one) on tooth loss for reasons other than periodontitis, verified against each paper, in
  [research.md](research.md) ("Shared risk factors") and `docs/references.md`
- [x] T023 [US8] Failing tests (`test_open_dental.py`): the rate ratio and its norm; observed/expected
  non-periodontal count by smoking and diabetes; age-band shares still hold; no link to worst CAL within age band
  and risk group; neutral ratios give US7's means; seeded
- [x] T024 [US8] `open_dental.py`: `Params.entry_other_smoking_ratios`, `entry_other_diabetes_ratio`,
  `entry_other_norm_draws`; `entry_other_rate_ratio`, `entry_other_rate_norm`; the Poisson mean scaled on the same
  stream
- [x] T025 [US8] Regenerate with the scripts (tooth table, model results, ERD dictionary, website JSON);
  `docs/tooth_loss.md` with before/after AUC and specificity on teeth missing at entry and the stage recount,
  labelled synthetic; the analysis plan's change log; R parity and the full suite

## US9 #507: a planned periodontal extraction counts only when the tooth is missing at a later visit

- [x] T026 [US9] Failing tests (`test_tooth_loss.py`, `test_tooth_loss_model.py`, `test_open_dental.py`): the new
  statuses, labels and day counts; the window and the earlier rule as a setting; later-missing teeth in the stage
  recount; the generator's later-missing rows, after the plan, on their own stream
- [x] T027 [US9] `open_dental.py` (`Params.planned_then_missing`, own stream), `tooth_loss.py`
  (`planned_then_missing_*`, `missing_later`, `plan_to_missing_days`), `tooth_loss_model.py`
  (`ModelParams.planned_window_days`, `label_set`, the stage recount), `scripts/51_tooth_loss_model.py`
  (`--planned-window-days`); the silver model's `patient_tooth`
- [x] T028 [US9] R twin (`r/R/16_spec029.R`, `tooth_status_029`) and the parity check on statuses and day counts
- [x] T029 [US9] Regenerate with the scripts (tooth table, model results, presets, ERD dictionary, website JSON);
  `docs/tooth_loss.md` with the new rule and the earlier one beside it, labelled synthetic; R parity and the full
  suite

## US10 #529: the model follows the study lead's answers

- [x] T030 [US10] Failing tests: the four extraction codes; the most recent plan's label and window; no-diagnosis
  extractions dropped and counted; no age cut-off and a 548-day window by default; presets follow
- [x] T031 [US10] `open_dental.py` (codes), `tooth_loss.py` (most recent plan), `tooth_loss_model.py` (defaults,
  `eligible`, `exclusions`, applied and evaluation sets), `scripts/51_tooth_loss_model.py` (`--stage-recount`,
  `--min-age` default), `analysis_presets.yaml`; R twin (codes, most recent plan)
- [x] T032 [US10] Regenerate (tooth table, ERD, presets, site JSON, model results); `docs/tooth_loss.md`; R parity
  and the full suite

## US11 #567: perio by the study lead's codes, adult teeth, F1

- [x] T033 [US11] Failing tests: each of PE1-PE4 and P1-P4 is periodontal whatever the item's name, another code is
  not; lettered and supernumerary teeth never reach the tooth table; F1 in `classification` and the scores
- [x] T034 [US11] `open_dental.py` (`PERIO_CODES`, `diagnosis_classes`, the synthetic list codes), `tooth_loss.py`,
  `tooth_loss_model.py` (F1), `scripts/47_tooth_table.py` (`itemvalue`); R twin and hand-worked parity block
- [x] T035 [US11] Regenerate (tooth table, ERD, presets, site JSON, model results); `docs/tooth_loss.md` with F1;
  R parity and the full suite
