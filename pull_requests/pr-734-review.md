---
pr: 734
branch: ci/715-parity-skip-data-tasks
title: "000 AI2: the task sets are not an R parity input"
author: jcbowyer
reviewed_at: 2026-11-15
reviewer: coordinator
verdict: approve
---

# PR Review: 000 AI2: the task sets are not an R parity input

## Summary

The owner decided that `data/tasks/` is not an R parity input (#715, November 15, 2026). `parity_needed.py` now leaves
it out of the always-run inputs, so a pull request touching only the task sets no longer starts `r-parity`. A test
covers it, and ADR 0005 records the decision. Closes #715. Approve.

## Scope of Change

- Files changed: 5: `.github/scripts/parity_needed.py`, `python/tests/test_parity_needed.py`, a new
  `docs/adr/0005-task-sets-not-an-r-parity-input.md`, `docs/adr/README.md`, and this review
- Areas touched: CI's choice of jobs. No package code, data, metric or label rule.

## CI Status

To be read on the PR's latest commit before merging. `r-parity` runs on this PR, because the PR edits
`parity_needed.py`.

## Findings

None blocking, none to fix.

- **Correctness.** Only `data/tasks/` is excluded. `data/datasets/` and `data/labels/`, which `r/tests/test_parity.R`
  reads, still start the job, and the test checks both.
- **Coverage stays.** Pushes to `main`, manual runs and the Monday schedule always run parity, whatever changed, so a
  wrong exclusion would still be caught there.
- **One rule for both callers.** `needed()` and the printed list now share one `_reaches` check, so the script's
  output can't disagree with the function the test exercises.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| Issue and branch | Yes | `ci/715-...`; `Closes #715` |
| Decisions in ADRs | Yes | ADR 0005, listed in the index |
| Test first | Yes | The new test failed before the change |
| Settings change by pull request | Yes | CI's choice of jobs only; no environment changes |
| Python and R parity | Unchanged | R still runs for every input it reads |

## Verdict

Approve, and merge when every check is green on the latest commit.
