---
pr: 394
branch: docs/387-030-record-sets
title: "030 US1: say which records each scoring number counts"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-10-31
reviewer: coordinator verification (no reviewer subagent run)
verdict: approve
---

# PR Review: 030 US1: say which records each scoring number counts

## Summary
Docs only. `docs/scoring.md` gains a table of the synthetic record sets. Each count was checked against the committed
files:
- 1,200 patients and 4,343 visits;
- 3,484 training notes from 960 patients;
- 240 review charts from the other 240 patients;
- 3,437 charted visits;
- the separate 2,000-patient Open Dental extract.

It also says that no held-out patient is trained on. Approve.

## Secrets, PHI and Claims Scan
Clean.

## Findings
None.

## Rubric
`Refs #387`. Wording and bench-order checks pass.
