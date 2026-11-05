# PR 588 review: spend and speed in the data-quality report

Refs #576 (T010). Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Checks
- Test first: 15 tests in `test_governance.py`, which failed before the module existed. They cover the register,
  each measure, a projected overrun, the report-not-pass cases, the cost-data checks and the gold shape.
  Full suite: 2,148 passed, 4 skipped.
- Settings: each budget is declared once, with a limit, owner and action (AGENTS.md: an alert without an action
  isn't one). A malformed entry stops Load results, naming the field (settings checked before work).
- Estimates and calibration: the per-task budget leaves `calib:` runs out (FR-012). A check fails if a priced row
  doesn't say "estimate".
- Gold: `measure_text` and `run_ts` are declared in `gold_model.py` and `gold_names.py`. The ERD sources are
  regenerated. The SQL-conventions and table-comments tests pass.
- Note text: the guard against `_text` columns in the DQ tables is narrowed to exempt only `measure_text`. A new
  assertion keeps that column empty on every row built from the records.
- Idempotent: `dq_check` is still overwritten whole on every Load results run.

## Findings
- Not blocking: a failing budget isn't routed to a digest yet. That is T011, and until then the rows show on the
  dashboards.
- Not blocking: the first limits are guesses, set before any priced run. They're the owner's to change by PR, and
  the file says so.
- Not blocking: weeks start Monday 00:00 UTC. Kaggle's own reset time is uncertain (third-party guides disagree),
  so the allowance budget is approximate around the boundary.

Nothing blocking. It starts no run, so it can merge when CI is green.
