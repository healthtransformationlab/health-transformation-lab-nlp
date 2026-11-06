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
| `procedurelog` | extractions (D7111, D7140, D7210, D7250; the generator draws the middle two): completed, planned, or done elsewhere (at the first visit, or dated at a later one); the diagnosis item (`Dx`) | [Procedure.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/Procedure.cs) |
| `definition` | the practice's own diagnosis lists (older and 2017), mapped to periodontal / other | [Def.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/Def.cs) |
| `toothinitial` | teeth missing at the first exam | [ToothInitial.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/ToothInitial.cs) |
| `perioexam`, `periomeasure` | probing depth, gingival margin (CAL is computed), bleeding, mobility | [PerioExam.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/PerioExam.cs), [PerioMeasure.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/PerioMeasure.cs) |
| `treatplan`, `proctp` | plan copies of a planned extraction, counted once | [TreatPlan.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/TreatPlan.cs), [ProcTP.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/ProcTP.cs) |
| `patient`, `disease`, `diseasedef` | age, smoking (`SmokingSnoMed`), diabetes (E10-E11) | [Patient.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/Patient.cs), [Disease.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/Disease.cs) |

Radiographic bone loss comes from a SIMULATED reading of each radiograph (`radiograph_bone_level`): Open Dental
stores the image, not a reading of it.

## How it is built

