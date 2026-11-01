---
pr: 424
branch: feat/132-004-medgemma-per-field
title: "004 AI2: MedGemma accuracy per field, in Python and R, logged to MLflow"
author: jcbowyer
reviewed_at: 2026-11-01
reviewer: superpowers requesting-code-review subagent + coordinator verification
verdict: approve-with-nits
---

# PR Review: 004 AI2: MedGemma accuracy per field, in Python and R, logged to MLflow

## Summary
Scores each committed MedGemma run per field (status, grade, extent) against #418's reference answers: n, correct,
accuracy and a 95% Wilson CI, written to `ladder/medgemma_field_accuracy.csv`, with a base R twin checked by the
parity test and MLflow metrics from the new script and from `11_ai_predict.py`. It works: the status row equals each
run's headline accuracy, and CI `r-parity` reports `medgemma per field: 2 runs x 3 fields, max |R - Python| =
0.00e+00` (and the same for the simulated run). It builds on #418 and must merge after it. Approve with nits.

## Scope of Change
- Files changed (this PR's own work, beyond #418): 10 (+300 / -1, excluding the two generated CSVs)
- Areas touched: python / r / docs / specs / data
- Commits (own): 59a0b6a Report MedGemma accuracy per field, in Python and R, logged to MLflow;
  1c2ea8f merge of the #130 branch, which also renames script 52 → 54
- Range reviewed: `54b2d92..83dda03` (#418's commits reviewed in `pr-418-review.md`)

## CI Status
| Check | Status |
|---|---|
| python | success |
| postgres | success |
| r-parity | success (section 9e ran: 0.00e+00 real and simulated) |
| bundle | success |
| check (PR conventions) | success |

## Secrets, PHI and Claims Scan
- Secrets: clean.
- PHI / real data: clean; the new CSVs hold run names, field names and numbers.
- Organization claims: clean. The docs label the table as synthetic notes against generator truth, "not evidence
  about either model on real records"; the simulated file is called out as placeholder.

## Strengths
- Clear, documented scoring rules, the same on both sides: status from the rung's answer (so it ties to the headline
  accuracy, asserted in a test), grade and extent only where they apply and only from gated answers.
- A partial (`--limit`) run is refused rather than scored on a subset, in Python and R.
- One `field_metrics` helper gives the MLflow names, used by both scripts and unit-tested without mlflow installed.
- Doc claims re-derived: the table matches the CSV; "4B called 26 of the 65 localized cases generalized (1.5
  called 6)" was checked with a crosstab of `llm_details_*` against the reference.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
- `python/health_transformation_lab_nlp/reference_answers.py` `field_accuracy`: grade and extent are scored
  regardless of whether the stage was right, so a correct grade on a wrong stage counts. Documented in the module,
  docs and spec; an owner choice, not a bug. A "given status correct" variant could be added later.
- The 52 → 54 rename was folded into a merge commit (1c2ea8f), so it doesn't show as its own commit. Verified that no
  `52_`/`51_` references remain outside `pull_requests/`.
- `python/scripts/11_ai_predict.py:122`: `ruff --fix` dropped a `noqa: E402` that ruff reports unused. Harmless,
  unrelated to the feature.
- `docs/medgemma.md` is also edited by open PR #417; expect a text conflict for whichever merges second.
- Locally `make_parity_inputs.sh` stopped at `16_cost_effectiveness.py` (no matplotlib in the container), after the
  new 53 and 54 steps had run and reproduced the committed CSVs byte for byte; CI installs matplotlib and ran it all.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | |
| Synthetic only, no PHI | ✅ | |
| No organization claims; vendors cited | ✅ | |
| Test first | ✅ | new tests in `test_reference_answers.py` seen failing before the code |
| Python and R in parity | ✅ | `r/R/17_spec004.R`, parity 9e, CI green at 0.00e+00 |
| Simulated is labelled simulated | ✅ | `simulated_medgemma_field_accuracy.csv`, `sim:` run names in MLflow, banner printed |
| Seeds fixed | ✅ | no sampling (Wilson CI, not bootstrap) |
| Paths | ✅ | `paths.DATASETS_DIR` |
| Spec for big changes | ✅ | spec 004 US6, FR-010, T022 |
| Commits | ✅ | imperative, body says why, trailer |
| Docs | ✅ | `docs/medgemma.md` table and scoring rules |
| Configuration | ✅ | no new settings; MLflow via the existing `tracking.track` |
| Idempotent writes | ✅ | CSV overwritten; MLflow runs are event logs |
| Telemetry | ✅ | `@traced` on `wilson_ci`, `field_accuracy`, `field_metrics` |
| Gold naming | n/a | no table added |

## Test Coverage
13 tests in `test_reference_answers.py` (7 new): per-field n/correct/accuracy, Wilson bounds and edges, the
fallback and not-applicable rules, refusal of partial runs, the committed table vs a fresh computation and vs the
headline accuracy, MLflow metric names, and both scripts using them. Local: `python -m pytest -q tests` 1260 passed,
15 skipped; `ruff check` clean. Not run locally: R (not installed; CI `r-parity` green), MLflow logging against a
real store (mlflow not installed here; tracking is a no-op), anything on Databricks or a GPU.

## Verdict
approve-with-nits. Merge after #418.
