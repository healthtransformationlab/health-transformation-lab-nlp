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

# The larger-budget rerun (November 10, 2026)

`gemma-4-e4b-it_larger_budget.csv` has one row per task that was run again with a larger budget, beside its run
under the tight limits (`../agent_runs/gemma-4-e4b-it_kaggle.csv`, the `tight_` columns). It answers one question:
do the tight limits (2,048 output tokens a turn, thinking off) decide the baseline's result? (Spec 035, issue #656.)

| | Tight limits (the baseline) | Larger budget |
|---|---|---|
| Hardware | two T4s (Kaggle), internet off | one L4 (Colab Pro+), internet on |
| Output tokens a turn | 2,048 | 16,384 |
| Thinking | off | on |
| Context | 24,576 tokens | 20,000 tokens (what an L4's 24 GB holds beside the weights) |
| Tool calls, turns, minutes, seconds a command | 40, 60, 30, 120 | 100, 500, 20, 300 |
| Harness | `htlnlp-harness-v1` | the same |

`python/scripts/62_colab_agent.py bundles` built one private bundle per task from the published task set (no
reference patch, no tests, one commit), `kaggle/colab_agent.ipynb` ran them one at a time, cheapest first by the tight
run's session time, and `62_colab_agent.py score` verified each patch here in the sandbox and wrote the table. The
`larger_` columns: when the task ran, whether its patch resolved the task, the patch's size, tool calls (the two free
tools not counted), calls to the three graph tools counted from the transcript, the largest output of any turn, turns
the model could not take because the prompt was past the context limit, the task's seconds on the GPU, and the GPU.

The run was read while still going: 23 of the 48 scored tasks had finished.

| 23 tasks, each run twice | Tight limits | Larger budget |
|---|---|---|
| Resolved | 2 | 2 |
| Wrote a patch | 19 | 20 |

With the larger budget: One of the 23 runs had a turn above 2,048 output tokens (the longest, 3,335), and one reached the context limit. 5 of 139 tool calls were to a graph tool, in 4 runs.
The 23 tasks took 2.1 hours on the one GPU.

Two differences favour neither side cleanly and are stated in the paper: the context is smaller than the baseline's,
and the notebook has network access, which Kaggle's kernels did not. No `run_command` in the 23 transcripts names
a network tool or address, and a command sees only an allow-listed environment (`agent_harness._env`), not the
notebook's Kaggle token. One sampled run per task at temperature 0.2. Measured with this repository's harness, not
the competition's evaluator.
