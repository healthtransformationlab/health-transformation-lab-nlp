---
pr: 768
branch: fix/751-034-comments-in-the-overwrite
title: "034 BUG8: write Load results' overwrites with their column comments (held for the owner)"
author: jcbowyer (agent session)
reviewed_at: 2026-11-15
reviewer: an independent read-only reviewer subagent (given the diff, the rubric, AGENTS.md and CLAUDE.md, not the author's conclusions; Superpowers isn't installed in this session) + coordinator verification
verdict: approve-with-nits
---

# PR Review: 034 BUG8: write Load results' overwrites with their column comments

## Summary
Load results rewrites 14 grader tables from pandas on every run. An overwrite drops their column comments, so
`table_comments.apply` sent them all again afterwards: 214 statements a run, one at a time. This pull request adds
`table_comments.with_comments`, which puts each declared column's comment in the frame's schema, so the overwrite
commits them. The loop now prints how many statements `apply` still sent for each table.

The reviewer found nothing critical or important, and the design can't make comments worse: if the metadata doesn't
survive, `apply` sends the comments as before. The five minor findings were fixed, or are noted for the merge. Approve
with nits. It waits for the owner, because merging runs Load results, and that run is the real test.

## Scope of Change
- Files changed: 5: `table_comments.py`, `test_table_comments.py`, `10_load_results.py`, spec 034's `plan.md` and this review
- Areas touched: python, databricks, specs
- Commits:
  - `b93ebc3` Write Load results' overwrites with their column comments
  - `b9c9b18` Tie with_comments to apply in a test, and say what an overwrite still drops
  - this file
- Range reviewed: `ffa1953..b93ebc3` by the reviewer; `b93ebc3..b9c9b18` by the coordinator, from the findings

## CI Status
| Check | Status |
|---|---|
| `check`, `changes`, `python`, `python-databricks-runtime`, `postgres`, `bundle`, `azure-infra` | pass on `b93ebc3` |
| `r-parity` | skipped (no R-relevant change) |
| `b9c9b18` and this file | CI runs again on push; the head must be green before merge |

## Secrets, PHI and Claims Scan
- **Secrets:** clean.
- **PHI / real data:** clean. No data file is touched.
- **Organization claims:** clean. No organization names, and no phrases from the wording list.

## Strengths
- If the metadata isn't kept, `apply` falls back to the old path. Comments can't get worse, only the saving can be smaller.
- The helper is pure, imports no pyspark, and is tested with stand-in objects.
- **No schema changes for readers.** The reviewer rebuilt all 14 tables from the tree:
  - All 200 declared columns are plain `\w+` names, and no table has an undeclared column.
  - The three all-null columns are cast to string before the select.
  - An alias changes no type, nullability or order. Dashboards, Genie and the contracts see the same columns.
- Each table gets one Delta commit instead of one plus about 15 comment commits.
- The new print makes the after-merge check readable from the job's output.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
1. **Fixed in `b9c9b18`.** The notebook test only looked for `table_comments.with_comments(` in the 3 lines before each
   overwrite, so a frame made in between passed.
   - It now requires the line before each overwrite to assign the helper's result, and the overwrite to write that frame.
   - Checked against the notebook (passes), with a frame replaced before the write (fails), and with a different frame written (fails).
2. **Fixed in `b9c9b18`.** No test joined the helper to `apply`. The new test
   `test_what_with_comments_writes_is_what_apply_reads` feeds what `with_comments` writes into `apply`: 0 statements
   when the table's own comment is kept, and only that one when it isn't.
3. **Fixed in `b9c9b18`.** The docstring said `apply` sends nothing after the overwrite and counted 214.
   - The 14 tables declare 200 column comments, so 214 = 200 + 14 table comments, and the overwrite most likely still drops the table's own.
   - The docstring now says no column comment is sent, and that the table's own may still be.
   - Expect `1 comment statements sent` per table.
4. **Fixed in `b9c9b18`.** A comment carried in the frame is written with the data, so a comment the catalog refused
   would now fail that table's write instead of warning.
   - The plan and the docstrings say so.
   - Low risk: the same texts were already accepted by `ALTER`, and the longest is 165 characters.
5. **For the merge.** `Closes #751` closes the issue before its last "Done when" line, which can only be read from the
   first Load results run after the merge. Whoever merges reads that run and reopens #751 if any of the 14 tables
   prints more than 1.

Not taken, and outside this issue:
- **The table comment in the write:** `saveAsTable` may accept `.option("comment", ...)` for the table's own comment, which would remove the last 14 statements. Unverified.
- **The other overwrites:** notebooks 01, 07 and 12 also overwrite, so `with_comments` fits them too. Notebook 11's renames keep their comments, because an alias without new metadata carries the column's own.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | scan clean |
| Synthetic only, no PHI | ✅ | no data files |
| No organization claims; vendors cited | ✅ | |
| Test first | ✅ | the three new tests failed before the change (2 `AttributeError`, 1 assertion); the coordinator saw them fail first, and the reviewer confirmed it against the base |
| Python and R in parity | n/a | |
| Spec for big changes | n/a | a fix with tests; spec 034's plan is updated |
| Configuration | ✅ | no setting changes; dev changes at the next Load results |
| Idempotent writes | ✅ | the overwrite is unchanged apart from the column metadata |
| Commits | ✅ | imperative subjects, bodies say why, co-author trailers |
| Telemetry | ✅ | `with_comments` has `@traced` |
| Secrets register, alerts, seeds, paths, prices, deck figures | n/a | |

## Test Coverage
- **`tests/test_table_comments.py`:** 32 passed on `b9c9b18`.
- **The tests that read the notebook, the callers and the rules:** 283 passed, 4 skipped on `b93ebc3`. The reviewer ran the eight files that read the notebook again: 170 passed.
- **The whole suite on `b93ebc3`, with the deploy job's packages:** 2,599 passed, 39 skipped, 6 failed.
  - The 6 are in `test_agent_harness.py`. They fail the same way on unchanged `main` in this sandbox and pass in CI.
- **`ruff check`:** clean on the changed lines. The notebook's import-order finding (line 30) is on `main` too.
- **Not tested here: real Spark.** That `Column.alias(..., metadata=...)` on Spark Connect carries the comment into the Delta schema through an overwrite. The reviewer was about 90% confident on the alias and 80–85% on Delta, from the code. The first run's printed counts show it.

## Verdict
Approve with nits. Nothing must change before merge. It waits for the owner: merging runs the deploy, which starts
Load results on the Free Edition workspace (AGENTS.md rule 6). Read that run's per-table counts after the merge, as
finding 5 says.
