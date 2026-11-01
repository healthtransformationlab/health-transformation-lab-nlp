# Was a missing tooth lost to gum disease? (spec 029)

A plain account of the tooth-loss model: the question, the records it reads, what it found on **synthetic** data, and
what a real extract can and can't check. The full method is the pre-specified
[analysis plan](../specs/029-tooth-loss/analysis_plan.md) (TRIPOD+AI order); the requirements are in
[spec.md](../specs/029-tooth-loss/spec.md). Every number on this page is from synthetic records made in this repo:
agreement with a synthetic answer key, not a finding about any practice or any patient.

## The question

The 2017 AAP/EFP classification separates stage III from stage IV periodontitis partly by how many teeth were
lost to periodontitis: five or more makes stage IV ([staging_grading.md](staging_grading.md)). Dental records
seldom say why a tooth is missing. A tooth may be missing at the first exam with no reason given, or extracted
without a diagnosis item recorded. So the count of teeth lost to periodontitis, and with it the stage, is uncertain.

The model estimates, for each missing tooth, the probability that it was lost to periodontitis. It is trained on
extractions that do carry a recorded diagnosis (periodontal = 1, any other reason = 0), using only what was charted
on or before the loss. Each patient's stage is then recounted with the **expected** number of teeth lost to
periodontitis: the recorded periodontal extractions plus the model's probabilities for the missing teeth with no
recorded reason (`labels.stage4_rule`, rule `expected_perio_loss`). It explains a loss already in the record; it
doesn't predict future loss.

This is finding gum disease in dental records (phenotyping), not a clinical judgement: the label is the dentist's
recorded diagnosis item, and a record that doesn't fit is a record to recheck, not an error by the dentist.

## The records it reads

A seeded synthetic extract in Open Dental's own table format (`open_dental.py`), cleaned as silver and reduced to
one row per patient and tooth (`tooth_loss.tooth_table`). The table and column names were checked against Open
Dental's source ([research.md](../specs/029-tooth-loss/research.md); references item 58), branch `24_3`:

| Table | What the model takes from it | Open Dental source |
|---|---|---|
| `procedurelog` | extractions (D7140, D7210): completed, planned, or done elsewhere; the diagnosis item (`Dx`) | [Procedure.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/Procedure.cs) |
| `definition` | the practice's own diagnosis lists (older and 2017), mapped to periodontal / other | [Def.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/Def.cs) |
| `toothinitial` | teeth missing at the first exam | [ToothInitial.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/ToothInitial.cs) |
| `perioexam`, `periomeasure` | probing depth, gingival margin (CAL is computed), bleeding, mobility | [PerioExam.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/PerioExam.cs), [PerioMeasure.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/PerioMeasure.cs) |
| `treatplan`, `proctp` | plan copies of a planned extraction, counted once | [TreatPlan.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/TreatPlan.cs), [ProcTP.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/ProcTP.cs) |
| `patient`, `disease`, `diseasedef` | age, smoking (`SmokingSnoMed`), diabetes (E10-E11) | [Patient.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/Patient.cs), [Disease.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/Disease.cs) |

Radiographic bone loss comes from a SIMULATED reading of each radiograph (`radiograph_bone_level`): Open Dental
stores the image, not a reading of it.

## How it is built

- **Teeth:** third molars are left out by default. A minimum age is a parameter (`ModelParams.min_age`,
  `--min-age`); the study lead hasn't decided it yet, so the default is none.
- **Two label sets** (FR-010): completed extractions only, and completed plus planned extractions (one per planned
  procedure, however many plan copies; a tooth planned then extracted counts once, as completed).
- **Two predictor sets:** *shared* (what every missing tooth has: tooth type, neighbours' worst CAL, the mouth at
  the first exam, teeth missing at entry, age, smoking, diabetes) is the applied model; *own* adds the tooth's own
  last measures and how good that chart was, and is shown beside it.
- **Models:** logistic regression (L2, C = 1, standardised, median imputation and missing indicators) and XGBoost
  (depth 3, 200 trees, learning rate 0.05, subsample 0.8), with three baselines.
- **Validation:** 70/30 split by patient, stratified on the outcome, seed 42. Both label sets are scored on the same
  held-out extractions. The applied sets (teeth missing at entry, extractions without a diagnosis) are scored
  against the synthetic answer key, which is never a feature.
- **Measures:** AUC, Brier score, calibration intercept and slope, a 10-bin calibration table, and sensitivity,
  specificity and predictive values at 0.5 and at the Youden threshold chosen on the training teeth. 95% intervals
  from 1,000 bootstrap resamples of patients. The run is repeated on 5 generator seeds.

