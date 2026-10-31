# Analysis plan: was a missing tooth lost to periodontitis? (spec 029)

**Status:** pre-specified on 2026-10-31, before any model result exists (#395). Any later change goes in the change log
at the end, dated, with its reason, so results can be checked against what was planned.
**Reporting:** TRIPOD+AI (Collins et al., BMJ 2024; [references](../../docs/references.md) item 59), since this is a
prediction model, and RECORD (Benchimol et al. 2015, item 60), since it uses routinely collected records. The headings
follow TRIPOD+AI's order.
**Data:** synthetic only in this repo (`open_dental.py`). The same code is meant to run on a real Open Dental extract
inside its own secure environment. No real data comes into this repo.

Each item is marked:
- **Fixed:** decided here, and the code follows it.
- **Planned:** decided, not built yet.
- **Decision:** the study lead decides. The default used until then is named.

## 1. Objective

**Fixed.** For each tooth missing from an adult's record, estimate the probability that it was lost to
periodontitis. Use it to count teeth lost to periodontitis per patient. That count separates stage III from stage IV
under the 2017 AAP/EFP classification.

This estimates why a tooth already lost was lost. It doesn't predict future loss.

## 2. Data source and setting

- **Fixed:**
  - the source is a dental practice's Open Dental records: procedures, treatment plans, perio charts, the missing-tooth
    record (`toothinitial`), radiographs, medical history;
  - the cleaned silver tables and `tooth_loss.tooth_table` are described in [spec.md](spec.md) and
    [research.md](research.md).
- **Decision (study period):**
  - default: all years;
  - sensitivity: from the year the practice fully used the 2017 diagnosis list.

## 3. Participants and teeth

- **Decision (age):**
  - default: no cut-off;
  - sensitivity: 18 and over, and 30 and over (the national survey's adults).
  - Age is measured at the tooth's loss, or at the first visit for a tooth missing at entry.
  - Children's teeth are mostly baby teeth or orthodontic extractions, not periodontitis.
- **Fixed:** third molars are excluded from the label and the stage count by default ([spec.md](spec.md), edge cases).
  Including them is a sensitivity analysis.
- **Fixed:** the unit is the tooth; patients contribute several teeth, and every split and interval respects that
  (sections 9 and 10).

## 4. Outcome (the label)

- **Fixed:**
  - 1 = the tooth's extraction carries a periodontal diagnosis item;
  - 0 = it carries another diagnosis item.
  - Items from both of the practice's diagnosis lists (older and 2017) are mapped by a declared lookup
    (`open_dental.DIAGNOSIS_LOOKUP`).
  - An extraction with no diagnosis has no label.
- **Fixed, two label sets (FR-010):**
  - completed extractions only;
  - completed plus planned extractions (one per procedure, however many plan copies; completed wins).
  - Both are reported.
- **Fixed, a limit:** the label is the dentist's recorded diagnosis, not an independent judgement. On real records,
  "agreement" means agreement with the recorded diagnosis. Section 13 covers how to check the label itself.

## 5. Predictors

**Fixed.** Only what was charted on or before the tooth's loss (`tooth_loss.tooth_table`). Two sets:
- **shared:** available for every missing tooth, including those missing at entry: tooth type, the neighbours' worst
  attachment loss, mouth-level measures at the first exam (sites with attachment loss of 5 mm or more, deepest
  pocket, bleeding, worst radiographic bone loss), teeth missing at entry, age, smoking, diabetes;
- **own:** the shared set plus the tooth's own last measures (pocket depth, attachment loss, bleeding, mobility,
  radiographic bone loss) and the quality of that chart (complete, partial, copied, uniform).

The applied model uses the shared set, because teeth missing at entry have no own measures. The own-measures model is
reported beside it to show what those measures add.

## 6. Sample size

- **Planned:** before fitting on real data, check the labelled teeth against the minimum sample size for a binary
  prediction model (Riley et al., BMJ 2020; item 61). The inputs are the outcome rate, the number of predictor
  parameters, and an expected R² taken from the synthetic run.
- **Planned:** if there are too few labelled teeth, the planned extractions (label set 2) and fewer predictors are the
  fixes, in that order.
- **On synthetic data,** the size is a parameter (`Params.n_patients`), set large enough that the intervals are narrow.

## 7. Missing data

- **Fixed:** missingness is expected and is part of the question: visits without a chart, partial charts, unread
  radiographs ([spec.md](spec.md) US6).
- **Fixed, logistic regression:** median imputation fitted on training data only, plus one missing-indicator per
  predictor with any missing values.
- **Fixed, XGBoost:** uses missing values as they are.
- **Fixed:** report the share missing for each predictor, by label set and by split.
- **Planned:** sensitivity analyses on charted teeth only, and with every mess rate at zero (synthetic `NO_MESS`).
  Together they show what messy records cost.

## 8. Models

- **Fixed:** logistic regression (L2, C = 1, standardised inputs) and XGBoost.
  - XGBoost: depth 3, 200 trees, learning rate 0.05, subsample 0.8.
  - Hyperparameters are fixed here, not tuned on the test set. Tuning, if any, uses cross-validation within the
    training set only.
- **Fixed:** no resampling for class imbalance, since it would distort the probabilities. Report the outcome rate in
  every set instead.
- **Fixed, baselines:**
  - "every missing tooth counts as periodontitis";
  - "only recorded periodontal extractions count";
  - the outcome rate alone (no predictors).

## 9. Validation

- **Fixed, internal:** split 70/30 by patient, stratified on the outcome, seed fixed. The test set is used once, after
  everything else is fixed.
- **Planned, over time:** train on extractions before a cut-off date and test on those after. Default: the date the
  practice switched diagnosis lists.
- **Planned, a second site:** the same code on a second practice's extract, unchanged. This is the strongest check, and
  where a thesis's external validity comes from.
- **Fixed, applied set:**
  - the model is applied to teeth missing at entry and to extractions without a diagnosis;
  - on synthetic data both have a known answer (`tooth_loss_truth`), so the gap from the held-out score is measured;
  - on real data that gap can't be measured, and that is stated.

## 10. Performance measures

- **Fixed, discrimination:** AUC.
- **Fixed, calibration:** calibration intercept and slope, and a 10-bin table and plot.
- **Fixed, overall:** Brier score.
- **Fixed, classification:** sensitivity, specificity and positive and negative predictive value at a threshold of
  0.5, and at the threshold chosen on the training set (Youden). Both are named.
- **Fixed, uncertainty:** 95% intervals from 1,000 bootstrap resamples of patients, not teeth.
- **Fixed, stability:** the synthetic run is repeated on 5 generator seeds, and the spread is reported.
- **Fixed, per patient:** stage III vs IV under four counting rules: recorded only, every missing tooth, expected from
  the model, and (synthetic only) the truth. Report how many patients each rule moves between III and IV.
- **Fixed:** metrics have base-R twins, checked by `r/tests/test_parity.R` (FR-005, FR-006).

## 11. Subgroups and fairness

**Planned.** Every measure in section 10, by:
- age band (under 35, 35–64, 65 and over);
- sex;
- type of site (office; mobile, nursing home or school);
- diabetes; smoking;
- chart quality of the tooth's last chart.

Subgroups with fewer than 30 labelled teeth are reported as counts only.

## 12. Sensitivity analyses

**Planned**, each a single change from the main analysis:
- label set (completed vs completed plus planned);
- diagnosis list (older vs 2017 items only);
- age cut-off (none, 18+, 30+);
- third molars included;
- shared vs own predictors;
- messy vs `NO_MESS` records (synthetic);
- study period (all years vs after the list switch).

## 13. Checking the label itself (real data)

**Decision.** The recorded diagnosis may be wrong or missing. Options, cheapest first:
1. Compare it with the chart: teeth extracted as periodontal should show deeper pockets and more attachment loss
   beforehand than teeth extracted for other reasons.
2. A small expert review: for example 50–100 extractions, two reviewers, each blind to the recorded diagnosis.
   Report their agreement (Cohen's kappa) and their agreement with the recorded diagnosis.

## 14. Model output

**Fixed:**
- one row per patient and missing tooth, with its probability and the label at the threshold, model, label set and
  run (gold `fact_tooth_loss_prediction`);
- one row per patient with the stage under each counting rule.

## 15. Open science and ethics

- **Fixed:** code, seeds and synthetic data are public, and every number is reproducible from the repo.
- **On real data:** ethics approval and data-use terms belong to the data holder's process. Only aggregate results
  leave the secure environment.
- **Planned:** register this plan, for example on OSF, before the first real-data run.

## 16. Reporting

**Planned.** Results are written against the TRIPOD+AI checklist, with each item's location given. Limitations are
stated plainly:
- synthetic results are agreement with a synthetic answer key;
- the label is the recorded diagnosis;
- the applied set can't be checked on real data.

## Change log

| Date | Change | Reason |
|---|---|---|
| 2026-10-31 | Plan written | Before any model result (#395) |
