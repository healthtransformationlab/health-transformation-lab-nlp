# Feature Specification: synthetic data parameters, documented and sourced

**Feature Branch**: `spec/484-033-synthetic-data-parameters`

**Created**: 2026-11-03

**Status**: specified

**Input**: the owner asked which rates in the synthetic data match NHANES and other published sources, and whether
the parameters are documented. Answer: a few are sourced and checked (medical-record conditions, the reasons teeth
are missing, the smoking and diabetes effects on tooth loss); the periodontitis mix and the record-mess rates are
placeholders; smoking, diabetes and insurance are unsourced and differ from published US figures. Each parameter is
documented where it is set, but no page lists them all.

> Personal learning project; synthetic data only. Every number is SYNTHETIC; a "source" means a published figure
> the synthetic value is set from or checked against, never real records.

## User stories

### US1 - A data card lists every parameter with its value and a checked source or "placeholder" (P1) #484

- `docs/synthetic_data.md`: one table per generator (study visits, the Open Dental extract, the medical record)
  giving each parameter, its value, its source (checked against the full text and added to `docs/references.md`)
  or "placeholder", and the published figure it should match where one exists, with the comparisons the repo
  already runs (`data/datasets/prevalence/vs_published.csv`, `data/datasets/nhanes/`).
- A test fails when a declared parameter has neither a source nor a placeholder label.
- No data or result changes.

### US2 - The Open Dental extract's smoking, diabetes and insurance follow published US figures (P1) #485

- Smoking, diabetes and insurance shares become settings of the shared risk draw (`synthetic.draw_risk`) and
  `open_dental.Params`; the extract's values come from checked sources (US adult cigarette smoking, CDC NHIS;
  diabetes, CDC National Diabetes Statistics Report, defined by HbA1c >= 6.5 as NHANES does; dental coverage, ADA
  Health Policy Institute or NCHS).
- The study build keeps its current values (its notes were scored by external model runs; US3).
- Tooth-loss, data-quality and preset results are rerun and recommitted, with a before/after table.

### US3 - The benchmark notes use the same shares when they are rebuilt (P3) #486

- Done together with #467 (rebuild the notes for adults from the start date), so the external model runs are
  redone once.

### US4 - The Open Dental extract has patients with no natural teeth, and optionally a state per clinic (P2) #500

- A share of the extract's patients have no natural teeth (edentulism), by age band: 65-69, 70-74 and 75+ from
  NHANES 2015-2018 (NCHS Data Brief 368, references item 79); under 65 from this repo's own NHANES 2009-2014 run
  (`scripts/38_nhanes_perio.py` writes `data/datasets/nhanes/nhanes_edentulous_by_age.csv`; real public data), as
  Data Brief 368 covers 65 and over only. Drawn on a random stream of its own, so patients with teeth keep their rows.
- An edentulous patient has every tooth missing in `toothinitial` and no perio chart, radiograph, hygiene visit or
  extraction. Why their teeth were lost isn't modelled, so they have no answer-key rows.
- The tooth table holds them as 32 teeth missing at entry; the tooth-loss model and the stage recount leave them out
  (the 2018 classification can't stage a mouth with no teeth). The data-quality checks leave their visits out of the
  charting rates (no chart because no teeth is not a missing chart), report their share, and flag a chart recorded
  for one (`chart_without_teeth`).
- Optional geography (`open_dental.Params.clinic_states`, default empty, so the default extract has no state): each
  clinic gets a US state and its patients' share is scaled by that state's rate over the US rate (all teeth lost at
  65 and over, BRFSS 2022, CDC U.S. Chronic Disease Indicators; references item 81).
- Tooth-loss, data-quality and preset results are rerun and recommitted; the data card moves edentulism from "Known
  gaps" to a sourced parameter with the synthetic against the published table.

## Out of scope

- Calibrating the periodontitis mix to NHANES (a later spec; it changes every benchmark number).
- Record-mess rates with no published standard: they stay placeholders until a real extract's realism profile sets
  them.

## Success criteria

- SC-001: every generator parameter appears in the data card with a source or the word "placeholder" (test).
- SC-002: every cited figure is checked against its full text before it is added (`docs/references.md`).
- SC-003: after US2 the extract's smoking, diabetes and insurance shares fall within the cited figures' ranges.
