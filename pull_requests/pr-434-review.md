---
pr: 434
branch: feat/433-029-shared-tooth-loss-risk
title: "029 US8: synthetic tooth loss for other reasons shares risk factors with periodontal loss"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-01
reviewer: agent self-review against the rubric (no reviewer subagent run)
verdict: approve
---

# PR Review: 029 US8: synthetic tooth loss for other reasons shares risk factors with periodontal loss

## Summary
This adds spec 029 US8 (#433; T022-T025). Before it, the synthetic non-periodontal teeth missing at entry depended on
age and tooth type only, so they shared no risk factor with periodontal losses. Now:
- the spec (US8, FR-012, SC-010), plan step 9, tasks and an analysis-plan change-log row come first (it changes a
  dataset);
- `research.md` ("Shared risk factors") records the published effects of smoking and diabetes on tooth loss for
  reasons other than periodontitis, with full citations and populations, checked against PubMed or the PMC full text:
  smoking from Mai et al. 2013 (caries-only loss, packs a day: 1.05 and 1.38), diabetes from Ahmadinia et al. 2022
  (all-cause adjusted OR 1.20, used as an upper bound because Suzuki et al. 2021 find no caries association within
  extractions); attendance and deprivation are recorded but not modelled (no effect size, no synthetic attribute);
- `open_dental.py` multiplies each patient's Poisson mean by the rate ratio and divides by its mean over
  `draw_risk` patients, so each age band keeps its US7 mean and share; same stream, `sites.draw_mouth_columns`
  untouched, teeth still chosen by tooth type;
- everything built from the extract was regenerated with the repo's scripts, and `docs/tooth_loss.md` reports the
  missing-at-entry AUC, specificity and stage recount before and after, labelled SYNTHETIC.

Meets the US8 acceptance scenarios. Approve.

## Tests
- New tests written first and seen failing (`Params` had no `entry_other_smoking_ratios`; observed/expected
  non-periodontal count for daily smokers 0.997): the rate ratio and its cited defaults; the norm against independent
  `draw_risk` draws; neutral ratios give US7's means exactly; O/E above 1 for daily smokers (1.13) and diabetes
  (1.15), below 1 for never-smokers without diabetes (0.97) on a seeded 6,000-patient extract; no correlation of the
  non-periodontal count with worst CAL within age band and risk group.
- The US7 share test now pools seeds 13-15. Seed 13 alone sat 0.07 from target in two bands after the change, from
  the heavy-tailed periodontal counts (the extract is a fresh sample once the main stream moves). Pooled over eight
  seeds the shares are as close to target after the change as before (within 0.034), so this is noise, not drift.
- Full suite: 1447 passed, 15 skipped after merging main (1295 passed before). `ruff` clean on the touched files.
- R parity ran in full before and after merging main: all OK, including spec 029 (6,400 teeth, 0 statuses differ) and US3 (424
  metric values, 8,000 stage rows, 0 differ). Unrelated committed files the parity inputs rewrote were restored.

## Secrets, PHI and Claims Scan
Clean.
- **Data:** synthetic only; published aggregate figures only. The truth stays out of the extract (existing test).
- **Claims:** every result is labelled SYNTHETIC with the command and seeds. The page and the PR say the effects
  used are small and not statistically significant, that the diabetes figure is an all-cause upper bound, and that
  the AUC change (about 0.01) is inside the seed spread.
- **Wording:** "recorded diagnosis", "finding", "record mismatch"; `test_wording.py` passes. No organization named
  beyond cited papers.
- **Secrets:** none.

## Findings
None blocking.
- **Small effect by design:** the cited non-periodontal effects are weak, so the missing-at-entry AUC stays about
  0.94-0.95. The page says what keeps it high (the age mix and attachment loss). Making the evaluation harder would
  need a stronger, sourced link (for example caries risk or attendance), not larger invented ratios.
- **Diabetes upper bound:** 1.20 is all-cause; Suzuki et al. 2021 point lower. 1.0 is a parameter away.
- **ORs as rate ratios on a count:** stated in research.md; generous to the shared risk.
- **Before/after is confounded by resampling:** the main stream moves with the number of teeth present, so every
  extract is a new sample; the page gives 5-seed means for that reason. On the new seed 42 the completed-extraction
  models' probabilities run low on teeth missing at entry, so they undercount stage IV (21-27 against a truth of 97);
  the 5-seed means (50-53 against 94) show it is partly that seed.
- **Attendance and deprivation not modelled:** no effect size found and no synthetic attribute; a follow-up.
- **ERD PNG:** re-rendered with `drawio_render.js` against a local copy of draw.io's `viewer-static.min.js`.

## Rubric
- Spec before code for a dataset change; test first; new public functions (`entry_other_rate_ratio`,
  `entry_other_rate_norm`, `entry_other_mean`) are `@traced`.
- Python/R parity: no label rule or metric changed; parity passes on the regenerated inputs.
- Seeds fixed: the same entry stream; the norm uses its own fixed stream; the study datasets are unchanged
  (`sites.draw_mouth_columns` untouched). Paths through `paths`.
- Generated files rebuilt by their scripts (`docs/tooth_loss.md` is a hand-written page, updated from the script's
  output).
- Environments: no settings or schema change; the Load Open Dental job writes the new extract on its next run.
- `Closes #433`. The branch follows `feat/<issue>-<slug>`.
