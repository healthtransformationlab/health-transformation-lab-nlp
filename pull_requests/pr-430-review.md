---
pr: 430
branch: feat/200-023-per-class-metrics
title: "023 US3: per-class sensitivity, specificity, AUC and Brier score, the same in R"
author: jcbowyer
reviewed_at: 2026-11-01
reviewer: coordinator verification against the rubric (no reviewer subagent was available in this session)
verdict: approve-with-nits
---

# PR Review: 023 US3: per-class sensitivity, specificity, AUC and Brier score, the same in R

## Summary
This adds `classify_status.class_metrics`, the per-class one-vs-rest sensitivity, specificity, AUC and Brier score
with a mean row over the classes present, and its base-R twin `r/R/13_spec023.R`. A spec 023 block in
`r/tests/test_parity.R` checks the two to 1e-9 on the committed held-out predictions and on seeded cases with ties
and a missing class. The parity inputs come from `44_medical_features.py --metrics-only`, which needs no xgboost, so
CI's `r-parity` job (which installs no `ml` extra) can produce them. The tests were written first, the R block passes
locally (max gap 1.11e-16), and the full Python suite is green. The PR is stacked on #428 and merges after it.
Approve with nits.

## Scope of Change
- Files changed: 13 (+419 / -59 including the regenerated CSVs; about +190 / -20 without them)
- Areas touched: python, r, docs, specs, data
- Commits:
  - 958c76b 023 US3: failing tests for per-class sensitivity, specificity, AUC and Brier
  - a7b6bec 023 US3: per-class sensitivity, specificity, AUC and Brier score, the same in R
- Range reviewed: `dd8502e..a7b6bec`. The PR targets main, so GitHub also shows #428's commits beneath it.

## CI Status
| Check | Status |
|---|---|
| python | pending at review time; local full suite 1304 passed, 15 skipped |
| r-parity | pending; needed (r/ and the parity pipeline changed). Spec 023 block run locally with R 4.3.3: 25 rows, max \|R - Python\| = 1.11e-16 |
| postgres, bundle | pending; untouched areas |

## Secrets, PHI and Claims Scan
- Secrets: clean (diff grep for token, secret, password and key patterns: nothing).
- PHI / real data: clean. The cases table is seeded random votes; the predictions come from the synthetic study.
- Organization claims: clean.

## Strengths
- The hand-worked tests cover each edge case the spec names: a perfect model, a constant model, a class missing from
  test (missing, not zero; means over the 2 classes present), tied scores (0.875 worked by hand, and agreement with
  scikit-learn on rounded scores) and the Brier definition.
- Both sides use the same tie rules: numpy's `argmax` and R's `max.col(ties.method = "first")` both pick the first
  class, and pandas' `rank(method="average")` matches R's default `rank`. The seeded cases contain ties, and parity
  holds on them.
- A test checks that the committed comparison equals `class_metrics` recomputed from the committed predictions. A
  stale results file would fail it.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
- `tests/test_class_metrics.py::test_committed_results_match_class_metrics_on_the_committed_predictions` compares
  to 1e-6, not 1e-9. That is because the committed metrics were computed from xgboost's float32 probabilities in
  memory, while the predictions CSV holds them to 10 significant digits. Verified: the R parity block, which reads
  the same CSV on both sides, agrees to 1.11e-16.
- The whole of `make_parity_inputs.sh` was not run locally. It stopped at `16_cost_effectiveness.py`, which needs
  matplotlib (not installed here; CI installs it). The unrelated files it had rewritten were restored before the
  commit. CI's `r-parity` job is the check of record.
- `class_metrics` returns `classes_averaged` as a float column (NaN on the class rows). Integer-valued, harmless.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | Scan clean |
| Synthetic only, no PHI | ✅ | |
| No organization claims; vendors cited | ✅ | |
| Test first | ✅ | Failing-test commit 958c76b precedes the code |
| Python and R in parity | ✅ | `13_spec023.R` + test_parity.R block; inputs in `make_parity_inputs.sh` |
| Simulated is labelled simulated | ✅ | `synthetic_*` files; SYNTHETIC in the docs |
| Seeds fixed | ✅ | Cases seeded (`default_rng(23)`); comparison seed 0 |
| Paths | ✅ | `DATASETS_DIR` |
| Spec for big changes | ✅ | spec 023; T009–T011 ticked |
| Telemetry | ✅ | `class_metrics` is `@traced` |
| Words rule | ✅ | `test_wording.py` passes |
| Gold naming, configuration, secrets register, alerts, writes | n/a | None touched |

## Test Coverage
New `tests/test_class_metrics.py` (6 tests, no xgboost needed). `tests/test_classify_feature_sets.py` is updated for
the mean rows and the Brier column. Ran locally: full suite 1304 passed and 15 skipped; `ruff check` clean; the R
spec 023 parity block passes.

## Verdict
Approve with nits; merge after #428.
