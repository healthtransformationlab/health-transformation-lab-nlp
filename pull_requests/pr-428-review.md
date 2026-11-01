---
pr: 428
branch: feat/199-023-classifier-feature-sets
title: "023 US2: the status classifier runs dental-only, dental+medical and medical-only"
author: jcbowyer
reviewed_at: 2026-11-01
reviewer: coordinator verification against the rubric (no reviewer subagent was available in this session)
verdict: approve-with-nits
---

# PR Review: 023 US2: the status classifier runs dental-only, dental+medical and medical-only

## Summary
This adds spec 023 US2. Patel et al. 2026's 4-class scheme and four named feature sets (`dental`, `dental_no_asa`,
`dental_medical`, `medical`) go into `classify_status.py`, along with a person-level frame joined to US1's synthetic
medical record, a 70/30 split stratified by class and kept by person, and a comparison that trains each set on the
same split. `scripts/44_medical_features.py` writes the per-class metrics, held-out probabilities and SHAP
importances under `data/datasets/classify_status/`. The docs show the run labelled SYNTHETIC, with the paper's
Table 2 averages cited in a separate table. The tests were written first and pass; the full suite is green locally.
No finding blocks it: approve with nits.

## Scope of Change
- Files changed: 10 (+about 380 / -5 excluding the generated CSVs; the three CSVs add about 1,440 lines)
- Areas touched: python, docs, specs, data
- Commits:
  - e5316a3 023 US2: failing tests for the four scheme, feature sets and stratified split
  - c4221ec 023 US2: run the status classifier on dental, dental+medical and medical features
  - 2eca0bf Merge remote-tracking branch 'origin/main' into feat/199-023-classifier-feature-sets
- Range reviewed: `a59b70b..2eca0bf` (merge base with main to head)

## CI Status
| Check | Status |
|---|---|
| python | pending at review time; local full suite 1279 passed, 15 skipped |
| r-parity | not affected by this PR (no scoring function changes; US3 adds `class_metrics` and its R twin) |
| postgres, bundle | pending; untouched areas |

## Secrets, PHI and Claims Scan
- Secrets: clean (grep of the diff for token, secret, password, key patterns: nothing).
- PHI / real data: clean. All rows come from the seeded generator; the paper's patient data is not used, only its
  published Table 2 averages, cited.
- Organization claims: clean. The paper is cited by its authors and journal; no organization's plan or finding is
  described.

## Strengths
- Test first: the scheme, exact feature lists, split shares and grouping, a clear failure on a too-small class, and
  the comparison's row shape and reproducibility are pinned before the code (commit e5316a3).
- The split guarantee in acceptance scenario 2 (within one visit per class of proportional, no person in both) holds
  by construction with one row per person, and it is tested on the real study frame.
- Honest outputs: `is_synthetic` on every row, SYNTHETIC in the script output and docs, and the paper's figures in
  their own table, marked "for reference only".
- The existing 5level/3level path, its 80/20 split and its committed outputs are untouched.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
- `classify_status.py` `_one_vs_rest` repeats the per-class metric code already in `train_eval`. Verified by reading
  both. US3 (#200) replaces it with the public `class_metrics` (with the Brier score and an R twin), so leave it here.
- `tests/test_classify_feature_sets.py::test_comparison_rows_one_per_feature_set_and_class` is skipped in CI, which
  doesn't install the `ml` extra (verified in `.github/workflows/ci.yml`: `pip install -e "./python[dev]"`). It ran
  locally with xgboost 3.4.1. The split and feature tests run without xgboost.
- The record's periodontal status comes from each person's latest visit (US1), while the label here comes from
  their latest *charted* visit. When a person's last visit is uncharted, the two visits differ. Status never goes
  back from periodontitis, so the effect is small. Worth a sentence in the walkthrough if it ever matters.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | Scan clean |
| Synthetic only, no PHI | ✅ | Generator data only |
| No organization claims; vendors cited | ✅ | Paper cited (references item 53) |
| Test first | ✅ | Failing-test commit precedes the code |
| Python and R in parity | ✅ | No scoring change here; US3 carries `class_metrics` and its R twin |
| Simulated is labelled simulated | ✅ | `synthetic_*` file names, `is_synthetic`, SYNTHETIC in the docs |
| Seeds fixed | ✅ | `split_stratified(seed=0)`, script `--seed 0` default |
| Paths | ✅ | `DATASETS_DIR` |
| Spec for big changes | ✅ | spec 023; tasks T005–T008 ticked |
| Words rule | ✅ | No avoided phrases (`test_wording.py` passes) |
| Telemetry | ✅ | New public functions are `@traced` (`test_telemetry_calls.py` passes) |
| Gold naming | n/a | Nothing is loaded to gold (FR-009 applies only if it is) |
| Configuration, secrets register, alerts, idempotent writes | n/a | No settings, credentials, alerts or table writes |

## Test Coverage
New `tests/test_classify_feature_sets.py` (9 tests). Ran locally: `python -m pytest -q tests`, 1279 passed and 15
skipped; `ruff check` on the changed Python files is clean; `scripts/44_medical_features.py` finishes in about 3
minutes (SC-003 asks for under 10).

## Verdict
Approve with nits. Nothing has to change before merge; US3 (#200) removes the duplicated metric code.
