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

# The experiment again on Colab: the baseline, graph retrieval and the failing test's report (November 12, 2026)

The experiment above could not test either context: its baseline arm lost its model server after 21 tasks, and
Kaggle refused the rerun. The owner asked whether it could be finished on Colab (028 AI9, #687). Running the
missing 72 tasks there would have put two machines inside one arm, so the arms were run again whole, on one Colab
machine: a new comparison inside one environment. Its counts are never added to the Kaggle arms', and the Kaggle
baseline's rerun is still owed (issue 681).

Two addenda to the plan fix it, each hashed and recorded on issue 687 before the runs it covers:

| Addendum | Registers | SHA-256 | Recorded (UTC) | Its first task started (UTC) |
|---|---|---|---|---|
| 2, `specs/028-dataops-task-set/preregistration-colab-paired-run.md` | `colab-statement`, then `colab-graph`, on all 93 tasks, and one paired test | `312041e89860d9fcb05ec57312231275178652ba6d7a0fd3499af7ced5fd2fc9` | November 11, 23:51 | November 12, 02:04 |
| 3, `specs/028-dataops-task-set/preregistration-colab-report-arm.md` | `colab-report`, third on the same machine, and one paired test | `0532820a9e221d60cda0299143f6e3a50c1cc937ebad19bc391fb15ee56ff5cf` | November 12, 05:01 | November 12, 06:10 |

Addendum 3 followed an outside review of the paper that the owner passed on. It recommends the three conditions
on one Colab GPU configuration, the third "only if compute and time remain". The addendum was frozen when the
baseline's outcome was known (4 of 93) and while the graph arm was running, with none of its patches verified.

**In short.** On one A100 the baseline resolved 4 of 93 tasks and graph retrieval 6, and the failing test's
report 4. Neither context differs from the baseline by its registered test (exact McNemar, two-sided: p = 0.5 for graph
retrieval, p = 1.0 for the report), so neither "graph retrieval helps" nor "the report helps" is claimed, and
neither is ruled out at this size. A second session ran the same two arms on an L4 at the same time: its baseline
resolved 5 and its graph arm 8 (p = 0.375; unplanned, so described and not tested). The two runs of the baseline
differ on 3 resolved tasks; on the A100, graph retrieval and the baseline differ on 2. Described only, as the plans
name the core split: over the 5 runs its 17 tasks were resolved 26 times in 85 task-runs, and the other 76 tasks 1
time in 380 (`htlnlp_116` in `colab-graph-l4`).

| Run | The task's text | Machine | Table |
|---|---|---|---|
| `colab-statement` | as published | one NVIDIA A100-SXM4-40GB | `gemma-4-e4b-it-qat-w4a16-ct_swegemma_colab-statement.csv` |
| `colab-graph` | as published, with the graph's retrieval after its hints: addendum 1's context file, byte for byte | the same notebook session, second | `gemma-4-e4b-it-qat-w4a16-ct_swegemma_colab-graph.csv` |
| `colab-report` | as published, with the failing test's report after its hints: the first plan's context file, byte for byte. Built from the task's hidden test: a test-first workflow's context, not a benchmark condition | the same notebook session, third | `gemma-4-e4b-it-qat-w4a16-ct_swegemma_colab-report.csv` |
| `colab-statement-l4` | as published | one NVIDIA L4, a second session (below) | `gemma-4-e4b-it-qat-w4a16-ct_swegemma_colab-statement-l4.csv` |
| `colab-graph-l4` | as published, with the graph's retrieval: the same sealed bundle as `colab-graph` | the same L4 session, second | `gemma-4-e4b-it-qat-w4a16-ct_swegemma_colab-graph-l4.csv` |

## What is as on Kaggle, and what is not

As on Kaggle: the tasks (dataset version 4), the agent (`gemma-developer-agent` at `b95b235`),
`gemma-4-e4b-it-qat-w4a16-ct` served by vLLM 0.19.1, swegemma 0.2.11's own agent loop, the agent's own budgets
(16,384 output tokens, a 4,096-token thinking budget, 40 tool calls, 5 minutes), the one seeded order (seed
20261110), each task sealed until its turn, no patch or tests beside the agent, the two context files, and each
patch verified afterwards by the competition's own `verify_task` on the collecting machine. The versions each run
recorded are the Kaggle arms': swegemma 0.2.11, adk-submission 0.2.13, adk-eval-core 0.1.0, google-adk 1.36.1,
vLLM 0.19.1, transformers 5.13.1, torch 2.10.0 (Kaggle's build is tagged `+cu128`), litellm 1.82.4. Each arm is one
process with its own model server.

Not as on Kaggle:

- **One GPU, not four.** One A100 with 40 GB (the second session: one L4 with 23 GB), `bfloat16`,
  `tensor_parallel_size` 1. A model call takes a different time than on Kaggle's four L4s, and each task still has
  its 5 minutes, so a task can end differently here for that reason alone. All arms on one machine share it.
- **Colab's image, not Kaggle's pinned one.** Its Python is 3.13.16, and 9 of the wheelhouse's 41 wheels are
  compiled for 3.12 alone. Those nine packages stay at the versions PyPI gave: apache-tvm-ffi 0.1.16 (wheelhouse
  0.1.13.post3), cbor2 6.2.1 (6.1.4), ijson 3.6.0 (3.5.1), msgspec 0.22.0 (0.21.1), nvidia-cudnn-frontend 1.18.0
  (the same), outlines_core 0.2.11 (the same), pybase64 1.5.2 (1.5.0), setproctitle 1.3.8 (1.3.7) and xgrammar
  0.2.9 (0.2.5.post1). The model server and the agent framework are installed from PyPI at the versions the Kaggle
  kernels recorded, and the wheelhouse is installed over them by the kernel, as on Kaggle.
- **The Docker SDK** is installed from PyPI: the evaluator imports it even for its subprocess sandbox. No
  container is started.
- **A network.** A Colab machine has one. The kernel's process starts with no credential and with every proxy
  pointed at a port nothing listens on, and every command the agent ran is read afterwards for a reach at the
  network (`network_command_count` in `kaggle/colab_official.py`: a download tool, an installer, git over a
  remote). The counts are with the paired tests below.
- **Three changes to the kernel file**, listed on issue 687 before the first arm started, as addendum 2 allows for
  what a test run shows is needed (`kaggle/official_agent_kernel.py` at `db7e928`, SHA-256
  `6f2500defeeb91ffa96cd048675b2b3aab418405cf2b483bbf05a74007dcc649`; the addendum had pinned `26209de7…`). It
  reads where its inputs are from `HTL_INPUT`, because Colab has a read-only `/kaggle/input` of its own. It leaves
  out a wheel whose file name says it does not fit this Python. And a batch that starts again keeps the tasks an
  earlier start finished and runs the rest, because the owner ran the notebook from a phone. On Kaggle none of the
  three changes what a kernel does.

Five test starts came first, all on one task (`htlnlp_143`, as published), as addendum 2 says: three stopped
before the agent ran (the read-only folder, the bundle not found, the missing Docker SDK) and two ran, through the
single-task path and the arms' own path. The task was not resolved either time; it belongs to no arm and is run
again in each, in its place in the order. Two starts of the arms themselves then stopped before any kernel
started: Kaggle answered "not found" to the whole download of each arm's 1.2 GB bundle, though each file could be
had. The helper now fetches file by file, and the two arms were listed again as `colab-statement-try2` and
`colab-graph-try2` so that an open notebook would make them. No task of either arm had run.

## Two sessions made the first arm (a deviation from the plan)

The session that made the test runs was still reading the run list when the owner opened the notebook again, and
the list offered a run to every session that read it. So two machines made `colab-statement` at the same time,
each all 93 tasks, from the same sealed bundle, order and kernel file:

| | Session of 00:37:11 UTC | Session of 01:17:24 UTC |
|---|---|---|
| GPU, from its own log | one NVIDIA L4, 23,034 MiB | one NVIDIA A100-SXM4-40GB, 40,960 MiB |
| Kernel of the first arm started | 02:01:20 | 02:04:33 |
| Its first task started | 02:04:29 | 02:09:33 |

Both sent their output to the arm's one private dataset, as alternating versions. Each version is one session's
whole upload, and its log opens with that session's start and names its GPU, so the two are told apart with
certainty. This was found at 03:20 UTC, when the owner asked which GPU the run was on, and a rule was recorded on
issue 687 at 03:25 UTC, before any patch of either session had been verified:

1. **The registered pair is the A100 session's**: its `colab-statement`, then its `colab-graph`. That is the
   machine addendum 2 asks for. The primary test and the sensitivity test use this pair and no other.
2. **The L4 session finishes its baseline and then makes the graph arm too**, into a dataset of its own
   (`colab-graph-l4`): a second, unplanned run of the design, each pair inside one machine. It is described beside
   the registered pair. No claim rests on it, and no count is added across machines.
3. Had the A100 pair not been complete by 12:00 UTC and the L4 pair been, the L4 pair would have been the one
   tested. It did not come to that.
4. Each arm is collected from its own session's last upload, picked by version number and by the session start
   its log opens with, never "the latest version".

One change to the helper followed, and none to the kernel or the bundles: an entry of the run list can name the
GPU it is for, and a machine with another GPU does not make that run and reads, fetches and uploads nothing of it
(`is_for_this_gpu` in `kaggle/colab_official.py`, with tests). Both sessions' logs show it working: the L4 session
passed over `colab-graph` and took `colab-graph-l4`, and the A100 session passed over `colab-graph-l4` and took
`colab-report`.

## Result

| Run | Machine | Run | Wrote a patch | **Resolved** | 95% Wilson interval | Core split: resolved (of 17) | The other 76: resolved |
|---|---|---|---|---|---|---|---|
| `colab-statement` | A100 | 93 of 93 | 66 | **4** | 1.7 to 10.5% | 4 | 0 |
| `colab-graph` | A100 | 93 of 93 | 52 | **6** | 3.0 to 13.4% | 6 | 0 |
| `colab-report` | A100 | 93 of 93 | 73 | **4** | 1.7 to 10.5% | 4 | 0 |
| `colab-statement-l4` | L4 | 93 of 93 | 62 | **5** | 2.3 to 12.0% | 5 | 0 |
| `colab-graph-l4` | L4 | 93 of 93 | 64 | **8** | 4.4 to 16.1% | 7 | 1 |

Resolved: `colab-statement` `htlnlp_143`, `htlnlp_187`, `htlnlp_226`, `htlnlp_pr63`; `colab-graph` `htlnlp_111`,
`htlnlp_143`, `htlnlp_144`, `htlnlp_187`, `htlnlp_226`, `htlnlp_pr63`; `colab-report` `htlnlp_143`, `htlnlp_144`,
`htlnlp_187`, `htlnlp_pr63`; `colab-statement-l4` `htlnlp_143`, `htlnlp_144`, `htlnlp_174`, `htlnlp_187`,
`htlnlp_pr63`; `colab-graph-l4` `htlnlp_111`, `htlnlp_116`, `htlnlp_143`, `htlnlp_144`, `htlnlp_170`, `htlnlp_187`,
`htlnlp_226`, `htlnlp_pr63`.

No task was left out of any run: every one made model calls and has a row.

## The paired tests

Each context against the baseline on the same machine, task by task (`context_pairs_colab_<arm>.csv`, written by
`python/scripts/70_context_pairs.py --machine colab`):

| Against `colab-statement` | Registered in | Pairs | Left out | Both resolved | Baseline only | The context only | Neither | Exact McNemar p, two-sided |
|---|---|---|---|---|---|---|---|---|
| `colab-graph` | addendum 2 | 93 | 0 | 4 | 0 | 2 | 87 | 0.5 |
| `colab-report` | addendum 3 | 93 | 0 | 3 | 1 | 1 | 88 | 1.0 |

**No difference detected at this size.** Graph retrieval resolved the baseline's 4 tasks and 2 more (`htlnlp_111`,
`htlnlp_144`); the baseline resolved none that graph retrieval did not. The report resolved 3 of the baseline's 4
and 1 more (`htlnlp_144`); the baseline alone resolved 1 (`htlnlp_226`). The plans claim a difference only at p <
0.05, which needs at least six discordant pairs all one way. Neither "graph retrieval helps" nor "the report helps"
is claimed, and neither is ruled out: with a baseline this low, 93 tasks can show only a large effect. These are
the third and fourth comparisons registered on these tasks (the first two could not be tested); a reader who
corrects for that holds them to 0.0167 and 0.0125, and the reading is the same.

**Sensitivity.** The plans' second test leaves out any pair in which either side ran a command that reaches for the
network (a download tool, an installer, git over a remote). The commands read: `colab-statement` 161, `colab-graph`
104, `colab-report` 154, `colab-statement-l4` 150, `colab-graph-l4` 118. No command of `colab-statement` or
`colab-graph` does, so addendum 2's sensitivity test is its primary test. One command of `colab-report` does: an
installer, an editable install of the repository itself (`pip install -e .`), in `htlnlp_cc163083`, a task no run
resolved. pip had no index and every proxy pointed at a port nothing listens on. Without that pair, addendum 3's
test has 92 pairs: both resolved 3, the baseline alone 1, the report alone 1, p = 1.0. On the L4, which no test
rests on: `colab-statement-l4` 2 in `htlnlp_pr2`; without such pairs its own table has 92 pairs, both resolved 4,
the baseline alone 1, graph retrieval alone 4, p = 0.375.

## Described, not tested

The plans name these as descriptions. None is a test, and none is evidence that a context helped.

- **Two runs of the same baseline.** `colab-statement` and `colab-statement-l4` are one arm run twice, at the same
  time, on two machines: both resolved 3, the A100's alone 1 (`htlnlp_226`), the L4's alone 2 (`htlnlp_144`,
  `htlnlp_174`), neither 87. So two runs of one arm differ on 3 resolved tasks, where graph retrieval differs from
  the baseline on 2. Of the 2 tasks graph retrieval resolved alone on the A100, 1 (`htlnlp_144`) is resolved from
  the statement alone by the L4's baseline. The machines differ too (a task has 5 minutes on either, and the L4 is
  slower), so this is run-to-run and machine-to-machine variation together.
