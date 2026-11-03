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
| `procedurelog` | extractions (D7140, D7210): completed, planned, or done elsewhere (at the first visit, or dated at a later one); the diagnosis item (`Dx`) | [Procedure.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/Procedure.cs) |
| `definition` | the practice's own diagnosis lists (older and 2017), mapped to periodontal / other | [Def.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/Def.cs) |
| `toothinitial` | teeth missing at the first exam | [ToothInitial.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/ToothInitial.cs) |
| `perioexam`, `periomeasure` | probing depth, gingival margin (CAL is computed), bleeding, mobility | [PerioExam.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/PerioExam.cs), [PerioMeasure.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/PerioMeasure.cs) |
| `treatplan`, `proctp` | plan copies of a planned extraction, counted once | [TreatPlan.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/TreatPlan.cs), [ProcTP.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/ProcTP.cs) |
| `patient`, `disease`, `diseasedef` | age, smoking (`SmokingSnoMed`), diabetes (E10-E11) | [Patient.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/Patient.cs), [Disease.cs](https://github.com/OpenDental/OpenDental/blob/24_3/OpenDentBusiness/TableTypes/Disease.cs) |

Radiographic bone loss comes from a SIMULATED reading of each radiograph (`radiograph_bone_level`): Open Dental
stores the image, not a reading of it.

## How it is built

- **Teeth:** third molars are left out by default. Only adults are included: the minimum age
  (`ModelParams.min_age`, `--min-age`) is 18 by default; no cut-off and 30 and over are sensitivity analyses.
  A start date (`ModelParams.start_date`, `--start-date`, spec 032; 2018-01-01 by default since spec 032 US8, `""`
  for every year) keeps the teeth lost on or after it, or first charted on or after it when the loss date isn't
  recorded.
  `tooth_loss_model.exclusions` counts the teeth left out by each reason.
- **Two label sets** (FR-010): completed extractions only, and completed plus planned extractions (one per planned
  procedure, however many plan copies; a tooth planned then extracted counts once, as completed). Since 029 US9
  (#507) a planned extraction counts only when the tooth is **recorded missing at a later visit within 365 days of
  the plan** (`ModelParams.planned_window_days`, `--planned-window-days`): a planned extraction often never happens,
  so one whose tooth is still in the mouth isn't tooth loss. One still in the mouth, or missing after the window, has
  no label. The earlier rule (every planned extraction with a diagnosis counts) is kept as a sensitivity setting,
  `--planned-window-days none`. In the synthetic extract the later loss is an extraction by another provider dated
  at that visit; on a real extract the date may come from a dated `toothinitial`. Every tooth recorded missing later
  counts as missing in the stage recount, with the model's probability.
- **Two predictor sets:** *shared* (what every missing tooth has: tooth type, neighbours' worst CAL, the mouth at
  the first exam, teeth missing at entry, age, smoking, diabetes) is the applied model; *own* adds the tooth's own
  last measures and how good that chart was, and is shown beside it.
- **Models:** logistic regression (L2, C = 1, standardised, median imputation and missing indicators) and XGBoost
  (depth 3, 200 trees, learning rate 0.05, subsample 0.8), with three baselines.
- **Validation:** 80/20 split by patient, stratified on the outcome, seed 42, with XGBoost tuned by 5-fold
  cross-validation (the defaults since spec 032 US8; before it, 70/30 with fixed settings, the `repo_v1` preset). Both label sets are scored on the same
  held-out extractions. The applied sets (teeth missing at entry, extractions without a diagnosis) are scored
  against the synthetic answer key, which is never a feature. Options (spec 032): `--test-share`; `--split-unit
  visit` holds out random teeth instead of patients, so one patient's teeth can be on both sides, which flatters the
  score: the run prints how many patients that is, and it is never the default; `--cv-folds K` tunes XGBoost by
  K-fold cross-validation over a small fixed grid, folds grouped by patient unless the split is by visit.
- **Measures:** AUC, Brier score, calibration intercept and slope, a 10-bin calibration table, and sensitivity,
  specificity and predictive values at 0.5 and at the Youden threshold chosen on the training teeth. 95% intervals
  from 1,000 bootstrap resamples of patients. The run is repeated on 5 generator seeds.

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

**Under the planned-extraction rule since 029 US9** (#507; the defaults, SYNTHETIC). A planned extraction now counts
only when the tooth is recorded missing at a later visit within 365 days; the earlier rule (every planned extraction
with a diagnosis counts) is run beside it with `--planned-window-days none`. Same command, same five generator seeds
and 1,000 bootstrap resamples. The start date leaves out 89,986 of the 168,000 non-third-molar teeth (78,014 left).
Generator seed 42, shared predictors, AUC (95% CI); the completed + planned columns are where the rule changes:

| Teeth scored | completed: logistic | completed: XGBoost | completed + planned: logistic | completed + planned: XGBoost |
|---|---|---|---|---|
| held-out extractions (96 teeth, 89 patients) | 0.83 (0.69-0.93) | 0.86 (0.75-0.95) | 0.84 (0.70-0.94) | 0.84 (0.72-0.94) |
| missing at the first exam (3,519 teeth, 1,447 patients) | 0.93 (0.91-0.94) | 0.94 (0.92-0.96) | 0.92 (0.90-0.94) | 0.93 (0.91-0.95) |
| extractions without a diagnosis (102 teeth) | 0.97 (0.91-1.00) | 0.98 (0.94-1.00) | 0.94 (0.86-0.99) | 0.96 (0.92-0.99) |
| *earlier rule, held-out extractions* | 0.79 (0.63-0.93) | 0.85 (0.73-0.95) | 0.80 (0.63-0.94) | 0.84 (0.70-0.94) |
| *earlier rule, missing at the first exam* | 0.93 (0.91-0.95) | 0.93 (0.91-0.95) | 0.95 (0.93-0.96) | 0.96 (0.95-0.97) |

The completed + planned set now trains on 424 teeth, not 506: planned extractions whose tooth stayed in the mouth no
longer count. (The completed columns move a little too: teeth that go missing later leave the chart, which changes the
synthetic extract.) Across the 5 generator seeds the held-out AUC of the shared models ranges from 0.76 to 0.89 (0.69
to 0.85 under the earlier rule). The AUC hardly moves; the stage recount does. Of the 2,374 patients at stage III-IV
by worst CAL, the synthetic truth puts 103 at stage IV:

| Expected count, shared predictors | stage IV | wrongly called IV | IV missed |
|---|---|---|---|
| completed + planned, logistic / XGBoost: new rule | 63 / 59 | 10 / 12 | 50 / 56 |
| completed + planned, logistic / XGBoost: earlier rule | 95 / 92 | 25 / 25 | 33 / 36 |
| completed, logistic / XGBoost: new rule | 37 / 25 | 3 / 2 | 69 / 80 |

Counting planned extractions still in the mouth as tooth loss called 25 patients stage IV whom the synthetic truth
puts at stage III; the new rule calls 10-12, and misses more stage IV patients in exchange. Every missing tooth
(289 stage IV, 186 wrongly) and recorded extractions only (0) bracket it. These are agreement with a synthetic answer
key, whose planned-then-missing share (`Params.planned_then_missing`, 0.5) is a placeholder; a real extract decides
how much this matters.

The tables from here down are runs before 029 US9.

**Under the defaults since spec 032 US8** (#448; [presets](presets.md), `repo_v2`): teeth lost (or first charted)
from 2018-01-01, an 80/20 split by patient and XGBoost tuned by 5-fold cross-validation. The start date leaves out
88,266 of the 168,000 non-third-molar teeth (79,734 left), so every set is smaller and the intervals wider.
Generator seed 42, shared predictors, AUC (95% CI):

| Teeth scored | completed: logistic | completed: XGBoost | completed + planned: logistic | completed + planned: XGBoost |
|---|---|---|---|---|
| held-out extractions (95 teeth, 87 patients) | 0.87 (0.75-0.97) | 0.82 (0.65-0.96) | 0.83 (0.64-0.97) | 0.83 (0.66-0.95) |
| missing at the first exam (3,630 teeth, 1,483 patients) | 0.97 (0.96-0.98) | 0.94 (0.93-0.96) | 0.96 (0.95-0.97) | 0.96 (0.95-0.97) |
| extractions without a diagnosis (78 teeth) | 0.93 (0.86-0.99) | 0.97 (0.93-1.00) | 0.94 (0.88-0.99) | 0.96 (0.92-1.00) |

Across the 5 generator seeds the held-out AUC of the shared models ranges from 0.61 to 0.93. The start date and the
minimum age choose the teeth that train and score the model, not how many teeth a patient has lost: the stage recount
still counts every missing tooth but third molars (`tooth_loss_model.stage_teeth`), and the fitted model gives the
unlabelled ones outside its own teeth a probability too. So stage IV, all 2,470 patients at stage III-IV by worst
CAL, is the same under both: 280 by every missing tooth, 52 by fewer than 20 teeth, 180 by fewer than 10 occluding
pairs, 115 by the synthetic truth; by the expected count (shared predictors) 57 / 25 (completed, logistic / XGBoost)
and 91 / 84 (completed + planned), against 66 / 68 and 98 / 94 under the earlier settings, as the model itself
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

**Held-out extractions** (266 teeth with a recorded diagnosis, 237 patients, 18% periodontal), shared predictors:

| Label set | Model | AUC (95% CI) | Brier | Calibration slope | Sensitivity / specificity at 0.5 |
|---|---|---|---|---|---|
| completed | logistic | 0.84 (0.76-0.92) | 0.09 | 0.98 (0.75-1.33) | 0.46 / 0.98 |
| completed | XGBoost | 0.78 (0.69-0.87) | 0.09 | 0.77 (0.60-1.04) | 0.48 / 0.98 |
| completed + planned | logistic | 0.84 (0.76-0.91) | 0.10 | 0.84 (0.66-1.13) | 0.60 / 0.93 |
| completed + planned | XGBoost | 0.82 (0.74-0.90) | 0.10 | 0.72 (0.55-0.94) | 0.60 / 0.93 |
| baseline: outcome rate | - | 0.50 | 0.15 | - | - |

With the tooth's own measures, AUC is 0.84 (logistic) and 0.80 (XGBoost) on completed extractions: about the same as
the shared set. Adding planned extractions raises sensitivity but shifts the probabilities up (calibration
intercept -0.44 and -0.17), since planned extractions in the synthetic set are mostly periodontal. Across the 5
generator seeds the held-out AUC of the shared models ranges from about 0.75 to 0.85: the held-out set is small, so
one seed's number shouldn't be read alone.

**Teeth missing at the first exam** (7,770 teeth, 3,154 patients, third molars left out; 21% periodontal by the
answer key), shared predictors (the tooth has no own measures there):

| Label set | Model | AUC (95% CI) | Brier | Calibration intercept / slope | Mean probability | Sensitivity / specificity at 0.5 |
|---|---|---|---|---|---|---|
| completed | logistic | 0.97 (0.96-0.97) | 0.07 | -0.33 / 2.06 | 0.25 | 0.77 / 0.95 |
| completed | XGBoost | 0.94 (0.93-0.95) | 0.07 | -0.19 / 1.26 | 0.23 | 0.72 / 0.96 |
| completed + planned | logistic | 0.96 (0.95-0.96) | 0.08 | -0.90 / 1.41 | 0.31 | 0.90 / 0.91 |
| completed + planned | XGBoost | 0.95 (0.95-0.96) | 0.07 | -0.78 / 1.40 | 0.29 | 0.90 / 0.90 |
| baseline: every missing tooth is periodontal | - | 0.50 | 0.79 | - | 1.00 | 1.00 / 0.00 |

Across the 5 generator seeds the AUC there ranges from 0.93 to 0.97. Specificity is the share of non-periodontal
losses the model doesn't call periodontal: 0.95-0.98 on completed extractions, 0.88-0.92 with planned extractions
added, against 0 for "every missing tooth". On this seed the completed-extraction models' probabilities run a little
high on average (intercept below 0, mean 0.23-0.25 against 21% periodontal) and too close together (slope above 1),
so at 0.5 they find about three quarters of the periodontal teeth; with planned extractions added they run higher
(intercept about -0.8 to -0.9). The AUC is higher than on the held-out
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

**Extractions without a diagnosis** (149 teeth, 11% periodontal by the answer key): AUC 0.97 (0.95-0.99) and 0.96
(0.92-0.99) for the shared logistic and XGBoost models on completed extractions, Brier 0.05; the calibration
intercept is a little below 0 (-0.45 and -0.52).

**Stage III vs IV** (2,470 patients whose worst CAL in the record is 5 mm or more):

| Counting rule | Stage IV | Agree with truth | Called IV, truth III | Called III, truth IV |
|---|---|---|---|---|
| recorded periodontal extractions only | 0 | 2,355 | 0 | 115 |
| every missing tooth | 280 | 2,305 | 165 | 0 |
| expected, completed, logistic | 66 | 2,409 | 6 | 55 |
| expected, completed, XGBoost | 68 | 2,407 | 8 | 55 |
| expected, completed + planned, logistic | 98 | 2,411 | 21 | 38 |
| expected, completed + planned, XGBoost | 94 | 2,401 | 24 | 45 |
| fewer than 20 teeth left (spec 032) | 52 | 2,383 | 12 | 75 |
| fewer than 10 occluding pairs left (spec 032) | 180 | 2,297 | 119 | 54 |
| the synthetic truth | 115 | 2,470 | 0 | 0 |

"Every missing tooth" calls 280 patients stage IV, 165 of them wrongly: about two and a half times the true number.
The expected count calls 66-98, with 6-24 wrongly and 38-55 missed; with planned extractions it is the closest to the
truth, and recorded periodontal extractions alone find no stage IV patient by tooth loss. On this seed the
completed-extraction models still undercount (66-68 against 115), missing about half the stage IV patients.

The last two rules (spec 032 US4, #443) don't ask why teeth were lost: they call stage IV from the teeth left,
fewer than 20 teeth or fewer than 10 occluding pairs (upper and lower teeth that meet), third molars left out as in
`aces.py`, counted from the whole tooth table (`labels.stage4_rule`, rules `teeth_lt_20` and `pairs_lt_10`). Fewer
than 20 teeth calls 52 stage IV (12 wrongly, 75 missed): it misses most true stage IV patients, who keep 20 or more
teeth. Fewer than 10 pairs calls 180 (119 wrongly, 54 missed): a tooth lost for any reason can break a pair, so this
rule overcounts like "every missing tooth", though less. Mean of the 5 generator seeds: fewer than 20
teeth 43 called stage IV (10 wrongly, 69 missed), fewer than 10 pairs 171 (120 wrongly, 51 missed). Adding the two
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
