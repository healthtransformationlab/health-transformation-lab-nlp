# Feature Specification: remaining phenotyping and data-quality methods from the published literature

**Feature Branch**: `013-literature-methods`

**Created**: 2026-10-27

**Status**: draft

**Input**: "Collect the data and make sure we have the methods" for periodontal phenotyping from
structured data and notes, judged by a data-quality framework. This is a check of the repo against
methods described in the **published** literature. Nothing here comes from, or describes, any
organization's plans, data or study.

> Personal learning project; synthetic data; public sources only. Public datasets (NHANES) are
> downloaded by a script at run time and only aggregates are committed.

## What the repo already has

| Method (published source) | Where |
|---|---|
| 2017 AAP/EFP staging, grade and extent from a chart (Tonetti, Greenwell & Kornman 2018) | `labels.py`, `docs/staging_grading.md` |
| CDC/AAP 2012 surveillance case definitions (Eke et al. 2012) | `sites.cdc_aap`, spec 006 |
| Site- and tooth-level charts, missing teeth and why | `sites.py`, spec 006 |
| Rule-based cascade over evidence sources (exam form → diagnosis code → note NLP → chart), every order scored (Patel et al. 2022) | `phenotype.py`, `18_phenotype_order.py`, spec 005 |
| Agreement between methods; agreement with reviewers (kappa, weighted kappa) | `phenotype.agreement_matrix`, `reliability.py` |
| Sensitivity, specificity, PPV, NPV on the yes/no periodontitis question | `eval/score.py`, spec 011 |
| Temporal plausibility: CAL or bone loss falling, periodontitis "resolving", stage drops (Kahn et al. 2016) | `plausibility.py` |
| Conformance, completeness and plausibility checks, per clinic (Kahn et al. 2016) | `dq.py`, `20_data_quality.py` |
| Clinic-level prevalence with Wilson CIs, NHANES comparison | `prevalence.py`, `19_prevalence.py` |
| Note NLP: rules, encoders, LLM readers; chart review in Label Studio | specs 002, 004 |
| Progression model with held-out AUROC and permutation importance | `prediction.py` |

## Gaps (this spec)

