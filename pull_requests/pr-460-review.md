---
pr: 460
branch: feat/440-032-status-grouping
title: "032 US1: scores and prevalence at a chosen status grouping"
author: jcbowyer
reviewed_at: 2026-11-01
reviewer: implementing agent (self-review against .claude/review-rubric.md and AGENTS.md)
verdict: approve
---

# PR Review: scores and prevalence at a chosen status grouping

## Summary
- `labels.GROUPINGS` (`six`, `five`, `three`) and `labels.group_status`. No answer, `unknown` and NaN keep their
  value; `healthy_gingivitis` merges at five and three groups.
- `eval/score.py` `score(..., grouping="six")` and `prevalence.prevalence_by_group(..., grouping)`. The default is
  unchanged.
- R twins: `r/R/labels.R` (`STATUS_GROUPINGS`, `group_status`), `eval/score.R` (`score_run(..., grouping)`),
  `r/R/06_validation.R` (`prevalence_by_group`). The parity test checks five and three.

## Scope of Change
- 11 files plus this review: `labels.py`, `prevalence.py`, `eval/score.py`, `eval/score.R`, `eval/README.md`,
  `r/R/labels.R`, `r/R/06_validation.R`, `r/tests/test_parity.R`, `scripts/export_rules_predictions.py`,
  `tests/test_status_grouping.py` (new) and `specs/032-analysis-options/tasks.md` (T001 ticked).

## Scans
- **Secrets:** none. **PHI / real data:** none; the tests use hand-made status lists. **Organisation claims:** none;
  the groupings are generic.

## Checks against the rubric
- **Test first:** `test_status_grouping.py` imports `GROUPINGS`, `group_status` and `prevalence_by_group`, none of
  which exist on `main`, so it fails there. It covers the mapping, no answer, grouping twice giving the same result
  as grouping once, an unknown grouping, scoring at five and three groups, and prevalence by group.
- **Results byte-identical (SC-001):** with the default `six`, `score()` gives byte-identical output to `main`'s
  scorer on 500 random inputs (timestamp aside). `data/datasets/prevalence/` regenerates unchanged. Rerunning
  `make_parity_inputs.sh` in this container also rewrites some unrelated committed files: predictions that differ at
  float precision, de-id engines whose optional modules aren't installed, and the simulated reliability sets. None of
  those files comes from code this PR touches, so they were restored and not committed.
- **Python/R parity:** `Rscript r/tests/test_parity.R` prints `parity OK` in every section. Scorer at five groups
  0.00e+00 (11 metrics), at three groups 0.00e+00 (9 metrics). Prevalence by group 0.00e+00 over 112 rows (8 clinics,
  six, five and three groups). `group_status` edge cases are checked in R too.
- **Telemetry:** `group_status`, `periodontitis_groups` and `prevalence_by_group` carry `@traced`.
- **Paths, seeds:** `paths` used throughout; there is no new sampler.
- **Wording, benchmark order, organisation names:** `test_wording`, `test_bench_order` and `test_no_org_references`
  pass.
- **Configuration:** no new environment setting.
- **Full suite:** `pytest -q tests`: 1551 passed, 16 skipped. `ruff check` on the touched Python files is clean.

## Findings
- **Important (fixed on the branch):** the scoring contract in `eval/README.md` didn't mention the new argument. It
  now has a paragraph on status grouping.
- **Minor (fixed on the branch):** the first version imported `labels` lazily from `eval/score.py`. That would have
  tied the standalone scorer (also used from the Databricks notebook) to the package being installed. The scorer now
  keeps its own copy of the mapping, as it does `LABEL_ORDER`, and a test checks the copy matches `labels.GROUPINGS`.
- **Nit (left):** no script writes grouped prevalence yet. `prevalence_by_group` runs only in the parity inputs until
  the preset script (US7) and the new defaults (US8) use it.

## Verdict
Approve. The defaults leave committed results unchanged, and Python and R agree at every grouping.
