# Paired reruns of the Gemma agent (November 10, 2026)

`gemma-4-e4b-it_graph_tools.csv` has one row per task that was run twice with the same model and settings: once
before the harness fault of #621 was fixed, when a task's code graph and embeddings were not shipped and the three
graph tools had nothing to query, and once after, with them (workflow run 42742256439, 28 tasks; a cap on GPU hours
stopped it before the other five it was given).

A rerun replaces its task's row in `../agent_runs/gemma-4-e4b-it_kaggle.csv` (spec 036), so the first run of each of
these tasks would otherwise be in git history only. The `first_` columns are that table's row at commit `db0a29d`,
the `rerun_` columns its row now. `rerun_graph_tool_call_count` counts calls to `get_code_neighbors`,
`search_similar_code` and `get_code_subgraph` in the run's saved transcript (`result.json`, in the task's private
Kaggle notebook). `is_rerun_evaluator_resolved` is the competition's evaluator on the rerun's patch, from
`../official_verifier/published_verification.csv`; it is empty for the five tasks that are not in the published set.

On the 23 published tasks:

| | First run (no graph tools) | Rerun (graph tools available) |
|---|---|---|
| Resolved | 2 | 2 |
| Wrote a patch | 18 | 20 |
| GPU-hours per task, mean | 0.21 | 0.35 |

One task was resolved only the first time (`htlnlp_144`), one only the second (`htlnlp_226`), and one both times
(`htlnlp_pr63`). With the tools available the model called one in 4 of the 23 runs: 6 calls, all
`search_similar_code`, among 145 tool calls. The competition's evaluator gives the same verdict as
`htlnlp-harness-v1` on all 23 rerun patches.

One run each, sampled at temperature 0.2, so a task that flips is within run-to-run variation. This says the graph
tools made no measurable difference to this model at these settings, mostly because it did not use them. It does not
say what they are worth to a model that is prompted to use them.

Measured with this repository's harness (`htlnlp-harness-v1`), not the competition's evaluator, except the last
column.
