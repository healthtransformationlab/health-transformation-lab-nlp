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
  mean utilization 76%, 7.5 Wh a task. `estimated_cost_usd` is an estimate at the L4 price declared in
  `ops/cost_settings.yaml` since November 11, 2026 (0.83 USD a GPU-hour): 4.76 USD over the 40 tasks, 0.12 a
  task. Kaggle's GPUs were free; the estimate is what the same GPU time would cost to rent.

## What it is not

One sampled run per task at temperature 0.2. Twenty-three tasks: the interval reaches 32%. The 23 are the tasks a
Kaggle kernel can verify, 15 of them from rich, so they are not a sample of the 129. Not a leaderboard score: the
leaderboard's tasks are private.

# More context for the same agent: a pre-registered run on the 93 tasks (November 11, 2026)

Three arms of one experiment: the same agent on the published tasks, each time with a different text beside the
task (028 AI7, #674). The plan was written and hashed before any kernel started
(`specs/028-dataops-task-set/preregistration-failing-test-report.md`, SHA-256
`1b517ae1bb96d84d670ac6891542278275a0802a33ac57dae43c0c715e43d7c4`, recorded on issue 674 at 14:39 UTC; the
first kernel started at 14:42), and its addendum for the graph arm before that arm's kernel started and before
any outcome of the first two had been read (`preregistration-graph-retrieval-arm.md`, SHA-256
`7121f14cd2c28baaa63af5bbcc35d668edb1fe8843f0351005673819393a0f29`, recorded at 14:56 UTC). The owner asked for
the run, and for a controlled experiment on graph retrieval.

**In short.** The two arms with added context ran all 93 tasks and resolved 4 (`graph`) and 5 (`report`). The
`statement` arm, the baseline, lost its model server after 21 tasks, and the rerun the plan provides for could
not run, so the experiment cannot say whether either context helps: the paired tests have 21 pairs and nothing
resolved in them. Described only, as the plan names the core split: 7 of the 8 tasks either arm resolved are
among its 17 tasks.

| Arm | The task's text | Table |
|---|---|---|
| `statement` | as published | `gemma-4-e4b-it-qat-w4a16-ct_swegemma_statement.csv` |
| `graph` | as published, with the graph's retrieval after its hints: built from the statement and the graph alone | `gemma-4-e4b-it-qat-w4a16-ct_swegemma_graph.csv` |
| `report` | as published, with the failing test's report after its hints: built from the task's hidden test, so a test-first workflow's context and not a benchmark condition | `gemma-4-e4b-it-qat-w4a16-ct_swegemma_report.csv` |

Everything else is the same in every arm: the agent (`gemma-developer-agent` at `b95b235`),
`gemma-4-e4b-it-qat-w4a16-ct` served by vLLM on four L4 GPUs, swegemma 0.2.11's own agent loop, the agent's own
budgets (16,384 output tokens, a 4,096-token thinking budget, 40 tool calls, 5 minutes), one seeded order (seed
20261110), each task sealed until its turn, and no patch or tests beside the agent. Each patch was then verified
by the competition's own `verify_task` on the published snapshot with the task's tests
(`kaggle/official_verify.py`). The two contexts are built by `python/scripts/69_failure_report.py` and
`python/scripts/72_graph_context.py`; their text is not committed, their shapes are
(`data/tasks/failure_report_shape.csv`, `data/tasks/graph_context_shape.csv`), and each arm's `_settings.json`
gives its context file's SHA-256, which is the one its plan pinned. The report's list of functions is every
public function the task's test files called, passing tests included, in order of name and cut to the first 15
(the list is longer in 14 reports). The kernel's own trace of every task in the `graph` and `report` arms holds
the first line of that arm's context, and no trace holds the other arm's (checked on the kernels' output, which
is not committed).

## Result

| Arm | Run | Wrote a patch | **Resolved** | 95% Wilson interval | Core split: run | Core split: resolved |
|---|---|---|---|---|---|---|
| `statement` | 21 of 93 | 14 | **0** | 0.0 to 15.5% | 1 | 0 |
| `graph` | 93 of 93 | 62 | **4** | 1.7 to 10.5% | 17 | 4 |
| `report` | 93 of 93 | 70 | **5** | 2.3 to 12.0% | 17 | 4 |

The core split is the 17 tasks whose statements say what their tests check
(`data/tasks/screening/core_split.csv`, fixed by the screen of November 10).

## The `statement` arm: its kernel lost its model server

The kernel ran 21 tasks normally. From the next task in the seeded order on, a task made no model call and ended
at its 5-minute limit, and later on a connection error: the model server in that kernel had stopped answering,
and the kernel went on to its own deadline. By the plan's rule ("a task a kernel did not reach, or whose agent
phase did not start, is not run"), the 60 tasks with no model call and the 12 the kernel did not reach are not
run. They have no row; `gemma-4-e4b-it-qat-w4a16-ct_swegemma_statement_settings.json` lists all 72 with the
reason for each, how it ended and after how long (`not_run`): 33 at the 5-minute limit, 27 on a server error,
over 234 minutes of the kernel's time. This was recorded on issue 674 at 19:01 UTC, from the kernel's live log,
before the kernel ended and before any of its patches was verified.

"No model call, ended at the time limit or on a server error" is this project's reading of "agent phase did not
start", and it was written into the runner at 19:00 UTC, after the `report` arm had been collected (17:35 UTC)
and before the other two were. It cannot change what is claimed. Under the other reading, with all 72 counted as
tasks the baseline failed, `graph` would have 4 discordant pairs, all one way (p = 0.125) and `report` would
have 5 discordant pairs, all one way (p = 0.0625): still no difference at p < 0.05.

The plan provides one more kernel for such tasks, once, with the same settings and order. It was pushed at 19:30
UTC, and again at 19:33 to read the answer the first push's code had not kept. Kaggle refused it: "Maximum
weekly GPU quota of 30.00 hours reached." The account's weekly GPU allowance was spent, and it resets on
November 14, 2026. By the account's own quota readings (`kaggle quota`: 15.66 hours used at 14:46 UTC, 31.84 at
18:51 with two four-L4 sessions running almost throughout, 33.69 when both had ended) a four-L4 session counted
about two hours for each hour it ran, and the first kernel ran almost four hours with a dead server. So the
pairs below are the tasks both arms ran, and the rest are left out and counted, as the plan says. The rerun is
still owed: issue 681.

