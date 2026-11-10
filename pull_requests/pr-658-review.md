---
pr: 658
branch: feat/636-028-official-agent-run
title: "028 T011b: the agent run end to end by the competition's own evaluator (0 of 20 sampled tasks)"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-10
reviewer: the authoring session (the table was recomputed from the kernels' outputs and the evaluator's verdicts; no reviewer subagent run)
verdict: approve
---

# PR Review: 028 T011b: the agent run end to end by the competition's own evaluator (0 of 20 sampled tasks)

## Summary
Runs the agent under the competition's evaluator on a seeded, stratified sample of 20 published tasks and records the
result: 0 resolved. The code, the table, its settings and an account of the run. Nothing blocking.

## Checks
| Check | Result |
|---|---|
| The numbers come from a run | 21 private Kaggle kernels on November 10, 2026; each row's `kaggle_kernel_url`, `run_ts` and `script_seconds` |
| The harness is the competition's | the kernel calls `swegemma.evaluate.Evaluator.evaluate_task` and serves the model with `adk_submission.VllmServer`, as the starter notebook does; `versions` in the settings: swegemma 0.2.11, vLLM 0.19.1 |
| The sample is not chosen by cost | `sample()` uses only the seed and the tiers; a test checks the stratification (9, 7, 4 for 39, 34, 20) and that input order does not matter; the 20 ids are in the settings |
| 0 of 20 | `is_resolved` false for all 20 `is_in_sample` rows; 11 `tests fail`, 5 `errors before any test ran`, 4 `empty patch` |
| The failures are real | the evaluator's output for the 16 patches: failing assertions (most with other tests passing), two syntax errors in the model's code, two missing imports and a missing file. No patch failed to apply |
| The verdict is the evaluator's | `_verify` runs `kaggle/official_verify.py`, whose `verify_task` resolves all 93 reference patches on the same files (`official_verifier/published_verification.csv`) |
| No answers on the GPU machine | the bundle's `tasks.jsonl` has no `patch` or `test_patch` (tested), the kernel refuses a bundle that has one, one task per kernel, internet off |
| Budgets did not decide it | longest agent phase 238 s of 300; most tool calls 22 of 40 |
| Tool counts | from the evaluator's own trace: 9 graph-tool calls in 4 runs, 3 sub-agent calls, 0 skill calls, 0 calls naming a path outside the workspace (text the model writes into a file is not counted as a path) |
| The prompt defect | three first-pass rows in `_hints_defect.csv`: 0 model calls, "Context variable not found: `hints`"; fixed in gemma-developer-agent pull request 34 before the affected tasks ran; the settings' notes say which tasks ran on which side of the fix |
| Mixing two submission commits | for a task with hints `{hints}` and `{hints?}` render the same prompt, so the nine first-pass rows stand |
| The pilot is kept apart | `is_in_sample` false; chosen because the model had resolved it before; in no rate |
| Written rules | spec first (028 US5 gets the run's design); tests first; a GPU run with the owner's go-ahead; typed column names; rows in their own folder, since `agent_runs/` feeds a gold table defined as our harness |
| Tests and lint | 503 passed, 2 skipped; ruff clean on the new files |
| Branch name and issue link | `feat/636-028-official-agent-run`, `Closes #636` |

## Should fix later
- The 21 private kernels and 21 private datasets the run left on Kaggle are the evidence behind the rows. Keep them
  until the paper is judged; deleting them is the owner's call.
- The sealed batch mode is tested and dry-run but has never run on Kaggle.
- The competition's defaults give an agent 60 minutes and 100 tool calls; this run used the submission's 5 and 40. No
  run reached either, but a run at the defaults would remove the question.
- `script_seconds` is the kernel script's own time; Kaggle's charge per session (boot and shutdown included) is higher.

## Secrets, PHI and Claims Scan
Secrets: none; the Kaggle token is read from the environment and never printed, and the batch key is generated per
run and never written to the repository or a dataset. PHI or real notes: none. Claims: 0 of 20 with its interval, the
tool counts, the defect, all from committed tables.
