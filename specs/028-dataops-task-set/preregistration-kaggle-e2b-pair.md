# Pre-registration, addendum 5: E2B against E4B, two paired arms on one Kaggle machine shape

Spec 028, action item 12 (issue 748). This is an addendum to five earlier files, all unchanged:

| File | SHA-256 |
|---|---|
| `preregistration-failing-test-report.md` | `1b517ae1bb96d84d670ac6891542278275a0802a33ac57dae43c0c715e43d7c4` |
| addendum 1, `preregistration-graph-retrieval-arm.md` | `7121f14cd2c28baaa63af5bbcc35d668edb1fe8843f0351005673819393a0f29` |
| addendum 2, `preregistration-colab-paired-run.md` | `312041e89860d9fcb05ec57312231275178652ba6d7a0fd3499af7ced5fd2fc9` |
| addendum 3, `preregistration-colab-report-arm.md` | `0532820a9e221d60cda0299143f6e3a50c1cc937ebad19bc391fb15ee56ff5cf` |
| addendum 4, `preregistration-colab-e2b-arm.md` | `a6f2461efb374982730254c764c721368998f543df944f0b6a01d263e9422a64` |

**State: frozen on November 15, 2026 (UTC), before any kernel of either arm has started.** The SHA-256 of this file
as committed is recorded on issue 748 the same day. The kernels start only on the owner's word, once the Kaggle
account's weekly GPU quota has room for them. This text is not edited after that. Anything learned between freezing
and the start goes on issue 748 as a dated line, before the kernels start.

## Why this replaces addendum 4

Addendum 4 put one E2B arm on Colab and set it against `colab-statement`, a run made three days earlier in another
session. Before any session made that arm, the owner chose a cleaner design on November 15, 2026: E2B and E4B as two
arms of the same experiment, on the same Kaggle machine shape and image, made close together in time. Session-to-session
variation then lies inside the pair rather than between the arms. The owner's linked Colab Pro+ subscription adds GPU
hours on Kaggle.

So addendum 4's arm is withdrawn, untested:

- its run-list entry is removed;
- its bundle `jcblearning/htlnlp-official-colab-e2b-statement` and kernel file
  `jcblearning/htlnlp-colab-kernel-colab-e2b-statement` are unused, and both are kept.

Its comparison and decision rule are replaced by the ones below.

## Design

Two arms, paired task by task, on all 93 published tasks, each task run once in each arm.

