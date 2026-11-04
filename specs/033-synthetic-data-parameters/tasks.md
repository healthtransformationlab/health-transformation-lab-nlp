# Tasks: synthetic data parameters (spec 033)

- [ ] T001 [US1] failing test: every generator parameter has a source or "placeholder" in docs/synthetic_data.md
- [ ] T002 [US1] write the data card; check each source's full text; add it to docs/references.md
- [ ] T003 [US2] failing tests for settable smoking, diabetes and insurance shares; old study-build values unchanged
- [ ] T004 [US2] set the extract's shares from checked sources; rerun tooth-loss, data-quality and preset results
- [x] T005 [US3] with #467: the study build uses US2's shares
- [x] T006 [US4] failing tests: edentulous share by age on its own stream, no chart or answer-key rows, left out of
  the model, the stage recount and the charting rates, the `chart_without_teeth` check, optional clinic states; then
  the code; rerun tooth-loss, data-quality and preset results; the data card's edentulism row
- [x] T007 [US5] failing test pinning the ADA HPI shares; set them; cite item 82; rerun what reads insurance
