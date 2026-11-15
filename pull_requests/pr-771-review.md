---
pr: 771
branch: docs/770-000-kaggle-objects-and-links
title: "000 DOCS19: kaggle/README lists every Kaggle object with its visibility and competition link"
author: jcbowyer
reviewed_at: 2026-11-15
reviewer: coordinator verification of each row against the objects' Kaggle metadata, read the same day
verdict: approve
---

# PR Review: 000 DOCS19: kaggle/README lists every Kaggle object with its visibility and competition link (#770)

## Summary
The README's table of Kaggle objects listed the PerioBench objects only, and nothing anywhere said which notebook is
linked to which competition, a setting Kaggle's API cannot carry. This adds the missing public objects and the private
run families, a visibility and competition-link column, and how a link is set by hand. Docs only; no Kaggle object
changes. Approve.

## Scope of Change
- Files changed: 1 (`kaggle/README.md`), plus this review
- Areas touched: docs
- Range reviewed: `origin/main..HEAD`

## CI Status
| Check | Status |
|---|---|
| all | read on the head commit before merging |

## Secrets, PHI and Claims Scan
Secrets: none (the token is never named, only the CLI version). PHI or real data: none. Organization claims: none;
Kaggle's product behaviour is described from its own client (the save-kernel request's fields in Kaggle CLI 2.2.5).

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
1. The three public datasets each score 0.94 for usability, one item short of the 10 the rules aim at. The API does not
   say which item; the dataset page's usability breakdown does. Worth a look by the owner; not changed here.
2. The quickstart's link to Gemma 4 Developer Agent is a recommendation recorded here; if the owner picks the Paper
   Track instead, the row changes in one cell.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets, no PHI, no org claims | yes | |
| Test first | n/a | docs only |
| Every number from a run or a source | yes | visibility and sources read from Kaggle; no numbers claimed |
| Commits | yes | Closes #770, trailer |
| Rule 6 (who merges) | yes | changes no Kaggle object, starts no run |

## Test Coverage
`test_wording`, `test_no_org_references`, `test_bench_order`, `test_kaggle_dataset_docs`, `test_tasks_quickstart`,
`test_quickstart`: 72 passed.

## Verdict
Approve. Merge when CI is green.
