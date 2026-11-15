---
pr: 773
branch: chore/772-gpu-quota-ration
title: "000 CHORE3: ration the Kaggle GPU hours: read the quota around every run, one run at a time"
author: claude
reviewed_at: 2026-11-15
reviewer: coordinator verification against .claude/review-rubric.md
verdict: approve (owner merges: it changes AGENTS.md)
---

# PR Review: ration the Kaggle GPU hours

## Summary
Adds `kaggle/gpu_quota.py`, which prints the account's weekly GPU hours from Kaggle's API, and rationing rules in
AGENTS.md and `kaggle/README.md`. The owner asked for both. Nothing blocking. It changes the agent rules, so the owner
says "merge".

## Checks
| Check | Result |
|---|---|
| Issue #772 with its four parts before the first commit; `Closes #772` | yes |
| Test first: `test_kaggle_gpu_quota.py` failed (no script, no rules), then passed | yes |
| The script against the real account | `used 32.41 allowed 60.00 left 27.59 refresh 2026-11-21T00:00:00 UTC` |
| No secret printed or stored; the existing Kaggle token is used, no new credential (register unchanged) | yes |
| The rules fit the existing "a quota ... is raised before it is worked around" bullet, after it, not instead of it | yes |
| Wording, org references, benchmark order | pass |
| `ruff` | clean |

## Findings
### Blocking
None.
### Should fix
None.
### Minor
1. The refresh time comes back from Kaggle as a naive datetime; the script labels it UTC, which the API documents
   and the account's Settings page agrees with (Saturday 00:00). If Kaggle ever returns a zone, `isoformat()` shows it.
2. The cost of one 4×L4 run isn't in the README yet: the first measured run (PR 107's, label `pr107`) is running now.
   Add the number when it's in.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | |
| Synthetic only, no PHI | ✅ | No data |
| Test first | ✅ | |
| Configuration | ✅ | No setting added |
| Secrets register | ✅ | No new credential |
| Changes the rules | ⏸ | Waits for the owner's "merge" (Branches and issues, 6) |

## Verdict
Approve. The owner merges.