Python: `tooth_loss_model.py`, run by `scripts/51_tooth_loss_model.py`. The metrics and the stage rule have base-R
twins (`r/R/16_spec029.R`) checked to 1e-9 by `r/tests/test_parity.R`. The gold table
`gold_opendental_perio.fact_tooth_loss_prediction` holds one probability per tooth, model, label set and run
(written by the Load Open Dental job).

## Results (SYNTHETIC)

```bash
cd python && python scripts/51_tooth_loss_model.py --patients 6000 --stability-seeds 5 --n-boot 1000
```

Synthetic extract of 6,000 patients, generator seed 42 (generator seeds 42-46 for the spread). Files in
`data/results/synthetic_tooth_loss_*.csv` (not committed; the command rebuilds them).

**Held-out extractions** (231 teeth with a recorded diagnosis, 218 patients, 14% periodontal), shared predictors:

| Label set | Model | AUC (95% CI) | Brier | Calibration slope | Sensitivity / specificity at 0.5 |
|---|---|---|---|---|---|
| completed | logistic | 0.79 (0.68-0.90) | 0.08 | 1.02 (0.68-1.60) | 0.41 / 0.98 |
| completed | XGBoost | 0.77 (0.66-0.88) | 0.09 | 0.78 (0.55-1.11) | 0.50 / 0.96 |
| completed + planned | logistic | 0.79 (0.70-0.89) | 0.12 | 0.69 (0.47-1.01) | 0.66 / 0.88 |
| completed + planned | XGBoost | 0.76 (0.65-0.87) | 0.12 | 0.60 (0.40-0.86) | 0.66 / 0.88 |
| baseline: outcome rate | - | 0.50 | 0.12 | - | - |

With the tooth's own measures, AUC is 0.82 (logistic) and 0.80 (XGBoost) on completed extractions: a little more
than the shared set. Adding planned extractions raises sensitivity but shifts the probabilities up (calibration
intercept about -1.3), since planned extractions in the synthetic set are mostly periodontal (training outcome
rate 32% against 14% in completed extractions). Across the 5 generator seeds the held-out AUC of the shared models
ranges from about 0.68 to 0.90: the held-out set is small, so one seed's number shouldn't be read alone.

**Extractions without a diagnosis** (145 teeth, 11% periodontal by the answer key): AUC 0.98 (0.96-1.00) for both
shared models on completed extractions, Brier 0.04-0.05; the calibration slope is above 1 (1.8 and 3.6), so the
probabilities are less spread out than the outcomes, and the intercept is below 0, so they run high on average.

**Teeth missing at the first exam** (1,726 teeth, third molars left out): in this synthetic generator every one is
periodontal by the answer key, because the only other reason it draws for a tooth missing at entry is a third molar
(`sites.draw_mouth_columns`). AUC and specificity can't be computed there. The shared models give a mean
probability of 0.58 (logistic) and 0.65 (XGBoost) on completed extractions, and 0.77-0.79 with planned extractions
added; sensitivity at 0.5 is 0.70-0.75 and 0.92-0.93. This is a limit of the synthetic data, not a measure of
how the model carries over to teeth never extracted in the record.

**Stage III vs IV** (2,436 patients whose worst CAL in the record is 5 mm or more):

| Counting rule | Stage IV | Agree with truth | Called IV, truth III | Called III, truth IV |
|---|---|---|---|---|
| recorded periodontal extractions only | 0 | 2,320 | 0 | 116 |
| every missing tooth | 125 | 2,427 | 9 | 0 |
| expected, completed, logistic | 46 | 2,366 | 0 | 70 |
| expected, completed, XGBoost | 54 | 2,374 | 0 | 62 |
| expected, completed + planned, logistic | 72 | 2,392 | 0 | 44 |
| expected, completed + planned, XGBoost | 68 | 2,388 | 0 | 48 |
| the synthetic truth | 116 | 2,436 | 0 | 0 |

Counting recorded periodontal extractions alone finds no stage IV patient by tooth loss; the expected count moves
46-72 patients to stage IV with none wrongly. Here "every missing tooth" comes closest, again because almost every
missing tooth other than a third molar is periodontal in this generator; on real records that rule is expected to
overcount.

## What a real extract can and can't check

- **Can:** the same code runs unchanged on a real Open Dental extract inside its own secure environment, with the
  data-quality checks (`tooth_loss_dq.py`) first. The held-out scores against the recorded diagnosis, the
  calibration and the stage counts by rule can all be computed. Only aggregate results leave that environment.
- **Can't:** a real extract has no answer key, so the scores on teeth missing at entry and on extractions without a
  diagnosis can't be measured; that gap is stated, not estimated. The label is the recorded diagnosis item, so
  "agreement" means agreement with what the dentist recorded; checking the label itself needs the chart comparison
  or expert review in the analysis plan (section 13).
- **Not built yet:** subgroups (section 11), the temporal and second-site validation (section 9), the sensitivity
  analyses other than the minimum age and third molars (section 12), and the sample-size check (section 6).
