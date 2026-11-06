---
pr: (see the PR for #625)
branch: feat/625-013-shap-by-outcome
title: "013 CHORE2: SHAP by outcome within each metric's population"
author: claude (agent session)
reviewed_at: 2026-11-06
reviewer: coordinator review against .claude/review-rubric.md
verdict: approve
---

# PR Review: 013 CHORE2: SHAP by outcome within each metric's population

## Summary
`classify_status.shap_drilldown_by_outcome` splits SHAP into right and wrong answers within each metric's
population: TP and FN for sensitivity, TN and FP for specificity, TP and FP for PPV, TN and FN for NPV. For each
group it gives `n`, `mean_shap` and `mean_abs_shap` per feature and for the bias. `train_eval` returns it one-vs-rest
per class. `tooth_loss_model.run` computes it for XGBoost on the held-out teeth, using exact TreeSHAP from
`pred_contribs`. `outputs_to_write` never writes it (ARTIFACT_OUTPUTS), so the results files, the gold load (which
reads `predictions` only) and the R twin (`stage_probabilities`) are unchanged. Scripts 40 and 51 log it as an MLflow
artifact through `track()`, from a temporary file. ADR 0002 gets a dated confirmation. Verdict: approve.

## Secrets, PHI and Claims Scan
Clean. The work is generic and draws only on this repo's own synthetic-data code. Nothing from any employer project
(names, tables, figures) is in the diff.

## Findings
None blocking.
- Additivity is tested on the means: in each group, the bias plus the features' mean SHAP equals the group's mean
  margin, to 1e-12 on a hand-built case and 1e-6 against `train_eval`'s own `shap_test`.
- The logistic model gets no SHAP; only XGBoost does, as the issue asks.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Test first | ✅ | 4 new tests reference the new function and key, so they failed before |
| Telemetry | ✅ | `shap_drilldown_by_outcome` and `_XGBoost.shap` are `@traced` |
| Python and R parity | ✅ | no label, scoring or written-output change; the R twin's input is unchanged |
| Decisions in ADRs | ✅ | ADR 0002 confirmation appended |

## Test Coverage
`tests/test_classify_status.py` and `tests/test_tooth_loss_model.py`: 47 passed. Full suite: 2239 passed. One local
error, in `test_digests.py`, because the `pipeline_doctor` package isn't installed in the sandbox; CI installs it.
`ruff check` is clean on the changed files.

## Verdict
approve: merge once CI is green.
