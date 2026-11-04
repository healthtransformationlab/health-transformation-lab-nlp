# Feature Specification: score an agent on our task set with a local copy of the documented harness

**Feature Branch**: `035-local-agent-harness`

**Created**: 2026-11-04

**Status**: draft; US1 implemented first

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
An OpenAI-compatible chat client with tool calls (vLLM serves Gemma 4 that way, with the `gemma4` tool parser),
run from a Kaggle GPU notebook. This uses limited compute, so it waits for the owner (AGENTS.md rule 6).

### US3 - Resolution rates per fidelity tier, labelled as ours (P2) #545
Overall and per tier (A, B, C), with and without the pipeline-doctor skill, recorded in spec 028 T012.

## Known differences from the competition's harness
- No Docker container: a temporary folder and subprocesses, like swegemma's subprocess backend.
- No ADK: no context compaction or prefix caching.
- Sub-agents (`agent_tool`) and skills are not run. The runner lists them as left out.
- `PYTHONPATH=<workspace>/python` instead of an editable install, as the gate uses.
- Patch application tries five `git apply` variants, not the guide's four passes with GNU `patch`.

## Out of scope
Submitting to the competition; LoRA training.

## Constitution check
No metric, label or data change. Synthetic data only: the tasks are code. Test-first. `@traced` on public
functions. Honest outputs: the calibration runs are named `calib:`, and every result names its harness.
