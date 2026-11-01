# Implementation Plan: synthetic medical-record features for the status classifier (spec 023)

**Spec**: [spec.md](spec.md) · **Issues**: #198 (US1), #199 (US2), #200 (US3) · **Follows**: Patel et al. 2026
(references item 53); spec 013 G10–G11.

## Approach

1. **Medical record, declared once.** `python/health_transformation_lab_nlp/medical_record.py`:
   - The table `CONDITIONS` gives each condition's column, base rate by age band, odds ratio by periodontal
     status, and source (citation plus table or page).
   - `draw_medical_record(person, status, risk, rng)` draws one record. It reuses the generator's
     `RiskFactors.hba1c`: diabetes = HbA1c ≥ 6.5, as `study.py` already decides.
   - Each condition is drawn given periodontal status and age band only, so the age-adjusted odds ratio is
     the declared one.
   - Blood pressure is drawn from a hypertension flag (normal or raised ranges).
   - ASA class follows from the number and kind of conditions (ASA Physical Status definitions: I healthy, II
     mild systemic disease, III severe systemic disease, IV a constant threat to life). It therefore carries
     medical signal into the dental set, which is the point of the `dental_no_asa` run.
   - The record is written to `data/datasets/medical_record.csv`, one row per person. Its columns are
     `person_id`, `is_<condition>`, `systolic_bp_mmhg`, `diastolic_bp_mmhg` and `asa_class_code`. HbA1c stays
     in the visits.
2. **Own random stream, own file.** `study.generate_visits` keeps its current draws in the same order. The
   medical record uses `random.Random(f"{seed}:medical")` after them and goes to its own file, so existing
   outputs are byte-identical (FR-001).
3. **Feature sets and scheme.** `classify_status.py` gets:
   - `FEATURE_SETS = {"dental": [...], "dental_no_asa": [...], "dental_medical": [...], "medical": [...]}`. Medical
     is the record's features plus age; there is no sex column;
   - a `four` scheme (healthy+gingivitis, I, II, III+IV);
   - `split_stratified(f, seed, test_share=0.3)`, grouped by person and stratified by class;
   - `compare_feature_sets(visits, seed)`, which returns one row per feature set and class.
4. **Metrics.** `classify_status.class_metrics(y, proba)` computes sensitivity, specificity, AUC (rank-based,
   ties averaged) and Brier score per class, one-vs-rest, plus their means. Its base-R twin is
   `r/R/13_spec023.R`, and `make_parity_inputs.sh` writes a fixed prediction table for `test_parity.R`.
   Sensitivity and specificity use the arg-max class, as the paper's confusion matrices do.
5. **Script and results.** `python/scripts/44_medical_features.py --seed 0` writes
   `data/results/synthetic_medical_feature_sets.csv`. Gold names are declared in `gold_names.py` if Load
   results takes it; the plan's default is not to load it into gold until the spec is reviewed.
6. **Docs.** These pages change:
   - `docs/classify_status.md` (or the existing walkthrough section): the three runs, labelled synthetic,
     with the paper's Table 2 averages cited beside them;
   - `docs/probast_tripod_ai.md`: the items that apply and don't;
   - the data card: medical records are synthetic.

## Research (to check before any number is used)

Each source is checked against the paper itself before its figure enters `CONDITIONS`. None is used from
memory.

| Link | Candidate source |
|---|---|
| Diabetes ↔ periodontitis | Preshaw PM et al., *Periodontitis and diabetes: a two-way relationship*, Diabetologia 2012 |
| Hypertension ↔ periodontitis | Muñoz Aguilera E et al., *Periodontitis is associated with hypertension*, Cardiovasc Res 2020 |
| Cardiovascular disease ↔ periodontitis | Sanz M et al., *Periodontitis and cardiovascular diseases: consensus report*, J Clin Periodontol 2020 |
| CKD ↔ periodontitis | Chambrone L et al., systematic review of periodontitis and CKD, J Clin Periodontol 2013 |
| Base rates by age | CDC NCHS NHANES data briefs (hypertension, diabetes) and the CDC CKD surveillance system |
| ASA class | American Society of Anesthesiologists, *ASA Physical Status Classification System* |
| Respiratory, haematologic, other endocrine | named in Patel et al. 2026's results as contributing; a rate source is needed, or they're left out |

**Checked for US1 (#198).** Each figure below was read from the source's abstract or key findings (PubMed or the
CDC page) before it went into `CONDITIONS` in `medical_record.py`, which carries the full citations:

| Link or rate | Used | Figure |
|---|---|---|
| Hypertension ↔ periodontitis | Muñoz Aguilera et al. 2020, PMID 31549149 | moderate–severe OR 1.22 (1.10–1.35), applied to stages II–IV |
| CKD ↔ periodontitis | Kapellas K et al., Nephrology 2019;24(2):202–212 (in place of Chambrone 2013, which was not checked: Kapellas gives a pooled odds ratio in its abstract) | pooled OR 1.60 (1.44–1.79) |
| Cardiovascular disease ↔ periodontitis | Janket SJ et al. 2003, PMID 12738947 (in place of the Sanz 2020 consensus report, which was not checked for a pooled figure) | summary RR 1.19 (1.08–1.32), used as an odds ratio |
| COPD (respiratory) ↔ periodontitis | Zeng XT et al., PLoS One 2012;7(10):e46508 | pooled OR 2.08 (1.48–2.91) |
| Hypertension by age; its definition and control | NCHS Data Brief 289 (2017) | 7.5 / 33.2 / 63.1% at 18–39 / 40–59 / 60+; ≥ 140/90 or medication; controlled 32.5 / 50.8 / 49.4% |
| CKD by age | CDC, *Chronic Kidney Disease in the United States*, 2026 (NHANES 2021–2023) | 6 / 13 / 34% at 18–44 / 45–64 / 65+ |
| Heart disease by age | NCHS QuickStats, MMWR 2022;71(23) (NHIS 2020) | 0.9 / 5.9 / 18.2% at 18–44 / 45–64 / 65+ |
| COPD by age | NCHS Data Brief 529 (2025) | 0.4 / 1.4 / 2.9 / 7.4 / 8.9 / 10.5% at 18–24 … 75+ |
| ASA class | ASA Physical Status Classification System (amended 2020), read from secondary copies: the ASA's own page was not reachable from the build session | definitions and adult examples for I–IV |
| Diabetes | the generator's HbA1c ≥ 6.5 (not drawn; reported, not tested against a source) | |
| Haematologic, other endocrine | no source checked | left out for now |

## Tests first

- `test_medical_record.py`:
  - seeded and reproducible;
  - existing columns byte-identical;
  - every `CONDITIONS` row has a source;
  - diabetes agrees with HbA1c;
  - age-adjusted (Mantel–Haenszel) odds ratios recovered within tolerance on 10,000 people;
  - ranges and AGENTS.md column names.
- `test_classify_status.py`:
  - the `four` scheme;
  - each feature set uses exactly its features;
  - the stratified split's shares and grouping;
  - `class_metrics` on hand-worked cases (perfect, constant, missing class).
- `r/tests/test_parity.R`: `class_metrics` to 1e-9.

## Environments

None change. If gold tables are added later, dev, uat and prod get them on their next deploy, and that PR says so.
