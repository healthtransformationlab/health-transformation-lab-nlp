---
pr: 422
branch: feat/371-029-tooth-loss-model
title: "029 US3: a tooth-level model says whether a missing tooth was lost to periodontitis"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-01
reviewer: agent self-review against the rubric (no reviewer subagent run)
verdict: approve
---

# PR Review: 029 US3: a tooth-level model says whether a missing tooth was lost to periodontitis

## Summary
This finishes spec 029 US3 (#371; T008-T011). The code follows the pre-specified analysis plan:
- `tooth_loss_model.py` fits logistic regression and XGBoost on both label sets (FR-010), with shared and own
  predictors.
- The split is 70/30 by patient, stratified and seeded, and both label sets share it, so they are scored on the
  same held-out teeth (US3 scenario 4).
- Measures: AUC, Brier, calibration, threshold metrics at 0.5 and at Youden, and patient-bootstrap intervals.
- `labels.stage4_rule` recounts stage III vs IV under four rules, including `expected_perio_loss`.
- Base-R twins exist for the metrics and the stage rule.
- The gold `fact_tooth_loss_prediction` is declared, and the Load Open Dental job writes it.

This meets the US3 acceptance scenarios on synthetic data. Approve.

## Tests
- `test_tooth_loss_model.py` (19 tests) was written first, and failed at import before the module existed.
- Full suite: 1266 passed, 15 skipped. `ruff` is clean on the touched files.
- R parity ran in full, and all sections were OK:
  - spec 029 US3: 424 metric values across 36 sets of teeth match to 1e-9;
  - stage rule: 8,000 patient rows, 0 differ (24,000 rows on the 6,000-patient run).

## Secrets, PHI and Claims Scan
Clean.
- **Data:** synthetic only. The answer key is read only to score the unlabelled teeth, and a test checks it is never
  a feature. No result CSVs are committed (`data/results/` is ignored). The committed data files that the parity
  inputs rewrote locally were restored, not committed.
- **Claims:** every number in `docs/tooth_loss.md` and the PR is labelled SYNTHETIC, and the run command and seed
  are given.
- **Wording:** the page says "finding gum disease in dental records (phenotyping)" and "recorded diagnosis item";
  `test_wording.py` passes.
- **Secrets:** no new credentials or settings.

## Findings
None blocking.
- **Synthetic generator limit (worth an issue):** with third molars excluded, every tooth missing at entry is
  periodontal by the answer key, because `sites.draw_mouth_columns` draws "other" only for third molars. So AUC and
  specificity are undefined on that applied set, and "every missing tooth" looks nearly right for stage IV. The doc
  says so. A generator change would alter existing datasets and needs its own spec.
- **Calibration:** on held-out extractions, the completed + planned label set runs high (intercept about -1.3),
  because planned extractions are mostly periodontal.
- **Deviations** are logged in the analysis plan's change log:
  - age at the first exam for planned teeth;
  - per-patient stratification;
  - applied sets scored over all patients;
  - bootstrap on the main seed only;
  - stage population is worst CAL >= 5 mm;
  - the recorded-only baseline only on applied sets;
  - 6,000 patients.
- **Placement:** the model lives in `tooth_loss_model.py` and `scripts/51_...`, not in `tooth_loss.py` and
  `scripts/45_...` as plan.md said (45 was taken); `tasks.md` notes it.
- **ERD PNGs:** not re-rendered, because that needs the draw.io viewer. The sources and `data_model.md` are
  regenerated.

## Rubric
- Test first; every new public function and method is `@traced`. `labels.stage4_rule` and `expected_perio_loss`
  are set to `detail` level in `telemetry_levels.yaml`, since they run once per patient.
- Python/R parity: the label rule and the metrics have twins, and parity ran.
- Gold names follow "SQL and data names" (`test_sql_conventions.py`). The write is idempotent (delete-then-append
  by `run_id`), and every row carries its batch key.
- Seeds are fixed (split, models and bootstrap: 42; generator seeds 42-46). Paths go through `paths.RESULTS_DIR`.
- Environments: dev, uat and prod gain the gold table on the next deploy and job run, as the PR says.
- `Closes #371`. The branch follows `feat/<issue>-<slug>`.
