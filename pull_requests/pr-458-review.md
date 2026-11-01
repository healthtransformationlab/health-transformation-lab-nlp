---
pr: 458
branch: feat/444-032-validation-options
title: "032 US5: how a model is validated (split unit, test share, CV tuning)"
author: jcbowyer
reviewed_at: 2026-11-01
reviewer: coordinator self-review against .claude/review-rubric.md and AGENTS.md
verdict: approve-with-nits
---

# PR Review: how a model is validated (split unit, test share, CV tuning)

## Summary
Spec 032 US5 turns three validation choices into settings for the tooth-loss model and the visit-level status
classifier. `split_unit`: `person` (default) or `visit`, where `visit` means random rows and the output counts the
people in both parts. `test_share`. `cv_folds`: k-fold cross-validated XGBoost tuning over a small fixed grid, grouped
by person unless the split is by visit. The defaults give the same output as before: identical CSVs from a seeded
run before and after, and scripts 40 and 51 rerun with defaults leave `data/` unchanged. Verdict: approve with nits.

## Scope of Change
- Files changed: 7 plus this review (+385 / -32)
- Areas touched: python (`tooth_loss_model.py`, `classify_status.py`, scripts 40 and 51, a new test file), docs
  (`docs/tooth_loss.md`), specs (T005 ticked)
- Commits:
  - b92d343 Add failing tests for the validation settings (spec 032 US5)
  - 577c505 Make the split unit, test share and CV tuning settings (spec 032 US5)
  - 49dfb0b Expose the validation settings in scripts 40 and 51 (spec 032 US5)
  - 2b75dcb Document the tooth-loss validation options (spec 032 US5)
- Range reviewed: `origin/main..feat/444-032-validation-options`

## CI Status
| Check | Status |
|---|---|
| python, postgres, r-parity, bundle | not read here; the full suite was run locally (see Test Coverage) |

## Secrets, PHI and Claims Scan
- Secrets: clean.
- PHI or real data: clean. Synthetic extract and committed synthetic visits only.
- Organization claims: clean. The settings are generic and name no study.

## Strengths
- Defaults are untouched, and `check_params` / `_check_split` fail at once, naming the bad setting.
- A split by visit always reports `people_in_both_count`, so the leak is never hidden.
- A script run away from the defaults writes files with a suffix, next to the committed results instead of over them.
- `ModelParams` gains two fields at the end only, so the parallel `start_date` change should merge cleanly.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- `classify_status.tune` keeps `GroupKFold` (unshuffled). With `split_unit=visit`, its folds are by visit in row
  order. That is reproducible but doesn't use the seed. It is left as is so the default path stays identical. The
  tooth-loss tuning uses seeded `StratifiedGroupKFold` / `StratifiedKFold`.
- The classifier's tuning setting is still named `folds` (default 5, and it always tunes), while the tooth-loss model
  uses `cv_folds` (default None). Script 40's flag is `--cv-folds`, so the command line matches. The US7 preset
  should map `cv_folds` to `folds` for the classifier.
- `xgboost_params` in the `validation` frame is a Python dict's `str()`, not JSON. It is fine for reading, but
  should become JSON if the frame is ever written to gold.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | |
| Synthetic only, no PHI | ✅ | |
| No organization claims | ✅ | |
| Test first | ✅ | b92d343 failed (missing `SPLIT_UNITS`) before the code |
| Python and R in parity | ➖ | Model fitting has no R twin (spec 032 plan); no label, metric or stage rule changed |
| Simulated labelled | ✅ | `validation` rows carry `data_label=synthetic` |
| Seeds fixed | ✅ | splits and tuning folds take the model seed |
| Paths | ✅ | `RESULTS_DIR`, `DATASETS_DIR` |
| Spec | ✅ | spec 032 US5; T005 ticked |
| Telemetry | ✅ | new public functions are `@traced` |
| Configuration | ✅ | function arguments with fixed defaults; no environment variable; no environment changes |
| Commits | ✅ | imperative subjects, why in the body, co-author trailer |

## Test Coverage
- `tests/test_validation_options.py`, 11 tests: defaults; a split by visit is seeded, stratified and shows overlap;
  `people_in_both`; tuning folds grouped by person or by rows; tuning picks a grid point by CV AUC; bad settings
  fail; full `run` with defaults and with visit + `cv_folds`; the classifier's split by visit, its `validation` dict,
  and the row-stratified `split_stratified`.
- Byte-identity: a seeded snapshot (tooth-loss run on 400 patients; `train_eval`; `compare_feature_sets`) was taken
  from `origin/main` and from this branch, and the files are identical. `scripts/40_classify_status.py` and
  `scripts/51_tooth_loss_model.py` were rerun with defaults, and `git status` is clean.
- Full suite: `pytest -q tests`: 1550 passed, 16 skipped. `ruff check` is clean on the changed files.

## Verdict
Approve with nits. Nothing needs to change before merge.