- **The second session's pair, on the L4** (`context_pairs_colab_l4_graph.csv`, `--machine colab-l4`). Baseline 5
  of 93 (2.3 to 12.0%), graph retrieval 8 (4.4 to 16.1%): both resolved 4, the baseline alone 1 (`htlnlp_174`),
  graph retrieval alone 4 (`htlnlp_111`, `htlnlp_116`, `htlnlp_170`, `htlnlp_226`), neither 84 (exact McNemar p =
  0.375, given as a description: this pair is not the registered one). The two graph arms: both resolved 6, the
  A100's alone 0, the L4's alone 2 (`htlnlp_116`, `htlnlp_170`).
- **The report against graph retrieval**, on the A100: both resolved 4, graph retrieval alone 2 (`htlnlp_111`,
  `htlnlp_226`), the report alone 0, neither 87.
- **Beside the Kaggle arms**, never pooled. Graph retrieval on Kaggle and on the A100: both resolved 3, Kaggle's
  alone 1 (`htlnlp_pr31`), the A100's alone 3 (`htlnlp_143`, `htlnlp_187`, `htlnlp_pr63`). On the 21 tasks Kaggle's
  `statement` arm ran, neither it nor `colab-statement` resolved any. The report on Kaggle and on the A100: both
  resolved 3, Kaggle's alone 2 (`htlnlp_116`, `htlnlp_174`), the A100's alone 1 (`htlnlp_pr63`).
