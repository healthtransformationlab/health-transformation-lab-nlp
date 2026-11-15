# Pre-registration, addendum 4: the smaller model, E2B, against the Colab baseline

Spec 028, action item 12 (issue 748). This is an addendum to four earlier files, all unchanged:

| File | SHA-256 |
|---|---|
| `preregistration-failing-test-report.md` | `1b517ae1bb96d84d670ac6891542278275a0802a33ac57dae43c0c715e43d7c4` |
| addendum 1, `preregistration-graph-retrieval-arm.md` | `7121f14cd2c28baaa63af5bbcc35d668edb1fe8843f0351005673819393a0f29` |
| addendum 2, `preregistration-colab-paired-run.md` | `312041e89860d9fcb05ec57312231275178652ba6d7a0fd3499af7ced5fd2fc9` |
| addendum 3, `preregistration-colab-report-arm.md` | `0532820a9e221d60cda0299143f6e3a50c1cc937ebad19bc391fb15ee56ff5cf` |

Frozen on November 15, 2026 (UTC), before any run of this arm exists. The SHA-256 of this file as committed is
recorded on issue 748 before the arm starts.

## Why this arm

The owner's two competition entries both run `gemma-4-e4b-it-qat-w4a16-ct` (E4B). The competition's small-model
bonus goes to the best entry on E2B or E4B. `gemma-4-e2b-it-qat-w4a16-ct` (E2B) is smaller, so each model call
returns sooner, and each task's 5 minutes buy more steps. Whether that makes this agent resolve more tasks, or a
smaller model's weaker steps make it resolve fewer, is not known.

The competition allows one submission a day, and a single public score cannot tell two models apart. The 93
published tasks already have a complete E4B baseline on one Colab A100: addendum 2's `colab-statement`, 4 of 93.
This arm reruns that baseline with only the model changed, and the owner approved it on November 15, 2026.

## Design

One arm, on all 93 published tasks, each run once, paired task by task with `colab-statement`.

