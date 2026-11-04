---
pr: 539
branch: fix/536-025-kbench-grouping
title: "025 BUG3: score the Kaggle task's macro F1 at the default grouping, run its tests in CI"
author: claude (agent session)
reviewed_at: 2026-11-04
reviewer: coordinator review against .claude/review-rubric.md (small diff, 4 files)
verdict: approve
---

# PR Review: 025 BUG3: score the Kaggle task's macro F1 at the default grouping, run its tests in CI

## Summary
`kbench.score_rows` now computes macro F1 at `labels.DEFAULT_GROUPING`, the same as `eval/score.py`, so a Kaggle
Benchmarks run reports the repo's metric. The eval-frame test sizes the review set from `review_key.csv`. CI now
installs the `kbench` extra, so `test_kbench.py` runs instead of being skipped. The skip is why the drift went
unseen. The doc's counts are corrected. A second commit adds `six` to the four Kaggle workflows that pinned kaggle 2.2.5 without it. Publish datasets failed on exactly that (run 41780007824, `ModuleNotFoundError: No module named 'six'`). A new test checks every workflow that installs kaggle. The parity test failed before the fix (0.553 vs 0.597) and passes after.
Verdict: approve.

## Scope of Change
- Files changed: 9 (code fix, CI, four Kaggle workflows, one test, doc, this review)
- Areas touched: python, ci, workflows, docs
- Commits: the six fix (Kaggle workflows); 97601ce 025 BUG3: score the Kaggle task's macro F1 at the default grouping, run its tests in CI
- Range reviewed: `origin/main..97601ce`

## CI Status
| Check | Status |
|---|---|
| python (now with kbench) | see the PR; must be green before merge |

## Secrets, PHI and Claims Scan
Clean: no credentials, no real data and no organization claims.

## Strengths
- The fix reuses `labels.group_status` and `GROUPINGS` instead of copying the mapping.
- The CI change closes the gap that hid the bug.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- `kbench.py` hard-codes the default grouping. If a Kaggle leaderboard ever wants the three-group view, `score_rows` could take a `grouping` argument, as `eval/score.py` does. Not needed now.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Test first | ✅ | the existing parity test failed before the fix and passes after |
| Python and R in parity | ✅ | `eval/score.R` already groups; `kbench.py` has no R twin |
| Simulated is labelled | ✅ | dry run still prints `is_simulated: true` |
| Commits | ✅ | |

## Test Coverage
With the kbench extra: `tests/test_kbench.py` 15 passed. Full suite: 1964 passed and 31 skipped. `ruff check` is clean.

## Verdict
approve: merge once CI is green.