- **The core split.** `colab-statement` 4 of its 17 tasks and 0 of the other 76; `colab-graph` 6 of its 17 tasks
  and 0 of the other 76; `colab-report` 4 of its 17 tasks and 0 of the other 76; `colab-statement-l4` 5 of its 17
  tasks and 0 of the other 76; `colab-graph-l4` 7 of its 17 tasks and 1 of the other 76. Outside the split:
  `htlnlp_116` in `colab-graph-l4`. Over the 5 runs that is 26 of 85 task-runs on the core split and 1 of 380 on
  the rest. The split was fixed by the screen of November 10, before any of these runs.
- **Found and fixed** (addendum 2), among the 51 tasks whose fix edits code the graph holds. Where the retrieval
  listed a node the fix edits (41 tasks), the baseline resolved 2 (`htlnlp_143`, `htlnlp_226`) and graph retrieval
  3 (`htlnlp_111`, `htlnlp_143`, `htlnlp_226`), writing a patch in 31 and 27. Where it did not (10 tasks): 0 and 0.
  On the other 42 tasks, whose fix edits no code the graph holds: 2 and 3. Being handed the right function is not
  the same as fixing it.
- **Task by task across the seven full runs under the evaluator** (three with graph retrieval: Kaggle's `graph`,
  `colab-graph`, `colab-graph-l4`; four without: Kaggle's `report`, `colab-statement`, `colab-report`,
  `colab-statement-l4`; never pooled, and counted here only to say which tasks). Resolved by all three
  graph-retrieval runs: `htlnlp_111`, `htlnlp_144`, `htlnlp_226`. Of those, resolved by none of the four runs
  without it: `htlnlp_111`. Resolved by all four runs without it and by no graph-retrieval run: none. One task is
  an anecdote, not a test: it says where to look, not that retrieval helps.
