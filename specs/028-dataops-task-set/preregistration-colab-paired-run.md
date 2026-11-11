# Pre-registration, addendum 2: both arms again, on one Colab GPU

Spec 028, action item 9 (issue 687). An addendum to `preregistration-failing-test-report.md` (SHA-256
`1b517ae1bb96d84d670ac6891542278275a0802a33ac57dae43c0c715e43d7c4`) and to its addendum 1,
`preregistration-graph-retrieval-arm.md` (SHA-256 `7121f14cd2c28baaa63af5bbcc35d668edb1fe8843f0351005673819393a0f29`),
both unchanged. Frozen on November 11, 2026 (UTC), before any Colab run of either arm exists and before the test run
described below has returned anything. The SHA-256 of this file as committed is recorded on issue 687 before the
first arm starts.

## Why run both arms again

The first plan's baseline, the `statement` arm, ran 21 of the 93 tasks before its kernel's model server stopped
answering. The plan provides one more kernel for such tasks. Kaggle refused it: the account's weekly GPU allowance
is spent until November 14, 2026 (issue 681). So neither registered comparison could be tested: no arm resolved any
of the 21 tasks the baseline ran.

Running the other 72 on another machine would put two machines inside one arm. This addendum runs **both** arms,
`statement` and `graph`, on all 93 tasks, on one Colab machine: a new paired comparison inside one environment. It
does not complete the first plan's baseline, which is still owed on Kaggle (issue 681), and its counts are not added
to the Kaggle arms'.

## Design

Paired. All 93 published tasks, each run once in each of two arms.

| | Both arms |
|---|---|
| Tasks, agent, model, harness, budgets, order | the first plan's: dataset version 4, `gemma-developer-agent` at `b95b235`, `gemma-4-e4b-it-qat-w4a16-ct`, `swegemma` 0.2.11, the agent's own `eval_config.yaml`, one seeded shuffle (seed 20261110), each task sealed until its turn |
| Kernel code | `kaggle/official_agent_kernel.py` as the Kaggle arms ran it, unchanged (SHA-256 below), started by `kaggle/colab_official.py` |
| Machine | one Colab machine with one GPU. An A100 is asked for; the type given is recorded. Colab's base image, not Kaggle's pinned one |
| Software | the model server and the agent framework from PyPI at the versions the Kaggle kernels recorded (vLLM 0.19.1, google-adk 1.36.1, litellm 1.82.4), then the competition's wheelhouse installed over them by the kernel, as on Kaggle |
| Network | a Colab machine has one. The kernel's process starts with no credential, and with every proxy pointed at a port nothing listens on. Afterwards every command the agent ran is read for a reach at the network, and the count is reported |
| Telemetry | on, as in the Kaggle arms |

| Arm | The task's text | Run |
|---|---|---|
| `colab-statement` | as published | first |
| `colab-graph` | as published, with the graph's retrieval after its hints: addendum 1's context file, byte for byte | second, in the same notebook session |

The baseline runs first because it is the arm that is missing. Each arm is one process with its own model server.
Nothing of the first arm's is kept for the second but the downloaded wheels and model.

One GPU in place of four changes how fast the model answers, and each task still has 5 minutes. A task can end
differently here than on Kaggle for that reason alone. Both arms share it.

## A test run first

Before the arms, the notebook runs one task (`htlnlp_143`, as published) through the same code, to see that the model
server starts on this machine. It scores nothing and belongs to neither arm; `htlnlp_143` is run again in each arm, in
its place in the order. Its outcome is not known as this is frozen, and is recorded on issue 687 before the first arm
starts. A change the test shows is needed for the kernel to start on Colab is made before the first arm starts,
applies to both arms, and is listed on issue 687 before that arm starts.

## Outcome

The first plan's: resolved, by the competition's own `verify_task` (unmodified) on the published snapshot with the
agent's patch, on the collecting machine, where the reference patch resolves 93 of 93 tasks and an empty patch 0 of 93.

