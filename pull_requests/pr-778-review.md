---
pr: 778
branch: data/777-028-devset-pr107
title: "028 CHORE9: record the development-set run of gemma-developer-agent PR 107 and its GPU-hour cost"
author: claude
reviewed_at: 2026-11-15
reviewer: coordinator verification against .claude/review-rubric.md
verdict: approve
---

# PR Review: record the PR 107 development-set run and its GPU cost

## Summary
Adds the runner's table and settings for gemma-developer-agent PR 107's run on the 23 development tasks, a README
section paired with main at 8,192, and the measured cost of a run in `kaggle/README.md`. Data and docs only.

## Checks
| Check | Result |
|---|---|
| Rows written by the runner (`--label pr107 --collect --reuse-output`) | yes |
| 23 rows, 4 resolved as the issue names; `max_output_tokens` 12288; one kernel URL that exists | yes |
| Agent commit in the settings is the one that ran (`5ce5f98`) | yes, after a correction: the runner read the branch's later merge commit at collect time. The README says so. |
| README numbers match both tables (reasons, calls, graph calls, context endings, discordant tasks) | recomputed |
| Quota cost from the readings before and after (`kaggle/gpu_quota.py`): 32.34 → 34.34 | yes |
| Task text not committed; traces stay on Kaggle | yes |
| Secrets, PHI, claims | clean; not a leaderboard score |

## Findings
### Blocking
None.
### Minor
1. The runner's collect mode records the agent folder's current commit, not the one the kernel ran. Worth a fix in
   the runner (read the commit from the bundle the kernel used); a separate issue.

## Verdict
Approve. Merge when CI is green.
