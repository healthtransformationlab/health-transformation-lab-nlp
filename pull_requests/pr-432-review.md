---
pr: 432
branch: feat/429-029-missing-tooth-reasons
title: "029 US7: synthetic teeth missing at the first visit have a realistic mix of reasons"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-01
reviewer: agent self-review against the rubric (no reviewer subagent run)
verdict: approve
---

# PR Review: 029 US7: synthetic teeth missing at the first visit have a realistic mix of reasons

## Summary
This adds spec 029 US7 (#429; T018-T021). Before it, every synthetic tooth missing at the first visit (third molars
aside) was periodontal, so the model's scores on that set had no negatives. Now:
- the spec, plan, tasks and an analysis-plan change-log row come first (it changes a dataset);
- `research.md` records the published shares of reasons for extraction by age band, with full citations and
  populations, checked against PubMed or the PMC full text; Suzuki et al. 2022 (Table 2) is used, and the sources
  that disagree (Scotland 1994/1999; the 2022 review's range) are named with the reason for the choice;
- `open_dental.py` adds non-periodontal teeth missing at entry: a Poisson count per patient by age band, chosen by
  tooth type, never by CAL, on their own seeded stream; the worst-CAL and worst-PD teeth stay; a mouth below stage IV
  keeps 20 teeth; the reason lives only in `tooth_loss_truth`;
- every output built from the extract was regenerated with the repo's scripts, and `docs/tooth_loss.md` reports AUC
  and specificity on teeth missing at entry and the new stage recount, labelled SYNTHETIC.

Meets the US7 acceptance scenarios. Approve.

## Tests
- New tests written first and seen failing (`entry_reasons` missing): the share by age band within 0.05 on a seeded
  6,000-patient extract and rising with age; no correlation of non-periodontal counts with worst CAL within bands
  (|r| < 0.05) while periodontal counts do correlate (r > 0.1); own stream and seed; both classes and numeric AUC and
  specificity in the missing-at-entry scores (`test_tooth_loss_model.py`).
- Full suite: 1292 passed, 15 skipped. `ruff` is clean on the touched files (the repo has older findings elsewhere).
- R parity ran in full: all OK, including spec 029 (6,400 teeth, 0 statuses differ) and US3 (424 metric values,
  8,000 stage rows, 0 differ). The unrelated committed files the parity inputs rewrote were restored.

## Secrets, PHI and Claims Scan
Clean.
- **Data:** synthetic only; published aggregate figures only, nothing from any practice. The truth stays out of the
  extract (existing test).
- **Claims:** every result in `docs/tooth_loss.md` and the PR is labelled SYNTHETIC with the command and seeds. The
  page says the high AUC on teeth missing at entry is a property of the generator, not something to expect on real
  records.
- **Wording:** "recorded diagnosis", "finding"; `test_wording.py` passes. No organization named beyond cited papers.
- **Secrets:** none.

## Findings
None blocking.
- **The missing-at-entry AUC (0.95-0.96) is easy by construction:** non-periodontal losses depend on age and tooth
  type only, so they sit mostly in young mouths with little attachment loss. Real caries losses co-occur with
  periodontitis. A follow-up could make non-periodontal loss depend on caries risk shared with periodontal risk
  (smoking, diabetes, access to care), which would make the evaluation harder and more honest.
- **Counts per patient are not calibrated:** matching the share against the spec 006 periodontal losses (flat with
  age, about 0.25-0.31 per patient) gives young patients more non-periodontal missing teeth (mean 3.6 at 25-34) than
  older ones. `research.md` states this; the share, not the count, is what the evaluation needs.
- **Incidence applied to prevalence:** the shares are for extractions in one week, applied to teeth already missing;
  stated as a caveat.
- **Seed noise:** periodontal counts are heavy-tailed, so one seed's share in a band can sit 0.03-0.05 from the
  target (seed 42's 35-44 band: 0.17 against 0.21). The test uses 6,000 patients.
- **ERD PNG:** only the dictionary changed; it was re-rendered with `drawio_render.js` against a local copy of the
  draw.io viewer (`viewer-static.min.js` from the jgraph/drawio repository), since viewer.diagrams.net is not
  reachable here.

## Rubric
- Spec before code for a dataset change; test first; new public functions (`entry_reasons`, `patient_age`,
  `age_band`) are `@traced`.
- Python/R parity: no label rule or metric changed; parity ran and passes on the regenerated inputs.
- Seeds fixed: the new stream is `f"{seed}:open_dental:entry_reason"`; the study datasets are unchanged
  (`sites.draw_mouth_columns` untouched; existing test passes). Paths through `paths`.
- Generated files rebuilt by their scripts, not by hand (`docs/tooth_loss.md` is a hand-written page, updated from
  the script's output).
- Environments: no settings or schema change; the Load Open Dental job writes the new extract on its next run in
  each environment.
- `Closes #429`. The branch follows `feat/<issue>-<slug>`.
