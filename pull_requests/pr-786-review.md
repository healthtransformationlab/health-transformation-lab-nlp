---
pr: 786
branch: feat/780-028-colab-devset
title: "028 AI13: run the competition's development set on Colab's one L4"
author: claude (implemented by a subagent, reviewed by the coordinator)
reviewed_at: 2026-11-15
reviewer: coordinator verification against .claude/review-rubric.md
verdict: approve
---

# PR Review: run the competition's development set on Colab's one L4

## Summary
`colab_official.fetch_competition_files` fetches the drawn tasks' competition files onto a Colab machine and lays them
out where the kernel finds a Kaggle mount; the runner marks a Colab development batch's order and settings. No new
options. Nothing blocking.

## Checks
| Check | Result |
|---|---|
| Issue #780's four parts written first; dated line added for the function's name | yes |
| Test first: 7 new tests failed, then passed; 121 pass on the rebased branch | yes |
| Only what a batch needs is fetched (selection tested on a stub listing; 196 files, 3.69 GB for 23 tasks by a read-only listing) | yes |
| Layout matches the kernel: a test runs the kernel's own `find_competition` on the fetched tree | yes |
| Deletions confined to the batch's folder on the Colab machine (`snapshots`, `graphs`, `embeddings` not in this batch) | yes |
| Secrets: the token arrives through the Kaggle API from the notebook's Colab Secret; the function never reads the environment; a test checks the log | yes |
| Kaggle path unchanged: the kernel ignores the new `competition` key; settings text differs only when `--colab` | yes |
| No task text or reference patch committed | yes |
| `ruff`: no new findings | yes |

## Findings
### Blocking
None.
### Minor
1. As on a Kaggle mount, the Colab machine holds all of `tasks.jsonl`, reference patches included; the kernel still
   stages only the task without its patch for the agent. Same exposure as Kaggle's.
2. `--competition` stays required with `--source competition`; the issue's line left it out. Kept, since it names
   what is fetched; the dated line says so.
3. The AGENTS.md sentence "until then a development-set run stays on Kaggle" becomes stale on merge; it changes in a
   separate PR because rule changes wait for the owner.

## Verdict
Approve. Merge when CI is green. It starts no run; the owner opens the first Colab run.