- **Other splits the plans name.** Where the statement names a node of the graph (54 tasks): baseline 3, graph
  retrieval 4; where it names none (39): 1 and 2. On the 20 tasks of November 10: 0 and 0, and the report 0. Where
  the task's report holds an import error (32 tasks): baseline 0, the report 0; where it holds none (61): 4 and 4.
- **Every run of this model on these tasks.** Before Colab, 9 different tasks had been resolved by some run, 8 of
  them in the core split. The A100's runs resolved 6 different tasks, none of them new, and the L4's 9 (new:
  `htlnlp_170`). Over every run, 10 different tasks have been resolved, 9 of them in the core split.

What the agent did in each run, over all 93 tasks:

| | `colab-statement` | `colab-graph` | `colab-report` | `colab-statement-l4` | `colab-graph-l4` |
|---|---|---|---|---|---|
| Resolved | 4 | 6 | 4 | 5 | 8 |
| Tests fail with the agent's patch | 46 | 32 | 43 | 36 | 38 |
| Errors before any test ran, with the agent's patch | 16 | 14 | 26 | 21 | 18 |
| Empty patch | 27 | 41 | 20 | 31 | 29 |
| Tool calls | 808 | 709 | 769 | 800 | 714 |
| To a graph tool | 72 (8.9%) | 61 (8.6%) | 53 (6.9%) | 58 (7.2%) | 60 (8.4%) |
| To the analyzer sub-agent | 20 | 17 | 19 | 24 | 16 |
| Naming a path outside the workspace | 0 | 0 | 0 | 0 | 0 |
| Model calls | 1,025 | 913 | 979 | 1,042 | 911 |
| Prompt tokens a task | 108,231 | 102,752 | 108,063 | 109,644 | 102,766 |
| Output tokens a task | 5,414 | 4,942 | 5,190 | 4,984 | 4,748 |
| Agent seconds a task | 76 | 72 | 78 | 140 | 128 |
| Ended at the model's context window | 19 | 22 | 17 | 8 | 17 |
| Ended at the 5-minute limit | 0 | 1 | 3 | 8 | 4 |

