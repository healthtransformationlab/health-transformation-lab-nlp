---
pr: 746
branch: fix/741-034-skip-comments-in-place
title: "034 BUG7: send only the table and column comments a table doesn't already hold (held for the owner)"
author: jcbowyer (agent session)
reviewed_at: 2026-11-15
reviewer: an independent read-only reviewer subagent (given the diff, the rubric, AGENTS.md and CLAUDE.md, not the author's conclusions; Superpowers isn't installed in this session) + coordinator verification
verdict: approve-with-nits
---

# PR Review: 034 BUG7: send only the table and column comments a table doesn't already hold

## Summary
Since pull request 538, every Load results run has sent up to 1,132 comment statements, one at a time, comments in
place or not. Its `load` task went from about 1 to about 17 minutes on every merge, on the shared Free Edition
allowance. This pull request makes `table_comments.apply` read the comments a table holds and send only the ones
that are missing or different.

The reviewer found no correctness bug, and every uncertain read falls back to sending, which is the old behaviour.
The important finding is the scope. Load results overwrites 14 tables each run, and an overwrite drops their column
comments, so about 214 statements still go out: roughly 3 minutes, not 17. That is now #751. The minor findings were
fixed on the branch. Approve with nits; it waits for the owner because merging runs the deploy.

## Scope of Change
- Files changed: 4 (+114 / -22 in total): `table_comments.py`, `test_table_comments.py`, spec 034's `plan.md` and this review
- Areas touched: python, specs
- Commits:
  - `acbf5c1` Send only the table and column comments a table doesn't already hold
  - `7a91918` Log the comment statements sent, and never fail a write on a field's metadata
  - this file
- Range reviewed: `0114053..acbf5c1` by the reviewer; `acbf5c1..7a91918` by the coordinator, from the findings

## CI Status
| Check | Status |
|---|---|
| `check`, `changes`, `python`, `python-databricks-runtime`, `postgres`, `bundle`, `azure-infra` | pass on `acbf5c1` |
| `r-parity` | skipped (no R-relevant change) |
| `7a91918` and this file | CI runs again on push; the head must be green before merge |

## Secrets, PHI and Claims Scan
- **Secrets:** clean. No token, key or credentialed URL in the diff.
- **PHI / real data:** clean. No data file is touched.
- **Organization claims:** clean. No organization names, and no phrases from the wording list.

## Strengths
- Every unreadable or uncertain read sends the comment, as before. The realistic risk is a smaller speed-up, not a stale comment.
- The new arguments are keyword-only, so existing callers don't change, and the contract matches the issue.
- The comparison uses the declared text before escaping, which is the right side to compare. The reviewer checked all 1,132 declared texts: unescaping `sql_string(text)` gives back the text in every case.
- The tests are small, and each fails without the change it tests.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **Moved to #751: the tables Load results overwrites still get every column comment, every run.**
   - Where: `databricks/notebooks/10_load_results.py` near the end, the overwrite loop. It writes 14 grader tables with `mode("overwrite")` and `overwriteSchema` from pandas DataFrames that carry no column metadata, then calls `apply`.
   - Effect: those tables never hold their comments when `apply` runs, so it sends all of them: 214 statements, counted from `table_comments.declared`. At the issue's rate that is about 3 minutes a run.
   - Verified: read the loop, and its own note ("an overwrite drops them").
   - Fix, in #751: attach the declared comments as column metadata before the write, so the overwrite commits them.
   - Not done here: it needs real PySpark, which neither this sandbox nor CI has, and #741's contract doesn't cover it. The pull request's description says what remains.

### 🔵 Nits / suggestions (Minor)
2. **Fixed in `7a91918`.** `apply_all` printed "commented N tables" even when it sent nothing, so the job's log couldn't
   show whether skipping works on real Spark. The fake Spark in the tests encodes the same assumptions as the code.
   It now prints `checked N tables in <catalog>, sent M comment statements`, and a test checks both cases.
3. **Fixed in `7a91918`.** Reading a field's metadata sat outside the guarded part of `apply`, so a field with no
   `metadata` attribute raised out of the write. It now counts as no comment.
   - Verified: the new test `test_a_field_without_metadata_still_gets_its_comment` fails on `acbf5c1` and passes now.
4. **Fixed in `7a91918`.** `apply` built every statement once just to check the table is declared, which also added a
   traced span per table. It now checks the declaration directly.
5. **Added in `7a91918`.** No test had a comment with a quote already in place; 93 declared texts contain one.
   - The new test `test_a_comment_with_a_quote_already_in_place_is_not_sent_again` passes on `acbf5c1` and fails on the base.
   - It guards against comparing the escaped literal; it doesn't fix a bug.
6. **Fixed in `7a91918`.** Spec 034's `plan.md` still said `apply` runs every statement.
7. **Not taken.** Two `information_schema` queries could replace the 330 per-table round trips of the sweep. That is
   outside #741's contract; #751 or a later issue can take it.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | scan clean |
| Synthetic only, no PHI | ✅ | no data files |
| No organization claims; vendors cited | ✅ | |
| Test first | ✅ | the five tests of `acbf5c1` failed on the base (5 failed, 21 passed) before the fix; the no-metadata and log tests fail on `acbf5c1` |
| Python and R in parity | n/a | not labels, scoring, reliability or cost-effectiveness |
| Spec for big changes | n/a | a fix with tests; spec 034's plan is updated |
| Configuration | ✅ | no setting changes; dev changes at the next Load results |
| Idempotent writes | ✅ | comment statements only; no data write changes |
| Commits | ✅ | imperative subjects, bodies say why, co-author trailers |
| Telemetry | ✅ | `statements` and `apply` keep `@traced`; `_table_comment` is private |
| Secrets register, alerts, seeds, paths, prices, deck figures | n/a | |

## Test Coverage
- **`tests/test_table_comments.py`:** 28 passed on `7a91918`.
- **The callers and the rules:** `test_delta`, `test_digests`, `test_telemetry_calls`, `test_data_contracts`, `test_data_products`, `test_gold_names`, `test_bundle`, `test_sql_conventions`, `test_wording`, `test_no_org_references`, `test_bench_order` and `test_agent_docs`: 201 passed, 4 skipped.
- **The whole suite on `acbf5c1`, with the deploy job's packages (`[dev]`, no Databricks SDK):** 2,558 passed, 39 skipped, 6 failed.
  - The 6 are all in `test_agent_harness.py`. They fail the same way on unchanged `main` in this sandbox and pass in CI.
- **`ruff check` on both Python files:** clean.
- **Not tested here: real Spark.** That `StructField.metadata["comment"]` carries a Unity Catalog column's comment and that `catalog.getTable(...).description` gives the table's (the reviewer was about 85% and 75 to 80% confident from Spark's and Delta's code). The first Load results after the merge prints the count.

## Verdict
Approve with nits. Nothing must change before merge. It waits for the owner: merging runs the deploy, which starts
Load results on the Free Edition workspace (AGENTS.md rule 6). That workspace refuses new runs at the moment (#742).
