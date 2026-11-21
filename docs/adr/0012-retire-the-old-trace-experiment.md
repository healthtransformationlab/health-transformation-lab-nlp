# ADR 0012: Retire the old trace experiment /Shared/gemma-agent-runs

Date: 2026-11-21 · Status: accepted · Issue: #896

## Context

Spec 041 moved the coding-agent traces from the experiment `/Shared/gemma-agent-runs`, in MLflow's default storage, to
`/Shared/coding-agent-runs`, whose traces live in Unity Catalog (`health_transformation_lab.ops_agent_trace`). FR-005
kept the old experiment as a backup until its traces were all in the new one, and left retiring it to an ADR.

The check on November 21, 2026:

- **Every run is in the new experiment.** The old experiment holds 414 traces across 14 run labels. All 14 labels are
  in the new experiment with at least as many traces each. One of them, `devset-e4b-colab-l4` (23 traces), was missing
  that morning and was reloaded with `kaggle/load_agent_traces.py` before the check was repeated.
- **Nothing in the old experiment is still needed.** It has the first assessments, from the code scorers before
  `SCORER_VERSION` 2026-11-17.2, and the swe_* scorers a Genie session registered. Every trace in the new experiment has
  been scored again at 2026-11-17.2, and the grounding judge reads failed runs there.
- **The new experiment has much more.** It holds 1,611 traces across 61 run labels, including every run since November
  17. The old one stopped receiving traces on November 19.

The owner, on November 21: delete the old experiment, and record the decision here. Two experiments with similar
names had caused confusion for days.

## Decision

- Delete `/Shared/gemma-agent-runs` (experiment `3270281325394338`). Databricks moves a deleted experiment to its trash,
  where it can be restored for 30 days.
- `/Shared/coding-agent-runs` is the only experiment for coding-agent traces, as the bundle declares
  (`databricks/resources/agent_traces.yml`). Nothing writes to the old name: the loader and the scorers read
  `AGENT_TRACE_EXPERIMENT`, whose default is the new experiment.

## Consequences

- One place to look for every run's traces, in the experiment's own pages, in SQL and in Genie.
- The first assessments made in the old experiment are gone once the trash is emptied. They were superseded by the
  rescoring and were never cited in a doc or result.
- A run that exists only in the old experiment can no longer be read from there. The check found none.

## Revisit when

- Someone needs a trace that is not in `/Shared/coding-agent-runs`: restore the old experiment from the trash within
  30 days, or reload the run from its Kaggle dataset with `kaggle/load_agent_traces.py`.
