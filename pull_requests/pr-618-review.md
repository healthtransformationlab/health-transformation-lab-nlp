---
pr: (see the PR for #618)
branch: docs/618-025-first-clean-kaggle-run
title: "025 DOCS1: record PerioBench's first clean Kaggle run and its public task page"
author: claude (agent session)
reviewed_at: 2026-11-06
reviewer: coordinator review against .claude/review-rubric.md (docs only)
verdict: approve
---

# PR Review: 025 DOCS1: record PerioBench's first clean Kaggle run and its public task page

## Summary
Docs only. `docs/kaggle_benchmarks.md` records the first clean Kaggle Benchmarks run: workflow run 42173351209, task
version 3. All four models' runs were Completed on 223 notes with 0 errored. The doc also gives the public task page
(published by workflow run 42179437319, `Public: True` per `kaggle b t status`) and keeps the two earlier days as
history. Verdict: approve.

## Secrets, PHI and Claims Scan
Clean. Every score is labelled as agreement with the synthetic answer key, not accuracy on real patients. The model
slugs are Kaggle's proxy names, and the scores come from Kaggle's own run files (`kaggle b t download perio-bench`).
The self-judging caveat (the judge is `google/gemini-3.8-flash`) is stated.

## Findings
None blocking. Figures checked against the downloaded run files: each value in the table is the run's
`results[0].dictResult` rounded to 3 places.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Simulated is labelled | ✅ | real runs, labelled synthetic and answer key |
| Words, benchmark order, org names | ✅ | those tests pass (37) |

## Verdict
approve: merge once CI is green.
