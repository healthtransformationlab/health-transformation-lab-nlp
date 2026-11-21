---
pr: 891
branch: chore/890-leaderboard-timeout-hours
title: "014 CHORE: record Notebook Timeout and wall_hours on leaderboard watch"
author: jcbowyer
reviewed_at: 2026-11-21
reviewer: coordinator (rubric scan; CI green)
verdict: approve
---

# PR Review: 014 CHORE leaderboard watch timeout and wall_hours

## Summary
Extends `kaggle/submission_watch.py` so ledger rows record `finished_ts`, `wall_hours`, and `final_status_text` (score or Notebook Timeout), with tests. Independent of the 042 stack. CI green; approve.

## Scope of Change
- Leaderboard watch workflow, ledger CSV, submission_watch, tests, prior review note
- Range: PR branch vs main

## CI Status
| Check | Status |
|---|---|
| check, python, python-databricks-runtime, postgres, azure-infra, bundle | SUCCESS |
| r-parity | SKIPPED |

## Secrets, PHI and Claims Scan
- Secrets: clean
- PHI: clean (competition leaderboard metadata only)
- Organization claims: clean

## Findings
### 🔴 Blocking
None.

## Verdict
**approve** — merge under AGENTS.md rule 6 (#497).
