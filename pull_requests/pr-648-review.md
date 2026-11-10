---
pr: 648
branch: data/569-036-gemma-early-tasks-rerun
title: "035 US2: the early tasks rerun with the code graph, and both runs kept side by side"
author: Claude Code (agent session for jcbowyer); the run table's rows are the Kaggle workflow's own commit
reviewed_at: 2026-11-10
reviewer: the authoring session (the paired figures were recomputed from the two states of the run table and the saved transcripts; no reviewer subagent run)
verdict: approve, held for the owner
---

# PR Review: 035 US2: the early tasks rerun with the code graph, and both runs kept side by side

## Summary
Records the rerun of 28 early tasks on the fixed harness and keeps each task's first run beside its rerun. On the 23
published tasks the model resolved 2 both times. Nothing blocking in the change itself. It is held for the owner
because it replaces rows the paper's Section 6 cites.

## Checks
| Check | Result |
|---|---|
| The rows are a run's | the workflow's commit `daae471` (run 42742256439); 28 rows have a new `run_ts`, the other 30 are untouched |
| Same model and settings in both runs | `gemma-4-e4b-it_kaggle_settings.json` unchanged; each rerun's `result.json` lists the three graph tools among its tools |
| First-run columns are the earlier rows | taken from the run table at `db0a29d`; every one has a `run_ts` before the fix of #621 |
| Paired figures | 23 published tasks: resolved 2 and 2 (`htlnlp_144` lost, `htlnlp_226` gained, `htlnlp_pr63` both); patches 18 and 20; mean GPU-hours 0.211 and 0.352 |
| Graph-tool calls | counted from the transcripts: 6 calls (all `search_similar_code`) in 4 of 23 runs; the 23 rows' `tool_call_count` sums to 145 |
| The evaluator's verdicts | 23 rows added to `published_verification.csv`: 2 resolved, the same verdict as our harness on all 23 |
| The claim is no wider than the evidence | the README says one sampled run per condition, "no measurable difference", and that it does not measure a model prompted to use the tools |
| The overall baseline | with the rerun rows, 5 of the 48 published tasks attempted are resolved (10.4%), as before |
| Cost | the 28 reruns used 9.64 GPU-hours (4.82 allowance hours), under the 5-hour cap the run was given |
| Written rules | a rerun replaces its row (spec 036); the new folder keeps the replaced runs and is not read by `grader_tables`, so no gold table changes shape; column names follow the typed suffixes |
| Tests | 476 passed, 2 skipped in the run-table, cost, task and Kaggle tests |
| Branch name and issue link | `data/569-036-gemma-early-tasks-rerun`, `Refs #544`, `Refs #569` |

## Should fix later
- Five of the 33 tasks given were not rerun (`htlnlp_116`, `155`, `244`, `pr33`, `pr47`). Running them is a GPU run and
  waits for the owner.
- `data/tasks/agent_reruns/` was built by hand from committed rows and transcripts. If reruns become routine, the
  runner should write the replaced row there itself.
- The run recreated private Kaggle datasets (`htlnlp-agent-htlnlp-*`), one per task. Deleting them is the owner's call.

## Secrets, PHI and Claims Scan
Secrets: none. PHI or real notes: none. Claims: the paired result and the tool-use count, both from committed tables.
