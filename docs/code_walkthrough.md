# Code walkthrough

> Personal learning project; synthetic data only. See [DISCLAIMER](../DISCLAIMER.md).

Three levels, the same way throughout: the **[study page](edr/README.md)** says what
the study does, this page explains **how the code does it, step by step in
run order**, and each step links the **code**. The Databricks notebook
[`databricks/notebooks/00_walkthrough.py`](../databricks/notebooks/00_walkthrough.py)
has one section per step below, with a cell that shows that step's output.

Every number from these steps is from synthetic patients and simulated reviewers.

Pictures of the same: [medallion architecture](../diagrams/d0_medallion_architecture.png), [study process](../diagrams/d1_study_process.png), [platform](../diagrams/d2_platform_architecture.png),
[ERD](../diagrams/d3_erd_omop_dental.png), [site storage designs](../diagrams/d4_site_storage_designs.png),
[MLOps](../diagrams/d5_mlops_lifecycle.png), [run order](../diagrams/flows/01_run_order.png) ([all diagrams](../diagrams/README.md)).

## The steps in run order

| # | Step | Command | README section |
|---|---|---|---|
| 1 | [Generate the synthetic study](#1-generate-the-synthetic-study) | `python scripts/10_build_study.py` | [Evidence types](edr/README.md) |
| 2 | [De-identify and gate](#2-de-identify-and-gate) | (inside step 1) | [Ground rules](edr/README.md#ground-rules) |
| 3 | [Read the diagnostic evidence](#3-read-the-diagnostic-evidence) | (inside step 1) | [Evidence types](edr/README.md) |
| 4 | [Compare the evidence](#4-compare-the-evidence) | (inside step 1) | [Study process](process.md) |
| 5 | [Rule-based phenotype](#5-rule-based-phenotype) | (inside step 1) | [Staging and grading](edr/README.md) |
| 6 | [AI models read the notes](#6-ai-models-read-the-notes) | `python scripts/11_ai_predict.py --rung <id>` | [Models evaluated](edr/README.md#models-evaluated-the-12-from-the-evaluation-sheet-modelsyaml) |
| 7 | [Reviewers stage charts](#7-reviewers-stage-charts) | Label Studio, then `12_import_review.py` | [How results are measured](edr/README.md#how-results-are-measured) |
| 8 | [Reliability and the acceptance test](#8-reliability-and-the-acceptance-test) | `python scripts/13_reliability.py` | [How results are measured](edr/README.md#how-results-are-measured) |
| 9 | [Five categories and evidence order](#9-five-categories-and-evidence-order) | `python scripts/18_phenotype_order.py` | [Action items](edr/README.md#action-items) |
| 10 | [Over time: plausibility and data quality](#10-over-time-plausibility-and-data-quality) | `python scripts/20_data_quality.py` | [Action items](edr/README.md#action-items) |
| 11 | [Clinic prevalence](#11-clinic-prevalence) | `python scripts/19_prevalence.py` | [Action items](edr/README.md#action-items) |
| 12 | [Predict progression](#12-predict-progression) | `python scripts/21_predict_progression.py` | [Action items](edr/README.md#action-items) |
| 13 | [Site-level charts, both classifications](#13-site-level-charts-both-classifications) | `python scripts/22_build_sites.py` | [Drill-downs](edr/README.md#drill-downs) |
| 14 | [OMOP storage designs on Postgres](#14-omop-storage-designs-on-postgres) | `python scripts/23_site_designs.py --url ...` | [Drill-downs](edr/README.md#drill-downs) |
| 15 | [OMOP into Lakebase](#15-omop-into-lakebase) | `python scripts/05_load_omop_db.py --url ...` | [Drill-downs](edr/README.md#drill-downs) |
| 16 | [LLM judge and cost at 1M notes](#16-llm-judge-and-cost-at-1m-notes) | `14_benchmark_cost.py`, `15_judge.py`, `16_cost_effectiveness.py` | [Drill-downs](edr/README.md#drill-downs) |
| 17 | [MedGemma](#17-medgemma) | `11_ai_predict.py --rung medgemma-1.5-4b-it`, `17_medgemma_lora.py` | [Drill-downs](edr/README.md#drill-downs) |
| 18 | [Deploy: dev, UAT, prod](#18-deploy-dev-uat-prod) | `databricks bundle deploy -t <target>` | [Drill-downs](edr/README.md#drill-downs) |
| 19 | [MLflow: track, register, judge, promote](#19-mlflow-track-register-judge-promote) | `11_ai_predict.py --register`, `24_promote_model.py`, `15_judge.py --backend mlflow` | [Drill-downs](edr/README.md#drill-downs) |
| — | [R side and parity](#r-side-and-parity) | `python/scripts/make_parity_inputs.sh && Rscript r/tests/test_parity.R` | [Ground rules](edr/README.md#ground-rules) |

Commands run from `python/` unless they start with `python/` or `r/`.

## 1. Generate the synthetic study

Synthetic people with **histories**: 1–6 recall visits about six months apart,
in one of 8 clinics. Attachment and bone loss never recover; smoking and diabetes
speed progression; therapy lowers pockets and bleeding; 2% of charted follow-up
visits get a charting error (answer key only). Each visit gets a chart note, an
exam form, procedure codes and diagnosis codes (completed and planned), a probing
chart, and a structured radiograph AI read.

- Code: [`study.py`](../python/health_transformation_lab_nlp/study.py) `generate_visits`, `build_study`;
  [`synthetic.py`](../python/health_transformation_lab_nlp/synthetic.py) `draw_history`, `draw_chart`, `draw_risk`;
  [`clinical_notes.py`](../python/health_transformation_lab_nlp/clinical_notes.py) (published note styles, [note_realism.md](note_realism.md));
  [`sources.py`](../python/health_transformation_lab_nlp/sources.py) (forms, CDT, ICD-10); [`radiograph.py`](../python/health_transformation_lab_nlp/radiograph.py).
- Truth: [`labels.py`](../python/health_transformation_lab_nlp/labels.py), the AAP worksheet ([staging_grading.md](staging_grading.md)).
- Output: `data/datasets/train.csv`, `review_tasks.json`, `visits_structured.csv`; `answer_key/` (truth; reviewers never see it).
- Check: `build_summary.json` (counts, de-id recall, errors injected, review mix).

## 2. De-identify and gate

**In plain words:** the synthetic notes contain fake patient identifiers (names, dates of birth,
record numbers, phone numbers), put there on purpose so we can test removing them. Three steps:

1. **Remove.** An engine finds the identifiers and replaces each with a tag such as `[NAME]` or
   `[DATE]`. The study pipeline still uses the simplest engine (patterns plus a list of dental
   abbreviations it must not touch), and that's the weak point: on held-out shapes it removes only
   20% of identifiers. The standard methods are compared on a separate, harder test set
   ([deidentification.md](deidentification.md)): improved patterns, Presidio (an NER model),
   two transformer models trained for clinical de-identification (Stanford, OBI), an LLM, and
   Microsoft's Azure services, alone and combined, with a dental guard so clinical terms survive.
   Best measured so far: Presidio + improved patterns + guard, 57% on held-out shapes. Choosing the
   pipeline's engine is action item H2.
2. **Final check (the "leak gate").** We know every fake identifier we put in, so we search the
   cleaned note for each one. If even one survived, the note is held back: it never reaches
   Label Studio, the reviewers or any AI model.
3. **Second look (residual scan).** The detectors run again on the cleaned text and flag anything
   still shaped like an identifier. With real notes, where nothing is known in advance, this
   and a human review sample are what's left.

- Code: [`phi.py`](../python/health_transformation_lab_nlp/phi.py), [`deid.py`](../python/health_transformation_lab_nlp/deid.py) (`deidentify`, `leak_check`, `residual_scan`); `study.apply_deid`.
- Output: `data/datasets/deid_report.csv`. Raw notes with fake PHI stay in `data/raw/` (gitignored).
- Check: recall 1.0, nothing blocked, over-redaction 0 in `build_summary.json`.
- That check is easy by design: the regex was written against the same note shapes. A harder,
  labeled challenge set (hard and held-out tiers, dental look-alikes) compares regex, regex v2,
  Presidio and the Azure services, with costs: [deidentification.md](deidentification.md),
  [`scripts/26_deid_benchmark.py`](../python/scripts/26_deid_benchmark.py), R [`08_deid.R`](../r/R/08_deid.R).

## 3. Read the diagnostic evidence

One status per type of diagnostic evidence per visit, or `unknown` when it's silent.

- Code: [`note_reader.py`](../python/health_transformation_lab_nlp/note_reader.py) (stated diagnosis in any scheme, else findings; copy-forward ignored);
  `sources.READERS` (exam form, CDT completed/planned, ICD-10 completed/planned); probing chart staged from the **recorded** chart;
  `radiograph.read_radiograph` (stage II–III lower bound only).
- Output: one column per evidence type in `answer_key/review_key.csv` and `visits_structured.csv`.

## 4. Compare the evidence

Pairwise agreement and kappa between evidence types, and how often each says anything.
This is the input to the qualitative review.

- Code: [`phenotype.py`](../python/health_transformation_lab_nlp/phenotype.py) `agreement_matrix`, `coverage`.
- Output: `data/datasets/method_agreement.csv`, `method_coverage.csv`.

## 5. Rule-based phenotype

Two orders, both kept, both this repo's own: the study design's starting order (exam form → diagnosis
code → note NLP → periodontal chart) as `algorithm_design`, and the earlier placeholder (chart first,
radiograph as a lower bound) as `algorithm_v0`. Neither is the order in Patel et al., *Methods Inf Med* 2022
([references](references.md), item 4; checked against the full text, action item A2): the structured
diagnosis section, then clinical notes, then periodontal charting, with no exam-form or PSR step. That order
is `algorithm_patel2022` (spec 024; [periodx.md](periodx.md)).

- Code: `phenotype.RULES_DESIGN`, `RULES_V0`, `phenotype()`.
- Output: `algorithm_design`, `algorithm_v0` columns. Differences: [action_items.md](action_items.md) A2–A6.

## 6. AI models read the notes

Every model reads **only** the de-identified note. Baselines (rules, TF-IDF,
TF-IDF + radiograph features), the 12-model BERT ladder, and LLM readers.
What a BERT model is, in plain words: [bert.md](bert.md).

- Code: [`rungs.py`](../python/health_transformation_lab_nlp/rungs.py) `make_rung`; [`models.yaml`](../models.yaml) (Hugging Face ids, papers);
  [`llm_reader.py`](../python/health_transformation_lab_nlp/llm_reader.py); [`scripts/11_ai_predict.py`](../python/scripts/11_ai_predict.py).
- Output: `data/datasets/ai_predictions_<rung>.csv` (LLMs also `llm_details_<rung>.csv`).
- Status: baselines and eleven encoders run (base-size on CPU; the Longformers and large ModernBERTs on Kaggle GPUs): 77-83% correct on the synthetic review charts, not distinguishable from the note rules (79%); all miss nearly every stage IV chart (7 training examples). With the note rules deciding stage IV (`+rules4`) they reach 87-91%. MedGemma 1.5 4B and 4B v1 (zero-shot) score 76% and 78%; see [MedGemma](medgemma.md).
- Compare against the truth: [`scripts/28_ladder_vs_truth.py`](../python/scripts/28_ladder_vs_truth.py) → `data/datasets/ladder/ladder_vs_truth.csv` (accuracy with bootstrap CIs, difference from note rules, stage IV recall, unsafe rate, calibration); R twin `r/R/10_ladder.R`.
- MedGemma vs BERT: [`scripts/29_medgemma_vs_bert.py`](../python/scripts/29_medgemma_vs_bert.py) → `data/datasets/ladder/medgemma_vs_bert.csv` (each MedGemma run minus the best encoder, paired bootstrap CI; stage IV recall; gate and fallback rates; assumed corpus cost) and `..._by_difficulty.csv`. MedGemma variants keep their own files (`+lora`, `+k<shots>`, `+terse`). `--simulated` uses the placeholder reader: a dry run.

## 7. Reviewers stage charts

**In plain words:** several periodontists each read the same 240 de-identified charts and record
the status they'd assign (healthy, gingivitis, or periodontitis with stage, grade and extent),
plus which evidence decided it. They work separately and never see each other's answers. Their
labels are the human benchmark the AI and the rules are checked against.

**Label Studio** is a free, open-source labeling tool: it shows each chart on screen with buttons
for the answers. Each reviewer gets their own project with `review_tasks.json` and follows the
written protocol.

- Code / config: [`labelstudio/chart_review.xml`](../labelstudio/chart_review.xml), [`labelstudio/README.md`](../labelstudio/README.md),
  [`labeling_protocol.md`](labeling_protocol.md); [`labelstudio.py`](../python/health_transformation_lab_nlp/labelstudio.py), [`scripts/12_import_review.py`](../python/scripts/12_import_review.py).
- Dry run: `12_import_review.py --simulate 4` writes `simulated_*` files.
- Output: `data/review/[simulated_]reviewer_labels.csv`.

## 8. Reliability and the acceptance test

**In plain words:** people don't agree perfectly either, so the bar for the AI isn't 100%. It's
"agrees with the periodontists at least as often as they agree with each other". First measure
how much the reviewers agree among themselves; then how much each method agrees with them.

In detail: Fleiss' kappa across reviewers; each evidence type, the phenotype and each AI model
against the reviewers; errors by clinical severity and by difficulty; and the
**acceptance test**: does the method agree with the reviewers at least as much
as they agree with each other ([process.md](process.md#validation-criterion-as-reliable-as-a-human-reviewer), [statistics.md](statistics.md)).

- Code: [`reliability.py`](../python/health_transformation_lab_nlp/reliability.py) (`reliability_report`, `agreement_vs_humans`), [`harm.py`](../python/health_transformation_lab_nlp/harm.py);
  [`scripts/13_reliability.py`](../python/scripts/13_reliability.py); R [`r/R/04_reliability.R`](../r/R/04_reliability.R).
- Output: `data/review/[simulated_]reliability/` (`methods_vs_reviewers.csv`, `agreement_vs_humans.csv`, `by_level.csv`).

## 9. Five categories and evidence order

**Six vs five categories.** The six labels are healthy, gingivitis and periodontitis stages I–IV.
The study design also uses five, with healthy and gingivitis merged into one "no periodontitis"
category. Reviewers still label six; every result is reported both ways.

**Evidence order.** When the evidence disagrees, the rule-based phenotype takes the first of
four groups that has an answer: exam form, then diagnosis codes, then the note, then the probing
chart (the study design's order). Four groups can be ordered 24 ways. Each order is tried, the
one that agrees best with the reviewers is picked on half the charts, and its agreement is then
measured on the other half, so the pick isn't graded on the charts that chose it.

- Code: `phenotype.collapse5`, `score_orders`; [`scripts/18_phenotype_order.py`](../python/scripts/18_phenotype_order.py); R [`09_spec005.R`](../r/R/09_spec005.R) (`score_orders_r`).
- Output: `data/review/[simulated_]reliability_5cat/` (`agreement_vs_humans.csv`, `phenotype_orders.csv`).

## 10. Over time: plausibility and data quality

**In plain words:** before trusting any number, check the data makes sense.

- **Does each value make sense?** Probing depths, attachment loss and bleeding % within possible
  ranges ("conformance"); required fields filled in ("completeness"); values that fit together
  ("plausibility"). These are the categories OHDSI's Data Quality Dashboard uses. Checked overall
  and per clinic, since one clinic with sloppy charting can skew everything.
- **Does each patient's history make sense?** Some changes can't happen between visits:
  attachment or bone lost to periodontitis doesn't grow back, extracted teeth don't return, and
  periodontitis doesn't turn back into healthy (once diagnosed, it's managed, not cured). If a
  later visit shows one of these, a record is probably wrong, or the phenotype misread it.

**Simulated dry run (not a result):** 2% recording errors were injected on purpose; the history
checks caught a third of them, while flagging only 0.2% of clean records. The study design's
phenotype dropped a stage at 24% of follow-up visits (action item B2), because forms and codes
vary visit to visit.

- Code: [`plausibility.py`](../python/health_transformation_lab_nlp/plausibility.py), [`dq.py`](../python/health_transformation_lab_nlp/dq.py); [`scripts/20_data_quality.py`](../python/scripts/20_data_quality.py); R [`r/R/06_validation.R`](../r/R/06_validation.R), [`09_spec005.R`](../r/R/09_spec005.R) (`run_checks_r`).
- Output: `data/datasets/data_quality/` (`dq_overall.csv`, `dq_by_clinic.csv`, `temporal_by_method.csv`, `injected_error_recall.csv`).

## 11. Clinic prevalence

**In plain words:** what share of each clinic's patients have periodontitis, and severe
(stage III–IV) periodontitis? Each patient counts once, using their latest visit with a known
status. Every share has a 95% confidence interval (Wilson method). A clinic far outside the
others, or far from national figures, is worth a look: its patients differ, or its records do.

National figures for comparison: NHANES 2009–2014, 42.2% of US adults 30+ with periodontitis,
7.8% severe. They use the CDC/AAP definitions, not the 2017 stages, so they're a sanity check,
not a target.

**Simulated dry run (not a result):** 56% with periodontitis overall (52% in the generator's
truth), clinics ranging from 50% to 65%. That's above NHANES's 42% mostly because the 2017
system counts mild stage I cases that the CDC/AAP definitions call "no periodontitis"
(step 13 compares the two on the same charts).

- Code: [`prevalence.py`](../python/health_transformation_lab_nlp/prevalence.py); [`scripts/19_prevalence.py`](../python/scripts/19_prevalence.py); R `06_validation.R`.
- Output: `data/datasets/prevalence/`.

## 12. Predict progression

**Question:** looking only at what's in today's visit, can we tell whose gum disease
will be worse at their next visit?

- **What counts as "worse":** the next visit's phenotype is a higher category than
  today's, e.g. healthy → periodontitis, or stage II → stage III.
- **What the model sees (today's visit only):** today's phenotype; chart measurements
  (deepest pocket, bleeding %, attachment loss, bone loss, teeth lost); age, smoking,
  diabetes; whether the patient was treated before.
- **Model:** logistic regression, a simple, explainable model.
- **Fair test:** 70% of *patients* train the model and the other 30% test it. Splitting
  by patient, not by visit, stops the model from being tested on someone it has already seen.
- **How good is it: AUROC.** Pick one patient who got worse and one who didn't; AUROC is
  how often the model gives the first a higher risk. 0.5 is a coin flip, 1.0 is perfect,
  and 0.7–0.8 is typical of useful clinical risk scores. The 95% confidence interval
  (bootstrap) is the range the true value plausibly falls in.
- **What drives it: permutation importance.** Shuffle one input at random and see how
  much AUROC drops. A big drop means the model relies on that input.

**Simulated dry run (synthetic data, not a result):** 3,143 visit pairs, 23% got worse;
AUROC 0.70 (95% CI 0.66–0.74). Today's stage matters most (people already at a high stage
have less room to move up), then attachment loss and prior treatment. Smoking and diabetes
barely register, because the synthetic histories are too short for them to show (action item D3).

- Code: [`prediction.py`](../python/health_transformation_lab_nlp/prediction.py); [`scripts/21_predict_progression.py`](../python/scripts/21_predict_progression.py); R [`09_spec005.R`](../r/R/09_spec005.R) (same model; parity-tested).
- Output: `data/datasets/prediction/`.

### Classify status from the chart, explained with SHAP (spec 013 G10)

**Question:** from today's chart alone, which status is this visit, and *which measurements made the
model say so*?

- **Model:** gradient-boosted trees (XGBoost), after Patel et al. 2022: 80% of patients train, 20% test;
  depth, learning rate, regularization and class weighting picked by 5-fold cross-validation within the
  training patients. Two schemes: 5 levels (healthy or gingivitis, stage I-IV) and 3 levels (healthy or
  gingivitis, stage I-II, stage III-IV). Only charted visits: without a chart there is nothing to read.
- **SHAP, in plain words:** for each visit, SHAP splits the model's answer into a share per input. Start from
  the average answer (the "bias"); each input pushes it up or down; the pushes add up exactly to the
  model's score for that visit. Averaged over visits (mean |SHAP|) it ranks the inputs; per visit, it says
  why *this* visit got *this* stage, which is what a reviewer wants next to a disagreement.
- **Reading the figure** (`classify_status/<outcome>_<scheme>_shap.png`): left, how much each input moves the
  answer, split by class; right, one dot per test visit for the most severe class, red when the input is
  high. Dots right of zero push towards that class.
- **What to expect on synthetic data:** the labels come from the 2017 AAP/EFP rules on the same chart, so
  the stage criteria should lead and smoking and diabetes (which set the *grade*, not the stage) should be
  near zero. Each input is tagged with its role in the rules so this can be checked at a glance.

**Simulated dry run (synthetic data, not a result), outcome `algorithm_design`, 5 levels:** accuracy 0.80,
macro F1 0.75 on 713 held-out visits (the label also uses notes and codes, so the chart can't explain all of
it; on `truth_status` accuracy is 0.99). SHAP ranks attachment loss first, then % of teeth involved: it is 0
when no tooth has attachment loss, so it separates healthy and gingivitis from periodontitis. Bone loss,
teeth lost and probing depth follow; smoking and diabetes are near zero, as the rules say. On `truth_status`
bone loss falls to 0.08 (5 levels) and to zero (3 levels), because the rules use it only when CAL is missing
and every charted visit has CAL. One oddity it surfaces: older age pulls *away* from stage IV (mean |SHAP|
0.135 for stage IV, 0.05 over all classes); unexplained so far.

- Code: [`classify_status.py`](../python/health_transformation_lab_nlp/classify_status.py);
  [`scripts/40_classify_status.py`](../python/scripts/40_classify_status.py). Needs the `ml` extra
  (`pip install -e "python[ml]"`). No R twin (spec 013 FR-007: model outputs are outside label/scoring parity).
- Output: `data/datasets/classify_status/`.

## 13. Site-level charts, both classifications

32 teeth × 6 sites per charted exam, generated to reproduce the visit chart; the
derived-measure layer; the 2017 AAP/EFP stage and the 2012 CDC/AAP category from
the same sites.

- Code: [`sites.py`](../python/health_transformation_lab_nlp/sites.py) (`draw_mouth`, `derive`, `aap_from_derived`, `cdc_aap`);
  [`scripts/22_build_sites.py`](../python/scripts/22_build_sites.py); R [`r/R/07_sites.R`](../r/R/07_sites.R).
- Output: `data/sites/derived.csv`, `aap_vs_cdc.csv` (site rows in gitignored Parquet).

## 14. OMOP storage designs on Postgres

The same mouths stored three ways (SITE/SITE_EVENT; pre-coordinated concepts;
site columns), the same derived query on each, results checked against Python.

- Code: [`site_designs.py`](../python/health_transformation_lab_nlp/site_designs.py); SQL [`omop/sql/site_designs/`](../omop/sql/site_designs/);
  [`scripts/23_site_designs.py`](../python/scripts/23_site_designs.py). Findings: [site_level_omop.md](site_level_omop.md).
- Output: `data/sites/site_designs.csv`.

## 15. OMOP into Lakebase

OMOP CDM 5.4 (OHDSI Postgres DDL) + dental extension + synthetic data into any
Postgres, including Lakebase; `perio_chart` view.

- Code: [`db.py`](../python/health_transformation_lab_nlp/db.py); [`scripts/05_load_omop_db.py`](../python/scripts/05_load_omop_db.py);
  notebook [`04_load_lakebase.py`](../databricks/notebooks/04_load_lakebase.py); DDL [`omop/ddl/`](../omop/ddl/); R full CDM [`r/R/01_etl_synthea.R`](../r/R/01_etl_synthea.R).
- Storage overall: [results_storage.md](results_storage.md).

## 16. LLM judge and cost at 1M notes

A judge calibrated against the reviewers estimates each method's accuracy on
a corpus sample; a cost model prices each method over every note.

- Code: [`judge.py`](../python/health_transformation_lab_nlp/judge.py), [`cost_effectiveness.py`](../python/health_transformation_lab_nlp/cost_effectiveness.py);
  scripts 14–16; [`costs.yaml`](../costs.yaml) (illustrative); SQL judge [`02_llm_judge.sql`](../databricks/notebooks/02_llm_judge.sql).
- Docs: [cost_effectiveness.md](cost_effectiveness.md), [financial_tradeoffs.md](financial_tradeoffs.md).

## 17. MedGemma

MedGemma as a note reader (local, served or simulated), a LoRA fine-tune, and
the judge family rule.

- Code: `llm_reader.py`; [`scripts/17_medgemma_lora.py`](../python/scripts/17_medgemma_lora.py); notebook [`03_medgemma_reader.py`](../databricks/notebooks/03_medgemma_reader.py).
- Docs: [medgemma.md](medgemma.md).

## 18. Deploy: dev, UAT, prod

A Databricks Asset Bundle: per-environment catalog/schema, Lakebase instance,
endpoints and GPU settings; GitHub Actions for tests and deploys.

- Code: [`databricks.yml`](../databricks.yml), [`databricks/resources/jobs.yml`](../databricks/resources/jobs.yml),
  [`.github/workflows/`](../.github/workflows/). Docs: [deployment.md](deployment.md).

## 19. MLflow: track, register, judge, promote

Every scoring step logs an MLflow run (step, git commit, dataset fingerprint,
simulated flag). A rung can be registered in Unity Catalog as a pyfunc (alias
challenger) and promoted to champion only if it passes the acceptance test and
matches the current champion. The judge also runs as an MLflow GenAI judge.

- Code: [`tracking.py`](../python/health_transformation_lab_nlp/tracking.py), [`model_registry.py`](../python/health_transformation_lab_nlp/model_registry.py),
  [`mlflow_judge.py`](../python/health_transformation_lab_nlp/mlflow_judge.py), [`scripts/24_promote_model.py`](../python/scripts/24_promote_model.py);
  bundle [`databricks/resources/mlops.yml`](../databricks/resources/mlops.yml). Docs: [mlops.md](mlops.md).

## R side and parity

R twins of every computation behind a reported number (labels, scorer,
reliability and acceptance test, by level, cost-effectiveness, judge bake-off,
five categories, plausibility, prevalence, site-derived measures). The parity
test regenerates the Python outputs and compares them.

- Code: [`r/R/`](../r/R/), [`r/tests/test_parity.R`](../r/tests/test_parity.R), [`python/scripts/make_parity_inputs.sh`](../python/scripts/make_parity_inputs.sh). Setup: [r/README.md](../r/README.md).
