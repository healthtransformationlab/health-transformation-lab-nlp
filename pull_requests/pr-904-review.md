---
pr: 904
branch: fix/832-027-doctor-task-error
title: "027 BUG2: doctor reads failed task errors; missing package is config"
author: jcbowyer
reviewed_at: 2026-11-21
reviewer: coordinator (rubric scan + local pytest)
verdict: approve
---

# PR Review: 027 BUG2 doctor task errors

## Summary
Enriches failed pipeline runs from Jobs API task get-output and classifies
`ModuleNotFoundError` as `config`. Spec 027 updated with that decision. Approve —
no blocking findings. Live re-run of the five Nov 15 failures is optional and
needs a Databricks doctor job (not this PR).

## Scope of Change
- Files: doctor.py, doctor_job.py, notebook 13, tests, specs/027 plan+spec
- Range: `origin/main..HEAD`

## CI Status
Pending at review write; re-check before merge.

## Secrets, PHI and Claims Scan
- Secrets / PHI / org claims: clean (synthetic get-output fixtures only)

## Findings
### 🔴 Blocking
None.

### 🟡 Should fix
None.

### 🔵 Nits
- Live doctor re-run over the five historical failures is Done-when residual; needs workspace job.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Spec before rule change | yes | plan.md + spec.md name `config` for missing packages |
| Test first | yes | parse/apply + classify cases failed before code |
| Idempotent / no note text | yes | first line of error only |

## Verdict
**approve** — merge when CI is green.
