# Tasks: synthetic medical-record features for the status classifier (spec 023)

Implementation starts after this spec, plan and tasks are reviewed.

## US1 #198: the synthetic visits carry seeded medical-record features

- [x] T001 [US1] Research: check each candidate source in plan.md against its paper; fill `CONDITIONS` with
  cited numbers only
- [x] T002 [US1] Failing tests: `test_medical_record.py` (seed, byte-identical rebuild, sources, diabetes =
  HbA1c, odds ratios within tolerance, ranges, column names)
- [x] T003 [US1] `medical_record.py`: `CONDITIONS`, `draw_medical_record`, own random stream; `@traced`
- [x] T004 [US1] `study.py` writes `medical_record.csv` (a new file; existing files unchanged); the data card says synthetic

## US2 #199: dental-only, dental+medical and medical-only

- [x] T005 [US2] Failing tests: `four` scheme, the four feature sets (incl. `dental_no_asa`), stratified split grouped by person
- [x] T006 [US2] `classify_status.py`: `FEATURE_SETS`, `four`, `split_stratified`, `compare_feature_sets`
- [x] T007 [US2] `scripts/44_medical_features.py`, writes `synthetic_medical_feature_sets.csv`
- [x] T008 [US2] Docs: results labelled synthetic, the paper's Table 2 averages cited beside them; PROBAST /
  TRIPOD-AI page

## US3 #200: per-class metrics, the same in R

- [x] T009 [US3] Failing tests: `class_metrics` on hand-worked cases
- [x] T010 [US3] `class_metrics` in Python; base-R twin in `r/R/13_spec023.R`; parity input and check
- [x] T011 Full test suite, `ruff`, R parity; review file for the implementation PR
