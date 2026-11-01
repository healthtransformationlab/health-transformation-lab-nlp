# PROBAST and TRIPOD+AI for the status classifier (spec 023)

Which items of the two checklists Patel et al. 2026 used ([references](references.md), item 53) apply to this
repo's status classifier (`classify_status.py`, `scripts/40_classify_status.py` and
`scripts/44_medical_features.py`), and which don't. The classifier is a **synthetic benchmark**: every person,
chart, label and medical record is generated, so it checks a pipeline and says nothing about patients.

- **PROBAST** (Prediction model Risk Of Bias ASsessment Tool): 20 signalling questions in 4 domains
  (participants, predictors, outcome, analysis). Source: Moons KGM, Wolff RF, Riley RD, et al. *PROBAST:
  explanation and elaboration.* Ann Intern Med 2019;170(1):W1–W33, doi:10.7326/M18-1377.
- **TRIPOD+AI**: reporting guidance for prediction models built with regression or machine learning
  ([references](references.md), item 59).

Status: ✅ applies and is met · 🟡 applies, partly met · ➖ doesn't apply to a synthetic benchmark (and why).

## PROBAST, by domain

| Domain | What it asks | Here |
|---|---|---|
| Participants | Is the data source right for the question; are inclusions and exclusions appropriate? | ➖ No participants: a seeded generator (`study.py`, `medical_record.py`). The unit is a person's latest charted visit with a known status; uncharted visits are left out (nothing to read) |
| Predictors | Defined and measured the same way for everyone; known at the time the model would be used? | ✅ Declared once (`classify_status.FEATURE_SETS`); every predictor is in the record at the visit. 🟡 ASA class follows from the medical conditions, so it carries medical signal into the dental set: the `dental_no_asa` run shows how much |
| Outcome | Is the outcome defined without knowledge of the predictors? | 🟡 No, by design: the label (`algorithm_design`, or `truth_status`) is the 2017 AAP/EFP rules applied to the same chart the dental sets read. That is why dental features score so high; it is declared, not hidden |
| Analysis | Enough events per predictor; missing data handled; overfitting and optimism dealt with; right metrics? | ✅ Split by person (70/30, stratified by class), tuning by grouped cross-validation inside the training people only, test set used once, one-vs-rest sensitivity, specificity and AUC per class. ✅ Missing HbA1c stays missing (trees route it), never imputed. 🟡 Calibration is not reported for this comparison. ➖ Events per predictor: the study size is a generator setting, not a constraint |

**Risk of bias, overall:** not assessable in PROBAST's sense: there is no target population to be biased about.
**Applicability:** none to any real population.

## TRIPOD+AI, by section

| Section | Here |
|---|---|
| Title and abstract: say it is a prediction model, its population and outcome | ✅ Every output and page says SYNTHETIC; the outcome is the 4-class periodontal status |
| Introduction: purpose and intended use | ✅ A learning benchmark mirroring Patel et al. 2026 experiments 1 and 5; no clinical use is intended |
| Data source, participants, dates | ➖ Generated: `scripts/10_build_study.py` (seed 42, 1,200 people) and `medical_record.csv` (its own random stream) |
| Outcome definition | ✅ `classify_status.SCHEMES["four"]`: healthy (with gingivitis), stage I, stage II, stages III+IV. Gingivitis as healthy is this repo's choice; the paper has no gingivitis class |
| Predictors | ✅ `FEATURE_SETS`; sources of every medical-record number in `medical_record.CONDITIONS` |
| Sample size | ➖ Set by the generator, not justified by a calculation |
| Missing data | ✅ HbA1c missing when not measured; uncharted visits excluded |
| Analysis methods: model, tuning, split | ✅ XGBoost, grid by grouped 5-fold cross-validation, 70/30 split stratified by class and kept by person, the same split for every feature set |
| Class imbalance | ✅ Class weighting is one of the tuned options |
| Fairness and subgroups | ➖ No sex or other protected attributes are generated (spec 013 G11) |
| Model output and performance measures | ✅ Per class and averaged: sensitivity, specificity, AUC (US3 adds the Brier score) |
| Explainability | ✅ Mean \|SHAP\| per feature and feature set (`synthetic_medical_feature_sets_shap.csv`) |
| Results | ✅ [code_walkthrough.md](code_walkthrough.md#dental-and-medical-record-features-spec-023), labelled synthetic; the paper's figures are cited beside them, never mixed in |
| Limitations | ✅ The links between periodontitis and each condition are built in from published odds ratios, so the medical-only run measures the generator, not biology |
| Open science: code, data, protocol | ✅ Code, seeds and data are in the repo; the spec is `specs/023-medical-record-features/` |
| Patient and public involvement | ➖ No patients |
