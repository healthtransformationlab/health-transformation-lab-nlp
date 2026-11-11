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

# The competition's own development set: the controls (November 11, 2026)

Before an agent's verdict on a development task in a Kaggle kernel can be read, the same verification must resolve
the task with its reference patch and fail it with an empty one, as our own tasks were checked (spec 028, #668).
`devset_controls.csv` holds both for the seeded 40 the agent runs on: `kaggle/official_controls_run.py` ran
`kaggle/official_verify.py`, the evaluator's `verify_task` unmodified, in a private CPU kernel with the competition
attached, from the competition's own folder, and the same pinned image as the agent's run. No model, no GPU.

| Patch | Resolved |
|---|---|
| The reference patch | 24 of 40 |
| An empty patch | 1 of 40 (`fastapi_14851`) |

So 23 of the 40 can be verified in a Kaggle kernel: the reference patch passes and an empty one fails. The agent's
result on the development set is counted over those 23, as ours is over the 93 that pass both controls. Of the 16
whose reference patch fails, 12 (fastapi) stop before any test runs (exit code 2, an error collecting the tests), 3
(requests) pass 135 or 136 tests and error in 185 to 187, and 1 (requests) fails one assertion. The table keeps ids,
verdicts, exit codes and seconds only, never the competition's test output.

The cause is in the kernel's own log. For every task the evaluator's sandbox reported that it could not add pip to
its environment (`ensurepip unavailable ... creating venv without pip`), and the competition's `sandbox/setup.py`
installs a task's dependencies with pip. Seven of the fastapi tasks' outputs name the test library they lack
(`inline_snapshot` in six, `dirty_equals` in one); for the other nine tasks the cause is inferred, not read.

A participant reported the same on the competition's Paper Track forum on October 27, 2026 (topic 753370): 27
fastapi tasks that no patch can resolve in the provided sandbox, for want of those two libraries. Ten of the 12
here are on that list. The host replied that scoring uses private repositories and does not include these tasks.

# The competition's own development set: the agent's run (November 11, 2026)

The same agent, settings and evaluator as the run above, on a seeded 40 of the competition's 129 development tasks
(028 AI4, #668): `kaggle/official_agent_run.py --source competition --sample 40 --seed 20261110 --batch --telemetry`,
with the owner's go-ahead. The draw is stratified by repository (fastapi 21, rich 15, requests 4; httpx's one task
gets no place). One private kernel on four L4 GPUs attached the competition and read each task from its mounted
files, with no reference patch beside the agent; the evaluator verified each patch there with the task's tests, as
the competition's own run does. `gemma-4-e4b-it-qat-w4a16-ct_swegemma_devset.csv` has one row per task. The tasks are the competition's:
the tables hold ids, counts and verdicts, never a statement, a patch or test output.

| | Tasks |
|---|---|
| Run | 40 of 40, in one kernel of 94 minutes (71 of them the agent's own; model load 353 s) |
| Can be verified in a Kaggle kernel (the controls above) | 23: rich 15, fastapi 8 |
| **Resolved, of those 23** | **3** (`fastapi_14301`, `rich_3454`, `rich_3535`); 95% Wilson interval 4.5 to 32.1% |
| Tests fail with the agent's patch | 10 |
| Empty patch | 5 |
| Errors before any test ran | 3 |
| The tests ran out of time (exit code 124) | 2 |

The other 17 rows are kept and not counted: the 16 whose reference patch fails in the kernel, and `fastapi_14851`,
which the kernel's verification passes with an empty patch (its row says resolved; it is not).

Against this project's own tasks under the same evaluator (0 of 20 above, 3 of 23 here), Fisher's exact test,
two-sided, gives p = 0.24: two samples this small cannot tell the sets apart by resolved tasks.

What the agent did, over all 40: 439 tool calls, 83 of them to a graph tool
(19%, against 9 of 189 on this project's tasks), 28 to the analyzer sub-agent, none to a
skill, and none naming a path outside the workspace (`outside_workspace_call_count` is 0 in every row). 8 runs
ended when a prompt passed the model's 32,768-token window less its 16,384 output tokens, and 2 at the 5-minute
limit (`error_text`). A task
took 106 agent seconds on average (the longest 306), 120,722 prompt tokens and 6,871 output tokens.

## Where the time went, and the GPUs (spec 014 US6, 036 US2)

The kernel kept the agent framework's OpenTelemetry spans (names, counts and seconds; no prompt or reply) and
sampled its GPUs every five seconds. `python/scripts/71_run_telemetry.py` rolls them up as self time, a span's
time less its children's, so each second of a task is counted once:

| Code section | Share of the tasks' time | Spans | Seconds |
|---|---|---|---|
| model call | 62.9% | 572 | 3,249 |
| harness | 19.9% | 40 | 1,026 |
| tool run_command | 10.1% | 55 | 521 |
| context compaction | 6.6% | 39 | 340 |
| tool search_similar_code | 0.3% | 42 | 17 |
| tool get_code_neighbors | 0.1% | 37 | 6 |
| agent data_pipeline_fixer | 0.1% | 72 | 5 |

The rest (agent code_analyzer, tool submit_patch, tool edit_file, tool read_file, agent loop, tool write_file, tool get_code_subgraph, tool code_analyzer, tool get_status) is under 0.05% each.
"harness" is the evaluator's own work around the agent: setting up the sandbox and verifying the patch. The model
calls took 9,657,738 input tokens and 549,676 output tokens in 572 calls.

- `..._task_sections.csv`: the same for each task (427 rows).
- `..._gpu.csv`: each task's seconds, GPU-hours, mean utilization, peak memory and energy. Over the 40 tasks:
  5.74 GPU-hours on the four L4s (the tasks' own time; loading the model is not in it), 301 Wh,
  mean utilization 76%, 7.5 Wh a task. `estimated_cost_usd` is empty: `ops/cost_settings.yaml`
  declares a price for a T4 hour and none for an L4, and no number is given a price it does not have.

## What it is not

One sampled run per task at temperature 0.2. Twenty-three tasks: the interval reaches 32%. The 23 are the tasks a
Kaggle kernel can verify, 15 of them from rich, so they are not a sample of the 129. Not a leaderboard score: the
leaderboard's tasks are private.
