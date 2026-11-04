---
pr: 538
branch: feat/534-034-uc-comments
title: "034 US2: every Unity Catalog table the jobs write gets its table and column comments"
author: johncbowyer
reviewed_at: 2026-11-04
reviewer: coordinator review and verification
verdict: approve-with-nits
---

# PR Review: 034 US2: every Unity Catalog table the jobs write gets its table and column comments

## Summary
After every write, table and column comments go on from the existing declarations: `gold_model.py` for gold, the
Open Dental silver model for silver and bronze, and a table comment for the OMOP tables and `load_log`. Load
results sweeps every declared table after each deploy, and the SQL judge sets its own table comment. A comment
never fails a write. Unit-tested with a fake Spark; CI is green. Not yet run on Databricks. Stacked on #537.
Approve with nits. It waits for the owner's "merge", because it edits AGENTS.md.

## Scope of Change
- Areas touched: python (new `table_comments.py`, `delta.py`), databricks notebooks 01, 02, 07, 10, 11, 12,
  AGENTS.md, spec 034
- Commits: 5fb42bc (US2), b4cbbce (AGENTS.md, spec tasks)
- Range reviewed: `feat/533-034-kaggle-usability..b4cbbce`

## CI Status
| Check | Status |
|---|---|
| python, python-databricks-runtime | success |
| postgres, bundle, azure-infra, check | success |
| r-parity | skipped |

## Secrets, PHI and Claims Scan
Clean. The comments are the repo's own table and column descriptions. SQL string literals are escaped, and table
names are checked against `catalog.schema.table` before use.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
1. Not exercised on Databricks. The statements (`COMMENT ON TABLE`, `ALTER TABLE ... ALTER COLUMN ... COMMENT`)
   are standard Databricks SQL, and a failure only warns, but the first real run is the next deploy's Load
   results. Its output should be read once: "commented N tables", and any warnings.
2. The OMOP tables (`person`, `visit_occurrence`, `measurement`, `note`) get only a table comment. Their columns
   are OMOP CDM's own and could be described later from the CDM's documentation.
3. Each write runs one statement per column, so a few dozen small SQL calls per table. That's cheap on these
   tables, but worth knowing on serverless.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets / PHI / claims | ✅ | |
| Test first | ✅ | `test_table_comments.py` seen failing first |
| Telemetry | ✅ | public functions `@traced` |
| Paths | ✅ | `paths.REPO_ROOT` |
| Configuration | ✅ | no new setting; failures warn |
| Changes these rules | ⚠️ | waits for the owner's "merge" (rule 6) |

## Test Coverage
`tests/test_table_comments.py` (new, 21 tests); `tests/test_delta.py` still passes. CI's `python` job ran the
full suite green.

## Verdict
approve-with-nits.
