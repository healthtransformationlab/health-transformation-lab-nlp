# The agent run by the competition's own evaluator (November 10, 2026)

`gemma-4-e4b-it-qat-w4a16-ct_swegemma.csv` has one row per task that the Gemma 4 Developer Agent competition's
evaluator ran end to end: its agent loop (`swegemma` 0.2.11, `Evaluator.evaluate_task`, subprocess sandbox), its
model server (vLLM 0.19.1 from the competition's wheelhouse dataset) and its verification (`verify_task`), following
the competition's starter notebook. Kaggle gave each kernel four L4 GPUs, the competition's hardware. The budgets are
the submission's own (`eval_config.yaml`, `configs/sampling.yaml`): 40 tool calls, 5 minutes, 60 turns, 120 seconds
per command, 16,384 output tokens, a 4,096-token thinking budget. `_settings.json` holds every setting, the versions,
and each budget that differs from the competition's defaults.

Every other agent number in this repository comes from `htlnlp-harness-v1`, our re-implementation
(`../agent_runs/`). These rows do not.

## The sample

20 of the 93 published tasks, drawn with seed 20261110 and stratified by fidelity tier in proportion to the published
set (A 9, B 7, C 4): `kaggle/official_agent_run.py --sample 20 --seed 20261110`. Nothing about a task's cost or size
decides the draw or the order. `is_in_sample` is false for one more row, the pilot `htlnlp_143`, which was chosen
because the model had resolved it before; it is not part of any rate below.

## Result

| | Tasks | Wrote a patch | Resolved |
|---|---|---|---|
| The sample | 20 | 16 | 0 (0%, 95% Wilson interval 0 to 16.1) |
| The pilot, outside the sample | 1 | 1 | 1 |

Of the 16 patches, 11 fail the target tests and 5 raise an error before any test runs (two syntax errors in the
model's own code, three imports or files the tests need and the patch does not provide). Four runs submitted nothing.
No run reached its time budget (the longest took 238 of 300 seconds) or its 40 tool calls, so the budgets did not
decide the outcome.

What the model did with what it was given, over the 20 runs and 189 tool calls: it called a graph tool 9 times in
4 runs, the analyzer sub-agent 3 times in 3 runs, and a skill never. No tool call named a path outside the
workspace.

Eleven of the 20 had also been run on `htlnlp-harness-v1` with tighter settings (`../agent_runs/`); it resolved none
of them either.

## Keeping answers from the model

Each task ran alone in a private, offline kernel beside a private dataset holding that task only, in the evaluator's
own layout with no `patch` and no `test_patch` (`kaggle/official_agent_bundle.py`). So the evaluator's verification
had no tests on that machine. The patch came back and the same evaluator's `verify_task` scored it here against the
published snapshot and the task's tests, the call `kaggle/official_verify.py` makes.

## A defect the run found in the submission

The submission's prompt used `{hints}`. The evaluator sets that variable only for a task that has hints, and its
agent framework ends the agent on a variable that is not set. In the first pass three sampled tasks without hints
ended before the first model call (`_hints_defect.csv`: 0 model calls, 1.2 to 1.4 seconds, "Context variable not
found: `hints`"). The run was stopped and the prompt fixed to the framework's optional form, `{hints?}`
(gemma-developer-agent issue 33). The ten sampled tasks without hints, and one not yet run, then ran with the fix;
the nine with hints had already run, and for them both forms render the same prompt. 48 of the 93 published tasks
have no hints. `htlnlp-harness-v1` had hidden the defect: it fills a missing variable with an empty string
(spec 035, known differences).

## What it cost

The 21 kernels in the table ran for 3.2 hours in all, on four L4s each: 12.8 GPU-hours. With two earlier pilots
whose model server did not start and the first pass's three stopped tasks, the whole run used about 7.4 hours of the
Kaggle account's weekly 30-hour GPU allowance (Kaggle's own quota reading, before and after).

## What it is not

One sampled run per task at temperature 0.2. Twenty tasks: the interval reaches 16%. The evaluator's two phases ran
on different machines, as described above. This is not a leaderboard score: the leaderboard's tasks are the
competition's own.
