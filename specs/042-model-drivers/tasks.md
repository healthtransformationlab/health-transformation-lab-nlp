# Tasks: How each model ranks, and what drives its score (spec 042)

## US1 - each note-reading model ranked, paired, with its drivers (#863)

- [x] T001 [US1] Failing test `python/tests/test_model_drivers.py`
- [x] T002 [US1] `model_drivers.py`: features, exact McNemar, rank, contrasts, chart effects, driver fit
- [x] T003 [US1] `scripts/74_model_drivers.py` with `--check`; tables in `data/datasets/model_drivers/`
- [x] T004 [US1] `docs/model_drivers.md`, the block in `docs/edr/README.md`, the link in the landing README

## US2 - load into Databricks with explanations (#864)

- [x] T005 [US2] Failing test `python/tests/test_load_model_drivers.py` (fake client)
- [x] T006 [US2] `scripts/75_load_model_drivers.py`: tables with comments and batch key; runs; traces and assessments
- [ ] T007 [US2] Load the dev workspace; record row counts, the leader's count and the trace count in the PR

## US3 - de-identification in the same format (#866)

- [x] T030 [US3] Failing test `python/tests/test_deid_drivers.py`
- [x] T031 [US3] CPU rerun of the 15 local tools; reproduction of `data/deid/scores.csv` (60 of 60 tool-tier cells)
- [x] T032 [US3] `deid_drivers.py`, `scripts/76_deid_drivers.py`, `docs/deid_drivers.md`, `deid_*.csv`
- [x] T033 [US3] `scripts/77_load_deid_drivers.py`; eight tables loaded on dev, counts and comments checked in SQL
