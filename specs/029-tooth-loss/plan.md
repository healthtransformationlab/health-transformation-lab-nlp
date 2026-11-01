# Implementation Plan: tooth lost to periodontitis (spec 029)

**Spec**: [spec.md](spec.md) · **Issues**: #369 (US1), #370 (US2), #371 (US3); #377 (diagnoses and treatment plans); #429 (US7)

## Approach

1. **Schema check (T001), done.** [research.md](research.md) records every table and column used, with its meaning
   and the Open Dental source file it came from (github.com/OpenDental/OpenDental, branch `24_3`, commit `d804c19`).
   `TABLES` in `open_dental.py` is written from it. What the source changed in this plan:
   - CAL is computed, not stored: probing (sequence 4) + gingival margin (sequence 2, values of 100 and up are
     negative).
   - Bleeding is bit 1 of sequence 6.
   - An extraction carries the practice's own diagnosis (`Dx` → `definition`, category Diagnosis). An ICD code
     (`DiagnosticCode` with `IcdVersion`) is there only for medical claims, so it is rare and only a check.
   - A planned procedure is one `procedurelog` row (`ProcStatus` 1) copied into every saved plan (`proctp`, back
     to it by `ProcNumOrig`); the copies are editable text (#377).
   - Smoking is `patient.SmokingSnoMed`. Diabetes is a `disease` row whose `diseasedef` has an E10–E11 ICD-10 code.
   - `ProcStatus` 4 ("Existing Other Prov") is an extraction done elsewhere: a third way a tooth is missing,
     treated like missing at the first exam.
2. **Generator** (`open_dental.py`, `@traced`).
   - For each synthetic person (study visits), take the mouth `sites.draw_mouth` makes at each visit. Its
     `missing_reason` is the truth.
   - Split the person's missing teeth into missing at the first exam (`toothinitial`) and extracted during the
     record (`procedurelog`, completed, D7140/D7210, dated between exams), by the share parameters.
   - Write two invented diagnosis lists into `definition` (before and after the 2017 classification). Attach the
     item in use on the procedure's date to extractions (`Dx`) by the diagnosis-rate parameters (periodontal,
     other, none, mismatch), with the older list fading out over the adoption lag; fill `DiagnosticCode` on a
     small share only. Record some prior extractions as `ProcStatus` 4 ("Existing Other Prov").
   - Plan extractions at exams: a `procedurelog` row with `ProcStatus` 1, copied into one or more `treatplan`
     plans that day (`proctp`) and again at later exams until completed (same row set to 2) or never. Plant a
     few edited copies (code, tooth or diagnosis text) for the data-quality checks.
   - Write probing and gingival margin per site (never CAL), mobility and furcation per tooth, and bleeding as bit 1
     of sequence 6. Smoking goes in `patient.SmokingSnoMed`, diabetes in `disease` / `diseasedef`.
   - Write perio exams and measures for every visit from the site table. Medical problems come from the existing
     risk factors.
   - Own stream `random.Random(f"{seed}:open_dental")`. Output: `data/datasets/open_dental/*.csv`, plus
     `tooth_loss_truth.csv` apart from them.
3. **Bench and bundle.**
   - `schemas.LAYERS["opendental_perio"] = ("landing", "bronze", "silver", "gold")`: schemas
     `<layer>_opendental_perio`.
   - `unity_catalog.yml` declares the four schemas and the landing volume `data`, all with `prevent_destroy`.
   - A job `tooth_loss_load`: bronze from the CSVs (overwrite per run); silver and gold from the Python
     functions; rows carry `run_id`, `run_ts` and `git_commit_sha`.
4. **Silver tooth table** (`tooth_loss.py`). `tooth_table(extract)` returns one row per patient and tooth:
   - status, the five codes in the spec;
   - loss date;
   - own last measures before the loss;
   - neighbour and mouth features;
   - tooth type, age, smoking, diabetes.

   `planned_extraction(extract)` returns one row per planned `procedurelog` extraction with its plan-copy
   count, first and last plan dates and outcome.

   Its base-R twin is `r/R/15_spec029.R`. (Check the next free R number at implementation time: specs 023 and
   024 have planned 13 and 14.)
5. **Model** (`tooth_loss.py`, `scripts/45_tooth_loss.py`; check the next free script number then).
   - Logistic regression (scikit-learn, standardized) and XGBoost (the `ml` extra).
   - 70/30 split, grouped by patient and stratified by label.
   - Two feature sets: shared (applied) and with own measures (comparison only).
   - Two label sets (FR-010): completed extractions only, and completed plus planned (one per `procedurelog`
     row). Both are scored on the same held-out and missing-at-entry teeth.
   - Threshold fixed at 0.5, and also reported at Youden's J on the training fold.
   - Writes `data/results/synthetic_tooth_loss_{scores,calibration,stage_recount}.csv`.
6. **Stage recount.** `labels.stage4_rule` gains `expected_perio_loss`: recorded periodontal losses plus the sum of
   predicted probabilities over the unlabelled missing teeth. Stage IV when that is 5 or more. Its R twin goes in
   the same file.