| # | Gap | Published source | Priority |
|---|---|---|---|
| G1 | **ACES** staging for epidemiological/secondary data: case definition and both decision trees (minimal information; additional information) | Holtfreter et al., J Clin Periodontol 2024; Tay et al., J Clin Periodontol 2025 | P1 |
| G2 | **Stage III vs IV without "teeth lost to periodontitis"**: configurable rule, one of: < 20 teeth; < 10 occluding pairs; all missing teeth count as lost to periodontitis; a rule over extraction diagnoses. Needs an **occluding-pair count** from the tooth chart | as reviewed in Tay 2025 and West et al. 2025 | P1 |
| G3 | **Alternative case threshold**: interdental CAL > 2 mm on ≥ 2 teeth (more specific than any CAL) | Tokede et al. (periodontal phenotyping decision tree) | P1 |
| G4 | **NHANES 2009–2014 periodontal exam**: download the public files (OHXPER, OHXDEN, DEMO), compute CDC/AAP and ACES prevalence with survey weights, and check against the published figures (Eke 2018; Tay 2025) | CDC NCHS (public domain) | P1 |
| G5 | **Reliability of CAL** (not just agreement): multilevel model of CAL over time with patient, tooth and site levels, time as fixed effect; ICC per level. Needs synthetic repeated site charts with realistic probing error | de Vet et al. 2006 (Liaw et al. 2013 removed, #405: it doesn't define reliability) | P2 |
| G6 | **Probabilistic reference standard** (PheValuator-style): very-likely-positive and very-likely-negative sets, a diagnostic model giving each visit a probability, then expected sensitivity, specificity, PPV and NPV per method | Swerdel, Hripcsak & Ryan 2019 (OHDSI PheValuator) | P2 |
| G7 | **Completeness à la Zozus**: data-element completeness (expected schema vs extract), column-value completeness per phenotype input, row completeness (every input needed for the chart algorithm present); results on three scales: all visits, complete cases, reference set | Zozus et al. 2014 (NIH Collaboratory) | P2 |
| G8 | **Transitions over time**: phenotype at a visit vs 1–2 years later, excluding people treated in between; transition matrix (Sankey input) and share improving | Kahn et al. 2016 (temporal plausibility) | P2 |
| G9 | **Consistency by provider type** (dentist, hygienist) and provider, not only clinic | Zozus et al. 2014 | P3 |
| G10 | **Classification model**: gradient-boosted trees for 5-level (healthy/gingivitis, I–IV) and 3-level (healthy/gingivitis, I–II, III–IV) status; 80/20 split; 5-fold CV over max depth, learning rate, lambda, class weight, min child weight; one-vs-rest metrics; SHAP importance compared with published risk factors. Could adopt from Patel et al. 2026: the 4-class scheme (healthy, I, II, III+IV), a 70/30 stratified split, the Brier score per class, and the PROBAST and TRIPOD-AI checklists | Patel et al. 2022, Front Artif Intell (XGBoost; SHAP use not checked against the full text); Patel et al. 2026, JDR Clin Trans Res (references item 53); Swinckels et al.; Shimpi et al. | P3 |
| G11 | **Features the model needs** in the synthetic data: DMFT/DMFS from an odontogram plus later procedures; xerostomia-causing medications; systemic disease (ICD-10); insurance; site type (fixed clinic, mobile, long-term care); provider licence; blood pressure and pulse; age, sex, race-ethnicity. The medical-record side (systemic conditions, HbA1c, blood pressure, ASA class; dental-only, dental+medical and medical-only runs) is spec 023 | literature above; Patel et al. 2026 (references item 53) | P3 |
| G12 | **Synthetic extract in a public EDR schema** (Open Dental's published schema: perio exam and measures, exam sheets, procedure notes, treatment plans), mapped to OMOP, so the same code runs on a real extract | Open Dental public schema docs | P3 |
| G13 | **Published prevalence benchmarks** in one table with citations and definitions (practice-based 2017 staging; NHANES; other surveys) | each paper, numbers checked against the paper | P2 |

## Requirements

- **FR-001** (G1–G3) `labels_aces.py` (name tbd) implements the ACES case definition and both trees
  on the site/tooth tables of spec 006, with every rule cited to the paper and every choice that
  the paper leaves open exposed as a parameter. R twin and parity test.
- **FR-002** (G2) `occluding_pairs(teeth)` from present teeth (universal numbering, opposing pairs
  per published definition). Python = R.
- **FR-003** (G4) `scripts/37_nhanes_perio.py --download DIR` reads the NHANES XPT files, maps sites
  from the variable labels (not hard-coded letters), applies CDC/AAP and ACES, and writes weighted
  prevalence with design-based 95% CIs. Committed: the aggregate table only. Test against a small
  synthetic file in NHANES layout. A Databricks job runs the download (this container cannot reach
  cdc.gov).
- **FR-004** (G5) synthetic repeated charts with examiner error; `reliability_cal.py` fits the
  multilevel model (statsmodels; R `lme4`) and reports ICCs; parity within tolerance.
- **FR-005** (G6) `phevaluator.py`: xSpec/xSens sets from rules, a regularized logistic diagnostic
  model, expected confusion matrix per method.
- **FR-006** (G7–G9) extend `dq.py`: element, column and row completeness; three scales; strata by
  provider type.
- **FR-007** (G10–G11) `classify_status.py` with xgboost (new optional extra `ml`), SHAP; R twin is
  out of scope (model outputs are not part of label/scoring parity).
- **FR-008** (G13) `docs/benchmarks.md`: every number cited to the paper it came from.

## Out of scope

- Any real or non-public data, documents or code lists. Real diagnosis-code sets, form fields or
  extract layouts are parameters to be filled in elsewhere, not committed here.
- Radiograph AI (spec 003 covers the synthetic version).

## Success criteria

- SC-001 Each gap has a test written first, then code; Python and R agree where labels or scores change.
- SC-002 NHANES prevalence under CDC/AAP reproduces the published 2009–2014 figures within their
  95% CIs when run on the real files; this is a check of the code, labelled as such.
- SC-003 Every output on synthetic data is labelled synthetic or simulated.
