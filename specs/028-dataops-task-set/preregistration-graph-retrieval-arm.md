# Pre-registration, addendum 1: a graph-retrieval arm

Spec 028, action item 7 (issue 674). An addendum to `preregistration-failing-test-report.md`, which is unchanged
(SHA-256 `1b517ae1bb96d84d670ac6891542278275a0802a33ac57dae43c0c715e43d7c4`). Frozen on November 11, 2026, while the
two arms of that plan were running and before any outcome of either had been read: their kernels write their
results when they end, and the patches are verified after that. The SHA-256 of this file as committed is recorded
on issue 674 before this arm's kernel starts.

## Why a third arm

A review of the paper asked for a controlled experiment on whether graph-guided retrieval improves an agent's
outcomes. The first plan's `report` arm is controlled, but its context comes from the task's hidden test. This arm's
context comes from the statement and the graph alone, so it is a condition a deployed agent could have. The agent
asks a graph tool on its own in about one tool call in twenty on these tasks; here the retrieval is done for it.

## The arm

| Arm | The task's text |
|---|---|
| `graph` | as published, with the graph's retrieval after its hints |

The retrieval is the output of `python/scripts/72_graph_context.py` at commit `00f3d81` on the published dataset
(version 4): up to 5 functions or classes the statement names (script 63's rule), up to 8 nodes one `calls` edge
from those in either direction, and the 10 nodes nearest the statement by embedding search (script 64's method:
EmbeddingGemma's query prompt against the published node vectors), each with the file that holds it. Nothing in it
comes from the reference patch or the tests.

Everything else is the first plan's: the same 93 tasks, agent, model, harness, budgets and seeded order, one kernel
on four L4 GPUs with telemetry on, started when one of the first two kernels ends (Kaggle runs two at a time).

## Outcome

The first plan's: resolved, by the competition's own `verify_task` on the published snapshot with the agent's patch.

## Analysis

Primary:

- `graph` against `statement`: resolved tasks in each arm with 95% Wilson intervals, the paired table, and the exact
  McNemar test, two-sided. "Graph retrieval helps" is claimed only at p < 0.05.

Two comparisons now share one baseline: `report` against `statement` (the first plan, its rule unchanged) and
`graph` against `statement`. Both p-values are reported. A reader who corrects for two comparisons can hold each to
0.025; the paper says which claims would survive that.

Described, not tested:

- the split by whether the retrieval listed a node the fix edits, among the 51 tasks whose fix edits code the
  graph holds; by whether the statement names any node; by the screen; and by the 20 of November 10;
- `graph` against `report`, as a paired table;
- the first plan's measures: patches, tool calls and graph-tool calls, tokens, seconds, GPU energy;
- **a core split**: the 17 tasks that pass the screen of all 93 (both ratings 0 or 1: the statement says what its
  tests check). Each arm's resolved count on those 17 is reported beside its count on all 93. The split was fixed
  by the screen of November 10 (`data/tasks/screening/agent_screen_all.csv`), before any of these runs.

## Exclusions and reruns

The first plan's.

## What was known when this was frozen

- Everything the first plan lists.
- Where this retrieval points, as counts from files: it lists a node the fix edits in 41 of the 51 tasks whose
  fix edits code the graph holds (`data/tasks/graph_context_shape.csv`), and names at least one node in 54 of
  the 93.
- No outcome of the `statement` or `report` arm: both kernels started at 14:44 UTC and were still running.

## Pinned input

| Input | SHA-256 |
|---|---|
| The graph context file (93 tasks, one retrieval each) | `f4d3f1c00a649936d1885016a4dae49b63f10f5508659558056d222fd14d33fc` |