## Where the time went, and the GPUs (spec 014 US6, 036 US2)

As for the Kaggle arms: the agent framework's OpenTelemetry spans (names, counts and seconds; no prompt or reply)
and a GPU sample every five seconds, rolled up by `python/scripts/71_run_telemetry.py` as self time
(`..._sections.csv`, `..._task_sections.csv`, `..._gpu.csv` beside each run's table).

| Share of the tasks' time | `colab-statement` | `colab-graph` | `colab-report` | `colab-statement-l4` | `colab-graph-l4` |
|---|---|---|---|---|---|
| model call | 77.1% | 74.6% | 72.7% | 76.8% | 78.4% |
| tool run_command | 10.8% | 9.8% | 12.1% | 9.0% | 5.2% |
| context compaction | 11.2% | 14.6% | 14.3% | 13.8% | 15.8% |
| harness (the evaluator's own work around the agent) | 0.76% | 0.79% | 0.73% | 0.41% | 0.45% |
| the three graph tools together | 0.03% | 0.01% | 0.02% | 0.01% | 0.02% |

| The tasks' own GPU time (loading the model is not in it) | `colab-statement` | `colab-graph` | `colab-report` | `colab-statement-l4` | `colab-graph-l4` |
|---|---|---|---|---|---|
| GPU | one A100 | one A100 | one A100 | one L4 | one L4 |
| Loading the model, seconds | 249.4 | 148.5 | 144.3 | 144.3 | 144.4 |
| GPU-hours | 1.96 | 1.87 | 2.01 | 3.62 | 3.30 |
| GPU-seconds a task | 76 | 72 | 78 | 140 | 128 |
| Energy, Wh | 304 | 295 | 315 | 247 | 229 |
| Energy a task, Wh | 3.3 | 3.2 | 3.4 | 2.7 | 2.5 |
| Mean utilization | 88% | 88% | 89% | 90% | 94% |
| Estimated cost, USD | 3.66 | 3.50 | 3.76 | 3.01 | 2.74 |
| Estimated cost a task, USD | 0.04 | 0.04 | 0.04 | 0.03 | 0.03 |
| For each resolved task: GPU-hours; Wh; estimated USD | 0.49; 76; 0.92 | 0.31; 49; 0.58 | 0.50; 79; 0.94 | 0.72; 49; 0.60 | 0.41; 29; 0.34 |

`estimated_cost_usd` is the task's GPU-hours at the price `ops/cost_settings.yaml` declares for its GPU: 1.87 USD
an A100 GPU-hour and 0.83 an L4 GPU-hour, each the median on-demand price across providers for the week of
October 26, 2026 at getdeploying.com (the A100's read on November 12, 2026, over 38 providers). It is a rental
estimate, not what was paid: Colab is the owner's paid subscription, charged in compute units and not by the
GPU-hour, and what these runs used of it was not read. The estimate covers the tasks' own time, not the model's
loading, the fetching of a bundle, or the hours a machine waited.

## Checks

- **Each run was read from its own session's last upload**, by version and by the session start its log opens
  with (`kaggle/official_agent_run.py --colab-results <dataset>/<version> --colab-session <start>`), after its
  kernel had ended:

  | Run | Session | Kernel started (UTC) | Kernel ended (UTC) | Version read |
  |---|---|---|---|---|
  | `colab-statement` | 01:17:24, A100 | 02:04:33 | 04:07:33 | 36 of `htlnlp-colab-official-colab-statement` |
  | `colab-graph` | 01:17:24, A100 | 04:09:13 | 06:05:13 | 20 of `htlnlp-colab-official-colab-graph` |
  | `colab-report` | 01:17:24, A100 | 06:06:53 | 08:11:53 | 17 of `htlnlp-colab-official-colab-report` |
  | `colab-statement-l4` | 00:37:11, L4 | 02:01:20 | 05:42:20 | 49 of `htlnlp-colab-official-colab-statement` |
  | `colab-graph-l4` | 00:37:11, L4 | 05:43:55 | 09:05:55 | 26 of `htlnlp-colab-official-colab-graph-l4` |

- **No patch of a run was verified before its kernel had ended.** While a run was going, only counts were read
  from its uploads: how many tasks had a result, and whether the kernel had ended.
- **Each run got its own text and no other.** The kernel's own trace of every task holds the first line of that
  run's context and of no other: `colab-statement` the graph's in 0 of 93 and the report's in 0; `colab-graph` the
  graph's in 93 of 93 and the report's in 0; `colab-report` the graph's in 0 of 93 and the report's in 93;
  `colab-statement-l4` the graph's in 0 of 93 and the report's in 0; `colab-graph-l4` the graph's in 93 of 93 and
  the report's in 0 (checked on the kernels' output, which is not committed). Each `_settings.json` gives its
  context file's SHA-256, which is the one its plan pinned.
- **The verifier** is the one above ("The verifier on the collecting machine"): the competition's evaluator on
  the collecting machine, whose two controls gave 93 of 93 and 0 of 93 there.
- **The 12:00 UTC limit.** The A100 session's three arms were complete at 08:12 UTC on November 12 and the L4
  session's second arm at 09:06 UTC, inside the plans' limit of 12:00 UTC for what goes into the paper. No run
  needed a second start after its first task, and no task was run again.

## What it is not

Not evidence that graph retrieval or the report helps, and not evidence that either does not: the tests found no
difference, at a size where only a large one could show. One sampled run per task and run, at temperature 0.2;
the two runs of the baseline show how much one more draw moves the count. The L4 pair is a second run of the
design that nobody planned, on a slower GPU, and is not added to the registered pair. The `colab-report` arm is
not a benchmark condition: its context comes from the hidden test. Not the Kaggle arms' environment: one GPU,
another Python, nine packages at other versions, so no count here completes or corrects a Kaggle arm, and the
Kaggle baseline is still owed (issue 681). Every run had 5 minutes and 40 tool calls a task, not the leaderboard's
limits, on this project's own tasks: not a leaderboard score.
