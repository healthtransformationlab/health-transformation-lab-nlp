# Pre-registration: does a failing test's report help a small agent on real changes?

Spec 028, action item 7 (issue 674). Frozen on November 11, 2026, before any kernel of either arm started. The
SHA-256 of this file as committed is recorded on issue 674, whose timestamp GitHub sets.

## Question

With a task's statement, does also giving Gemma 4 E4B the failing test's report change how many tasks it resolves
under the competition's evaluator?

The counts of pull requests 671 and 673 say where such a report points (with the statement, to the fix in 48 of the
51 tasks that edit existing code, against 42). They are counts from files. No run has given an agent the report.

## Design

Paired. All 93 published tasks, each run once in each of two arms, by the competition's harness.

| | Both arms |
|---|---|
| Agent | `gemma-developer-agent` at `b95b235`; its agent files are those of the run of November 10 (`6fed55c`) and of its `main` today |
| Model and server | `gemma-4-e4b-it-qat-w4a16-ct`, vLLM from the competition's wheelhouse, four L4 GPUs, the pinned image of the earlier runs |
| Harness | `swegemma` 0.2.11, its agent loop (`Evaluator.evaluate_task`), subprocess sandbox |
| Budgets | the agent's own `eval_config.yaml`: 16,384 output tokens, a 4,096-token thinking budget, 40 tool calls, 5 minutes |
| Order | one seeded shuffle (seed 20261110), the same in both arms; each task sealed until its turn |
| Beside the agent | the task's snapshot, graph and embeddings; no patch and no tests |
| Kernels | one per arm, started together on November 11, 2026; telemetry on (GPU samples, the agent framework's spans) |

| Arm | The task's text |
|---|---|
| `statement` | as published |
| `report` | as published, with the failing test's report after its hints |

The report is the output of `python/scripts/69_failure_report.py` at commit `749b859` on the published dataset
(version 4): up to 10 distinct errors, each with the first test that fails that way, how many more do, and the
first line of the error (at most 240 characters); then up to 15 public functions those tests called, which is what
the repository's OpenTelemetry spans record. It
is built from the task's hidden test. That is the context a test-first workflow has before the fix. It is not a
benchmark condition, and every report of this run says so.

The exact text given is pinned by the SHA-256 of the context file, below. The text is not committed.

## Sample

Every published task: the 93 of dataset version 4. No draw.

Twenty of them were run with the `statement` arm's settings on November 10 (seed 20261110, stratified by tier); they
are named below because their earlier outcomes are known:
`htlnlp_152`, `htlnlp_189`, `htlnlp_191`, `htlnlp_214`, `htlnlp_244`, `htlnlp_276`, `htlnlp_68`, `htlnlp_71`,
`htlnlp_90`, `htlnlp_c95eedd3`, `htlnlp_cbc00f07`, `htlnlp_cc73f4cf`, `htlnlp_cf773377`, `htlnlp_pr21`,
`htlnlp_pr28`, `htlnlp_pr31`, `htlnlp_pr34`, `htlnlp_pr37`, `htlnlp_pr47`, `htlnlp_pr54`.

## Outcome

Resolved, for each task and arm: the competition's own `verify_task` (unmodified) on the published snapshot with
the agent's patch, by `kaggle/official_verify.py`, as in the run of November 10. An empty patch is unresolved.

## Analysis

Primary:

- resolved tasks in each arm, with 95% Wilson intervals;
- the paired table (both, `statement` only, `report` only, neither);
- the exact McNemar test, two-sided: a binomial test on the discordant pairs.

"The report helps" is claimed only at p < 0.05. Anything else is reported as no difference detected at this size,
with the counts and intervals. With a baseline near zero, p < 0.05 needs at least 6 discordant pairs all one way,
so a real effect of fewer tasks than that will not show.

Described, not tested:

- non-empty patches; the tests' exit codes; tool calls, model calls and graph-tool calls;
- prompt and output tokens, the agent's seconds, and each task's GPU energy and utilisation from the kernel's
  samples;
- the split by whether the report holds an import error, by whether the task passes the screen, by whether the
  fix edits existing code the graph holds, and by the 20 of November 10 against the other 73;
- for those 20, the outcomes of November 10 beside today's `statement` arm, as run-to-run variation.

## Exclusions and reruns

- A task a kernel did not reach, or whose agent phase did not start, is "not run" in that arm. Such tasks are run
  in one more kernel for that arm, once, with the same settings and order. A pair with a side still not run leaves
  the paired test and is counted as left out.
- No task is run again after its outcome is known.

## What was known when this was frozen

- The run of November 10 resolved 0 of those 20, with the `statement` arm's settings.
- Where the reports point, as counts (pull requests 671 and 673).
- The reports' sizes and kinds for all 93 tasks (`data/tasks/failure_report_shape.csv`). The text of a few was read
  to check its format.
- No run of the `report` arm exists.

## Pinned inputs

| Input | SHA-256 |
|---|---|
| The context file (93 tasks, one report each) | `4ff681e5ae08222945b2cf13d775c6698a1807e5060039a507896e920e2611d2` |
| The published `tasks.jsonl` (dataset version 4) | `c98d4b53e119d4922c4a24971b23dd002c9ef5b135e4607df3f0a55480ee6911` |
