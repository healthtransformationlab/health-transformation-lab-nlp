---
pr: 914
branch: fix/913-041-trace-loader-dupes
title: "041 BUG3: load each Colab task once and delete Unity Catalog traces by SQL"
author: jcbowyer
reviewed_at: 2026-11-23
reviewer: claude-code (in-session checklist against .claude/review-rubric.md; local pytest; live reloads checked by SQL)
verdict: approve-with-nits
---

# PR Review: load each Colab task once and delete Unity Catalog traces by SQL

## Summary

Closes #913. The trace loader read both copies of each task in a collected Colab run, so `lean-nlp25` was written
twice. Its reload delete (#899) couldn't remove a Unity Catalog trace, because MLflow's `delete_traces` rejects every
id form. Now the loader takes one folder per task, skips a repeated `trace_key` within a load, and deletes by SQL
from the spans and annotations tables.

## Scope of change

- `kaggle/load_agent_traces.py`: `_task_dirs`, `load_run` (`skipped_duplicate`), `_bare_trace_id`,
  `delete_statements`, and `MlflowTraceClient.delete_keys` and `_sql`; `table_prefix` comes from the experiment's
  trace location.
- `python/tests/test_load_agent_traces.py`: 9 new tests; 2 existing expected dicts gain `skipped_duplicate`.
- `docs/telemetry.md`: removal, duplicate check and fix, the warehouse setting.

## Checks

- `pytest tests/test_load_agent_traces.py`: 33 passed; the new tests failed before the change.
  `tests/test_migrate_agent_traces.py`: 4 passed.
- Live, with this branch's loader:
  - `lean-nlp25`: replaced 25, wrote 25; 25 traces for 25 keys, 15 solved (`official_verify`).
  - `k-lean-hard36`: replaced 36, wrote 36; 36 for 36, 11 solved.
  - The whole table has 1,768 traces and no run label with a repeated key.
- The SQL matches the rows checked by hand: `trace_id` in `<prefix>_otel_spans`, and `target_id` in
  `<prefix>_otel_annotations` (the source of the `trace_metadata` view: METADATA, TAG, RUN_LINK and assessment rows).

## Findings

### Blocking

None.

### Should fix

None.

### Nits

- `existing_trace_ids` still maps each key to one trace id. A run that already holds two traces under one key would
  lose only one on reload. No such run is left after the repair, and the loader can't create one now.
- The ids go into the SQL as literals, after a check that each is a plain token (letters, digits, `_`, `-`); a test
  covers an injection-shaped id. The Statement Execution API's parameters would also work.
- Follow-up #915: with `--verdicts`, a kernel-graded task the file omits isn't loaded.

## Rules

- Test first; issue with four parts (#913); branch `fix/913-041-trace-loader-dupes`; `Closes #913`; docs in the same PR.
- Deletes: this PR deletes nothing when merged. The loader deletes only a reload's own old traces by key, as #899
  designed. The one-off repair of 57 duplicate traces was done on the owner's go-ahead and is recorded in the PR with
  the table versions for `RESTORE`.
- No secret in code, tests or spans; `DATABRICKS_WAREHOUSE_ID` is a setting, not a credential.

## Verdict

**approve-with-nits**