6a. **Data-quality checks** (`tooth_loss_dq.py`). The 12 checks of Kookal et al. 2024 are adapted to the extract's
   tables (FR-009). The generator plants faults at named rates (duplicate rows, out-of-range probing values, an
   invalid diagnosis item, a missing value, one office with more missing values, edited plan copies, plan copies
   with no original, older-list items after the switch) and records them, so the tests know what each check must
   find. Results go to silver `tooth_loss_dq_check`. Built (#370): faults are planted by `open_dental.plant_faults`
   in the tests only, so the default extract is unchanged; offices are compared with the rest, not the mean of all
   (4 offices); `group_consistency` adds the split by office, provider, sex, race, exam year and age band
   (`tooth_loss_dq_group`).
7. **Docs.** `docs/tooth_loss.md` is a plain page covering:
   - the question;
   - the extract's tables, with links to Open Dental's schema docs;
   - the results, labelled synthetic;
   - what a real extract can and can't check.

8. **Why teeth are missing at entry (US7, #429).**
   - Sources first: published shares of reasons for extraction by age band go in [research.md](research.md) ("Why
     teeth are missing"), each with its citation and population; `docs/references.md` gains the sources.
   - `open_dental.ENTRY_PERIO_SHARE_BY_AGE`: the periodontal share by age band (Suzuki et al. 2022, impacted teeth
     left out). `Params.entry_other_teeth_by_age`: the mean number of non-periodontal teeth missing at entry per
     patient, by age band, set so the generated shares match it; `Params.entry_other_tooth_weights`: which teeth
     (molars, premolars, front teeth).
   - In `build_with_readings`, after `draw_mouth_columns` and before the teeth are written: a second stream
     `random.Random(f"{seed}:open_dental:entry_reason")` draws the count (Poisson) and the teeth; the teeth holding
     the worst CAL and probing depth stay; a mouth below stage IV keeps 20 teeth. The main stream is untouched by
     these draws, though the extract downstream changes because fewer teeth are present.
   - Regenerate with the scripts: `47_tooth_table.py` (parity inputs), `51_tooth_loss_model.py` (results,
     `docs/tooth_loss.md` by hand from them), `diagrams/_build/silver_erd.py` (dictionary counts),
     `50_dq_site.py` (website JSON); R parity. The analysis plan's change log records the change.

9. **Shared risk factors for non-periodontal loss (US8, #433).**
   - Sources first: published effects of smoking and diabetes (and, where a source gives one, dental attendance or
     socioeconomic status) on tooth loss for reasons other than periodontitis go in [research.md](research.md)
     ("Shared risk factors"), each checked against the paper; `docs/references.md` gains the sources.
   - `Params.entry_other_smoking_ratios` (cigarettes a day, lower bound → rate ratio) and
     `Params.entry_other_diabetes_ratio` (HbA1c 6.5% or more), fixed defaults citing research.md.
     `open_dental.entry_other_rate_ratio(risk, p)` multiplies them; `open_dental.entry_other_rate_norm(p)` is its mean
     over `Params.entry_other_norm_draws` patients from `synthetic.draw_risk` on the stream
     `"open_dental:entry_reason:norm"` (no seed: the same for every extract). The patient's Poisson mean is the
     band's mean × ratio / norm, so each band's mean count, and its periodontal share, is unchanged.
   - Same entry stream; `sites.draw_mouth_columns` untouched; teeth still chosen by tooth type.
   - Regenerate as in step 8, and give `docs/tooth_loss.md` the before/after missing-at-entry AUC and specificity and
     the stage recount, labelled synthetic.

## Tests first

- `test_open_dental.py`:
  - seeded and identical;
  - existing datasets unchanged;
  - every column has a source;
  - no extract column carries the truth;
  - the shares and rates are recovered within tolerance;
  - every planned extraction is one `procedurelog` row with one or more `proctp` copies;
  - diagnoses come from `definition` (both lists), and ICD codes are on the declared small share only.
- `test_tooth_loss.py`:
  - each status on hand-built extracts;
  - no feature dated after the loss;
  - the shared feature set has no own measures;
  - the answer key is never a feature;
  - the split is grouped and stratified;
  - the metrics on hand-worked cases;
  - the expected-count stage rule;
  - plan copies counted once (`planned_extraction`), and a planned-then-completed tooth counted as completed;
  - both label sets built from the same extract.
- `test_schemas.py` and `test_bundle.py`: the new bench and its three schemas.
- `r/tests/test_parity.R`: statuses, the stage rule and the metrics.
- US7: `test_open_dental.py` (the periodontal share at entry by age band recovered within 0.05 on a large seeded
  extract and lower when young; non-periodontal counts not correlated with worst CAL; own stream, seeded);
  `test_tooth_loss_model.py` (the missing-at-entry evaluation holds both classes; AUC and specificity are numbers).
- US8: `test_open_dental.py` (the rate ratio and its norm on hand-built risks; observed/expected non-periodontal
  count above 1 for daily smokers and for diabetes, below 1 for the rest, on a large seeded extract; age-band shares
  still within 0.05; no link to worst CAL within age band and risk group; neutral ratios give US7's means; seeded).

## Environments

dev, uat and prod get the three new schemas and the job on their next deploy. The implementation PR says so.
