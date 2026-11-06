# Tasks: extraction rates (spec 037)

- [ ] T001 [US1-US3] Failing tests in `python/tests/test_open_dental.py`: rate, share by age, visit window
- [ ] T002 [US1-US3] `extraction_rates` measure (counts only, `@traced`)
- [ ] T003 [US3] `Params.visits (2, 20)`, `last_visit` 2025-12-31
- [ ] T004 [US1] `extraction_per_year` replaces `other_extraction_per_visit`; other-reason extractions by band
- [ ] T005 [US2] Periodontal top-up on the worst teeth; set `perio_topup_scale_by_age` by measurement
- [ ] T006 Data card (`docs/synthetic_data.md`) and references (Vehkalahti 2023; Burke and Lucarotti 2015)
- [ ] T007 Rerun the tooth-loss model (60,000 patients), update `docs/tooth_loss.md`, the study page, the analysis
  plan's change log; regenerate the silver ERDs
