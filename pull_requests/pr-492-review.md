---
pr: 492
branch: chore/491-004-hf-token-name
title: "004 CHORE2: name the Databricks MedGemma token as Hugging Face shows it, \"claude read\""
author: jcbowyer
reviewed_at: 2026-11-03
reviewer: coordinator only (a 4-line register text change; no reviewer subagent)
verdict: approve
---

# PR Review: 004 CHORE2: name the Databricks MedGemma token as Hugging Face shows it, "claude read"

## Summary
The PR corrects the name of the Hugging Face token recorded for the Databricks secret `health_transformation_lab` /
`hf_token`: "claude read", as it appears on Hugging Face, not "databricks-medgemma". The match rests on the owner's
token list. No "databricks-medgemma" exists there, and "claude read" (Read) was last used 2026-11-01, the day the
MedGemma reader job succeeded with that secret. The change is to record text only. Verdict: approve.

## Scope of Change
- Files changed: 1 (+4 / -2)
- Areas touched: ops
- Commits: b7479c6 004 CHORE2: name the Databricks MedGemma token as Hugging Face shows it, "claude read"
- Range reviewed: `5e4b45d..b7479c6`

## CI Status
| Check | Status |
|---|---|
| python, postgres, r-parity, bundle, pr-conventions | pending when this was written |

## Secrets, PHI and Claims Scan
- Secrets: clean. A token name only, never a value.
- PHI / real data: clean.
- Organization claims: clean.

## Strengths
- It says how the match was made, so it can be checked again later.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
1. `ops/secrets_register.yaml:48`. The match is by date, not confirmed inside Databricks; a secret's value can't be
   read back. Rotating the token next time settles it for certain: make a new token, put it in the scope, run the
   reader, then revoke "claude read".
   - Also, the first wording broke the YAML twice: ": " inside a plain value, and " #" read as a comment. Both
     were fixed before the commit, and the register loads.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | Pass | name only |
| Secrets register | Pass | this is the register fix |
| Configuration | Pass | no setting changes; no environments change |
| Commits | Pass | imperative subject, body says why, co-author trailer |
| Test first, parity, simulated, seeds, paths, spec, prices, decks, idempotent writes, alerts | n/a | no code or data |

## Test Coverage
- Run locally: `yaml.safe_load` of the register loads.
- `pytest -q tests -k "secret or register or wording or org_ref"`: 112 passed, 3 skipped.

## Verdict
Approve. Merge once CI is green.