| | This arm |
|---|---|
| Tasks, harness, budgets, order | `colab-statement`'s: dataset version 4, `swegemma` 0.2.11, the agent's own `eval_config.yaml` (40 tool calls, 5 minutes, 60 turns, 120 s a command), the same seeded order (seed 20261110, the ids as that arm's settings list them), each task sealed until its turn, a kernel deadline of 255 minutes, telemetry on |
| The task's text | as published, as in `colab-statement` |
| Agent | `gemma-developer-agent` at `b95b235` with one change: both `model:` lines (`agent.yaml`, `sub_agents/code_analyzer.yaml`) name `gemma-4-e2b-it-qat-w4a16-ct`. Commit `8f4541fecdc7f9bf65b83300d57fa7a165540851` on that repository's branch `chore/101-e2b-variant-at-b95b235` (its issue 101), never merged |
| Model | `google/gemma-4/other/gemma-4-e2b-it-qat-w4a16-ct/2` from Kaggle, the latest version, as the E4B arms used version 2 of theirs. Served by vLLM as the kernel serves E4B: no change to the kernel's arguments |
| Kernel code | `kaggle/official_agent_kernel.py` as the Colab arms ran it, unchanged (SHA-256 below), started by `kaggle/colab_official.py`. The helper mounts the model the run list's entry names (`"model"`), the one change to it. An entry that names no model gets E4B, as before |
| Machine | a new Colab notebook session with one A100, asked for by the entry's `"gpu": "A100"`. The GPU given is recorded. It is not the session that made `colab-statement` |
| Network, telemetry | as in addendum 2: no credential reaches the kernel's process, and every command the agent ran is read afterwards for a reach at the network |

Run label `colab-e2b-statement`:

- sealed bundle `jcblearning/htlnlp-official-colab-e2b-statement`;
- keyed kernel file `jcblearning/htlnlp-colab-kernel-colab-e2b-statement`;
- results `jcblearning/htlnlp-colab-official-colab-e2b-statement`.

All three datasets are private.

What differs from `colab-statement`, beside the model:

- **The session.** It runs three days later, on another machine of the same GPU type.
- **The agent.** The two `model:` lines.

The second is the condition. The first is what "Two runs of the same baseline" in
`data/tasks/official_agent_runs/README.md` measures, together with machine-to-machine variation. That is why the
decision rule below allows for it.

## Outcome

As in the first plan: a task is resolved when the competition's own `verify_task` (unmodified) passes it on the
published snapshot with the agent's patch, on the collecting machine. On that machine the reference patch resolves
93 of 93 tasks and an empty patch 0 of 93.

## Analysis

Primary, for this addendum:

- resolved tasks in `colab-e2b-statement` and in `colab-statement`, each with a 95% Wilson interval;
- the paired table;
- the exact McNemar test, two-sided, `colab-e2b-statement` against `colab-statement`.

"E2B resolves more", or fewer, is claimed only at p < 0.05.

This is the fifth comparison registered on these tasks. A reader who corrects for five can hold this one to 0.01.
Reaching p < 0.05 takes six discordant pairs all one way, and p < 0.01 takes eight. With a baseline of 4, the test
can show only a large difference. "No difference detected at this size" is a likely outcome, and it will be reported
as it is.

### The decision: which model the submissions use

This is separate from the claim above. It decides what the owner submits, and it is fixed here before the arm runs.

- **E2B:** only if `colab-e2b-statement` resolves at least 8 of the 93 tasks. That is more than `colab-statement`'s
  4 by more than 3, and 3 is the number of resolved tasks on which two runs of that one E4B arm differed. Those runs
  were `colab-statement` and `colab-statement-l4`: README, "Two runs of the same baseline", the run-to-run noise
  documented on these tasks.
- **E4B:** in every other case, including a tie and a gain of 1 to 3 tasks. The entries stay on E4B.

The rule is applied as written whatever the McNemar test gives. Clearing it is not a claim that E2B is better, and
the report says so if the test does not reach p < 0.05.

Sensitivity:

- the same test without any pair in which either side ran a command that reaches for the network
  (`network_command_count` in `kaggle/colab_official.py`).

Described, not tested:

- `colab-e2b-statement` beside `colab-statement-l4`, `colab-graph` and `colab-report`, task by task: variation
  between runs, never pooled;
- the core split (17 tasks): the arm's resolved count on it, and on the other 76;
- the first plan's measures beside `colab-statement`'s: patches, tool calls and graph-tool calls, model calls,
  tokens, agent seconds a task, runs ended at the context window or at the 5-minute limit, GPU energy. These show
  whether E2B did take more steps in the same time.

## Exclusions and reruns

- What counts as not run is addendum 2's rule (`not_run_reasons` in `kaggle/official_agent_run.py`). The kernel stops
  the arm when two tasks in a row end without an answer from the model server.
- Tasks not run are run once more, in one further Colab run with the same settings, using
  `--order-of-ids` so each task keeps its place in the order. That run starts before any patch of this arm is
  verified. A pair with a side still not run leaves the paired test and is counted as left out.
- If the E2B model server does not start on the machine, no task has an outcome. That is recorded on issue 748. A
  change needed to make it start is listed there, with its reason, before the arm starts again. A change to the
  kernel file means this addendum's pinned hash no longer holds, and the issue says so.
- If the session ends within the arm, the rest runs in a new session from the last upload, as the helper does.
- If the arm ends up on another type of GPU, it is reported and labelled as such. It is not called matched, and the
  decision rule is not applied to it.
- No task is run again after its outcome is known.

## What was known when this was frozen

- Everything the first plan and its three addenda list.
- Every Colab run's outcome on these tasks (`data/tasks/official_agent_runs/README.md`): `colab-statement` 4 of 93
  (`htlnlp_143`, `htlnlp_187`, `htlnlp_226`, `htlnlp_pr63`), `colab-graph` 6, `colab-report` 4,
  `colab-statement-l4` 5, `colab-graph-l4` 8. 26 of the 27 fixes the Colab runs made are in the core split.
- The owner's two public competition scores, both on E4B: 0.05 and 0.03.
- That the agent's `main` has changed since `b95b235`: the prompt (gemma-developer-agent issue 97) and the output
  budget (its issue 99). This arm does not test those changes. A switch it decides applies to the agent as it then
  is, and is checked on the competition's own leaderboard.
- No run of E2B under the competition's evaluator, on these tasks or any other.

## Pinned inputs

| Input | SHA-256 or commit |
|---|---|
| The published `tasks.jsonl` (dataset version 4) | `c98d4b53e119d4922c4a24971b23dd002c9ef5b135e4607df3f0a55480ee6911` |
| `kaggle/official_agent_kernel.py`, before a run's seal key is written into it (as the Colab arms ran it) | `6f2500defeeb91ffa96cd048675b2b3aab418405cf2b483bbf05a74007dcc649` |
| The agent, `healthtransformationlab/gemma-developer-agent` | commit `8f4541fecdc7f9bf65b83300d57fa7a165540851` (`b95b235` with the two `model:` lines changed) |
| The order | `colab-statement`'s bundle's `official_batch.json` order, matched entry by entry by this arm's before upload |
