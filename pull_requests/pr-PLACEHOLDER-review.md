# PR review: 034 AI1, a public notebook that loads the coding-agent task set (#535)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

| Check | Result |
|---|---|
| Issue and branch | `Closes #535` once the notebook is live; branch `feat/535-034-tasks-notebook` |
| Test first | `tests/test_tasks_quickstart.py` (4 tests) failed before the notebook and the kernel job existed |
| Notebook | `notebooks/agent_tasks_quickstart.ipynb`: reads `tasks.jsonl`, shows a task's statement, patch and test patch, unpacks its snapshot (`filter="data"`), loads its graph and embeddings and lists the nearest symbols. CPU, no internet, numpy only (no networkx). Saved without outputs; says it is not affiliated |
| Real data | run here on files downloaded from the published dataset: 113 tasks, `htlnlp_100`'s snapshot unpacked, 576 symbols and 487 calls, sensible nearest symbols |
| Kaggle | `prepare_kernel.py --job tasks-quickstart`: public, CPU, internet off, the task set attached; `kaggle-publish-tasks.yml` pushes it and waits for its run, as `kaggle-publish.yml` does for the PerioBench quickstart |
| Publishing | merging publishes nothing: the notebook goes live when the owner runs the task-set workflow |
| Tests | full Python suite: 2158 passed |

Nothing blocking.
