---
pr: 494
branch: docs/493-000-method-choice
title: "000 DOCS3: explain how and why each method was chosen, linked from the study design"
author: jcbowyer
reviewed_at: 2026-11-03
reviewer: coordinator (docs only; checked against .claude/review-rubric.md and AGENTS.md)
verdict: approve
---

# PR Review: how and why each method was chosen

## Summary
New `docs/method_choice.md`, linked from the study design in `docs/process.md`.

## Checks
- **Matches the code:** each method named is the one the code uses:
  - `phenotype.py` and `labels.py` (rules);
  - `reliability.py` (kappa);
  - `prevalence.wilson_ci` (Wilson intervals);
  - `nhanes.py` (Taylor-linearized survey weighting);
  - `reliability_cal.py` (the ICC);
  - `tooth_loss_model.py` (logistic regression with median imputation and missing indicators, alongside XGBoost);
  - `classify_status.py` (XGBoost with TreeSHAP);
  - `prediction.py` (logistic regression with permutation importance).
- **No results claimed:** the page says every number is synthetic and explains the choices only.
- **Wording:** no "diagnose"; it says "finding gum disease in the record (phenotyping)". Organisation-name and
  benchmark-order tests pass.
- **Links:** every link resolves.

## Findings
- **Minor (no change):** the textbook rules (Mann-Whitney, Fisher's exact, 10 events per predictor) are standard and
  stated as rules of thumb without a citation, like the Landis and Koch note in `statistics.md`.

## Verdict
Approve.
