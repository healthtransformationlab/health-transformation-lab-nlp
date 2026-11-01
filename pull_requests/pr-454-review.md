---
pr: 454
branch: fix/452-028-snapshot-root
title: "Put snapshot files at the archive root, like the competition's; compare commit-named graphs"
author: jcbowyer
reviewed_at: 2026-11-01
reviewer: coordinator verification (small fix driven by the competition check's own output)
verdict: approve
---

# PR Review: Put snapshot files at the archive root, like the competition's

## Summary
The competition check showed the competition's snapshots have their files and `.git` at the archive root, and ours
didn't. This PR changes `task_graph.snapshot` to match, and checks the result with the same layout function the check
applies to the competition's own snapshot.

It also lets the check compare graphs and embeddings using the commit-named copies, the only ones the competition
lists. Approve.

## Scope of Change
- Files changed: 6
  - `task_graph.py`, `competition_check.py`;
  - their tests;
  - spec 028 `tasks.md`;
  - this review.
- Areas touched: python, specs.

## Secrets, PHI and Claims Scan
Clean.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important)
None.
### 🔵 Nits (Minor)
- The graph fallback picks the smallest commit-named pair, not necessarily the same task as the downloaded snapshot.
  That's enough for a format comparison, which is all the check does.

## Test Coverage
- New tests:
  - the root layout, checked with `snapshot_layout`;
  - the commit-named fallback (smallest pair, same stem).
- Updated tests: the extraction paths (no `workspace/` folder), and the comparison line now expects `MATCHES`.
- The full suite passed: 1526 passed, 15 skipped. Ruff is clean.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets / PHI / org name | ✅ | |
| Test first | ✅ | |
| Spec updated | ✅ | `tasks.md` T008 |
| Commits | ✅ | `Closes #452` |

## Verdict
Approve. After the merge, re-run the competition check to confirm `MATCHES snapshot root` and to compare graphs and
embeddings.
