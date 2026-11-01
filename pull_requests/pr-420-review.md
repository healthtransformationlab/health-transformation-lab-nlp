---
pr: 420
branch: chore/419-004-hf-token-register
title: "004: record the rotated MedGemma reader token in the secrets register"
author: jcbowyer
reviewed_at: 2026-11-01
reviewer: coordinator (one register entry; no subagent needed)
verdict: approve
---

# PR Review: 004: record the rotated MedGemma reader token in the secrets register

## Summary
This PR updates the Hugging Face read-token entry in `ops/secrets_register.yaml` after the token was rotated on
2026-11-01. The entry now gives the new token's name and date, says it has no expiry on Hugging Face, and says to
delete it when the runs are done. Verdict: approve.

## Scope of Change
- Files changed: 2 (the register entry, and this review)
- Commits: 480b789 Record the rotated MedGemma reader token in the secrets register

## Scans
- Secrets: none. The PR has the token's name and date only, never its value.
- PHI / real data: none.
- Organization claims: none.

## Evidence
- The Databricks secret `health_transformation_lab` / `hf_token` was last updated 2026-11-01 11:29 UTC.
- Job 239474419615162 run 169911544718518 (limit 0) finished with SUCCESS.
- `gold_perio_bench.fact_prediction` holds 240 rows for `medgemma-1.5-4b-it` from that run, and `fact_llm_call`
  holds 240 rows from the same run.

## Findings
None.

## Verdict
Approve once CI is green.
