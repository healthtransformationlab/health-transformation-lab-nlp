---
pr: 726
branch: data/725-028-devset-prompt97
title: "Record the development-set run of the agent's localize-first prompt"
author: claude
reviewed_at: 2026-11-14
reviewer: coordinator verification (data and README only)
verdict: approve
---

# PR Review: Record the development-set run of the agent's localize-first prompt

## Summary
This PR records one run: gemma-developer-agent PR 98's prompt, through the competition's own evaluator, on the 23
development tasks that pass both controls. It adds a table of 23 rows, its settings and a README section with the
paired result. The verdicts match the runner's own end-of-run output: 4 of 23, the same tasks. The README claims no
difference (exact McNemar p = 1.0) and keeps what changed as described, not tested. The November 11 table is untouched.
Verdict: approve.

## Scope of Change
- Files changed: 3 (README +~35 lines; a 23-row CSV; its settings JSON)
- Areas touched: data
- Range reviewed: `origin/main..HEAD`

## CI Status
| Check | Status |
|---|---|
| all | running at review time |

## Secrets, PHI and Claims Scan
- Secrets: clean.
- PHI / real data: clean. The table holds the competition's task ids, verdicts, counts, seconds and the evaluator's
  error type. It holds no statement, patch or test output, as for the November 11 table. Four `error_text` cells hold
  the model server's context-window error, as the November 11 table's do.
- Organization claims: clean.

## Strengths
- The comparison is paired on identical tasks, settings and evaluator, so the 3-against-4 difference is read with the
  right test, and the README doesn't overclaim.
- The rows come from the runner's own functions, not a hand transcription.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
1. `settings_for` records the kernel's image as a sentence, not the digest, because the run reused the kernel created
   with the starter's pin and the runner was given no `--docker-image`. The November 11 settings name the digest; the
   two runs used the same kernel. Acceptable as written.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | |
| Synthetic only, no PHI | ✅ | Competition ids and counts only, as before |
| No organization claims | ✅ | |
| Test first | n/a | No behaviour change |
| Simulated is labelled simulated | ✅ | A measured run, labelled with its date, settings and approval |
| Idempotent writes | ✅ | `write_table` merges by `instance_id` into its own table |
| Commits | ✅ | Closes #725, co-author trailer |

## Test Coverage
`test_official_agent`, `test_colab_official`, `test_kaggle_dataset_docs`, `test_deck_claims`, `test_wording`,
`test_no_org_references` and `test_bench_order` pass on the branch.

## Verdict
Approve. Merge when CI is green: it starts no run and publishes nothing outside this repository.
