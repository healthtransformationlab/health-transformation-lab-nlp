---
pr: 438
branch: chore/437-029-adults-only-default
title: "029 CHORE1: the tooth-loss model includes adults only (18 and over) by default"
author: jcbowyer
reviewed_at: 2026-11-01
reviewer: coordinator (small chore; checked against .claude/review-rubric.md and AGENTS.md)
verdict: approve
---

# PR Review: the tooth-loss model includes adults only by default

## Summary
- The default minimum age moves from no cut-off to 18 (`ModelParams.min_age`, `--min-age`).
- No cut-off and 30 and over become the sensitivity analyses.
- The analysis plan (s. 3, the planned sensitivity list and the change log) and `docs/tooth_loss.md` say the same.

## Scope of Change
- Files changed: 6, including this review:
  - `tooth_loss_model.py`, `51_tooth_loss_model.py`, `test_tooth_loss_model.py`;
  - `specs/029-tooth-loss/analysis_plan.md`, `docs/tooth_loss.md`.

## Checks against the rubric
- **Test first:** the test was changed to expect 18 and failed against the old default before the code changed.
- **Spec:** analysis plan s. 3 is a pre-specified decision. The change is logged in the plan's change log with its
  reason, as TRIPOD+AI asks.
- **Results:** no committed synthetic result changes. Synthetic patients are 25 or older; 168,000 teeth are eligible
  with and without the cut-off (6,000 patients, seed 42).
- **Python/R parity:** not affected. The R twins cover the metrics and the stage rule, not eligibility, and their
  inputs don't change.
- **Synthetic only, no organisation or decision named:** yes.
- **Wording, benchmark order:** unaffected.

## Findings
- **Minor (no change):** a tooth whose age is unknown is dropped once a cut-off applies (`pd.to_numeric` coerces to
  NaN). No synthetic tooth lacks an age. On real data, the count of teeth dropped for a missing age should be reported
  with the run.

## Verdict
Approve.
