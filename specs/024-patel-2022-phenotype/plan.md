# Implementation Plan: the PerioDx phenotype method of Patel et al. 2022 (spec 024)

**Spec**: [spec.md](spec.md) · **Issues**: #201 (US1), #202 (US2), #203 (US3), #204 (US4) · **Source**:
Patel et al., Methods Inf Med 2022;61(S2):e125–e133 (references item 4), Fig. 1, Fig. 2, Table 1.

## Approach

1. **Diagnoser** (`python/health_transformation_lab_nlp/periodx.py`):
   - `chart_status(chart, age, cigarettes_per_day, diabetes, hba1c) -> PerioDxFinding` follows Fig. 2 top to
     bottom: health and gingivitis, then stage, extent, grade.
   - Constants are named after the figure's boxes (`BOP_LOCALIZED_PCT = 10`, `BOP_GENERALIZED_PCT = 30`,
     `MIDDLE_THIRD_BL_PCT = 33`, `OCCLUDING_PAIRS_MIN = 10`, ...), each citing Fig. 2.
   - It reads the chart fields the generator already writes. Inputs the synthetic chart lacks (occluding pairs,
     recession, drifting/bite collapse) map from existing fields where spec 006/013 provide them (`aces.py`'s
     `occluding_pairs`; the `PerioChart` fields `remaining_teeth`, `complex_rehab` and `mobility_degree` in
     `labels.py`), or use the documented fallback (`III_IV_NO_TOOTH_LOSS`, `GRADE_MID_ENTRY` and the rest,
     each a named constant).
2. **Extractor** (same module):
   - `note_status(note, negation=False) -> PerioDxFinding` ("no_diagnosis" when the note has none).
   - Step 1: normalise and filter on `PERIODX_TERMS`, a checked-in table of 2017 classification terms plus the
     repo's synthetic abbreviations.
   - Step 2: stem with a small suffix stripper, and match with `difflib.SequenceMatcher` at a declared
     threshold, so no new dependency. Gensim word vectors are named as the paper's choice and not reproduced.
   - With negation on, it uses the NegEx-style cue window the repo's note reader already uses, if one exists;
     otherwise a minimal cue list.
3. **Stepwise phenotype**:
   - `phenotype.py` gets `phenotype_patel2022(row)`, which returns the label and the deciding section. Its
     order (diagnosis codes, then the Extractor's note reading, then the Diagnoser's chart reading) is a
     separate constant, `PATEL2022_ORDER`, not entries in `DESIGN_GROUPS`. Script 18 keeps its 24 orderings
     and adds the paper's order as one extra scored row.
   - The Extractor and Diagnoser outputs per visit are written to a new `periodx_visits.csv` (FR-010), never
     into `visits_structured.csv`.
   - Wherever methods are listed, `algorithm_patel2022` joins `algorithm_design`: `grader_tables.EVIDENCE`,
     `gold_names` (`rules_patel2022_status_code`), the dashboards, and `scripts/18_phenotype_order.py`'s
     comparison.
4. **Completeness**: a new `completeness.section_completeness(v, sections, merged)` writes
   `data/results/data_quality/completeness_patel2022.csv`. The paper's Fig. 1 shares are cited in the doc,
   not the CSV.
5. **Scores**: the existing agreement and kappa tables pick up the method. A confusion-matrix row (TP, FP, TN,
   FN, precision, recall, F1) for the Diagnoser and for the Extractor goes against the reviewer key, per class
   one-vs-rest and pooled (FR-006). `reliability.py` has no precision, recall or F1 function, so
   `reliability.confusion_scores` is new, with an R twin in `r/R/14_spec024.R`.
6. **R**: `r/R/14_spec024.R` mirrors `diagnose` and the stepwise order, and `make_parity_inputs.sh` writes
   charts and labels for `test_parity.R`. The Extractor is NLP, so its parity is on its outputs over a fixed
   snippet set: R reads the Python extraction table and checks the stepwise merge only.
7. **Docs (US4)**:
   - References item 4 gets the full citation, what is implemented, and the three inconsistencies.
   - `evidence_rules.md`, `code_walkthrough.md`, the `phenotype.py` comment and `action_items.md` A2: the
     exam-form-first order is the repo's; the paper's is `algorithm_patel2022`.
   - `test_rule_order_citation.py` is updated first, so it fails on today's wording.

## Tests first

- `test_periodx.py` (new):
  - one chart per Fig. 2 branch, including tooth loss before stage I/II and the `III_IV_NO_TOOTH_LOSS` dead end;
  - the grade paths (smoker < 10 a day with HbA1c ≥ 7.0 is C; the 0.25–1.0 band never gives A);
  - extent with the stage-specific CAL/PD pairs;
  - grade not assessable without age or bone loss;
  - bone-loss categories accepted;
  - Extractor snippets with negation off and on, abbreviations, and no-diagnosis.
- `test_phenotype_patel2022.py` (new): the stepwise order (code beats note beats chart; exam form never used); deciding
  section reported.
- `test_completeness.py`: section and merged completeness on a hand-built table.
- `test_reliability.py`: `confusion_scores` on hand-worked cases (one-vs-rest and pooled; "no diagnosis").
- `test_phenotype_order.py`: still 24 orderings, plus the paper's order as one row.
- Existing datasets byte-identical after the build writes `periodx_visits.csv`.
- `test_rule_order_citation.py`: the corrected wording.
- `r/tests/test_parity.R`: Diagnoser labels, the stepwise merge, and `confusion_scores` to 1e-9.

## Environments

None change. The gold column `rules_patel2022_status_code` reaches dev, uat and prod with their next Load
results; the implementation PR says so.
