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

**Why teeth are missing at entry (spec 029 US7, #429, and US8, #433).** Since US7, teeth already missing at a
patient's first visit are lost to periodontitis or to another reason (caries, fracture, orthodontic, failed
treatment), in a mix that depends on age: the share lost to periodontitis follows a national survey of extractions by
age band (Suzuki et al., Int Dent J 2022, references item 63), from 6% at 25-34 to about half from 55 on
([research.md](../specs/029-tooth-loss/research.md), "Why teeth are missing"). The non-periodontal ones are chosen by
tooth type, never by attachment loss. Since US8, how many a patient has also rises with smoking (1.05 times under a
pack a day, 1.38 from a pack; Mai et al. 2013, item 68) and diabetes (1.20; Ahmadinia et al. 2022, item 70), rescaled
so each age band keeps its share ([research.md](../specs/029-tooth-loss/research.md), "Shared risk factors"). The
published effects of smoking and diabetes on tooth loss for reasons other than periodontitis are small and not
statistically significant, so this is a small change.

**Held-out extractions** (242 teeth with a recorded diagnosis, 223 patients, 14% periodontal), shared predictors:

| Label set | Model | AUC (95% CI) | Brier | Calibration slope | Sensitivity / specificity at 0.5 |
|---|---|---|---|---|---|
| completed | logistic | 0.84 (0.73-0.93) | 0.07 | 1.09 (0.76-1.62) | 0.59 / 0.99 |
| completed | XGBoost | 0.86 (0.77-0.93) | 0.07 | 0.85 (0.62-1.23) | 0.53 / 0.98 |
| completed + planned | logistic | 0.81 (0.69-0.91) | 0.10 | 0.72 (0.51-1.02) | 0.74 / 0.90 |
| completed + planned | XGBoost | 0.86 (0.78-0.94) | 0.09 | 0.75 (0.57-1.04) | 0.74 / 0.89 |
| baseline: outcome rate | - | 0.50 | 0.12 | - | - |

With the tooth's own measures, AUC is 0.84 (logistic) and 0.85 (XGBoost) on completed extractions: about the same as
the shared set. Adding planned extractions raises sensitivity but shifts the probabilities up (calibration
intercept about -1.2), since planned extractions in the synthetic set are mostly periodontal (training outcome
rate 34% against 13% in completed extractions). Across the 5 generator seeds the held-out AUC of the shared models
ranges from about 0.71 to 0.86: the held-out set is small, so one seed's number shouldn't be read alone.

**Teeth missing at the first exam** (7,588 teeth, 3,090 patients, third molars left out; 21% periodontal by the
answer key), shared predictors (the tooth has no own measures there):

| Label set | Model | AUC (95% CI) | Brier | Calibration intercept / slope | Mean probability | Sensitivity / specificity at 0.5 |
|---|---|---|---|---|---|---|
| completed | logistic | 0.94 (0.93-0.95) | 0.09 | 0.28 / 1.85 | 0.18 | 0.43 / 0.98 |
| completed | XGBoost | 0.94 (0.92-0.95) | 0.08 | 0.44 / 1.30 | 0.17 | 0.55 / 0.98 |
| completed + planned | logistic | 0.94 (0.93-0.95) | 0.08 | -0.77 / 1.21 | 0.29 | 0.85 / 0.91 |
| completed + planned | XGBoost | 0.95 (0.93-0.95) | 0.08 | -0.75 / 1.10 | 0.27 | 0.89 / 0.90 |
| baseline: every missing tooth is periodontal | - | 0.50 | 0.79 | - | 1.00 | 1.00 / 0.00 |

