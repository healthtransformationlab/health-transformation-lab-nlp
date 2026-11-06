---
pr: (see the PR for #628)
branch: feat/628-029-gauges-shap-both
title: "029 CHORE3: tooth-loss gauges, and SHAP by outcome for both models"
author: claude (agent session)
reviewed_at: 2026-11-06
reviewer: coordinator review against .claude/review-rubric.md
verdict: approve
---

# PR Review: 029 CHORE3: tooth-loss gauges, and SHAP by outcome for both models

## Summary
- **`model_gauges.py`:** turns a tooth-loss run's `scores` into one gauge per measure, as a question with an answer:
  AUC, sensitivity, PPV, LR+, LR−, specificity and NPV.
  - The needle is XGBoost; logistic regression is the reference value, with the difference in points.
  - Each gauge has a "per 100" reading (caught and missed per 100 periodontal losses, correct and false per 100
    flags) and, for PPV, the random-selection baseline (the outcome rate).
  - LR+ and LR− are derived from sensitivity and specificity for display only; the scoring is unchanged.
  - Bands only where a published convention exists: AUC after Hosmer, Lemeshow & Sturdivant 2013, likelihood ratios
    after Jaeschke, Guyatt & Sackett, JAMA 1994. Sensitivity, specificity, PPV and NPV say "target not set".
  - Script 51 writes the page beside its results and logs it to MLflow.
- **Logistic regression gets exact linear SHAP** (`_Logistic.shap`): coefficient times standardised input, with the
  intercept as the bias. `run()`'s artifact-only `shap_drilldown` covers both models.

Verdict: approve.

## Secrets, PHI and Claims Scan
Clean. Every number comes from this repo's synthetic tooth-loss run, and the page is labelled SYNTHETIC. Nothing from
any employer project (names, tables, figures) is in the diff: the gauge design follows standard evaluation
practice, and the bands cite public sources.

## Findings
None blocking.
- A real bug caught while checking the rendered page: the likelihood-ratio dial's zones didn't match `lr_band`'s
  cut-offs (an LR+ of 6.7 read "higher" but drew in the intermediate zone). The zones are now placed at log10(2)/2
  and log10(5)/2, and `test_every_needle_lands_in_the_zone_of_its_own_band` checks it (the old zones fail it).
- The logistic SHAP test checks each row adds up to the model's log-odds, to 1e-8.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Test first | ✅ | `tests/test_model_gauges.py` failed to import first; the SHAP tests reference the new method |
| Simulated is labelled | ✅ | SYNTHETIC banner and footnote on the page |
| Python and R parity | ✅ | no scored metric changes; LR+ and LR− are display only |
| Telemetry | ✅ | public functions and methods `@traced` |

## Test Coverage
The gauge, tooth-loss, classifier, telemetry, wording and organization-name tests: 112 passed and 1 skipped. Script
51 ran end to end on a 1,500-patient synthetic extract. The page rendered at 1100 px and at 390 px with no horizontal
scroll. `ruff check` is clean.

## Verdict
approve: merge once CI is green, after #627.
