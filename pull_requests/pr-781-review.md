---
pr: 781
branch: docs/779-000-one-l4-for-mechanisms
title: "000 DOCS20: a run asking why the agent fails uses one L4 on Colab; Kaggle's four L4s only where the competition's hardware matters"
author: jcbowyer
reviewed_at: 2026-11-15
reviewer: coordinator verification of each figure against the committed tables (one rules bullet)
verdict: approve
---

# PR Review: 000 DOCS20: one L4 on Colab for runs asking why the agent fails (#779)

## Summary
Adds one rule to the GPU rationing in AGENTS.md: a run asking why the agent fails goes to one L4 on Colab, and a run
whose answer depends on the competition's hardware stays on Kaggle's four L4s. The evidence is cited and labelled as
not a controlled test, and the gap that keeps development-set runs on Kaggle for now is filed (#780). It changes the
rules, at the owner's request on November 15. Approve.

## Scope of Change
- Files changed: 1 (`AGENTS.md`, +14), plus this review
- Range reviewed: `origin/main..HEAD`

## CI Status
| Check | Status |
|---|---|
| all | read on the head commit before merging |

## Secrets, PHI and Claims Scan
Secrets: none. PHI or real data: none. Organization claims: none; Kaggle's and Colab's behaviour is described from our
own runs and the account's quota readings.

## Checks
| Check | Result |
|---|---|
| Resolved 4 (Kaggle `graph`, four L4s) and 8 (Colab `colab-graph-l4`, one L4), re-read from the two committed tables, 93 rows each | ok |
| 297 and 128 GPU-seconds a task, from the README's GPU tables; about 74 seconds a task on four L4s is 297 / 4, which matches the statement arm's 419 / 4 = 105 against its recorded mean agent time of 104.8 | ok |
| "Kaggle counts an hour on four L4s as two" matches the README's quota readings (November 11) and PR 107's run (61 minutes, 2.00 hours) | ok |
| Says it is not a controlled test, and what differs on Colab (Python, 9 of 41 packages), as the README's "What is as on Kaggle, and what is not" does | ok |
| The Colab path's limit is stated (published tasks only) with its action item (#780), so no session sends a development-set run to Colab before it can run there | ok |

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
1. The comparison mixes the published tasks with the rule's main use, the development set; #780's last item records one
   development-set run on both machines, which would test the rule where it is applied.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets, no PHI, no org claims | yes | |
| Every number from a run or a source | yes | committed tables and README; each cited |
| Commits | yes | Closes #779, trailer |
| Rule 6 (who merges) | yes | changes the rules; the owner asked for this rule on November 15 ("Do above and write in agent.md") |

## Test Coverage
`test_agent_docs`, `test_wording`, `test_no_org_references`, `test_bench_order`, `test_pr_conventions`: 106 passed.

## Verdict
Approve. Merge when CI is green.