Across the 5 generator seeds the AUC there ranges from 0.89 to 0.98. Specificity is the share of non-periodontal
losses the model doesn't call periodontal: 0.94-0.98 on completed extractions, 0.89-0.91 with planned extractions
added, against 0 for "every missing tooth". On this seed the completed-extraction models' probabilities run low
(intercept above 0, mean 0.17-0.18 against 21% periodontal), so at 0.5 they miss more than half the periodontal
teeth; with planned extractions added they run high (intercept below 0). The AUC is higher than on the held-out
extractions, and that is a property of this generator, not a result to expect on real records: most
non-periodontal teeth missing at entry are in young mouths (the published mix by age), while the periodontal ones
come with the mouth's attachment loss. US8 lets the two share smokers and patients with diabetes, but by the small
published effects, so they still fall mostly in different patients.

**Before and after US8** (SYNTHETIC; the same command on the code before and after the change). Because the
generator's main stream moves with the number of teeth present, every extract is a fresh synthetic sample after the
change, so the 5-seed means are the fairer comparison:

| Teeth missing at entry, shared predictors | AUC seed 42, before → after | AUC 5-seed mean, before → after | Specificity at 0.5, 5-seed mean, before → after |
|---|---|---|---|
| completed, logistic | 0.96 → 0.94 | 0.955 → 0.944 | 0.94 → 0.96 |
| completed, XGBoost | 0.96 → 0.94 | 0.951 → 0.954 | 0.96 → 0.96 |
| completed + planned, logistic | 0.95 → 0.94 | 0.948 → 0.954 | 0.89 → 0.90 |
| completed + planned, XGBoost | 0.95 → 0.95 | 0.954 → 0.959 | 0.90 → 0.90 |

The missing-at-entry AUC moves by about 0.01 either way, inside the seed-to-seed spread (0.93-0.97 before, 0.89-0.98
after): with effects this small, sharing smoking and diabetes doesn't make the two kinds of loss much harder to tell
apart. What keeps the AUC high is the age mix and attachment loss, not these risk factors.

**Extractions without a diagnosis** (146 teeth, 16% periodontal by the answer key): AUC 0.97 (0.93-1.00) and 0.92
(0.84-0.99) for the shared logistic and XGBoost models on completed extractions, Brier 0.05; the calibration
intercept is near 0 (0.18 and 0.07).

**Stage III vs IV** (2,411 patients whose worst CAL in the record is 5 mm or more):

| Counting rule | Stage IV | Agree with truth | Called IV, truth III | Called III, truth IV |
|---|---|---|---|---|
| recorded periodontal extractions only | 0 | 2,314 | 0 | 97 |
| every missing tooth | 273 | 2,235 | 176 | 0 |
| expected, completed, logistic | 21 | 2,333 | 1 | 77 |
| expected, completed, XGBoost | 27 | 2,339 | 1 | 71 |
| expected, completed + planned, logistic | 85 | 2,347 | 26 | 38 |
| expected, completed + planned, XGBoost | 84 | 2,348 | 25 | 38 |
| the synthetic truth | 97 | 2,411 | 0 | 0 |

"Every missing tooth" calls 273 patients stage IV, 176 of them wrongly: nearly three times the true number. The
expected count calls 21-85, with 1-26 wrongly and 38-77 missed; with planned extractions it is the closest to the
truth, and recorded periodontal extractions alone find no stage IV patient by tooth loss. On this seed the
completed-extraction models undercount (their probabilities run low on teeth missing at entry, above), so they miss
more stage IV patients than before US8 (40-45 on the earlier seed 42 extract).

Stage recount, mean of the 5 generator seeds, before → after US8: "every missing tooth" 271 → 264 called stage IV
(168 → 170 wrongly) against a truth of 102 → 94; expected count, completed, 56-61 → 50-53 (7-8 → 5 wrongly, 49-54 →
46-48 missed); completed + planned, 91-95 → 92-98 (21-23 → 24-28 wrongly, 30-32 → 23-26 missed). Before US8, seed
42 alone: every missing tooth 250 (164 wrongly), expected count 48-81 (7-26 wrongly, 29-45 missed), truth 86.

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
