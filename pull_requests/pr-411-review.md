---
pr: 411
branch: fix/248-migrate-missing-key
title: "018 BUG2: migration handles a merge key column neither gold table has"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-01
reviewer: implementing agent's self-review (no reviewer subagent run)
verdict: approve
---

# PR Review: 018 BUG2: migration handles a merge key column neither gold table has

## Summary
This fixes issue #248 as the issue proposes. dev's Load results failed in `migrate_gold_names` because
`merge_missing` took the type of a null stand-in key column from the legacy table, and `run_id` (in
`MERGE_KEYS["fact_llm_call"]`) is in neither table. `not_carried` had the same gap on the legacy side.
- **Type of the stand-in:** `gold_names.merge_key_types` gives the legacy side's type, else the current side's,
  else `string`. It is pure Python and unit-tested.
- **Both sides:** the notebook's `keyed()` adds a typed null for a key column missing on either side, and both
  `merge_missing` and `not_carried` use it.
- **Only the legacy table's own columns are written** (`select(*src.columns)`), so no stand-in column reaches gold.

Approve.

## Tests
- Four new tests in `python/tests/test_gold_names.py`: the key on the legacy side only, on the current side only,
  on neither, and a notebook check. All four failed before the fix.
- Full suite: 1203 passed, 16 skipped.

## Secrets, PHI and Claims Scan
Clean. No data, settings or credentials change.

## Findings
None blocking.
- **Spark code checked by text only:** pyspark isn't installed locally. The next dev Load results run will confirm
  the merge and that every legacy key arrives (`not_carried` fails the run if not).
- **Idempotent:** null matches null under `eqNullSafe`, so a key column neither side has never splits or duplicates
  rows, and a rerun adds nothing.
- **Rows already carried** before the failure (`ai_predictions`, `dim_result_file`, `fact_judge_call`) are matched
  by key and not added again.

## Rubric
- `@traced` is on the new public function.
- No hard-coded data paths.
- Environments: dev reruns the migration in Load results. uat and prod have no legacy schemas, so nothing changes.
- `Closes #248`.
