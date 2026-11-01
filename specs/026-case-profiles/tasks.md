# Tasks: case profiles and record-mismatch flags (spec 026)

Tests come first in every story (constitution III). Each story is its own branch and PR off `main`:
`feat/234-026-case-profiles`, `feat/235-026-mismatch-rules`, `feat/236-026-recheck-page`. Every output is
synthetic and says so; all wording follows `AGENTS.md` "Words" (`test_wording.py` guards it).

## Phase 1: Setup

- [x] T001 Create `python/health_transformation_lab_nlp/case_profile.py` with a module docstring (spec 026, synthetic only, KEEPER citation, the Words rule) and `python/tests/test_case_profile.py`

## Phase 2: Foundational

- [x] T002 In `python/health_transformation_lab_nlp/case_profile.py`, a `_shown(value)` helper: missing or `"unknown"` reads "not recorded", booleans yes/no, numbers without trailing zeros, statuses as their code; and `history_frame(visits)` renaming `rec_max_cal_mm`, `rec_rbl_pct`, `rec_teeth_lost_perio` for `plausibility.check_history` (as `scripts/20_data_quality.py` does)

## Phase 3: US1 #234, a standard case profile for every visit (P1, MVP)

**Goal**: one profile per visit, nine categories, structured values only. **Independent test**: build profiles for the study; every visit has all nine categories, missing values read "not recorded", no note text.

- [x] T003 [US1] Failing tests in `python/tests/test_case_profile.py`: hand-built visits give all nine categories in order; values carry their units; a visit with no chart shows measurements "not recorded" and the chart reading "not taken"; unknown statuses read "not recorded"; a patient's last visit reads "no later visit"; the next visit's code and its failed plausibility flags (from `check_history`) appear under "after the visit", "none" when it fails none; only the note reader's status column (`notes`, a status, not text) is read and every value is short; one complete profile per visit of the built study
- [x] T004 [US1] `PROFILE_ITEMS` in `python/health_transformation_lab_nlp/case_profile.py`: ordered (category, item, source column or `None`, unit) for Demographics (age, clinic), Presentation (`proc_dx_completed`, `proc_dx_planned`, `exam_form`), Visit context (`visit_seq`, `charted`, `treated_before`), Measurements (`rec_max_probing_depth_mm`, `rec_bop_pct`, `rec_max_cal_mm`, `rec_rbl_pct`, `rec_teeth_lost_perio`, `rec_pct_teeth_involved`), Tests and imaging (`probing_chart`, `radiograph_ai`), Risk factors (`cigarettes_per_day`, `diabetes`, `hba1c`), Treatment (`proc_codes_completed`, `proc_codes_planned`), Other readings (`notes`, `algorithm_v0`, `algorithm_design`), After the visit (two derived items)
- [x] T005 [US1] `build_profiles(visits)` (`@traced`): long frame `visit_id, category, category_order, item, item_order, value, unit`
- [x] T006 [US1] `grader_tables.dq_tables` builds `fact_case_profile_item` from `visits_structured.csv` (not a committed CSV: the long form is about 6 MB); gold columns in `gold_names.py` (`category_name`, `category_order_num`, `item_name`, `item_order_num`, `item_value_name`, `item_unit_name`; a `_num` column must be bigint, so values stay labels); declare it in `diagrams/_build/gold_model.py` with a `fact_visit_evidence` relationship and rerun `gold_erd.py`; extend `test_grader_tables.py` and `test_gold_model.py`
- [x] T007 [US1] Genie: add `fact_case_profile_item` to `DQ_TABLES`, an instruction on reading a profile and a sample question ("Show the case profile of visit 1234.") in `dashboards.py`, with a test in `test_dashboards.py`; rebuild with `scripts/42_build_dashboards.py`
- [x] T008 [US1] Docs: profiles in `docs/graders.md`; R6 in `docs/rag_and_vocabulary.md` notes the profile exists

## Phase 4: US2 #235, record-mismatch flags scored against the truth (P1)

**Goal**: six named rules, each scored over the visits it can check. **Independent test**: one hand-built visit per rule fails only that rule; on the study every rule is scored with its checkable count; R gives the same outcomes and scores.

- [x] T009 [US2] Failing tests in `python/tests/test_case_profile.py`. One visit per rule that fails only it, with the other evidence set so no second rule fires (chart reading within one step of the code, a periodontal procedure on file, radiograph unknown):
  - stage III code, CAL 2 mm, bone loss 10%, no tooth lost, PD 4 mm (code higher than the chart);
  - gingivitis code, CAL 4 mm (code lower than the chart);
  - stage II code, no periodontal procedure (no periodontal care);
  - healthy code, chart reading stage II (code against the chart reading);
  - gingivitis code, radiograph stage III (code against the radiograph);
  - stage III then stage I for the same patient (stage drops).

  Also: no chart gives `not_checkable` for the chart rules; no code gives `no_code` for all; no earlier periodontitis code gives stage drop `not_checkable`; stage-drop flags equal `check_history`; a drop whose earlier code is the wrong one is a true flag; `score_rules` on a hand-worked table gives precision, recall and injected errors over checkable visits, "only this rule", and "any rule" over every coded visit
