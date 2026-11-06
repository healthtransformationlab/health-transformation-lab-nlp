# Implementation plan: extraction rates (spec 037)

All changes are in `python/health_transformation_lab_nlp/open_dental.py` (the extract generator) and its tests.

## Parameters (`Params`)

- `visits: (2, 20)` (was `(2, 8)`) and `last_visit: date(2025, 12, 31)`. Visits after `last_visit` are dropped
  (at least two are kept by moving the first visit earlier when needed). US3.
- `extraction_per_year: 0.17` replaces `other_extraction_per_visit`. Per recall interval (half a year) and age
  band, the expected extractions are split by `ENTRY_PERIO_SHARE_BY_AGE` into a periodontal and an other part. US1.
- Other-reason extractions: Poisson with mean `0.5 * extraction_per_year * (1 - share)` per interval, on a random
  tooth present.
- Periodontal extractions: the chart-driven losses (`draw_history`) stay. Extra periodontal extractions top them
  up to the band's target, `0.5 * extraction_per_year * share` per interval. They're drawn only for patients whose
  chart has attachment loss (`max_cal_mm >= 3`), with the mean scaled up by `perio_topup_scale_by_age` so the band
  as a whole hits the target. They fall on the present teeth with the worst attachment loss. US2.
- `perio_topup_scale_by_age` is set by measurement (as `entry_other_teeth_by_age` was in spec 029 US7) and the
  method is recorded in `docs/synthetic_data.md`.

## Measures

- `extraction_rates(tables, truth)`: one row per age band with patient-years, completed extractions, the rate per
  patient-year and the share periodontal. It's used by the tests and the data card, counts only.

## Tests (written first)

- Pooled over generator seeds (3 extracts of 6,000 patients): the rate is 0.15-0.20; every band's periodontal share
  is within 0.07 of target; no visit is after 2025-12-31; visits per patient run 2-20; the mean years of record is
  reported and is over 3.
- The existing entry-share and edentulism tests still pass.

## Reruns

`scripts/51_tooth_loss_model.py` (60,000 patients, #609), then `docs/tooth_loss.md`, the study page and the
analysis plan's change log. The ERD profile counts (`diagrams/_build/silver_erd.py`) are regenerated.
