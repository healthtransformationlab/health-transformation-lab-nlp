# Action items: where the repo differs from the study design

Each row is a difference between what the study design describes and what
this repo does, or a decision the repo can't make on synthetic data. Numbers
are from **simulated** reviewers and synthetic patients: they show what the
analysis produces, not results.

Status: **Open** = needs a decision or real data; **Done** = implemented here,
needs confirming.

## Integrated phenotype

| # | Difference | What the repo does now | Action | Owner | Status |
|---|---|---|---|---|---|
| A1 | Study design uses **five categories** (healthy/gingivitis combined, stage I–IV); the repo labels six | Both: reviewers still label six; every reliability table is also reported on five (`reliability_5cat/`) | Agree which is the headline; keep six in Label Studio so healthy vs gingivitis isn't lost | study lead | Done, confirm |
| A2 | **Starting evidence order** in the design is exam form → diagnosis code → note NLP → periodontal-chart algorithm. The repo's earlier placeholder put the chart first | Design order is now `algorithm_design` (`RULES_DESIGN`); the old order stays as `algorithm_v0` for comparison; the paper's own order is `algorithm_patel2022` (spec 024) | Checked against the full text (PMC9788909; #389, #204). The paper's order is the structured diagnosis section (the clinician's recorded diagnosis), then clinical notes, then periodontal charting, each only filling gaps. So the exam-form-first order is this repo's own, not the paper's: (1) the paper has no exam-form or PSR step (the periodontal evaluation form is read only as note text, and for bone loss); (2) it has no diagnosis codes attached to done or planned procedures, so that step, and planned vs completed, are the repo's own stand-in for the diagnosis section; (3) its charting uses the most recent visit and complete charts only; (4) it never validated the order against expert review. Study lead: keep or drop the exam-form and codes steps, and decide planned vs completed | study lead | Checked; decision open |
| A3 | The design lets the order change if another evidence type proves more accurate | `18_phenotype_order.py` scores all 24 orders: chosen on half the review charts, reported on the other half with the acceptance test | Pre-specify the selection metric (kappa vs consensus here) and margin before the real reviews | study lead | Done, confirm |
| A4 | Dry run: design order held-out kappa **0.74** (inconclusive) vs **0.97** for chart > notes > exam form > dx code | Simulated reviewers are generated from truth and the chart is closest to truth, so chart-first wins **by construction** | Decide with real reviewer labels only | — | Open |
| A5 | Procedure codes (CDT) are not in the design's four evidence groups | Excluded from `algorithm_design`; still used as evidence in v0 and the comparisons | Confirm they stay out of the integrated phenotype | study lead | Open |
| A6 | Radiograph AI is not in the design | Not in `algorithm_design`; v0 uses it as a lower bound when the chart is missing (spec 003) | Decide whether it enters the phenotype | study lead | Open |

## Validation over time and against external evidence

| # | Difference | What the repo does now | Action | Owner | Status |
|---|---|---|---|---|---|
| B1 | **Temporal plausibility** wasn't checked before; synthetic visits were independent | Patient histories: attachment/bone loss never recover; therapy lowers pockets and bleeding; checks flag CAL drops > 1.5 mm, RBL drops > 5 points, teeth regained, periodontitis "resolving", stage drops (`plausibility.py`, Py + R) | Periodontist to confirm the tolerances (probe error, RBL measurement error) | periodontist | Done, confirm |
| B2 | Dry run: the design-order phenotype drops a stage at **24%** of follow-up visits (chart alone: 0.6%) because forms and codes vary visit to visit | Reported per method in `data_quality/temporal_by_method.csv` | Use temporal plausibility as a second criterion when choosing the evidence order | study lead | Open |
| B3 | Repo assumes **the stage reached is kept** after therapy, even when pockets shrink below a complexity threshold | Truth keeps the highest stage; the probing-chart evidence reads each visit alone | Confirm against the classification's guidance | periodontist | Open |
| B4 | Grade from **direct evidence** needs a 5-year history | Not generated (histories ≤ 3 years); grade uses % bone loss ÷ age | Decide whether real histories are long enough; otherwise document indirect grading | study lead | Open |
| B5 | **Clinic-level prevalence**: synthetic clinics only | 8 clinics with their own case mix and charting rates; person-level prevalence with Wilson 95% CIs (`19_prevalence.py`, Py + R) | Define "clinic" in real data (location, provider group); set a minimum number of people per clinic to report | data engineering | Done, confirm |
| B6 | **External comparison**: published figures use different case definitions | Adults 30+: synthetic design phenotype 57% (95% CI 54–60%) vs NHANES 2009–2014 42.2% any, 7.8% severe (CDC/AAP definitions). The generator's mix is a placeholder, so the gap means nothing yet | Pick directly comparable published studies (practice-based, 2017 staging); compute CDC/AAP case definitions too (spec 006, needs site-level data) | study lead | Open |
| B7 | **Transitions 1–2 years later** in people not treated in between (spec 013 G8) | Each visit paired with the first visit 365–730 days later; five-category transition matrix (Sankey input) and share better / same / worse per method (`20_data_quality.py` → `transitions_*.csv`, Py + R). Dry run: the design-order phenotype improves in **13.7%** of untreated pairs, the chart alone in **0.5%** | Agree the window and what counts as treatment (scaling and root planing? any perio procedure?) | study lead | Done, confirm |
| B8 | **ACES** (spec 013 G1–G3): the 2018 classification on charts alone, with the published variants for stage III vs IV and a stricter case threshold | `aces.py` (Py + R). Synthetic exams: ACES agrees with the worksheet on most charts; it moves stage III → II when PD ≥ 6 mm is on one tooth only, and IV → III when teeth are lost but ≥ 10 opposing pairs remain | Confirm the ACES rules against the primary paper (BOP threshold, furcation/mobility/vertical defect) before using it on real data; choose the stage IV rule | study lead | Done, confirm |
| B9 | **NHANES 2009–2014 from the public files** (spec 013 G4): real charts, CDC/AAP and ACES, survey-weighted | `nhanes.py`, `38_nhanes_perio.py`, Databricks job `nhanes_perio` (not run yet: needs cdc.gov) | Run the job; compare with Eke 2018 (42.2% any, 7.8% severe) and Tay 2025 (ACES); investigate any gap outside the published CIs before trusting the case definitions | study lead | Open |

## Data quality

| # | Difference | What the repo does now | Action | Owner | Status |
|---|---|---|---|---|---|
| C1 | Data trustworthiness wasn't assessed as such | Conformance, completeness and plausibility checks overall and per clinic, using OHDSI Data Quality Dashboard terms (`20_data_quality.py`) | Agree thresholds (5% failing used here) and which checks matter | data engineering | Done, confirm |
| C2 | Dry run: temporal checks catch **33%** of the injected charting errors (0.2% false flags) | Decimal slips are caught; another patient's chart often isn't | Add cross-evidence checks (chart vs note vs codes at the same visit) | data engineering | Open |
| C3 | Data quality, order search and prediction were Python only | R twins in `r/R/09_spec005.R`: all 24 orders, every data-quality check and both progression models match Python (parity section 10). The halves and test people are shared files, so bootstrap CIs and permutation importance still differ slightly by RNG | Confirm approximate CIs are acceptable | data science | Done, confirm |
| C4 | **Completeness after Zozus et al.** (spec 013 G7): column-value, row-value and data-element completeness; prevalence on three scales (all visits, complete cases, reviewed reference set) | `completeness.py`, `20_data_quality.py` → `completeness_*.csv`, `prevalence_by_scale.csv` (Py + R for the scales). Synthetic charts are never partial, so row completeness is 100% here; data-element completeness needs the source system's published schema (G12) | Add partial charts to the generator; list the expected tables and columns from the vendor's public schema | data engineering | Done, confirm |
| C5 | **Reliability of CAL**, not just agreement (spec 013 G5): patient, tooth and site variance and probing error from repeated charts; ICC per level; how often the worst-CAL stage band changes between two charts of an untreated mouth | `reliability_cal.py`, `37_cal_reliability.py` (nested ANOVA, Py + R exact; REML via statsmodels for real, unbalanced charts). SIMULATED, placeholder components: at 0.8 mm probing error, site ICC 0.68 and the stage band changes in 24% of visit pairs (down in 9%) | Fit REML on real repeated charts; decide whether to include examiner as a level | data science | Done, confirm |

## Prediction

| # | Difference | What the repo does now | Action | Owner | Status |
|---|---|---|---|---|---|
| D1 | The study design calls for predicting who gets worse; this repo had no prediction step until spec 005 added one | Predicts whether the next visit's phenotype is worse, from the current visit only (`21_predict_progression.py`; explained in [walkthrough step 12](code_walkthrough.md#12-predict-progression)) | Define the outcome (stage up? any CAL gain?) and horizon (next visit? 1, 3, 5 years?) | study lead | Done, confirm |
| D2 | Dry run: with the phenotype as outcome, **22.6%** of visit pairs "progress" vs **7.5%** in truth; the model mostly learns phenotype noise (current stage dominates) | Reported for both outcomes | Correct for misclassification, or use outcomes only when the evidence is stable (B2) | data science | Open |
| D3 | Even against truth, smoking and diabetes barely register: stage changes are rare over ≤ 3 years | — | Longer follow-up, or model CAL change directly; compare importance with published risk factors | data science | Open |

## Site-level OMOP (spec 006)

| # | Item | Status |
|---|---|---|
| F1 | Choose a storage design: A (SITE/SITE_EVENT, base OMOP intact, 5 joins, ~2x storage), B (pre-coordinated concepts), C (site columns, simplest and fastest, changes a CDM table). Dry-run numbers in [site_level_omop.md](site_level_omop.md) | Open |
| F2 | Confirm LOINC 32910-2 / 32912-8 standard status in Athena; map bleeding, furcation, mobility, tooth status, teeth | Open |
| F3 | Propose derived measures (counts of teeth over thresholds etc.) as concepts; until then local concepts, written back as MEASUREMENT rows so Atlas can use them | Done, confirm |
| F4 | ADA 1084 mapping needs access to the standard | Open |
| F5 | Report prevalence under CDC/AAP 2012 next to NHANES (closes part of B6) | Open |
| F6 | Primary dentition, surfaces, conditions per tooth, implants not generated | Open |

## MLOps

| # | Item | Status |
|---|---|---|
| G1 | MLflow tracking, UC registry, champion/challenger on the acceptance test, MLflow GenAI judge ([mlops.md](mlops.md)) | Done, confirm on a workspace |
| G2 | Run the judge with a real endpoint (`--backend mlflow`) and align it to reviewer labels (MLflow ≥ 3.14) | Open |
| G3 | Monitoring: judges on live traces (done: `judge_monitoring` job, uat/prod); still open: inference tables on a serving endpoint, data profiling of predictions, alerts | Partly done |
| G4 | Retraining: scheduled, then triggered | Open |

## Free text

| # | Item | Status |
|---|---|---|
| H1 | Chart notes are the only free text here and the only AI input. Inventory the real EHR's other free text (exam-form and perio-chart comments, radiograph interpretations, treatment-plan and procedure notes, referral/specialist letters, medical-history text, scanned documents) and decide which to de-identify and read | Open |
| H2 | De-identification: the pipeline uses `regex`, which removes 20% of identifiers on held-out shapes. presidio+regex_v2+guard removes 57% and keeps 95% of dental terms; the Azure services are wired but not run ([deidentification.md](deidentification.md)). Next: run `azure_deid+regex_v2+guard` and `azure_language+regex_v2+guard` on the challenge set; fill real prices in `costs.yaml`; pick the engine on the unseen tier and switch `study.py`; add ASQ-PHI (MIT) as a second test set; keep a human review sample on real notes. On real case reports (MACCROBAT, spec 009) regex and regex_v2 miss month-year dates (22% and 27% recall) while hf_stanford removes 98% with the least clinical damage (0.17%) | Open |

## Earlier items

| # | Item | Status |
|---|---|---|
| E1 | Severity matrix for unsafe errors needs periodontist sign-off | Open |
| E2 | BERT ladder and MedGemma not yet run on real weights | Open |
| E3 | Prices in `costs.yaml` are illustrative | Open |
| E4 | Databricks UAT/prod need catalog names, service principal, GitHub secrets | Open |
