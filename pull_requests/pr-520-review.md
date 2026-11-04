---
pr: 520
branch: docs/518-days-suffix
title: "000 DOCS5: AGENTS.md lists _days for a duration in whole days"
author: jcbowyer
reviewed_at: 2026-11-04
reviewer: coordinator (two-file change; no subagent)
verdict: approve
---

# PR Review: 000 DOCS5: AGENTS.md lists _days for a duration in whole days

## Summary
Adds a `_days` suffix (a duration in whole days, `bigint`) to AGENTS.md's "SQL and data names" table and to the gold
column check in `python/tests/test_sql_conventions.py`, so `plan_to_missing_days` (silver, from #513) has a listed
suffix before it ever reaches gold. A new test keeps the table and the check's list identical. It works and is small.
Verdict: approve; it changes the repo's rules, so it waits for the owner's "merge" (AGENTS.md rule 6).

## Scope of Change
- Files changed: 2 (+20 / -1)
- Areas touched: docs (AGENTS.md) / python (tests)
- Commits: 3d479d7 000 DOCS5: AGENTS.md lists _days for a duration in whole days
- Range reviewed: `origin/main..3d479d7`

## CI Status
| Check | Status |
|---|---|
| all | pending at the time of writing; read on the PR before merge |

## Secrets, PHI and Claims Scan
Clean: no secrets, no data, no organization named.

## Strengths
- The new test parses the AGENTS.md table itself, so a suffix added to one list and not the other fails CI.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- `tests/test_sql_conventions.py`: the `TYPES` literal now wraps one entry onto its own line; harmless.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | |
| Synthetic only, no PHI | ✅ | no data |
| No organization claims | ✅ | |
| Test first | ✅ | the parity test failed with `_days` in AGENTS.md only, then passed |
| Python and R in parity | n/a | |
| Spec for big changes | n/a | a rules table entry, with its own issue |
| Commits | ✅ | |
| Changes these rules | ⚠️ | waits for the owner's "merge" (rule 6) |

## Test Coverage
`pytest -q tests/test_sql_conventions.py tests/test_wording.py tests/test_gold_model.py` (30 passed), `ruff check`
clean. The full suite runs in CI.

## Verdict
**Approve.** Merge when the owner says so and CI is green.