Three changes to the runner came out of it, each with a test. `kaggle/official_agent_run.py` applies the plan's
rule itself: a task with no model call has no row and is listed as not run. The kernel stops a batch when two
tasks in a row make no model call and end in an error (`server_gone`), so a dead server cannot spend hours of
the allowance again. And a kernel Kaggle refuses ends the run in Kaggle's own words (`push_kernel`).

## The paired tests

Each arm against `statement`, task by task (`context_pairs_<arm>.csv`, written by
`python/scripts/70_context_pairs.py`):

| Arm | Pairs | Left out | Both resolved | `statement` only | The arm only | Neither | Exact McNemar p, two-sided |
|---|---|---|---|---|---|---|---|
| `graph` | 21 | 72 | 0 | 0 | 0 | 21 | 1.00 |
| `report` | 21 | 72 | 0 | 0 | 0 | 21 | 1.00 |

**No difference detected, and none could have been.** No arm resolved any of the 21 tasks all three ran, so
there is no discordant pair for the test to count. The plan claims a difference only at p < 0.05, which needs at
least six discordant pairs all one way. Neither "graph retrieval helps" nor "the report helps" is claimed, and
neither is ruled out: the baseline is missing for 72 of the 93 tasks, among them 16 of the core split's 17.

## Described, not tested

The plan names these as descriptions. None is a test, and none is evidence that a context helped.

- **`graph` against `report`**, over the 93 tasks both ran: both resolved 1 (`htlnlp_144`), `report` only 4
  (`htlnlp_116`, `htlnlp_143`, `htlnlp_174`, `htlnlp_187`), `graph` only 3 (`htlnlp_111`, `htlnlp_226`,
  `htlnlp_pr31`), neither 85.
- **The core split.** `graph` resolved 4 of the 17 core tasks and 0 of the other 76; `report` 4 and 1. Between
  them the two arms resolved 8 different tasks, 7 of them core. The `statement` arm ran 1 core task.
- **Every `statement` run under these settings.** The run of November 10 took 20 tasks with the same agent and
  settings and resolved 0; today's arm took 21 and resolved 0. 4 tasks are in both, so that is 41 runs over 37
  tasks with nothing resolved. Those 37 hold 4 of the core split's 17 tasks. On the same 37 tasks `graph`
  resolved 1 (`htlnlp_pr31`) and `report` 0. The two days are not one run, so this is not a paired test.
- **The same tasks, resolved without either context.** Of the 8 tasks the two arms resolved, 6 had already been
  resolved from the statement alone by an earlier run under another harness, budget or checkpoint (`htlnlp_116`,
  `htlnlp_143`, `htlnlp_144`, `htlnlp_174`, `htlnlp_187`, `htlnlp_226`:
  `data/tasks/agent_runs/gemma-4-e4b-it_kaggle.csv`, `data/tasks/agent_reruns/gemma-4-e4b-it_graph_tools.csv`,
  `gemma-4-e4b-it_larger_budget.csv` and the pilot row of `gemma-4-e4b-it-qat-w4a16-ct_swegemma.csv`; the first
  three ran `gemma-4-e4b-it` on the local harness). So a task resolved in an arm is not shown to be one its
  context was needed for. Over every run of this model on these tasks, 9 different tasks have been resolved, 8
  of them in the core split.
- **On the 21 tasks all three arms ran**, a task took on average `statement` 9.9 tool calls, 125k prompt tokens
  and 105 agent seconds; `graph` 9.5 tool calls, 119k prompt tokens and 89 agent seconds; `report` 5.8 tool
  calls, 81k prompt tokens and 75 agent seconds. No arm resolved any of the 21, and one draw of 21 tasks does
  not say why the runs differ.

