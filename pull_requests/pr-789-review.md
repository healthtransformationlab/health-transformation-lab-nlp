---
pr: 789
branch: fix/785-credentials-table-test
title: "000 BUG8: read AGENTS.md's credentials table whether or not it is indented"
author: jcbowyer (agent session)
reviewed_at: 2026-11-15
reviewer: an independent read-only reviewer subagent (given the diff, the rubric, AGENTS.md and CLAUDE.md, not the author's conclusions; Superpowers isn't installed in this session) + coordinator verification
verdict: approve-with-nits
---

# PR Review: 000 BUG8: read AGENTS.md's credentials table whether or not it is indented

## Summary
`test_every_credential_in_agents_md_is_in_the_register` had checked nothing since `8cadc13` indented AGENTS.md's
credentials table: its pattern matched only the header, and the test passed. This pull request adds a reader that
finds every row, indented or not, and a check that names rows with no register entry.

The reviewer confirmed it now catches what it should:
- With any one of the 9 register entries deleted, the test fails and names that row. On `main` it passed.
- The new synthetic test fails with the old reader swapped in.

There are no critical or important findings. The minor ones that matter are fixed in the second commit. Approve with
nits.

## Scope of Change
- Files changed: 2: `python/tests/test_operations_rules.py` and this review
- Areas touched: python (tests only)
- Commits:
  - `6a581f3` Read AGENTS.md's credentials table whether or not it is indented
  - the review fixes, and this file
- Range reviewed: `69ff005..6a581f3` by the reviewer; the fixes by the coordinator

## CI Status
| Check | Status |
|---|---|
| `check`, `changes`, `postgres`, `bundle`, `azure-infra` | pass on `6a581f3` |
| `python`, `python-databricks-runtime` | running on `6a581f3` when this was written |
| `r-parity` | skipped (no R-relevant change) |
| the fix commit and this file | CI runs again on push; the head must be green before merge |

## Secrets, PHI and Claims Scan
- **Secrets:** clean.
- **PHI / real data:** clean.
- **Organization claims:** clean.

## Strengths
- Small and well explained.
- **No more silent passes:** `assert rows and "Credential" not in rows` keeps it from passing without reading a row again.
- **Clear failures:** the message names the missing rows.
- **The `gh` login row matches** without renaming anything, by removing backticks, and the docstring and the commit say so.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
1. **Fixed:** the reader stopped at the first line not starting with `|`.
   - A row without its leading pipe, or a stray line inside the table, silently dropped every row after it.
   - The reviewer showed it: a stray line before the second row returned only the first.
   - Now the reader reads to the first blank line and fails, naming the line, on anything in between that isn't a row. A test checks it.
2. **Fixed:** the synthetic test covered only an indented table, though the issue says "indented or not". It now checks an unindented one too.
3. **Fixed:** a renamed header raised a bare `ValueError`. It now fails with a message naming the missing header.
4. **Not taken:** `split("|")` splits on an escaped `\|`.
   - That would cause a loud false failure, not a silent pass.
   - The table has no `\|` today.
5. **Not taken:** names match by substring, as before.
   - Removing backticks can't hide a missing entry beyond what substring matching already allows.
   - `startswith` would be stricter, and is a choice for later.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | |
| Synthetic only, no PHI | ✅ | |
| No organization claims; vendors cited | ✅ | |
| Test first | ✅ | both new tests failed before the helpers existed; the synthetic one fails with the old reader |
| Configuration | ✅ | no setting changes |
| Commits | ✅ | imperative subjects, bodies say why, co-author trailers |
| Issue contract | ✅ | #785 has a dated line naming `_credential_rows` and `_unregistered` |
| Python and R parity, idempotent writes, alerts, seeds, paths, prices, deck figures, spec | n/a | |

## Test Coverage
- **`tests/test_operations_rules.py`:** 11 passed after the fixes.
- **The reviewer's probes:**
  - Each register entry deleted in turn: each one is flagged.
  - Also handled correctly: CRLF, a tab indent, an alignment rule (`|:---|`), a table at the end of the file, an empty first cell.
  - Combined with pull request 790: no conflict, and the whole suite passes on an indexed export.
- **`ruff check`:** clean. It also removes `main`'s older FURB167 warning in this file.

## Verdict
Approve with nits. Nothing must change before merge. Merging runs the deploy (`python/` isn't in its path filter),
and the owner said "merge" on 2026-11-15.