- [x] T010 [US2] `RULES` and named thresholds in `case_profile.py`: `HIGH_CODE_MAX_CAL_MM = 3`, `HIGH_CODE_RBL_PCT = 15`, `HIGH_CODE_MAX_PD_MM = 6` (stage I limits, `labels.py`), `LOW_CODE_CAL_MM = 3`, `LOW_CODE_RBL_PCT = 15` (beyond stage I), `CHART_STEPS = 1`, each with its source comment
- [x] T011 [US2] `check_rules(visits)` (`@traced`): one row per (visit, rule), `outcome` in `fail | pass | not_checkable | no_code`, `evidence` with the triggering values (stage drops name the earlier visit); the recorded code is `proc_dx_completed`; periodontal care is `proc_codes_completed` or `proc_codes_planned` reading periodontitis; status steps from `labels.LABELS`
- [x] T012 [US2] `score_rules(checks, truth)` (`@traced`): per rule and `any_rule`, overall (`clinic = "All"`) and per clinic: checkable, flagged, not checkable, code-truth mismatches (`proc_dx_completed != truth_status`; for stage drops, either visit), true flags, precision, recall, only this rule, injected errors (`record_error` non-empty) checkable and caught
- [x] T013 [US2] `python/scripts/45_case_profiles.py` writes `data/datasets/case_profiles/record_mismatch.csv` (failed rules only, with clinic and `is_injected_error`) and `mismatch_rule_score.csv`; prints the score table headed SYNTHETIC with the injected-error ceiling (34/45) and the temporal checks' rate from `data_quality/injected_error_recall.csv`; add it to `make_parity_inputs.sh` after `20_data_quality.py`
- [x] T014 [P] [US2] R twin `r/R/15_spec026.R` (base R): `check_rules`, `score_rules`; source it in `r/tests/test_parity.R` and compare outcomes exactly and scores to 1e-9 against the CSVs, skipping with a message when they are missing
- [x] T015 [US2] `grader_tables.dq_tables` adds `fact_record_mismatch` and `dq_mismatch_rule`; gold columns (`rule_name`, `rule_label_name`, `mismatch_evidence_text`, `is_injected_error`, `checkable_count`, `flagged_count`, `not_checkable_count`, `code_truth_mismatch_count`, `true_flag_count`, `precision_ratio`, `recall_ratio`, `only_rule_count`, `injected_checkable_count`, `injected_caught_count`) in `gold_names.py`; declare both in `gold_model.py`; extend the tests
- [x] T016 [US2] `docs/graders.md`: each rule, its threshold and source, and the measured scores labelled "synthetic records, against the generator's truth", with per-clinic injected-error counts marked too few to read

## Phase 5: US3 #236, "Records to recheck" in the DQ grader and its Genie space (P2)

**Goal**: the profile and flags where people already look. **Independent test**: dashboard and Genie files build from code, `--check` passes, the page reads only declared gold tables.

- [x] T017 [US3] Failing tests in `python/tests/test_dashboards.py`: the DQ grader has a "Records to recheck" page with a synthetic banner, the rule-score table with checkable counts, the flagged-visit table and a visit-filtered profile table; its datasets read only declared gold tables; the Genie space lists the mismatch tables and its instructions call flags record mismatches (Genie's own answers are LLM output, checked by hand on dev)
- [x] T018 [US3] Add the page to `dq_grader()` in `dashboards.py` (banner: "Synthetic records. A mismatch is a coding or charting gap, not a clinical error."; clinic, rule and visit filters)
- [x] T019 [US3] Extend `DQ_TABLES`, `DQ_INSTRUCTIONS` (the rules, the denominators, "not checkable", the Words rule) and `DQ_QUESTIONS` ("Which visits have a stage III code but max CAL under 3 mm?", "Which rule adds the most flags no other rule makes?") in `dashboards.py`
- [x] T020 [US3] Rebuild `databricks/dashboards/dq_grader.lvdash.json` and `databricks/genie/dq_grader.geniespace.json` with `scripts/42_build_dashboards.py`; describe the page in `docs/graders.md`

## Phase 6: Polish

- [ ] T021 Full checks: `cd python && pytest -q tests`, `ruff check` on changed files, `python/scripts/make_parity_inputs.sh && Rscript r/tests/test_parity.R` where R is available, `python scripts/42_build_dashboards.py --check`; rerender the gold ERD PNGs with `diagrams/_build/drawio_render.js` where the draw.io viewer is reachable
- [ ] T022 Each PR says no environment's settings change and the new gold tables reach dev, uat and prod with the next deploy and Load results; review written to `pull_requests/pr-<n>-review.md`

## Dependencies

- Setup (T001) → Foundational (T002) → US1 (T003–T008).
- US2 needs T002 (`history_frame`, for the stage-drop rule through `check_history`); it doesn't need the profile.
- US3 needs the gold tables from US1 (T006) and US2 (T015).
- Polish runs per PR.

## Parallel opportunities

- T014 (R twin) runs beside T013 once T011–T012 are written.
- T008 and T016 (docs) run beside the code in their story.
- Within US3, T017's dashboard and Genie tests can be written together.

## Implementation strategy

MVP is US1: a profile per visit in gold, which Genie can show before the page exists. Then US2 adds the flags and
scores; US3 puts both on the dashboard. Each story ships as its own PR closing its issue.
