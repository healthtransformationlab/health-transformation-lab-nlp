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

## Out of scope

- Calibrating the periodontitis mix to NHANES (a later spec; it changes every benchmark number).
- Record-mess rates with no published standard: they stay placeholders until a real extract's realism profile sets
  them.

## Success criteria

- SC-001: every generator parameter appears in the data card with a source or the word "placeholder" (test).
- SC-002: every cited figure is checked against its full text before it is added (`docs/references.md`).
- SC-003: after US2 the extract's smoking, diabetes and insurance shares fall within the cited figures' ranges.
