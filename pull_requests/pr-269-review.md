---
pr: 269
branch: chore/267-025-hf-token-register
title: "Record the Hugging Face publish token in the secrets register"
author: jcbowyer
reviewed_at: 2026-10-29
reviewer: coordinator verification
verdict: approve
---

# PR Review: Record the Hugging Face publish token in the secrets register

## Summary
This PR updates the register entry for the Hugging Face publish token to match what is in use:
- the fine-grained token "Claude", in `dev` as `HF_TOKEN`;
- no expiry set on Hugging Face;
- replacement due by 2027-01-24.

`expires: never` follows the register's allowed values (a date, `never` or `unknown`). The renewal date sits in
`lifetime`. Approve.

## Scope of Change
- `ops/secrets_register.yaml`: `stored_in`, `lifetime`, `expires` for "Hugging Face publish token"

## Secrets, PHI and Claims Scan
Clean. Only the token's display name is recorded. The value appears nowhere, and neither does its masked tail.

## Findings
- 🔵 A token that never expires breaks the register's own "90 days at most" lifetime. The entry says so, with
  the date to replace it. The owner will need to act on it then.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Secrets register | ✅ | where it lives, scope, owner, expiry and what breaks are all present |
| No secrets | ✅ | |
| Commits | ✅ | |

## Verdict
approve. Merge once CI is green.
