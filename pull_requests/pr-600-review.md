# PR 600 review: `_dbu` suffix and `fact_pipeline_run.billed_dbu` (#597)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

| Check | Result |
|---|---|
| Branch `<type>/<issue>-<slug>`, `Closes #597` | ok |
| Test first: `test_a_run_carries_its_dbus_beside_its_cost`, `test_fact_pipeline_run_declares_billed_dbu_after_cost` | ok |
| SQL names: `billed_dbu` is `<what>_<kind>`, `double`, enforced by `test_sql_conventions.py` | ok |
| New column described in `gold_model.py` (table comments) and mapped in `gold_names.py` | ok |
| Write stays idempotent (same MERGE on run key) | ok |
| ERD regenerated from `gold_erd.py`, not hand-edited | ok |
| No secrets, no PHI, no org names | ok |
| Full suite | 2194 passed, 4 skipped |

## Notes
- DBU lines only: a usage line in another unit (e.g. GPU hours) adds 0 DBU but still adds its cost, so
  `billed_dbu` and `cost_usd` can move independently by design.
- Empty until the service principals get SELECT on `system.billing`.

## Blocking
None. Changes AGENTS.md, so it waits for the owner's "merge".
