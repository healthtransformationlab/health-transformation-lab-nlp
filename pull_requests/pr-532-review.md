---
pr: 532
branch: docs/356-028-kaggle-dataset-url
title: "028 US5: record the published task set's Kaggle URL (T011)"
author: johncbowyer
reviewed_at: 2026-11-04
reviewer: coordinator review (docs only: one line in tasks.md)
verdict: approve
---

# PR Review: 028 US5: record the published task set's Kaggle URL (T011)

## Summary
Marks T011 done and records the dataset's URL, the run it came from and its contents. Every figure was checked:
the run's steps all succeeded, and the Kaggle API lists the dataset as public, CC BY 4.0, with 316 files
(113 snapshots, 100 graphs, 100 embeddings and three files at the root), 1.55 GB. Approve.

## Scope of Change
- Files changed: 1 (+1 / -1), plus this review
- Areas touched: specs
- Range reviewed: `origin/main..HEAD`

## Secrets, PHI and Claims Scan
Clean. The URL names the public Kaggle account the dataset was published from; no credential is in it.

## Findings
None.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | |
| No organization claims | ✅ | |
| Commits | ✅ | |
| Publishes outside the repo | n/a | records a publish already done; runs nothing |

## Test Coverage
`tests/test_wording.py`, `tests/test_no_org_references.py` passed locally.

## Verdict
approve.
