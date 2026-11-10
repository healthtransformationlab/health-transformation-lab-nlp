# Feature Specification: score an agent on our task set with a local copy of the documented harness

**Feature Branch**: `035-local-agent-harness`

**Created**: 2026-11-04

**Status**: draft; US1 implemented first

> **Correction, November 10, 2026 (#636).** The evaluator is available: `swegemma` ships as a wheel in the Kaggle
> dataset `metric/gemma-4-developer-agent-wheelhouse`, which the competition's starter notebook attaches, with the
> vLLM server that notebook uses. The text below is what was known when this spec was written. Since then the
> evaluator's own verification has been run on the task set (spec 028 US6, `data/tasks/official_verifier/`), and
> it gives the same verdict as this harness on every agent patch compared.

**Input**: Spec 028's task set is public on Kaggle, but its scoring step (T011b) is blocked. The competition's
evaluator, `swegemma`, is not on PyPI, is not among the competition's files (#449), and Kaggle runs it only on
submissions against the competition's own tasks. Its guide (`HARNESS_README.md`, read from the competition's files,
never committed) documents what it does:
- the initial prompt;
- the multi-turn loop;
- the nine tools, with their arguments, results and limits;
- the budgets;
- patch extraction;
- verification.

Our gate (`task_gate.py`, #453) already does the verification. This spec builds the rest locally, so the agent in
[gemma-developer-agent](https://github.com/healthtransformationlab/gemma-developer-agent) can be scored on our tasks.

> Personal learning project. Every number this produces is labelled "measured with this repository's
> re-implementation of the documented harness, not the competition's evaluator". It is never presented as an
> official score.

## User stories

### US1 - A local runner for the documented harness, proven with scripted models (P1) #543
`agent_harness.py` follows the guide's sections 4.2 to 8.2:
- **Workspace:** the task's files at `base_commit` as one commit, tagged `_swegemma_baseline`, with the documented
  `.git/info/exclude`.
- **Tools:** the nine tools, with their JSON results, the 5,000-character, 150-line and 10,000-character limits,
  budget gating, and the warning at 10 or fewer calls left.
- **Prompt:** the initial prompt's sections, and the instruction's `{problem_description}` and `{hints}`.
- **Loop:** `submit_patch` ends it; a turn without a tool call gets a nudge, and more than three such turns in a
  row end the session.
- **Patch extraction:** `git add -N .`, a diff against the baseline, then the protected files stripped.
- **Verification:** a fresh workspace, the patch, the test patch, then the target tests, with the gate's pytest
  and JUnit check.

`scripts/59_run_agent.py` reads a submission folder (`agent.yaml` with its `!include`s, the declared tools, and
`eval_config.yaml`'s budgets) and writes a run table. Two scripted models bound it:
- `calib:oracle` replays each reference patch and must resolve every task;
- `calib:null` submits nothing and must resolve none.

### US2 - The Gemma agent through the local harness on a Kaggle GPU (P2) #544
Gemma 4 with transformers on a Kaggle GPU (2x T4). Kaggle's image has no vLLM (the competition's wheelhouse
dataset carries one, found later: see the correction above), and the QAT compressed-tensors model runs
out of memory on a T4, so this run uses `gemma-4-e4b-it` in fp16. `gemma_agent.py` reads and writes Gemma 4's own
tool-call format, as its chat template has it. This uses limited compute, so it waits for the owner (AGENTS.md
rule 6).

**No answers on Kaggle.** Kaggle blocks namespaces (`unshare` fails), and anything the agent runs can read every
attached file: the input mount is world-readable and read-only, so a second user can't be kept out (probed Nov 2026).
Later snapshots hold earlier tasks' fixes, and this repository's code is later than every task. So each task runs
alone, in its own private kernel with internet off, beside a private dataset holding only that task
(`kaggle/agent_bundle.py`):
- the prompt's fields, without the reference patch or tests;
- a one-commit snapshot (refused if its `.git` holds more);
- its graph and embeddings;
- the harness files no task changes (`agent_harness.py`, `gemma_agent.py`, `task_gate.py`), with a telemetry stub.

The patch comes back and is verified here, in the sandbox (`scripts/60_kaggle_agent.py`).

**Budgets.** These are the submission's 40 tool calls and 60 turns. The time budget is raised from 5 minutes to 30:
transformers on T4s generates about 8 tokens a second, far slower than the competition's evaluator. Thinking is off
and each turn gets at most 2,048 new tokens. Every row records the settings it ran with.

### US3 - Resolution rates per fidelity tier, labelled as ours (P2) #545
Overall and per tier (A, B, C), with and without the pipeline-doctor skill, recorded in spec 028 T012.

## Isolation (from the review before the PR)
Commands and verification run in a sandbox built from Linux user, mount, network and pid namespaces (`unshare`):
- the workspace at `/workspace`;
- the system and Python bound read-only;
- a private `/tmp`;
- no network;
- an environment of `PATH`, `HOME`, `LANG` and `PYTHONPATH` only.

Without it, a model could read this repository's history, which holds every fix, and the task files, which hold
every reference patch, from the host, as well as the host's tokens. A real model never runs without it
(`59_run_agent.py --sandbox required` is the default for anything that isn't `calib:`).

## Which tasks a model is scored on
A task counts toward a real model's resolution rate only if `calib:oracle` resolves it in the same environment, so
the denominator is what the harness can verify there. The rest are listed with their reason in the oracle's run
table: a test that needs a Postgres server, or R, skips there.

The run environment installs `python[dev,tasks,ml,track,stats,db,azure,otlp]`. Without the optional groups, tests
that need MLflow, statsmodels, psycopg or the Azure exporter skip, and the strict criterion counts a skipped
required test as unresolved.

## Known differences from the competition's harness
- Namespaces, not a Docker container. The sandbox brings up the namespace's own loopback, so tests that
  serve on 127.0.0.1 work. It also provides `/dev/shm` and `/dev/fd`, and names the host's user site-packages
  (`PYTHONUSERBASE`), since `HOME` is `/tmp`.
- No ADK: no context compaction or prefix caching.
- Sub-agents (`agent_tool`) and skills are not run. The runner lists them as left out.
- `PYTHONPATH=<workspace>/python` instead of an editable install, as the gate uses.
- Patch application tries five `git apply` variants, not the guide's four passes with GNU `patch`.
- Packages come from the host's Python, so `PYTHONNOUSERSITE` isn't set. `PYTHONSAFEPATH` isn't set either: this
  repository's tests run its scripts, which import the modules beside them, and the flag broke 7 tasks whose
  reference fix passes. `-p no:anyio` and `-o python_classes` are set.
- Snapshots get no `pytest.ini` or `conftest.py` written into them.
- Budgets default to gemma-developer-agent's `eval_config.yaml` (40 calls, 5 minutes, 60 turns, 120 s), not the
  guide's defaults.
- Resolved also requires every test function the test patch adds or changes to pass, not be skipped. That's the
  guide's criterion as we read it, without its FAIL_TO_PASS and PASS_TO_PASS lists.

## Out of scope
Submitting to the competition; LoRA training.

## Constitution check
No metric, label or data change. Synthetic data only: the tasks are code. Test-first. `@traced` on public
functions. Honest outputs: the calibration runs are named `calib:`, and every result names its harness.
