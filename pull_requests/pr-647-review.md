---
pr: 647
branch: data/644-028-published-set-verified
title: "028 T016: the published set, checked with the competition's evaluator as published"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-10
reviewer: the authoring session (the check was run by this session on the downloaded files; no reviewer subagent run)
verdict: approve
---

# PR Review: 028 T016: the published set, checked with the competition's evaluator as published

## Summary
Records the competition's verification on dataset version 4 as downloaded: the reference patch resolves 93 of 93 and
an empty patch 0 of 93. Refreshes the snapshot index and one line of the card. Nothing blocking.

## Checks
| Check | Result |
|---|---|
| The numbers come from a run | `published_verification.csv`, 186 rows: 93 `reference` rows all resolved with exit code 0; 93 `empty` rows none resolved (61 exit code 1, 32 exit code 2). Written from the driver's own output |
| The files checked are the published ones | downloaded with the Kaggle command line after the workflow finished; `tasks.jsonl` has 93 rows and their ids equal the 93 the committed table vouches for; nothing was added to a snapshot |
| The evaluator is unmodified | `kaggle/official_verify.py` on `main` calls `swegemma.harness.verification.verify_task` as shipped (0.2.11), subprocess sandbox |
| Snapshot index | 114 rows as before; `base_commit`, `redacted_paths` and `withheld_paths` unchanged in every row; heads and trees new in every row; all 93 published snapshots have the head and tree the index gives, one commit, and the root `conftest.py` |
| `size_bytes` | from the published files for 93 rows and from the rebuild for 21; said in the README, since sizes differ by a few bytes between builds |
| Card | the licence line is accurate for the commits the snapshots hold and no longer reads as contradicting the repository's licence |
| Written rules | no change to a dataset's rows, a metric or a rule beyond what spec 028 US6 planned (T016); the new table is not a published file, so `kaggle/dataset_docs.yaml` needs no entry |
| Tests | 142 passed, 1 skipped in the task-set, publishing, docs, wording and name tests |
| Branch name and issue link | `data/644-028-published-set-verified`, `Closes #644` |

## Should fix later
- The card's new wording is not on Kaggle until the next publish or metadata refresh. That is the owner's call
  (it publishes outside the repository).

## Secrets, PHI and Claims Scan
Secrets: none. PHI or real notes: none. Claims: one added (93 of 93 and 0 of 93 on the published files), from the
committed table.