## Analysis

Primary:

- resolved tasks in each arm with 95% Wilson intervals, the paired table, and the exact McNemar test, two-sided,
  `colab-graph` against `colab-statement`. "Graph retrieval helps", or hurts, is claimed only at p < 0.05.

This is the third comparison registered on these tasks; the first two could not be tested. A reader who corrects for
three can hold this one to 0.0167. p < 0.05 needs six discordant pairs all one way, and p < 0.0167 needs seven. The
Kaggle `graph` arm resolved 4 tasks. If the arms here resolve about as many, the test cannot reach either threshold,
and the result will read "no difference detected at this size", with a complete baseline beside it. That is the
likeliest outcome, and it is reported as it is. Whatever the result, the paper says it.

Sensitivity:

- the same test without any pair in which either side ran a command that reaches for the network
  (`network_command_count` in `kaggle/colab_official.py`: a download tool, an installer, git over a remote).

Described, not tested:

- each Colab arm beside the Kaggle arm of the same text, task by task: `colab-graph` beside `graph` on all 93,
  `colab-statement` beside `statement` on its 21. This is variation between runs and between machines. It is not a
  test, and no count is pooled across machines;
- the core split (addendum 1's 17 tasks): each arm's resolved count on it;
- found and fixed: among the 51 tasks whose fix edits code the graph holds, each arm's resolved count by whether the
  retrieval listed a node the fix edits (41 tasks) or not (10);
- by whether the statement names any node, and by the 20 of November 10;
- the first plan's measures: patches, tool calls and graph-tool calls, tokens, seconds, GPU energy.

## Exclusions and reruns

- "Not run" is the runner's rule as committed (`not_run_reasons` in `kaggle/official_agent_run.py`): a task the
  process did not reach, or one that made no model call at all and ended at its time limit or on a server error. Any
  other failure keeps its row and counts as unresolved. The kernel stops an arm when two tasks in a row end that way.
- Tasks not run in an arm are run once more, in one further Colab run with the same settings and order, if that can
  finish by 12:00 UTC on November 12, 2026. A pair with a side still not run leaves the paired test and is counted as
  left out.
- If the notebook's session ends between or within the arms, the rest runs in a new session. If the two arms end up
  on different types of GPU, the test is still reported, labelled as across GPU types.
- No task is run again after its outcome is known.
- The paper's submission closes at 23:59 UTC on November 12, 2026. What is complete by 12:00 UTC goes into the paper;
  anything later is reported in this repository only. If the first arm has not started by 04:00 UTC on November 12,
  the run is dropped, and that is said on issue 687.

## What was known when this was frozen

- Everything the first plan and addendum 1 list.
- The Kaggle arms' outcomes (`data/tasks/official_agent_runs/README.md`): `statement` resolved 0 of the 21 tasks it
  ran; `graph` 4 of 93 (`htlnlp_111`, `htlnlp_144`, `htlnlp_226`, `htlnlp_pr31`), all four in the core split;
  `report` 5 of 93.
- That 6 of the 8 tasks those two arms resolved had been resolved from the statement alone by an earlier run under
  another harness, budget or checkpoint. So the baseline here may well resolve some of the same tasks.
- No Colab run of either arm, and nothing from the test run.

## Pinned inputs

| Input | SHA-256 |
|---|---|
| The graph context file (93 tasks, one retrieval each; addendum 1's) | `f4d3f1c00a649936d1885016a4dae49b63f10f5508659558056d222fd14d33fc` |
| The published `tasks.jsonl` (dataset version 4) | `c98d4b53e119d4922c4a24971b23dd002c9ef5b135e4607df3f0a55480ee6911` |
| `kaggle/official_agent_kernel.py`, before a run's seal key is written into it | `26209de7c07325a1b997fb37755e9bed6d15f6220e1dd6823a334bd1424b89b6` |
