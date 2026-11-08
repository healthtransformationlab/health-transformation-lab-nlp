---
pr: 634
branch: docs/633-029-tooth-loss-results-refresh
title: "029 DOCS1: refresh the synthetic tooth-loss results after the tooth-table fixes"
author: jcbowyer
reviewed_at: 2026-11-08
reviewer: coordinator verification (docs-only change)
verdict: approve
---

# PR Review: refresh the synthetic tooth-loss results

## Summary
Docs-only: a new results block in `docs/tooth_loss.md` from a fresh run of the model script after #632, with the
earlier spec 037 table kept as the record and marked as pre-#631. Every figure in the new table was read from
`data/results/synthetic_tooth_loss_scores.csv` of that run (seed 42, shared predictors, fixed 0.5 threshold; AUC
intervals from its bootstrap columns; counts from `tooth_count`, `patient_count` and `outcome_rate`). The text says
why the numbers moved and labels everything SYNTHETIC. Approve.

## Scope of Change
- Files changed: 1 (+30 / -1)
- Areas touched: docs

## Checks
| Check | Result |
|---|---|
| Figures match the run output | yes, re-read from the scores CSV |
| Synthetic labelled; no organization claims; wording rules | `test_wording`, `test_no_org_references`, `test_bench_order` pass |
| Earlier results kept as the record | yes |
| Compute | local CPU, 11 minutes; nothing on Databricks or Kaggle |
| Commit | imperative, body says why, co-author trailer |

## Blocking
None. Mergeable by the agent when CI is green (AGENTS.md rule 6).