| | Both arms |
|---|---|
| Tasks, harness, budgets, order | `colab-statement`'s: dataset version 4, `swegemma` 0.2.11, the agent's own `eval_config.yaml` (40 tool calls, 5 minutes, 60 turns, 120 s a command), the 93 ids as that arm's settings list them, one seeded shuffle (seed 20261110, the same order as `colab-statement`'s bundle), each task sealed until its turn, telemetry on. The task's text is as published |
| Kernel code | `kaggle/official_agent_kernel.py` as every arm since addendum 2 ran it, unchanged (SHA-256 below) |
| Machine | a private, offline Kaggle kernel, machine shape `NvidiaL4` (the starter notebook's: four L4s in every earlier Kaggle arm), the starter image pinned by digest (`STARTER_DOCKER_IMAGE` in `kaggle/official_agent_run.py`), the competition attached, as the Kaggle `graph` and `report` arms. The GPUs given are recorded |
| Kernel limits | `--deadline-minutes 600` and `--kernel-minutes 690` in both arms. The Kaggle `graph` and `report` arms needed about 2 hours of agent time for 93 tasks on this shape, and 93 tasks at the full 5 minutes each is 7.75 hours. Kaggle stops a GPU session at 12 hours. These limits only bound the kernel: no task's budget changes |
| The model a kernel attaches | the one the submission declares (`declared_model` and `model_source` in `kaggle/official_agent_run.py`, issue 748), version 2 on Kaggle. An E4B kernel's metadata is byte for byte what it was before that change |

| Arm | Agent (`healthtransformationlab/gemma-developer-agent`) | Model |
|---|---|---|
| `kaggle-e4b-statement` | `b95b235739268e311cddcb254a7cb58d07a7b89c`, as every arm on these tasks | `google/gemma-4/Other/gemma-4-e4b-it-qat-w4a16-ct/2` |
| `kaggle-e2b-statement` | `8f4541fecdc7f9bf65b83300d57fa7a165540851`: `b95b235` with only its two `model:` lines changed (branch `chore/101-e2b-variant-at-b95b235`, its issue 101, never merged) | `google/gemma-4/Other/gemma-4-e2b-it-qat-w4a16-ct/2` |

**When they run.** The two kernels are pushed together when two GPU sessions are free, since Kaggle allows two at once. If only one is free, `kaggle-e4b-statement` goes first and `kaggle-e2b-statement` follows as soon as a session frees. Each arm is its own kernel with its own model server, so the order cannot reach a task's outcome. How they were run is reported.

**Datasets.** Each arm gets its own sealed bundle, `jcblearning/htlnlp-official-<label>` (private), and its own kernel,
`jcblearning/htlnlp-offrun-<label>` (private).

## Outcome

As in the first plan: a task is resolved when the competition's own `verify_task` (unmodified) passes it on the
published snapshot with the agent's patch, on the collecting machine. On that machine the reference patch resolves
93 of 93 tasks and an empty patch 0 of 93.

## Analysis

Primary:

- resolved tasks in each arm, each with a 95% Wilson interval;
- the paired table;
- the exact McNemar test, two-sided, `kaggle-e2b-statement` against `kaggle-e4b-statement`.

"E2B resolves more", or fewer, is claimed only at p < 0.05.

Addendum 4's comparison is withdrawn untested, so this is the fifth comparison registered on these tasks that can be
tested. A reader who corrects for five holds it to 0.01. Reaching p < 0.05 takes six discordant pairs all one way,
and p < 0.01 takes eight. With E4B resolving about 4 to 6, the test can show only a large difference. "No difference
detected at this size" is a likely outcome, and it will be reported as it is.

### The decision: which model the submissions use

This is fixed here, before either arm runs. The submissions switch to E2B only if both of these hold:

1. **More than the noise.** `kaggle-e2b-statement` resolves more tasks than `kaggle-e4b-statement` by more than 3,
   i.e. by at least 4. 3 is the number of resolved tasks on which two runs of one E4B arm differed:
   `colab-statement` and `colab-statement-l4`, in `data/tasks/official_agent_runs/README.md`, "Two runs of the same
   baseline", the run-to-run noise documented on these tasks.
2. **The test agrees.** The primary test gives p < 0.05, with more tasks resolved by E2B alone than by E4B alone.

In every other case the submissions stay on E4B. That includes a tie, an E2B gain of 1 to 3, and a gain of 4 or more
without p < 0.05. Meeting the rule is not a claim beyond what the test supports. Missing it is not a claim that the
models are equal.

Sensitivity:

- the same test without any pair in which either side ran a command that reaches for the network. On Kaggle the
  kernels are offline, so this is expected to leave every pair in, and the count is reported.

Described, not tested:

- each arm beside `colab-statement` and `colab-statement-l4`, task by task: variation between runs and machines,
  never pooled;
- `kaggle-e4b-statement` beside the Kaggle `report` and `graph` arms' resolved tasks (other texts, so named only);
- the core split (17 tasks): each arm's resolved count on it, and on the other 76;
- per arm: patches, tool calls and graph-tool calls, model calls, tokens, agent seconds a task, runs ended at the
  context window or at the 5-minute limit, GPU-hours and energy. These show whether E2B took more steps in the same
  time.

## Exclusions and reruns

- What counts as not run is addendum 2's rule (`not_run_reasons` in `kaggle/official_agent_run.py`). A kernel stops
  its arm when two tasks in a row end without an answer from the model server.
- Tasks not run in an arm are run once more, in one further kernel of that arm with the same settings, using
  `--order-of-ids` so each keeps its place in the order. That kernel starts before any patch of that arm is
  verified. A pair with a side still not run leaves the paired test and is counted as left out.
- A kernel that Kaggle refuses, or that ends for an infrastructure reason before its first task (no GPU given, a
  download or install failure), may be started once more unchanged. The retry is logged on issue 748 with Kaggle's
  own words.
- If the E2B model server does not start with the kernel's unchanged arguments, the E2B arm has no outcome. That is
  reported on issue 748, and nothing in this design is changed to work around it. A fix would need a new addendum
  before any further kernel.
- No task is run again after its outcome is known.

## What was known when this was frozen

- Everything the first plan and its four addenda list.
- Every Colab run's outcome on these tasks: `colab-statement` 4 of 93, `colab-graph` 6, `colab-report` 4,
  `colab-statement-l4` 5, `colab-graph-l4` 8.
- The Kaggle arms': `statement` 0 of the 21 it ran, `graph` 4 of 93, `report` 5 of 93.
- The owner's two public competition scores, both on E4B: 0.05 and 0.03.
- No run of E2B under the competition's evaluator, on these tasks or any other. Addendum 4's Colab arm was never run.
- The account's GPU quota on November 15: 30.19 of 30.00 hours used, resetting on November 21, 2026, with the Colab
  Pro+ hours not yet shown. Two of the owner's development-set kernels held both GPU sessions.
- The agent's `main` has changed since `b95b235` (gemma-developer-agent issues 97 and 99). This pair does not test
  those changes. A switch it decides applies to the agent as it then is, and is checked on the competition's own
  leaderboard.

## Pinned inputs

| Input | SHA-256 or commit |
|---|---|
| The published `tasks.jsonl` (dataset version 4) | `c98d4b53e119d4922c4a24971b23dd002c9ef5b135e4607df3f0a55480ee6911` |
| `kaggle/official_agent_kernel.py`, before a run's seal key is written into it | `6f2500defeeb91ffa96cd048675b2b3aab418405cf2b483bbf05a74007dcc649` |
| E4B agent | `b95b235739268e311cddcb254a7cb58d07a7b89c` |
| E2B agent | `8f4541fecdc7f9bf65b83300d57fa7a165540851` |

## Starting and collecting (the commands)

Run from the repository root of this branch, after the owner's go-ahead.

```bash
export KAGGLE_API_TOKEN="$KAGGLE_API_KEY" KAGGLE_USERNAME=jcblearning   # never echo the token
W=${TMPDIR:-/tmp}/htl_e2b_pair && mkdir -p "$W"
AGENT=<path to a clone of healthtransformationlab/gemma-developer-agent>

# 1. Quota and slots: both must allow the pair before anything is pushed
python - <<'PY'
from kaggle.api.kaggle_api_extended import KaggleApi
a = KaggleApi(); a.authenticate()
with a.build_kaggle_client() as k:
    q = k.kernels.kernels_api_client.get_accelerator_quota_statistics().gpu_quota
left = (q.total_time_allowed - q.time_used).total_seconds() / 3600
print(f"GPU hours left this week: {left:.1f} (allowed {q.total_time_allowed.total_seconds()/3600:.1f}); "
      "the pair needs up to 2 x 11.5")
PY
kaggle kernels list --mine --sort-by dateRun --page-size 6   # then `kaggle kernels status <ref>` for each: at most one RUNNING to start both

# 2. The two agents, one worktree each
git -C "$AGENT" fetch -q origin
git -C "$AGENT" worktree add --detach "$W/agent-e4b" b95b235739268e311cddcb254a7cb58d07a7b89c
git -C "$AGENT" worktree add --detach "$W/agent-e2b" 8f4541fecdc7f9bf65b83300d57fa7a165540851

# 3. The published tasks, version 4 (check tasks.jsonl's SHA-256 against the pinned value)
kaggle datasets download jcblearning/health-transformation-lab-coding-agent-tasks/4 -p "$W/tasks" --unzip -q
sha256sum "$W/tasks/tasks.jsonl"   # c98d4b53e119d4922c4a24971b23dd002c9ef5b135e4607df3f0a55480ee6911
IDS=$(python -c "import json;print(','.join(json.load(open('data/tasks/official_agent_runs/gemma-4-e4b-it-qat-w4a16-ct_swegemma_colab-statement_settings.json'))['sample']['instance_ids']))")
COMMON=(--dataset "$W/tasks" --ids "$IDS" --seed 20261110 --batch --telemetry --competition gemma-4-developer-agent
        --deadline-minutes 600 --kernel-minutes 690 --work "$W/runs"
        --sample-method "the 93 published tasks as colab-statement ran them, fixed by addendum 5 (specs/028-dataops-task-set/preregistration-kaggle-e2b-pair.md)")

# 4. Start both (each process uploads its sealed bundle, pushes its kernel, then waits for it).
#    Each waits for its kernel, then verifies its patches with the competition's evaluator. Install that first,
#    as data/tasks/official_verifier/README.md says, or start without it and collect later with --collect.
nohup python kaggle/official_agent_run.py "${COMMON[@]}" --agent-dir "$W/agent-e4b" --label kaggle-e4b-statement > "$W/e4b.log" 2>&1 &
nohup python kaggle/official_agent_run.py "${COMMON[@]}" --agent-dir "$W/agent-e2b" --label kaggle-e2b-statement > "$W/e2b.log" 2>&1 &

# 5. Collect (re-runnable; reads each finished kernel, verifies, writes the table and settings)
python kaggle/official_agent_run.py "${COMMON[@]}" --agent-dir "$W/agent-e4b" --label kaggle-e4b-statement --collect
python kaggle/official_agent_run.py "${COMMON[@]}" --agent-dir "$W/agent-e2b" --label kaggle-e2b-statement --collect
```

The tables are `data/tasks/official_agent_runs/gemma-4-e4b-it-qat-w4a16-ct_swegemma_kaggle-e4b-statement.csv` and
`gemma-4-e2b-it-qat-w4a16-ct_swegemma_kaggle-e2b-statement.csv`, each with its `_settings.json`.
