---
pr: 409
branch: feat/370-029-dq-checks
title: "029 US2 T006a: data-quality checks after Kookal et al. 2024, and chart consistency by group"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-01
reviewer: coordinator verification (no reviewer subagent run)
verdict: approve
---

# PR Review: 029 US2 T006a: data-quality checks and chart consistency by group

## Summary
This implements spec 029 FR-009 (T006a) as written. There are two deliberate changes from the spec, and both are
recorded in the spec and the plan:
- **Planted faults:** they are applied in the tests only, so the default extract and every committed result stay as
  they were.
- **Office comparison:** each office is compared with the other offices rather than the mean of all, because with 4
  offices an outlier can never reach 2 SD.

The new group split (office, provider, sex, race, exam year, age band) answers the study lead's question about
consistency. It is marked provisional until he names his groups. Approve.

## Tests
- Every planted fault is found exactly, and a clean extract finds nothing.
- The flag rules are tested on hand cases.
- The silver tables are tied to the data model, and the load job to both tables.

## Secrets, PHI and Claims Scan
Clean.
- **Data:** counts only. No row-level data goes into the outputs.
- **Clinic names:** they are invented and labelled "(synthetic)".
- **Sources:** no study-site findings are named. The checks are general to any Open Dental extract.

## Findings
None blocking.
- **Load job not yet run:** it was checked by test only, against the notebook text. The first dev run will confirm
  the Spark writes.
- **Chance flag:** one group is flagged on the default extract (exam year 2025). That is expected from a 2 SD rule
  across about 30 groups.

## Rubric
- `@traced` is on every public function.
- No hard-coded data paths.
- The notebook's Open Dental tables still carry no `run_id`; the dq tables do, as the model declares.
- `Refs #370` (the rest of the story is already merged).
