---
pr: 765
branch: data/762-028-devset-prompt98-out8192
title: "028 CHORE7: record the development-set run of gemma-developer-agent main (PR 98's prompt with an 8,192-token output budget)"
author: jcbowyer
reviewed_at: 2026-11-15
reviewer: coordinator verification (data and README only), every figure recomputed from the four committed tables and the kernel's output
verdict: approve
---

# PR Review: 028 CHORE7: record the development-set run of gemma-developer-agent main (#762)

## Summary
Records the first run of the two single changes together: gemma-developer-agent `main` at `d13dc52` (PR 98's prompt,
PR 100's `max_output_tokens` 8,192), on the same 23 development tasks as the three runs before it. It resolved 4,
no run ended at the context window, and p = 1.0 against each earlier run. The README reports the one cost this pair
showed and the 8,192 run alone did not: an answer cut off at the limit. Approve.

## Scope of Change
- Files changed: 3 (README +~45 lines; a 23-row CSV; its settings JSON), plus this review
- Areas touched: data
- Range reviewed: `origin/main..HEAD`

## CI Status
| Check | Status |
|---|---|
| all | read on the head commit before merging |

## Secrets, PHI and Claims Scan
- Secrets: clean.
- PHI / real data: clean. Ids, verdicts, counts, seconds and error types only, as in the other development-set
  tables. The patch sizes and file names in the README describe the agent's own output; no patch content is committed.
- Organization claims: clean.

## Strengths
- Written by the runner on `main` with the fixes of #721 and #737: its own table, 8,192 in every row, the image pinned.
- The README corrects an earlier impression rather than leaving it: the 8,192 run's "no visible cost" is shown to hold
  for that run and not for this pair (`fastapi_14873`, the cut-off tool call).
- The four-way table and the three McNemar tests are recomputed from the committed tables, so each number can be
  checked from the repository; the per-call sizes and the scratch files name their source (the kernel's output).

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
1. The README's per-call sizes, the cut-off answer and the patch contents rest on the kernel's private output, which
   issue 720 deletes after judging. A column for each task's largest prompt and answer would keep them in the table.
2. The scratch files the agent leaves behind (`fastapi_14463`) are an agent change for gemma-developer-agent, not a
   change here.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | yes | |
| Synthetic only, no PHI | yes | competition ids and counts only |
| No organization claims | yes | |
| Test first | n/a | no behaviour change |
| Simulated is labelled simulated | yes | a measured run with its date, settings and approval |
| Every number from a run in the repo | yes | the tables; the per-call figures from the kernel's output, said so |
| Idempotent writes | yes | `write_table` merges by `instance_id` into its own table |
| Commits | yes | Closes #762, co-author trailer |
| Rule 6 (who merges) | yes | starts no run, publishes nothing outside the repository |

## Test Coverage
`test_official_agent`, `test_wording`, `test_no_org_references`, `test_bench_order`, `test_kaggle_dataset_docs` and
`test_deck_claims` pass on the branch (189).

## Verdict
Approve. Merge when CI is green.
