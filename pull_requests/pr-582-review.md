# PR 582 review: the coding-agent task runs and their cost in gold

Refs #569 (T004). Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Checks
- Test first: five tests in `test_grader_tables.py` errored until `agent_tables` existed:
  - rows and provenance per run file;
  - calibration labels and tiers;
  - budget in seconds, and estimates named;
  - Load results writes the table;
  - the frame becomes the declared gold table.
  Full suite: 2,125 passed, 4 skipped.
- Names follow AGENTS.md: `_count`, `_seconds`, `_hours` (#580), `_ratio`, `_usd`, `_text`, `_url`, `is_`.
  - The exit status is `verify_exit_num`: a number, not a coded value.
  - The patch size is `agent_patch_byte_count`.
  - `test_sql_conventions.py` checks every column.
- The table comment states the grain and that the harness is this repo's, not the competition's evaluator
  (`test_table_comments.py`).
- Idempotent: Load results overwrites the table whole from the committed CSVs, as it does the other grader tables.
- Calibration rows are labelled (`is_calibration`) and stay in the table, so the harness's bounds sit next to a
  model's runs. A view of a model's rates must filter on it (spec 036 FR-012, US3's view).

## Findings
- Not blocking: the cost columns are empty for every committed row, since the pilot ran before them. They fill on
  the next Kaggle run.
- Not blocking: a cost column that is empty in every row is written as a string. Load results does this for
  every grader table with an all-empty column (an all-null column has no type). It becomes a double once a row has
  a value; `overwriteSchema` allows the change.
- Not blocking: the gold PNGs aren't re-rendered (no draw.io renderer here). The `.drawio`, `.mmd` and
  `data_model.md` sources are current.

Nothing blocking. It starts no run, so it can merge when CI is green.