What the agent did in each arm, over the tasks it ran. `statement` is over its 21 tasks and the other two over
93, so the columns are not like for like; the line above sets the three arms on the same tasks.

| | `statement` | `graph` | `report` |
|---|---|---|---|
| Tasks run | 21 | 93 | 93 |
| Resolved | 0 | 4 | 5 |
| Tests fail with the agent's patch | 10 | 40 | 39 |
| Errors before any test ran, with the agent's patch | 4 | 18 | 26 |
| Empty patch | 7 | 31 | 23 |
| Tool calls | 207 | 710 | 707 |
| To a graph tool | 17 (8.2%) | 61 (8.6%) | 48 (6.8%) |
| To the analyzer sub-agent | 5 | 22 | 17 |
| Naming a path outside the workspace | 0 | 0 | 1 |
| Model calls | 256 | 916 | 909 |
| Prompt tokens a task | 125,365 | 102,788 | 101,302 |
| Output tokens a task | 6,224 | 4,715 | 4,857 |
| Agent seconds a task | 105 | 74 | 87 |
| Ended at the model's context window | 3 | 24 | 18 |
| Ended at the 5-minute limit | 1 | 1 | 1 |

## Where the time went, and the GPUs (spec 014 US6, 036 US2)

Each kernel kept the agent framework's OpenTelemetry spans (names, counts and seconds; no prompt or reply) and
sampled its GPUs every five seconds. `python/scripts/71_run_telemetry.py` rolls them up as self time, so each
second of a task is counted once (`..._sections.csv`, `..._task_sections.csv`, `..._gpu.csv` beside each arm's
table). The tables cover the tasks each arm ran, so `statement` covers its 21: again not like for like.

| Share of the tasks' time | `statement` | `graph` | `report` |
|---|---|---|---|
| model call | 82.8% | 76.5% | 66.3% |
| tool run_command | 2.6% | 7.8% | 17.3% |
| context compaction | 13.8% | 14.6% | 15.4% |
| harness (the evaluator's own work around the agent) | 0.62% | 0.90% | 0.78% |
| the three graph tools together | 0.02% | 0.02% | 0.02% |

| The tasks' own GPU time (loading the model is not in it) | `statement` | `graph` | `report` |
|---|---|---|---|
| Tasks | 21 | 93 | 93 |
| GPU-hours on the four L4s | 2.45 | 7.67 | 9.04 |
| GPU-seconds a task | 419 | 297 | 350 |
| Energy, Wh | 141 | 449 | 511 |
| Energy a task, Wh | 6.7 | 4.8 | 5.5 |
| Mean utilization | 86% | 86% | 79% |
| Estimated cost at 0.83 USD an L4 GPU-hour | 2.03 | 6.37 | 7.50 |
| Estimated cost a task, USD | 0.10 | 0.07 | 0.08 |

For each resolved task: `graph` 1.92 GPU-hours, 112 Wh and an estimated 1.59 USD; `report` 1.81 GPU-hours, 102 Wh
and an estimated 1.50 USD. `estimated_cost_usd` is the task's GPU-hours at the price `ops/cost_settings.yaml`
declares for an L4: the median on-demand price across providers for the week of October 26, 2026 at
getdeploying.com, the same week and figure as the T4's 0.69. Until November 11, 2026 the file declared no L4
price and the column was empty; the tables were rebuilt from the same kernels' saved output, and no other
column changed. Nothing was paid: Kaggle's GPUs were free, and these three kernels and the development-set run
before them used the account's whole weekly allowance. The estimate covers the tasks' own time, not the model's
loading or the hours the `statement` kernel ran with a dead server.

## The verifier on the collecting machine

The patches were verified on the machine that collected the kernels, where the competition's evaluator was
installed that day from its wheelhouse (`swegemma` 0.2.11, `adk-submission` 0.2.13, `adk-eval-core` 0.1.0).
Before any patch was scored, its two controls ran there on the published files (`context_run_controls.csv`: each
row is a line of `kaggle/official_verify.py --patch oracle` or `--patch null`, shaped by
`official_controls_run.row_for`; no single command writes the file): the reference patch resolved 93 of 93 and
an empty patch 0 of 93. That is the verdict of `data/tasks/official_verifier/published_verification.csv` in all
186 of 186 rows; the exit code is the same in 184 (the other 2, both empty patches, end in a failed test here
and in a collection error there). The `report` arm's patches were verified twice, in two collections of the same
kernel, with the same verdict on all 93.

The session's machine restarted at 17:03 UTC while the first two kernels were running. Kaggle's kernels were not
affected; each table was collected from its finished kernel afterwards (`kaggle/official_agent_run.py
--collect`), as each `_settings.json` says.

## What it is not

Not a test of either context against the baseline: that needs the `statement` arm on the tasks it did not run.
One sampled run per task and arm, at temperature 0.2, so a task resolved in one arm and not another can be the
arm or the draw. The `report` arm is not a benchmark condition: its context comes from the hidden test. Every
arm ran with 5 minutes and 40 tool calls a task, not the leaderboard's limits, on this project's own tasks: not
a leaderboard score.
