# PR 683 review: declare an L4 price, so the evaluator's runs carry an estimated cost (#569)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

| Check | Result |
|---|---|
| Branch `data/569-036-l4-price`, `Refs #569` (one part of US2, which stays open for T005) | ok |
| A setting changes by pull request, with its value, source and read date, and the pull request says which environments change: none. The setting is read by `71_run_telemetry.py` after a run, and by no job | ok |
| The price is read from the source's own weekly series (`getdeploying.com/dataset/gpu-prices/nvidia-l4.json`, CC BY 4.0, fetched November 11, 2026): on demand, week of October 26, 2026, median across providers 0.8319 over 14 providers; 0.83 declared | ok |
| It is the T4's figure and week: the same series for the T4 gives 0.691 over 10 providers that week, which is the 0.69 declared on November 4 | ok |
| Test first: `test_every_gpu_the_kernels_ran_on_has_a_declared_price` failed with "no price declared for NVIDIA L4" before the setting was added; a GPU with no declared price still gets no estimate and says why | ok |
| The four `_gpu.csv` tables were rebuilt from the same kernels' saved output; each was compared with the committed one: every column but `estimated_cost_usd` and `price_basis_text` is identical, and the section tables are unchanged byte for byte | ok |
| The numbers in the README and the description, recomputed from the rebuilt tables: 2.03, 6.37, 7.50 and 4.76 USD; 1.59 and 1.50 USD for each resolved task (6.37 / 4 and 7.50 / 5) | ok |
| Every place says estimate, never paid, and that Kaggle's GPUs were free; the estimate covers the tasks' own time, not the model's loading or the hours the `statement` kernel ran with a dead server | ok |
| `pytest -q -n auto tests`: 2,442 passed, 4 skipped | ok |
| Merging starts no run and publishes nothing; no rule changes; self-merge under AGENTS.md "Branches and issues", 6 | ok |
| The script reads the settings of the checkout its package is imported from. Run from a second worktree it read the first checkout's file until `PYTHONPATH` named the worktree; the first rebuild here wrote unchanged tables for that reason, and was repeated | note |

Nothing blocking.

## Notes
- The two prices are for one week (October 26, 2026), so the T4 and L4 estimates can be set side by side. The
  source's provisional figure for the week of November 9 is 0.59 for a T4 (13 providers) and 0.84 for an L4
  (18 providers). Moving both settings to a later week is its own pull request, and would move the T4 estimates
  already reported (0.53 and 2.49 USD for each resolved task).
- The source's page headline ("Median price (current)") is the provisional week's figure, and the median of each
  provider's cheapest on-demand offer on the page is lower (0.70 for an L4). The setting uses the series the T4's
  figure came from.
