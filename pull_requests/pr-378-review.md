---
pr: 378
branch: docs/377-029-open-dental-diagnoses
title: "Spec 029: diagnoses from the practice's own lists, and planned extractions"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-10-31
reviewer: coordinator verification (spec-only change; no reviewer subagent run)
verdict: approve
---

# PR Review: Spec 029: diagnoses from the practice's own lists, and planned extractions

## Summary
The PR updates spec 029 before any implementation, from the owner's clarification of the tooth-loss task. It
replaces the ICD-10-CM diagnosis assumption with Open Dental's own mechanism: the practice's diagnosis list in
`definition`, which changes over time. It adds planned extractions as a second label set and checks plan copies
against their original. It keeps silver close to Open Dental. Each change is checked against `research.md`, which
comes from Open Dental's public source. Approve.

## Scope of Change
- Files changed: 4 (spec, plan, research, tasks), plus this review
- Areas touched: specs
- Range reviewed: `origin/main..docs/377-029-open-dental-diagnoses`

## Secrets, PHI and Claims Scan
- Secrets: clean.
- PHI / real data: clean. The diagnosis lists, adoption date and lag, and planning rates are declared as invented
  parameters, not observations.
- Organization claims: clean. No practice, organisation or person is named, and a search for those names found
  none. The behaviour described (`Dx` → `definition`; `proctp` copies with `ProcNumOrig`) is Open Dental's public
  schema, recorded in `research.md`.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
- FR-010 is placed before FR-009 in the list, so the numbers read out of order. The text is right; reorder them
  the next time the spec is touched.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets, no PHI | Yes | |
| No organization claims | Yes | |
| Spec before implementation | Yes | spec, plan and tasks updated; implementation tasks still open |
| Python and R in parity | n/a | the new statuses and `planned_extraction` are already in T006's R twin |
| Simulated is labelled simulated | Yes | the rates are named parameters; results stay labelled synthetic |
| Commits | Yes | |
| Branch and issue | Yes | `docs/377-029-open-dental-diagnoses`, `Closes #377` |

## Test Coverage
`cd python && python -m pytest -q tests`: 1115 passed, 16 skipped, including `test_open_dental_schema_research.py`.

## Verdict
Approve. It can merge once CI is green.
