---
pr: 793
branch: feat/791-014-entries-to-azure
title: "014 US7: leaderboard entries and the GPU runs' spans reach Azure"
author: claude (implemented by a subagent, reviewed by the coordinator)
reviewed_at: 2026-11-15
reviewer: coordinator verification against .claude/review-rubric.md
verdict: approve
---

# PR Review: leaderboard entries and the GPU runs' spans reach Azure

## Checks
| Check | Result |
|---|---|
| Issue #791 with its four parts first; spec 014 US7 names it; `plan.md` beside it | yes |
| Test first: 27 new tests failed, then passed; full suite 2728 passed, 37 skipped | yes |
| Secrets: tokens and the connection string reach the job only through masked `secrets.*`; spans carry ref, status and score, never the description; nothing printed | yes |
| Optional setting: without `APPINSIGHTS_CONNECTION_STRING`, a `::warning::` annotation, telemetry off, ledger updated (AGENTS.md, Configuration) | yes |
| Alert: an entry turning to error fails the job after the ledger is pushed (SEV2, owner emailed the same day); only on the change, so an old error doesn't fail every run | yes |
| Idempotent ledger (one row per ref, overwritten); `kaggle-results/*` branch as the Kaggle workflows do | yes |
| `forward_spans`: original times in ns, parentage under new ids, children ended first; 0 with the exporter off; tested with the memory exporter | yes |
| Read-only on Kaggle; no GPU; publishes nothing | yes |

## Findings
### Blocking
None.
### Should fix (follow-up, not here)
1. The ledger's columns (`ref`, `status`, `description`, `public_score`) are bare names the data-naming rule would
   reject for a table; the Contract fixed them and it is a CSV, not gold. If it ever loads to gold, `gold_names` must
   map them (`submission_ref_id`, `status_code`, `description_text`, `public_score_ratio`).
2. The Application Insights resource doesn't exist yet (#792): until the owner creates it and sets the secret, the
   watcher keeps the ledger and warns.
### Minor
3. `completed_ts` is the first watch that saw an entry complete, within two hours of the real time; the docstring says so.

## Verdict
Approve. Merge when CI is green.
