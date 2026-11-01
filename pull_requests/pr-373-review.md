---
pr: 373
branch: feat/369-029-open-dental-schema
title: "Check spec 029's Open Dental tables against Open Dental's source"
author: jcbowyer
reviewed_at: 2026-10-30
reviewer: coordinator verification against the Open Dental source
verdict: approve
---

# PR Review: Check spec 029's Open Dental tables against Open Dental's source

## Summary
This PR completes spec 029's T001. Each of the 12 tables and every column the extract uses was read from Open
Dental's GPL source: `OpenDentBusiness/TableTypes`, branch `24_3`, commit `d804c19`. Each is recorded in
`research.md` in our own words, and the plan is corrected where it had guessed. Approve.

## Verified against the source
- Table names. `procedurelog` and `definition` are named by their classes' `CrudTable` attribute (from
  `Procedure` and `Def`). The others are their class names, lowercased.
- `PerioSequenceType`:
  - 0 Mobility, 1 Furcation, 2 GingMargin, 3 MGJ, 4 Probing, 5 SkipTooth, 6 BleedSupPlaqCalc, 7 CAL;
  - CAL is "never saved to the db";
  - flags are bleeding 1, suppuration 2, plaque 4, calculus 8.
- `periomeasure`: -1 is "no measurement", and gingival-margin values of 100 and up are negatives.
- `ToothInitialType` 0 = Missing.
- `ProcStatus` values 1–7 come from the `procedurelog` column's own comment: 4 = Existing Other Prov.
- `procedurelog.Dx` is an FK to `definition`. `DiagnosticCode`–`DiagnosticCode4` sit with `IcdVersion` (9 or 10).
- `patient.SmokingSnoMed`. `diseasedef.Icd10Code`.

## Secrets, PHI and Claims Scan
Clean. No data. Only public schema facts, attributed to the source, with no code copied (a test checks that no
class text appears).

## Findings
- 🔵 These are the `24_3` columns. An older practice version may lack newer ones, e.g. `IcdVersion` or
  `DateComplete`. That doesn't matter for a synthetic extract, and the research note gives the version.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets / PHI / org claims | ✅ | |
| Test first | ✅ | `test_open_dental_schema_research.py` failed 3/3 before |
| Citations | ✅ | reference 58, with branch, commit and licence |
| Words | ✅ | "diagnosis" only as recorded in the source's own field names |

## Verdict
approve. Merge once CI is green.
