# Tasks: extraction rates (spec 037)

- [x] T001 [US1-US3] Failing tests in `python/tests/test_open_dental.py`: rate, share by age, visit window
- [x] T002 [US1-US3] `extraction_rates` measure (counts only, `@traced`)
- [x] T003 [US3] `Params.visits (2, 20)`, `last_visit` 2025-12-31
- [x] T004 [US1] `extraction_per_year` replaces `other_extraction_per_visit`; other-reason extractions by band
- [x] T005 [US2] Periodontal top-up on the worst teeth; set `perio_topup_scale_by_age` by measurement
- [x] T006 Data card (`docs/synthetic_data.md`) and references (Vehkalahti 2023; Burke and Lucarotti 2015)
- [x] T007 Rerun the tooth-loss model (60,000 patients), update `docs/tooth_loss.md`, the study page, the analysis
  plan's change log; regenerate the silver ERDs
- [x] T008 [US4] `nhanes.missing_teeth_by_age` and `scripts/61_tooth_loss_targets.py` (NHANES 2009-2014, BRFSS 2022)
- [x] T009 [US4] Failing tests: entry mean and share none by band against NHANES (dentate)
- [x] T010 [US4] Negative binomial entry counts; periodontal labelling for Suzuki's share; the 20-teeth rule at stage III
- [x] T011 [US5] State scaling by ORH02 with a test
