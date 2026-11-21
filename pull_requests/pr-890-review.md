# Review: Notebook Timeout and wall_hours on leaderboard watch

## Summary

`kaggle/submission_watch.py` records `finished_ts` on first COMPLETE or failed
sighting, `wall_hours`, and `final_status_text` (score or `Notebook Timeout` when
Kaggle reports exceeded runtime). Optional `--entries` writes the slim companion
CSV. Older ledgers migrate on read.

## Checks

- [x] `pytest python/tests/test_leaderboard_watch.py` (20 passed)
- [x] Runtime exceedance maps to status `error` and `Notebook Timeout`
- [x] Already-complete-on-first-sight still leaves finish time empty
