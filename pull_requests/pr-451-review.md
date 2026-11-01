---
pr: 451
branch: fix/450-028-kaggle-needs-six
title: "Install six for the competition check; kaggle 2.2.5 imports it undeclared"
author: jcbowyer
reviewed_at: 2026-11-01
reviewer: coordinator verification (one-line CI fix)
verdict: approve
---

# PR Review: Install six for the competition check

## Summary
The competition check workflow, from #449, failed on its first run at `import six`: `kaggle==2.2.5` uses `six`
without declaring it. This PR adds `six` to the workflow's install line, with a test that keeps it there. Approve.

## Scope of Change
- Files changed: 3 (the workflow, `test_competition_check.py`, this review). Area: ci.

## Secrets, PHI and Claims Scan
Clean. No credential changes.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important)
None.
### 🔵 Nits (Minor)
None.

## Test Coverage
- Reproduced in a clean venv: the import fails without `six` and succeeds with it.
- The new test failed before the fix and passes after.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | |
| Test first | ✅ | |
| Configuration | ✅ | No settings change |
| Commits | ✅ | `Closes #450` |

## Verdict
Approve. Merge once CI is green, then re-run the competition check.
