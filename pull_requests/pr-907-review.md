---
pr: 907
branch: chore/711-036-project-tag
title: "036 CHORE4: use pipeline-doctor billing and tag every job with project"
author: jcbowyer
reviewed_at: 2026-11-22
reviewer: coordinator (rubric scan + local pytest)
verdict: approve
---

# PR Review: 036 CHORE4 project tag and shared billing

## Summary
Drops the duplicate `billing_costs` in `doctor_job` for the pipeline-doctor 0.5.0
re-export, pins that commit, and sets `presets.tags.project` on every bundle target.
Approve — matches #711 Done when; no blocking findings.

## Scope of Change
- Files changed: 5 (+26 / −27)
- Areas touched: python / databricks

## Secrets / PHI / claims
Clean. No secrets, PHI, or organization claims.

## Compliance
| Rule | Result |
|---|---|
| Test first | ok — identity + presets.tags assertions fail before the pin and yml change |
| Configuration | ok — presets.tags only; no new settings or secrets |
| Simulated labelled | n/a |

## Findings
None blocking.

## Verdict
**approve** — merge when CI is green.
