---
pr: (see the PR for #624)
branch: fix/624-db-statements-quotes
title: "000 BUG5: split SQL on ; only outside quotes and comments"
author: claude (agent session)
reviewed_at: 2026-11-06
reviewer: coordinator review against .claude/review-rubric.md (small diff)
verdict: approve
---

# PR Review: 000 BUG5: split SQL on ; only outside quotes and comments

## Summary
`db._statements` is now a small scanner. It splits on `;` only outside single-quoted strings (with `''` escapes),
double-quoted identifiers and comments, and it drops `--` and `/* */` comments outside quotes. Five regression tests
cover a COMMENT holding `--` and `;`, a multi-line literal with a `--` line, escaped quotes, quoted identifiers,
comments holding `;`, and blank statements. Four failed before the fix. Verdict: approve.

## Findings
None blocking. Checked against every DDL file `create_schema` runs: the statement counts are unchanged (39, 28, 102
and 3). The only text differences are comments the old code left in, at the top of the index file and as trailing
notes in `dental_extension.sql`. Postgres ignored them, so the executed SQL is equivalent.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Test first | ✅ | `tests/test_db_statements.py` failed 4 of 5 first |
| No secrets, PHI or org claims | ✅ | |

## Verdict
approve: merge once CI is green.