- **Teeth:** the permanent (adult) teeth 1-32 only, whatever the patient's age (029 US11, #567): primary teeth are
  lettered in Open Dental and supernumerary teeth are 51-82, so neither reaches the tooth table. Third molars are left
  out by default. There is no age cut-off by default since 029 US10 (#529,
  the study lead's answer); 18 and over and 30 and over (`ModelParams.min_age`, `--min-age`) are sensitivity
  analyses. Extractions with no diagnosis are dropped entirely (029 US10): not a negative, not trained on, not scored.
  A start date (`ModelParams.start_date`, `--start-date`, spec 032; 2018-01-01 by default since spec 032 US8, `""`
  for every year) keeps the teeth lost on or after it, or first charted on or after it when the loss date isn't
  recorded.
  `tooth_loss_model.exclusions` counts the teeth left out by each reason.
- **The label:** an extraction is periodontal when its diagnosis item's code is PE1, PE2, PE3, PE4, P1, P2, P3 or
  P4 (the study lead's list, 029 US11, #567; `open_dental.PERIO_CODES`), matched on the code, not the item's name.
  Any other recorded diagnosis is another reason, including an item outside the practice's lists (read by name it
  was none; the data-quality check `diagnosis_not_in_lists` still flags such items). The synthetic lists carry P3 and P4 (older list) and PE3 and PE4
  (2017 list) on their periodontal items.
- **Two label sets** (FR-010): completed extractions only, and completed plus planned extractions (one per planned
  procedure, however many plan copies; a tooth planned then extracted counts once, as completed). Since 029 US9
  (#507) a planned extraction counts only when the tooth is **recorded missing at a later visit within 548 days
  (1.5 years) of its most recent plan**, whose diagnosis gives the label: a later plan with another reason overrides
  an earlier periodontal one (029 US10, #529) (`ModelParams.planned_window_days`, `--planned-window-days`): a planned extraction often never happens,
  so one whose tooth is still in the mouth isn't tooth loss. One still in the mouth, or missing after the window, has
  no label. The earlier rule (every planned extraction with a diagnosis counts) is kept as a sensitivity setting,
  `--planned-window-days none`. In the synthetic extract the later loss is an extraction by another provider dated
  at that visit; on a real extract the date may come from a dated `toothinitial`. Every tooth recorded missing later
  counts as missing in the stage recount, with the model's probability; for a planned-then-missing tooth inside the
  window that is a tooth the completed + planned model trained on, so its probability there is in-sample (only a
  completed periodontal extraction counts as recorded).
- **Two predictor sets:** *shared* (what every missing tooth has: tooth type, neighbours' worst CAL, the mouth at
  the first exam, teeth missing at entry, age, smoking, diabetes) is the applied model; *own* adds the tooth's own
  last measures and how good that chart was, and is shown beside it.
- **Models:** logistic regression (L2, C = 1, standardised, median imputation and missing indicators) and XGBoost
  (depth 3, 200 trees, learning rate 0.05, subsample 0.8), with three baselines.
- **Validation:** 80/20 split by patient, stratified on the outcome, seed 42, with XGBoost tuned by 5-fold
  cross-validation (the defaults since spec 032 US8; before it, 70/30 with fixed settings, the `repo_v1` preset). Both label sets are scored on the same
  held-out extractions. The applied set (teeth missing at entry; extractions without a diagnosis were an applied set before 029 US10) is scored
  against the synthetic answer key, which is never a feature. Options (spec 032): `--test-share`; `--split-unit
  visit` holds out random teeth instead of patients, so one patient's teeth can be on both sides, which flatters the
  score: the run prints how many patients that is, and it is never the default; `--cv-folds K` tunes XGBoost by
  K-fold cross-validation over a small fixed grid, folds grouped by patient unless the split is by visit.
- **Measures:** AUC, Brier score, calibration intercept and slope, a 10-bin calibration table, and sensitivity,
  specificity, predictive values and F1 (029 US11, #567, the study lead's ask) at 0.5 and at the Youden threshold chosen on the training teeth. 95% intervals
  from 1,000 bootstrap resamples of patients. The run is repeated on 5 generator seeds.
- **Output, tooth level only** (029 US10, #529): the model gives one probability per missing tooth. Summing them to
  the person (the stage III vs IV recount below) is a separate, later decision, so it is written only with
  `--stage-recount`. No inter-rater statistics and no consistency measures grade this model; it is a predictive model.

Python: `tooth_loss_model.py`, run by `scripts/51_tooth_loss_model.py`. The metrics and the stage rule have base-R
twins (`r/R/16_spec029.R`) checked to 1e-9 by `r/tests/test_parity.R`. The gold table
`gold_opendental_perio.fact_tooth_loss_prediction` holds one probability per tooth, model, label set and run
(written by the Load Open Dental job).

These options can also be run together as a named preset, beside today's defaults: see [presets](presets.md)
(spec 032 US7).

## Results (SYNTHETIC)

```bash
cd python && python scripts/51_tooth_loss_model.py --patients 6000 --stability-seeds 5 --n-boot 1000
```

**On the spec 037 extract** (the defaults since spec 037, SYNTHETIC; tooth level only). Spec 037 set the extract's
tooth loss from published figures: extractions in the record at about 0.17 per patient-year (item 87), periodontal at
Suzuki's share by age (item 63), up to ten years of record per patient, and teeth missing at the first visit at
NHANES 2009-2014's counts by age ([synthetic_data.md](synthetic_data.md)). The analysis is unchanged. Same command,
6,000 patients, five generator seeds, 1,000 bootstrap resamples. Of the 192,000 teeth, 14,368 belong to patients with
no natural teeth, 606 are extractions with no diagnosis, 22,175 are other third molars and 79,704 are lost (or first
charted) before the start date, so 75,147 are left. The completed set trains on 1,881 teeth and the completed +
planned set on 1,937, against 348 and 391 before.

Held-out extractions (448 teeth, 320 patients, 153 periodontal; 88 teeth and 14 periodontal before), shared
predictors, generator seed 42:

| At a threshold of 0.5 | completed: logistic | completed: XGBoost | completed + planned: logistic | completed + planned: XGBoost |
|---|---|---|---|---|
| sensitivity (of 153 periodontal) | 0.82 | 0.82 | 0.82 | 0.84 |
| specificity (of 295 other) | 0.90 | 0.92 | 0.89 | 0.91 |
| positive predictive value | 0.81 | 0.84 | 0.79 | 0.82 |
| negative predictive value | 0.91 | 0.91 | 0.90 | 0.91 |
| F1 | 0.82 | 0.83 | 0.80 | 0.83 |
| AUC (95% CI) | 0.91 (0.87-0.94) | 0.92 (0.89-0.95) | 0.91 (0.87-0.94) | 0.92 (0.88-0.95) |
| Brier score | 0.106 | 0.095 | 0.109 | 0.101 |

The intervals are about a third as wide as before, and across the five generator seeds the held-out AUC of the shared
models runs 0.86-0.92 (0.60-0.93 before): the earlier spread was mostly the 14 periodontal teeth.

On the teeth missing at the first visit (10,761 teeth, 1,732 patients; scored against the synthetic answer key) the
AUC falls to 0.60 / 0.62 (completed) and 0.62 / 0.67 (completed + planned), 0.59-0.74 across seeds, from 0.92-0.96.
Before spec 037 nearly every tooth missing at entry was periodontal and sat in a mouth with attachment loss, an easy
set; now 57% are lost for other reasons, spread over every kind of mouth as NHANES's counts require, and a model
trained on extractions with a recorded reason tells them apart far less well. This is the harder, more realistic
set; what a real extract shows is still open.

The tables below are from before spec 037, kept as the record.

**Under the study lead's answers since 029 US10** (#529; the defaults, SYNTHETIC; tooth level only). Extractions are
D7111, D7140, D7210 and D7250; extractions with no diagnosis are dropped; a planned extraction counts if the tooth
goes missing within 548 days of its most recent plan; no age cut-off; the 2018-01-01 start date stays until confirmed.
Same command, 6,000 patients, five generator seeds, 1,000 bootstrap resamples. Of the 192,000 teeth, 14,016 belong to
patients with no natural teeth, 161 are extractions with no diagnosis, 22,244 are other third molars and 82,976 are
lost (or first charted) before the start date, so 72,603 are left. The completed set trains on 348 teeth and the
completed + planned set on 391.

Held-out extractions (88 teeth, 85 patients, 14 periodontal), shared predictors, generator seed 42. As the study lead
asked, the confusion-matrix measures lead; AUC and the Brier score are beside them:

| At a threshold of 0.5 | completed: logistic | completed: XGBoost | completed + planned: logistic | completed + planned: XGBoost |
|---|---|---|---|---|
| sensitivity (of 14 periodontal) | 0.57 | 0.64 | 0.64 | 0.71 |
| specificity (of 74 other) | 0.95 | 0.96 | 0.95 | 0.95 |
| positive predictive value | 0.67 | 0.75 | 0.69 | 0.71 |
| negative predictive value | 0.92 | 0.93 | 0.93 | 0.95 |
| F1 (029 US11) | 0.62 | 0.69 | 0.67 | 0.71 |
| AUC (95% CI) | 0.92 (0.84-0.98) | 0.92 (0.82-0.99) | 0.89 (0.79-0.98) | 0.89 (0.74-0.98) |
| Brier score | 0.079 | 0.062 | 0.082 | 0.078 |

On the teeth missing at the first exam (3,558 teeth, 1,400 patients; scored against the synthetic answer key) the AUC
is 0.92 / 0.92 (completed) and 0.93 / 0.96 (completed + planned). With 14 periodontal teeth held out, one tooth moves
sensitivity by 0.07, and across the 5 generator seeds the held-out AUC of the shared models ranges from 0.60 to 0.93:
read the seed-42 numbers with that spread in mind. The stage III vs IV recount below is from before US10 and is now
written only with `--stage-recount`.

Rerun under 029 US11 (#567; perio read by the codes PE1-PE4 and P1-P4, permanent teeth only, F1 added): same
command, 6,000 patients, five seeds, 1,000 resamples. Every number above is unchanged, as expected: the synthetic
periodontal items now carry those codes, so the same teeth get the same labels, and the teeth were already 1-32. F1
is the new row.

**Under the planned-extraction rule of 029 US9** (#507; the defaults before US10, SYNTHETIC). A planned extraction now counts
only when the tooth is recorded missing at a later visit within 365 days; the earlier rule (every planned extraction
with a diagnosis counts) is run beside it with `--planned-window-days none`. Same command, same five generator seeds
and 1,000 bootstrap resamples, on the extract as spec 033 (US2 and US4) draws it. Of the 192,000 teeth, 14,016 belong
to patients with no natural teeth, 22,248 are other third molars and 83,044 are lost (or first charted) before the
start date, so 72,692 are left. Generator seed 42, shared predictors, AUC (95% CI); the completed + planned columns
are where the rule changes:

| Teeth scored | completed: logistic | completed: XGBoost | completed + planned: logistic | completed + planned: XGBoost |
|---|---|---|---|---|
| held-out extractions (88 teeth, 86 patients) | 0.80 (0.66-0.91) | 0.79 (0.65-0.91) | 0.81 (0.68-0.92) | 0.76 (0.61-0.89) |
| missing at the first exam (3,558 teeth, 1,400 patients) | 0.93 (0.91-0.95) | 0.93 (0.91-0.95) | 0.93 (0.91-0.95) | 0.95 (0.94-0.96) |
| extractions without a diagnosis (89 teeth) | 0.86 (0.60-1.00) | 0.94 (0.83-1.00) | 0.94 (0.84-0.99) | 0.92 (0.79-1.00) |
| *earlier rule, held-out extractions (86 teeth)* | 0.86 (0.75-0.96) | 0.84 (0.68-0.97) | 0.81 (0.65-0.95) | 0.83 (0.67-0.96) |
| *earlier rule, missing at the first exam* | 0.92 (0.90-0.94) | 0.95 (0.93-0.96) | 0.92 (0.89-0.94) | 0.96 (0.95-0.97) |

The completed + planned set now trains on 381 teeth, not 462: planned extractions whose tooth stayed in the mouth no
longer count. The split by patient is drawn from that set, so the held-out teeth differ a little between the rules
(88 and 86), and the completed columns move too. Across the 5 generator seeds the held-out AUC of the shared models
ranges from 0.66 to 0.90 (0.58 to 0.92 under the earlier rule); with under 100 held-out teeth the intervals overlap
throughout, so the change in AUC is within the noise. Of the 2,230 patients at stage III-IV by worst CAL, the
synthetic truth puts 93 at stage IV:

| Expected count, shared predictors | stage IV | wrongly called IV | IV missed |
|---|---|---|---|
| completed + planned, logistic / XGBoost: new rule | 85 / 71 | 18 / 18 | 26 / 40 |
| completed + planned, logistic / XGBoost: earlier rule | 100 / 90 | 26 / 24 | 19 / 27 |
| completed, logistic / XGBoost: new rule | 71 / 58 | 15 / 11 | 37 / 46 |

Counting planned extractions still in the mouth as tooth loss called 26 / 24 patients stage IV whom the synthetic
truth puts at stage III; the new rule calls 18, and misses more stage IV patients in exchange. The size of the effect
depends on how many planned teeth stay in the mouth: on the extract before spec 033 the same comparison moved 25 wrong
calls to 10-12, and on the one between US2 and US4 it hardly moved them. Every missing tooth (277 stage IV, 184
wrongly) and recorded extractions only (0) bracket it. The rule is there because a planned extraction that never
happens isn't tooth loss. These are agreement with a synthetic answer key, whose planned-then-missing share
(`Params.planned_then_missing`, 0.5) is a placeholder; a real extract decides how much this matters.

The tables from here down are runs before 029 US9.

**Under the defaults since spec 032 US8** (#448; [presets](presets.md), `repo_v2`): teeth lost (or first charted)
from 2018-01-01, an 80/20 split by patient and XGBoost tuned by 5-fold cross-validation. Since spec 033 US4 the 429 patients with no natural teeth come out first (12,012 non-third-molar teeth); the start
date then leaves out 82,673 of the other 155,988 (73,315 left), so every set is smaller and the intervals wider.
Generator seed 42, shared predictors, AUC (95% CI):

| Teeth scored | completed: logistic | completed: XGBoost | completed + planned: logistic | completed + planned: XGBoost |
|---|---|---|---|---|
| held-out extractions (89 teeth, 83 patients) | 0.72 (0.50-0.89) | 0.75 (0.57-0.90) | 0.74 (0.53-0.89) | 0.74 (0.56-0.89) |
| missing at the first exam (3,440 teeth, 1,391 patients) | 0.98 (0.97-0.98) | 0.97 (0.95-0.98) | 0.97 (0.96-0.98) | 0.96 (0.95-0.97) |
| extractions without a diagnosis (71 teeth) | 0.94 (0.86-0.99) | 0.97 (0.93-1.00) | 0.95 (0.89-1.00) | 0.93 (0.85-0.99) |

Across the 5 generator seeds the held-out AUC of the shared models ranges from 0.72 to 0.90. The start date and the
minimum age choose the teeth that train and score the model, not how many teeth a patient has lost: the stage recount still counts every missing tooth but third molars (`tooth_loss_model.stage_teeth`; patients with
no natural teeth are left out, as an edentulous mouth can't be staged), and the fitted model gives the
unlabelled ones outside its own teeth a probability too. So stage IV, all 2,299 patients at stage III-IV by worst CAL, is the same under both: 261 by every missing tooth, 49
by fewer than 20 teeth, 171 by fewer than 10 occluding pairs, 98 by the synthetic truth; by the expected count (shared
predictors) 64 / 45 (completed, logistic / XGBoost) and 92 / 80 (completed + planned), against 69 / 69 and 94 / 89
under the earlier settings, as the model itself
changed. The detailed tables below are the run before spec 032 US8 (every year,
70/30, fixed XGBoost settings: `--start-date "" --test-share 0.3 --cv-folds 0`, the `repo_v1` preset); they are kept
because they describe the whole extract.

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

**Held-out extractions** (223 teeth with a recorded diagnosis, 208 patients, 13% periodontal), shared predictors:

| Label set | Model | AUC (95% CI) | Brier | Calibration slope | Sensitivity / specificity at 0.5 |
|---|---|---|---|---|---|
| completed | logistic | 0.81 (0.70-0.91) | 0.09 | 0.70 (0.46-1.04) | 0.53 / 0.94 |
| completed | XGBoost | 0.80 (0.70-0.89) | 0.09 | 0.65 (0.45-0.88) | 0.53 / 0.93 |
| completed + planned | logistic | 0.82 (0.72-0.91) | 0.11 | 0.61 (0.43-0.86) | 0.63 / 0.90 |
| completed + planned | XGBoost | 0.82 (0.73-0.90) | 0.12 | 0.53 (0.44-0.73) | 0.57 / 0.89 |
| baseline: outcome rate | - | 0.50 | 0.12 | - | - |

With the tooth's own measures, AUC is 0.80 (logistic) and 0.80 (XGBoost) on completed extractions: about the same as
the shared set. Adding planned extractions raises sensitivity but shifts the probabilities up (calibration intercept -1.24 and -1.33), since planned extractions in the synthetic set are mostly periodontal. Across the 5
generator seeds the held-out AUC of the shared models ranges from about 0.73 to 0.86: the held-out set is small, so
one seed's number shouldn't be read alone.

**Teeth missing at the first exam** (7,417 teeth, 2,983 patients, third molars left out; 20% periodontal by the answer key), shared predictors (the tooth has no own measures there):

| Label set | Model | AUC (95% CI) | Brier | Calibration intercept / slope | Mean probability | Sensitivity / specificity at 0.5 |
|---|---|---|---|---|---|---|
| completed | logistic | 0.96 (0.96-0.97) | 0.07 | -0.59 / 1.82 | 0.26 | 0.85 / 0.94 |
| completed | XGBoost | 0.92 (0.91-0.93) | 0.09 | -0.60 / 0.98 | 0.25 | 0.69 / 0.93 |
| completed + planned | logistic | 0.95 (0.94-0.96) | 0.08 | -1.08 / 1.22 | 0.31 | 0.91 / 0.90 |
| completed + planned | XGBoost | 0.95 (0.94-0.96) | 0.08 | -1.06 / 1.08 | 0.29 | 0.88 / 0.90 |
| baseline: every missing tooth is periodontal | - | 0.50 | 0.80 | - | 1.00 | 1.00 / 0.00 |

Across the 5 generator seeds the AUC there ranges from 0.92 to 0.97. Specificity is the share of non-periodontal
losses the model doesn't call periodontal: 0.93-0.97 on completed extractions, 0.87-0.92 with planned extractions added, against 0 for "every missing tooth". On this seed the completed-extraction models' probabilities run a little high on average (intercept below 0, mean
0.25-0.26 against 20% periodontal), and the logistic model's too close together (slope 1.82; XGBoost 0.98), so at
0.5 they find 69-85% of the periodontal teeth; with planned extractions added they run higher (intercept about -1.1). The AUC is higher than on the held-out
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

**Extractions without a diagnosis** (138 teeth, 12% periodontal by the answer key): AUC 0.97 (0.93-1.00) and 0.94
(0.88-0.98) for the shared logistic and XGBoost models on completed extractions, Brier 0.05 and 0.06; the calibration
intercept is below 0 (-0.83 and -1.01).

**Stage III vs IV** (2,299 patients whose worst CAL in the record is 5 mm or more; patients with no natural teeth
left out):

| Counting rule | Stage IV | Agree with truth | Called IV, truth III | Called III, truth IV |
|---|---|---|---|---|
| recorded periodontal extractions only | 0 | 2,201 | 0 | 98 |
| every missing tooth | 261 | 2,136 | 163 | 0 |
| expected, completed, logistic | 69 | 2,248 | 11 | 40 |
| expected, completed, XGBoost | 69 | 2,238 | 16 | 45 |
| expected, completed + planned, logistic | 94 | 2,247 | 24 | 28 |
| expected, completed + planned, XGBoost | 89 | 2,242 | 24 | 33 |
| fewer than 20 teeth left (spec 032) | 49 | 2,226 | 12 | 61 |
| fewer than 10 occluding pairs left (spec 032) | 171 | 2,136 | 118 | 45 |
| the synthetic truth | 98 | 2,299 | 0 | 0 |

"Every missing tooth" calls 261 patients stage IV, 163 of them wrongly: about two and a half times the true number.
The expected count calls 69-94, with 11-24 wrongly and 28-45 missed; with planned extractions it is the closest to the
truth, and recorded periodontal extractions alone find no stage IV patient by tooth loss. On this seed the completed-extraction models still undercount (69 against 98), missing 40-45 of the 98 stage IV
patients.

The last two rules (spec 032 US4, #443) don't ask why teeth were lost: they call stage IV from the teeth left,
fewer than 20 teeth or fewer than 10 occluding pairs (upper and lower teeth that meet), third molars left out as in
`aces.py`, counted from the whole tooth table (`labels.stage4_rule`, rules `teeth_lt_20` and `pairs_lt_10`). Fewer than 20 teeth calls 49 stage IV (12 wrongly, 61 missed): it misses most true stage IV patients, who keep 20 or more
teeth. Fewer than 10 pairs calls 171 (118 wrongly, 45 missed): a tooth lost for any reason can break a pair, so this
rule overcounts like "every missing tooth", though less. Mean of the 5 generator seeds: fewer than 20 teeth 42 called stage IV (10 wrongly, 61 missed), fewer than 10 pairs 166 (119 wrongly, 46 missed). Adding the two
rules left every other number on this page unchanged.

Stage recount, mean of the 5 generator seeds, before → after US8: "every missing tooth" 271 → 264 called stage IV
(168 → 170 wrongly) against a truth of 102 → 94; expected count, completed, 56-61 → 50-53 (7-8 → 5 wrongly, 49-54 →
46-48 missed); completed + planned, 91-95 → 92-98 (21-23 → 24-28 wrongly, 30-32 → 23-26 missed). Before US8, seed
42 alone: every missing tooth 250 (164 wrongly), expected count 48-81 (7-26 wrongly, 29-45 missed), truth 86.

**Before and after spec 033 US2** (#485; SYNTHETIC; the same command on the code before and after). The extract's
smoking and diabetes shares moved from the study's placeholders to the published US figures
([synthetic_data.md](synthetic_data.md); references items 72 and 73). Every extract is a fresh synthetic sample after
the change, so the 5-seed means are the fairer comparison. Under the defaults (`repo_v2`), shared predictors:

| | Before | After |
|---|---|---|
| patients who smoke / 10+ a day / with type 2 diabetes listed (6,000 patients, seed 42) | 18.3% / 7.9% / 7.9% | 11.7% / 5.2% / 15.6% |
| held-out extractions, AUC seed 42, completed: logistic / XGBoost | 0.81 / 0.82 (91 teeth) | 0.87 / 0.82 (95 teeth) |
| held-out extractions, AUC 5-seed mean, completed: logistic / XGBoost | 0.788 / 0.791 | 0.817 / 0.829 |
| missing at entry, AUC seed 42, completed: logistic / XGBoost | 0.91 / 0.89 | 0.97 / 0.94 |
| missing at entry, AUC 5-seed mean, completed: logistic / XGBoost | 0.930 / 0.939 | 0.961 / 0.957 |
| missing at entry, AUC 5-seed mean, completed + planned: logistic / XGBoost | 0.949 / 0.950 | 0.961 / 0.960 |
| stage III-IV patients; stage IV by the truth / every missing tooth (seed 42) | 2,411; 97 / 273 | 2,470; 115 / 280 |
| stage IV by the expected count, 5-seed mean, completed + planned: logistic / XGBoost | 89.8 / 89.8 (truth 93.8) | 90.6 / 85.4 (truth 102.2) |

With about twice the share of patients with diabetes, more of them progress to stage III-IV (the diabetes term in
`synthetic.cal_rate_per_year`), so the truth has more stage IV patients. The missing-at-entry AUC rises by about
0.01-0.03 on the 5-seed means, and the seed-to-seed range moves up (0.88-0.97 before, 0.94-0.98 after): more of the
periodontal losses now come with diabetes and fast attachment loss, which the shared predictors carry. The held-out
AUC moves inside its wide spread. The insurance shares did not change (still placeholders), nor did any study result.

**Before and after spec 033 US4** (#500; SYNTHETIC; the same command on the code before and after). The extract now
has patients with no natural teeth, at the published rates by age ([synthetic_data.md](synthetic_data.md); references
items 79 and 80). They are drawn on a random stream of their own and have no chart, extraction or answer-key rows, and
the model and the stage recount leave them out. Under the defaults (`repo_v2`), shared predictors:

| | Before | After |
|---|---|---|
| patients with no natural teeth (6,000 patients, seed 42) | 0 | 429 (7.2%; 13.8% of those 65 and over) |
| teeth the model can use under the defaults (non-third-molar, from 2018-01-01) | 79,734 | 73,315 |
| held-out extractions, AUC seed 42, completed: logistic / XGBoost | 0.87 / 0.82 (95 teeth) | 0.72 / 0.75 (89 teeth) |
| held-out extractions, AUC 5-seed mean, completed: logistic / XGBoost | 0.817 / 0.829 | 0.771 / 0.790 |
| missing at entry, AUC seed 42, completed: logistic / XGBoost | 0.97 / 0.94 | 0.98 / 0.97 |
| missing at entry, AUC 5-seed mean, completed: logistic / XGBoost | 0.961 / 0.957 | 0.956 / 0.958 |
| missing at entry, AUC 5-seed mean, completed + planned: logistic / XGBoost | 0.961 / 0.960 | 0.962 / 0.952 |
| stage III-IV patients; stage IV by the truth / every missing tooth (seed 42) | 2,470; 115 / 280 | 2,299; 98 / 261 |
| stage IV by the expected count, 5-seed mean, completed + planned: logistic / XGBoost | 90.6 / 85.4 (truth 102.2) | 87.2 / 87.2 (truth 93.4) |

The patients left out are mostly older, so the stage III-IV count falls by 171 and the true stage IV count by 17.
The missing-at-entry AUC barely moves. The held-out AUC falls on seed 42 (0.87 to 0.72), but that set is small (89
teeth, 14 of them periodontal) and the split by patient is drawn afresh once patients drop out; the 5-seed means fall
by about 0.04, within the seed-to-seed spread (0.61-0.93 before, 0.72-0.90 after). The default extract's clinics have
no state; the optional `Params.clinic_states` is not used by any committed result.

## What a real extract can and can't check

- **Can:** the same code runs unchanged on a real Open Dental extract inside its own secure environment, with the
  data-quality checks (`tooth_loss_dq.py`) first. The held-out scores against the recorded diagnosis, the
  calibration and the stage counts by rule can all be computed. Only aggregate results leave that environment.
- **Can't:** a real extract has no answer key, so the scores on teeth missing at entry and on extractions without a
  diagnosis can't be measured; that gap is stated, not estimated. The label is the recorded diagnosis item, so
  "agreement" means agreement with what the dentist recorded; checking the label itself needs the chart comparison
  or expert review in the analysis plan (section 13).
- **Before a real run** (029 US11): check that the extract's diagnosis definitions (`definition`, category 16)
  carry the codes in `itemvalue`, and count the extractions by code: a periodontal item coded otherwise would be read
  as another reason. Confirm the start date (2018-01-01 by default). Only aggregate scores leave the environment.
- **Not built yet, for a real run:** `tooth_loss_model.run` needs the synthetic answer key and labels every row
  synthetic, and script 51 only builds synthetic extracts; a run on a real extract needs a mode with no answer key
  (no missing-at-entry scores, no truth stage rule), rows labelled real, and the radiograph reading left out unless
  the practice has one (029 US12, #572).
- **Not built yet:** subgroups (section 11), the temporal and second-site validation (section 9), the sensitivity
  analyses other than the minimum age and third molars (section 12), and the sample-size check (section 6).
