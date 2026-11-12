# Pre-registration, addendum 3: the failing test's report beside the Colab pair, on the same machine

Spec 028, action item 9 (issue 687). An addendum to `preregistration-failing-test-report.md` (SHA-256
`1b517ae1bb96d84d670ac6891542278275a0802a33ac57dae43c0c715e43d7c4`), its addendum 1
`preregistration-graph-retrieval-arm.md` (SHA-256 `7121f14cd2c28baaa63af5bbcc35d668edb1fe8843f0351005673819393a0f29`)
and its addendum 2 `preregistration-colab-paired-run.md` (SHA-256
`312041e89860d9fcb05ec57312231275178652ba6d7a0fd3499af7ced5fd2fc9`), all unchanged. Frozen on November 12, 2026 (UTC),
before any Colab run of the report arm exists and while the Colab pair's second arm is still running. The SHA-256 of
this file as committed is recorded on issue 687 before the arm starts.

## Why a third arm on Colab

An outside review of the paper, which the owner passed on shortly before 05:00 UTC on November 12, recommends running three
conditions on one Colab GPU configuration, and not setting a new Colab baseline beside the old Kaggle arms: the
baseline, graph retrieval, and the failing test's report, the third "only if compute and time remain". Addendum 2
registered the first two. Its baseline is in, its second arm ends at about 06:10 UTC, and the same notebook session
is then free, hours before the paper's cut-off. So the third condition runs there too. On Kaggle the `report` arm
resolved 5 of 93 with no baseline to set it against; here it has one, from the same machine.

The report is built from each task's hidden test. It is a test-first workflow's context, not a benchmark condition,
as the first plan says.

## Design

One more arm of addendum 2's design, on all 93 published tasks, each run once.

| | This arm |
|---|---|
| Tasks, agent, model, harness, budgets, order | addendum 2's: dataset version 4, `gemma-developer-agent` at `b95b235`, `gemma-4-e4b-it-qat-w4a16-ct`, `swegemma` 0.2.11, the agent's own `eval_config.yaml`, the same seeded order (seed 20261110), each task sealed until its turn |
| The task's text | as published, with the failing test's report after its hints: the first plan's context file, byte for byte |
| Kernel code | `kaggle/official_agent_kernel.py` as the Colab pair ran it (SHA-256 below), started by `kaggle/colab_official.py` |
| Machine | the notebook session that made the registered pair: the session that began at 01:17:24 UTC, one NVIDIA A100-SXM4-40GB, Colab's image, Python 3.13.16, the same installed packages |
| Order of the arms | third, after `colab-statement` and `colab-graph`. Each arm is one process with its own model server, as in addendum 2 |
| Network, telemetry | as in addendum 2 |

Run label `colab-report`. The second session, on an L4, does not make this arm.

The review also recommends alternating the arms task by task, so that an interruption costs each arm alike. That is
not done: an arm here is one process over one sealed bundle, the first arm had finished before the review arrived,
and the second was running. What stands in for it: a session that drops resumes its arm from its last upload
(eight minutes' work at most is lost), and no arm of the registered pair has been interrupted so far.

## Outcome

The first plan's: resolved, by the competition's own `verify_task` (unmodified) on the published snapshot with the
agent's patch, on the collecting machine, where the reference patch resolves 93 of 93 tasks and an empty patch 0 of 93.

## Analysis

Primary, for this addendum:

- resolved tasks in `colab-report` and in `colab-statement` with 95% Wilson intervals, the paired table, and the exact
  McNemar test, two-sided, `colab-report` against `colab-statement`. "The failing test's report helps", or hurts, is
  claimed only at p < 0.05.

This is the fourth comparison registered on these tasks. The first two could not be tested, and the third is addendum
2's. A reader who corrects for four can hold this one to 0.0125. p < 0.05 needs six discordant pairs all one way, and
p < 0.0125 needs eight. On Kaggle the report arm resolved 5 tasks, and the Colab baseline resolved 4. If this arm
resolves about as many, the test cannot reach either threshold, and the result will read "no difference detected at
this size". That is the likeliest outcome, and it is reported as it is.

Addendum 2's primary test is unchanged by this one, and is reported whatever this arm does.

Sensitivity:

- the same test without any pair in which either side ran a command that reaches for the network.

Described, not tested:

- `colab-report` beside `colab-graph`, task by task, as a paired table;
- `colab-report` beside the Kaggle `report` arm on all 93: variation between runs and machines, never pooled;
- the core split (17 tasks): the arm's resolved count on it, beside the other two arms';
- by whether the task's report holds an import error, and by the 20 of November 10 (the first plan's splits);
- the first plan's measures: patches, tool calls and graph-tool calls, tokens, seconds, GPU energy.

## Exclusions and reruns

- Addendum 2's rules: what counts as not run, and that no task is run again after its outcome is known.
- Tasks not run in this arm are run once more only if that can finish by 12:00 UTC on November 12, 2026. A pair
  with a side not run leaves the paired test and is counted as left out.
- If the session ends before or within the arm, the rest runs in a new session if one is started in time; an arm
  that ends up on another type of GPU is reported and labelled as such, and is not called matched.
- What is complete by 12:00 UTC on November 12 goes into the paper. If the arm is not complete by then, what it ran
  is reported in this repository only, as incomplete, and the paper says the third condition was not completed on
  Colab.

## What was known when this was frozen

- Everything the first plan and its two addenda list, and the Kaggle arms' outcomes: `statement` 0 of the 21 it ran,
  `graph` 4 of 93, `report` 5 of 93 (`htlnlp_116`, `htlnlp_143`, `htlnlp_144`, `htlnlp_174`, `htlnlp_187`).
- The Colab baseline of the registered pair, collected and verified at 04:14 UTC on November 12: `colab-statement`
  resolved 4 of 93 (`htlnlp_143`, `htlnlp_187`, `htlnlp_226`, `htlnlp_pr63`), all four in the core split, with all 93
  run and none of its 161 commands reaching for the network.
- Of the Colab graph arm: that it is running, and how many of its tasks have a saved result. No patch of it has been
  verified.
- Of the second session's baseline, on the L4: how many tasks have a saved result. No patch of it has been
  verified, and its second arm has not started.
- No Colab run of the report arm.

## Pinned inputs

| Input | SHA-256 |
|---|---|
| The report context file (93 tasks, one report each; the first plan's) | `4ff681e5ae08222945b2cf13d775c6698a1807e5060039a507896e920e2611d2` |
| The published `tasks.jsonl` (dataset version 4) | `c98d4b53e119d4922c4a24971b23dd002c9ef5b135e4607df3f0a55480ee6911` |
| `kaggle/official_agent_kernel.py`, before a run's seal key is written into it (commit `db7e928`) | `6f2500defeeb91ffa96cd048675b2b3aab418405cf2b483bbf05a74007dcc649` |
