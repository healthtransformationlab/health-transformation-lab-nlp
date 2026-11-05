---
pr: 592
branch: fix/591-035-deploy-numpy-user-site
title: "035 BUG1: the shipped-code import test finds numpy in the deploy job"
author: jcbowyer
reviewed_at: 2026-11-05
reviewer: coordinator review against the rubric (one-file test fix; no subagent dispatched)
verdict: approve
---

# PR Review: 035 BUG1: the shipped-code import test finds numpy in the deploy job

## Summary
Every dev deploy since #578 failed on one test. The test starts the bundle's interpreter with `-I`, which drops the
user site-packages, and that is where the deploy job's pip installs numpy. The test now adds numpy's directory back,
and asserts that no repository module was imported. That keeps the isolation the test exists for, and checks it more
strictly than before. The failure was reproduced (`-I -S`) and the fix shown to pass. The file's 26 tests pass.
Verdict: approve.

## Scope of Change
- Files changed: 2: `python/tests/test_gemma_agent.py` (+8 / -1) and this review file
- Areas touched: python (tests)
- Commits: 7d012ae 035 BUG1: the shipped-code import test finds numpy in the deploy job
- Range reviewed: `400d847..7d012ae`

## CI Status
| Check | Status |
|---|---|
| all | read on the PR before merge; the deploy job itself runs only after the merge |

## Secrets, PHI and Claims Scan
Clean: no secrets, no data, no organization named.

## Strengths
- The cause is traced to the deploy log line "Defaulting to user installation".
- The new assertion makes the isolation check stricter than before.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- `ruff check` reports three pre-existing warnings in this file (unused `io`, `subprocess.run` without `check`, an
  implicit concatenation). CI doesn't run ruff, and all three were there before this change. Left as they are.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | |
| Synthetic only, no PHI | ✅ | |
| No organization claims | ✅ | |
| Test first | ✅ | the failure was reproduced before the change |
| Python and R in parity | n/a | |
| Spec for big changes | n/a | a one-file test fix with its issue |
| Commits | ✅ | |

## Test Coverage
- `pytest -q tests/test_gemma_agent.py`: 26 passed.
- Reproduction with `-I -S`: the old command fails (`No module named 'numpy'`) and the new one passes.

## Verdict
**Approve.** Merge when CI is green, then confirm the next dev deploy passes.
