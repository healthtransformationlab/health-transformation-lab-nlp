---
pr: 745
branch: data/744-028-devset-max-output-8192
title: "028 CHORE6: record the development-set run of gemma-developer-agent PR 100's output budget"
author: jcbowyer
reviewed_at: 2026-11-15
reviewer: coordinator verification (data and README only), every figure recomputed from the committed tables and the kernel's traces
verdict: approve
---

# PR Review: 028 CHORE6: record the development-set run of gemma-developer-agent PR 100's output budget (#744)

## Summary
Records one run: gemma-developer-agent PR 100 (`max_output_tokens` 8,192), through the competition's evaluator, on
the 23 development tasks that pass both controls, paired with the November 11 run. It adds the 23-row table, its
settings and a README section. Resolved 3 against 3 (one each way, exact McNemar p = 1.0), and no run ended at the
context window against 3. The README claims no difference in resolved tasks. Approve.

## Scope of Change
- Files changed: 3 (README +~40 lines; a 23-row CSV; its settings JSON), plus this review
- Areas touched: data
- Range reviewed: `origin/main..HEAD`

## CI Status
| Check | Status |
|---|---|
| all | read on the head commit before merging |

## Secrets, PHI and Claims Scan
- Secrets: clean.
- PHI / real data: clean. The table holds the competition's task ids, verdicts, counts, seconds and the evaluator's
  error type, as the November 11 and PR 98 tables do; no statement, patch or test output. The traces the per-call
  sizes come from are not committed, because they hold the competition's task text.
- Organization claims: clean.

## Strengths
- Written by the runner itself, not by hand: `--label` (#721) gave the run its own table, and `--collect` with the fix
  of #737 records the submission's 8,192 in every row, with the evaluator's fallback kept in the settings.
- The README separates what is tested (resolved: no difference) from what is described (the context-window endings,
  the largest prompt and answer), and says the setting and PR 98's prompt were not run together.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
1. The README cites the fix of #737, which is pull request 740; merge that first so the cited code is on `main`.
2. The per-call sizes (largest prompt 17,155, largest answer 4,813, 418 calls) rest on the kernel's output on Kaggle,
   which is private and is to be deleted after judging (#720). If they are wanted later, a column of each task's
   largest prompt would keep them in a table.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | yes | |
| Synthetic only, no PHI | yes | competition ids and counts only, as before |
| No organization claims | yes | |
| Test first | n/a | no behaviour change |
| Simulated is labelled simulated | yes | a measured run, with its date, settings, approval and the failed first attempt |
| Every number from a run in the repo | yes | the table and settings; the per-call sizes from the kernel's traces, said so |
| Idempotent writes | yes | `write_table` merges by `instance_id` into its own table |
| Commits | yes | Closes #744, co-author trailer |
| Rule 6 (who merges) | yes | starts no run, publishes nothing outside the repository |

## Test Coverage
`test_official_agent`, `test_wording`, `test_no_org_references`, `test_bench_order`, `test_kaggle_dataset_docs` and
`test_deck_claims` pass on the branch (187).

## Verdict
Approve. Merge after pull request 740, when CI is green.
